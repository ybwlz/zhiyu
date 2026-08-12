# -*- coding: utf-8 -*-
"""文档：列表 / 按 key / 创建 / 复制到书房 / 收藏副本 / 更新 / 草稿 / 删除"""
from flask import Blueprint, request, jsonify
import os
import json
import re
import secrets
from datetime import datetime

from config import UPLOAD_FOLDER
from db import get_conn
from auth import get_current_user, require_login
from shared import fetch_doc_visible
from utils import (IMG_RE, DOC_SELECT, can_view_doc, make_slug, ensure_unique_slug,
                   gen_public_id, grant_points, daily_points, bump_doc_count)

bp = Blueprint('docs', __name__)

@bp.route('/api/docs', methods=['GET'])
def list_docs():
    try:
        user = get_current_user()
        scope = request.args.get('scope', 'mixed')  # mixed|mine|public
        type_filter = request.args.get('type', '').strip()
        search = request.args.get('search', '').strip()
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                sql = DOC_SELECT + ", d.content AS content FROM docs d LEFT JOIN users u ON d.user_id=u.id WHERE 1=1"
                params = []
                uid = user['id'] if user else None
                if scope == 'mine':
                    sql += " AND d.user_id=%s"; params.append(uid)
                elif scope == 'public':
                    sql += " AND d.visibility='public'"
                else:  # mixed：公开 + 自己的
                    if uid:
                        sql += " AND (d.visibility='public' OR d.user_id=%s OR d.user_id IS NULL)"; params.append(uid)
                    else:
                        sql += " AND (d.visibility='public' OR d.user_id IS NULL)"
                if type_filter:
                    sql += " AND d.type=%s"; params.append(type_filter)
                if search:
                    sql += " AND (d.title LIKE %s OR d.content LIKE %s OR d.type LIKE %s)"
                    params += [f'%{search}%', f'%{search}%', f'%{search}%']
                sql += " ORDER BY (d.pinned_until IS NOT NULL AND d.pinned_until > NOW()) DESC, d.updated_at DESC"
                cur.execute(sql, params)
                rows = cur.fetchall()
                # 列表只返回前 2000 字做预览，但提前从完整正文提取图片列表（不受截断影响）
                for r in rows:
                    c = r.get('content') or ''
                    imgs = []
                    for m in IMG_RE.finditer(c):
                        u = m.group(1)
                        if u.startswith('/uploads/') or re.search(r'\.(?:png|jpe?g|gif|webp)(?:[?#]|$)', u, re.I):
                            imgs.append(u)
                        if len(imgs) >= 5:
                            break
                    r['preview_imgs'] = imgs
                    r['content'] = c[:2000]
                # 登录用户：标记我赞过/收藏过
                if user:
                    cur.execute("SELECT doc_id FROM note_likes WHERE user_id=%s", (user['id'],))
                    liked_set = {r['doc_id'] for r in cur.fetchall()}
                    cur.execute("SELECT doc_id FROM note_favorites WHERE user_id=%s", (user['id'],))
                    faved_set = {r['doc_id'] for r in cur.fetchall()}
                    for r in rows:
                        r['liked_by_me'] = r['id'] in liked_set
                        r['faved_by_me'] = r['id'] in faved_set
        finally:
            conn.close()
        return jsonify(rows)
    except Exception as e:
        print('[ERROR]', e)
        return jsonify({'error': 'server_error'}), 500


@bp.route('/api/docs/by-key/<key>', methods=['GET'])
def get_doc_by_key(key: str):
    """按对外 key（public_id）取文档；兼容旧链接（明文 slug / 数字 id）。"""
    try:
        row, err = fetch_doc_visible(key=key)
        if err:
            return err
        return jsonify(row)
    except Exception as e:
        print('[ERROR]', e)
        return jsonify({'error': 'server_error'}), 500

@bp.route('/api/docs/by-slug/<slug>', methods=['GET'])
def get_doc_by_slug(slug: str):
    try:
        row, err = fetch_doc_visible(slug=slug)
        if err:
            return err
        return jsonify(row)
    except Exception as e:
        print('[ERROR]', e)
        return jsonify({'error': 'server_error'}), 500

@bp.route('/api/docs/<int:doc_id>', methods=['GET'])
def get_doc(doc_id: int):
    try:
        row, err = fetch_doc_visible(doc_id=doc_id)
        if err:
            return err
        return jsonify(row)
    except Exception as e:
        print('[ERROR]', e)
        return jsonify({'error': 'server_error'}), 500

