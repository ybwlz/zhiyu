# -*- coding: utf-8 -*-
"""管理后台接口（/api/admin/*）：仪表盘、用户、笔记、审核、评论、知屿币、兑换码、通知、管理员、AI 日志。
权限：require_perm(权限点)，admin 全权限，moderator 按勾选的 admin_perms。"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta

from db import get_conn
from auth import require_perm, require_role, user_can, ALL_PERMS
from utils import grant_points, log_admin, check_sensitive, ai_moderate

bp = Blueprint('admin', __name__)

PERM_LABELS = {
    'audit': '内容审核', 'notes': '笔记管理', 'comments': '评论管理',
    'coins': '知屿币', 'codes': '兑换码', 'users': '用户管理',
    'notices': '通知', 'admins': '管理员管理',
}


# ─────────────────── 仪表盘 ───────────────────
@bp.route('/api/admin/stats', methods=['GET'])
@require_perm('notes')
def admin_stats(user):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) c FROM users")
            user_total = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) c FROM docs")
            doc_total = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) c FROM docs WHERE visibility='public'")
            doc_public = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) c FROM docs WHERE visibility='private'")
            doc_private = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) c FROM ai_chat_logs")
            ai_total = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) c FROM docs WHERE audit_status='pending'")
            audit_pending = cur.fetchone()['c']
            # 用户角色分布
            cur.execute("SELECT role, COUNT(*) c FROM users GROUP BY role")
            roles = {r['role']: r['c'] for r in cur.fetchall()}
            cur.execute("SELECT COUNT(*) c FROM ai_chat_logs WHERE created_at >= %s", (datetime.now() - timedelta(days=6),))
            ai_7 = cur.fetchone()['c']
            # 近 7 天：每日新增用户 / 笔记 / AI 使用
            cur.execute("""SELECT DATE(created_at) d, COUNT(*) c FROM users
                WHERE created_at >= %s GROUP BY DATE(created_at) ORDER BY d""",
                        (datetime.now() - timedelta(days=6),))
            users_7 = [{'date': str(r['d']), 'count': r['c']} for r in cur.fetchall()]
            cur.execute("""SELECT DATE(created_at) d, COUNT(*) c FROM docs
                WHERE created_at >= %s GROUP BY DATE(created_at) ORDER BY d""",
                        (datetime.now() - timedelta(days=6),))
            docs_7 = [{'date': str(r['d']), 'count': r['c']} for r in cur.fetchall()]
        return jsonify({
            'users': user_total, 'docs': doc_total, 'docs_public': doc_public, 'docs_private': doc_private,
            'ai_usage': ai_total, 'audit_pending': audit_pending, 'ai_7': ai_7,
            'users_roles': roles,
            'users_7': users_7, 'docs_7': docs_7,
        })
    finally:
        conn.close()


# ─────────────────── 用户管理 ───────────────────
@bp.route('/api/admin/users', methods=['GET'])
@require_perm('users')
def admin_users(user):
    q = (request.args.get('q') or '').strip()
    role = (request.args.get('role') or '').strip()
    page = max(1, int(request.args.get('page') or 1))
    size = min(50, max(10, int(request.args.get('size') or 20)))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            where = []
            args = []
            if q:
                where.append("(u.username LIKE %s OR u.nickname LIKE %s OR u.email LIKE %s)")
                like = f'%{q}%'
                args += [like, like, like]
            if role:
                where.append("u.role=%s")
                args.append(role)
            wsql = ('WHERE ' + ' AND '.join(where)) if where else ''
            cur.execute(f"SELECT COUNT(*) c FROM users u {wsql}", args)
            total = cur.fetchone()['c']
            cur.execute(f"""SELECT u.id, u.username, u.nickname, u.role, u.email, u.points, u.banned, u.admin_perms,
                    CAST(u.created_at AS CHAR) created_at, u.public_id
                FROM users u {wsql} ORDER BY u.id DESC LIMIT %s OFFSET %s""",
                        args + [size, (page - 1) * size])
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                try:
                    r['admin_perms'] = r.get('admin_perms') or '[]'
                except Exception:
                    r['admin_perms'] = '[]'
        return jsonify({'total': total, 'page': page, 'items': rows})
    finally:
        conn.close()


@bp.route('/api/admin/users/<int:uid>/ban', methods=['POST'])
@require_perm('users')
def admin_ban_user(user, uid):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, role FROM users WHERE id=%s", (uid,))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': '用户不存在'}), 404
            if row['id'] == user['id']:
                return jsonify({'error': '不能封禁自己'}), 400
            cur.execute("UPDATE users SET banned=1 WHERE id=%s", (uid,))
        conn.commit()
        log_admin(conn, user['id'], 'ban_user', 'user', uid)
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@bp.route('/api/admin/users/<int:uid>/unban', methods=['POST'])
@require_perm('users')
def admin_unban_user(user, uid):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET banned=0 WHERE id=%s", (uid,))
        conn.commit()
        log_admin(conn, user['id'], 'unban_user', 'user', uid)
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@bp.route('/api/admin/users/<int:uid>', methods=['DELETE'])
@require_perm('users')
def admin_delete_user(user, uid):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, role FROM users WHERE id=%s", (uid,))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': '用户不存在'}), 404
            if row['id'] == user['id']:
                return jsonify({'error': '不能删除自己'}), 400
            # 级联清理
            for t in ('tokens', 'notifications', 'point_logs', 'reading_list', 'follows', 'friendships', 'messages'):
                try:
                    cur.execute(f"DELETE FROM {t} WHERE user_id=%s OR actor_id=%s", (uid, uid))
                except Exception:
                    pass
            cur.execute("DELETE FROM docs WHERE user_id=%s", (uid,))
            cur.execute("DELETE FROM users WHERE id=%s", (uid,))
        conn.commit()
        log_admin(conn, user['id'], 'delete_user', 'user', uid)
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ─────────────────── 笔记管理 ───────────────────
@bp.route('/api/admin/docs', methods=['GET'])
@require_perm('notes')
def admin_docs(user):
    q = (request.args.get('q') or '').strip()
    vis = (request.args.get('vis') or '').strip()
    audit = (request.args.get('audit') or '').strip()
    page = max(1, int(request.args.get('page') or 1))
    size = min(50, max(10, int(request.args.get('size') or 20)))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            where = []
            args = []
            if q:
                where.append("(d.title LIKE %s OR u.username LIKE %s OR u.nickname LIKE %s)")
                like = f'%{q}%'
                args += [like, like, like]
            if vis:
                where.append("d.visibility=%s")
                args.append(vis)
            if audit:
                where.append("d.audit_status=%s")
                args.append(audit)
            wsql = ('WHERE ' + ' AND '.join(where)) if where else ''
            cur.execute(f"SELECT COUNT(*) c FROM docs d LEFT JOIN users u ON u.id=d.user_id {wsql}", args)
            total = cur.fetchone()['c']
            cur.execute(f"""SELECT d.id, d.title, d.visibility, d.audit_status, d.audit_reason, d.type,
                    CAST(d.updated_at AS CHAR) updated_at, d.price,
                    u.username, u.nickname, u.role
                FROM docs d LEFT JOIN users u ON u.id=d.user_id {wsql}
                ORDER BY d.id DESC LIMIT %s OFFSET %s""",
                        args + [size, (page - 1) * size])
            items = [dict(r) for r in cur.fetchall()]
        return jsonify({'total': total, 'page': page, 'items': items})
    finally:
        conn.close()


@bp.route('/api/admin/docs/<int:did>/unpublish', methods=['POST'])
@require_perm('notes')
def admin_unpublish_doc(user, did):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE docs SET visibility='private' WHERE id=%s", (did,))
        conn.commit()
        log_admin(conn, user['id'], 'unpublish_doc', 'doc', did)
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@bp.route('/api/admin/docs/<int:did>', methods=['DELETE'])
@require_perm('notes')
def admin_delete_doc(user, did):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM docs WHERE id=%s", (did,))
        conn.commit()
        log_admin(conn, user['id'], 'delete_doc', 'doc', did)
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ─────────────────── 审核队列 ───────────────────
@bp.route('/api/admin/audits', methods=['GET'])
@require_perm('audit')
def admin_audits(user):
    page = max(1, int(request.args.get('page') or 1))
    size = min(50, max(10, int(request.args.get('size') or 20)))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) c FROM docs WHERE audit_status='pending'")
            total = cur.fetchone()['c']
            cur.execute("""SELECT d.id, d.title, d.visibility, d.type, d.content,
                    CAST(d.updated_at AS CHAR) updated_at, d.user_id,
                    u.username, u.nickname, u.role
                FROM docs d LEFT JOIN users u ON u.id=d.user_id
                WHERE d.audit_status='pending'
                ORDER BY d.id DESC LIMIT %s OFFSET %s""", (size, (page - 1) * size))
            items = []
            for r in cur.fetchall():
                item = dict(r)
                item['content'] = (item.get('content') or '')[:600]
                items.append(item)
        return jsonify({'total': total, 'page': page, 'items': items})
    finally:
        conn.close()


@bp.route('/api/admin/audits/<int:did>/approve', methods=['POST'])
@require_perm('audit')
def admin_approve(user, did):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE docs SET audit_status='approved', audit_reason=NULL WHERE id=%s", (did,))
        conn.commit()
        log_admin(conn, user['id'], 'audit_approve', 'doc', did)
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@bp.route('/api/admin/audits/<int:did>/reject', methods=['POST'])
@require_perm('audit')
def admin_reject(user, did):
    data = request.get_json(silent=True) or {}
    reason = (data.get('reason') or '违规内容').strip()[:255]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE docs SET audit_status='blocked', audit_reason=%s WHERE id=%s", (reason, did))
            # 下架（转私密）
            cur.execute("UPDATE docs SET visibility='private' WHERE id=%s", (did,))
        conn.commit()
        log_admin(conn, user['id'], 'audit_reject', 'doc', did, reason)
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ─────────────────── 评论管理 ───────────────────
@bp.route('/api/admin/comments', methods=['GET'])
@require_perm('comments')
def admin_comments(user):
    q = (request.args.get('q') or '').strip()
    page = max(1, int(request.args.get('page') or 1))
    size = min(50, max(10, int(request.args.get('size') or 20)))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            where = "c.content LIKE %s" if q else "1=1"
            args = [f'%{q}%'] if q else []
            cur.execute(f"SELECT COUNT(*) c FROM note_comments c {('WHERE ' + where) if q else ''}", args)
            total = cur.fetchone()['c']
            cur.execute(f"""SELECT c.id, c.content, c.doc_id, CAST(c.created_at AS CHAR) created_at,
                    u.username, u.nickname, d.title AS doc_title
                FROM note_comments c
                LEFT JOIN users u ON u.id=c.user_id
                LEFT JOIN docs d ON d.id=c.doc_id
                WHERE {where} ORDER BY c.id DESC LIMIT %s OFFSET %s""",
                        args + [size, (page - 1) * size])
            items = [dict(r) for r in cur.fetchall()]
        return jsonify({'total': total, 'page': page, 'items': items})
    finally:
        conn.close()


@bp.route('/api/admin/comments/<int:cid>', methods=['DELETE'])
@require_perm('comments')
def admin_delete_comment(user, cid):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT doc_id FROM note_comments WHERE id=%s", (cid,))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': '评论不存在'}), 404
            cur.execute("DELETE FROM note_comments WHERE id=%s", (cid,))
            # 评论数 -1
            cur.execute("UPDATE docs SET comments_count = GREATEST(comments_count-1, 0) WHERE id=%s", (row['doc_id'],))
        conn.commit()
        log_admin(conn, user['id'], 'delete_comment', 'comment', cid)
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ─────────────────── 知屿币发放 ───────────────────
@bp.route('/api/admin/coins/grant', methods=['POST'])
@require_perm('coins')
def admin_grant_coins(user):
    data = request.get_json(silent=True) or {}
    uid = data.get('user_id')
    amount = int(data.get('amount') or 0)
    note = (data.get('note') or '').strip()
    if not uid or amount <= 0 or amount > 100000:
        return jsonify({'error': '参数错误'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 支持 ID 或用户名
            if str(uid).isdigit():
                cur.execute("SELECT id, username, nickname FROM users WHERE id=%s", (int(uid),))
            else:
                cur.execute("SELECT id, username, nickname FROM users WHERE username=%s", (str(uid),))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': '用户不存在'}), 404
            target_id = row['id']
        grant_points(conn, target_id, amount, 'admin_grant')
        # 通知用户
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO notifications (user_id, actor_id, type, extra) VALUES (%s,%s,'admin_coins',%s)",
                            (target_id, user['id'], json_dumps({'amount': amount, 'note': note})))
        except Exception:
            pass
        conn.commit()
        log_admin(conn, user['id'], 'grant_coins', 'user', target_id, f'+{amount} {note}')
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@bp.route('/api/admin/coins/logs', methods=['GET'])
@require_perm('coins')
def admin_coins_logs(user):
    page = max(1, int(request.args.get('page') or 1))
    size = min(50, max(10, int(request.args.get('size') or 20)))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT COUNT(*) c FROM point_logs WHERE reason='admin_grant'""")
            total = cur.fetchone()['c']
            cur.execute("""SELECT p.id, p.user_id, p.delta, p.reason, CAST(p.created_at AS CHAR) created_at, u.username, u.nickname
                FROM point_logs p LEFT JOIN users u ON u.id=p.user_id
                WHERE p.reason='admin_grant' ORDER BY p.id DESC LIMIT %s OFFSET %s""",
                        (size, (page - 1) * size))
            items = [dict(r) for r in cur.fetchall()]
        return jsonify({'total': total, 'page': page, 'items': items})
    finally:
        conn.close()


