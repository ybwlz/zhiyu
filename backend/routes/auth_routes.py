# -*- coding: utf-8 -*-
"""认证：邮箱验证码注册 / 登录 / 改密 / 换绑 / 修改 ID / me / logout"""
from flask import Blueprint, request, jsonify
import re
import secrets
import hmac
from datetime import datetime, timedelta
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash

from config import DEV_MODE, SMTP_HOST, SMTP_USER
from db import get_conn
from auth import (EMAIL_CODES, CODE_TTL, CODE_RESEND, CODE_MAX_TRIES,
                  send_email_code, issue_token, get_current_user, require_login)
from utils import gen_public_id

bp = Blueprint('auth', __name__)

# ── 登录防爆破（内存，重启失效） ──
LOGIN_FAILS = {}   # 归一化账号 -> {'count': n, 'lock_until': datetime}
CODE_SEND_IP = {}  # 客户端 ip -> {'last': datetime}


def _login_locked(key):
    rec = LOGIN_FAILS.get(key)
    return bool(rec and rec.get('lock_until') and datetime.now() < rec['lock_until'])


def _login_fail(key):
    rec = LOGIN_FAILS.get(key) or {'count': 0, 'lock_until': None}
    rec['count'] = rec.get('count', 0) + 1
    if rec['count'] >= 5:
        rec['lock_until'] = datetime.now() + timedelta(minutes=10)
        rec['count'] = 0
    LOGIN_FAILS[key] = rec


def _login_ok(key):
    LOGIN_FAILS.pop(key, None)

@bp.route('/api/auth/send-code', methods=['POST'])
def auth_send_code():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    if not re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', email):
        return jsonify({'error': '邮箱格式不正确'}), 400
    now = datetime.now()
    # IP 维度限流：同一 IP 5 秒内只能发一次（防刷邮件）
    ip = request.remote_addr or ''
    ip_prev = CODE_SEND_IP.get(ip)
    if ip_prev and now - ip_prev['last'] < timedelta(seconds=5):
        return jsonify({'error': '发送太频繁，请稍后再试'}), 429
    CODE_SEND_IP[ip] = {'last': now}
    prev = EMAIL_CODES.get(email)
    if prev and prev['last_sent'] and now - prev['last_sent'] < CODE_RESEND:
        return jsonify({'error': '发送太频繁，请 60 秒后再试'}), 429
    code = f'{secrets.randbelow(1000000):06d}'
    EMAIL_CODES[email] = {'code': code, 'expires': now + CODE_TTL, 'last_sent': now}
    sent = send_email_code(email, code)
    resp = {'success': True, 'sent': sent}
    # 仅「开发模式 + 未配置 SMTP（本地发不出信）」才回显验证码；配了 SMTP（生产）即使 DEV_MODE=1 也严格不返回
    if not sent and DEV_MODE and not (SMTP_HOST and SMTP_USER):
        print(f'[DEV] 验证码 for {email}: {code}')
        resp['dev_code'] = code  # 仅开发模式返回，方便本地测试
    return jsonify(resp)

@bp.route('/api/auth/register', methods=['POST'])
def auth_register():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    code = (data.get('code') or '').strip()
    nickname = (data.get('nickname') or '').strip()
    if not re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', email):
        return jsonify({'error': '邮箱格式不正确'}), 400
    if len(password) < 6:
        return jsonify({'error': '密码至少 6 位'}), 400
    rec = EMAIL_CODES.get(email)
    if not rec or rec['expires'] < datetime.now():
        return jsonify({'error': '验证码已过期，请重新获取'}), 400
    if not hmac.compare_digest(rec['code'], code):
        rec['tries'] = rec.get('tries', 0) + 1
        if rec['tries'] >= CODE_MAX_TRIES:
            EMAIL_CODES.pop(email, None)
            return jsonify({'error': '验证码错误次数过多，请重新获取'}), 400
        return jsonify({'error': '验证码错误'}), 400
    # username 自动生成（邮箱前缀，冲突加短随机串），内部标识用
    base = email.split('@')[0]
    username = base[:40]
    username = re.sub(r'[^A-Za-z0-9_]', '_', username) or 'user'
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM users")
            is_first = cur.fetchone()['cnt'] == 0
            role = 'admin' if is_first else 'user'
            final_user = username
            if not is_first:
                cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE username=%s", (final_user,))
                if cur.fetchone()['cnt'] > 0:
                    final_user = f'{username[:32]}_{secrets.token_hex(3)}'
            cur.execute(
                "INSERT INTO users (username, password_hash, role, nickname, email, email_verified, public_id) VALUES (%s, %s, %s, %s, %s, 1, %s)",
                (final_user, generate_password_hash(password), role, nickname or None, email, gen_public_id())
            )
            new_id = cur.lastrowid
            # AI 官方账号自动关注新用户
            cur.execute("INSERT IGNORE INTO follows (follower_id, followee_id) SELECT id, %s FROM users WHERE username='ai'", (new_id,))
        conn.commit()
        EMAIL_CODES.pop(email, None)
    except pymysql.err.IntegrityError:
        conn.rollback()
        return jsonify({'error': '该邮箱已注册'}), 409
    finally:
        conn.close()
    return jsonify({'success': True, 'role': role})