@bp.route('/api/docs', methods=['POST'])
@require_login
def create_doc(user=None):
    """创建笔记：md 文本 / 附件（pdf/ppt/word/图片等）/ JSON 文本创建（编辑器/AI 构建/涂鸦）"""
    try:
        file = request.files.get('file')
        if request.is_json:
            type_val = (request.json.get('type') or '').strip()
            title_val = (request.json.get('title') or '').strip()
            visibility = (request.json.get('visibility') or 'private').strip()
        else:
            type_val = (request.form.get('type') or '').strip()
            title_val = (request.form.get('title') or '').strip()
            visibility = (request.form.get('visibility') or 'private').strip()
        if not type_val or not title_val:
            return jsonify({'error': 'bad_request'}), 400
        if visibility not in ('public', 'private'):
            visibility = 'private'
        downloadable = 1
        price = 0
        preview_only = 0
        if request.is_json:
            downloadable = 1 if request.json.get('downloadable', 1) else 0
            price = int(request.json.get('price') or 0)
            if price < 0 or price > 99999:
                return jsonify({'error': '价格需在 0~99999 之间'}), 400
            preview_only = 1 if request.json.get('preview_only') else 0
        fmt = 'md'
        attachment = None
        content_val = ''
        if file:
            ext = (file.filename or '').rsplit('.', 1)[-1].lower() if '.' in (file.filename or '') else ''
            # 真实大小校验（FileStorage.content_length 通常不可用）
            try:
                file.stream.seek(0, os.SEEK_END)
                fsize = file.stream.tell()
                file.stream.seek(0)
            except Exception:
                fsize = 0
            if fsize > 5 * 1024 * 1024:
                return jsonify({'error': '文件不能超过 5MB'}), 400
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            tmp_name = f"tmp_{secrets.token_hex(8)}"
            tmp_path = os.path.join(UPLOAD_FOLDER, tmp_name)
            file.save(tmp_path)
            if ext in ('md', 'txt'):
                with open(tmp_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content_val = f.read()
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            else:
                # 附件扩展名白名单（禁止 .html/.svg 等可执行/嗅探类型落盘）
                ALLOWED_ATT = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar', '7z',
                               'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp3', 'mp4', 'csv', 'txt'}
                if ext not in ALLOWED_ATT:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                    return jsonify({'error': '不支持的文件类型'}), 400
                att_dir = os.path.join(UPLOAD_FOLDER, 'attachments')
                try:
                    os.makedirs(att_dir, exist_ok=True)
                except Exception:
                    pass
                att_name = f"{secrets.token_hex(8)}.{ext}" if ext else f"{secrets.token_hex(8)}"
                att_path = os.path.join(att_dir, att_name)
                try:
                    os.replace(tmp_path, att_path)
                except Exception:
                    import shutil
                    try:
                        shutil.move(tmp_path, att_path)
                    except Exception:
                        with open(att_path, 'wb') as wf, open(tmp_path, 'rb') as rf:
                            wf.write(rf.read())
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
                attachment = f"attachments/{att_name}"
                fmt = ext or 'file'
                content_val = f'这是一篇 {ext.upper() if ext else "附件"} 笔记。\n\n> 附件已保存，可在预览中打开或下载。'
        elif request.is_json and request.json.get('content'):
            content_val = request.json.get('content')
            fmt = (request.json.get('format') or 'md')[:16]
            if request.json.get('attachment'):
                attachment = request.json.get('attachment')[:255]
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                base_slug = make_slug(title_val)
                slug_val = ensure_unique_slug(conn, base_slug)
                pid_val = gen_public_id()
                cur.execute(
                    "INSERT INTO docs (type, title, slug, public_id, content, user_id, visibility, format, attachment, downloadable, price, preview_only, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (type_val, title_val, slug_val, pid_val, content_val, user['id'], visibility, fmt, attachment, downloadable, price, preview_only, datetime.now(), datetime.now())
                )
                new_id = cur.lastrowid
            if visibility == 'public' and daily_points(conn, user['id'], 'note_published', 9) < 9:
                grant_points(conn, user['id'], 3, 'note_published')
            conn.commit()
        finally:
            conn.close()
        return jsonify({'id': new_id, 'slug': slug_val, 'public_id': pid_val})
    except Exception as e:
        print('[ERROR]', e)
        return jsonify({'error': 'server_error'}), 500

