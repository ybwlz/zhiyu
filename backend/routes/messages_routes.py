# -*- coding: utf-8 -*-
"""私信 / 群聊 / AI 官方账号回复"""
from flask import Blueprint, request, jsonify
import json
import urllib.request
import pymysql

from pymysql.cursors import DictCursor

from config import DEEPSEEK_API_KEY, DEEPSEEK_RESPONSES_MODEL, DEEPSEEK_RESPONSES_URL, FREE_AI_QUOTA
from db import get_conn
from auth import require_login
from utils import notify

bp = Blueprint('messages', __name__)

@bp.route('/api/messages', methods=['POST'])
@require_login
def message_send(user=None):
    data = request.get_json(silent=True) or {}
    to_key = str(data.get('to_user_id') or '').strip()
    content = (data.get('content') or '').strip()
    if not to_key:
        return jsonify({'error': '参数错误'}), 400
    if not content or len(content) > 2000:
        return jsonify({'error': '内容需在 1-2000 字内'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # to_user_id 支持 public_id 或数字 id（数字兼容旧引用）
            to_id = 0
            if to_key.isdigit():
                to_id = int(to_key)
            else:
                cur.execute("SELECT id FROM users WHERE public_id=%s LIMIT 1", (to_key,))
                r = cur.fetchone()
                if r:
                    to_id = r['id']
            if not to_id or to_id == user['id']:
                return jsonify({'error': '参数错误'}), 400
            cur.execute("SELECT id FROM users WHERE id=%s", (to_id,))
            if not cur.fetchone():
                return jsonify({'error': '用户不存在'}), 404
            cur.execute("INSERT INTO messages (sender_id, receiver_id, content) VALUES (%s, %s, %s)",
                        (user['id'], to_id, content))
            msg_id = cur.lastrowid
            # 私信通知接收方（排除自己 / AI 账号不通知）
            ai_row = None
            cur.execute("SELECT id FROM users WHERE username='ai'")
            ai_row = cur.fetchone()
            ai_id = ai_row['id'] if ai_row else None
            if to_id != user['id'] and to_id != ai_id:
                notify(conn, to_id, user['id'], 'message')
            # 发给 AI 官方账号 → DeepSeek 生成回复（异步同请求内完成）
            if ai_id and to_id == ai_id:
                reply = _ai_reply(user['id'], content)
                if reply:
                    cur.execute("INSERT INTO messages (sender_id, receiver_id, content) VALUES (%s, %s, %s)",
                                (ai_id, user['id'], reply))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'id': msg_id})

def _ai_reply(user_id, content):
    """AI 官方账号回复：带上与 AI 的最近对话作多轮上下文，返回回复文本（失败返回 None）"""
    if not DEEPSEEK_API_KEY:
        return None
    # AI 私信与 AI 助手共用免费额度（防刷爆 DeepSeek API）
    conn0 = get_conn()
    try:
        with conn0.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT ai_used, ai_quota_bonus FROM users WHERE id=%s", (user_id,))
            u = cur.fetchone()
    finally:
        conn0.close()
    if u and (u.get('ai_used') or 0) >= FREE_AI_QUOTA + (u.get('ai_quota_bonus') or 0):
        return 'AI 额度已用完，可去知屿币商城兑换额度后继续使用'
    conn = get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT id FROM users WHERE username='ai'")
            arow = cur.fetchone()
            if not arow:
                return None
            ai_id = arow['id']
            cur.execute(
                "SELECT sender_id, receiver_id, content FROM messages "
                "WHERE (sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s) "
                "ORDER BY id DESC LIMIT 10",
                (user_id, ai_id, ai_id, user_id)
            )
            hist = list(cur.fetchall())
            cur.execute("UPDATE users SET ai_used = ai_used + 1 WHERE id=%s", (user_id,))
        conn.commit()
    finally:
        conn.close()
    hist.reverse()
    system = (
        "你是「知屿」的 AI 助手（官方账号），在私信里陪伴用户学习备考（考研 408 / 数学 / 英语 / 政治）。"
        "回答简洁、准确、友善；涉及数学或 408 内容给出关键步骤；可用 Markdown；不知道的不要编造。"
        "若用户问「你是什么模型/谁开发的」：直接干脆地回答你是「知屿」的 AI 助手即可，"
        "不要提及或暗示底层模型名称（DeepSeek/Claude/GPT/OpenAI 等），不要回避问题，也不要说『没有公开信息』之类的话。"
    )
    input_items = []
    for h in hist:
        role = 'user' if h['sender_id'] == user_id else 'assistant'
        input_items.append({'role': role, 'content': str(h['content'])[:2000]})
    # 统一走 Responses API + deepseek-v4-flash（关闭思考，保持轻快）
    payload = {
        'model': DEEPSEEK_RESPONSES_MODEL,
        'instructions': system,
        'input': input_items,
        'temperature': 0.6,
        'reasoning': {'effort': 'none'},
        'stream': False,
    }
    req = urllib.request.Request(
        DEEPSEEK_RESPONSES_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + DEEPSEEK_API_KEY},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        answer = ''
        for item in result.get('output') or []:
            if item.get('type') == 'message':
                for c in item.get('content') or []:
                    if c.get('type') == 'output_text':
                        answer += c.get('text') or ''
        return answer.strip() or None
    except Exception:
        return None


