# -*- coding: utf-8 -*-
"""认证与会话：邮箱验证码、token 签发/校验、登录装饰器。"""
import re
import secrets
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify

from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM
from db import get_conn

SESSION_TTL = timedelta(days=7)

# ── 邮箱验证码 ─────────────────────────────
# EMAIL_CODES[email] = {'code': '123456', 'expires': datetime, 'last_sent': datetime}
EMAIL_CODES = {}
CODE_TTL = timedelta(minutes=10)
CODE_RESEND = timedelta(seconds=60)
CODE_MAX_TRIES = 5  # 验证码最多尝试次数，防爆破

def send_email_code(to_email, code):
    """发送验证码邮件；未配置 SMTP 时返回 False（由调用方落到控制台/dev_code）"""
    if not SMTP_HOST or not SMTP_USER:
        return False
    subject = '【知屿】邮箱验证码'
    body = f'你的知屿注册验证码是：{code}（10 分钟内有效）。如果不是你本人操作，请忽略本邮件。'
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = SMTP_FROM
    msg['To'] = to_email
    try:
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10)
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_FROM, [to_email], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print('[send_email_code] 失败:', e)
        return False

def issue_token(username):
    """签发登录 token：写入数据库（服务重启仍有效，7 天过期）"""
    token = secrets.token_hex(24)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (username,))
            r = cur.fetchone()
            if not r:
                return token
            cur.execute("INSERT INTO tokens (token, user_id, expires_at) VALUES (%s, %s, %s)",
                        (token, r['id'], datetime.now() + SESSION_TTL))
            # 顺带清理过期 token，防止表无限增长
            cur.execute("DELETE FROM tokens WHERE expires_at < NOW()")
        conn.commit()
    finally:
        conn.close()
    return token

def get_current_user():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:]
    else:
        token = auth
    if not token:
        return None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT u.id, u.username, u.role, u.nickname, u.email, u.avatar, u.cover, u.public_id, u.likes_public, u.favorites_public
                FROM tokens t JOIN users u ON u.id = t.user_id
                WHERE t.token=%s""", (token,))
            row = cur.fetchone()
            if row:
                cur.execute("SELECT expires_at FROM tokens WHERE token=%s", (token,))
                exp = cur.fetchone()['expires_at']
                if exp < datetime.now():
                    cur.execute("DELETE FROM tokens WHERE token=%s", (token,))
                    conn.commit()
                    row = None
    finally:
        conn.close()
    return row

def require_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'unauthorized'}), 401
        return f(user=user, *args, **kwargs)
    return wrapper
