"""QueryHistory SQLModel 实体。"""
from __future__ import annotations

from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text, DateTime
from datetime import datetime, timezone
from enum import Enum


class QuerySource(str, Enum):
    """查询来源类型。"""

    MANUAL = "manual"
    NATURAL_LANGUAGE = "natural_language"


class QueryHistory(SQLModel, table=True):
    """存储在 SQLite 中的查询历史实体。"""

    __tablename__ = "queryhistory"

    id: int | None = Field(default=None, primary_key=True)
    database_name: str = Field(foreign_key="databaseconnections.name")
    sql_text: str = Field(sa_column=Column(Text))
    executed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        sa_column=Column(DateTime(timezone=False), index=True),
    )
    execution_time_ms: int | None = None
    row_count: int | None = None
    success: bool
    error_message: str | None = Field(default=None, sa_column=Column(Text))
    query_source: QuerySource = Field(default=QuerySource.MANUAL)
