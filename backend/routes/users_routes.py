# -*- coding: utf-8 -*-
"""用户主页 / 资料 / 头像封面 / 今日概览 / 知屿币 / 热力图"""
from flask import Blueprint, request, jsonify
import os
import secrets

from config import FREE_AI_QUOTA, UPLOAD_FOLDER
from db import get_conn
from auth import get_current_user, require_login
from utils import DOC_SELECT

bp = Blueprint('users', __name__)

@bp.route('/api/users/by-key/<key>', methods=['GET'])
def user_by_key(key: str):
    """按对外 key（public_id）取用户；兼容旧链接（数字 id / 用户名）。"""
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE public_id=%s OR username=%s OR id=%s LIMIT 1", (key, key, key))
                r = cur.fetchone()
        finally:
            conn.close()
        if not r:
            return jsonify({'error': 'not_found'}), 404
        return user_profile(r['id'])
    except Exception as e:
        print('[ERROR]', e)
        return jsonify({'error': 'server_error'}), 500

@bp.route('/api/users/<int:uid>', methods=['GET'])
def user_profile(uid):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id, username, nickname, avatar, cover, bio, interests, points, read_seconds, badge, public_id, role,
                likes_public, favorites_public,
                CAST(created_at AS CHAR) AS created_at FROM users WHERE id=%s""", (uid,))
            u = cur.fetchone()
            if not u:
                return jsonify({'error': 'not_found'}), 404
            cur.execute("SELECT COUNT(*) AS c FROM docs WHERE user_id=%s AND visibility='public'", (uid,))
            u['public_notes'] = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) AS c FROM docs WHERE user_id=%s", (uid,))
            u['total_notes'] = cur.fetchone()['c']
            # 隐私：他人访问时不暴露私有笔记数
            viewer = get_current_user()
            if not (viewer and viewer['id'] == uid):
                u.pop('total_notes', None)
            cur.execute("""SELECT COUNT(*) AS c FROM note_likes l
                JOIN docs d ON l.doc_id=d.id WHERE d.user_id=%s""", (uid,))
            u['received_likes'] = cur.fetchone()['c']
            cur.execute("""SELECT COUNT(*) AS c FROM friendships WHERE (user_id=%s OR friend_id=%s) AND status='accepted'""", (uid, uid))
            u['friends_count'] = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) AS c FROM follows WHERE follower_id=%s", (uid,))
            u['following_count'] = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) AS c FROM follows WHERE followee_id=%s", (uid,))
            u['followers_count'] = cur.fetchone()['c']
            u['is_following'] = False
            if viewer:
                cur.execute("SELECT id FROM follows WHERE follower_id=%s AND followee_id=%s", (viewer['id'], uid))
                u['is_following'] = bool(cur.fetchone())
    finally:
        conn.close()
    return jsonify(u)

@bp.route('/api/users/<int:uid>/notes', methods=['GET'])
def user_notes(uid):
    """主页笔记：?scope=public（默认，公开）/ mine（自己的全部，仅本人）"""
    viewer = get_current_user()
    scope = request.args.get('scope', 'public')
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if scope == 'mine':
                if not viewer or viewer['id'] != uid:
                    return jsonify({'error': 'forbidden'}), 403
                cur.execute(DOC_SELECT + " FROM docs d LEFT JOIN users u ON d.user_id=u.id WHERE d.user_id=%s ORDER BY d.updated_at DESC", (uid,))
            else:
                cur.execute(DOC_SELECT + " FROM docs d LEFT JOIN users u ON d.user_id=u.id WHERE d.user_id=%s AND d.visibility='public' ORDER BY d.updated_at DESC", (uid,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify(rows)

@bp.route('/api/users/<int:uid>/favorites', methods=['GET'])
def user_favorites(uid):
    """TA 收藏的公开笔记（用户关闭收藏公开则他人不可见）"""
    viewer = get_current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT favorites_public FROM users WHERE id=%s", (uid,))
            row = cur.fetchone()
            if row and not row['favorites_public'] and not (viewer and viewer['id'] == uid):
                return jsonify([])
            cur.execute(DOC_SELECT + """ FROM docs d
                LEFT JOIN users u ON d.user_id=u.id
                JOIN note_favorites f ON f.doc_id=d.id
                WHERE f.user_id=%s AND d.visibility='public'
                ORDER BY f.created_at DESC""", (uid,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify(rows)

@bp.route('/api/users/<int:uid>/likes', methods=['GET'])
def user_likes(uid):
    """TA 点赞的公开笔记（用户关闭点赞公开则他人不可见）"""
    viewer = get_current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT likes_public FROM users WHERE id=%s", (uid,))
            row = cur.fetchone()
            if row and not row['likes_public'] and not (viewer and viewer['id'] == uid):
                return jsonify([])
            cur.execute(DOC_SELECT + """ FROM docs d
                LEFT JOIN users u ON d.user_id=u.id
                JOIN note_likes l ON l.doc_id=d.id
                WHERE l.user_id=%s AND d.visibility='public'
                ORDER BY l.created_at DESC""", (uid,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify(rows)

@bp.route('/api/user/profile', methods=['PUT'])
@require_login
def update_profile(user=None):
    data = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 未传的字段保持原值（避免只改隐私时清空资料）
            cur.execute("SELECT nickname, bio, interests, avatar, likes_public, favorites_public FROM users WHERE id=%s", (user['id'],))
            row = cur.fetchone()
            nickname = row['nickname'] if data.get('nickname') is None else ((data.get('nickname') or '').strip()[:32] or None)
            bio = row['bio'] if data.get('bio') is None else ((data.get('bio') or '').strip()[:200] or None)
            interests = row['interests'] if data.get('interests') is None else ((data.get('interests') or '').strip()[:200] or None)
            avatar = row['avatar'] if data.get('avatar') is None else ((data.get('avatar') or '').strip()[:255] or None)
            likes_public = row['likes_public'] if data.get('likes_public') is None else (1 if data.get('likes_public') else 0)
            favorites_public = row['favorites_public'] if data.get('favorites_public') is None else (1 if data.get('favorites_public') else 0)
            cur.execute("UPDATE users SET nickname=%s, bio=%s, interests=%s, avatar=%s, likes_public=%s, favorites_public=%s WHERE id=%s",
                        (nickname, bio, interests, avatar, likes_public, favorites_public, user['id']))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'likes_public': likes_public, 'favorites_public': favorites_public})

@bp.route('/api/user/avatar', methods=['POST'])
@require_login
def upload_avatar(user=None):
    """头像上传（multipart file=avatar），存 uploads/avatars/，返回访问路径"""
    file = request.files.get('avatar')
    if not file or not file.filename:
        return jsonify({'error': 'bad_request'}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        return jsonify({'error': '仅支持图片格式'}), 400
    # 头像大小限制 2MB（先读流校验再落盘，防超大文件）
    data = file.read()
    if len(data) > 2 * 1024 * 1024:
        return jsonify({'error': '头像图片不能超过 2MB'}), 400
    if not data:
        return jsonify({'error': 'bad_request'}), 400
    avatar_dir = os.path.join(UPLOAD_FOLDER, 'avatars')
    os.makedirs(avatar_dir, exist_ok=True)
    fname = f"u{user['id']}_{secrets.token_hex(6)}{ext}"
    with open(os.path.join(avatar_dir, fname), 'wb') as f:
        f.write(data)
    path = f"/uploads/avatars/{fname}"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET avatar=%s WHERE id=%s", (path, user['id']))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'avatar': path})

@bp.route('/api/user/cover', methods=['POST'])
@require_login
def upload_cover(user=None):
    # 主页背景上传（multipart file=cover），存 uploads/covers/，返回访问路径
    file = request.files.get('cover')
    if not file or not file.filename:
        return jsonify({'error': 'bad_request'}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        return jsonify({'error': '仅支持图片格式'}), 400
    # 封面大小限制 5MB（先读流校验再落盘，防超大文件）
    data = file.read()
    if len(data) > 5 * 1024 * 1024:
        return jsonify({'error': '封面图片不能超过 5MB'}), 400
    if not data:
        return jsonify({'error': 'bad_request'}), 400
    cover_dir = os.path.join(UPLOAD_FOLDER, 'covers')
    os.makedirs(cover_dir, exist_ok=True)
    fname = "u" + str(user['id']) + "_" + secrets.token_hex(6) + ext
    with open(os.path.join(cover_dir, fname), 'wb') as f:
        f.write(data)
    path = "/uploads/covers/" + fname
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE users SET cover=%s WHERE id=%s', (path, user['id']))
            cur.execute('SELECT id FROM user_covers WHERE user_id=%s AND cover=%s', (user['id'], path))
            if not cur.fetchone():
                cur.execute('INSERT INTO user_covers (user_id, cover) VALUES (%s, %s)', (user['id'], path))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'cover': path})

@bp.route('/api/user/covers', methods=['GET'])
@require_login
def user_cover_history(user=None):
    # QQ 风格：返回该用户全部历史背景，current 标记当前生效项
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT cover, CAST(created_at AS CHAR) AS created_at FROM user_covers WHERE user_id=%s ORDER BY id DESC', (user['id'],))
            rows = cur.fetchall()
            cur.execute('SELECT cover FROM users WHERE id=%s', (user['id'],))
            current = (cur.fetchone() or {}).get('cover')
    finally:
        conn.close()
    for r in rows:
        r['current'] = (r['cover'] == current)
    return jsonify({'covers': rows})

@bp.route('/api/user/cover/apply', methods=['POST'])
@require_login
def apply_cover(user=None):
    # 应用历史背景或系统预设背景
    data = request.get_json(silent=True) or {}
    cover = (data.get('cover') or '').strip()[:255]
    if not cover:
        return jsonify({'error': 'bad_request'}), 400
    allowed = cover.startswith('/uploads/presets/')
    if not allowed:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT id FROM user_covers WHERE user_id=%s AND cover=%s', (user['id'], cover))
                allowed = bool(cur.fetchone())
        finally:
            conn.close()
    if not allowed:
        return jsonify({'error': '该背景不属于你'}), 403
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE users SET cover=%s WHERE id=%s', (cover, user['id']))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'cover': cover})

@bp.route('/api/user/cover/reset', methods=['POST'])
@require_login
def reset_cover(user=None):
    # 恢复为初始背景（无 cover，显示系统默认渐变）
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE users SET cover=NULL WHERE id=%s', (user['id'],))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True})

@bp.route('/api/user/today', methods=['GET'])
@require_login
def user_today(user=None):
    """今日概览：今日阅读分钟、AI 已用/额度、知屿币"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT points, ai_used, ai_quota_bonus FROM users WHERE id=%s", (user['id'],))
            u = cur.fetchone()
            cur.execute("""SELECT COALESCE(SUM(seconds), 0) AS secs FROM read_logs
                           WHERE user_id=%s AND created_at >= CURDATE()""", (user['id'],))
            today_read = cur.fetchone()['secs'] or 0
    finally:
        conn.close()
    return jsonify({
        'points': u['points'],
        'ai_used': u['ai_used'],
        'ai_quota': FREE_AI_QUOTA + (u['ai_quota_bonus'] or 0),
        'today_read_min': int(today_read) // 60,
    })

