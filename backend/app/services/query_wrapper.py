from app.models.query import QuerySource
from app.models.schemas import QueryResult, QueryColumn
from app.services.database_service import database_service
from app.services.sql_validator import SqlValidationError
from app.services.security import SecurityPolicy, SecurityViolationError
from app.services.query import save_query_history

async def execute_query_with_service(session, database_name, db_type, url, sql, query_source=QuerySource.MANUAL):
    policy = SecurityPolicy.from_connection_name(database_name, db_type)
    policy.enforce(sql)
    try:
        result, execution_time_ms = await database_service.execute_query(db_type=db_type, name=database_name, url=url, sql=sql, limit=1000)
        columns = [QueryColumn(**col) for col in result.columns]
        await save_query_history(session, database_name, sql, result.row_count, execution_time_ms, True, None, query_source)
        return QueryResult(columns=columns, rows=result.rows, rowCount=result.row_count, executionTimeMs=execution_time_ms, sql=sql)
    except SqlValidationError as e:
        await save_query_history(session, database_name, sql, None, None, False, str(e), query_source); raise
    except SecurityViolationError as e:
        await save_query_history(session, database_name, sql, None, None, False, f"[SECURITY] {e}", query_source); raise
    except Exception as e:
        await save_query_history(session, database_name, sql, None, None, False, str(e), query_source); raise
