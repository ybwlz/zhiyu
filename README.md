# 知屿 · 个人知识库

> 把散落的笔记、截图与灵感，收进一座自己的知识库。支持网页端与 Windows 桌面版。

## ✨ 功能特性

- 📚 **笔记管理**：文章/笔记的创建、编辑、版本历史、草稿自动保存
- 🖼 **富内容**：Markdown、代码高亮（行号/高亮行）、公式（MathJax）、图片、表格、自定义容器
- 🤖 **AI 助手**：DeepSeek 驱动的问答、总结、改写，内置免费额度
- 🏷 **知识组织**：科目/分类、标签、收藏、阅读列表、目录大纲
- 👥 **社交**：关注、好友、私信、群聊、评论、点赞、评分
- 🪙 **知屿币**：积分体系 + 商城兑换 AI 次数
- 🖌 **批注涂鸦**：笔记内的划线批注与手绘涂鸦
- 🖥 **桌面版**：Electron Windows 客户端，本地渲染、云端同步、服务器可切换

## 🛠 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vite + Vue 3 + Element Plus + Pinia + Vue Router |
| 后端 | Python Flask + Gunicorn + MySQL (PyMySQL) |
| 桌面 | Electron + electron-packager |
| 其他 | Markdown-it（渲染）、MathJax（公式）、highlight.js（高亮）、DeepSeek API（AI） |

## 📁 目录结构

```
├── backend/            # Flask 后端（config/db/auth/utils + routes 蓝图）
├── doctmanage/         # 前端（Vite + Vue）与 Electron 桌面版
│   ├── src/            # 前端源码
│   ├── electron/       # Electron 主进程（main.cjs）
│   └── public/         # 静态资源（含 MathJax 运行时）
├── docs/               # 文档
└── .env.example        # 环境变量示例
```

## 🚀 本地开发

```bash
# 后端（Python 3.11+）
cd backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt   # Windows
source venv/bin/pip install -r requirements.txt # Linux
cp .env.example .env    # 按需配置数据库/SMTP/DeepSeek
venv\Scripts\python app.py                      # 启动，默认 5000

# 前端
cd doctmanage
npm install
npm run dev             # http://localhost:5173/zhiyu/
```

## ☁️ 部署

- 服务器：Nginx + Gunicorn + MySQL（详见 `DEPLOY.md`）
- 前端构建：`npm run build`，产物在 `dist/`（base 为 `/zhiyu/`）

## 🖥 桌面版

- 打包：`npm run pack:win`（electron-packager）
- 后端地址可配置：exe 同目录 `config.json` 写 `{"backend": "http://服务器地址"}`，
  默认已连接云端；环境变量 `ZHIYU_BACKEND` 优先级最高

## 📄 License

[MIT](./LICENSE)
