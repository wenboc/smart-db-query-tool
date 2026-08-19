"""数据库连接构造与测试流程的单元测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.adapters.base import ConnectionConfig
from app.adapters.mysql import MySQLAdapter
from app.adapters.registry import DatabaseAdapterRegistry
from app.models.database import DatabaseType
from app.services.database_service import DatabaseService


def test_mysql_adapter_decodes_encoded_connection_values() -> None:
    """MySQL 适配器应解码连接 URL 中的特殊字符。"""
    adapter = MySQLAdapter(
        ConnectionConfig(
            name="test",
            url=(
                "mysql://root%40example:QWEasd%40123%3A%2F"
                "@10.0.0.10:3306/order%20db"
            ),
        )
    )

    params = adapter._parse_url(adapter.config.url)

    assert params == {
        "host": "10.0.0.10",
        "port": 3306,
        "user": "root@example",
        "password": "QWEasd@123:/",
        "db": "order db",
    }


@pytest.mark.asyncio
async def test_connection_uses_and_closes_transient_adapter() -> None:
    """连接测试应使用临时适配器，并在测试后立即关闭资源。"""
    registry = MagicMock(spec=DatabaseAdapterRegistry)
    adapter = MagicMock()
    adapter.test_connection = AsyncMock(return_value=(True, None))
    adapter.close_connection_pool = AsyncMock()
    registry.create_adapter.return_value = adapter
    service = DatabaseService(registry)

    result = await service.test_connection(
        DatabaseType.MYSQL,
        "mysql://root:secret@localhost:3306/app",
    )

    assert result == (True, None)
    registry.create_adapter.assert_called_once()
    adapter.test_connection.assert_awaited_once()
    adapter.close_connection_pool.assert_awaited_once()
