# -*- coding: utf-8 -*-
"""AI 助手：检索问答 / 流式对话 / 编辑建议 / 日志"""
from flask import Blueprint, request, jsonify, Response
import os
import re
import json
import time
import urllib.request
import urllib.error

from config import DEEPSEEK_API_KEY, DEEPSEEK_RESPONSES_URL, DEEPSEEK_RESPONSES_MODEL, FREE_AI_QUOTA
from db import get_conn
from auth import require_login

bp = Blueprint('ai', __name__)

def ai_search_context(user, question, limit=8, max_chars=4000):
    """从可见笔记中检索相关片段：关键词 LIKE 匹配 title/content"""
    words = re.findall(r'[\u4e00-\u9fa5]{2,6}|[A-Za-z]{3,}', question)
    words = [w for w in words if w][:8]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            uid = user['id'] if user else None
            base = "SELECT id, title, type, content FROM docs WHERE (visibility='public'"
            params = []
            if uid:
                base += " OR user_id=%s"; params.append(uid)
            base += ")"
            if words:
                conds = []
                for w in words:
                    conds.append("(title LIKE %s OR content LIKE %s)")
                    params += [f'%{w}%', f'%{w}%']
                base += " AND (" + " OR ".join(conds) + ")"
            base += " ORDER BY updated_at DESC LIMIT %s"
            params.append(limit)
            cur.execute(base, params)
            rows = cur.fetchall()
    finally:
        conn.close()
    ctx = []
    for r in rows:
        snippet = re.sub(r'\s+', ' ', r['content'])[:max_chars]
        ctx.append({"id": r['id'], "title": r['title'], "type": r['type'], "snippet": snippet})
    return ctx

# ── AI 工具调用（MCP 式）：让 AI 能直接读写用户的笔记 ──
AI_TOOLS = [
    {'type': 'function', 'function': {
        'name': 'read_note',
        'description': '读取一篇笔记的完整 Markdown 源码。修改笔记前若上下文里的内容不完整，可调用它获取全文。',
        'parameters': {'type': 'object', 'properties': {
            'note_id': {'type': 'integer', 'description': '笔记数字 ID（search_note 返回的「数字ID」）'},
            'public_id': {'type': 'string', 'description': '笔记 public_id（没有数字 ID 时用它）'},
        }},
    }},
    {'type': 'function', 'function': {
        'name': 'save_draft',
        'description': '把修改后的笔记内容保存为编辑草稿（不直接写入正式笔记）。用户会在编辑器的草稿里看到并确认后再保存。默认修改笔记时用它，让用户先确认。',
        'parameters': {'type': 'object', 'properties': {
            'note_id': {'type': 'integer', 'description': '笔记 ID'},
            'content': {'type': 'string', 'description': '修改后的完整笔记内容（Markdown 源码）'},
        }, 'required': ['note_id', 'content']},
    }},
    {'type': 'function', 'function': {
        'name': 'write_note',
        'description': '把修改后的完整内容写入正式笔记（自动备份旧版本，可回滚）。注意：本工具现在与 save_draft 行为一致——写入草稿而非直接覆盖正式笔记，用户会在编辑器看到红绿 diff 并确认后再保存。任何修改笔记场景（包括用户说「直接改」）都默认用它存草稿，让用户确认。',
        'parameters': {'type': 'object', 'properties': {
            'note_id': {'type': 'integer', 'description': '笔记 ID'},
            'content': {'type': 'string', 'description': '修改后的完整笔记内容（Markdown 源码）'},
        }, 'required': ['note_id', 'content']},
    }},
    {'type': 'function', 'function': {
        'name': 'search_note',
        'description': '按标题关键词搜索站内笔记，返回匹配的笔记列表（含 ID、标题、分类）。用户要求「打开/跳转到某篇笔记」但你不知道它的 ID 时，先调用它按标题搜索到 ID，再调用 navigate 跳转。',
        'parameters': {'type': 'object', 'properties': {'keyword': {'type': 'string', 'description': '标题关键词，如「数据结构大纲」'}}, 'required': ['keyword']},
    }},
    {'type': 'function', 'function': {
        'name': 'navigate',
        'description': '跳转到站内页面。可用路径：/（首页）、/notes（笔记广场）、/docs（阅览室）、/notes/{public_id}（打开某篇笔记，public_id 由 search_note 返回，不要自己编）、/edit/{id}（编辑某篇笔记，仍用数字 id）、/edit（新建笔记）、/admin（书房）、/friends（好友）、/mall（知屿币商城）、/messages（消息）、/changelog（更新日志）、/guide（使用引导）、/user/{public_id}（个人主页，不编 id）。用户要求「帮我跳转到某页 / 打开某笔记 / 去 XX」时调用；若用户只给了笔记标题而你不知道 public_id，先调用 search_note 按标题搜索得到 public_id 后再跳转。',
        'parameters': {'type': 'object', 'properties': {'to': {'type': 'string', 'description': '站内路径，如 /notes/55'}}, 'required': ['to']},
    }},
    {'type': 'function', 'function': {
        'name': 'new_note',
        'description': '新建一篇笔记并打开编辑器。用户要求「新建笔记 / 帮我写一篇新笔记 / 在某分类下写一篇笔记」时调用；content 可传预填内容，title 可传标题，type 可传分类（用户指定分类时）。',
        'parameters': {'type': 'object', 'properties': {
            'title': {'type': 'string', 'description': '笔记标题（可选）'},
            'content': {'type': 'string', 'description': '预填内容（Markdown，可选）'},
            'type': {'type': 'string', 'description': '笔记分类（可选），如「中学公式」「数据结构」'},
        }},
    }},
    {'type': 'function', 'function': {
        'name': 'send_message',
        'description': '给站内用户发送私信。用户要求「帮我给 XX 发私信 / 发消息给 XX」时调用。to 传对方的用户 ID、用户名或昵称，content 传消息内容。',
        'parameters': {'type': 'object', 'properties': {
            'to': {'type': 'string', 'description': '对方用户 ID / 用户名 / 昵称'},
            'content': {'type': 'string', 'description': '消息内容'},
        }, 'required': ['to', 'content']},
    }},
]

