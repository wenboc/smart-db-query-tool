"""数据库适配器注册表（工厂模式）。"""

from typing import Dict, Type, List
import logging

from app.models.database import DatabaseType
from app.adapters.base import DatabaseAdapter, ConnectionConfig
from app.adapters.postgresql import PostgreSQLAdapter
from app.adapters.mysql import MySQLAdapter

logger = logging.getLogger(__name__)


class DatabaseAdapterRegistry:
    """数据库适配器注册表（工厂模式）。

    此类维护数据库类型到适配器类的映射。新增数据库类型时，可以通过
    注册适配器进行扩展，而无须修改已有适配器实现。

    示例：
        registry = DatabaseAdapterRegistry()
        config = ConnectionConfig(url="postgresql://...", name="mydb")
        adapter = registry.get_adapter(DatabaseType.POSTGRESQL, config)
        result = await adapter.execute_query("SELECT 1")
    """

    def __init__(self):
        """使用内置适配器初始化注册表。"""
        self._adapters: Dict[DatabaseType, Type[DatabaseAdapter]] = {}
        self._instances: Dict[str, DatabaseAdapter] = {}

        # 注册内置适配器
        self.register(DatabaseType.POSTGRESQL, PostgreSQLAdapter)
        self.register(DatabaseType.MYSQL, MySQLAdapter)

        logger.info(f"Initialized adapter registry with {len(self._adapters)} adapters")

    def register(
        self, db_type: DatabaseType, adapter_class: Type[DatabaseAdapter]
    ) -> None:
        """注册数据库适配器。

        参数：
            db_type：数据库类型枚举值。
            adapter_class：必须继承 DatabaseAdapter 的适配器类。

        异常：
            TypeError：adapter_class 未继承 DatabaseAdapter。

        示例：
            registry.register(DatabaseType.ORACLE, OracleAdapter)
        """
        if not issubclass(adapter_class, DatabaseAdapter):
            raise TypeError(
                f"{adapter_class.__name__} must inherit from DatabaseAdapter"
            )

        self._adapters[db_type] = adapter_class
        logger.info(f"Registered {adapter_class.__name__} for {db_type.value}")

    def get_adapter(
        self, db_type: DatabaseType, config: ConnectionConfig
    ) -> DatabaseAdapter:
        """获取或创建数据库适配器实例。

        参数：
            db_type：数据库类型。
            config：连接配置。

        返回：
            DatabaseAdapter 实例。

        异常：
            ValueError：数据库类型尚未注册。

        示例：
            config = ConnectionConfig(url="mysql://...", name="mydb")
            adapter = registry.get_adapter(DatabaseType.MYSQL, config)
        """
        # 使用连接名称和数据库类型组成缓存键
        cache_key = f"{db_type.value}:{config.name}"

        if cache_key not in self._instances:
            adapter = self.create_adapter(db_type, config)
            self._instances[cache_key] = adapter
            logger.info(f"Created new {type(adapter).__name__} instance for {config.name}")

        return self._instances[cache_key]

    def create_adapter(
        self, db_type: DatabaseType, config: ConnectionConfig
    ) -> DatabaseAdapter:
        """创建不写入缓存的数据库适配器。

        连接测试使用临时适配器，防止不同 URL 因共用连接名称而复用旧配置。
        """
        if db_type not in self._adapters:
            available = [t.value for t in self._adapters.keys()]
            raise ValueError(
                f"Unsupported database type: {db_type.value}. "
                f"Available types: {available}"
            )

        adapter_class = self._adapters[db_type]
        return adapter_class(config)

    async def close_adapter(self, db_type: DatabaseType, name: str) -> None:
        """关闭并移除适配器实例。

        参数：
            db_type：数据库类型。
            name：连接名称。
        """
        cache_key = f"{db_type.value}:{name}"

        if cache_key in self._instances:
            adapter = self._instances.pop(cache_key)
            await adapter.close_connection_pool()
            logger.info(f"Closed adapter for {name}")

    async def close_all_adapters(self) -> None:
        """关闭全部适配器实例。"""
        logger.info(f"Closing {len(self._instances)} adapter instances")
        for adapter in list(self._instances.values()):
            await adapter.close_connection_pool()
        self._instances.clear()

    def is_supported(self, db_type: DatabaseType) -> bool:
        """检查是否支持指定数据库类型。

        参数：
            db_type：待检查的数据库类型。

        返回：
            支持时为 True，否则为 False。
        """
        return db_type in self._adapters

    def get_supported_types(self) -> List[DatabaseType]:
        """返回支持的数据库类型列表。

        返回：
            已注册的数据库类型列表。
        """
        return list(self._adapters.keys())


# 全局注册表实例
adapter_registry = DatabaseAdapterRegistry()
