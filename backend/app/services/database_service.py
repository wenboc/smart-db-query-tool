"""数据库高层服务（外观模式）。"""

import time
from typing import Tuple, Optional
import logging

from app.models.database import DatabaseType
from app.adapters.base import ConnectionConfig, QueryResult, MetadataResult
from app.adapters.registry import DatabaseAdapterRegistry, adapter_registry
from app.services.sql_validator import validate_and_transform_sql, SqlValidationError

logger = logging.getLogger(__name__)


class DatabaseService:
    """数据库操作的高层服务（外观模式）。

    此类协调适配器、校验器和其他组件，为数据库操作提供简化接口。

    示例：
        service = DatabaseService(adapter_registry)
        result = await service.execute_query(
            DatabaseType.POSTGRESQL,
            "mydb",
            "postgresql://...",
            "SELECT * FROM users"
        )
    """

    def __init__(self, registry: DatabaseAdapterRegistry):
        """使用适配器注册表初始化服务。

        参数：
            registry：数据库适配器注册表。
        """
        self.registry = registry
        logger.info("Initialized DatabaseService")

    async def test_connection(
        self, db_type: DatabaseType, url: str
    ) -> Tuple[bool, Optional[str]]:
        """测试数据库连接。

        参数：
            db_type：数据库类型。
            url：连接 URL。

        返回：
            由 (success, error_message) 组成的元组。

        示例：
            success, error = await service.test_connection(
                DatabaseType.POSTGRESQL,
                "postgresql://localhost/test"
            )
        """
        config = ConnectionConfig(url=url, name="connection_test")
        adapter = self.registry.create_adapter(db_type, config)
        try:
            return await adapter.test_connection()
        finally:
            await adapter.close_connection_pool()

    async def execute_query(
        self,
        db_type: DatabaseType,
        name: str,
        url: str,
        sql: str,
        limit: int = 1000,
    ) -> Tuple[QueryResult, int]:
        """执行 SQL 查询。

        参数：
            db_type：数据库类型。
            name：连接名称。
            url：连接 URL。
            sql：待校验的 SQL 查询。
            limit：最多返回的行数。

        返回：
            由 (QueryResult, execution_time_ms) 组成的元组。

        异常：
            SqlValidationError：SQL 无效。
            Exception：查询执行失败。

        示例：
            result, time_ms = await service.execute_query(
                DatabaseType.MYSQL,
                "mydb",
                "mysql://...",
                "SELECT * FROM users"
            )
        """
        # 校验并转换 SQL
        validated_sql = validate_and_transform_sql(sql, limit=limit, db_type=db_type)

        # 获取适配器
        config = ConnectionConfig(url=url, name=name)
        adapter = self.registry.get_adapter(db_type, config)

        # 执行查询并统计耗时
        start_time = time.time()
        try:
            result = await adapter.execute_query(validated_sql)
            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"Query executed successfully on {name}: "
                f"{result.row_count} rows in {execution_time_ms}ms"
            )

            return result, execution_time_ms

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Query failed on {name} after {execution_time_ms}ms: {e}")
            raise

    async def extract_metadata(
        self,
        db_type: DatabaseType,
        name: str,
        url: str,
    ) -> MetadataResult:
        """提取数据库元数据。

        参数：
            db_type：数据库类型。
            name：连接名称。
            url：连接 URL。

        返回：
            MetadataResult。

        示例：
            metadata = await service.extract_metadata(
                DatabaseType.POSTGRESQL,
                "mydb",
                "postgresql://..."
            )
        """
        config = ConnectionConfig(url=url, name=name)
        adapter = self.registry.get_adapter(db_type, config)

        logger.info(f"Extracting metadata for {name}")
        metadata = await adapter.extract_metadata()
        logger.info(
            f"Extracted metadata for {name}: "
            f"{len(metadata.tables)} tables, {len(metadata.views)} views"
        )

        return metadata

    async def close_connection(
        self,
        db_type: DatabaseType,
        name: str,
    ) -> None:
        """关闭数据库连接。

        参数：
            db_type：数据库类型。
            name：连接名称。
        """
        await self.registry.close_adapter(db_type, name)
        logger.info(f"Closed connection for {name}")


# 全局服务实例
database_service = DatabaseService(adapter_registry)