@bp.route('/api/groups', methods=['POST'])
@require_login
def group_create(user=None):
    """创建群聊：{name, member_ids:[]}"""
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    try:
        member_ids = [int(x) for x in (data.get('member_ids') or [])]
    except (TypeError, ValueError):
        member_ids = []
    if not name or len(name) > 30:
        return jsonify({'error': '群名需在 1-30 字内'}), 400
    member_ids = [m for m in member_ids if m != user['id']]
    if not member_ids:
        return jsonify({'error': '请至少选择一位群成员'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO chat_groups (name, owner_id) VALUES (%s, %s)", (name, user['id']))
            gid = cur.lastrowid
            cur.execute("INSERT INTO chat_group_members (group_id, user_id) VALUES (%s, %s)", (gid, user['id']))
            for m in member_ids:
                cur.execute("INSERT IGNORE INTO chat_group_members (group_id, user_id) VALUES (%s, %s)", (gid, m))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'id': gid})

@bp.route('/api/groups', methods=['GET'])
@require_login
def group_list(user=None):
    """我的群列表（含成员数与最后一条消息）"""
    conn = get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("""
                SELECT g.id, g.name, g.owner_id,
                    CAST(g.created_at AS CHAR) AS created_at,
                    (SELECT COUNT(*) FROM chat_group_members m2 WHERE m2.group_id=g.id) AS member_count,
                    (SELECT gm.content FROM group_messages gm WHERE gm.group_id=g.id ORDER BY gm.id DESC LIMIT 1) AS last_content
                FROM chat_groups g JOIN chat_group_members m ON m.group_id=g.id
                WHERE m.user_id=%s ORDER BY g.id DESC""", (user['id'],))
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify(rows)

@bp.route('/api/groups/<int:gid>', methods=['GET'])
@require_login
def group_detail(gid, user=None):
    """群详情 + 成员"""
    conn = get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT id FROM chat_group_members WHERE group_id=%s AND user_id=%s", (gid, user['id']))
            if not cur.fetchone():
                return jsonify({'error': '你不是群成员'}), 403
            cur.execute("SELECT id, name, owner_id, CAST(created_at AS CHAR) AS created_at FROM chat_groups WHERE id=%s", (gid,))
            g = cur.fetchone()
            cur.execute("SELECT u.id, u.username, u.nickname, u.avatar FROM chat_group_members m JOIN users u ON u.id=m.user_id WHERE m.group_id=%s", (gid,))
            members = cur.fetchall()
    finally:
        conn.close()
    return jsonify({'group': g, 'members': members})

