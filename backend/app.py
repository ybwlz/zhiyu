from flask import Flask, request, jsonify, make_response, send_from_directory, Response
from flask_cors import CORS
import os
import json
import threading
import time
import urllib.request
import secrets
import smtplib
from email.mime.text import MIMEText
from functools import wraps
import pymysql
from pymysql.cursors import DictCursor
from datetime import datetime, timedelta
import re
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
# CORS 白名单（仅允许前端站点跨域）
CORS(app, resources={r"/api/*": {"origins": [
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:4173", "http://192.168.1.230:5173",
]}})
CORS(app)

DB_HOST = os.getenv('DB_HOST')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME', 'doc_manager')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_server_conn():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        charset='utf8mb4',
        cursorclass=DictCursor
    )

def get_conn():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4',
        cursorclass=DictCursor,
        autocommit=False
    )

def init_db():
    server_conn = get_server_conn()
    with server_conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    server_conn.commit()
    server_conn.close()

    conn = get_conn()
    with conn.cursor() as cur:
        # 笔记版本历史：每次修改前自动备份旧内容，改错可回滚（AI 修改/用户编辑都有备份）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS doc_versions (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                doc_id BIGINT NOT NULL,
                title VARCHAR(255),
                content LONGTEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_doc (doc_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        # 编辑草稿（后端版）：AI 工具 save_draft 写入，编辑器打开时检查
        cur.execute("""
            CREATE TABLE IF NOT EXISTS doc_drafts (
                doc_id BIGINT PRIMARY KEY,
                content LONGTEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS docs (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                type VARCHAR(100) NOT NULL,
                title VARCHAR(255) NOT NULL,
                slug VARCHAR(255) NOT NULL UNIQUE,
                public_id VARCHAR(16),
                content LONGTEXT NOT NULL,
                downloadable TINYINT NOT NULL DEFAULT 1,
                price INT NOT NULL DEFAULT 0,
                preview_only TINYINT NOT NULL DEFAULT 0,
                format VARCHAR(16) NOT NULL DEFAULT 'md',
                attachment VARCHAR(255),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        try:
            cur.execute("ALTER TABLE docs ADD COLUMN slug VARCHAR(255) NOT NULL UNIQUE")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE docs ADD COLUMN public_id VARCHAR(16) NULL")
        except Exception:
            pass
        try:
            cur.execute("CREATE UNIQUE INDEX uq_docs_public_id ON docs(public_id)")
        except Exception:
            pass
        # 用户表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                username VARCHAR(64) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(16) NOT NULL DEFAULT 'user',
                nickname VARCHAR(64),
                public_id VARCHAR(16),
                email VARCHAR(128),
                email_verified TINYINT NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        try:
            cur.execute("ALTER TABLE users ADD COLUMN public_id VARCHAR(16) NULL")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE users ADD COLUMN email VARCHAR(128)")
            cur.execute("ALTER TABLE users ADD COLUMN email_verified TINYINT NOT NULL DEFAULT 0")
        except Exception:
            pass
        try:
            cur.execute("CREATE UNIQUE INDEX uq_users_public_id ON users(public_id)")
        except Exception:
            pass
        try:
            cur.execute("CREATE UNIQUE INDEX uq_users_email ON users(email)")
        except Exception:
            pass
        # ── 用户资料扩展：头像/简介/喜好/积分/阅读时长 ──
        for col, ddl in [
            ("avatar", "VARCHAR(255)"),
            ("bio", "VARCHAR(255)"),
            ("interests", "VARCHAR(255)"),
            ("points", "INT NOT NULL DEFAULT 0"),
            ("read_seconds", "INT NOT NULL DEFAULT 0"),
            ("ai_used", "INT NOT NULL DEFAULT 0"),
            ("ai_quota_bonus", "INT NOT NULL DEFAULT 0"),
            ("badge", "VARCHAR(32) DEFAULT NULL"),
            ("cover", "VARCHAR(255) DEFAULT NULL"),
            ("likes_public", "TINYINT NOT NULL DEFAULT 1"),
            ("favorites_public", "TINYINT NOT NULL DEFAULT 1"),
            ("username_changed_at", "DATETIME DEFAULT NULL"),
        ]:
            try:
                cur.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
            except Exception:
                pass
        # ── 持久化登录会话（token 存库，服务重启不失效） ──
        cur.execute("""CREATE TABLE IF NOT EXISTS tokens (
            token CHAR(48) PRIMARY KEY,
            user_id BIGINT NOT NULL,
            expires_at DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        # ── 主页背景历史（QQ 风格，可回看历史背景） ──
        cur.execute("""CREATE TABLE IF NOT EXISTS user_covers (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id BIGINT NOT NULL,
            cover VARCHAR(255) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_uid (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        # ── docs 多用户化：user_id / 可见性 / 互动计数 ──
        for col, ddl in [
            ("user_id", "BIGINT DEFAULT NULL"),
            ("visibility", "VARCHAR(16) NOT NULL DEFAULT 'private'"),
            ("likes_count", "INT NOT NULL DEFAULT 0"),
            ("favorites_count", "INT NOT NULL DEFAULT 0"),
            ("comments_count", "INT NOT NULL DEFAULT 0"),
            ("downloads_count", "INT NOT NULL DEFAULT 0"),
            ("pinned_until", "DATETIME DEFAULT NULL"),
            ("origin_id", "BIGINT DEFAULT NULL"),
        ]:
            try:
                cur.execute(f"ALTER TABLE docs ADD COLUMN {col} {ddl}")
            except Exception:
                pass
        # 旧笔记归属：迁移给第一个 admin（若无主则保持 NULL=系统笔记）
        cur.execute("SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1")
        first_admin = cur.fetchone()
        if first_admin:
            cur.execute("UPDATE docs SET user_id=%s, visibility='private' WHERE user_id IS NULL", (first_admin['id'],))

        # AI 官方账号（username='ai'）：默认关注所有用户，可在私信里直接与它聊天
        cur.execute("SELECT id FROM users WHERE username='ai'")
        ai_row = cur.fetchone()
        ai_id = ai_row['id'] if ai_row else None
        if ai_id is None:
            cur.execute("INSERT INTO users (username, password_hash, role, nickname, email, email_verified) VALUES (%s, %s, 'ai', %s, NULL, 1)",
                        ('ai', generate_password_hash(secrets.token_hex(24)), 'AI 助手'))
            ai_id = cur.lastrowid
        if ai_id:
            cur.execute("INSERT IGNORE INTO follows (follower_id, followee_id) SELECT %s, id FROM users WHERE id<>%s", (ai_id, ai_id))

        # ── 互动新表 ──
        cur.execute("""CREATE TABLE IF NOT EXISTS note_likes (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id BIGINT NOT NULL,
            doc_id BIGINT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_like (user_id, doc_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        cur.execute("""CREATE TABLE IF NOT EXISTS note_favorites (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id BIGINT NOT NULL,
            doc_id BIGINT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_fav (user_id, doc_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        cur.execute("""CREATE TABLE IF NOT EXISTS note_shares (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id BIGINT NOT NULL,
            doc_id BIGINT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_share (user_id, doc_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        cur.execute("""CREATE TABLE IF NOT EXISTS note_comments (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            doc_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            content TEXT NOT NULL,
            parent_id BIGINT DEFAULT NULL,
            anchor VARCHAR(128),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            KEY idx_doc (doc_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        try:
            cur.execute("ALTER TABLE note_comments ADD COLUMN anchor VARCHAR(128)")
        except Exception:
            pass
        # ── 主题评分表 ──
        cur.execute("""CREATE TABLE IF NOT EXISTS note_ratings (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            doc_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            professional TINYINT NOT NULL DEFAULT 0,
            practical TINYINT NOT NULL DEFAULT 0,
            readable TINYINT NOT NULL DEFAULT 0,
            insight TINYINT NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_rating (doc_id, user_id),
            KEY idx_doc (doc_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        cur.execute("""CREATE TABLE IF NOT EXISTS note_rating_tags (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            doc_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            tag VARCHAR(20) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_tag (doc_id, user_id, tag),
            KEY idx_doc (doc_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        for col in ("downloadable TINYINT NOT NULL DEFAULT 1", "price INT NOT NULL DEFAULT 0", "preview_only TINYINT NOT NULL DEFAULT 0",
                    "format VARCHAR(16) NOT NULL DEFAULT 'md'", "attachment VARCHAR(255)"):
            try:
                cur.execute("ALTER TABLE docs ADD COLUMN " + col)
            except Exception:
                pass
        cur.execute("""CREATE TABLE IF NOT EXISTS reading_list (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id BIGINT NOT NULL,
            doc_id BIGINT NOT NULL,
            source VARCHAR(16) NOT NULL DEFAULT 'square',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_rl (user_id, doc_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        cur.execute("""CREATE TABLE IF NOT EXISTS purchased_docs (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id BIGINT NOT NULL,
            doc_id BIGINT NOT NULL,
            price INT NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_pd (user_id, doc_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        cur.execute("""CREATE TABLE IF NOT EXISTS friendships (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id BIGINT NOT NULL,
            friend_id BIGINT NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_friend (user_id, friend_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        cur.execute("""CREATE TABLE IF NOT EXISTS follows (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            follower_id BIGINT NOT NULL,
            followee_id BIGINT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_follow (follower_id, followee_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        cur.execute("""CREATE TABLE IF NOT EXISTS messages (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            sender_id BIGINT NOT NULL,
            receiver_id BIGINT NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            read_at DATETIME NULL,
            KEY idx_msg_pair (sender_id, receiver_id),
            KEY idx_msg_recv (receiver_id, read_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        # ── 群聊 ──
        cur.execute("""CREATE TABLE IF NOT EXISTS chat_groups (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(64) NOT NULL,
            owner_id BIGINT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        cur.execute("""CREATE TABLE IF NOT EXISTS chat_group_members (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            group_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_member (group_id, user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        cur.execute("""CREATE TABLE IF NOT EXISTS group_messages (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            group_id BIGINT NOT NULL,
            sender_id BIGINT NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            KEY idx_group (group_id, id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        cur.execute("""CREATE TABLE IF NOT EXISTS point_logs (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id BIGINT NOT NULL,
            delta INT NOT NULL,
            reason VARCHAR(64) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            KEY idx_user (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        cur.execute("""CREATE TABLE IF NOT EXISTS ai_chat_logs (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id BIGINT,
            page VARCHAR(32) DEFAULT '',
            note_id BIGINT,
            question TEXT,
            system_prompt MEDIUMTEXT,
            answer MEDIUMTEXT,
            reasoning MEDIUMTEXT,
            tool_names VARCHAR(255) DEFAULT '',
            changed TINYINT(1) DEFAULT 0,
            err VARCHAR(500) DEFAULT '',
            delta_count INT DEFAULT 0,
            elapsed_ms INT DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            KEY idx_ai_logs_created (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        cur.execute("""CREATE TABLE IF NOT EXISTS notifications (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id BIGINT NOT NULL,
            actor_id BIGINT NOT NULL,
            type VARCHAR(32) NOT NULL,
            doc_id BIGINT DEFAULT NULL,
            extra TEXT NULL,
            is_read TINYINT NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            KEY idx_user (user_id, is_read)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        try:
            cur.execute("ALTER TABLE notifications ADD COLUMN extra TEXT NULL")
        except Exception:
            pass
        cur.execute("""CREATE TABLE IF NOT EXISTS daily_digests (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            digest_date DATE NOT NULL UNIQUE,
            summary TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        cur.execute("""CREATE TABLE IF NOT EXISTS note_annotations (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            doc_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            strokes LONGTEXT NOT NULL,
            canvas_w INT NOT NULL DEFAULT 0,
            canvas_h INT NOT NULL DEFAULT 0,
            kind VARCHAR(12) NOT NULL DEFAULT 'doodle',
            para_idx INT NULL,
            sel_text TEXT NULL,
            note_text TEXT NULL,
            img_path VARCHAR(255) NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            KEY idx_doc_user (doc_id, user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
        for acol in ("kind VARCHAR(12) NOT NULL DEFAULT 'doodle'", "para_idx INT NULL", "sel_text TEXT NULL", "note_text TEXT NULL", "img_path VARCHAR(255) NULL"):
            try:
                cur.execute("ALTER TABLE note_annotations ADD COLUMN " + acol)
            except Exception:
                pass
        cur.execute("""CREATE TABLE IF NOT EXISTS read_logs (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id BIGINT NOT NULL,
            doc_id BIGINT NOT NULL,
            seconds INT NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            KEY idx_user (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""")
    # 为已有文档回填 public_id（对外 URL 用不可猜测的随机短串，不暴露数字 id 或明文 slug）
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM docs WHERE public_id IS NULL")
            for row in cur.fetchall():
                cur.execute("UPDATE docs SET public_id=%s WHERE id=%s", (gen_public_id(), row['id']))
    except Exception:
        pass
    # 为已有用户回填 public_id（/user/{public_id} 对外 URL，不暴露数字 id）
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE public_id IS NULL")
            for row in cur.fetchall():
                cur.execute("UPDATE users SET public_id=%s WHERE id=%s", (gen_public_id(), row['id']))
    except Exception:
        pass
    conn.commit()
    conn.close()

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

# 为 GET 请求添加 Cache-Control 头
@app.after_request
def add_header(response):
    # 仅缓存状态码为 200 的 GET 请求
    if request.method == 'GET' and response.status_code == 200:
        # 动态数据接口（评论/互动/笔记/用户/好友/积分/AI）不缓存，避免新数据被旧缓存遮挡
        if request.path.startswith(('/api/notes/', '/api/docs', '/api/users', '/api/friends',
                                    '/api/user/', '/api/changelog', '/api/ai/')):
            response.headers['Cache-Control'] = 'no-store'
        else:
            # 其余 GET 缓存 10 分钟 (600 秒)
            response.headers['Cache-Control'] = 'public, max-age=600'
    return response

# ═══════════════ 用户认证 ═══════════════
# 内存会话：token -> username（服务重启失效，个人库够用）
SESSIONS = {}
SESSION_TTL = timedelta(days=7)

# ── 邮箱验证码 ─────────────────────────────
# EMAIL_CODES[email] = {'code': '123456', 'expires': datetime, 'last_sent': datetime}
EMAIL_CODES = {}
CODE_TTL = timedelta(minutes=10)
CODE_RESEND = timedelta(seconds=60)
CODE_MAX_TRIES = 5  # 验证码最多尝试次数，防爆破
# 开发模式：未配 SMTP 时向响应返回 dev_code（生产环境请置 DEV_MODE=0）
DEV_MODE = os.getenv('DEV_MODE', '1') == '1'

# SMTP 配置（.env 可配；未配置时验证码打印到控制台，响应带 dev_code 便于本地调试）
SMTP_HOST = os.getenv('SMTP_HOST', '')
SMTP_PORT = int(os.getenv('SMTP_PORT', '465'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASS = os.getenv('SMTP_PASS', '')
SMTP_FROM = os.getenv('SMTP_FROM', SMTP_USER)

def send_email_code(to_email, code):
    """发送验证码邮件；未配置 SMTP 时返回 False（由调用方落到控制台/dev_code）"""
    if not SMTP_HOST or not SMTP_USER:
        return False
    subject = '【知屿】邮箱验证码'
    body = f'你的知屿注册验证码是：{code}（10 分钟内有效）。如果不是你本人操作，请忽略本邮件。'
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = SMTP_FROM
    msg['To'] = to_email
    try:
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10)
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_FROM, [to_email], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print('[send_email_code] 失败:', e)
        return False

def issue_token(username):
    """签发登录 token：写入数据库（服务重启仍有效，7 天过期）"""
    token = secrets.token_hex(24)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username=%s", (username,))
            r = cur.fetchone()
            if not r:
                return token
            cur.execute("INSERT INTO tokens (token, user_id, expires_at) VALUES (%s, %s, %s)",
                        (token, r['id'], datetime.now() + SESSION_TTL))
        conn.commit()
    finally:
        conn.close()
    return token

def get_current_user():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:]
    else:
        token = auth
    if not token:
        return None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT u.id, u.username, u.role, u.nickname, u.email, u.avatar, u.cover, u.public_id, u.likes_public, u.favorites_public
                FROM tokens t JOIN users u ON u.id = t.user_id
                WHERE t.token=%s""", (token,))
            row = cur.fetchone()
            if row:
                cur.execute("SELECT expires_at FROM tokens WHERE token=%s", (token,))
                exp = cur.fetchone()['expires_at']
                if exp < datetime.now():
                    cur.execute("DELETE FROM tokens WHERE token=%s", (token,))
                    conn.commit()
                    row = None
    finally:
        conn.close()
    return row

def require_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'unauthorized'}), 401
        return f(user=user, *args, **kwargs)
    return wrapper

# ═══════════════ 积分与工具 ═══════════════
def grant_points(conn, user_id, delta, reason):
    """给用户加/减积分并记日志"""
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET points = points + %s WHERE id=%s", (delta, user_id))
        cur.execute("INSERT INTO point_logs (user_id, delta, reason) VALUES (%s, %s, %s)", (user_id, delta, reason))

def daily_points(conn, user_id, reason, limit):
    """返回该用户当日某原因已获得积分；达到 limit 后不再加分"""
    with conn.cursor() as cur:
        cur.execute("""SELECT COALESCE(SUM(delta),0) AS got FROM point_logs
            WHERE user_id=%s AND reason=%s AND DATE(created_at)=CURDATE()""", (user_id, reason))
        return cur.fetchone()['got']

def bump_doc_count(conn, doc_id, col, delta):
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

@app.route('/api/auth/send-code', methods=['POST'])
def auth_send_code():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    if not re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', email):
        return jsonify({'error': '邮箱格式不正确'}), 400
    now = datetime.now()
    prev = EMAIL_CODES.get(email)
    if prev and prev['last_sent'] and now - prev['last_sent'] < CODE_RESEND:
        return jsonify({'error': '发送太频繁，请 60 秒后再试'}), 429
    code = f'{secrets.randbelow(1000000):06d}'
    EMAIL_CODES[email] = {'code': code, 'expires': now + CODE_TTL, 'last_sent': now}
    sent = send_email_code(email, code)
    resp = {'success': True, 'sent': sent}
    if not sent and DEV_MODE:
        print(f'[DEV] 验证码 for {email}: {code}')
        resp['dev_code'] = code  # 仅开发模式返回，方便本地测试
    return jsonify(resp)

@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    code = (data.get('code') or '').strip()
    nickname = (data.get('nickname') or '').strip()
    if not re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', email):
        return jsonify({'error': '邮箱格式不正确'}), 400
    if len(password) < 6:
        return jsonify({'error': '密码至少 6 位'}), 400
    rec = EMAIL_CODES.get(email)
    if not rec or rec['expires'] < datetime.now():
        return jsonify({'error': '验证码已过期，请重新获取'}), 400
    if rec['code'] != code:
        rec['tries'] = rec.get('tries', 0) + 1
        if rec['tries'] >= CODE_MAX_TRIES:
            EMAIL_CODES.pop(email, None)
            return jsonify({'error': '验证码错误次数过多，请重新获取'}), 400
        return jsonify({'error': '验证码错误'}), 400
    # username 自动生成（邮箱前缀，冲突加短随机串），内部标识用
    base = email.split('@')[0]
    username = base[:40]
    username = re.sub(r'[^A-Za-z0-9_]', '_', username) or 'user'
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM users")
            is_first = cur.fetchone()['cnt'] == 0
            role = 'admin' if is_first else 'user'
            final_user = username
            if not is_first:
                cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE username=%s", (final_user,))
                if cur.fetchone()['cnt'] > 0:
                    final_user = f'{username[:32]}_{secrets.token_hex(3)}'
            cur.execute(
                "INSERT INTO users (username, password_hash, role, nickname, email, email_verified, public_id) VALUES (%s, %s, %s, %s, %s, 1, %s)",
                (final_user, generate_password_hash(password), role, nickname or None, email, gen_public_id())
            )
            new_id = cur.lastrowid
            # AI 官方账号自动关注新用户
            cur.execute("INSERT IGNORE INTO follows (follower_id, followee_id) SELECT id, %s FROM users WHERE username='ai'", (new_id,))
        conn.commit()
        EMAIL_CODES.pop(email, None)
    except pymysql.err.IntegrityError:
        conn.rollback()
        return jsonify({'error': '该邮箱已注册'}), 409
    finally:
        conn.close()
    return jsonify({'success': True, 'role': role})

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.get_json(silent=True) or {}
    account = (data.get('email') or data.get('username') or '').strip().lower()
    password = data.get('password') or ''
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password_hash, role, nickname, email, avatar, cover, public_id FROM users WHERE email=%s OR username=%s",
                (account, account)
            )
            user = cur.fetchone()
    finally:
        conn.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': '账号或密码错误'}), 401
    token = issue_token(user['username'])
    return jsonify({'token': token, 'user': {
        'id': user['id'], 'username': user['username'], 'role': user['role'], 'nickname': user['nickname'], 'email': user['email'], 'avatar': user['avatar'], 'cover': user['cover'], 'public_id': user['public_id']
    }})

@app.route('/api/auth/change-password', methods=['POST'])
@require_login
def auth_change_password(user=None):
    # 修改密码：校验旧密码后更新
    data = request.get_json(silent=True) or {}
    old_pw = data.get('old_password') or ''
    new_pw = data.get('new_password') or ''
    if len(new_pw) < 6:
        return jsonify({'error': '新密码至少 6 位'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT password_hash FROM users WHERE id=%s', (user['id'],))
            row = cur.fetchone()
            if not row or not check_password_hash(row['password_hash'], old_pw):
                return jsonify({'error': '旧密码不正确'}), 400
            cur.execute('UPDATE users SET password_hash=%s WHERE id=%s',
                        (generate_password_hash(new_pw), user['id']))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True})

@app.route('/api/auth/update-email', methods=['POST'])
@require_login
def auth_update_email(user=None):
    """绑定/更换邮箱：校验邮箱验证码后更新（邮箱唯一）"""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    code = (data.get('code') or '').strip()
    if not re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', email):
        return jsonify({'error': '邮箱格式不正确'}), 400
    rec = EMAIL_CODES.get(email)
    if not rec or rec['expires'] < datetime.now():
        return jsonify({'error': '验证码已过期，请重新获取'}), 400
    if rec['code'] != code:
        rec['tries'] = rec.get('tries', 0) + 1
        if rec['tries'] >= CODE_MAX_TRIES:
            EMAIL_CODES.pop(email, None)
            return jsonify({'error': '验证码错误次数过多，请重新获取'}), 400
        return jsonify({'error': '验证码错误'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email=%s AND id<>%s", (email, user['id']))
            if cur.fetchone():
                return jsonify({'error': '该邮箱已被其他账号使用'}), 409
            cur.execute("UPDATE users SET email=%s, email_verified=1 WHERE id=%s", (email, user['id']))
        conn.commit()
        EMAIL_CODES.pop(email, None)
    finally:
        conn.close()
    return jsonify({'success': True, 'email': email})

@app.route('/api/auth/update-username', methods=['POST'])
@require_login
def auth_update_username(user=None):
    """修改 ID（@用户名）：字母数字下划线 3-32 位，每月仅可修改一次"""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    if not re.match(r'^[A-Za-z0-9_]{3,32}$', username):
        return jsonify({'error': 'ID 仅限字母、数字、下划线，长度 3-32 位'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT username_changed_at FROM users WHERE id=%s", (user['id'],))
            row = cur.fetchone()
            last = row['username_changed_at']
            if last:
                days = (datetime.now() - last).days
                if days < 30:
                    return jsonify({'error': f'每月只能修改一次 ID，还需 {30 - days} 天'}), 400
            cur.execute("SELECT id FROM users WHERE username=%s AND id<>%s", (username, user['id']))
            if cur.fetchone():
                return jsonify({'error': '该 ID 已被其他人使用'}), 409
            cur.execute("UPDATE users SET username=%s, username_changed_at=NOW() WHERE id=%s", (username, user['id']))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'username': username})

@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'unauthorized'}), 401
    return jsonify(user)

@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    auth = request.headers.get('Authorization', '')
    token = auth[7:] if auth.startswith('Bearer ') else auth
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tokens WHERE token=%s", (token,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True})

# 列表预览：提取正文 markdown 图片（最多 5 张）
IMG_RE = re.compile(r'!\[[^\]]*\]\(([^)\s]+)\)')
DOC_SELECT = """SELECT d.id, d.type, d.title, d.slug, d.public_id, d.visibility,
    d.likes_count, d.favorites_count, d.comments_count, d.downloads_count, d.pinned_until,
    d.downloadable, d.price, d.preview_only, d.format, d.attachment,
    d.origin_id,
    CAST(d.updated_at AS CHAR) as updated_at, CAST(d.created_at AS CHAR) as created_at,
    d.user_id, u.nickname AS author_nickname, u.username AS author_username, u.avatar AS author_avatar, u.public_id AS author_public_id"""

@app.route('/api/docs', methods=['GET'])
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

@app.route('/api/docs/by-key/<key>', methods=['GET'])
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

@app.route('/api/docs/by-slug/<slug>', methods=['GET'])
def get_doc_by_slug(slug: str):
    try:
        row, err = fetch_doc_visible(slug=slug)
        if err:
            return err
        return jsonify(row)
    except Exception as e:
        print('[ERROR]', e)
        return jsonify({'error': 'server_error'}), 500

@app.route('/api/docs/<int:doc_id>', methods=['GET'])
def get_doc(doc_id: int):
    try:
        row, err = fetch_doc_visible(doc_id=doc_id)
        if err:
            return err
        return jsonify(row)
    except Exception as e:
        print('[ERROR]', e)
        return jsonify({'error': 'server_error'}), 500

@app.route('/api/docs', methods=['POST'])
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
            preview_only = 1 if request.json.get('preview_only') else 0
        fmt = 'md'
        attachment = None
        content_val = ''
        if file:
            ext = (file.filename or '').rsplit('.', 1)[-1].lower() if '.' in (file.filename or '') else ''
            if (file.content_length or 0) > 5 * 1024 * 1024:
                return jsonify({'error': '文件不能超过 5MB'}), 400
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

@app.route('/api/docs/<int:doc_id>/copy-to-studio', methods=['POST'])
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

@app.route('/api/docs/<int:doc_id>/collect', methods=['POST'])
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

@app.route('/api/docs/<int:doc_id>', methods=['PUT'])
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
                if visibility in ('public', 'private'):
                    cur.execute(
                        "UPDATE docs SET type=%s, title=%s, slug=%s, content=%s, visibility=%s, downloadable=%s, price=%s, preview_only=%s, updated_at=%s WHERE id=%s",
                        (type_val, title_val, slug_val, content_val, visibility,
                         1 if dl is None else (1 if dl else 0),
                         int(price or 0) if price is not None else 0,
                         1 if pv else 0, datetime.now(), doc_id)
                    )
                else:
                    cur.execute(
                        "UPDATE docs SET type=%s, title=%s, slug=%s, content=%s, downloadable=%s, price=%s, preview_only=%s, updated_at=%s WHERE id=%s",
                        (type_val, title_val, slug_val, content_val,
                         1 if dl is None else (1 if dl else 0),
                         int(price or 0) if price is not None else 0,
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

@app.route('/api/docs/<int:doc_id>/draft', methods=['GET'])
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

@app.route('/api/docs/<int:doc_id>', methods=['DELETE'])
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

@app.route('/api/notes/<int:doc_id>/interact', methods=['GET'])
def note_interact(doc_id):
    """互动状态（供页面初始化）"""
    row, err = fetch_doc_visible(doc_id=doc_id)
    if err:
        return err
    return jsonify(_interact_state(doc_id, get_current_user()))

@app.route('/api/notes/<int:doc_id>/like', methods=['POST'])
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
        # 笔记作者获得 1 积分（排除自己给自己点赞）
        if row.get('user_id') and row['user_id'] != user['id']:
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

@app.route('/api/notes/<int:doc_id>/rating', methods=['GET'])
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

@app.route('/api/notes/<int:doc_id>/rating', methods=['POST'])
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

@app.route('/api/notes/<int:doc_id>/like', methods=['DELETE'])
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

@app.route('/api/notes/<int:doc_id>/favorite', methods=['POST'])
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
            grant_points(conn, row['user_id'], 1, 'note_favorited')
            notify(conn, row['user_id'], user['id'], 'favorite', doc_id)
        conn.commit()
        return jsonify({'success': True, 'favorites_count': row.get('favorites_count', 0) + 1})
    except pymysql.err.IntegrityError:
        conn.rollback()
        return jsonify({'error': 'already_favorited'}), 409
    finally:
        conn.close()

@app.route('/api/notes/<int:doc_id>/favorite', methods=['DELETE'])
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

@app.route('/api/notes/<int:doc_id>/share', methods=['POST'])
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
            grant_points(conn, row['user_id'], 2, 'note_shared')
        conn.commit()
        return jsonify({'success': True})
    except pymysql.err.IntegrityError:
        conn.rollback()
        return jsonify({'error': 'already_shared'}), 409
    finally:
        conn.close()

@app.route('/api/notes/<int:doc_id>/comments', methods=['GET'])
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

@app.route('/api/notes/<int:doc_id>/comments', methods=['POST'])
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

@app.route('/api/notes/<int:doc_id>/comments/<int:comment_id>', methods=['DELETE'])
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

@app.route('/api/notes/<int:doc_id>/download', methods=['POST'])
def note_download(doc_id):
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

@app.route('/api/notes/<int:doc_id>/read', methods=['POST'])
@require_login
def note_read(doc_id, user=None):
    """阅读时长上报：累计阅读时长；每满 60 秒得 1 积分（每日上限 60 分）"""
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
            # 当日已获阅读积分
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
# ═══════════════ 用户主页 / 资料 / 好友 / 积分 ═══════════════

@app.route('/api/users/by-key/<key>', methods=['GET'])
def user_by_key(key: str):
    """按对外 key（public_id）取用户；兼容旧链接（数字 id / 用户名）。"""
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE public_id=%s LIMIT 1", (key,))
                r = cur.fetchone()
        finally:
            conn.close()
        if not r:
            return jsonify({'error': 'not_found'}), 404
        return user_profile(r['id'])
    except Exception as e:
        print('[ERROR]', e)
        return jsonify({'error': 'server_error'}), 500

@app.route('/api/users/<int:uid>', methods=['GET'])
def user_profile(uid):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id, username, nickname, avatar, cover, bio, interests, points, read_seconds, badge, public_id,
                likes_public, favorites_public,
                CAST(created_at AS CHAR) AS created_at FROM users WHERE id=%s""", (uid,))
            u = cur.fetchone()
            if not u:
                return jsonify({'error': 'not_found'}), 404
            cur.execute("SELECT COUNT(*) AS c FROM docs WHERE user_id=%s AND visibility='public'", (uid,))
            u['public_notes'] = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) AS c FROM docs WHERE user_id=%s", (uid,))
            u['total_notes'] = cur.fetchone()['c']
            # 隐私：他人访问时不暴露私有笔记数
            viewer = get_current_user()
            if not (viewer and viewer['id'] == uid):
                u.pop('total_notes', None)
            cur.execute("""SELECT COUNT(*) AS c FROM note_likes l
                JOIN docs d ON l.doc_id=d.id WHERE d.user_id=%s""", (uid,))
            u['received_likes'] = cur.fetchone()['c']
            cur.execute("""SELECT COUNT(*) AS c FROM friendships WHERE (user_id=%s OR friend_id=%s) AND status='accepted'""", (uid, uid))
            u['friends_count'] = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) AS c FROM follows WHERE follower_id=%s", (uid,))
            u['following_count'] = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) AS c FROM follows WHERE followee_id=%s", (uid,))
            u['followers_count'] = cur.fetchone()['c']
            u['is_following'] = False
            if viewer:
                cur.execute("SELECT id FROM follows WHERE follower_id=%s AND followee_id=%s", (viewer['id'], uid))
                u['is_following'] = bool(cur.fetchone())
    finally:
        conn.close()
    return jsonify(u)

@app.route('/api/users/<int:uid>/notes', methods=['GET'])
def user_notes(uid):
    """主页笔记：?scope=public（默认，公开）/ mine（自己的全部，仅本人）"""
    viewer = get_current_user()
    scope = request.args.get('scope', 'public')
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if scope == 'mine':
                if not viewer or viewer['id'] != uid:
                    return jsonify({'error': 'forbidden'}), 403
                cur.execute(DOC_SELECT + " FROM docs d LEFT JOIN users u ON d.user_id=u.id WHERE d.user_id=%s ORDER BY d.updated_at DESC", (uid,))
            else:
                cur.execute(DOC_SELECT + " FROM docs d LEFT JOIN users u ON d.user_id=u.id WHERE d.user_id=%s AND d.visibility='public' ORDER BY d.updated_at DESC", (uid,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify(rows)

@app.route('/api/users/<int:uid>/favorites', methods=['GET'])
def user_favorites(uid):
    """TA 收藏的公开笔记（用户关闭收藏公开则他人不可见）"""
    viewer = get_current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT favorites_public FROM users WHERE id=%s", (uid,))
            row = cur.fetchone()
            if row and not row['favorites_public'] and not (viewer and viewer['id'] == uid):
                return jsonify([])
            cur.execute(DOC_SELECT + """ FROM docs d
                LEFT JOIN users u ON d.user_id=u.id
                JOIN note_favorites f ON f.doc_id=d.id
                WHERE f.user_id=%s AND d.visibility='public'
                ORDER BY f.created_at DESC""", (uid,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify(rows)

@app.route('/api/users/<int:uid>/likes', methods=['GET'])
def user_likes(uid):
    """TA 点赞的公开笔记（用户关闭点赞公开则他人不可见）"""
    viewer = get_current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT likes_public FROM users WHERE id=%s", (uid,))
            row = cur.fetchone()
            if row and not row['likes_public'] and not (viewer and viewer['id'] == uid):
                return jsonify([])
            cur.execute(DOC_SELECT + """ FROM docs d
                LEFT JOIN users u ON d.user_id=u.id
                JOIN note_likes l ON l.doc_id=d.id
                WHERE l.user_id=%s AND d.visibility='public'
                ORDER BY l.created_at DESC""", (uid,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify(rows)

@app.route('/api/user/profile', methods=['PUT'])
@require_login
def update_profile(user=None):
    data = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 未传的字段保持原值（避免只改隐私时清空资料）
            cur.execute("SELECT nickname, bio, interests, avatar, likes_public, favorites_public FROM users WHERE id=%s", (user['id'],))
            row = cur.fetchone()
            nickname = row['nickname'] if data.get('nickname') is None else ((data.get('nickname') or '').strip()[:32] or None)
            bio = row['bio'] if data.get('bio') is None else ((data.get('bio') or '').strip()[:200] or None)
            interests = row['interests'] if data.get('interests') is None else ((data.get('interests') or '').strip()[:200] or None)
            avatar = row['avatar'] if data.get('avatar') is None else ((data.get('avatar') or '').strip()[:255] or None)
            likes_public = row['likes_public'] if data.get('likes_public') is None else (1 if data.get('likes_public') else 0)
            favorites_public = row['favorites_public'] if data.get('favorites_public') is None else (1 if data.get('favorites_public') else 0)
            cur.execute("UPDATE users SET nickname=%s, bio=%s, interests=%s, avatar=%s, likes_public=%s, favorites_public=%s WHERE id=%s",
                        (nickname, bio, interests, avatar, likes_public, favorites_public, user['id']))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'likes_public': likes_public, 'favorites_public': favorites_public})

@app.route('/api/user/avatar', methods=['POST'])
@require_login
def upload_avatar(user=None):
    """头像上传（multipart file=avatar），存 uploads/avatars/，返回访问路径"""
    file = request.files.get('avatar')
    if not file or not file.filename:
        return jsonify({'error': 'bad_request'}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        return jsonify({'error': '仅支持图片格式'}), 400
    avatar_dir = os.path.join(UPLOAD_FOLDER, 'avatars')
    os.makedirs(avatar_dir, exist_ok=True)
    fname = f"u{user['id']}_{secrets.token_hex(6)}{ext}"
    file.save(os.path.join(avatar_dir, fname))
    path = f"/uploads/avatars/{fname}"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET avatar=%s WHERE id=%s", (path, user['id']))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'avatar': path})

@app.route('/api/user/cover', methods=['POST'])
@require_login
def upload_cover(user=None):
    # 主页背景上传（multipart file=cover），存 uploads/covers/，返回访问路径
    file = request.files.get('cover')
    if not file or not file.filename:
        return jsonify({'error': 'bad_request'}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        return jsonify({'error': '仅支持图片格式'}), 400
    cover_dir = os.path.join(UPLOAD_FOLDER, 'covers')
    os.makedirs(cover_dir, exist_ok=True)
    fname = "u" + str(user['id']) + "_" + secrets.token_hex(6) + ext
    file.save(os.path.join(cover_dir, fname))
    path = "/uploads/covers/" + fname
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE users SET cover=%s WHERE id=%s', (path, user['id']))
            cur.execute('SELECT id FROM user_covers WHERE user_id=%s AND cover=%s', (user['id'], path))
            if not cur.fetchone():
                cur.execute('INSERT INTO user_covers (user_id, cover) VALUES (%s, %s)', (user['id'], path))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'cover': path})

@app.route('/api/user/covers', methods=['GET'])
@require_login
def user_cover_history(user=None):
    # QQ 风格：返回该用户全部历史背景，current 标记当前生效项
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT cover, CAST(created_at AS CHAR) AS created_at FROM user_covers WHERE user_id=%s ORDER BY id DESC', (user['id'],))
            rows = cur.fetchall()
            cur.execute('SELECT cover FROM users WHERE id=%s', (user['id'],))
            current = (cur.fetchone() or {}).get('cover')
    finally:
        conn.close()
    for r in rows:
        r['current'] = (r['cover'] == current)
    return jsonify({'covers': rows})

@app.route('/api/user/cover/apply', methods=['POST'])
@require_login
def apply_cover(user=None):
    # 应用历史背景或系统预设背景
    data = request.get_json(silent=True) or {}
    cover = (data.get('cover') or '').strip()[:255]
    if not cover:
        return jsonify({'error': 'bad_request'}), 400
    allowed = cover.startswith('/uploads/presets/')
    if not allowed:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT id FROM user_covers WHERE user_id=%s AND cover=%s', (user['id'], cover))
                allowed = bool(cur.fetchone())
        finally:
            conn.close()
    if not allowed:
        return jsonify({'error': '该背景不属于你'}), 403
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE users SET cover=%s WHERE id=%s', (cover, user['id']))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'cover': cover})

@app.route('/api/user/cover/reset', methods=['POST'])
@require_login
def reset_cover(user=None):
    # 恢复为初始背景（无 cover，显示系统默认渐变）
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE users SET cover=NULL WHERE id=%s', (user['id'],))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True})

@app.route('/api/user/today', methods=['GET'])
@require_login
def user_today(user=None):
    """今日概览：今日阅读分钟、AI 已用/额度、积分"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT points, ai_used, ai_quota_bonus FROM users WHERE id=%s", (user['id'],))
            u = cur.fetchone()
            cur.execute("""SELECT COALESCE(SUM(seconds), 0) AS secs FROM read_logs
                           WHERE user_id=%s AND created_at >= CURDATE()""", (user['id'],))
            today_read = cur.fetchone()['secs'] or 0
    finally:
        conn.close()
    return jsonify({
        'points': u['points'],
        'ai_used': u['ai_used'],
        'ai_quota': FREE_AI_QUOTA + (u['ai_quota_bonus'] or 0),
        'today_read_min': int(today_read) // 60,
    })

@app.route('/api/user/points', methods=['GET'])
@require_login
def user_points(user=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT points FROM users WHERE id=%s", (user['id'],))
            total = cur.fetchone()['points']
            cur.execute("""SELECT delta, reason, CAST(created_at AS CHAR) AS created_at
                FROM point_logs WHERE user_id=%s ORDER BY created_at DESC LIMIT 50""", (user['id'],))
            logs = cur.fetchall()
    finally:
        conn.close()
    return jsonify({'points': total, 'logs': logs})

# ── 学习热力图：最近 N 天阅读时长（仅本人） ──
@app.route('/api/user/heatmap', methods=['GET'])
@require_login
def user_heatmap(user=None):
    uid = request.args.get('uid', type=int) or user['id']   # 支持查看他人热力图（默认自己）
    days = 90
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT DATE(created_at) AS d, SUM(seconds) AS secs, COUNT(*) AS cnt
                FROM read_logs WHERE user_id=%s AND created_at >= CURDATE() - INTERVAL %s DAY
                GROUP BY DATE(created_at)""", (uid, days))
            rows = cur.fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        out.append({'date': str(r['d']), 'seconds': int(r['secs'] or 0), 'count': int(r['cnt'] or 0)})
    return jsonify({'days': days, 'data': out})

# ═══════════════ 消息通知 ═══════════════
def notify(conn, user_id, actor_id, ntype, doc_id=None):
    """给 user_id 插入一条通知（actor 触发，排除自己通知自己）"""
    if not user_id or user_id == actor_id:
        return
    with conn.cursor() as cur:
        cur.execute("INSERT INTO notifications (user_id, actor_id, type, doc_id) VALUES (%s, %s, %s, %s)",
                    (user_id, actor_id, ntype, doc_id))

@app.route('/api/notifications', methods=['GET'])
@require_login
def notifications_list(user=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT n.id, n.type, n.doc_id, d.public_id, n.is_read, n.extra, CAST(n.created_at AS CHAR) AS created_at,
                u.nickname, u.username, u.public_id AS actor_public_id, d.title AS doc_title
                FROM notifications n
                LEFT JOIN users u ON n.actor_id=u.id
                LEFT JOIN docs d ON n.doc_id=d.id
                WHERE n.user_id=%s ORDER BY n.created_at DESC LIMIT 30""", (user['id'],))
            rows = cur.fetchall()
            cur.execute("SELECT COUNT(*) AS c FROM notifications WHERE user_id=%s AND is_read=0", (user['id'],))
            unread = cur.fetchone()['c']
    finally:
        conn.close()
    return jsonify({'list': rows, 'unread': unread})

@app.route('/api/notifications/read', methods=['POST'])
@require_login
def notifications_read(user=None):
    """标记全部已读（或指定 id）"""
    data = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if data.get('id'):
                cur.execute("UPDATE notifications SET is_read=1 WHERE id=%s AND user_id=%s", (data['id'], user['id']))
            else:
                cur.execute("UPDATE notifications SET is_read=1 WHERE user_id=%s", (user['id'],))
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True})

# ── 好友系统 ──
@app.route('/api/friends/request', methods=['POST'])
@require_login
def friend_request(user=None):
    data = request.get_json(silent=True) or {}
    raw = str(data.get('user_id') or '').strip()
    if not raw:
        return jsonify({'error': '请输入用户 ID'}), 400
    if raw == str(user['id']) or raw == user['username']:
        return jsonify({'error': '不能添加自己'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 只按 ID（@用户名）查；系统编号不对外
            cur.execute("SELECT id FROM users WHERE username=%s", (raw,))
            r = cur.fetchone()
            friend_id = r['id'] if r else None
            if friend_id is None:
                return jsonify({'error': '用户不存在'}), 404
            # 反向是否已存在（对方加过我）
            cur.execute("SELECT id, user_id, friend_id, status FROM friendships WHERE (user_id=%s AND friend_id=%s) OR (user_id=%s AND friend_id=%s)",
                        (user['id'], friend_id, friend_id, user['id']))
            exist = cur.fetchone()
            if exist:
                if exist['status'] == 'accepted':
                    return jsonify({'error': '已是好友'}), 409
                if exist['user_id'] == friend_id:  # 对方已申请我 → 直接成为好友
                    cur.execute("UPDATE friendships SET status='accepted' WHERE id=%s", (exist['id'],))
                    conn.commit()
                    return jsonify({'success': True, 'auto_accepted': True})
                return jsonify({'error': '已发送过申请'}), 409
            cur.execute("INSERT INTO friendships (user_id, friend_id, status) VALUES (%s, %s, 'pending')",
                        (user['id'], friend_id))
        notify(conn, friend_id, user['id'], 'friend_request')
        conn.commit()
        return jsonify({'success': True})
    finally:
        conn.close()

@app.route('/api/friends', methods=['GET'])
@require_login
def friend_list(user=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT f.id, f.status, f.created_at,
                u.id AS other_id, u.username, u.nickname, u.avatar, u.bio, u.points, u.public_id AS other_public_id
                FROM friendships f JOIN users u ON u.id = IF(f.user_id=%s, f.friend_id, f.user_id)
                WHERE (f.user_id=%s OR f.friend_id=%s)
                ORDER BY f.created_at DESC""", (user['id'], user['id'], user['id']))
            rows = cur.fetchall()
            # 区分：发给我的（user_id=对方）
            cur.execute("""SELECT f.id, f.status, u.id AS other_id, u.username, u.nickname, u.avatar, u.public_id AS other_public_id
                FROM friendships f JOIN users u ON u.id=f.user_id
                WHERE f.friend_id=%s AND f.status='pending'""", (user['id'],))
            incoming = cur.fetchall()
    finally:
        conn.close()
    return jsonify({'list': rows, 'incoming': incoming})

@app.route('/api/friends/<int:rid>', methods=['POST'])
@require_login
def friend_respond(rid, user=None):
    """同意/拒绝好友申请：{action: accept|reject}"""
    data = request.get_json(silent=True) or {}
    action = data.get('action')
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, user_id, friend_id FROM friendships WHERE id=%s AND friend_id=%s", (rid, user['id']))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'not_found'}), 404
            if action == 'accept':
                cur.execute("UPDATE friendships SET status='accepted' WHERE id=%s", (rid,))
            elif action == 'reject':
                cur.execute("DELETE FROM friendships WHERE id=%s", (rid,))
            else:
                return jsonify({'error': 'bad_action'}), 400
        conn.commit()
        return jsonify({'success': True})
    finally:
        conn.close()

@app.route('/api/friends/<int:rid>', methods=['DELETE'])
@require_login
def friend_remove(rid, user=None):
    """删除好友（双向解除）"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, user_id, friend_id FROM friendships WHERE id=%s AND (user_id=%s OR friend_id=%s)", (rid, user['id'], user['id']))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'not_found'}), 404
            cur.execute("DELETE FROM friendships WHERE id=%s", (rid,))
        conn.commit()
        return jsonify({'success': True})
    finally:
        conn.close()

# ═══════════════ 单向关注（follow） ═══════════════
@app.route('/api/follows/toggle', methods=['POST'])
@require_login
def follow_toggle(user=None):
    """关注/取关（幂等切换）"""
    data = request.get_json(silent=True) or {}
    try:
        target = int(data.get('user_id') or 0)
    except (TypeError, ValueError):
        target = 0
    if not target or target == user['id']:
        return jsonify({'error': '参数错误'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE id=%s", (target,))
            if not cur.fetchone():
                return jsonify({'error': '用户不存在'}), 404
            cur.execute("SELECT id FROM follows WHERE follower_id=%s AND followee_id=%s", (user['id'], target))
            row = cur.fetchone()
            if row:
                cur.execute("DELETE FROM follows WHERE id=%s", (row['id'],))
                following = False
            else:
                cur.execute("INSERT INTO follows (follower_id, followee_id) VALUES (%s, %s)", (user['id'], target))
                following = True
            cur.execute("SELECT COUNT(*) AS c FROM follows WHERE followee_id=%s", (target,))
            followers_count = cur.fetchone()['c']
        conn.commit()
    finally:
        conn.close()
    return jsonify({'success': True, 'following': following, 'followers_count': followers_count})

@app.route('/api/users/<int:uid>/followers', methods=['GET'])
def user_followers(uid):
    """关注 TA 的人（粉丝）"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            viewer = get_current_user()
            cur.execute("""SELECT u.id, u.username, u.nickname, u.avatar, u.points, u.bio, u.public_id
                FROM follows f JOIN users u ON u.id=f.follower_id
                WHERE f.followee_id=%s ORDER BY f.created_at DESC LIMIT 200""", (uid,))
            rows = cur.fetchall()
            for r in rows:
                r['is_following'] = False
                if viewer:
                    cur.execute("SELECT id FROM follows WHERE follower_id=%s AND followee_id=%s", (viewer['id'], r['id']))
                    r['is_following'] = bool(cur.fetchone())
                r['is_me'] = bool(viewer and viewer['id'] == r['id'])
    finally:
        conn.close()
    return jsonify(rows)

@app.route('/api/users/<int:uid>/following', methods=['GET'])
def user_following(uid):
    """TA 关注的人"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            viewer = get_current_user()
            cur.execute("""SELECT u.id, u.username, u.nickname, u.avatar, u.points, u.bio, u.public_id
                FROM follows f JOIN users u ON u.id=f.followee_id
                WHERE f.follower_id=%s ORDER BY f.created_at DESC LIMIT 200""", (uid,))
            rows = cur.fetchall()
            for r in rows:
                r['is_following'] = False
                if viewer:
                    cur.execute("SELECT id FROM follows WHERE follower_id=%s AND followee_id=%s", (viewer['id'], r['id']))
                    r['is_following'] = bool(cur.fetchone())
                r['is_me'] = bool(viewer and viewer['id'] == r['id'])
    finally:
        conn.close()
    return jsonify(rows)

@app.route('/api/users/search', methods=['GET'])
@require_login
def user_search(user=None):
    """按 ID（@用户名）/昵称搜索用户"""
    q = (request.args.get('q') or '').strip()
    if not q or len(q) > 32:
        return jsonify({'error': '请输入搜索关键词'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id, username, nickname, avatar, points, public_id FROM users
                WHERE username LIKE %s OR nickname LIKE %s ORDER BY id ASC LIMIT 20""",
                ('%' + q + '%', '%' + q + '%'))
            rows = cur.fetchall()
            for r in rows:
                r['is_me'] = (r['id'] == user['id'])
                r['is_following'] = False
                if r['id'] != user['id']:
                    cur.execute("SELECT id FROM follows WHERE follower_id=%s AND followee_id=%s", (user['id'], r['id']))
                    r['is_following'] = bool(cur.fetchone())
    finally:
        conn.close()
    return jsonify(rows)
@app.route('/api/messages', methods=['POST'])
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


@app.route('/api/groups', methods=['POST'])
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

@app.route('/api/groups', methods=['GET'])
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

@app.route('/api/groups/<int:gid>', methods=['GET'])
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

@app.route('/api/groups/<int:gid>/messages', methods=['GET'])
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

@app.route('/api/groups/<int:gid>/messages', methods=['POST'])
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

@app.route('/api/messages/conversations', methods=['GET'])
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

@app.route('/api/messages', methods=['GET'])
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

# ═══════════════ AI 助手（DeepSeek 检索问答） ═══════════════
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
# Responses API：全站 AI 统一使用（deepseek-v4-flash + 服务端联网搜索 web_search + function 工具）
DEEPSEEK_RESPONSES_URL = 'https://api.deepseek.com/responses'
DEEPSEEK_RESPONSES_MODEL = 'deepseek-v4-flash'
FREE_AI_QUOTA = 20  # 每个用户免费次数

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
        'parameters': {'type': 'object', 'properties': {'note_id': {'type': 'integer', 'description': '笔记 ID'}}, 'required': ['note_id']},
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
        'description': '跳转到站内页面。可用路径：/（首页）、/notes（笔记广场）、/docs（阅览室）、/notes/{public_id}（打开某篇笔记，public_id 由 search_note 返回，不要自己编）、/edit/{id}（编辑某篇笔记，仍用数字 id）、/edit（新建笔记）、/admin（书房）、/friends（好友）、/mall（积分商城）、/messages（消息）、/changelog（更新日志）、/guide（使用引导）、/user/{public_id}（个人主页，不编 id）。用户要求「帮我跳转到某页 / 打开某笔记 / 去 XX」时调用；若用户只给了笔记标题而你不知道 public_id，先调用 search_note 按标题搜索得到 public_id 后再跳转。',
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
            nid = int(args.get('note_id') or 0)
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, title, content FROM docs WHERE id=%s AND (visibility='public' OR user_id=%s)", (nid, user['id']))
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
            lines = [f"{r['public_id']}.《{r['title']}》（{r['type']}）" for r in rows]
            return '按标题搜索到的笔记（用 public_id 拼 /notes/{public_id} 跳转）：\n' + '\n'.join(lines), False
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

@app.route('/api/ai/chat', methods=['POST'])
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
        return jsonify({'error': 'AI 额度已用完，可去积分商城兑换', 'used': used, 'quota': quota}), 402
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
                for _round in range(3):
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
    for _round in range(3):
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

@app.route('/api/ai/logs', methods=['GET'])
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

@app.route('/api/ai/edit-suggest', methods=['POST'])
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
        return jsonify({'error': 'AI 额度已用完，可去积分商城兑换', 'used': used, 'quota': quota}), 402
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

# ═══════════════ AI Agent 雏形：动态更新日志 ═══════════════
# ═══════════════ 阅览室（工作台：本次要学的内容） ═══════════════
@app.route('/api/reading-list', methods=['GET'])
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

@app.route('/api/reading-list', methods=['POST'])
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

@app.route('/api/reading-list/<int:doc_id>', methods=['DELETE'])
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
@app.route('/api/docs/<int:doc_id>/purchase', methods=['POST'])
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

@app.route('/api/feed')
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


@app.route('/api/changelog', methods=['GET'])
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

@app.route('/api/mall/exchange', methods=['POST'])
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
# ═══════════════ 涂鸦批注（纸质荧光笔式手绘） ═══════════════
@app.route('/api/notes/<int:doc_id>/annotations', methods=['GET'])
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

@app.route('/api/notes/<int:doc_id>/annotations', methods=['POST'])
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

@app.route('/api/annotations/upload-img', methods=['POST'])
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

@app.route('/api/annotations/<int:aid>', methods=['PUT'])
@require_login
def note_annotations_update(aid, user=None):
    """更新批注：文字(note_text) 或 手绘(strokes+canvas_w/h)。批注框内防抖局部保存用，不碰正文"""
    data = request.get_json(silent=True) or {}
    sets, vals = [], []
    if 'note_text' in data:
        sets.append('note_text=%s'); vals.append(str(data.get('note_text') or '')[:5000])
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

@app.route('/api/annotations/<int:aid>', methods=['DELETE'])
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
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """头像/上传文件静态访问（限制在 UPLOAD_FOLDER 内）"""
    return send_from_directory(UPLOAD_FOLDER, filename)
# ═══════════════ AI Agent：每日自动摘要（后台线程） ═══════════════
def agent_daily_summary():
    """每天 00:05 自动聚合昨日社区动态写入 daily_digests（更新日志页展示）"""
    while True:
        try:
            now = datetime.now()
            next_run = (now + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
            time.sleep(max(1, (next_run - now).total_seconds()))
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("""SELECT COUNT(*) AS c FROM docs
                        WHERE updated_at >= CURDATE() - INTERVAL 1 DAY AND visibility='public'""")
                    docs = cur.fetchone()['c']
                    cur.execute("""SELECT COUNT(*) AS c FROM note_comments
                        WHERE created_at >= CURDATE() - INTERVAL 1 DAY""")
                    cmts = cur.fetchone()['c']
                    cur.execute("""SELECT COUNT(*) AS c FROM users
                        WHERE created_at >= CURDATE() - INTERVAL 1 DAY""")
                    users = cur.fetchone()['c']
                    cur.execute("""SELECT COUNT(*) AS c FROM note_likes
                        WHERE created_at >= CURDATE() - INTERVAL 1 DAY""")
                    likes = cur.fetchone()['c']
                    summary = (f"昨日社区动态：新增/更新公开笔记 {docs} 篇、新评论 {cmts} 条、"
                               f"新成员 {users} 人、点赞 {likes} 次。")
                    cur.execute("""INSERT INTO daily_digests (digest_date, summary)
                        VALUES (CURDATE(), %s) ON DUPLICATE KEY UPDATE summary=VALUES(summary)""", (summary,))
                    # 群发每日摘要通知（每个用户一条，仅当天首次）
                    cur.execute("SELECT COUNT(*) AS c FROM notifications WHERE type='digest' AND created_at >= CURDATE()")
                    if cur.fetchone()['c'] == 0:
                        cur.execute("SELECT id FROM users")
                        uids = [r['id'] for r in cur.fetchall()]
                        for uid in uids:
                            cur.execute("INSERT INTO notifications (user_id, actor_id, type, doc_id, extra) VALUES (%s, 0, 'digest', NULL, %s)",
                                        (uid, summary))
                        print(f'[Agent] 每日摘要已群发 {len(uids)} 个用户')
                conn.commit()
                print(f'[Agent] 每日摘要已生成: {summary}')
            finally:
                conn.close()
        except Exception as e:
            print('[Agent] 异常:', e)
            time.sleep(3600)
if __name__ == '__main__':
    init_db()
    print("DB_USER =", DB_USER, "DB_HOST =", DB_HOST, "DB_NAME =", DB_NAME)
    # 启动 AI Agent 后台线程（每日摘要）
    threading.Thread(target=agent_daily_summary, daemon=True).start()
    port = int(os.getenv('PORT', 5000))
    # debug 默认关闭（单进程、不自动重启、不清 token）：需要热重载时设 FLASK_DEBUG=1
    DEBUG = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=port, debug=DEBUG)
