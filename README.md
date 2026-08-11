# 考研笔记平台 (DocManager)

这是一个基于 Markdown 的文档管理与展示平台，支持文档的上传、分类管理、在线预览以及基于 Slug 的路由访问。

## 项目结构

本项目采用前后端分离架构。

```
文档后台/
├── backend/                # 后端服务 (Python Flask)
│   ├── app.py              # 主应用程序入口
│   ├── requirements.txt    # Python 依赖列表
│   ├── .env                # 环境变量配置文件 (需自行创建)
│   └── uploads/            # 临时文件上传目录
│
├── doctmanage/             # 前端项目 (Vue 3 + Vite)
│   ├── src/
│   │   ├── views/          # 页面组件 (Home, Docs, Admin, Login)
│   │   ├── components/     # 功能组件 (Upload, Delete)
│   │   ├── router/         # 路由配置
│   │   ├── stores/         # Pinia 状态管理
│   │   └── utils/          # 工具函数 (API 封装等)
│   ├── public/             # 静态资源
│   └── package.json        # Node.js 依赖配置
│
├── API.md                  # API 接口文档
├── DEPLOY.md               # 部署文档
└── README.md               # 项目说明 (本文件)
```

## 技术栈

### 后端
- **框架**: Flask 3.0
- **数据库**: MySQL (PyMySQL)
- **其他**: Flask-Cors (跨域支持), python-dotenv (环境配置)

### 前端
- **框架**: Vue 3 (Composition API)
- **构建工具**: Vite
- **UI 组件库**: Element Plus
- **路由**: Vue Router 4
- **状态管理**: Pinia
- **Markdown 渲染**: markdown-it, highlight.js
- **HTTP 客户端**: Axios

## 快速开始

请参考 [DEPLOY.md](./DEPLOY.md) 进行环境配置与部署。

## 功能特性

- **文档管理**: 支持 Markdown 文件的上传、更新和删除。
- **分类展示**: 首页自动根据文档类型聚合展示。
- **在线预览**: 支持 Markdown 实时渲染、代码高亮、锚点跳转。
- **响应式设计**: 适配桌面端与移动端访问。
- **后台管理**: 独立的后台管理界面，需登录访问。

## 使用指南

### 1. 文档更新（日常使用）
**不需要重新部署代码**。
本系统是动态文档管理系统，文档内容存储在 MySQL 数据库中。
- 访问 `/login` 登录后台。
- 在“上传”标签页：上传新的 Markdown 文件，系统会自动解析并保存到数据库。
- 在“删除”标签页：管理已有的文档。
- 前端页面会实时读取数据库内容进行展示。

### 2. 系统升级（代码更新）
如果是修改了 Vue 前端样式或 Flask 后端逻辑，则需要：
- **前端**: 修改代码 -> `npm run build` -> 替换服务器 `dist` 目录。
- **后端**: 修改代码 -> 替换服务器 `app.py` -> 重启 Flask 服务。

## 其他说明
- 左侧导航栏文字背景颜色在 `doctmanage/src/views/Docs.vue` 的 1240 行。