@bp.route('/api/docs/<int:doc_id>/copy-to-studio', methods=['POST'])
@require_login
def copy_doc_to_studio(doc_id: int, user=None):
    """涂鸦保存：广场笔记 → 复制一份到我的书房（含涂鸦，原版不动）；书房笔记 → 涂鸦直接挂到当前笔记（仅本人可见）。"""
    try:
        data = request.get_json(silent=True) or {}
        strokes = data.get('strokes') or []
        if not isinstance(strokes, list):
            strokes = []
        canvas_w = int(data.get('canvas_w') or 0)
        canvas_h = int(data.get('canvas_h') or 0)
        strokes_json = json.dumps(strokes, ensure_ascii=False)
        row, err = fetch_doc_visible(doc_id=doc_id)
        if err:
            return err
        if row.get('preview'):
            return jsonify({'error': '该笔记需购买后才能复制到书房'}), 403
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                if row.get('user_id') == user['id']:
                    # 已是自己的笔记：不复制，涂鸦直接挂到当前笔记
                    if strokes:
                        cur.execute(
                            "INSERT INTO note_annotations (doc_id, user_id, strokes, canvas_w, canvas_h, kind) VALUES (%s, %s, %s, %s, %s, 'doodle')",
                            (doc_id, user['id'], strokes_json, canvas_w, canvas_h)
                        )
                    conn.commit()
                    return jsonify({'id': doc_id, 'copied': False, 'title': row['title']})
                # 别人的笔记：复制副本到书房（含涂鸦），原版不动
                new_title = row['title'] + '（批注版）'
                base_slug = make_slug(new_title)
                slug_val = ensure_unique_slug(conn, base_slug)
                pid_val = gen_public_id()
                cur.execute(
                    "INSERT INTO docs (type, title, slug, public_id, content, user_id, visibility, format, attachment, downloadable, price, preview_only, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, 'private', %s, %s, 0, 0, 0, %s, %s)",
                    (row['type'], new_title, slug_val, pid_val, row['content'], user['id'], row.get('format') or 'md', row.get('attachment'), datetime.now(), datetime.now())
                )
                new_id = cur.lastrowid
                if strokes:
                    cur.execute(
                        "INSERT INTO note_annotations (doc_id, user_id, strokes, canvas_w, canvas_h, kind) VALUES (%s, %s, %s, %s, %s, 'doodle')",
                        (new_id, user['id'], strokes_json, canvas_w, canvas_h)
                    )
            conn.commit()
        finally:
            conn.close()
        return jsonify({'id': new_id, 'copied': True, 'title': new_title})
    except Exception as e:
        print('[ERROR]', e)
        return jsonify({'error': 'server_error'}), 500

@bp.route('/api/docs/<int:doc_id>/collect', methods=['POST'])
@require_login
def collect_doc(doc_id: int, user=None):
    # 收藏为副本：把公开笔记复制成自己的私有副本并加入阅览室（幂等，原版不动，副本可编辑）
    try:
        row, err = fetch_doc_visible(doc_id=doc_id)
        if err:
            return err
        if row.get('preview'):
            return jsonify({'error': '该笔记需购买后才能收藏'}), 403
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                # 幂等：已有同源副本则直接返回
                cur.execute("SELECT id FROM docs WHERE user_id=%s AND origin_id=%s LIMIT 1", (user['id'], doc_id))
                exist = cur.fetchone()
                if exist:
                    return jsonify({'id': exist['id'], 'copied': False, 'title': row['title']})
                new_title = row['title']  # 加入书房：标题保留原名，来源用 origin_id 角标标识
                base_slug = make_slug(new_title)
                slug_val = ensure_unique_slug(conn, base_slug)
                pid_val = gen_public_id()
                cur.execute(
                    "INSERT INTO docs (type, title, slug, public_id, content, user_id, visibility, format, attachment, downloadable, price, preview_only, origin_id, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, 'private', %s, %s, 0, 0, 0, %s, %s, %s)",
                    (row['type'], new_title, slug_val, pid_val, row['content'], user['id'], row.get('format') or 'md', row.get('attachment'), doc_id, datetime.now(), datetime.now())
                )
                new_id = cur.lastrowid
                # 副本自动加入阅览室
                cur.execute("INSERT INTO reading_list (user_id, doc_id, source) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE source=VALUES(source)",
                            (user['id'], new_id, 'collect'))
            conn.commit()
        finally:
            conn.close()
        return jsonify({'id': new_id, 'copied': True, 'title': new_title})
    except Exception as e:
        print('[ERROR]', e)
        return jsonify({'error': 'server_error'}), 500