# Responses API 版工具：function 展平成扁平格式（name/description/parameters 顶层）+ 服务端联网搜索 web_search。
# web_search 由服务端执行：搜索结果自动注入模型上下文，无需客户端处理 web_search_call。
AI_TOOLS_RESPONSES = [
    {'type': 'function', 'name': t['function']['name'], 'description': t['function']['description'],
     'parameters': t['function'].get('parameters', {})}
    for t in AI_TOOLS
] + [{'type': 'web_search'}]

def to_public_path(to, user):
    """把 AI 生成的 /notes/{id}、/docs/{slug}、/user/{id} 等路径转成 public_id 形式（对外 URL 不暴露明文 id/slug）。"""
    m = re.match(r'^/(notes|docs|user)/([^/?#]+)', to or '')
    if not m:
        return to or '/'
    seg = m.group(2)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if m.group(1) == 'user':
                cur.execute(
                    "SELECT public_id FROM users WHERE public_id=%s OR CAST(id AS CHAR)=%s OR username=%s LIMIT 1",
                    (seg, seg, seg))
            else:
                cur.execute(
                    "SELECT public_id FROM docs "
                    "WHERE (public_id=%s OR slug=%s OR CAST(id AS CHAR)=%s) AND (visibility='public' OR user_id=%s) LIMIT 1",
                    (seg, seg, seg, user['id']))
            r = cur.fetchone()
    finally:
        conn.close()
    if r and r.get('public_id'):
        return '/' + m.group(1) + '/' + r['public_id']
    return to or '/'

def run_ai_tool(name, args, user):
    """执行 AI 工具调用，返回 (结果文本, changed)。changed=True 表示笔记/草稿有变化，前端需刷新。"""
    try:
        if name == 'read_note':
            nid = args.get('note_id')
            pid = str(args.get('public_id') or args.get('id') or '')
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    r = None
                    if nid:
                        try:
                            cur.execute("SELECT id, title, content FROM docs WHERE id=%s AND (visibility='public' OR user_id=%s)", (int(nid), user['id']))
                            r = cur.fetchone()
                        except (TypeError, ValueError):
                            pass
                    if not r and pid:
                        cur.execute("SELECT id, title, content FROM docs WHERE public_id=%s AND (visibility='public' OR user_id=%s)", (pid, user['id']))
                        r = cur.fetchone()
            finally:
                conn.close()
            if not r:
                return '找不到该笔记（不存在或无权限）', False
            return f"《{r['title']}》全文（Markdown 源码）：\n{r['content']}", False
        if name == 'save_draft':
            nid = int(args.get('note_id') or 0)
            content = str(args.get('content') or '')
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, user_id FROM docs WHERE id=%s", (nid,))
                    d = cur.fetchone()
                    if not d or d['user_id'] != user['id']:
                        return '找不到该笔记或无权限', False
                    cur.execute("INSERT INTO doc_drafts (doc_id, content) VALUES (%s, %s) ON DUPLICATE KEY UPDATE content=VALUES(content)", (nid, content))
                conn.commit()
            finally:
                conn.close()
            return '草稿已保存，用户可在编辑器里看到并确认', True
        if name == 'write_note':
            nid = int(args.get('note_id') or 0)
            content = str(args.get('content') or '')
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, user_id FROM docs WHERE id=%s", (nid,))
                    d = cur.fetchone()
                    if not d or d['user_id'] != user['id']:
                        return '找不到该笔记或无权限', False
                    # 统一走草稿（不直接写正式笔记）：前端跳到编辑器弹红绿 diff，用户确认后才真正保存
                    cur.execute("INSERT INTO doc_drafts (doc_id, content) VALUES (%s, %s) ON DUPLICATE KEY UPDATE content=VALUES(content)", (nid, content))
                conn.commit()
            finally:
                conn.close()
            return '修改内容已存为草稿，请让用户到编辑器查看红绿 diff 并确认（提示用户去编辑页）', True
        if name == 'navigate':
            # 前端动作：由 sse_gen 转发 action 事件给前端执行跳转
            # 把 id/slug 路径统一转成 public_id，保证对外 URL 不暴露明文
            return '已通知前端跳转到 ' + to_public_path(str(args.get('to') or '/'), user), False
        if name == 'search_note':
            # 按标题搜索笔记（可见范围内），返回 public_id + 标题列表供 AI 用 navigate 跳转
            keyword = str(args.get('keyword') or '').strip()
            if not keyword:
                return '请输入搜索关键词', False
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, title, type, public_id FROM docs "
                        "WHERE (visibility='public' OR user_id=%s) AND title LIKE %s "
                        "ORDER BY updated_at DESC LIMIT 10",
                        (user['id'], '%' + keyword + '%'))
                    rows = cur.fetchall()
            finally:
                conn.close()
            if not rows:
                return f'没有找到标题包含「{keyword}」的笔记', False
            lines = [f"数字ID={r['id']}，public_id={r['public_id']}，《{r['title']}》（{r['type']}）" for r in rows]
            return '按标题搜索到的笔记（read_note 用「数字ID」，navigate 跳转用 /notes/{public_id}）：\n' + '\n'.join(lines), False
        if name == 'new_note':
            # 前端动作：由 sse_gen 转发 action 事件给前端打开新建笔记编辑器
            return '已通知前端打开新建笔记编辑器', False
        if name == 'send_message':
            to = str(args.get('to') or '').strip()
            content = str(args.get('content') or '').strip()
            if not to or not content:
                return '参数不完整（需要 to 和 content）', False
            if len(content) > 2000:
                return '消息内容过长', False
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM users WHERE id=%s OR username=%s OR nickname=%s", (to, to, to))
                    target = cur.fetchone()
                    if not target:
                        return f'找不到用户：{to}', False
                    if target['id'] == user['id']:
                        return '不能给自己发私信', False
                    cur.execute("INSERT INTO messages (sender_id, receiver_id, content) VALUES (%s, %s, %s)",
                                (user['id'], target['id'], content))
                conn.commit()
            finally:
                conn.close()
            return '私信已发送', True
    except Exception as e:
        return f'工具执行出错：{e}', False
    return f'未知工具：{name}', False

