# 智能数据库查询工具

一个面向 PostgreSQL 和 MySQL 的 Web 数据库查询工具，支持连接管理、元数据浏览、只读 SQL 查询、查询历史、自然语言转 SQL，以及 CSV/JSON 导出。

## 主要功能

- 创建、更新、列出和删除数据库连接；
- 自动识别 PostgreSQL、MySQL 连接 URL；
- 浏览表、视图、列、主键、唯一约束和行数；
- 使用 Monaco Editor 编写并执行 SQL；
- 只允许 `SELECT`，缺少限制时自动添加 `LIMIT 1000`；
- 每个数据库保留最近 50 条查询历史；
- 使用 OpenAI `gpt-4o-mini` 将中英文自然语言转换为 SQL；
- 在浏览器中将结果导出为 CSV 或 JSON。

## 技术栈

- 后端：Python 3.12、FastAPI、SQLModel、SQLite、asyncpg、aiomysql、sqlglot；
- 前端：React、TypeScript、Vite、MUI (Material UI)、Monaco Editor；
- 包管理：后端使用 uv，前端使用 npm。

## 项目结构

```text
db_explorer/
├── backend/          # FastAPI 后端
│   ├── app/
│   │   ├── adapters/ # 数据库适配器（PostgreSQL、MySQL）
│   │   ├── api/      # API 路由
│   │   ├── models/   # 数据模型
│   │   ├── services/ # 业务逻辑
│   │   └── utils/    # 工具函数
│   └── tests/        # 单元测试
├── frontend/         # React 前端
│   └── src/
│       ├── views/    # 页面视图
│       ├── widgets/  # UI 组件
│       ├── services/ # API 客户端
│       ├── types/    # 类型定义
│       └── utils/    # 工具函数
└── Makefile          # 常用开发命令
```

## 快速开始

### 1. 准备后端

```bash
cd backend
cp .env.example .env
# 编辑 .env，填写真实的 OPENAI_API_KEY
uv sync --extra dev
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

后端启动后可访问：

- 健康检查：`http://localhost:8001/health`
- Swagger UI：`http://localhost:8001/docs`

### 2. 启动前端

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

浏览器访问 `http://localhost:5173`。

### 3. 添加数据库

在左侧栏点击添加按钮，填写：

- 连接名称：只能包含字母、数字、连字符和下划线；
- 数据库类型：PostgreSQL 或 MySQL；
- 主机、端口、数据库名、用户名、密码；
- 可选描述。

保存前后端会测试连接。连接成功后，选择数据库即可加载元数据、编写查询或使用自然语言生成 SQL。

## 常用命令

```bash
make install          # 安装前后端依赖
make dev-backend      # 启动后端
make dev-frontend     # 启动前端
make lint             # 运行代码检查
make test             # 运行测试
make frontend-build   # 构建前端
```

## 安全提示

- 目标数据库账号应只授予必要的只读权限；
- 数据库连接 URL 当前以明文保存在本地 SQLite；
- 自然语言查询会把数据库结构和用户输入发送给 OpenAI；
- 生产部署前应限制 CORS 来源并妥善管理 `.env`。
