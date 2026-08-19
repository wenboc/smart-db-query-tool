# 数据库适配器开发指南

## 1. 概述

适配器层把不同数据库驱动转换为统一的连接、元数据和查询接口。目前提供：

- `PostgreSQLAdapter`：asyncpg；
- `MySQLAdapter`：aiomysql；
- `DatabaseAdapterRegistry`：创建、缓存和关闭适配器；
- `DatabaseService`：面向 API 的外观服务。

当前连接测试、删除连接和主查询 API 已使用适配器。元数据 API 仍走旧服务，因此新增数据库时还要处理兼容路径。详情见 [`docs/DETAILED_DESIGN.md`](../../../docs/DETAILED_DESIGN.md)。

## 2. 快速开始

### 步骤 1：创建适配器文件

```text
backend/app/adapters/your_database.py
```

### 步骤 2：实现 DatabaseAdapter

```python
from typing import Any

from app.adapters.base import (
    ConnectionConfig,
    DatabaseAdapter,
    MetadataResult,
    QueryResult,
)


class YourDatabaseAdapter(DatabaseAdapter):
    """目标数据库适配器。"""

    async def test_connection(self) -> tuple[bool, str | None]:
        """测试连接并返回成功状态和错误。"""
        try:
            connection = await ...
            await ...
            return True, None
        except Exception as exc:
            return False, str(exc)

    async def get_connection_pool(self) -> Any:
        """延迟创建并返回连接池。"""
        if self._pool is None:
            self._pool = await ...
        return self._pool

    async def close_connection_pool(self) -> None:
        """关闭连接池并清空引用。"""
        if self._pool is not None:
            await ...
            self._pool = None

    async def extract_metadata(self) -> MetadataResult:
        """提取表、视图和列。"""
        return MetadataResult(tables=[], views=[])

    async def execute_query(self, sql: str) -> QueryResult:
        """执行已验证的只读 SQL。"""
        return QueryResult(columns=[], rows=[], row_count=0)

    def get_dialect_name(self) -> str:
        """返回 sqlglot 方言名。"""
        return "your_dialect"

    def get_identifier_quote_char(self) -> str:
        """返回标识符引用字符。"""
        return '"'
```

### 步骤 3：增加数据库枚举

文件：`app/models/database.py`

```python
class DatabaseType(str, Enum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    YOUR_DATABASE = "your_database"
```

### 步骤 4：注册适配器

文件：`app/adapters/registry.py`

```python
self._adapter_classes = {
    DatabaseType.POSTGRESQL: PostgreSQLAdapter,
    DatabaseType.MYSQL: MySQLAdapter,
    DatabaseType.YOUR_DATABASE: YourDatabaseAdapter,
}
```

### 步骤 5：更新 URL 检测

文件：`app/utils/db_parser.py`

```python
if scheme in ("yourdb", "yourdb+driver"):
    return DatabaseType.YOUR_DATABASE
```

### 步骤 6：更新 SQL 方言

当前 `sql_validator.py` 只区分 PostgreSQL 和 MySQL。新增数据库必须增加显式映射，避免自动落入错误方言。

### 步骤 7：处理当前元数据路径

元数据 API 迁移完成前，还要修改：

- `services/connection_factory.py`；
- 对应旧连接池服务；
- `services/metadata.py` 的数据库类型分派。

更合理的长期方案是先让元数据 API 调用 `DatabaseService.extract_metadata()`。

### 步骤 8：增加测试

至少增加：

- URL 检测；
- 适配器单元测试；
- 注册表测试；
- 统一契约测试；
- 真实数据库集成测试；
- API 连接、元数据和查询测试。

## 3. 基础类型

### 3.1 ConnectionConfig

```python
@dataclass
class ConnectionConfig:
    url: str
    name: str
    min_pool_size: int = 1
    max_pool_size: int = 5
    command_timeout: int = 60
```

注意：

- `name` 与数据库类型组成注册表缓存键；
- URL 更新后必须避免复用旧适配器；
- 池配置当前由默认值提供，后续应接入 `Settings`。

### 3.2 QueryResult

```python
QueryResult(
    columns=[
        {"name": "id", "dataType": "integer"},
        {"name": "name", "dataType": "character varying"},
    ],
    rows=[
        {"id": 1, "name": "Alice"},
    ],
    row_count=1,
)
```

规则：

- `columns` 按查询返回顺序排列；
- `rows` 必须是普通字典；
- 值必须可由 FastAPI 编码；
- `row_count` 与 `rows` 长度一致。

### 3.3 MetadataResult

