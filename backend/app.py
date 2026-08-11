# -*- coding: utf-8 -*-
"""知屿后端入口：创建 Flask 应用、注册蓝图、启动前初始化与后台 Agent 线程。

原单文件 app.py 已按功能拆分：
  config.py             全局配置常量
  db.py                 数据库连接与初始化建表
  auth.py               认证/会话/邮箱验证码
  utils.py              纯工具函数（id/slug/积分/可见性/通知）
  shared.py             路由间共享业务函数（fetch_doc_visible）
  routes/               各域蓝图（auth/docs/notes/users/social/messages/ai/misc/annotations）
"""
from flask import Flask, request, send_from_directory
from flask_cors import CORS
import os
import threading
import time
from datetime import datetime, timedelta

from config import DB_USER, DB_HOST, DB_NAME, UPLOAD_FOLDER
from db import init_db, get_conn
from routes.auth_routes import bp as auth_bp
from routes.docs_routes import bp as docs_bp
from routes.notes_routes import bp as notes_bp
from routes.users_routes import bp as users_bp
from routes.social_routes import bp as social_bp
from routes.messages_routes import bp as messages_bp
from routes.ai_routes import bp as ai_bp
from routes.misc_routes import bp as misc_bp
from routes.annotation_routes import bp as annotation_bp

app = Flask(__name__)
# CORS 白名单（仅允许前端站点跨域）
CORS(app, resources={r"/api/*": {"origins": [
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:4173", "http://192.168.1.230:5173",
]}})
CORS(app)

for _bp in (auth_bp, docs_bp, notes_bp, users_bp, social_bp, messages_bp, ai_bp, misc_bp, annotation_bp):
    app.register_blueprint(_bp)

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

if __name__ == '__main__':
    init_db()
    print("DB_USER =", DB_USER, "DB_HOST =", DB_HOST, "DB_NAME =", DB_NAME)
    # 启动 AI Agent 后台线程（每日摘要）
    threading.Thread(target=agent_daily_summary, daemon=True).start()
    port = int(os.getenv('PORT', 5000))
    # debug 默认关闭（单进程、不自动重启、不清 token）：需要热重载时设 FLASK_DEBUG=1
    DEBUG = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=port, debug=DEBUG)

