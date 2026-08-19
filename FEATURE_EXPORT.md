# 智能数据库查询工具 — 新增功能设计文档

## 一、项目概述

智能数据库查询工具是一款面向开发者和数据分析师的 Web 应用，支持 PostgreSQL 和 MySQL 两种数据库的连接管理、元数据浏览、SQL 查询执行与结果导出，以及自然语言转 SQL（NL2SQL）功能。

本项目在原始版本基础上进行了全面的前端重构与后端优化，核心目标：**差异化 UI 交互体验 + 深色科技风格 + 代码结构解耦**。

---

## 二、新增功能设计思路

### 2.1 全新 MUI 深色科技主题

**设计动机：** 原版使用 Ant Design + 奶油色暖色调方案，本项目切换至 MUI (Material UI) 并采用深色科技风格，视觉上完全区分。

**设计思路：**

| 设计要素 | 实现方案 |
|---------|---------|
| 主色调 | 赛博青 `#00d4ff` — 传达技术感与数据流动性 |
| 辅助色 | 深紫 `#7c4dff` — 用于次要操作与视图标记 |
| 背景色 | 深蓝黑 `#0a0e1a` (默认) / `#111827` (卡片) — 降低视觉疲劳 |
| 字体 | JetBrains Mono / Fira Code 等宽编程字体 — 契合 SQL 编辑场景 |
| 圆角 | 统一 8px — 保持现代感又不过于圆润 |
| 按钮风格 | `textTransform: none` + `fontWeight: 600` — 可读性优先 |

**关键代码：**
```typescript
const appTheme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#00d4ff" },
    secondary: { main: "#7c4dff" },
    background: { default: "#0a0e1a", paper: "#111827" },
  },
  typography: {
    fontFamily: '"JetBrains Mono", "Fira Code", "Consolas", monospace',
  },
});
```

### 2.2 左右分栏布局（Drawer + Split Panel）

**设计动机：** 原版采用三栏固定宽度布局，本项目改为「左侧 Drawer 连接列表 + 右侧左右分栏（Schema | Query）」，交互逻辑更清晰。

**设计思路：**

```
┌──────────┬────────────────────────────────────┐
│          │  AppBar: 数据库名 + 统计信息        │
│  连接    ├──────────┬─────────────────────────┤
│  列表    │  Schema  │  Query Panel             │
│  Drawer  │  Browser │  ┌─────────────────┐    │
│          │  (320px) │  │ SQL Editor       │    │
│  - mydb  │          │  └─────────────────┘    │
│  - test  │  表/视图  │  ┌─────────────────┐    │
│          │  树形展示  │  │ Result Table     │    │
│          │  + 搜索   │  └─────────────────┘    │
└──────────┴──────────┴─────────────────────────┘
```

- **Drawer (260px)**：固定左侧，展示数据库连接列表，支持新建/删除
- **Schema Browser (320px)**：可搜索的树形结构，展示表/视图/列
- **Query Panel (flex)**：SQL 编辑器 + 执行结果 + 导出按钮

### 2.3 Schema Browser — 可搜索的树形浏览器

**设计动机：** 原版的元数据展示平铺在一个面板中，当表数量较多时不便查找。新增搜索过滤和折叠分组。

**设计思路：**

1. **搜索框**：实时过滤表名和列名，快速定位目标
2. **折叠分组**：「表」和「视图」分别可折叠/展开
3. **点击交互**：点击表名自动生成 `SELECT * FROM schema.table LIMIT 100` 并填入编辑器
4. **列信息展示**：每列显示名称、类型、是否可为空、是否主键

```tsx
<TextField placeholder="搜索表、列..." onChange={(e) => setFilter(e.target.value)} />
<Box>
  <CollapsibleSection title="表" items={filteredTables} onTableClick={onTableClick} />
  <CollapsibleSection title="视图" items={filteredViews} />
</Box>
```

### 2.4 SQL 编辑器 — 自定义 Monaco 主题

**设计动机：** 原版使用 `vs-dark` 默认主题，本项目自定义了 `db-explorer-dark` 主题，与整体深色风格统一。

**设计思路：**

```typescript
monaco.editor.defineTheme("db-explorer-dark", {
  base: "vs-dark",
  inherit: true,
  rules: [
    { token: "keyword", foreground: "00d4ff", fontStyle: "bold" },   // SQL 关键字：赛博青
    { token: "string", foreground: "00e676" },                       // 字符串：绿色
    { token: "number", foreground: "ffd740" },                       // 数字：金黄
    { token: "comment", foreground: "6a737d", fontStyle: "italic" }, // 注释：灰色斜体
  ],
  colors: {
    "editor.background": "#0d1117",   // 编辑器背景
    "editorCursor.foreground": "#00d4ff",
    "editor.selectionBackground": "#1a3a4a",
  },
});
```

### 2.5 查询结果 — 分页 + CSV/JSON 导出

**设计动机：** 原版结果展示无分页，大数据量时性能差。新增分页和双格式导出。

