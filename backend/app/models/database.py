"""DatabaseConnection SQLModel 实体。"""

from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from enum import Enum


class DatabaseType(str, Enum):
    """数据库类型。"""

    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


class ConnectionStatus(str, Enum):
    """数据库连接状态。"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class DatabaseConnection(SQLModel, table=True):
    """存储在 SQLite 中的数据库连接实体。"""

    __tablename__ = "databaseconnections"

    name: str = Field(primary_key=True, max_length=50)
    url: str = Field(index=True, max_length=500)
    db_type: DatabaseType = Field(default=DatabaseType.POSTGRESQL)
    description: str | None = Field(default=None, max_length=200)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    last_connected_at: datetime | None = None
    status: ConnectionStatus = Field(default=ConnectionStatus.ACTIVE)
