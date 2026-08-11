# -*- coding: utf-8 -*-
"""通知 / 好友 / 关注"""
from flask import Blueprint, request, jsonify

from db import get_conn
from auth import get_current_user, require_login
from utils import notify

bp = Blueprint('social', __name__)

@bp.route('/api/notifications', methods=['GET'])
@require_login
def notifications_list(user=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT n.id, n.type, n.doc_id, d.public_id, n.is_read, n.extra, CAST(n.created_at AS CHAR) AS created_at,
                u.nickname, u.username, u.public_id AS actor_public_id, d.title AS doc_title
                FROM notifications n
                LEFT JOIN users u ON n.actor_id=u.id
                LEFT JOIN docs d ON n.doc_id=d.id
                WHERE n.user_id=%s ORDER BY n.created_at DESC LIMIT 30""", (user['id'],))
            rows = cur.fetchall()
            cur.execute("SELECT COUNT(*) AS c FROM notifications WHERE user_id=%s AND is_read=0", (user['id'],))
            unread = cur.fetchone()['c']
    finally:
        conn.close()
    return jsonify({'list': rows, 'unread': unread})

@bp.route('/api/notifications/read', methods=['POST'])
@require_login
def notifications_read(user=None):
    """标记全部已读（或指定 id）"""
    data = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if data.get('id'):
                cur.execute("UPDATE notifications SET is_read=1 WHERE id=%s AND user_id=%s", (data['id'], user['id']))
            else:
                cur.execute("UPDATE notifications SET is_read=1 WHERE user_id=%s", (user['id'],))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True})

# ── 好友系统 ──
@bp.route('/api/friends/request', methods=['POST'])
@require_login
def friend_request(user=None):
    data = request.get_json(silent=True) or {}
    raw = str(data.get('user_id') or '').strip()
    if not raw:
        return jsonify({'error': '请输入用户 ID'}), 400
    if raw == str(user['id']) or raw == user['username']:
        return jsonify({'error': '不能添加自己'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 只按 ID（@用户名）查；系统编号不对外
            cur.execute("SELECT id FROM users WHERE username=%s", (raw,))
            r = cur.fetchone()
            friend_id = r['id'] if r else None
            if friend_id is None:
                return jsonify({'error': '用户不存在'}), 404
            # 反向是否已存在（对方加过我）
            cur.execute("SELECT id, user_id, friend_id, status FROM friendships WHERE (user_id=%s AND friend_id=%s) OR (user_id=%s AND friend_id=%s)",
                        (user['id'], friend_id, friend_id, user['id']))
            exist = cur.fetchone()
            if exist:
                if exist['status'] == 'accepted':
                    return jsonify({'error': '已是好友'}), 409
                if exist['user_id'] == friend_id:  # 对方已申请我 → 直接成为好友
                    cur.execute("UPDATE friendships SET status='accepted' WHERE id=%s", (exist['id'],))
                    conn.commit()
                    return jsonify({'success': True, 'auto_accepted': True})
                return jsonify({'error': '已发送过申请'}), 409
            cur.execute("INSERT INTO friendships (user_id, friend_id, status) VALUES (%s, %s, 'pending')",
                        (user['id'], friend_id))
        notify(conn, friend_id, user['id'], 'friend_request')
        conn.commit()
        return jsonify({'success': True})
    finally:
        conn.close()

@bp.route('/api/friends', methods=['GET'])
@require_login
def friend_list(user=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT f.id, f.status, f.created_at,
                u.id AS other_id, u.username, u.nickname, u.avatar, u.bio, u.points, u.public_id AS other_public_id
                FROM friendships f JOIN users u ON u.id = IF(f.user_id=%s, f.friend_id, f.user_id)
                WHERE (f.user_id=%s OR f.friend_id=%s)
                ORDER BY f.created_at DESC""", (user['id'], user['id'], user['id']))
            rows = cur.fetchall()
            # 区分：发给我的（user_id=对方）
            cur.execute("""SELECT f.id, f.status, u.id AS other_id, u.username, u.nickname, u.avatar, u.public_id AS other_public_id
                FROM friendships f JOIN users u ON u.id=f.user_id
                WHERE f.friend_id=%s AND f.status='pending'""", (user['id'],))
            incoming = cur.fetchall()
    finally:
        conn.close()
    return jsonify({'list': rows, 'incoming': incoming})

