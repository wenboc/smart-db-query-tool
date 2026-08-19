"""使用新数据库服务的查询执行包装器。"""

from typing import List
from sqlmodel import Session, select, desc
from app.models.query import QueryHistory, QuerySource
from app.models.database import DatabaseType
from app.models.schemas import QueryResult, QueryColumn
from app.services.database_service import database_service
from app.services.sql_validator import SqlValidationError
from app.services.query import save_query_history, get_query_history, cleanup_old_queries


async def execute_query_with_service(
    session: Session,
    database_name: str,
    db_type: DatabaseType,
    url: str,
    sql: str,
    query_source: QuerySource = QuerySource.MANUAL,
) -> QueryResult:
    """
    使用新数据库服务执行 SQL 查询。

    参数：
        session：SQLite 数据库会话。
        database_name：数据库连接名称。
        db_type：数据库类型。
        url：数据库连接 URL。
        sql：SQL 查询字符串。
        query_source：查询来源，即手工输入或自然语言。

    返回：
        包含列、数据行和执行信息的 QueryResult。

    异常：
        SqlValidationError：SQL 校验失败。
        Exception：查询执行失败。
    """
    # 使用新数据库服务执行查询
    try:
        result, execution_time_ms = await database_service.execute_query(
            db_type=db_type,
            name=database_name,
            url=url,
            sql=sql,
            limit=1000,
        )

        # 将适配器结果转换为 API 响应模型
        columns = [QueryColumn(**col) for col in result.columns]

        # 保存成功查询的历史记录
        await save_query_history(
            session,
            database_name,
            sql,
            result.row_count,
            execution_time_ms,
            True,
            None,
            query_source,
        )

        return QueryResult(
            columns=columns,
            rows=result.rows,
            rowCount=result.row_count,
            executionTimeMs=execution_time_ms,
            sql=sql,
        )

    except SqlValidationError as e:
        # 保存因校验错误而失败的查询历史
        await save_query_history(
            session,
            database_name,
            sql,
            None,
            None,
            False,
            str(e),
            query_source,
        )
        raise

    except Exception as e:
        # 保存因执行错误而失败的查询历史
        await save_query_history(
            session,
            database_name,
            sql,
            None,
            None,
            False,
            str(e),
            query_source,
        )
        raise
