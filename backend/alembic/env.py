from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from sqlmodel import SQLModel
from app.config import settings
from app.database import engine
from app.models import *  # noqa: F401, F403

# Alembic 配置对象
config = context.config

# 读取配置文件中的 Python 日志设置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 根据应用配置设置 SQLAlchemy URL
config.set_main_option("sqlalchemy.url", str(engine.url))

# 指定模型的 MetaData 对象
target_metadata = SQLModel.metadata

def run_migrations_offline() -> None:
    """以离线模式运行迁移。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """以在线模式运行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
