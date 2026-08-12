# -*- coding: utf-8 -*-
"""阅览室 / 收费购买 / 首页动态流 / 更新日志聚合 / 积分商城"""
from flask import Blueprint, request, jsonify
from datetime import datetime

from db import get_conn
from auth import require_login
from utils import DOC_SELECT

bp = Blueprint('misc', __name__)

@bp.route('/api/reading-list', methods=['GET'])
@require_login
def reading_list(user=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(DOC_SELECT + """ FROM docs d LEFT JOIN users u ON d.user_id=u.id
                JOIN reading_list rl ON rl.doc_id = d.id
                WHERE rl.user_id=%s ORDER BY rl.created_at DESC""", (user['id'],))
            rows = cur.fetchall()
            for r in rows:
                r['in_room'] = True
    finally:
        conn.close()
    return jsonify(rows)

@bp.route('/api/reading-list', methods=['POST'])
@require_login
def reading_list_add(user=None):
    data = request.get_json(silent=True) or {}
    try:
        doc_id = int(data.get('doc_id') or 0)
    except (TypeError, ValueError):
        doc_id = 0
    source = (data.get('source') or 'square')[:16]
    if not doc_id:
        return jsonify({'error': '缺少笔记'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, visibility, user_id FROM docs WHERE id=%s", (doc_id,))
            d = cur.fetchone()
            if not d:
                return jsonify({'error': '笔记不存在'}), 404
            if not (d['visibility'] == 'public' or user['role'] == 'admin' or d['user_id'] == user['id']):
                return jsonify({'error': '无权添加'}), 403
            cur.execute("INSERT INTO reading_list (user_id, doc_id, source) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE source=VALUES(source)",
                        (user['id'], doc_id, source))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True})

@bp.route('/api/reading-list/<int:doc_id>', methods=['DELETE'])
@require_login
def reading_list_remove(doc_id, user=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM reading_list WHERE user_id=%s AND doc_id=%s", (user['id'], doc_id))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True})

# ═══════════════ 收费笔记购买（知屿币） ═══════════════
@bp.route('/api/docs/<int:doc_id>/purchase', methods=['POST'])
@require_login
def doc_purchase(doc_id, user=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, price, user_id FROM docs WHERE id=%s", (doc_id,))
            d = cur.fetchone()
            if not d:
                return jsonify({'error': '笔记不存在'}), 404
            if d['user_id'] and d['user_id'] == user['id']:
                return jsonify({'error': '自己的笔记无需购买'}), 400
            cur.execute("SELECT id FROM purchased_docs WHERE user_id=%s AND doc_id=%s", (user['id'], doc_id))
            if cur.fetchone():
                return jsonify({'success': True, 'already': True})
            price = int(d['price'] or 0)
            if price < 0 or price > 99999:
                return jsonify({'error': '笔记价格异常'}), 400
            cur.execute("SELECT points FROM users WHERE id=%s", (user['id'],))
            pts = cur.fetchone()['points'] or 0
            if pts < price:
                return jsonify({'error': f'知屿币不足，需要 {price}'}), 402
            cur.execute("UPDATE users SET points = points - %s WHERE id=%s", (price, user['id']))
            cur.execute("INSERT INTO purchased_docs (user_id, doc_id, price) VALUES (%s, %s, %s)", (user['id'], doc_id, price))
            if d['user_id']:
                cur.execute("UPDATE users SET points = points + %s WHERE id=%s", (price, d['user_id']))
                try:
                    cur.execute("INSERT INTO point_logs (user_id, delta, reason) VALUES (%s, %s, %s)", (d['user_id'], price, 'note_sold'))
                except Exception:
                    pass
            try:
                cur.execute("INSERT INTO point_logs (user_id, delta, reason) VALUES (%s, %s, %s)", (user['id'], -price, 'note_buy'))
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True})

@bp.route('/api/feed')
def api_feed():
    """首页动态流：新笔记/点赞/评论/收藏/新用户（?user_id=X 过滤指定用户）"""
    rows = []
    uid_f = request.args.get('user_id', type=int)
    uid_where = " AND d.user_id = %s" if uid_f else ""
    uid_args = (uid_f,) if uid_f else ()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT d.id, d.public_id, d.title, d.created_at AS ts, 'doc' AS act, u.username, u.nickname
                           FROM docs d JOIN users u ON u.id = d.user_id
                           WHERE d.visibility = 'public'""" + uid_where + " ORDER BY d.created_at DESC LIMIT 5", uid_args)
            for r in cur.fetchall():
                rows.append((r['ts'], {'type': 'doc', 'doc_id': r['id'], 'doc_public_id': r['public_id'], 'doc_title': r['title'],
                                       'username': r['username'], 'nickname': r['nickname']}))
            like_where = " AND nl.user_id = %s" if uid_f else ""
            cur.execute("""SELECT nl.doc_id, d.title, nl.created_at AS ts, u.username, u.nickname
                           FROM note_likes nl JOIN docs d ON d.id = nl.doc_id JOIN users u ON u.id = nl.user_id
                           WHERE d.visibility = 'public'""" + like_where + " ORDER BY nl.created_at DESC LIMIT 5", uid_args)
            for r in cur.fetchall():
                rows.append((r['ts'], {'type': 'like', 'doc_id': r['doc_id'], 'doc_title': r['title'],
                                       'username': r['username'], 'nickname': r['nickname']}))
            com_where = " AND nc.user_id = %s" if uid_f else ""
            cur.execute("""SELECT nc.doc_id, d.title, nc.created_at AS ts, u.username, u.nickname, nc.content
                           FROM note_comments nc JOIN docs d ON d.id = nc.doc_id JOIN users u ON u.id = nc.user_id
                           WHERE d.visibility = 'public'""" + com_where + " ORDER BY nc.created_at DESC LIMIT 5", uid_args)
            for r in cur.fetchall():
                rows.append((r['ts'], {'type': 'comment', 'doc_id': r['doc_id'], 'doc_title': r['title'],
                                       'username': r['username'], 'nickname': r['nickname'],
                                       'snippet': (r['content'] or '')[:30]}))
            fav_where = " AND nf.user_id = %s" if uid_f else ""
            cur.execute("""SELECT nf.doc_id, d.title, nf.created_at AS ts, u.username, u.nickname
                           FROM note_favorites nf JOIN docs d ON d.id = nf.doc_id JOIN users u ON u.id = nf.user_id
                           WHERE d.visibility = 'public'""" + fav_where + " ORDER BY nf.created_at DESC LIMIT 5", uid_args)
            for r in cur.fetchall():
                rows.append((r['ts'], {'type': 'favorite', 'doc_id': r['doc_id'], 'doc_title': r['title'],
                                       'username': r['username'], 'nickname': r['nickname']}))
            if uid_f:
                cur.execute("SELECT username, nickname, created_at AS ts FROM users WHERE id=%s", (uid_f,))
            else:
                cur.execute("SELECT username, nickname, created_at AS ts FROM users ORDER BY id DESC LIMIT 3")
            for r in cur.fetchall():
                rows.append((r['ts'], {'type': 'user', 'doc_id': None, 'doc_title': None,
                                       'username': r['username'], 'nickname': r['nickname']}))
    finally:
        conn.close()
    rows.sort(key=lambda x: x[0] or '', reverse=True)
    out = []
    for ts, r in rows[:12]:
        if hasattr(ts, 'strftime'):
            ts = ts.strftime('%Y-%m-%d %H:%M')
        out.append({**r, 'ts': ts})
    return jsonify(out)


@bp.route('/api/changelog', methods=['GET'])
def changelog_digest():
    """聚合最近 N 天的社区动态（文档更新/评论/新用户/互动统计），供更新日志页展示"""
    try:
        days = min(int(request.args.get('days', 7)), 30)
    except (TypeError, ValueError):
        days = 7
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT d.title, d.type, d.id, d.public_id, CAST(d.updated_at AS CHAR) AS ts,
                d.user_id, u.nickname, u.username
                FROM docs d LEFT JOIN users u ON d.user_id=u.id
                WHERE d.updated_at >= NOW() - INTERVAL %s DAY AND d.visibility='public'
                ORDER BY d.updated_at DESC LIMIT 20""", (days,))
            doc_updates = cur.fetchall()
            cur.execute("""SELECT c.content, CAST(c.created_at AS CHAR) AS ts,
                c.user_id, u.nickname, u.username, d.title AS doc_title, c.doc_id
                FROM note_comments c
                LEFT JOIN users u ON c.user_id=u.id
                LEFT JOIN docs d ON c.doc_id=d.id
                WHERE c.created_at >= NOW() - INTERVAL %s DAY
                ORDER BY c.created_at DESC LIMIT 20""", (days,))
            comments = cur.fetchall()
            cur.execute("""SELECT username, nickname, CAST(created_at AS CHAR) AS ts FROM users
                WHERE created_at >= NOW() - INTERVAL %s DAY ORDER BY created_at DESC LIMIT 10""", (days,))
            new_users = cur.fetchall()
            cur.execute("SELECT COUNT(*) AS c FROM note_likes WHERE created_at >= NOW() - INTERVAL %s DAY", (days,))
            likes = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) AS c FROM note_favorites WHERE created_at >= NOW() - INTERVAL %s DAY", (days,))
            favorites = cur.fetchone()['c']
            # AI Agent 最新每日摘要
            cur.execute("SELECT digest_date, summary, CAST(created_at AS CHAR) AS created_at FROM daily_digests ORDER BY digest_date DESC LIMIT 1")
            digest = cur.fetchone()
    finally:
        conn.close()
    return jsonify({'days': days, 'doc_updates': doc_updates, 'comments': comments,
                    'new_users': new_users, 'likes': likes, 'favorites': favorites, 'digest': digest})