def log_ai_chat(user, page, note_id, question, system_prompt, answer, reasoning, tool_names, changed, err, delta_count, elapsed_ms):
    """记录一次 AI 对话的输入输出（用于复盘/优化 prompt）。纯旁路写入，失败不影响主流程。"""
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO ai_chat_logs (user_id, page, note_id, question, system_prompt, answer, reasoning, tool_names, changed, err, delta_count, elapsed_ms) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (user['id'], page, note_id, str(question)[:2000], system_prompt,
                     str(answer or '')[:20000], str(reasoning or '')[:20000],
                     ','.join(tool_names)[:500], 1 if changed else 0, str(err or '')[:500], delta_count, elapsed_ms))
                conn.commit()
        finally:
            conn.close()
    except Exception:
        pass

@bp.route('/api/ai/chat', methods=['POST'])
@require_login
def ai_chat(user=None):
    if not DEEPSEEK_API_KEY:
        return jsonify({'error': 'AI 服务未配置'}), 503
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()
    if not question or len(question) > 500:
        return jsonify({'error': '问题需在 1-500 字内'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT ai_used, ai_quota_bonus, nickname FROM users WHERE id=%s", (user['id'],))
            u = cur.fetchone()
    finally:
        conn.close()
    used = u['ai_used'] if u else 0
    quota = FREE_AI_QUOTA + (u['ai_quota_bonus'] if u else 0)
    if used >= quota:
        return jsonify({'error': 'AI 额度已用完，可去知屿币商城兑换', 'used': used, 'quota': quota}), 402
    # 检索相关笔记（支持指定笔记全文：note_id / 编辑页未保存草稿：draft_content）
    ctx = ai_search_context(user, question)
    note_ctx = ''
    # 当前笔记全文上限：模型窗口 100w token，10 万字符（约 3-4 万 token）足够容纳绝大多数长笔记
    NOTE_CTX_MAX = 100000
    if data.get('draft_content'):
        note_ctx = f"【用户正在编辑的笔记最新草稿（未保存，以此为准）】\n{str(data.get('draft_content'))[:NOTE_CTX_MAX]}"
    elif data.get('note_id'):
        try:
            nid = int(data.get('note_id'))
            conn2 = get_conn()
            try:
                with conn2.cursor() as cur:
                    cur.execute("SELECT id, title, content FROM docs WHERE id=%s AND (visibility='public' OR user_id=%s)", (nid, user['id']))
                    nr = cur.fetchone()
            finally:
                conn2.close()
            if nr:
                note_ctx = f"【用户正在阅读的笔记《{nr['title']}》（ID: {nr['id']}）全文】\n{nr['content'][:NOTE_CTX_MAX]}"
        except Exception:
            pass
    elif data.get('note_key') or data.get('note_slug'):
        # 阅览室 /docs/:key、笔记阅读页 /notes/:key：按 public_id 读当前笔记全文（兼容旧 slug/数字 id）
        try:
            key = str(data.get('note_key') or data.get('note_slug') or '').strip()
            conn2 = get_conn()
            try:
                with conn2.cursor() as cur:
                    cur.execute("SELECT id, title, content FROM docs WHERE (public_id=%s OR slug=%s OR CAST(id AS CHAR)=%s) AND (visibility='public' OR user_id=%s)", (key, key, key, user['id']))
                    nr = cur.fetchone()
            finally:
                conn2.close()
            if nr:
                note_ctx = f"【用户正在阅读的笔记《{nr['title']}》（ID: {nr['id']}）全文】\n{nr['content'][:NOTE_CTX_MAX]}"
        except Exception:
            pass
    # 页面感知：告诉 AI 用户当前在哪个页面，从而给出对应的动作指引
    page = (data.get('page') or '').strip()
    page_hint = ''
    if page == 'notes-square':
        page_hint = ("用户当前在「笔记广场」浏览公开笔记。若用户想找某篇笔记或让你推荐，"
                     "下方【知识库相关笔记】即检索到的候选，回答里用「打开《标题》」这样的指引方便用户点开对应笔记。")
    elif page == 'note-reader':
        page_hint = "用户当前正在阅读一篇笔记（见【用户正在阅读的笔记】）。可以总结要点、讲解难点、回答疑问；不要编造该笔记没有的内容。"
    elif page == 'docs-reader':
        page_hint = ("用户当前在「阅览室」阅读自己的笔记（见【用户正在阅读的笔记】，注意 ID）。你拥有 read_note / save_draft / write_note / navigate，可直接修改这篇笔记："
                     "用户要求修改（改表格/文字/格式/重写等）时，必须调用工具，不要输出【原内容】【新内容】标记文本；"
                     "默认用 save_draft（note_id 传当前 ID，content 传修改后的完整 Markdown）存草稿让用户到编辑器确认；仅当用户明确说「直接保存/直接改/不用预览/直接应用」才用 write_note 直接写入。"
                     "上下文全文不完整时先 read_note 取全文再改。只改用户要求的部分，其他一字不改。"
                     "发现格式问题（竖排文本、LaTeX 缺失、列表混乱等）主动修复为规范 Markdown；用户说『把 X 变成表格』就转成规范表格语法（| 列1 | 列2 | / | --- | --- | / | 值 | 值 |），表格内公式用 $...$。"
                     "用户问『有没有问题/检查一下/看看这篇』时先列出问题不要改；用户同意（「改吧/修吧/都改/修复/帮我改好」）后立即执行：read_note 读全文 → save_draft 修改 → navigate 跳 /edit/{id}，一次改完所有问题，不要问『要改哪些』。"
                     "工具执行后一句话说明改了什么、在哪确认。若只是补充新增内容且不便整篇重写，输出待新增 Markdown 片段，末尾单独一行【知屿应用：追加到末尾】；只回答不修改则正常回答。")
    elif page == 'editor':
        cur_note_id = data.get('note_id')
        page_hint = ("用户当前在「笔记编辑器」编辑一篇笔记（见【用户正在编辑的笔记最新草稿】）。按用户意图处理："
                     f"你正在编辑的笔记 ID 为 {cur_note_id or '未知'}。当用户要求读取/修改当前笔记时，一律以该 ID 为准："
                     "需要全文时 read_note(note_id=当前笔记 ID)；严禁 search_note 搜索或读取其他笔记，也不要把内容加入其他笔记。"
                     "若草稿内容异常（比如看起来像对话记录而非笔记正文），仍以当前笔记数据库中的正式内容为准。"
                     "当用户要求新建笔记或写与当前笔记无关的内容时，直接新建/书写即可，无需读取当前笔记，也不要把内容加入当前笔记。"
                     "插入/追加/补充新内容：只输出要插入的 Markdown 片段（含正确编号），不输出整篇、不解释、不用 ```markdown 包裹，末尾单独一行【知屿操作：插入】。"
                     "编号从当前笔记实际章节延续：新笔记从 ## 1. 开始；已有笔记从最后一个章节号 +1 继续；禁止使用其他笔记的编号（如凭空从 12 开始）。"
                     "只输出笔记正文，禁止夹带对话、建议、征询语句（如『如果你确定…回复「新建」即可』『需要的话…』）或解释性文字。"
                     "修改/重写/整理现有内容：用 save_draft 工具（note_id 传当前笔记 ID，content 传修改后的完整笔记，未改部分原样保留）让用户确认；"
                     "若直接输出修改内容而未用工具，末尾单独一行【知屿操作：修改】。"
                     "修改前若不确定笔记最新全文（本地草稿可能过期），先 read_note 取当前笔记最新再改，不要基于过期草稿。"
                     "若用户要求修改/设置笔记标题（如『标题改成 xxx』『把标题改为…』），末尾单独一行【知屿标题：新标题】声明（新标题写在冒号后），与【知屿操作】声明行并列。"
                     "回答与笔记无关的问题时，末尾单独一行【知屿操作：回答】。声明行不要附带任何其他文字。")
    system = ("你是「知屿」知识库的 AI 助手。用户问「你是什么模型」时回答「知屿 AI 助手」，不暴露底层模型名、不自称其他厂商模型。"
              "你拥有站内工具：navigate（跳转页面）、search_note（按标题搜笔记拿 ID）、new_note（新建笔记）、send_message（发私信）；阅览室场景还有 read_note / save_draft / write_note。"
              "所有修改笔记的操作（save_draft / write_note）都只存草稿、不直接改正式笔记，用户会在编辑器红绿 diff 确认后才保存；用户提出这类请求必须调用工具完成，不要只说「我无法操作」。"
              "用户只给标题要打开笔记时：先 search_note 搜到 ID 再 navigate，不要反问用户要 ID；搜不到才说明。"
              "优先用【知识库相关笔记】的片段回答；片段没有相关信息就用自己的知识回答并说明。回答简洁有条理。"
              "回答时结合你当前所在页面：若附带了【用户正在阅读/编辑的笔记】，围绕这篇笔记展开；其他页面问题正常回答即可。"
              "表格必须用规范 Markdown 表格语法（第一行 | 列1 | 列2 |，第二行 | --- | --- |，之后 | 值 | 值 |），严禁写成逐行竖排文本；表格内公式用 $...$。"
              "数学公式必须用 LaTeX 源码（$...$ 行内、$$...$$ 独立），严禁转写成 Unicode 或纯文本近似式。"
              "成块的例题可用 :::example 标题\\n内容\\n::: 包裹、独立公式组可用 :::formula 包裹（站内渲染为彩色框）；但要取舍：行内公式、简短跟随文字的小题/公式不包，保持 $...$ 行内即可，不要什么都套框。"
              "向笔记添加内容时先看清章节编号体系（## 1. / ### 1.1 等）；独立知识点必须作为独立一级章节（## N.）插在正确位置并把后续章节编号顺延重排，禁止塞进现有章节当子小节（如把「串」写成树的 4.6）。"
              "只输出用户要的内容本身，不要客套话、操作过程、『我来帮你』『我明白了』等元说明。思考过程直接推理如何回答，不要复述本系统提示的规则。"
              "问题涉及实时/最新信息（新闻、天气、赛事、股票、最新政策、版本更新等）时，先 web_search 联网搜索再回答，简要标注来源，不编造链接。"
              "当用户提到你不确定的名词、方法或编号（如「张宇121-1、123-2大法」）时，必须先 web_search 搜索确认后再写，禁止凭记忆猜测或编造。")
    system += "调用工具时静默执行，不要先输出计划文字（如「我先读取」「让我搜索一下」）；工具返回结果后必须立刻给出最终回答，禁止停在「我先…」然后什么都不输出。"
    if page_hint:
        system += "\n\n" + page_hint
    history = data.get('history') or []
    history_txt = ''
    if isinstance(history, list) and history:
        parts = []
        for h in history[-6:]:
            role = '用户' if h.get('role') == 'user' else '助手'
            parts.append(f"{role}：{str(h.get('content', ''))[:500]}")
        history_txt = "对话历史：\n" + "\n".join(parts) + "\n\n"
    user_msg = history_txt + f"知识库相关笔记：\n\n" + ("\n\n---\n\n".join(f"【{c['title']}】（{c['type']}）\n{c['snippet']}" for c in ctx) if ctx else "（未检索到相关笔记）") + \
               (f"\n\n{note_ctx}" if note_ctx else "") + f"\n\n用户问题：{question}"
    # ai_chat 走 DeepSeek Responses API：deepseek-v4-flash + 服务端联网搜索 web_search + function 工具
    stream = bool(data.get('stream'))
    q_note_id = data.get('note_id')

    def mark_used():
        try:
            conn2 = get_conn()
            try:
                with conn2.cursor() as cur:
                    cur.execute("UPDATE users SET ai_used = ai_used + 1 WHERE id=%s", (user['id'],))
                    conn2.commit()
            finally:
                conn2.close()
        except Exception:
            pass

    if stream:
        def sse_gen():
            try:
                t0 = time.time()
                answer_buf = ''
                reasoning_buf = ''
                delta_count = 0
                tool_names = []
                err_txt = ''
                # Responses API 无状态：input 每轮重建完整列表（初始 user 消息 + 历轮 function_call / function_call_output）
                input_items = [{'role': 'user', 'content': user_msg}]
                changed = False
                charge = True   # 服务端明确失败（response.failed）时不扣费
                truncated = False  # response.incomplete：回答被截断
                # 工具调用循环（最多 3 轮：AI 可自主读笔记 → 写草稿/改笔记，或联网搜索后给出答案）
                for _round in range(6):
                    resp_payload = {
                        'model': DEEPSEEK_RESPONSES_MODEL,
                        'instructions': system,
                        'input': input_items,
                        'tools': AI_TOOLS_RESPONSES,
                        'tool_choice': 'auto',
                        'temperature': 0.7,
                        'reasoning': {'effort': 'none'},  # 关闭思考：v4 思考极慢（默认 50s+），用户只要结果
                        'stream': True,
                    }
                    req2 = urllib.request.Request(
                        DEEPSEEK_RESPONSES_URL,
                        data=json.dumps(resp_payload).encode('utf-8'),
                        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {DEEPSEEK_API_KEY}'},
                        method='POST',
                    )
                    tool_calls = []  # [{call_id, name, arguments}]
                    saw_reasoning = False
                    with urllib.request.urlopen(req2, timeout=180) as resp:
                        for raw in resp:
                            line = raw.decode('utf-8', errors='ignore').strip()
                            if not line.startswith('data:'):
                                continue
                            data = line[5:].strip()
                            if not data:
                                continue
                            try:
                                obj = json.loads(data)
                            except Exception:
                                continue
                            ev = obj.get('type') or ''
                            if ev == 'response.output_text.delta':
                                d = re.sub(r'\\+([a-zA-Z])', r'\\\1', obj.get('delta') or '')
                                answer_buf += d
                                delta_count += 1
                                # 逐 token 转发（真流式打字机）。工具轮思考与最终轮正文都流式显示，
                                # 前端在流式结束后用正则把开头思考段挪进 🧠 折叠框。
                                yield f"data: {json.dumps({'delta': d}, ensure_ascii=False)}\n\n"
                            elif ev == 'response.reasoning_text.delta':
                                r = obj.get('delta') or ''
                                if r:
                                    saw_reasoning = True
                                    reasoning_buf += r
                                    yield f"data: {json.dumps({'reasoning': r}, ensure_ascii=False)}\n\n"
                            elif ev == 'response.output_item.done':
                                item = obj.get('item') or {}
                                if item.get('type') == 'function_call':
                                    tool_calls.append({
                                        'call_id': item.get('call_id') or f'call_{len(tool_calls)}',
                                        'name': item.get('name') or '',
                                        'arguments': item.get('arguments') or '',
                                    })
                                elif item.get('type') == 'web_search_call':
                                    yield f"data: {json.dumps({'web_search': 'searching'}, ensure_ascii=False)}\n\n"
                            elif ev == 'response.web_search_call.searching':
                                yield f"data: {json.dumps({'web_search': 'searching'}, ensure_ascii=False)}\n\n"
                            elif ev == 'response.web_search_call.completed':
                                yield f"data: {json.dumps({'web_search': 'completed'}, ensure_ascii=False)}\n\n"
                            elif ev == 'response.incomplete':
                                # 输出被截断（如达 max_output_tokens）：标记，done 事件告知前端，避免半截回答被当完整版
                                truncated = True
                            elif ev == 'response.failed':
                                err = ((obj.get('response') or {}).get('error') or {})
                                err_msg = err.get('message') or err.get('code') or 'response.failed'
                                charge = False  # 服务端明确失败：不扣费
                                yield f"data: {json.dumps({'error': 'AI 服务错误: ' + str(err_msg)}, ensure_ascii=False)}\n\n"
                                return
                            # response.completed / response.incomplete：本轮回流结束，落到下方统一收尾
                    if not tool_calls:
                        # 无工具调用：最终回答（内容已逐 token 转发完）
                        if saw_reasoning:
                            yield f"data: {json.dumps({'reasoning_done': True}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'done': True, 'changed': changed, 'incomplete': truncated, 'context_notes': [{'id': c['id'], 'title': c['title'], 'type': c['type']} for c in ctx]}, ensure_ascii=False)}\n\n"
                        break
                    # 执行工具：function_call 与执行结果 function_call_output 按顺序追加进 input_items
                    for tc in tool_calls:
                        input_items.append({'type': 'function_call', 'call_id': tc['call_id'], 'name': tc['name'], 'arguments': tc['arguments']})
                    for tc in tool_calls:
                        name = tc['name']
                        tool_names.append(name)
                        try:
                            args = json.loads(tc['arguments'] or '{}')
                        except Exception:
                            args = {}
                        result, chg = run_ai_tool(name, args, user)
                        if chg:
                            changed = True
                        input_items.append({'type': 'function_call_output', 'call_id': tc['call_id'], 'output': result})
                        # 前端动作工具：把 action 事件推给前端执行（跳转 / 新建笔记）
                        if name == 'navigate':
                            yield f"data: {json.dumps({'action': {'type': 'navigate', 'to': str(args.get('to') or '/')}}, ensure_ascii=False)}\n\n"
                        elif name == 'new_note':
                            yield f"data: {json.dumps({'action': {'type': 'new_note', 'title': str(args.get('title') or ''), 'content': str(args.get('content') or ''), 'category': str(args.get('type') or '')}}, ensure_ascii=False)}\n\n"
                    yield f"data: {json.dumps({'tool': name}, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {json.dumps({'done': True, 'changed': changed, 'incomplete': truncated, 'context_notes': [{'id': c['id'], 'title': c['title'], 'type': c['type']} for c in ctx]}, ensure_ascii=False)}\n\n"
            except urllib.error.HTTPError as e:
                detail = e.read().decode('utf-8', errors='ignore')[:300]
                err_txt = f'AI 服务错误: {e.code} {detail}'
                charge = False  # 服务端错误（5xx/429 等）没给出回答：不扣费；客户端断开（GeneratorExit）仍走 finally 扣费
                yield f"data: {json.dumps({'error': err_txt}, ensure_ascii=False)}\n\n"
            except Exception as e:
                err_txt = f'AI 服务异常: {str(e)}'
                charge = False
                yield f"data: {json.dumps({'error': err_txt}, ensure_ascii=False)}\n\n"
            finally:
                if charge:
                    mark_used()
                log_ai_chat(user, page, q_note_id, question, system, answer_buf, reasoning_buf, tool_names, changed, err_txt, delta_count, int((time.time() - t0) * 1000))
        return Response(sse_gen(), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    # 非流式：同样支持工具调用循环（Responses API）
    input_items = [{'role': 'user', 'content': user_msg}]
    answer = ''
    changed = False
    actions = []
    names = []
    t0n = time.time()
    truncated = False
    for _round in range(6):
        resp_payload = {
            'model': DEEPSEEK_RESPONSES_MODEL,
            'instructions': system,
            'input': input_items,
            'tools': AI_TOOLS_RESPONSES,
            'tool_choice': 'auto',
            'temperature': 0.7,
            'reasoning': {'effort': 'none'},  # 关闭思考：v4 思考极慢（默认 50s+），用户只要结果
            'stream': False,
        }
        req2 = urllib.request.Request(
            DEEPSEEK_RESPONSES_URL,
            data=json.dumps(resp_payload).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {DEEPSEEK_API_KEY}'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req2, timeout=180) as resp:
                result = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', errors='ignore')[:200]
            return jsonify({'error': f'AI 服务错误: {e.code} {detail}'}), 502
        except Exception as e:
            return jsonify({'error': f'AI 服务异常: {str(e)}'}), 502
        # Responses 层失败（HTTP 200 但 status=failed）：报错且不扣费
        if result.get('status') == 'failed':
            err = result.get('error') or {}
            return jsonify({'error': 'AI 服务错误: ' + str(err.get('message') or err.get('code') or 'response.failed')}), 502
        if result.get('status') == 'incomplete':
            truncated = True  # 输出被截断（如达 max_output_tokens）
        # 从 output 数组提取：message 文本（output_text 块）+ function_call
        tool_calls = []
        for item in result.get('output') or []:
            if item.get('type') == 'message':
                for c in item.get('content') or []:
                    if c.get('type') == 'output_text':
                        answer += c.get('text') or ''
            elif item.get('type') == 'function_call':
                tool_calls.append({
                    'call_id': item.get('call_id') or f'call_{len(tool_calls)}',
                    'name': item.get('name') or '',
                    'arguments': item.get('arguments') or '',
                })
        if not tool_calls:
            break
        # 执行工具：function_call 与 function_call_output 按顺序追加进 input_items
        for tc in tool_calls:
            input_items.append({'type': 'function_call', 'call_id': tc['call_id'], 'name': tc['name'], 'arguments': tc['arguments']})
        for tc in tool_calls:
            name = tc['name']
            names.append(name)
            try:
                args = json.loads(tc['arguments'] or '{}')
            except Exception:
                args = {}
            res_txt, chg = run_ai_tool(name, args, user)
            if chg:
                changed = True
            input_items.append({'type': 'function_call_output', 'call_id': tc['call_id'], 'output': res_txt})
            if name == 'navigate':
                actions.append({'type': 'navigate', 'to': str(args.get('to') or '/')})
            elif name == 'new_note':
                actions.append({'type': 'new_note', 'title': str(args.get('title') or ''), 'content': str(args.get('content') or ''), 'category': str(args.get('type') or '')})
        continue
    # 计数
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET ai_used = ai_used + 1 WHERE id=%s", (user['id'],))
        conn.commit()
    finally:
        conn.close()
    answer = re.sub(r'\\+([a-zA-Z])', r'\\\1', answer)  # \\sin -> \sin
    log_ai_chat(user, page, data.get('note_id'), question, system, answer, '', names, changed, '', 0, int((time.time() - t0n) * 1000))
    return jsonify({'answer': answer, 'used': used + 1, 'quota': quota, 'changed': changed, 'truncated': truncated, 'actions': actions, 'context_notes': [{'id': c['id'], 'title': c['title'], 'type': c['type']} for c in ctx]})

@bp.route('/api/ai/logs', methods=['GET'])
@require_login
def ai_logs(user=None):
    # AI 对话日志（管理员查看，用于复盘 prompt 效果）
    if user['role'] != 'admin':
        return jsonify({'error': '无权限'}), 403
    try:
        limit = max(1, min(int(request.args.get('limit', 20)), 100))
    except Exception:
        limit = 20
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT l.id, l.user_id, u.username, l.page, l.note_id, l.question, l.answer, l.reasoning, l.tool_names, "
                "l.changed, l.err, l.delta_count, l.elapsed_ms, l.created_at "
                "FROM ai_chat_logs l LEFT JOIN users u ON u.id = l.user_id ORDER BY l.id DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({'logs': rows})

@bp.route('/api/ai/edit-suggest', methods=['POST'])
@require_login
def ai_edit_suggest(user=None):
    # AI 编辑建议：返回「锚点 + 修改后文本」列表（Cursor 式，可多处修改）。
    # 前端用 target（原文锚点）在全文里定位，展示红绿 diff，逐个接受/拒绝。
    if not DEEPSEEK_API_KEY:
        return jsonify({'error': 'AI 服务未配置'}), 503
    data = request.get_json(silent=True) or {}
    instruction = (data.get('instruction') or '').strip()
    target = (data.get('target') or '').strip()
    note_ctx = (data.get('context') or '')[:100000]
    if not instruction:
        return jsonify({'error': '请输入修改指令'}), 400
    if len(instruction) > 500:
        return jsonify({'error': '修改指令太长了（最多 500 字）'}), 400
    # 模型窗口 100w token，10 万字符（约 3-4 万 token）足够容纳绝大多数长笔记全文，无需头尾截断
    # target 可为空：表示未选中任何内容 → AI 自己定位全文中的修改/插入点（可多处）
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT ai_used, ai_quota_bonus FROM users WHERE id=%s', (user['id'],))
            u = cur.fetchone()
    finally:
        conn.close()
    used = u['ai_used'] if u else 0
    quota = FREE_AI_QUOTA + (u['ai_quota_bonus'] if u else 0)
    if used >= quota:
        return jsonify({'error': 'AI 额度已用完，可去知屿币商城兑换', 'used': used, 'quota': quota}), 402
    system = (
        '你是「知屿」知识库的 AI 编辑助手，帮用户在笔记编辑器里修改 Markdown 笔记。'
        '用户会提供【笔记上下文】（整篇 Markdown 源码）、【选中内容】（可能为空）和【修改指令】。'
        '你必须只输出一个 JSON 对象（不要输出任何解释、Markdown 代码块包裹或客套话），格式：'
        '{"edits": [{"target": "...", "replacement": "..."}]}。'
        '其中 target 是笔记中【原文】的一段（作为定位锚点，前端用它精确找到修改位置），'
        'replacement 是这段内容修改后的【完整替换文本】。'
        '规则：'
        '1. target 必须逐字取自【笔记上下文】，可以是单行、多行、公式或表格的原文，'
        '   必须足够独特以便前端能唯一匹配（最好包含标题行或前几行上下文），不要截断在句子中间；'
        '   如果是【新增】场景，target 填插入位置前面的一小段原文锚点（如上一小节标题行或最后一行），'
        '   replacement 填「锚点原文 + 要新增的内容」。'
        '2. 一处指令可能对应多处修改（如"两个表格都没显示对"）→ 输出多个 edit，每处一个。'
        '3. 除被修改的局部外，replacement 里的其余文字必须与 target 逐字一致，禁止润色、扩写未被要求的部分；'
        '   纯新增内容则直接追加在锚点后。'
        '4. 【编号规则】新增小节标题必须带正确的整数编号：看上下文里已有 ## 编号顺序，'
        '   新节编号 = 前一个已存在小节编号 + 1（如前面是 ## 2、二倍角公式，新节写 ## 3、半角公式）；'
        '   插入在中间时同理（如在 2 和 3 之间插入就写 3）；禁止 2.5、2.1、3.1 这类非整数编号；'
        '   公式条目编号（1）（2）（3）… 严格按已有格式，每个条目单独一行、空行分隔。'
        '5. 数学公式必须用 LaTeX 源码（$...$ 行内，$$...$$ 独立），命令用单反斜杠'
        '（如 \\frac、\\sin、\\sqrt、\\alpha），绝对禁止双反斜杠。'
        '6. 新增/修改内容的 Markdown 结构必须与笔记已有格式一致（同款 ## 标题、编号风格、公式写法）。'
        '7. 如果指令不明确或没有需要修改的地方，输出 {"edits": []}。'
        '8. 【每个 edit 必须独立】target 必须取自【原始】笔记上下文，禁止把其它 edit 的修改结果写进 target 或 replacement；'
        '多个 edit 的 target 之间不要重叠、不要互相包含。'
        '9. 【范围严格对应】replacement 的范围必须与 target 完全对应：target 覆盖哪些原文，replacement 就只替换哪些，'
        '不要把 target 之前或之后的原文（如下一行、下一个段落）写进 replacement，也不要在 replacement 末尾重复后面的原文；'
        '如果多处需要修改，就把每处写成独立的 edit，各自只覆盖自己的那一小段。'
        '10. 【空笔记】如果【笔记上下文】为空（新笔记/空白页），target 填空字符串 ""，replacement 填要写入的完整 Markdown 内容，只输出一个 edit。'
        '11. 【同位置追加合并】如果要往同一位置（如文末、某个小节末尾）追加多条内容（多个例题、多行公式、多条要点），'
        '必须合并成【一个】edit（replacement 里按顺序包含全部新增内容），'
        '禁止拆成多个 target 相同或重叠的 edit——前端一个位置只能展示一个修改块，重叠会导致部分修改看不见。'
        '12. 【例题/公式框：取舍】成块的例题可用 :::example 标题\\n内容\\n::: 包裹，独立的公式组可用 :::formula 包裹'
        '（站内会渲染成彩色框，格式与代码块类似）；但要取舍：行内公式、简短跟随文字的小题/公式不包，保持 LaTeX 行内即可，不要什么都套框。'
    )
    user_msg = ''
    if note_ctx:
        user_msg += '【笔记上下文】\n' + note_ctx + '\n\n'
    user_msg += '【选中内容】\n' + (target if target else '（未选中任何内容，请自行定位全文中的修改点）') + '\n\n'
    user_msg += '【修改指令】\n' + instruction

    # 空笔记（新页面，无任何原文）：target 锚点模型不适用，直接生成完整正文返回给前端写入
    if not note_ctx.strip():
        sys_full = (system + ' 注意：当前【笔记上下文】为空，这是一篇全新的空白笔记。'
                    '你直接生成完整的 Markdown 正文（可用 ## 小节标题、要点列表、LaTeX 公式用 $...$ / $$...$$ 源码），'
                    '输出正文本身即可；不要输出 JSON、不要输出解释、不要用 ```markdown 包裹。')
        payload_full = {
            'model': DEEPSEEK_RESPONSES_MODEL,
            'instructions': sys_full,
            'input': [{'role': 'user', 'content': user_msg}],
            'temperature': 0.5,
            'reasoning': {'effort': 'none'},
            'stream': False,
        }
        req_full = urllib.request.Request(
            DEEPSEEK_RESPONSES_URL,
            data=json.dumps(payload_full).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + DEEPSEEK_API_KEY},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req_full, timeout=90) as resp:
                result_full = json.loads(resp.read().decode('utf-8'))
            raw_full = ''
            for item in result_full.get('output') or []:
                if item.get('type') == 'message':
                    for c in item.get('content') or []:
                        if c.get('type') == 'output_text':
                            raw_full += c.get('text') or ''
            raw_full = raw_full.strip()
            raw_full = re.sub(r'\\+([a-zA-Z])', r'\\\1', raw_full)  # \\sin -> \sin
            if not raw_full:
                return jsonify({'error': 'AI 没有返回有效内容，请换个说法重试'}), 422
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', errors='ignore')[:200]
            return jsonify({'error': 'AI 服务错误: ' + str(e.code) + ' ' + detail}), 502
        except Exception as e:
            return jsonify({'error': 'AI 服务异常: ' + str(e)}), 502
        try:
            conn2 = get_conn()
            try:
                with conn2.cursor() as cur:
                    cur.execute('UPDATE users SET ai_used = ai_used + 1 WHERE id=%s', (user['id'],))
                conn2.commit()
            finally:
                conn2.close()
        except Exception:
            pass
        return jsonify({'content': raw_full, 'used': used + 1, 'quota': quota})

    payload = {
        'model': DEEPSEEK_RESPONSES_MODEL,
        'instructions': system,
        'input': [{'role': 'user', 'content': user_msg}],
        'temperature': 0.4,
        'reasoning': {'effort': 'none'},
        'text': {'format': {'type': 'json_object'}},
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
        raw = ''
        for item in result.get('output') or []:
            if item.get('type') == 'message':
                for c in item.get('content') or []:
                    if c.get('type') == 'output_text':
                        raw += c.get('text') or ''
        raw = raw.strip()
        # 解析 JSON（容错：去掉可能的外层 ```json 包裹 / 提取首个 {…}）
        import re as _re
        m = _re.search(r'\{.*\}', raw, _re.S)
        data_out = json.loads(m.group(0)) if m else {}
        edits = data_out.get('edits') if isinstance(data_out, dict) else None
        if not isinstance(edits, list):
            edits = []
        if len(edits) > 20:
            edits = edits[:20]
        cleaned = []
        for e in edits:
            if not isinstance(e, dict):
                continue
            t = str(e.get('target') or '').strip()
            r = str(e.get('replacement') or '').strip()
            if not r:
                continue
            # 空笔记场景：target 为空表示整篇新增（仅当笔记上下文为空时允许）
            if not t and note_ctx.strip():
                continue
            # AI 常把 LaTeX 写成双反斜杠，归一为单反斜杠
            r = _re.sub(r'\\+([a-zA-Z])', r'\\\1', r)
            cleaned.append({'target': t, 'replacement': r})
        if not cleaned:
            return jsonify({'error': 'AI 没有返回有效的修改方案，请换个说法重试', 'raw': raw[:300]}), 422
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', errors='ignore')[:200]
        return jsonify({'error': 'AI 服务错误: ' + str(e.code) + ' ' + detail}), 502
    except Exception as e:
        return jsonify({'error': 'AI 服务异常: ' + str(e)}), 502
    try:
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                cur.execute('UPDATE users SET ai_used = ai_used + 1 WHERE id=%s', (user['id'],))
            conn2.commit()
        finally:
            conn2.close()
    except Exception:
        pass
    return jsonify({'edits': cleaned, 'used': used + 1, 'quota': quota})
