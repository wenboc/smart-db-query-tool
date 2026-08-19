"""数据库查询工具的数据模型。"""

from pydantic import BaseModel, ConfigDict
from typing import Callable


def to_camel(string: str) -> str:
    """将 snake_case 转换为 camelCase。"""
    components = string.split("_")
    return components[0] + "".join(word.capitalize() for word in components[1:])


# 配置全局 Pydantic camelCase 序列化规则
BaseModel.model_config = ConfigDict(
    alias_generator=to_camel,
    populate_by_name=True,
    str_strip_whitespace=True,
)

from app.models.database import DatabaseConnection  # noqa: E402
from app.models.metadata import DatabaseMetadata  # noqa: E402
from app.models.query import QueryHistory, QuerySource  # noqa: E402
from app.models.schemas import (  # noqa: E402
    DatabaseConnectionInput,
    DatabaseConnectionResponse,
    DatabaseMetadataResponse,
    TableMetadata,
    ColumnMetadata,
    QueryInput,
    QueryResult,
    QueryColumn,
    QueryHistoryEntry,
    NaturalLanguageInput,
    GeneratedSqlResponse,
    ErrorResponse,
)

__all__ = [
    "DatabaseConnection",
    "DatabaseMetadata",
    "QueryHistory",
    "QuerySource",
    "DatabaseConnectionInput",
    "DatabaseConnectionResponse",
    "DatabaseMetadataResponse",
    "TableMetadata",
    "ColumnMetadata",
    "QueryInput",
    "QueryResult",
    "QueryColumn",
    "QueryHistoryEntry",
    "NaturalLanguageInput",
    "GeneratedSqlResponse",
    "ErrorResponse",
]