# ═══════════════ 积分商城兑换 ═══════════════
MALL_GOODS = {
    1: {'name': 'AI 助手额度 ×5', 'cost': 100, 'type': 'ai_quota', 'value': 5},
    2: {'name': '笔记广场置顶 24h', 'cost': 200, 'type': 'pin', 'value': 1},
    3: {'name': '专属徽章·学霸', 'cost': 500, 'type': 'badge', 'value': 1},
}

@bp.route('/api/mall/exchange', methods=['POST'])
@require_login
def mall_exchange(user=None):
    data = request.get_json(silent=True) or {}
    try:
        goods_id = int(data.get('goods_id') or 0)
    except (TypeError, ValueError):
        goods_id = 0
    goods = MALL_GOODS.get(goods_id)
    if not goods:
        return jsonify({'error': '商品不存在'}), 404
    if goods['type'] == 'pin':
        doc_id = 0
        try:
            doc_id = int(data.get('doc_id') or 0)
        except (TypeError, ValueError):
            doc_id = 0
        if not doc_id:
            return jsonify({'error': '请选择要置顶的笔记'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT points FROM users WHERE id=%s", (user['id'],))
            points = cur.fetchone()['points']
            if points < goods['cost']:
                return jsonify({'error': '积分不足'}), 400
            if goods['type'] == 'badge':
                cur.execute("UPDATE users SET badge='scholar' WHERE id=%s", (user['id'],))
                cur.execute("INSERT INTO point_logs (user_id, delta, reason) VALUES (%s, %s, %s)",
                            (user['id'], -goods['cost'], 'exchange_badge'))
            elif goods['type'] == 'pin':
                cur.execute("SELECT id, user_id, visibility FROM docs WHERE id=%s", (doc_id,))
                doc = cur.fetchone()
                if not doc:
                    return jsonify({'error': '笔记不存在'}), 404
                if doc['user_id'] != user['id']:
                    return jsonify({'error': '只能置顶自己的笔记'}), 403
                if doc['visibility'] != 'public':
                    return jsonify({'error': '只能置顶公开笔记'}), 400
                if doc.get('pinned_until') and datetime.strptime(str(doc['pinned_until'])[:19], '%Y-%m-%d %H:%M:%S') > datetime.now():
                    return jsonify({'error': '该笔记已在置顶中'}), 400
                cur.execute("UPDATE docs SET pinned_until = NOW() + INTERVAL 24 HOUR WHERE id=%s", (doc_id,))
                cur.execute("INSERT INTO point_logs (user_id, delta, reason) VALUES (%s, %s, %s)",
                            (user['id'], -goods['cost'], 'exchange_pin'))
            else:
                cur.execute("UPDATE users SET ai_quota_bonus = ai_quota_bonus + %s WHERE id=%s", (goods['value'], user['id']))
                cur.execute("INSERT INTO point_logs (user_id, delta, reason) VALUES (%s, %s, %s)",
                            (user['id'], -goods['cost'], 'exchange_ai_quota'))
            cur.execute("UPDATE users SET points = points - %s WHERE id=%s", (goods['cost'], user['id']))
        conn.commit()
    finally:
        conn.close()
    resp = {'success': True, 'points_left': points - goods['cost']}
    if goods['type'] == 'ai_quota':
        resp['bonus'] = goods['value']
    elif goods['type'] == 'badge':
        resp['badge'] = 'scholar'
    return jsonify(resp)
