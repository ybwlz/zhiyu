# 项目 API 文档

本文档描述了后端服务提供的 API 接口。

**Base URL**: `http://<server_ip>:5000/api`

## 1. 获取文档列表

获取所有文档的列表，按类型排序，然后按更新时间倒序排列。

- **URL**: `/docs`
- **Method**: `GET`
- **Response**:
    ```json
    [
        {
            "id": 1,
            "type": "数学公式",
            "title": "公式介绍",
            "slug": "project-intro",
            "updated_at": "2024-01-01 12:00:00"
        },
        ...
    ]
    ```

## 2. 根据 Slug 获取文档

通过文档的唯一标识符（slug）获取文档详情。

- **URL**: `/docs/by-slug/<slug>`
- **Method**: `GET`
- **Params**:
    - `slug` (path): 文档的唯一标识字符串
- **Response**:
    ```json
    {
        "id": 1,
        "type": "数学公式",
        "title": "项目介绍",
        "slug": "project-intro",
        "content": "# Markdown Content..."
    }
    ```
- **Errors**:
    - 404: `{ "error": "not_found" }`

## 3. 根据 ID 获取文档

通过文档的 ID 获取文档详情。

- **URL**: `/docs/<int:doc_id>`
- **Method**: `GET`
- **Params**:
    - `doc_id` (path): 文档的数字 ID
- **Response**: (同根据 Slug 获取文档)

## 4. 上传/创建文档

上传一个新的 Markdown 文件并创建文档记录。

- **URL**: `/docs`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **Body**:
    - `file`: (File) Markdown 文件 (.md)
    - `type`: (String) 文档分类（如 "数学公式"）
    - `title`: (String) 文档标题
- **Response**:
    ```json
    {
        "id": 2,
        "slug": "new-doc-slug"
    }
    ```

## 5. 更新文档

更新现有文档的元数据或内容。

- **URL**: `/docs/<int:doc_id>`
- **Method**: `PUT`
- **Content-Type**: `application/json`
- **Body**:
    ```json
    {
        "type": "更新后的分类",
        "title": "更新后的标题",
        "content": "更新后的 Markdown 内容..."
    }
    ```
- **Response**:
    ```json
    {
        "success": true,
        "slug": "updated-slug" // slug 可能会因为标题变化而自动更新
    }
    ```

## 6. 删除文档

删除指定 ID 的文档。

- **URL**: `/docs/<int:doc_id>`
- **Method**: `DELETE`
- **Response**:
    ```json
    {
        "success": true
    }
    ```
