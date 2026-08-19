"""查询历史管理服务。"""
from __future__ import annotations

from typing import List
from datetime import datetime, timezone
from sqlmodel import Session, select, desc
from app.models.query import QueryHistory


async def save_query_history(
    session: Session,
    database_name: str,
    sql: str,
    row_count: int | None,
    execution_time_ms: int | None,
    success: bool,
    error_message: str | None,
    query_source: QuerySource,
) -> QueryHistory:
    """
    保存查询历史。

    参数：
        session：SQLite 数据库会话。
        database_name：数据库连接名称。
        sql：SQL 查询字符串。
        row_count：返回的行数。
        execution_time_ms：执行耗时，单位为毫秒。
        success：查询是否成功。
        error_message：失败时的错误消息。
        query_source：查询来源。

    返回：
        已保存的 QueryHistory 实例。
    """
    history = QueryHistory(
        database_name=database_name,
        sql_text=sql,
        executed_at=datetime.now(timezone.utc),
        execution_time_ms=execution_time_ms,
        row_count=row_count,
        success=success,
        error_message=error_message,
        query_source=query_source,
    )

    session.add(history)
    session.commit()
    session.refresh(history)

    # 每个数据库仅保留最近 50 条查询
    await cleanup_old_queries(session, database_name)

    return history


async def cleanup_old_queries(session: Session, database_name: str) -> None:
    """
    仅保留指定数据库最近 50 条查询。

    参数：
        session：SQLite 数据库会话。
        database_name：数据库连接名称。
    """
    # 按执行时间倒序获取此数据库的全部查询
    statement = (
        select(QueryHistory)
        .where(QueryHistory.database_name == database_name)
        .order_by(desc(QueryHistory.executed_at))
    )
    all_queries = session.exec(statement).all()

    # 删除第 50 条之后的查询
    if len(all_queries) > 50:
        queries_to_delete = all_queries[50:]
        for query in queries_to_delete:
            session.delete(query)
        session.commit()


async def get_query_history(
    session: Session, database_name: str, limit: int = 50
) -> List[QueryHistory]:
    """
    获取指定数据库的查询历史。

    参数：
        session：SQLite 数据库会话。
        database_name：数据库连接名称。
        limit：最多返回的查询数量。

    返回：
        QueryHistory 条目列表。
    """
    statement = (
        select(QueryHistory)
        .where(QueryHistory.database_name == database_name)
        .order_by(desc(QueryHistory.executed_at))
        .limit(limit)
    )
    return list(session.exec(statement).all())
