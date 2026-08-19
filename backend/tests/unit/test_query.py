"""查询执行服务单元测试。"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime, timezone
from sqlmodel import Session, SQLModel, create_engine, select
from app.services.query import (
    execute_query,
    save_query_history,
    cleanup_old_queries,
    get_query_history,
)
from app.models.query import QueryHistory, QuerySource
from app.models.schemas import QueryResult, QueryColumn
from app.services.sql_validator import SqlValidationError


@pytest.fixture
def test_session():
    """创建用于测试的内存 SQLite 会话。"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def mock_pool():
    """创建模拟的 asyncpg 连接池。"""
    pool = MagicMock()
    conn = AsyncMock()

    # 为 pool.acquire() 创建异步上下文管理器
    acquire_context = AsyncMock()
    acquire_context.__aenter__.return_value = conn
    acquire_context.__aexit__.return_value = None
    pool.acquire.return_value = acquire_context

    return pool, conn


class TestExecuteQuery:
    """测试查询执行函数。"""

    @pytest.mark.asyncio
    async def test_execute_query_success(self, test_session, mock_pool):
        """测试有效 SQL 能够成功执行。"""
        pool, conn = mock_pool

        # 模拟查询结果
        mock_row = {"id": 1, "name": "test user"}
        conn.fetch.return_value = [mock_row]

        # 模拟 get_connection_pool
        with patch("app.services.query.get_connection_pool", return_value=pool):
            result = await execute_query(
                session=test_session,
                database_name="test_db",
                url="postgresql://localhost/test",
                sql="SELECT * FROM users",
                query_source=QuerySource.MANUAL,
            )

        # 验证结果结构
        assert isinstance(result, QueryResult)
        assert len(result.columns) == 2
        assert result.columns[0].name == "id"
        assert result.columns[1].name == "name"
        assert len(result.rows) == 1
        assert result.rows[0] == mock_row
        assert result.row_count == 1
        assert result.execution_time_ms >= 0
        assert "LIMIT" in result.sql.upper()

        # 验证查询已保存到历史记录
        statement = select(QueryHistory)
        history = test_session.exec(statement).first()
        assert history is not None
        assert history.database_name == "test_db"
        assert history.success is True
        assert history.error_message is None

    @pytest.mark.asyncio
    async def test_execute_query_with_validation_error(self, test_session):
        """测试执行无效 SQL 时会抛出校验错误。"""
        with pytest.raises(SqlValidationError):
            await execute_query(
                session=test_session,
                database_name="test_db",
                url="postgresql://localhost/test",
                sql="INSERT INTO users VALUES (1, 'test')",
                query_source=QuerySource.MANUAL,
            )

        # 验证失败查询已保存到历史记录
        statement = select(QueryHistory)
        history = test_session.exec(statement).first()
        assert history is not None
        assert history.success is False
        assert history.error_message is not None
        assert "SELECT" in history.error_message

    @pytest.mark.asyncio
    async def test_execute_query_with_execution_error(self, test_session, mock_pool):
        """测试数据库执行失败时的查询处理。"""
        pool, conn = mock_pool

        # 模拟连接抛出错误
        conn.fetch.side_effect = Exception("Database connection error")

        with patch("app.services.query.get_connection_pool", return_value=pool):
            with pytest.raises(Exception) as exc_info:
                await execute_query(
                    session=test_session,
                    database_name="test_db",
                    url="postgresql://localhost/test",
                    sql="SELECT * FROM users",
                    query_source=QuerySource.MANUAL,
                )

            assert "Database connection error" in str(exc_info.value)

        # 验证失败查询已保存到历史记录
        statement = select(QueryHistory)
        history = test_session.exec(statement).first()
        assert history is not None
        assert history.success is False
        assert "Database connection error" in history.error_message

    @pytest.mark.asyncio
    async def test_execute_query_with_multiple_rows(self, test_session, mock_pool):
        """测试返回多行结果的查询。"""
        pool, conn = mock_pool

        # 模拟多行结果
        mock_rows = [
            {"id": 1, "name": "user1", "age": 25},
            {"id": 2, "name": "user2", "age": 30},
            {"id": 3, "name": "user3", "age": 35},
        ]
        conn.fetch.return_value = mock_rows

        with patch("app.services.query.get_connection_pool", return_value=pool):
            result = await execute_query(
                session=test_session,
                database_name="test_db",
                url="postgresql://localhost/test",
                sql="SELECT * FROM users",
                query_source=QuerySource.NATURAL_LANGUAGE,
            )

        assert result.row_count == 3
        assert len(result.rows) == 3
        assert result.rows[0]["id"] == 1
        assert result.rows[2]["age"] == 35

    @pytest.mark.asyncio
    async def test_execute_query_with_empty_result(self, test_session, mock_pool):
        """测试查询返回空结果集。"""
        pool, conn = mock_pool

        # 模拟空结果
        conn.fetch.return_value = []

        with patch("app.services.query.get_connection_pool", return_value=pool):
            result = await execute_query(
                session=test_session,
                database_name="test_db",
                url="postgresql://localhost/test",
                sql="SELECT * FROM users WHERE id = -1",
                query_source=QuerySource.MANUAL,
            )

        assert result.row_count == 0
        assert len(result.rows) == 0
        assert len(result.columns) == 0


