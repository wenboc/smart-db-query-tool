"""数据库适配器包。"""

from app.adapters.base import (
    DatabaseAdapter,
    ConnectionConfig,
    QueryResult,
    MetadataResult,
)

__all__ = [
    "DatabaseAdapter",
    "ConnectionConfig",
    "QueryResult",
    "MetadataResult",
]