# ─────────────────── 兑换码 ───────────────────
_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'

def _gen_code():
    import secrets as _s
    return ''.join(_s.choice(_CODE_ALPHABET) for _ in range(12))


@bp.route('/api/admin/codes/generate', methods=['POST'])
@require_perm('codes')
def admin_gen_codes(user):
    data = request.get_json(silent=True) or {}
    amount = int(data.get('amount') or 0)
    count = min(200, max(1, int(data.get('count') or 1)))
    days = int(data.get('days') or 0)
    if amount <= 0 or amount > 100000:
        return jsonify({'error': '面值错误'}), 400
    conn = get_conn()
    codes = []
    try:
        with conn.cursor() as cur:
            for _ in range(count):
                code = _gen_code()
                cur.execute("INSERT INTO redeem_codes (code, amount, created_by, expires_at) VALUES (%s,%s,%s,%s)",
                            (code, amount, user['id'], datetime.now() + timedelta(days=days) if days else None))
                codes.append(code)
        conn.commit()
        log_admin(conn, user['id'], 'gen_codes', 'code', f'x{count}', f'面值{amount}')
        conn.commit()
        return jsonify({'ok': True, 'codes': codes})
    finally:
        conn.close()


@bp.route('/api/admin/codes', methods=['GET'])
@require_perm('codes')
def admin_codes(user):
    page = max(1, int(request.args.get('page') or 1))
    size = min(50, max(10, int(request.args.get('size') or 20)))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) c FROM redeem_codes")
            total = cur.fetchone()['c']
            cur.execute("""SELECT rc.id, rc.code, rc.amount, rc.used_by, rc.used_at, rc.expires_at,
                    CAST(rc.created_at AS CHAR) created_at, u.username AS used_username
                FROM redeem_codes rc LEFT JOIN users u ON u.id=rc.used_by
                ORDER BY rc.id DESC LIMIT %s OFFSET %s""", (size, (page - 1) * size))
            items = [dict(r) for r in cur.fetchall()]
        return jsonify({'total': total, 'page': page, 'items': items})
    finally:
        conn.close()