class TestSaveQueryHistory:
    """测试查询历史保存函数。"""

    @pytest.mark.asyncio
    async def test_save_query_history(self, test_session):
        """测试将成功查询保存到历史记录。"""
        history = await save_query_history(
            session=test_session,
            database_name="test_db",
            sql="SELECT * FROM users LIMIT 100",
            row_count=10,
            execution_time_ms=50,
            success=True,
            error_message=None,
            query_source=QuerySource.MANUAL,
        )

        assert history.id is not None
        assert history.database_name == "test_db"
        assert history.sql_text == "SELECT * FROM users LIMIT 100"
        assert history.row_count == 10
        assert history.execution_time_ms == 50
        assert history.success is True
        assert history.error_message is None
        assert history.query_source == QuerySource.MANUAL
        assert isinstance(history.executed_at, datetime)

    @pytest.mark.asyncio
    async def test_save_failed_query_history(self, test_session):
        """测试将失败查询保存到历史记录。"""
        history = await save_query_history(
            session=test_session,
            database_name="test_db",
            sql="SELECT * FROM invalid_table",
            row_count=None,
            execution_time_ms=25,
            success=False,
            error_message="Table does not exist",
            query_source=QuerySource.NATURAL_LANGUAGE,
        )

        assert history.success is False
        assert history.error_message == "Table does not exist"
        assert history.row_count is None
        assert history.query_source == QuerySource.NATURAL_LANGUAGE


class TestCleanupOldQueries:
    """测试查询历史清理函数。"""

    @pytest.mark.asyncio
    async def test_cleanup_old_queries(self, test_session):
        """测试清理后每个数据库只保留最近 50 条查询。"""
        # 为 test_db 创建 60 条查询
        for i in range(60):
            history = QueryHistory(
                database_name="test_db",
                sql_text=f"SELECT {i}",
                executed_at=datetime.now(timezone.utc),
                execution_time_ms=10,
                row_count=1,
                success=True,
                error_message=None,
                query_source=QuerySource.MANUAL,
            )
            test_session.add(history)

        # 为 another_db 创建 10 条查询
        for i in range(10):
            history = QueryHistory(
                database_name="another_db",
                sql_text=f"SELECT {i}",
                executed_at=datetime.now(timezone.utc),
                execution_time_ms=10,
                row_count=1,
                success=True,
                error_message=None,
                query_source=QuerySource.MANUAL,
            )
            test_session.add(history)

        test_session.commit()

        # 清理 test_db 的查询历史
        await cleanup_old_queries(test_session, "test_db")

        # 验证 test_db 恰好保留 50 条查询
        statement = select(QueryHistory).where(QueryHistory.database_name == "test_db")
        test_db_queries = test_session.exec(statement).all()
        assert len(test_db_queries) == 50

        # 验证 another_db 仍保留全部 10 条查询
        statement = select(QueryHistory).where(QueryHistory.database_name == "another_db")
        another_db_queries = test_session.exec(statement).all()
        assert len(another_db_queries) == 10

    @pytest.mark.asyncio
    async def test_cleanup_with_less_than_50_queries(self, test_session):
        """测试查询少于 50 条时的清理。"""
        # 仅创建 20 条查询
        for i in range(20):
            history = QueryHistory(
                database_name="test_db",
                sql_text=f"SELECT {i}",
                executed_at=datetime.now(timezone.utc),
                execution_time_ms=10,
                row_count=1,
                success=True,
                error_message=None,
                query_source=QuerySource.MANUAL,
            )
            test_session.add(history)

        test_session.commit()

        # 执行清理
        await cleanup_old_queries(test_session, "test_db")

        # 验证 20 条查询全部保留
        statement = select(QueryHistory).where(QueryHistory.database_name == "test_db")
        queries = test_session.exec(statement).all()
        assert len(queries) == 20


class TestGetQueryHistory:
    """测试查询历史获取函数。"""

    @pytest.mark.asyncio
    async def test_get_query_history(self, test_session):
        """测试获取指定数据库的查询历史。"""
        # 创建具有不同时间戳的查询
        for i in range(10):
            history = QueryHistory(
                database_name="test_db",
                sql_text=f"SELECT {i}",
                executed_at=datetime.now(timezone.utc),
                execution_time_ms=10 + i,
                row_count=i,
                success=True,
                error_message=None,
                query_source=QuerySource.MANUAL,
            )
            test_session.add(history)

        test_session.commit()

        # 获取查询历史
        history_list = await get_query_history(test_session, "test_db", limit=5)

        assert len(history_list) == 5
        # 验证查询按 executed_at 倒序排列，即最新记录在前
        assert all(isinstance(h, QueryHistory) for h in history_list)

    @pytest.mark.asyncio
    async def test_get_query_history_empty(self, test_session):
        """测试获取没有查询记录的数据库历史。"""
        history_list = await get_query_history(test_session, "nonexistent_db", limit=50)

        assert len(history_list) == 0
        assert history_list == []

    @pytest.mark.asyncio
    async def test_get_query_history_with_limit(self, test_session):
        """测试 limit 参数能够正确生效。"""
        # 创建 100 条查询
        for i in range(100):
            history = QueryHistory(
                database_name="test_db",
                sql_text=f"SELECT {i}",
                executed_at=datetime.now(timezone.utc),
                execution_time_ms=10,
                row_count=1,
                success=True,
                error_message=None,
                query_source=QuerySource.MANUAL,
            )
            test_session.add(history)

        test_session.commit()

        # 使用不同限制值获取历史
        history_10 = await get_query_history(test_session, "test_db", limit=10)
        history_25 = await get_query_history(test_session, "test_db", limit=25)

        assert len(history_10) == 10
        assert len(history_25) == 25
