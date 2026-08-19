"""管理 PostgreSQL 连接的数据库连接服务。"""
from __future__ import annotations

import asyncpg
from typing import Dict
from datetime import datetime
from app.models.database import DatabaseConnection, ConnectionStatus


# 全局连接池缓存
_connection_pools: Dict[str, asyncpg.Pool] = {}


async def test_connection(url: str) -> tuple[bool, str | None]:
    """
    测试 PostgreSQL 数据库连接。

    参数：
        url：PostgreSQL 连接 URL。

    返回：
        由 (success, error_message) 组成的元组。
    """
    try:
        conn = await asyncpg.connect(url)
        await conn.close()
        return True, None
    except Exception as e:
        return False, str(e)


async def get_connection_pool(
    name: str, url: str, min_size: int = 1, max_size: int = 5
) -> asyncpg.Pool:
    """
    获取或创建数据库的 asyncpg 连接池。

    参数：
        name：数据库连接名称。
        url：PostgreSQL 连接 URL。
        min_size：连接池最小连接数。
        max_size：连接池最大连接数。

    返回：
        asyncpg 连接池。
    """
    if name not in _connection_pools:
        pool = await asyncpg.create_pool(
            url,
            min_size=min_size,
            max_size=max_size,
            command_timeout=60,
        )
        _connection_pools[name] = pool
    return _connection_pools[name]


async def close_connection_pool(name: str) -> None:
    """
    关闭指定数据库的连接池。

    参数：
        name：数据库连接名称。
    """
    if name in _connection_pools:
        pool = _connection_pools.pop(name)
        await pool.close()


async def close_all_connection_pools() -> None:
    """关闭全部连接池。"""
    for name in list(_connection_pools.keys()):
        await close_connection_pool(name)