@bp.route('/api/user/points', methods=['GET'])
@require_login
def user_points(user=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT points FROM users WHERE id=%s", (user['id'],))
            total = cur.fetchone()['points']
            cur.execute("""SELECT delta, reason, CAST(created_at AS CHAR) AS created_at
                FROM point_logs WHERE user_id=%s ORDER BY created_at DESC LIMIT 50""", (user['id'],))
            logs = cur.fetchall()
    finally:
        conn.close()
    return jsonify({'points': total, 'logs': logs})

# ── 学习热力图：最近 N 天阅读时长（本人及他人主页展示，需登录） ──
@bp.route('/api/user/heatmap', methods=['GET'])
@require_login
def user_heatmap(user=None):
    # 他人主页也展示热力图（产品需求）；登录即可查看任意用户阅读热力图
    uid = request.args.get('uid', type=int) or user['id']
    days = 90
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT DATE(created_at) AS d, SUM(seconds) AS secs, COUNT(*) AS cnt
                FROM read_logs WHERE user_id=%s AND created_at >= CURDATE() - INTERVAL %s DAY
                GROUP BY DATE(created_at)""", (uid, days))
            rows = cur.fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        out.append({'date': str(r['d']), 'seconds': int(r['secs'] or 0), 'count': int(r['cnt'] or 0)})
    return jsonify({'days': days, 'data': out})
