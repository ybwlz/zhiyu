# 文档管理系统 (DocManager)

这是一个基于 Vue 3 的文档管理后台系统，用于上传、管理和删除 Markdown 文档。

## 📋 项目说明

### 这是什么项目？
- **前端项目**：Vue 3 + Element Plus 的网页界面
- **功能**：上传文档、查看文档列表、删除文档
- **文档格式**：仅支持 Markdown (.md) 文件

### 项目架构
```
前端（这个项目）
  ↓ 发送请求
后端 API 服务（另一个项目，运行在服务器上）
```

## 🚀 快速开始

### 最简单的方式（3步）

1. **安装依赖**
   ```bash
   npm install
   ```

2. **启动项目**
   ```bash
   npm run dev
   ```

3. **打开浏览器**
   访问：`http://localhost:5173`
   
   **默认登录**：
   - 账号：`djct123`
   - 密码：`djct123`

### 详细说明
- 📖 [快速开始指南](./快速开始.md) - 最简单的运行方式
- 📚 [完整运行指南](./运行指南.md) - 详细说明和问题解决

## 🔧 如果后端 API 不可用

如果远程后端（`dz.szdjct.com:5208`）不可用，可以使用本地 Python 后端：

### 使用本地后端

1. **安装 Python 依赖**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **启动后端**
   ```bash
   python app.py
   ```

3. **配置前端使用本地后端**
   - 在 `DocManager` 目录下创建 `.env` 文件
   - 添加：`VITE_API_BASE_URL=http://localhost:5000`

4. **重启前端**
   ```bash
   npm run dev
   ```

详细说明见：[backend/README.md](./backend/README.md)

## 📁 项目结构

```
DocManager/
├── src/                    # 源代码
│   ├── components/         # 组件（上传、删除）
│   ├── layout/            # 布局（登录、主页）
│   ├── router/            # 路由配置
│   ├── stores/            # 状态管理
│   └── utils/             # 工具函数（API 配置）
├── public/                # 静态资源
└── package.json           # 项目配置
```

## 📝 技术栈

- **Vue 3** - 前端框架
- **Element Plus** - UI 组件库
- **Pinia** - 状态管理
- **Vue Router** - 路由
- **Axios** - HTTP 请求
- **Vite** - 构建工具

## ⚠️ 常见问题

### 上传失败？
1. 检查后端 API 是否可访问
2. 打开浏览器控制台（F12）查看错误
3. 如果远程后端不可用，使用本地 Python 后端

### 登录后看不到数据？
1. 检查后端 API 是否返回数据
2. 查看浏览器控制台是否有错误
3. 确认 API 路径是否正确

### 如何修改 API 地址？
创建 `.env` 文件，添加：
```
VITE_API_BASE_URL=你的API地址
```

