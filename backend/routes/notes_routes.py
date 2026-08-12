# -*- coding: utf-8 -*-
"""笔记互动：互动状态 / 点赞 / 评分 / 收藏 / 转发 / 评论 / 下载 / 阅读时长"""
from flask import Blueprint, request, jsonify
import pymysql
from pymysql.cursors import DictCursor

from db import get_conn
from auth import get_current_user, require_login
from shared import fetch_doc_visible
from utils import bump_doc_count, grant_points, daily_points, notify

bp = Blueprint('notes', __name__)

# ═══════════════ 笔记互动（点赞/收藏/转发/评论/下载/阅读） ═══════════════

def _interact_state(doc_id, user):
    """当前用户对文档的互动状态"""
    if not user:
        return {'liked': False, 'favorited': False, 'shared': False}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM note_likes WHERE user_id=%s AND doc_id=%s", (user['id'], doc_id))
            liked = cur.fetchone() is not None
            cur.execute("SELECT 1 FROM note_favorites WHERE user_id=%s AND doc_id=%s", (user['id'], doc_id))
            favorited = cur.fetchone() is not None
            cur.execute("SELECT 1 FROM note_shares WHERE user_id=%s AND doc_id=%s", (user['id'], doc_id))
            shared = cur.fetchone() is not None
    finally:
        conn.close()
    return {'liked': liked, 'favorited': favorited, 'shared': shared}

@bp.route('/api/notes/<int:doc_id>/interact', methods=['GET'])
def note_interact(doc_id):
    """互动状态（供页面初始化）"""
    row, err = fetch_doc_visible(doc_id=doc_id)
    if err:
        return err
    return jsonify(_interact_state(doc_id, get_current_user()))

@bp.route('/api/notes/<int:doc_id>/like', methods=['POST'])
@require_login
def note_like(doc_id, user=None):
    row, err = fetch_doc_visible(doc_id=doc_id)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO note_likes (user_id, doc_id) VALUES (%s, %s)", (user['id'], doc_id))
        bump_doc_count(conn, doc_id, 'likes_count', 1)
        # 笔记作者获得 1 知屿币（排除自己给自己点赞；每日上限防刷币）
        if row.get('user_id') and row['user_id'] != user['id']:
            if daily_points(conn, row['user_id'], 'note_liked', 30) < 30:
                grant_points(conn, row['user_id'], 1, 'note_liked')
            notify(conn, row['user_id'], user['id'], 'like', doc_id)
        conn.commit()
        return jsonify({'success': True, 'likes_count': row.get('likes_count', 0) + 1})
    except pymysql.err.IntegrityError:
        conn.rollback()
        return jsonify({'error': 'already_liked'}), 409
    finally:
        conn.close()

RATING_TAGS = ['简洁明了', '内容充实', '值得一读', '干货满满', '有所收获']

