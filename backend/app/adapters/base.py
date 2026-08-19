"""数据库适配器的基类与数据结构。"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ConnectionConfig:
    """数据库连接配置。

    属性：
        url：数据库连接 URL。
        name：连接标识。
        min_pool_size：连接池最小连接数。
        max_pool_size：连接池最大连接数。
        command_timeout：命令超时时间，单位为秒。
    """
    url: str
    name: str
    min_pool_size: int = 1
    max_pool_size: int = 5
    command_timeout: int = 60


@dataclass
class QueryResult:
    """标准化查询结果。

    属性：
        columns：包含 name 和 dataType 的列定义列表。
        rows：由行字典组成的列表。
        row_count：返回的行数。
    """
    columns: List[Dict[str, str]]
    rows: List[Dict[str, Any]]
    row_count: int

    def to_dict(self) -> Dict[str, Any]:
        """转换为 API 响应使用的字典。"""
        return {
            "columns": self.columns,
            "rows": self.rows,
            "rowCount": self.row_count,
        }


@dataclass
class MetadataResult:
    """标准化元数据结果。

    属性：
        tables：表元数据字典列表。
        views：视图元数据字典列表。
    """
    tables: List[Dict[str, Any]]
    views: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """转换为 API 响应使用的字典。"""
        return {
            "tables": self.tables,
            "views": self.views,
        }


class DatabaseAdapter(ABC):
    """数据库适配器抽象基类。

    所有数据库实现都必须继承此类并实现全部抽象方法，以保证不同
    数据库类型具有一致的行为。

    适配器负责：
    - 连接管理（连接池）
    - 查询执行
    - 元数据提取
    - 数据库专用类型转换

    示例：
        class PostgreSQLAdapter(DatabaseAdapter):
            async def test_connection(self):
                # 具体实现
                pass
    """

    def __init__(self, config: ConnectionConfig):
        """使用连接配置初始化适配器。

        参数：
            config：连接配置。
        """
        self.config = config
        self._pool: Optional[Any] = None

    @abstractmethod
    async def test_connection(self) -> Tuple[bool, Optional[str]]:
        """测试数据库连接。

        此方法应尝试连接数据库，并确认连接可用。

        返回：
            由 (success, error_message) 组成的元组。
            - success：连接成功时为 True，否则为 False。
            - error_message：失败时返回错误消息，成功时为 None。

        示例：
            success, error = await adapter.test_connection()
            if not success:
                print(f"Connection failed: {error}")
        """
        pass

    @abstractmethod
    async def get_connection_pool(self) -> Any:
        """获取或创建连接池。

        此方法应在首次调用时创建连接池，后续调用返回缓存的连接池。

        返回：
            数据库专用的连接池对象。

        示例：
            pool = await adapter.get_connection_pool()
            async with pool.acquire() as conn:
                # 使用连接
        """
        pass

    @abstractmethod
    async def close_connection_pool(self) -> None:
        """关闭连接池并清理资源。

        此方法应关闭连接池中的全部连接并释放相关资源。

        示例：
            await adapter.close_connection_pool()
        """
        pass

    @abstractmethod
    async def extract_metadata(self) -> MetadataResult:
        """提取表、列等数据库元数据。

        此方法应查询数据库的元数据目录，例如 information_schema
        或 pg_catalog，以获取结构信息。

        返回：
            包含表和视图的 MetadataResult。

        示例：
            metadata = await adapter.extract_metadata()
            for table in metadata.tables:
                print(f"Table: {table['name']}")
        """
        pass

    @abstractmethod
    async def execute_query(self, sql: str) -> QueryResult:
        """执行 SQL 查询。

        此方法应执行给定的 SQL 查询，并以标准格式返回结果。

        参数：
            sql：已经过校验的 SQL 查询字符串。

        返回：
            包含列信息和数据行的 QueryResult。

        异常：
            Exception：查询执行失败。

        示例：
            result = await adapter.execute_query("SELECT * FROM users")
            for row in result.rows:
                print(row)
        """
        pass

    @abstractmethod
    def get_dialect_name(self) -> str:
        """返回此数据库在 sqlglot 中使用的 SQL 方言名称。

        返回：
            方言名称，例如 'postgres'、'mysql' 或 'oracle'。

        示例：
            dialect = adapter.get_dialect_name()  # 'postgres'
        """
        pass

    @abstractmethod
    def get_identifier_quote_char(self) -> str:
        """返回引用标识符所用的字符。

        返回：
            引用字符，例如 PostgreSQL 使用 '"'，MySQL 使用 '`'。

        示例：
            quote = adapter.get_identifier_quote_char()  # '"'
            table_name = f'{quote}my_table{quote}'  # "my_table"
        """
        pass

    async def __aenter__(self):
        """进入异步上下文管理器。"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出异步上下文管理器并清理资源。"""
        await self.close_connection_pool()