@bp.route('/api/friends/<int:rid>', methods=['POST'])
@require_login
def friend_respond(rid, user=None):
    """同意/拒绝好友申请：{action: accept|reject}"""
    data = request.get_json(silent=True) or {}
    action = data.get('action')
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, user_id, friend_id FROM friendships WHERE id=%s AND friend_id=%s", (rid, user['id']))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'not_found'}), 404
            if action == 'accept':
                cur.execute("UPDATE friendships SET status='accepted' WHERE id=%s", (rid,))
            elif action == 'reject':
                cur.execute("DELETE FROM friendships WHERE id=%s", (rid,))
            else:
                return jsonify({'error': 'bad_action'}), 400
        conn.commit()
        return jsonify({'success': True})
    finally:
        conn.close()

@bp.route('/api/friends/<int:rid>', methods=['DELETE'])
@require_login
def friend_remove(rid, user=None):
    """删除好友（双向解除）"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, user_id, friend_id FROM friendships WHERE id=%s AND (user_id=%s OR friend_id=%s)", (rid, user['id'], user['id']))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'not_found'}), 404
            cur.execute("DELETE FROM friendships WHERE id=%s", (rid,))
        conn.commit()
        return jsonify({'success': True})
    finally:
        conn.close()

# ═══════════════ 单向关注（follow） ═══════════════
@bp.route('/api/follows/toggle', methods=['POST'])
@require_login
def follow_toggle(user=None):
    """关注/取关（幂等切换）"""
    data = request.get_json(silent=True) or {}
    try:
        target = int(data.get('user_id') or 0)
    except (TypeError, ValueError):
        target = 0
    if not target or target == user['id']:
        return jsonify({'error': '参数错误'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE id=%s", (target,))
            if not cur.fetchone():
                return jsonify({'error': '用户不存在'}), 404
            cur.execute("SELECT id FROM follows WHERE follower_id=%s AND followee_id=%s", (user['id'], target))
            row = cur.fetchone()
            if row:
                cur.execute("DELETE FROM follows WHERE id=%s", (row['id'],))
                following = False
            else:
                cur.execute("INSERT INTO follows (follower_id, followee_id) VALUES (%s, %s)", (user['id'], target))
                following = True
            cur.execute("SELECT COUNT(*) AS c FROM follows WHERE followee_id=%s", (target,))
            followers_count = cur.fetchone()['c']
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'following': following, 'followers_count': followers_count})

@bp.route('/api/users/<int:uid>/followers', methods=['GET'])
def user_followers(uid):
    """关注 TA 的人（粉丝）"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            viewer = get_current_user()
            cur.execute("""SELECT u.id, u.username, u.nickname, u.avatar, u.points, u.bio, u.public_id
                FROM follows f JOIN users u ON u.id=f.follower_id
                WHERE f.followee_id=%s ORDER BY f.created_at DESC LIMIT 200""", (uid,))
            rows = cur.fetchall()
            for r in rows:
                r['is_following'] = False
                if viewer:
                    cur.execute("SELECT id FROM follows WHERE follower_id=%s AND followee_id=%s", (viewer['id'], r['id']))
                    r['is_following'] = bool(cur.fetchone())
                r['is_me'] = bool(viewer and viewer['id'] == r['id'])
    finally:
        conn.close()
    return jsonify(rows)

@bp.route('/api/users/<int:uid>/following', methods=['GET'])
def user_following(uid):
    """TA 关注的人"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            viewer = get_current_user()
            cur.execute("""SELECT u.id, u.username, u.nickname, u.avatar, u.points, u.bio, u.public_id
                FROM follows f JOIN users u ON u.id=f.followee_id
                WHERE f.follower_id=%s ORDER BY f.created_at DESC LIMIT 200""", (uid,))
            rows = cur.fetchall()
            for r in rows:
                r['is_following'] = False
                if viewer:
                    cur.execute("SELECT id FROM follows WHERE follower_id=%s AND followee_id=%s", (viewer['id'], r['id']))
                    r['is_following'] = bool(cur.fetchone())
                r['is_me'] = bool(viewer and viewer['id'] == r['id'])
    finally:
        conn.close()
    return jsonify(rows)

@bp.route('/api/users/search', methods=['GET'])
@require_login
def user_search(user=None):
    """按 ID（@用户名）/昵称搜索用户"""
    q = (request.args.get('q') or '').strip()
    if not q or len(q) > 32:
        return jsonify({'error': '请输入搜索关键词'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id, username, nickname, avatar, points, public_id FROM users
                WHERE username LIKE %s OR nickname LIKE %s ORDER BY id ASC LIMIT 20""",
                ('%' + q + '%', '%' + q + '%'))
            rows = cur.fetchall()
            for r in rows:
                r['is_me'] = (r['id'] == user['id'])
                r['is_following'] = False
                if r['id'] != user['id']:
                    cur.execute("SELECT id FROM follows WHERE follower_id=%s AND followee_id=%s", (user['id'], r['id']))
                    r['is_following'] = bool(cur.fetchone())
    finally:
        conn.close()
    return jsonify(rows)
