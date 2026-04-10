# 书架管理系统

一个基于 Flask 后端和 React 前端的全栈图书管理应用，支持 ISBN 图书查询、阅读偏好分析、LLM 调用统计等功能。

## 功能特性

- 📚 ISBN 图书查询（带 SQLite 缓存）
- 🧠 阅读偏好分析（异步任务队列）
- 📊 模型用量统计（按提供商、模型、全局统计）
- 📖 管理后台（图书列表、搜索、分页）
- ☁️ 封面图片存储（支持火山引擎 TOS 对象存储）

## 项目结构

```
bookcase-management/
├── backend/           # Flask 后端
│   ├── app.py         # 主应用
│   ├── llm_adapter.py # LLM 适配器
│   ├── reading_agent.py
│   ├── tos_client.py  # TOS 对象存储客户端
│   └── Dockerfile     # 后端 Docker 配置
├── frontend/          # React 前端
│   ├── src/           # 源代码
│   ├── nginx.conf     # Nginx 配置
│   └── Dockerfile     # 前端 Docker 配置
└── docker-compose.yml # 整体编排配置
```

## 本地开发

### 后端

```bash
cd backend

# 创建虚拟环境（可选）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 复制环境配置
cp .env.example .env

# 编辑 .env 文件，配置 LLM
# LLM_API_KEY=你的密钥
# LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
# LLM_MODEL=qwen3.5-flash

# 启动服务
python app.py
```

后端地址：http://127.0.0.1:8001

### 前端

```bash
cd frontend

# 安装依赖
npm install

# 构建
npm run build
```

前端访问：http://127.0.0.1:8001/admin/

## Docker 部署

### 方式一：前后端一键部署

```bash
# 1. 克隆仓库
git clone https://github.com/ApheaTech/bookcase-management.git
cd bookcase-management

# 2. 创建数据目录
mkdir -p backend/data

# 3. 创建 .env 文件
cp backend/.env.example backend/.env
# 编辑 backend/.env，配置 LLM_API_KEY 等敏感信息

# 4. 构建并启动
docker-compose up -d --build

# 5. 查看日志
docker-compose logs -f
```

访问：http://localhost/admin/

### 方式二：手动构建镜像

**后端：**

```bash
cd backend
docker build -t bookcase-backend:latest .
docker run -d --name bookcase-backend -p 8001:8001 -v ./data:/app/data --env-file .env bookcase-backend:latest
```

**前端：**

```bash
cd frontend
# 构建时传入后端地址
docker build --build-arg VITE_API_BASE_URL=http://<后端IP>:8001 -t bookcase-frontend:latest .
docker run -d -p 80:80 --name bookcase-frontend bookcase-frontend:latest
```

## 服务器部署（不使用 Docker）

### 后端

```bash
# 1. 安装 Python 3.11+
# 2. 克隆项目
git clone https://github.com/ApheaTech/bookcase-management.git
cd bookcase-management/backend

# 3. 安装依赖
pip install -r requirements.txt

# 4. 创建数据目录
mkdir -p data

# 5. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY 等

# 6. 使用 systemd 或 supervisor 运行
python app.py
```

### 前端

```bash
# 1. 安装 Node.js 20+
# 2. 进入前端目录
cd bookcase-management/frontend

# 3. 安装依赖并构建
npm install
VITE_API_BASE_URL=http://<后端服务器IP>:8001 npm run build

# 4. 复制到 Nginx 目录
# 将 dist 目录内容复制到 /usr/share/nginx/html/admin/
```

### Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    root /usr/share/nginx/html;
    index index.html;

    # 前端
    location /admin/ {
        try_files $uri $uri/ /admin/index.html;
    }

    # 后端 API
    location /book/ {
        proxy_pass http://127.0.0.1:8001/book/;
        proxy_set_header Host $host;
    }

    location /agent/ {
        proxy_pass http://127.0.0.1:8001/agent/;
        proxy_set_header Host $host;
    }

    location /admin/api/ {
        proxy_pass http://127.0.0.1:8001/admin/api/;
        proxy_set_header Host $host;
    }
}
```

## 环境变量说明

### 后端 (.env)

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DATABASE_URL` | 数据库连接地址 | `sqlite:///./bookcase.db` |
| `LLM_PROVIDER` | LLM 提供商 | `dashscope_compatible` |
| `LLM_BASE_URL` | LLM API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LLM_API_KEY` | LLM API 密钥 | - |
| `LLM_MODEL` | LLM 模型名称 | `qwen3.5-flash` |
| `LLM_TIMEOUT` | 请求超时时间（秒） | `120` |
| `ANALYSIS_WORKER_CONCURRENCY` | 分析任务并发数 | `1` |
| `CORS_ALLOW_ORIGINS` | 允许的跨域来源 | `http://127.0.0.1:3000,...` |

### 前端

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `VITE_API_BASE_URL` | 后端 API 地址 | `http://127.0.0.1:8001` |

## API 示例

### 创建阅读偏好分析任务

```bash
curl -X POST http://127.0.0.1:8001/agent/reading-preferences/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "book_titles": ["八次危机", "史蒂夫·乔布斯", "全球通史", "机器学习"]
  }'
```

### 查询任务状态

```bash
curl http://127.0.0.1:8001/agent/reading-preferences/tasks/<task_id>
```

### 获取模型用量统计

```bash
curl http://127.0.0.1:8001/admin/api/usage
```

### 获取图书列表

```bash
curl http://127.0.0.1:8001/admin/api/books?limit=20&offset=0
```

## 注意事项

1. **敏感信息**：`.env` 文件包含 API 密钥，已加入 `.gitignore`，请勿提交到仓库
2. **数据库**：`*.db` 文件已加入 `.gitignore`，数据存储在本地
3. **LLM 配置**：支持 DashScope、通义千问等 OpenAI 兼容接口，也支持本地部署的模型