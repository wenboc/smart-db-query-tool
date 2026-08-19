"""使用 camelCase 别名的 API 请求和响应模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal, Any
from datetime import datetime
from app.models.query import QuerySource


# 数据库连接模型
class DatabaseConnectionInput(BaseModel):
    """创建或更新数据库连接的输入模型。"""

    url: str = Field(..., description="Database connection URL (PostgreSQL or MySQL)")
    db_type: str | None = Field(default=None, alias="dbType", description="Database type (postgresql or mysql). Auto-detected from URL if not provided.")
    description: str | None = Field(default=None, max_length=200)


class DatabaseConnectionResponse(BaseModel):
    """数据库连接响应模型。"""

    name: str
    url: str
    db_type: str = Field(..., alias="dbType")
    description: str | None
    created_at: datetime
    updated_at: datetime
    last_connected_at: datetime | None
    status: str


# 元数据模型
class ColumnMetadata(BaseModel):
    """列元数据模型。"""

    name: str = Field(..., max_length=63)
    data_type: str = Field(..., alias="dataType")
    nullable: bool
    primary_key: bool = Field(..., alias="primaryKey")
    unique: bool = False
    default_value: str | None = Field(default=None, alias="defaultValue")
    comment: str | None = None


class TableMetadata(BaseModel):
    """表或视图的元数据模型。"""

    name: str = Field(..., max_length=63)
    type: Literal["table", "view"]
    columns: list[ColumnMetadata]
    row_count: int | None = Field(default=None, alias="rowCount")
    schema_name: str = Field(default="public", alias="schemaName")


class DatabaseMetadataResponse(BaseModel):
    """数据库元数据响应模型。"""

    database_name: str = Field(..., alias="databaseName")
    tables: list[TableMetadata]
    views: list[TableMetadata]
    fetched_at: datetime = Field(..., alias="fetchedAt")
    is_stale: bool = Field(..., alias="isStale")


# 查询模型
class QueryInput(BaseModel):
    """执行 SQL 查询的输入模型。"""

    sql: str = Field(..., min_length=1, description="SQL SELECT query to execute")


class QueryColumn(BaseModel):
    """查询结果列模型。"""

    name: str
    data_type: str = Field(..., alias="dataType")


class QueryResult(BaseModel):
    """查询结果响应模型。"""

    columns: list[QueryColumn]
    rows: list[dict[str, Any]]
    row_count: int = Field(..., alias="rowCount")
    execution_time_ms: int = Field(..., alias="executionTimeMs")
    sql: str


class QueryHistoryEntry(BaseModel):
    """查询历史条目模型。"""

    id: int
    database_name: str = Field(..., alias="databaseName")
    sql_text: str = Field(..., alias="sqlText")
    executed_at: datetime = Field(..., alias="executedAt")
    execution_time_ms: int | None = Field(None, alias="executionTimeMs")
    row_count: int | None = Field(None, alias="rowCount")
    success: bool
    error_message: str | None = Field(None, alias="errorMessage")
    query_source: str = Field(..., alias="querySource")


# 自然语言模型
class NaturalLanguageInput(BaseModel):
    """自然语言转 SQL 的输入模型。"""

    prompt: str = Field(..., min_length=5, max_length=500)


class GeneratedSqlResponse(BaseModel):
    """SQL 生成结果响应模型。"""

    sql: str
    explanation: str


# 错误响应模型
class ErrorResponse(BaseModel):
    """错误响应模型。"""

    error: dict[str, Any]