@bp.route('/api/docs/<int:doc_id>', methods=['PUT'])
@require_login
def update_doc(doc_id: int, user=None):
    try:
        data = request.get_json(silent=True) or {}
        type_val = data.get('type')
        title_val = data.get('title')
        content_val = data.get('content')
        if type_val is None or title_val is None or content_val is None:
            return jsonify({'error': 'bad_request'}), 400
        visibility = data.get('visibility')
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, user_id FROM docs WHERE id=%s", (doc_id,))
                doc = cur.fetchone()
                if not doc:
                    return jsonify({'error': 'not_found'}), 404
                # 归属校验：无主系统笔记仅 admin 可改；有主笔记仅本人
                if doc['user_id'] is None:
                    if user['role'] != 'admin':
                        return jsonify({'error': 'forbidden'}), 403
                elif doc['user_id'] != user['id']:
                    return jsonify({'error': 'forbidden'}), 403
                base_slug = make_slug(title_val)
                slug_val = ensure_unique_slug(conn, base_slug)
                # 修改前备份旧版本到 doc_versions（改错可回滚）
                cur.execute("INSERT INTO doc_versions (doc_id, title, content) SELECT id, title, content FROM docs WHERE id=%s", (doc_id,))
                dl = data.get('downloadable')
                price = data.get('price')
                pv = data.get('preview_only')
                new_price = int(price or 0) if price is not None else 0
                if new_price < 0 or new_price > 99999:
                    return jsonify({'error': '价格需在 0~99999 之间'}), 400
                if visibility in ('public', 'private'):
                    cur.execute(
                        "UPDATE docs SET type=%s, title=%s, slug=%s, content=%s, visibility=%s, downloadable=%s, price=%s, preview_only=%s, updated_at=%s WHERE id=%s",
                        (type_val, title_val, slug_val, content_val, visibility,
                         1 if dl is None else (1 if dl else 0),
                         new_price,
                         1 if pv else 0, datetime.now(), doc_id)
                    )
                else:
                    cur.execute(
                        "UPDATE docs SET type=%s, title=%s, slug=%s, content=%s, downloadable=%s, price=%s, preview_only=%s, updated_at=%s WHERE id=%s",
                        (type_val, title_val, slug_val, content_val,
                         1 if dl is None else (1 if dl else 0),
                         new_price,
                         1 if pv else 0, datetime.now(), doc_id)
                    )
            conn.commit()
        finally:
            conn.close()
        # 保存成功后清除对应草稿（AI 草稿已应用）
        try:
            conn2 = get_conn()
            try:
                with conn2.cursor() as cur2:
                    cur2.execute("DELETE FROM doc_drafts WHERE doc_id=%s", (doc_id,))
                conn2.commit()
            finally:
                conn2.close()
        except Exception:
            pass
        return jsonify({'success': True, 'slug': slug_val})
    except Exception as e:
        print('[ERROR]', e)
        return jsonify({'error': 'server_error'}), 500

@bp.route('/api/docs/<int:doc_id>/draft', methods=['GET'])
@require_login
def get_doc_draft(doc_id: int, user=None):
    # 读取编辑草稿（AI 工具 save_draft 写入），仅本人可读
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, user_id FROM docs WHERE id=%s", (doc_id,))
            d = cur.fetchone()
            if not d or d['user_id'] != user['id']:
                return jsonify({'error': 'forbidden'}), 403
            cur.execute("SELECT content FROM doc_drafts WHERE doc_id=%s", (doc_id,))
            r = cur.fetchone()
    finally:
        conn.close()
    return jsonify({'draft': r['content'] if r else None})

@bp.route('/api/docs/<int:doc_id>', methods=['DELETE'])
@require_login
def delete_doc(doc_id: int, user=None):
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, user_id FROM docs WHERE id=%s", (doc_id,))
                doc = cur.fetchone()
                if not doc:
                    return jsonify({'error': 'not_found'}), 404
                # 归属校验：无主系统笔记仅 admin 可改；有主笔记仅本人
                if doc['user_id'] is None:
                    if user['role'] != 'admin':
                        return jsonify({'error': 'forbidden'}), 403
                elif doc['user_id'] != user['id']:
                    return jsonify({'error': 'forbidden'}), 403
                # 级联清理关联数据（草稿/版本/点赞/收藏/分享/评论/批注/阅读记录）
                for tbl in ('doc_drafts', 'doc_versions', 'note_likes', 'note_favorites', 'note_shares',
                            'note_comments', 'note_annotations', 'reading_list'):
                    cur.execute(f"DELETE FROM {tbl} WHERE doc_id=%s", (doc_id,))
                cur.execute("DELETE FROM docs WHERE id=%s", (doc_id,))
            conn.commit()
        finally:
            conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print('[ERROR]', e)
        return jsonify({'error': 'server_error'}), 500
