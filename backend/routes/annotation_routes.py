# -*- coding: utf-8 -*-
"""涂鸦批注：列表 / 保存 / 贴图 / 更新 / 删除"""
from flask import Blueprint, request, jsonify
import os
import json
import secrets

from config import UPLOAD_FOLDER
from db import get_conn
from auth import require_login
from shared import fetch_doc_visible

bp = Blueprint('annotations', __name__)

@bp.route('/api/notes/<int:doc_id>/annotations', methods=['GET'])
@require_login
def note_annotations_get(doc_id, user=None):
    """我的批注列表（个人学习批注，仅本人可见）"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id, strokes, canvas_w, canvas_h, kind, para_idx, sel_text, note_text, img_path,
                                  CAST(created_at AS CHAR) AS created_at
                FROM note_annotations WHERE doc_id=%s AND user_id=%s ORDER BY created_at ASC""",
                (doc_id, user['id']))
            rows = cur.fetchall()
    finally:
        conn.close()
    for r in rows:
        try:
            r['strokes'] = json.loads(r['strokes'])
        except Exception:
            r['strokes'] = []
    return jsonify(rows)

@bp.route('/api/notes/<int:doc_id>/annotations', methods=['POST'])
@require_login
def note_annotations_save(doc_id, user=None):
    """保存一页批注（strokes 为 [{points:[[x,y]...], color, width}]，canvas_w/h 为绘制时尺寸）"""
    row, err = fetch_doc_visible(doc_id=doc_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    kind = (data.get('kind') or 'doodle')[:12]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if kind in ('note', 'bookmark', 'image'):
                # 段落级批注 / 书签 / 贴图
                para_idx = data.get('para_idx')
                try:
                    para_idx = int(para_idx) if para_idx is not None else None
                except (TypeError, ValueError):
                    para_idx = None
                sel_text = str(data.get('sel_text') or '')[:500]
                note_text = str(data.get('note_text') or '')[:2000]
                img_path = str(data.get('img_path') or '')[:255] or None
                # 批注允许空内容创建（先插占位，文字/笔迹随后防抖保存）
                cur.execute("""INSERT INTO note_annotations (doc_id, user_id, strokes, canvas_w, canvas_h, kind, para_idx, sel_text, note_text, img_path)
                    VALUES (%s, %s, '', 0, 0, %s, %s, %s, %s, %s)""",
                    (doc_id, user['id'], kind, para_idx, sel_text, note_text, img_path))
                aid = cur.lastrowid
            else:
                strokes = data.get('strokes')
                if not isinstance(strokes, list):
                    return jsonify({'error': 'bad_request'}), 400
                if len(strokes) > 200 or len(json.dumps(strokes)) > 200000:
                    return jsonify({'error': '批注过大'}), 400
                try:
                    w = max(0, min(int(data.get('canvas_w') or 0), 10000))
                    h = max(0, min(int(data.get('canvas_h') or 0), 10000))
                except (TypeError, ValueError):
                    w = h = 0
                cur.execute("""INSERT INTO note_annotations (doc_id, user_id, strokes, canvas_w, canvas_h)
                    VALUES (%s, %s, %s, %s, %s)""",
                    (doc_id, user['id'], json.dumps(strokes, ensure_ascii=False), w, h))
                aid = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'id': aid})

@bp.route('/api/annotations/upload-img', methods=['POST'])
@require_login
def annotation_upload_img(user=None):
    """段落批注贴图（base64 → 附件存储，返回路径）"""
    data = request.get_json(silent=True) or {}
    b64 = str(data.get('img') or '')
    if not b64 or len(b64) > 3 * 1024 * 1024:
        return jsonify({'error': '图片过大或为空'}), 400
    try:
        import base64
        header, sep, body = b64.partition(',')
        raw = base64.b64decode(body if sep else header)
    except Exception:
        return jsonify({'error': '图片格式错误'}), 400
    if len(raw) > 2 * 1024 * 1024:
        return jsonify({'error': '图片不能超过 2MB'}), 400
    # 魔数校验（防伪造扩展名的非图片内容落盘）
    magic = raw[:12]
    is_img = (magic.startswith(b'\x89PNG\r\n\x1a\n')
              or magic.startswith(b'\xff\xd8\xff')
              or magic.startswith(b'GIF87a') or magic.startswith(b'GIF89a')
              or (magic[:4] == b'RIFF' and magic[8:12] == b'WEBP'))
    if not is_img:
        return jsonify({'error': '图片格式不支持'}), 400
    att_dir = os.path.join(UPLOAD_FOLDER, 'attachments')
    try:
        os.makedirs(att_dir, exist_ok=True)
    except Exception:
        pass
    ext = '.png'
    if 'jpeg' in b64[:40] or 'jpg' in b64[:40]: ext = '.jpg'
    elif 'gif' in b64[:40]: ext = '.gif'
    elif 'webp' in b64[:40]: ext = '.webp'
    name = f"ann_{secrets.token_hex(8)}{ext}"
    with open(os.path.join(att_dir, name), 'wb') as f:
        f.write(raw)
    return jsonify({'success': True, 'path': f"attachments/{name}"})

@bp.route('/api/annotations/<int:aid>', methods=['PUT'])
@require_login
def note_annotations_update(aid, user=None):
    """更新批注：文字(note_text) 或 手绘(strokes+canvas_w/h)。批注框内防抖局部保存用，不碰正文"""
    data = request.get_json(silent=True) or {}
    sets, vals = [], []
    if 'note_text' in data:
        sets.append('note_text=%s'); vals.append(str(data.get('note_text') or '')[:5000])
    if 'img_path' in data:
        sets.append('img_path=%s'); vals.append(str(data.get('img_path') or '')[:255] or None)
    if 'strokes' in data:
        strokes = data.get('strokes')
        if not isinstance(strokes, list):
            return jsonify({'error': 'bad_request'}), 400
        if len(strokes) > 200 or len(json.dumps(strokes)) > 200000:
            return jsonify({'error': '批注过大'}), 400
        sets.append('strokes=%s'); vals.append(json.dumps(strokes, ensure_ascii=False))
    if 'canvas_w' in data or 'canvas_h' in data:
        try:
            w = max(0, min(int(data.get('canvas_w') or 0), 10000))
            h = max(0, min(int(data.get('canvas_h') or 0), 10000))
        except (TypeError, ValueError):
            w = h = 0
        sets.append('canvas_w=%s'); vals.append(w)
        sets.append('canvas_h=%s'); vals.append(h)
    if not sets:
        return jsonify({'error': 'nothing_to_update'}), 400
    vals.append(aid); vals.append(user['id'])
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE note_annotations SET " + ', '.join(sets) + " WHERE id=%s AND user_id=%s", vals)
            affected = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    if affected == 0:
        return jsonify({'error': 'not_found'}), 404
    return jsonify({'success': True})

@bp.route('/api/annotations/<int:aid>', methods=['DELETE'])
@require_login
def note_annotations_delete(aid, user=None):
    """删除自己的批注页"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM note_annotations WHERE id=%s AND user_id=%s", (aid, user['id']))
            affected = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    if affected == 0:
        return jsonify({'error': 'not_found'}), 404
    return jsonify({'success': True})