@bp.route('/api/notes/<int:doc_id>/rating', methods=['GET'])
def note_rating_stat(doc_id):
    """评分统计：综合得分(10分制) / 四维均分 / 标签占比 / 我的评分 / 今日剩余次数"""
    user = get_current_user()
    conn = get_conn()
    mine = None
    my_tags = []
    remaining = 3
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT COUNT(*) AS n, ROUND(AVG(professional),2) AS p, ROUND(AVG(practical),2) AS pr, "
                "ROUND(AVG(readable),2) AS r, ROUND(AVG(insight),2) AS i FROM note_ratings WHERE doc_id=%s",
                (doc_id,)
            )
            agg = cur.fetchone() or {}
            cur.execute("SELECT tag, COUNT(*) AS n FROM note_rating_tags WHERE doc_id=%s GROUP BY tag", (doc_id,))
            tag_rows = cur.fetchall()
            if user:
                cur.execute("SELECT professional, practical, readable, insight FROM note_ratings WHERE doc_id=%s AND user_id=%s", (doc_id, user['id']))
                r = cur.fetchone()
                if r:
                    mine = {k: (r[k] or 0) for k in ('professional', 'practical', 'readable', 'insight')}
                    cur.execute("SELECT tag FROM note_rating_tags WHERE doc_id=%s AND user_id=%s", (doc_id, user['id']))
                    my_tags = [x['tag'] for x in cur.fetchall()]
                cur.execute("SELECT COUNT(*) AS n FROM note_ratings WHERE user_id=%s AND DATE(created_at)=CURDATE()", (user['id'],))
                remaining = max(0, 3 - (cur.fetchone() or {}).get('n', 0))
    finally:
        conn.close()
    count = agg.get('n') or 0
    total = 0.0
    dims = {}
    if count:
        dims = {'professional': float(agg['p'] or 0), 'practical': float(agg['pr'] or 0),
                'readable': float(agg['r'] or 0), 'insight': float(agg['i'] or 0)}
        total = round((dims['professional'] + dims['practical'] + dims['readable'] + dims['insight']) / 4 * 2, 1)
    tags = {t: 0 for t in RATING_TAGS}
    for x in tag_rows:
        if x['tag'] in tags:
            tags[x['tag']] = x['n']
    return jsonify({'count': count, 'total': total, 'dims': dims, 'tags': tags,
                    'mine': mine, 'my_tags': my_tags, 'remaining_today': remaining})

@bp.route('/api/notes/<int:doc_id>/rating', methods=['POST'])
@require_login
def note_rate(doc_id, user=None):
    data = request.get_json(silent=True) or {}
    dims = {}
    for k in ('professional', 'practical', 'readable', 'insight'):
        v = int(data.get(k) or 0)
        if v < 1 or v > 5:
            return jsonify({'error': '评分须为 1-5 星'}), 400
        dims[k] = v
    tags = list(dict.fromkeys(t for t in (data.get('tags') or []) if t in RATING_TAGS))
    conn = get_conn()
    new_rating = False
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT id FROM note_ratings WHERE doc_id=%s AND user_id=%s", (doc_id, user['id']))
            existing = cur.fetchone()
            if not existing:
                cur.execute("SELECT COUNT(*) AS n FROM note_ratings WHERE user_id=%s AND DATE(created_at)=CURDATE()", (user['id'],))
                if (cur.fetchone() or {}).get('n', 0) >= 3:
                    return jsonify({'error': '今日评分次数已用完（每天 3 次）'}), 429
            if existing:
                cur.execute(
                    "UPDATE note_ratings SET professional=%s, practical=%s, readable=%s, insight=%s WHERE doc_id=%s AND user_id=%s",
                    (dims['professional'], dims['practical'], dims['readable'], dims['insight'], doc_id, user['id'])
                )
            else:
                cur.execute(
                    "INSERT INTO note_ratings (doc_id, user_id, professional, practical, readable, insight) VALUES (%s,%s,%s,%s,%s,%s)",
                    (doc_id, user['id'], dims['professional'], dims['practical'], dims['readable'], dims['insight'])
                )
                new_rating = True
            cur.execute("DELETE FROM note_rating_tags WHERE doc_id=%s AND user_id=%s", (doc_id, user['id']))
            for t in tags:
                cur.execute("INSERT INTO note_rating_tags (doc_id, user_id, tag) VALUES (%s,%s,%s)", (doc_id, user['id'], t))
        if new_rating:
            # 参与评分 +2 知屿币
            grant_points(conn, user['id'], 2, 'note_rating')
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'earned': 2 if new_rating else 0})

