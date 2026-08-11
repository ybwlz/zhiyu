# -*- coding: utf-8 -*-
"""路由间共享的业务函数（依赖 db/auth/utils，避免 routes 互相 import 形成环）。"""
from flask import jsonify

from db import get_conn
from auth import get_current_user
from utils import DOC_SELECT, can_view_doc

def fetch_doc_visible(doc_id=None, slug=None, key=None):
    """取文档并按可见性过滤，返回 (doc, error_resp)。key 兼容 public_id / 明文 slug / 数字 id。"""
    user = get_current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if doc_id is not None:
                cur.execute(DOC_SELECT + ", d.content FROM docs d LEFT JOIN users u ON d.user_id=u.id WHERE d.id=%s", (doc_id,))
            elif key is not None:
                cur.execute(DOC_SELECT + ", d.content FROM docs d LEFT JOIN users u ON d.user_id=u.id WHERE d.public_id=%s OR d.slug=%s OR CAST(d.id AS CHAR)=%s", (key, key, key))
            else:
                cur.execute(DOC_SELECT + ", d.content FROM docs d LEFT JOIN users u ON d.user_id=u.id WHERE d.slug=%s", (slug,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None, (jsonify({'error': 'not_found'}), 404)
    if not can_view_doc(user, row):
        return None, (jsonify({'error': 'forbidden'}), 403)
    # 收费仅预览：未购买者只能看前 500 字
    if row.get('preview_only') and not (user and (user.get('id') == row.get('user_id') or user.get('role') == 'admin')):
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                cur.execute("SELECT id FROM purchased_docs WHERE user_id=%s AND doc_id=%s", (user['id'] if user else 0, row['id']))
                bought = cur.fetchone()
        finally:
            conn2.close()
        if not bought:
            content = row.get('content') or ''
            row['content'] = content[:500]
            row['preview'] = True
    return row, None
