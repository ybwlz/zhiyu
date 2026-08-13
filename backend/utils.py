# -*- coding: utf-8 -*-
"""纯工具函数（不依赖 db/auth），供共享层与各路由使用。"""
import re
import json
import secrets
import urllib.request
from datetime import datetime

from config import DEEPSEEK_API_KEY, DEEPSEEK_RESPONSES_URL, DEEPSEEK_RESPONSES_MODEL

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


# ═══════════════ 管理后台：内容审核与审计 ═══════════════

# 内置敏感词库（免费秒拦的第一道防线；AI 负责更精细的二审）
SENSITIVE_WORDS = [
    '赌博', '博彩', '六合彩', '时时彩', '外围赌球', '棋牌代理',
    '裸聊', '约炮', '卖淫', '嫖娼', '援交', '包养', '一夜情',
    '代开发票', '发票代开', '办证', '假证', '代孕', '卵子交易',
    '刷单', '兼职日结', '打字员日结', '加QQ', '加微信', '加vx', 'v信',
    '传销', '资金盘', '庞氏', '拉人头', '直销模式',
    '冰毒', '海洛因', '摇头丸', '大麻出售', '毒品', '制毒',
    '枪支', '弹药', '军火', '爆炸物', '雷管', '手榴弹',
    '法轮', '邪教', '全能神', '颠覆', '恐怖袭击', 'isis', '基地组织',
    '儿童色情', '幼女', '强奸', '迷奸', '诈骗', '电信诈骗', '洗钱',
]
# 拼音/变体常见绕过词（简单覆盖，AI 兜底更全）
SENSITIVE_WORDS += ['du博', 'dubo', 'piao娼', 'maiyin', 'dupin', 'qiangzhi']

def check_sensitive(text):
    """第一道防线：内置敏感词匹配，命中返回词，未命中返回 None"""
    if not text:
        return None
    for w in SENSITIVE_WORDS:
        if w in text:
            return w
    return None

def ai_moderate(text, max_len=3000):
    """AI 内容审核（第二道防线）。返回 {'pass': bool, 'reason': str}；
    AI 不可用（无 key/超时/接口异常）返回 None → 由调用方走"先上架+待审"。"""
    if not DEEPSEEK_API_KEY:
        return None
    content = text[:max_len] if text else ''
    if not content.strip():
        return {'pass': True, 'reason': ''}
    system = ('你是内容安全审核员。判断用户内容是否违规，违规类别：政治敏感、色情低俗、'
              '暴力恐怖、毒品枪支、赌博、诈骗、广告导流（留联系方式引流）、辱骂攻击他人。'
              '仅输出 JSON，格式：{"pass": true} 或 {"pass": false, "reason": "简短违规原因（20字内）"}。')
    try:
        payload = json.dumps({
            'model': DEEPSEEK_RESPONSES_MODEL,
            'instructions': system,
            'input': content,
        }).encode('utf-8')
        req = urllib.request.Request(DEEPSEEK_RESPONSES_URL, data=payload, headers={
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + DEEPSEEK_API_KEY,
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        # responses 接口：取 output_text
        out = data.get('output_text') or ''
        m = re.search(r'\{.*\}', out, re.S)
        if m:
            obj = json.loads(m.group(0))
            return {'pass': bool(obj.get('pass', True)), 'reason': obj.get('reason', '')[:60]}
        return {'pass': True, 'reason': ''}
    except Exception:
        return None

def log_admin(conn, admin_id, action, target_type='', target_id='', detail=''):
    """记录管理操作（审计留痕）"""
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO admin_logs (admin_id, action, target_type, target_id, detail) VALUES (%s,%s,%s,%s,%s)",
                        (admin_id, action, target_type, str(target_id), detail[:255]))
    except Exception:
        pass