@bp.route('/api/auth/code-login', methods=['POST'])
def auth_code_login():
    """验证码登录即注册：邮箱+验证码。首次使用自动创建账号（须同意条款）；老用户直接登录"""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    code = (data.get('code') or '').strip()
    agree = data.get('agree') is True
    if not re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', email):
        return jsonify({'error': '邮箱格式不正确'}), 400
    rec = EMAIL_CODES.get(email)
    if not rec or rec['expires'] < datetime.now():
        return jsonify({'error': '验证码已过期，请重新获取'}), 400
    if not hmac.compare_digest(rec['code'], code):
        rec['tries'] = rec.get('tries', 0) + 1
        if rec['tries'] >= CODE_MAX_TRIES:
            EMAIL_CODES.pop(email, None)
            return jsonify({'error': '验证码错误次数过多，请重新获取'}), 400
        return jsonify({'error': '验证码错误'}), 400
    # 先查用户、校验条款（此时不消费验证码，未勾选可重试）
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, role, nickname, email, avatar, cover, public_id FROM users WHERE email=%s",
                (email,)
            )
            user = cur.fetchone()
            if not user:
                # 首次使用：自动创建账号（需已同意条款）；无密码，登录后可在设置中设置密码
                if not agree:
                    return jsonify({'error': '请先阅读并同意《服务条款》和《隐私协议》'}), 400
                base = email.split('@')[0]
                username = re.sub(r'[^A-Za-z0-9_]', '_', base[:40]) or 'user'
                cur.execute("SELECT COUNT(*) AS cnt FROM users")
                is_first = cur.fetchone()['cnt'] == 0
                role = 'admin' if is_first else 'user'
                final_user = username
                if not is_first:
                    cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE username=%s", (final_user,))
                    if cur.fetchone()['cnt'] > 0:
                        final_user = f'{username[:32]}_{secrets.token_hex(3)}'
                cur.execute(
                    "INSERT INTO users (username, password_hash, role, nickname, email, email_verified, public_id) VALUES (%s, %s, %s, %s, %s, 1, %s)",
                    (final_user, '', role, base[:20] or None, email, gen_public_id())
                )
                new_id = cur.lastrowid
                # AI 官方账号自动关注新用户
                cur.execute("INSERT IGNORE INTO follows (follower_id, followee_id) SELECT id, %s FROM users WHERE username='ai'", (new_id,))
                conn.commit()
                cur.execute(
                    "SELECT id, username, password_hash, role, nickname, email, avatar, cover, public_id FROM users WHERE id=%s",
                    (new_id,)
                )
                user = cur.fetchone()
    finally:
        conn.close()
    # 登录/建号成功后才消费验证码
    EMAIL_CODES.pop(email, None)
    token = issue_token(user['username'])
    return jsonify({'token': token, 'user': {
        'id': user['id'], 'username': user['username'], 'role': user['role'], 'nickname': user['nickname'], 'email': user['email'], 'avatar': user['avatar'], 'cover': user['cover'], 'public_id': user['public_id']
    }})

