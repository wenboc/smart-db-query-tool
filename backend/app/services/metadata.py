"""数据库元数据缓存与提取服务。"""

import json
from typing import Dict, Any
from datetime import datetime, timezone
from sqlmodel import Session, select
from app.models.metadata import DatabaseMetadata
from app.models.database import DatabaseType
from app.services.database_service import database_service


async def get_cached_metadata(
    session: Session, database_name: str
) -> DatabaseMetadata | None:
    """
    从 SQLite 获取尚未过期的缓存元数据。

    参数：
        session：SQLite 数据库会话。
        database_name：数据库连接名称。

    返回：
        找到且未过期时返回 DatabaseMetadata，否则返回 None。
    """
    statement = select(DatabaseMetadata).where(
        DatabaseMetadata.database_name == database_name
    )
    metadata = session.exec(statement).first()

    if metadata and not metadata.is_stale:
        return metadata

    return None


async def cache_metadata(
    session: Session,
    database_name: str,
    metadata_dict: Dict[str, Any],
) -> DatabaseMetadata:
    """
    将元数据缓存到 SQLite。

    参数：
        session：SQLite 数据库会话。
        database_name：数据库连接名称。
        metadata_dict：待缓存的元数据字典。

    返回：
        已缓存的 DatabaseMetadata 实例。
    """
    statement = select(DatabaseMetadata).where(
        DatabaseMetadata.database_name == database_name
    )
    existing = session.exec(statement).first()

    metadata_json = json.dumps(metadata_dict)
    table_count = len(metadata_dict.get("tables", [])) + len(
        metadata_dict.get("views", [])
    )

    if existing:
        existing.metadata_json = metadata_json
        existing.fetched_at = datetime.now(timezone.utc)
        existing.table_count = table_count
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    else:
        new_metadata = DatabaseMetadata(
            database_name=database_name,
            metadata_json=metadata_json,
            fetched_at=datetime.now(timezone.utc),
            table_count=table_count,
        )
        session.add(new_metadata)
        session.commit()
        session.refresh(new_metadata)
        return new_metadata


async def fetch_metadata(
    session: Session,
    database_name: str,
    db_type: DatabaseType,
    url: str,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    获取数据库元数据并使用缓存。

    参数：
        session：SQLite 数据库会话。
        database_name：数据库连接名称。
        db_type：数据库类型。
        url：数据库连接 URL。
        force_refresh：即使缓存存在也强制刷新。

    返回：
        元数据字典。
    """
    # 优先检查缓存
    if not force_refresh:
        cached = await get_cached_metadata(session, database_name)
        if cached:
            return json.loads(cached.metadata_json)

    # 使用适配器服务提取元数据
    result = await database_service.extract_metadata(db_type, database_name, url)
    metadata_dict = result.to_dict()

    # 写入缓存
    await cache_metadata(session, database_name, metadata_dict)

    return metadata_dict
