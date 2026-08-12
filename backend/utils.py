# -*- coding: utf-8 -*-
"""纯工具函数（不依赖 db/auth），供共享层与各路由使用。"""
import re
import secrets
from datetime import datetime

def gen_public_id():
    """生成对外展示用的不可猜测短 ID（去掉易混淆字符 O/0/I/l/1）。"""
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
    return ''.join(secrets.choice(alphabet) for _ in range(10))

def make_slug(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r'[^a-z0-9\u4e00-\u9fa5]+', '-', s)
    s = re.sub(r'-{2,}', '-', s).strip('-')
    return s or 'doc'

def ensure_unique_slug(conn, base_slug: str) -> str:
    slug = base_slug
    idx = 1
    with conn.cursor() as cur:
        while True:
            cur.execute("SELECT COUNT(*) AS cnt FROM docs WHERE slug=%s", (slug,))
            if cur.fetchone()['cnt'] == 0:
                return slug
            idx += 1
            slug = f"{base_slug}-{idx}"

def grant_points(conn, user_id, delta, reason):
    """给用户加/减知屿币并记日志"""
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET points = points + %s WHERE id=%s", (delta, user_id))
        cur.execute("INSERT INTO point_logs (user_id, delta, reason) VALUES (%s, %s, %s)", (user_id, delta, reason))

def daily_points(conn, user_id, reason, limit):
    """返回该用户当日某原因已获得知屿币；达到 limit 后不再加币"""
    with conn.cursor() as cur:
        cur.execute("""SELECT COALESCE(SUM(delta),0) AS got FROM point_logs
            WHERE user_id=%s AND reason=%s AND DATE(created_at)=CURDATE()""", (user_id, reason))
        return cur.fetchone()['got']

_ALLOWED_COUNT_COLS = {'likes_count', 'favorites_count', 'comments_count', 'downloads_count'}

def bump_doc_count(conn, doc_id, col, delta):
    # 列名白名单：防止拼接注入
    if col not in _ALLOWED_COUNT_COLS:
        return
    with conn.cursor() as cur:
        cur.execute(f"UPDATE docs SET {col} = GREATEST({col} + %s, 0) WHERE id=%s", (delta, doc_id))

def add_friend_row(conn, user_id, friend_id, status):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO friendships (user_id, friend_id, status) VALUES (%s, %s, %s)",
                    (user_id, friend_id, status))

def can_view_doc(user, doc):
    """文档可见性：public 任何人；private 仅本人或 admin（无主系统笔记同规则）"""
    if not doc:
        return False
    if doc.get('visibility') == 'public':
        return True
    if user:
        if doc.get('user_id') and doc['user_id'] == user['id']:
            return True
        if user['role'] == 'admin':
            return True
    return False

# 图片引用：支持 ![alt](url)、![alt](url "=宽x高")(带 title 尺寸参数，空格+引号，不截断 URL)
IMG_RE = re.compile(r'!\[[^\]]*\]\(([^)\s]+)(?:\s+["\'][^"\']*["\'])?\)')
DOC_SELECT = """SELECT d.id, d.type, d.title, d.slug, d.public_id, d.visibility,
    d.likes_count, d.favorites_count, d.comments_count, d.downloads_count, d.pinned_until,
    d.downloadable, d.price, d.preview_only, d.format, d.attachment,
    d.origin_id,
    CAST(d.updated_at AS CHAR) as updated_at, CAST(d.created_at AS CHAR) as created_at,
    d.user_id, u.nickname AS author_nickname, u.username AS author_username, u.avatar AS author_avatar, u.public_id AS author_public_id"""

def notify(conn, user_id, actor_id, ntype, doc_id=None):
    """给 user_id 插入一条通知（actor 触发，排除自己通知自己）"""
    if not user_id or user_id == actor_id:
        return
    with conn.cursor() as cur:
        cur.execute("INSERT INTO notifications (user_id, actor_id, type, doc_id) VALUES (%s, %s, %s, %s)",
                    (user_id, actor_id, ntype, doc_id))