@bp.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.get_json(silent=True) or {}
    raw = (data.get('email') or data.get('username') or '').strip()
    password = data.get('password') or ''
    # 邮箱不区分大小写；用户名区分大小写（修复大写用户名无法登录）
    email_part = raw.lower()
    if _login_locked(email_part):
        return jsonify({'error': '尝试次数过多，请 10 分钟后再试'}), 429
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, role, nickname, email, avatar, cover, public_id FROM users WHERE email=%s OR username=%s",
                (email_part, raw)
            )
            user = cur.fetchone()
    finally:
        conn.close()

    if not user or not user['password_hash'] or not check_password_hash(user['password_hash'], password):
        _login_fail(email_part)
        return jsonify({'error': '账号或密码错误'}), 401
    _login_ok(email_part)
    token = issue_token(user['username'])
    return jsonify({'token': token, 'user': {
        'id': user['id'], 'username': user['username'], 'role': user['role'], 'nickname': user['nickname'], 'email': user['email'], 'avatar': user['avatar'], 'cover': user['cover'], 'public_id': user['public_id']
    }})

@bp.route('/api/auth/change-password', methods=['POST'])
@require_login
def auth_change_password(user=None):
    # 修改密码：校验旧密码后更新
    data = request.get_json(silent=True) or {}
    old_pw = data.get('old_password') or ''
    new_pw = data.get('new_password') or ''
    if len(new_pw) < 6:
        return jsonify({'error': '新密码至少 6 位'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT password_hash FROM users WHERE id=%s', (user['id'],))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': '账号不存在'}), 400
            # 未设置过密码（验证码注册用户）：免旧密码直接设置
            if row['password_hash'] and not check_password_hash(row['password_hash'], old_pw):
                return jsonify({'error': '旧密码不正确'}), 400
            cur.execute('UPDATE users SET password_hash=%s WHERE id=%s',
                        (generate_password_hash(new_pw), user['id']))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True})

@bp.route('/api/auth/update-email', methods=['POST'])
@require_login
def auth_update_email(user=None):
    """绑定/更换邮箱：校验邮箱验证码后更新（邮箱唯一）"""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    code = (data.get('code') or '').strip()
    if not re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', email):
        return jsonify({'error': '邮箱格式不正确'}), 400
    rec = EMAIL_CODES.get(email)
    if not rec or rec['expires'] < datetime.now():
        return jsonify({'error': '验证码已过期，请重新获取'}), 400
    if not hmac.compare_digest(rec['code'], code):
        rec['tries'] = rec.get('tries', 0) + 1
        if rec['tries'] >= CODE_MAX_TRIES:
            EMAIL_CODES.pop(email, None)
            return jsonify({'error': '验证码错误次数过多，请重新获取'}), 400
        return jsonify({'error': '验证码错误'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email=%s AND id<>%s", (email, user['id']))
            if cur.fetchone():
                return jsonify({'error': '该邮箱已被其他账号使用'}), 409
            cur.execute("UPDATE users SET email=%s, email_verified=1 WHERE id=%s", (email, user['id']))
        conn.commit()
        EMAIL_CODES.pop(email, None)
    finally:
        conn.close()
    return jsonify({'success': True, 'email': email})

@bp.route('/api/auth/update-username', methods=['POST'])
@require_login
def auth_update_username(user=None):
    """修改 ID（@用户名）：字母数字下划线 3-32 位，每月仅可修改一次"""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    if not re.match(r'^[A-Za-z0-9_]{3,32}$', username):
        return jsonify({'error': 'ID 仅限字母、数字、下划线，长度 3-32 位'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT username_changed_at FROM users WHERE id=%s", (user['id'],))
            row = cur.fetchone()
            last = row['username_changed_at']
            if last:
                days = (datetime.now() - last).days
                if days < 30:
                    return jsonify({'error': f'每月只能修改一次 ID，还需 {30 - days} 天'}), 400
            cur.execute("SELECT id FROM users WHERE username=%s AND id<>%s", (username, user['id']))
            if cur.fetchone():
                return jsonify({'error': '该 ID 已被其他人使用'}), 409
            cur.execute("UPDATE users SET username=%s, username_changed_at=NOW() WHERE id=%s", (username, user['id']))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'username': username})

@bp.route('/api/auth/me', methods=['GET'])
def auth_me():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'unauthorized'}), 401
    # 附带是否已设置密码（验证码注册的无密码用户据此提示设置密码）
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash FROM users WHERE id=%s", (user['id'],))
            row = cur.fetchone()
            user['has_password'] = bool(row and row['password_hash'])
    finally:
        conn.close()
    return jsonify(user)

@bp.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    auth = request.headers.get('Authorization', '')
    token = auth[7:] if auth.startswith('Bearer ') else auth
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tokens WHERE token=%s", (token,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True})
