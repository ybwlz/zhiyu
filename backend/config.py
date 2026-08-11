# -*- coding: utf-8 -*-
"""全局配置：从 .env 读取的环境变量与常量。"""
import os
from dotenv import load_dotenv
load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME', 'doc_manager')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

# 开发模式：未配 SMTP 时向响应返回 dev_code（生产环境请置 DEV_MODE=0）
DEV_MODE = os.getenv('DEV_MODE', '1') == '1'

# SMTP 配置（.env 可配；未配置时验证码打印到控制台，响应带 dev_code 便于本地调试）
SMTP_HOST = os.getenv('SMTP_HOST', '')
SMTP_PORT = int(os.getenv('SMTP_PORT', '465'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASS = os.getenv('SMTP_PASS', '')
SMTP_FROM = os.getenv('SMTP_FROM', SMTP_USER)

# DeepSeek Responses API：全站 AI 统一使用（deepseek-v4-flash + 服务端联网搜索 web_search + function 工具）
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_RESPONSES_URL = 'https://api.deepseek.com/responses'
DEEPSEEK_RESPONSES_MODEL = 'deepseek-v4-flash'
FREE_AI_QUOTA = 20  # 每个用户免费次数