@bp.route('/api/groups/<int:gid>/messages', methods=['GET'])
@require_login
def group_messages_list(gid, user=None):
    conn = get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT id FROM chat_group_members WHERE group_id=%s AND user_id=%s", (gid, user['id']))
            if not cur.fetchone():
                return jsonify({'error': '你不是群成员'}), 403
            cur.execute("""
                SELECT gm.id, gm.sender_id, gm.content,
                    CAST(gm.created_at AS CHAR) AS created_at,
                    u.username, u.nickname, u.avatar
                FROM group_messages gm JOIN users u ON u.id=gm.sender_id
                WHERE gm.group_id=%s ORDER BY gm.id ASC LIMIT 200""", (gid,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify(rows)

@bp.route('/api/groups/<int:gid>/messages', methods=['POST'])
@require_login
def group_message_send(gid, user=None):
    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    if not content or len(content) > 2000:
        return jsonify({'error': '内容需在 1-2000 字内'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM chat_group_members WHERE group_id=%s AND user_id=%s", (gid, user['id']))
            if not cur.fetchone():
                return jsonify({'error': '你不是群成员'}), 403
            cur.execute("INSERT INTO group_messages (group_id, sender_id, content) VALUES (%s, %s, %s)", (gid, user['id'], content))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True})

@bp.route('/api/messages/conversations', methods=['GET'])
@require_login
def message_conversations(user=None):
    """会话列表：对方信息 + 最后一条 + 未读数"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT m.id, m.sender_id, m.receiver_id, m.content, m.created_at,
                    CASE WHEN m.sender_id=%s THEN m.receiver_id ELSE m.sender_id END AS peer_id,
                    (m.sender_id=%s) AS mine
                FROM messages m
                WHERE m.id IN (
                    SELECT MAX(m2.id) FROM messages m2
                    WHERE m2.sender_id=%s OR m2.receiver_id=%s
                    GROUP BY CASE WHEN m2.sender_id=%s THEN m2.receiver_id ELSE m2.sender_id END
                )
                ORDER BY m.id DESC""", (user['id'], user['id'], user['id'], user['id'], user['id']))
            rows = cur.fetchall()
            peers = {}
            for r in rows:
                peers.setdefault(r['peer_id'], []).append(r)
            # AI 官方账号：由前端固定条目展示，会话列表里不再重复出现
            ai_id = None
            cur.execute("SELECT id FROM users WHERE username='ai'")
            aiq = cur.fetchone()
            if aiq:
                ai_id = aiq['id']
            result = []
            for pid, msgs in peers.items():
                if ai_id and pid == ai_id:
                    continue
                last = msgs[0]
                cur.execute("SELECT id, username, nickname, avatar, public_id FROM users WHERE id=%s", (pid,))
                pu = cur.fetchone() or {}
                cur.execute("SELECT COUNT(*) AS c FROM messages WHERE sender_id=%s AND receiver_id=%s AND read_at IS NULL", (pid, user['id']))
                unread = cur.fetchone()['c']
                result.append({
                    'peer': pu, 'last': last['content'], 'last_at': last['created_at'],
                    'mine': bool(last['mine']), 'unread': unread,
                })
    finally:
        conn.close()
    # AI 官方账号信息（前端固定置顶的 AI 会话）
    ai_info = None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, nickname, avatar, public_id FROM users WHERE username='ai'")
            ai_info = cur.fetchone()
    finally:
        conn.close()
    return jsonify({'list': result, 'ai': ai_info})

@bp.route('/api/messages', methods=['GET'])
@require_login
def message_history(user=None):
    """与某人对话（with=<peer_id>），返回后标记已读"""
    data = request.args
    with_key = str(data.get('with') or '').strip()
    if not with_key:
        return jsonify({'error': '缺少对方'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # with 支持 public_id（URL 不暴露数字 id）；数字 id 兼容旧链接/内部引用
            peer_id = 0
            if with_key.isdigit():
                peer_id = int(with_key)
            else:
                cur.execute("SELECT id FROM users WHERE public_id=%s LIMIT 1", (with_key,))
                r = cur.fetchone()
                if r:
                    peer_id = r['id']
            if not peer_id:
                return jsonify({'error': '用户不存在'}), 404
            cur.execute("SELECT id, username, nickname, avatar, public_id FROM users WHERE id=%s", (peer_id,))
            peer = cur.fetchone()
            if not peer:
                return jsonify({'error': '用户不存在'}), 404
            cur.execute("""SELECT id, sender_id, receiver_id, content, CAST(created_at AS CHAR) AS created_at
                FROM messages WHERE (sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s)
                ORDER BY id ASC LIMIT 500""", (user['id'], peer_id, peer_id, user['id']))
            rows = cur.fetchall()
            for r in rows:
                r['mine'] = (r['sender_id'] == user['id'])
            cur.execute("UPDATE messages SET read_at=NOW() WHERE sender_id=%s AND receiver_id=%s AND read_at IS NULL", (peer_id, user['id']))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'peer': peer, 'messages': rows})