# ─────────────────── 通知（指定/多选/全站） ───────────────────
@bp.route('/api/admin/notices', methods=['POST'])
@require_perm('notices')
def admin_notice(user):
    data = request.get_json(silent=True) or {}
    target = data.get('target')  # 'all' 或 [user_id...]
    content = (data.get('content') or '').strip()
    title = (data.get('title') or '').strip() or '系统通知'
    if not content:
        return jsonify({'error': '通知内容不能为空'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if target == 'all':
                cur.execute("SELECT id FROM users WHERE banned=0")
                uids = [r['id'] for r in cur.fetchall()]
            else:
                uids = [int(x) for x in (target or []) if str(x).isdigit()]
            extra = json_dumps({'title': title, 'content': content})
            for uid in uids:
                # 管理后台通知：不跳过自己（站长也可给自己发通知/测试）
                cur.execute("INSERT INTO notifications (user_id, actor_id, type, extra) VALUES (%s,%s,'admin_notice',%s)",
                            (uid, user['id'], extra))
        conn.commit()
        log_admin(conn, user['id'], 'notice', 'user', f'x{len(uids)}', f'{title[:20]} | {content[:60]}')
        conn.commit()
        return jsonify({'ok': True, 'sent': len(uids)})
    finally:
        conn.close()


@bp.route('/api/admin/digests', methods=['GET'])
@require_perm('notes')
def admin_digests(user):
    """AI 每日摘要历史"""
    page = max(1, int(request.args.get('page') or 1))
    size = min(50, max(10, int(request.args.get('size') or 20)))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) c FROM daily_digests")
            total = cur.fetchone()['c']
            cur.execute("""SELECT id, digest_date, summary, CAST(created_at AS CHAR) created_at
                FROM daily_digests ORDER BY digest_date DESC LIMIT %s OFFSET %s""",
                        (size, (page - 1) * size))
            items = [dict(r) for r in cur.fetchall()]
        return jsonify({'total': total, 'page': page, 'items': items})
    finally:
        conn.close()


@bp.route('/api/admin/notices/history', methods=['GET'])
@require_perm('notices')
def admin_notice_history(user):
    """已发送通知的历史记录（从 notifications 聚合，含完整标题/内容/人数）"""
    page = max(1, int(request.args.get('page') or 1))
    size = min(50, max(10, int(request.args.get('size') or 20)))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 手动通知（admin_notice）：同一批（相同 extra + 同一天）聚合为一条
            cur.execute("SELECT COUNT(DISTINCT CONCAT(extra, '-', DATE(created_at))) c FROM notifications WHERE type='admin_notice'")
            total = cur.fetchone()['c']
            cur.execute("""SELECT MAX(id) id, extra, COUNT(*) c, MAX(created_at) mt
                FROM notifications WHERE type='admin_notice'
                GROUP BY extra, DATE(created_at) ORDER BY mt DESC LIMIT %s OFFSET %s""",
                        (size, (page - 1) * size))
            items = []
            for r in cur.fetchall():
                try:
                    e = json.loads(r['extra'] or '{}')
                    title = e.get('title') or '系统通知'
                    content = e.get('content') or ''
                except Exception:
                    title = '系统通知'
                    content = (r['extra'] or '')[:120]
                items.append({
                    'id': r['id'], 'title': title, 'content': content[:120],
                    'target_id': f'x{r["c"]}', 'created_at': str(r['mt']),
                })
        return jsonify({'total': total, 'page': page, 'items': items})
    finally:
        conn.close()


# ─────────────────── 管理员管理 ───────────────────
@bp.route('/api/admin/managers', methods=['GET'])
@require_perm('admins')
def admin_managers(user):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, nickname, role, admin_perms, banned, points FROM users WHERE role IN ('admin','moderator') ORDER BY id")
            items = []
            for r in cur.fetchall():
                d = dict(r)
                try:
                    d['perms'] = json.loads(d.get('admin_perms') or '[]')
                except Exception:
                    d['perms'] = []
                items.append(d)
        return jsonify({'items': items, 'perm_labels': PERM_LABELS})
    finally:
        conn.close()


@bp.route('/api/admin/managers', methods=['POST'])
@require_perm('admins')
def admin_set_manager(user):
    data = request.get_json(silent=True) or {}
    uid = data.get('user_id')
    role = data.get('role')  # 'moderator' / 'user'（取消）
    perms = data.get('perms') or []
    if not uid:
        return jsonify({'error': '参数错误'}), 400
    if role not in ('moderator', 'user'):
        return jsonify({'error': '角色错误'}), 400
    valid = [p for p in perms if p in ALL_PERMS]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 支持 ID 或用户名
            if str(uid).isdigit():
                cur.execute("SELECT id, role FROM users WHERE id=%s", (int(uid),))
            else:
                cur.execute("SELECT id, role FROM users WHERE username=%s", (str(uid),))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': '用户不存在'}), 404
            if row['id'] == user['id']:
                return jsonify({'error': '不能修改自己的角色'}), 400
            # 站长可降级/取消其他管理员（包括其他 admin），但不能动自己
            if role == 'moderator':
                cur.execute("UPDATE users SET role='moderator', admin_perms=%s WHERE id=%s",
                            (json_dumps(valid), row['id']))
            else:
                cur.execute("UPDATE users SET role='user', admin_perms=NULL WHERE id=%s", (row['id'],))
        conn.commit()
        log_admin(conn, user['id'], 'set_manager', 'user', row['id'], f'{role} {valid}')
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@bp.route('/api/admin/site-config', methods=['GET', 'POST'])
@require_role('admin')
def admin_site_config(user):
    """站点备案配置（站长专属）：ICP/公安备案号与链接，主页页脚展示"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if request.method == 'GET':
                cur.execute("SELECT k, v FROM site_config")
                cfg = {r['k']: r['v'] for r in cur.fetchall()}
                return jsonify(cfg)
            data = request.get_json(silent=True) or {}
            keys = ['icp_no', 'icp_link', 'gongan_no', 'gongan_link']
            for k in keys:
                v = str(data.get(k) or '').strip()[:255]
                if v:
                    cur.execute("INSERT INTO site_config (k, v) VALUES (%s, %s) ON DUPLICATE KEY UPDATE v=VALUES(v)", (k, v))
                else:
                    cur.execute("DELETE FROM site_config WHERE k=%s", (k,))
        conn.commit()
        log_admin(conn, user['id'], 'site_config', 'site', '', '备案配置更新')
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ─────────────────── AI 使用日志 ───────────────────
@bp.route('/api/admin/ai-logs', methods=['GET'])
@require_perm('notes')
def admin_ai_logs(user):
    page = max(1, int(request.args.get('page') or 1))
    size = min(50, max(10, int(request.args.get('size') or 20)))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) c FROM ai_chat_logs")
            total = cur.fetchone()['c']
            cur.execute("""SELECT l.id, l.user_id, l.page, CAST(l.created_at AS CHAR) created_at, u.username, u.nickname
                FROM ai_chat_logs l LEFT JOIN users u ON u.id=l.user_id
                ORDER BY l.id DESC LIMIT %s OFFSET %s""", (size, (page - 1) * size))
            items = [dict(r) for r in cur.fetchall()]
        return jsonify({'total': total, 'page': page, 'items': items})
    finally:
        conn.close()


def json_dumps(obj):
    import json as _json
    return _json.dumps(obj, ensure_ascii=False)