@bp.route('/api/notes/<int:doc_id>/like', methods=['DELETE'])
@require_login
def note_unlike(doc_id, user=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM note_likes WHERE user_id=%s AND doc_id=%s", (user['id'], doc_id))
            affected = cur.rowcount
        if affected:
            bump_doc_count(conn, doc_id, 'likes_count', -1)
        conn.commit()
        return jsonify({'success': True})
    finally:
        conn.close()

@bp.route('/api/notes/<int:doc_id>/favorite', methods=['POST'])
@require_login
def note_favorite(doc_id, user=None):
    row, err = fetch_doc_visible(doc_id=doc_id)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO note_favorites (user_id, doc_id) VALUES (%s, %s)", (user['id'], doc_id))
        bump_doc_count(conn, doc_id, 'favorites_count', 1)
        if row.get('user_id') and row['user_id'] != user['id']:
            if daily_points(conn, row['user_id'], 'note_favorited', 30) < 30:
                grant_points(conn, row['user_id'], 1, 'note_favorited')
            notify(conn, row['user_id'], user['id'], 'favorite', doc_id)
        conn.commit()
        return jsonify({'success': True, 'favorites_count': row.get('favorites_count', 0) + 1})
    except pymysql.err.IntegrityError:
        conn.rollback()
        return jsonify({'error': 'already_favorited'}), 409
    finally:
        conn.close()

@bp.route('/api/notes/<int:doc_id>/favorite', methods=['DELETE'])
@require_login
def note_unfavorite(doc_id, user=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM note_favorites WHERE user_id=%s AND doc_id=%s", (user['id'], doc_id))
            affected = cur.rowcount
        if affected:
            bump_doc_count(conn, doc_id, 'favorites_count', -1)
        conn.commit()
        return jsonify({'success': True})
    finally:
        conn.close()

@bp.route('/api/notes/<int:doc_id>/share', methods=['POST'])
@require_login
def note_share(doc_id, user=None):
    row, err = fetch_doc_visible(doc_id=doc_id)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO note_shares (user_id, doc_id) VALUES (%s, %s)", (user['id'], doc_id))
        if row.get('user_id') and row['user_id'] != user['id']:
            if daily_points(conn, row['user_id'], 'note_shared', 20) < 20:
                grant_points(conn, row['user_id'], 2, 'note_shared')
        conn.commit()
        return jsonify({'success': True})
    except pymysql.err.IntegrityError:
        conn.rollback()
        return jsonify({'error': 'already_shared'}), 409
    finally:
        conn.close()

@bp.route('/api/notes/<int:doc_id>/comments', methods=['GET'])
def note_comments(doc_id):
    row, err = fetch_doc_visible(doc_id=doc_id)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT c.id, c.content, c.parent_id, c.anchor, CAST(c.created_at AS CHAR) AS created_at,
                c.user_id, u.nickname, u.username, u.avatar, u.public_id AS user_public_id,
                pu.nickname AS parent_nickname, pu.username AS parent_username
                FROM note_comments c
                LEFT JOIN users u ON c.user_id=u.id
                LEFT JOIN note_comments pc ON pc.id = c.parent_id
                LEFT JOIN users pu ON pu.id = pc.user_id
                WHERE c.doc_id=%s ORDER BY c.created_at ASC""", (doc_id,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify(rows)

@bp.route('/api/notes/<int:doc_id>/comments', methods=['POST'])
@require_login
def note_comment(doc_id, user=None):
    row, err = fetch_doc_visible(doc_id=doc_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    if not content or len(content) > 1000:
        return jsonify({'error': '评论内容需在 1-1000 字内'}), 400
    anchor = (data.get('anchor') or '').strip()[:128]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO note_comments (doc_id, user_id, content, parent_id, anchor) VALUES (%s, %s, %s, %s, %s)",
                        (doc_id, user['id'], content, data.get('parent_id'), anchor or None))
            cid = cur.lastrowid
            parent_uid = None
            if data.get('parent_id'):
                cur.execute("SELECT user_id FROM note_comments WHERE id = %s", (data.get('parent_id'),))
                pc = cur.fetchone()
                if pc:
                    parent_uid = pc['user_id']
        bump_doc_count(conn, doc_id, 'comments_count', 1)
        # 评论者 +1，每日上限 20 分
        if daily_points(conn, user['id'], 'note_commented', 20) < 20:
            grant_points(conn, user['id'], 1, 'note_commented')
        # 作者收到评论 +1（排除自评），每日上限 20 分
        if row.get('user_id') and row['user_id'] != user['id']:
            notify(conn, row['user_id'], user['id'], 'comment', doc_id)
            if daily_points(conn, row['user_id'], 'note_received_comment', 20) < 20:
                grant_points(conn, row['user_id'], 1, 'note_received_comment')
        # 被回复者收到回复通知（非自己、非笔记作者）
        if parent_uid and parent_uid != user['id'] and parent_uid != row.get('user_id'):
            notify(conn, parent_uid, user['id'], 'reply', doc_id)
        conn.commit()
        return jsonify({'success': True, 'id': cid})
    finally:
        conn.close()

@bp.route('/api/notes/<int:doc_id>/comments/<int:comment_id>', methods=['DELETE'])
@require_login
def delete_note_comment(doc_id, comment_id, user=None):
    # 仅评论作者本人可删除（删除后评论数 -1）
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, user_id FROM note_comments WHERE id=%s AND doc_id=%s", (comment_id, doc_id))
            c = cur.fetchone()
            if not c:
                return jsonify({'error': 'not_found'}), 404
            if c['user_id'] != user['id']:
                return jsonify({'error': 'forbidden'}), 403
            cur.execute("DELETE FROM note_comments WHERE id=%s", (comment_id,))
        bump_doc_count(conn, doc_id, 'comments_count', -1)
        conn.commit()
        return jsonify({'success': True})
    finally:
        conn.close()

@bp.route('/api/notes/<int:doc_id>/download', methods=['POST'])
@require_login
def note_download(doc_id, user=None):
    """下载：作者未开放下载 / 收费仅预览需先购买"""
    row, err = fetch_doc_visible(doc_id=doc_id)
    if err:
        return err
    user = get_current_user()
    is_author = user and row.get('user_id') and row['user_id'] == user['id']
    if row.get('downloadable') == 0 and not is_author:
        return jsonify({'error': '作者未开放下载'}), 403
    if (row.get('preview_only') or (row.get('price') or 0) > 0) and not is_author:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM purchased_docs WHERE user_id=%s AND doc_id=%s", (user['id'] if user else 0, doc_id))
                bought = cur.fetchone()
        finally:
            conn.close()
        if not bought:
            price = row.get('price') or 0
            return jsonify({'error': f'仅预览，需 {price} 知屿币购买后下载'}), 402
    conn = get_conn()
    try:
        bump_doc_count(conn, doc_id, 'downloads_count', 1)
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'title': row['title'], 'content': row.get('content', '')})

@bp.route('/api/notes/<int:doc_id>/read', methods=['POST'])
@require_login
def note_read(doc_id, user=None):
    """阅读时长上报：累计阅读时长；每满 60 秒得 1 知屿币（每日上限 60 币）"""
    row, err = fetch_doc_visible(doc_id=doc_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    try:
        seconds = max(0, min(int(data.get('seconds', 0) or 0), 3600))
    except (TypeError, ValueError):
        seconds = 0
    if seconds <= 0:
        return jsonify({'success': True})
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO read_logs (user_id, doc_id, seconds) VALUES (%s, %s, %s)", (user['id'], doc_id, seconds))
            cur.execute("UPDATE users SET read_seconds = read_seconds + %s WHERE id=%s", (seconds, user['id']))
            # 当日已获阅读知屿币
            cur.execute("""SELECT COALESCE(SUM(delta),0) AS got FROM point_logs
                WHERE user_id=%s AND reason='read' AND DATE(created_at)=CURDATE()""", (user['id'],))
            got = cur.fetchone()['got']
            to_grant = min(seconds // 60, max(0, 60 - got))
            if to_grant > 0:
                grant_points(conn, user['id'], to_grant, 'read')
        conn.commit()
        return jsonify({'success': True, 'points_granted': to_grant})
    finally:
        conn.close()