**设计思路：**

1. **分页展示**：每页 20 行，使用 MUI TablePagination
2. **CSV 导出**：处理逗号/引号/换行等特殊字符
3. **JSON 导出**：格式化缩进输出
4. **执行统计**：行数 + 耗时显示在顶栏 Chip 中

### 2.6 自然语言转 SQL（NL2SQL）

**设计动机：** 原版已集成 OpenAI 接口，本项目保留了该功能，但在前端交互上预留了入口。

**设计思路：**

- 后端通过 `POST /api/v1/dbs/{name}/query/natural` 接口接收自然语言提示词
- 利用数据库元数据（表结构、列信息）作为上下文
- 调用 OpenAI 生成 SQL 和解释说明
- 前端可扩展为对话框式交互

### 2.7 连接管理增强

**设计动机：** 原版的连接表单直接拼接 URL，用户需要理解连接串格式。本项目拆分为独立字段，自动构建 URL。

**设计思路：**

1. **表单字段**：数据库类型、主机、端口、数据库名、用户名、密码、说明
2. **自动构建 URL**：根据字段值自动生成 `mysql://user:pass@host:port/db`
3. **默认端口**：选择数据库类型时自动填入默认端口（PostgreSQL=5432, MySQL=3306）
4. **连接测试**：提交前先测试连接，失败则给出友好错误提示

```typescript
export function buildConnectionUrl(v: ConnectionFormValues): string {
  const { dbType, host, port, database, username, password } = v;
  const scheme = dbType === "mysql" ? "mysql" : "postgresql";
  return `${scheme}://${username}:${password}@${host}:${port}/${database}`;
}
```

---

## 三、后端优化

### 3.1 调试代码清理

移除了所有 `urllib.request` 向 `127.0.0.1:7777` 发送调试事件的代码，包括：
- `databases.py` 中的 SQLite 提交追踪探针
- `mysql.py` 中的连接/握手/失败事件探针

### 3.2 SQL 校验与 LIMIT 自动补充

使用 sqlglot 库对 SQL 进行校验和转换：
- **白名单**：仅允许 SELECT 语句
- **自动 LIMIT**：缺少 LIMIT 时自动补充 1000 行限制
- **方言适配**：根据数据库类型选择对应方言解析

### 3.3 元数据缓存

数据库元数据通过 SQLite 缓存，避免每次请求都查询 INFORMATION_SCHEMA：
- 缓存有效期 30 分钟
- 支持手动刷新（`POST /api/v1/dbs/{name}/refresh`）
- 缓存过期自动标记 `isStale`

---

## 四、技术栈对比

| 技术栈 | 原版 | 本项目 |
|--------|------|--------|
| 前端框架 | React + Ant Design 5 | React + MUI 6 |
| 主题 | 奶油色暖色调 (MotherDuck 风格) | 深色科技风 (Cyberpunk) |
| CSS 方案 | Tailwind CSS | Emotion (CSS-in-JS via MUI) |
| 路由 | react-router-dom + @refinedev | 单页 Dashboard (无路由) |
| SQL 编辑器 | Monaco (vs-dark) | Monaco (db-explorer-dark 自定义) |
| 组件结构 | pages/ + components/ | views/ + widgets/ |
| 后端框架 | FastAPI | FastAPI (同) |
| 数据库 ORM | SQLModel | SQLModel (同) |
| 连接池 | aiomysql / asyncpg | aiomysql / asyncpg (同) |
| 调试代码 | 含探针日志 | 已全部清除 |

---

## 五、目录结构

```
db_explorer/
├── backend/
│   ├── app/
│   │   ├── adapters/          # 数据库适配器 (PostgreSQL/MySQL)
│   │   ├── api/v1/            # API 端点 (databases, queries)
│   │   ├── models/            # 数据模型
│   │   ├── services/          # 业务逻辑 (database_service, sql_validator, nl2sql)
│   │   ├── utils/             # 工具函数
│   │   ├── config.py          # 配置管理
│   │   ├── database.py        # SQLite 初始化
│   │   └── main.py            # FastAPI 入口
│   ├── .env                   # 环境变量
│   └── pyproject.toml         # Python 依赖
├── frontend/
│   ├── src/
│   │   ├── services/          # API 客户端
│   │   ├── types/             # TypeScript 类型定义
│   │   ├── utils/             # 工具函数
│   │   ├── views/             # 页面视图 (Dashboard)
│   │   ├── widgets/           # UI 组件 (SchemaBrowser, QueryPanel)
│   │   ├── App.tsx            # 主题配置
│   │   └── main.tsx           # 入口
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── fixtures/                  # 示例数据
├── docs/                      # 架构文档
└── FEATURE_EXPORT.md          # 本文档
```

---

## 六、运行方式

```bash
# 后端
cd backend
uv sync
uvicorn app.main:app --host 0.0.0.0 --port 8001

# 前端
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

访问 http://localhost:5173 即可使用。