```python
MetadataResult(
    tables=[
        {
            "name": "users",
            "type": "table",
            "schemaName": "public",
            "rowCount": 100,
            "columns": [
                {
                    "name": "id",
                    "dataType": "integer",
                    "nullable": False,
                    "primaryKey": True,
                    "unique": True,
                    "defaultValue": None,
                }
            ],
        }
    ],
    views=[],
)
```

## 4. 连接管理

### 4.1 延迟创建连接池

```python
async def get_connection_pool(self):
    if self._pool is None:
        self._pool = await driver.create_pool(...)
    return self._pool
```

不要在适配器构造函数中执行网络 I/O。

### 4.2 URL 解析

```python
from urllib.parse import urlparse

parsed = urlparse(self.config.url)
host = parsed.hostname or "localhost"
port = parsed.port or DEFAULT_PORT
database = parsed.path.lstrip("/")
```

处理：

- 默认主机和端口；
- 空数据库名；
- URL 编码；
- 驱动 scheme；
- TLS 和查询参数；
- IPv6。

### 4.3 连接测试

连接测试应使用最小资源：

1. 创建单连接或临时池；
2. 执行驱动级连通性验证；
3. 始终关闭临时资源；
4. 返回 `(True, None)` 或 `(False, message)`。

不要把密码写入错误或日志。

### 4.4 关闭协议

PostgreSQL：

```python
await pool.close()
```

MySQL：

```python
pool.close()
await pool.wait_closed()
```

关闭后必须：

```python
self._pool = None
```

关闭方法应允许重复调用。

## 5. 元数据提取

### 5.1 表和视图

返回对象必须区分：

```python
"type": "table"
"type": "view"
```

PostgreSQL 常用：

```text
pg_tables
pg_views
information_schema.columns
```

MySQL 常用：

```text
INFORMATION_SCHEMA.TABLES
INFORMATION_SCHEMA.COLUMNS
INFORMATION_SCHEMA.TABLE_CONSTRAINTS
INFORMATION_SCHEMA.KEY_COLUMN_USAGE
```

### 5.2 列

每列至少返回：

- `name`；
- `dataType`；
- `nullable`；
- `primaryKey`；
- `unique`；
- `defaultValue`。

保留数据库类型细节，例如 `varchar(255)`，但不要把驱动内部类型对象直接暴露给 API。

### 5.3 行数

当前适配器为每个普通表执行精确 `COUNT(*)`。新适配器应评估：

- 大表成本；
- 锁和一致性；
- 是否使用估算；
- 是否把行数作为可选能力；
- 单个表失败是否影响全部元数据。

当前行为在计数失败时返回无 `rowCount` 的表，不中断整个提取。

### 5.4 标识符安全

表名不能使用普通参数占位符。动态标识符必须来自可信目录结果，并使用数据库正确的引用规则。不要直接拼接用户输入。

## 6. 查询执行

### 6.1 输入契约

通过 `DatabaseService` 调用时，SQL 已经：

- 按数据库方言解析；
- 验证为只读查询；
- 在缺少限制时添加 `LIMIT`。

适配器不应再次实现一套不同的验证规则。

### 6.2 结果转换

```python
async def execute_query(self, sql: str) -> QueryResult:
    pool = await self.get_connection_pool()
    async with pool.acquire() as conn:
        driver_rows = await ...
        rows = [convert(row) for row in driver_rows]
        columns = describe(...)
        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
        )
```

需要处理：

- 空结果；
- NULL；
- 日期和时间；
- Decimal；
- UUID；
- JSON；
- 数组；
- bytes；
- 驱动专用对象。

### 6.3 类型信息

优先级：

1. 驱动列描述；
2. 数据库类型 OID/代码；
3. Python 值推断。

只看首行值会在首行 NULL 或空结果时失真。

### 6.4 异常

查询异常应保留原始异常链并交给服务/API。适配器不要返回伪造的空结果表示失败。

## 7. 方言配置

### 7.1 sqlglot 方言

```python
def get_dialect_name(self) -> str:
    return "postgres"
```

返回值必须是 sqlglot 支持的方言标识。

### 7.2 标识符引用

```python
def get_identifier_quote_char(self) -> str:
    return '"'
```

常见值：

- PostgreSQL：`"`；
- MySQL：反引号；
- SQL Server：`[`/`]`，单字符接口可能不足；
- SQLite：通常为 `"`。

若数据库需要成对字符，应扩展接口而不是返回误导值。

## 8. 注册表行为

```python
adapter = adapter_registry.get_adapter(db_type, config)
```

注册表：

- 验证类型是否支持；
- 生成 `type:name` 缓存键；
- 返回缓存实例或创建新实例；
- 关闭时调用适配器的池关闭方法。

