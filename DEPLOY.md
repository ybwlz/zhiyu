# 部署文档

本文档介绍如何部署“考研笔记平台”的前端和后端服务。

## 目录结构

- `backend/`: 后端 Flask 服务
- `doctmanage/`: 前端 Vue 3 + Vite 项目
- `docs/`: 其他项目文档 (API, Markdown 规范等)

## 环境要求

- **操作系统**: Windows / Linux / macOS
- **Python**: 3.8+
- **Node.js**: 16+
- **MySQL**: 5.7+

## 1. 数据库配置

1.  确保 MySQL 服务已启动。
2.  创建一个数据库（可选，后端代码会自动尝试创建）：
    ```sql
    CREATE DATABASE doc_manager CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    ```
3.  后端启动时会自动检查并创建 `docs` 表结构。

## 2. 后端部署 (Flask)

后端代码位于 `backend/` 目录。

### 步骤

1.  **进入目录**:
    ```bash
    cd backend
    ```

2.  **创建虚拟环境:**
    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # Linux/Mac
    source .venv/bin/activate
    ```

3.  **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **配置环境变量**:
    在 `backend/` 目录下创建一个 `.env` 文件，填入以下内容（根据实际情况修改）：
    ```env
    DB_HOST=localhost
    DB_PORT=3306
    DB_USER=root
    DB_PASSWORD=your_password
    DB_NAME=doc_manager
    PORT=5000 # 可选，默认为 5000
    ```

5.  **启动服务**:
    ```bash
    python app.py
    ```
    服务默认运行在 `http://0.0.0.0:5000` (或您配置的端口)。

### 修改后端端口

如果您需要修改后端运行端口（例如改为 8000）：
1.  **方法一 (推荐)**: 在 `.env` 文件中添加或修改 `PORT` 变量：
    ```env
    PORT=8000
    ```
2.  **方法二**: 设置系统环境变量 `PORT`。

## 3. 前端部署 (Vue 3 + Vite)

前端代码位于 `doctmanage/` 目录。

### 开发环境运行

1.  **进入目录**:
    ```bash
    cd doctmanage
    ```

2.  **安装依赖**:
    ```bash
    npm install
    ```

3.  **启动开发服务器**:
    ```bash
    npm run dev
    ```
    访问终端显示的地址（通常为 `http://localhost:5173`）。

### 修改前端开发端口

如果需要修改开发服务器端口（例如改为 3000）：
```bash
npm run dev -- --port 3000
```
或者修改 `vite.config.js`：
```javascript
export default defineConfig({
  server: {
    port: 3000
  }
})
```

### 生产环境构建

1.  **进入目录**:
    ```bash
    cd doctmanage
    ```

2.  **安装依赖 (至关重要)**:
    ```bash
    npm install
    ```
    **说明**: 这一步会读取 `package.json`，下载所有依赖。

3.  **构建**:
    ```bash
    npm run build
    ```
    构建完成后，会生成 `dist` 目录。

4.  **部署**:
    将 `doctmanage/dist/` 目录下的所有文件复制到 Web 服务器（如 Nginx, Apache, IIS）的静态资源目录下。

    **Nginx 配置示例**:
    ```nginx
    server {
        listen 80;
        server_name your_domain.com;

        location / {
            root /path/to/doctmanage/dist;
            index index.html;
            try_files $uri $uri/ /index.html; # 支持 Vue Router History 模式
        }

        # 代理 API 请求到后端
        location /api {
            proxy_pass http://localhost:5000; # 如果修改了后端端口，请同步修改此处
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # 头像/上传文件静态资源（否则 /uploads/... 直接 404）
        location /uploads {
            proxy_pass http://localhost:5000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
    ```

## 注意事项

- **防火墙**: 确保防火墙允许相应的端口访问（后端 5000，前端 80/443）。
- **API 地址**: 如果前后端分离部署在不同域名/端口，可能需要在前端代码中配置 `VITE_API_BASE_URL` 或修改 `proxy` 配置。当前项目默认使用相对路径 `/api` 配合 Nginx 反向代理。
