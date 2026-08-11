# -*- coding: utf-8 -*-
"""数据库连接与初始化建表。"""
import secrets
import pymysql
from pymysql.cursors import DictCursor
from werkzeug.security import generate_password_hash

from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from utils import gen_public_id

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