### 8.1 不要手工绕过注册表

业务路径直接实例化适配器会造成：

- 无法复用连接池；
- 无法统一关闭；
- 测试替换困难；
- 同一连接出现多个池。

独立单元测试可以直接实例化。

### 8.2 并发

当前字典缓存没有锁。两个并发首次请求可能都创建适配器。若运行场景会触发该竞争，应使用异步锁或单飞机制。

## 9. DatabaseService 用法

### 连接测试

```python
success, error = await database_service.test_connection(
    DatabaseType.POSTGRESQL,
    "postgresql://localhost/example",
)
```

### 查询

```python
result, elapsed_ms = await database_service.execute_query(
    db_type=DatabaseType.MYSQL,
    name="example",
    url="mysql://localhost/example",
    sql="SELECT * FROM users",
    limit=1000,
)
```

### 元数据

```python
metadata = await database_service.extract_metadata(
    db_type=DatabaseType.POSTGRESQL,
    name="example",
    url="postgresql://localhost/example",
)
```

该方法当前没有被元数据 API 使用。

### 关闭

```python
await database_service.close_connection(
    DatabaseType.POSTGRESQL,
    "example",
)
```

## 10. 测试

### 10.1 单元测试

模拟驱动连接和游标，验证：

- 参数解析；
- 池只创建一次；
- 关闭清空池；
- 元数据转换；
- 行转换；
- 类型映射；
- 异常路径。

### 10.2 契约测试

所有适配器必须通过统一测试：

```python
def assert_adapter_contract(adapter):
    assert isinstance(adapter, DatabaseAdapter)
    assert adapter.get_dialect_name()
    assert adapter.get_identifier_quote_char()
```

异步测试还应验证连接、查询、元数据和关闭的返回类型。

### 10.3 集成测试

真实数据库测试应独立标记，验证：

- 连接；
- 表和视图；
- 主键与唯一约束；
- Unicode；
- 常见类型；
- 空结果；
- 重连；
- 关闭后数据库连接数恢复。

### 10.4 API 测试

当前查询路由导入 `execute_query_with_service`。patch 应指向路由模块中的该名称，而不是旧 `execute_query`。

## 11. 错误处理与日志

推荐日志字段：

- 数据库类型；
- 连接名称；
- 操作；
- 耗时；
- 行数；
- 异常类。

禁止记录：

- 完整连接 URL；
- 密码；
- OpenAI Key；
- 不必要的完整 SQL 数据值。

连接测试可返回用户可理解的错误，但应清理敏感参数。

## 12. 适配器检查清单

- [ ] 继承 `DatabaseAdapter`；
- [ ] 实现全部抽象方法；
- [ ] URL 解析覆盖默认值和编码；
- [ ] 连接测试始终释放临时资源；
- [ ] 池延迟创建并复用；
- [ ] 关闭方法幂等；
- [ ] 元数据包含表、视图和列；
- [ ] 主键、唯一、可空和默认值准确；
- [ ] 表行数失败不影响其余元数据；
- [ ] 查询结果可 JSON 序列化；
- [ ] 空结果行为明确；
- [ ] 方言和引用规则正确；
- [ ] 注册表已注册；
- [ ] URL 检测已更新；
- [ ] SQL 验证器已更新；
- [ ] 当前元数据兼容路径已更新；
- [ ] 单元、契约和集成测试齐全；
- [ ] 文档和 REST 示例已更新。

## 13. 常见问题

### 为什么注册后查询可用但元数据失败？

因为当前查询 API 使用适配器，元数据 API 仍使用旧连接工厂。需要扩展旧路径或完成元数据迁移。

### 为什么连接 URL 更新后仍连接旧数据库？

注册表缓存键只包含类型和名称。更新前关闭旧适配器，或让注册表识别配置变化。

### 为什么空结果没有 PostgreSQL 列？

当前 PostgreSQL 适配器从首行推断列。应改用 prepared statement 或驱动列描述。

### 为什么元数据刷新很慢？

当前会逐表执行 `COUNT(*)`。大型数据库应改用估算或关闭精确行数。

### 为什么关闭应用后仍有连接？

当前关闭事件只清理旧 PostgreSQL 池，没有统一关闭注册表和全部旧 MySQL 池。

## 14. 相关文档

- [当前实现详细设计](../../../docs/DETAILED_DESIGN.md)
- [适配器快速参考](../../../docs/QUICK_REFERENCE.md)
- [架构重设计详案](../../../docs/ARCHITECTURE_REDESIGN.md)
- [迁移实施指南](../../../docs/IMPLEMENTATION_GUIDE.md)
