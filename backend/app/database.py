"""SQLite 数据库初始化与会话管理。"""

from sqlmodel import SQLModel, create_engine, Session
from app.config import settings
from typing import Generator


# 创建 SQLite 引擎
engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},  # SQLite 需要关闭同线程检查
    echo=False,  # 设为 True 时输出 SQL 查询日志
)


def init_db() -> None:
    """创建全部数据表以初始化数据库。"""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """为 FastAPI 依赖注入提供数据库会话。"""
    with Session(engine) as session:
        yield session
