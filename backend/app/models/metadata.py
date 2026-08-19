"""DatabaseMetadata SQLModel 实体。"""

from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text, DateTime
from datetime import datetime, timedelta, timezone


class DatabaseMetadata(SQLModel, table=True):
    """存储在 SQLite 中的数据库元数据缓存。"""

    __tablename__ = "databasemetadata"

    id: int | None = Field(default=None, primary_key=True)
    database_name: str = Field(foreign_key="databaseconnections.name", index=True)
    metadata_json: str = Field(sa_column=Column(Text))
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        sa_column=Column(DateTime(timezone=False)),
    )
    table_count: int = Field(default=0)

    @property
    def is_stale(self) -> bool:
        """检查元数据是否已过期，即获取时间是否超过 24 小时。"""
        # 统一转换为不带时区的 UTC 时间后再比较
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        fetched_at_naive = self.fetched_at.replace(tzinfo=None) if self.fetched_at.tzinfo else self.fetched_at
        return now_naive - fetched_at_naive > timedelta(hours=24)
