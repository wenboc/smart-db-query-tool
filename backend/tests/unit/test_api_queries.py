"""查询 API 端点单元测试。"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from app.main import app
from app.database import get_session
from app.models.database import DatabaseConnection, ConnectionStatus
from app.models.query import QueryHistory, QuerySource
from app.models.metadata import DatabaseMetadata
from app.models.schemas import QueryResult, QueryColumn
from app.services.sql_validator import SqlValidationError
import json


@pytest.fixture
def test_session():
    """创建用于测试的内存 SQLite 会话。"""
    # 导入全部模型，确保创建对应数据表
    from app.models.database import DatabaseConnection
    from app.models.metadata import DatabaseMetadata
    from app.models.query import QueryHistory

    # 使用共享缓存 URI，让多个连接访问同一个内存数据库
    engine = create_engine(
        "sqlite:///file:test_db?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False, "uri": True}
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(test_session):
    """使用测试数据库会话创建 TestClient。"""

    def get_test_session():
        return test_session

    app.dependency_overrides[get_session] = get_test_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_connection(test_session):
    """创建示例数据库连接。"""
    conn = DatabaseConnection(
        name="test_db",
        url="postgresql://user:pass@localhost/testdb",
        description="Test database",
        status=ConnectionStatus.ACTIVE,
        last_connected_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    test_session.add(conn)
    test_session.commit()
    test_session.refresh(conn)
    return conn


@pytest.fixture
def sample_metadata(test_session):
    """创建示例缓存元数据。"""
    metadata_dict = {
        "tables": [
            {
                "name": "users",
                "type": "table",
                "schemaName": "public",
                "rowCount": 100,
                "columns": [
                    {
                        "name": "id",
                        "dataType": "integer",
                        "nullable": False,
                        "primaryKey": True,
                        "unique": False,
                        "defaultValue": None,
                    }
                ],
            }
        ],
        "views": [],
    }
    cached = DatabaseMetadata(
        database_name="test_db",
        metadata_json=json.dumps(metadata_dict),
        fetched_at=datetime.now(timezone.utc).replace(tzinfo=None),
        table_count=1,
    )
    test_session.add(cached)
    test_session.commit()
    return metadata_dict


class TestExecuteSqlQuery:
    """测试 SQL 查询执行端点。"""

    @patch("app.api.v1.queries.execute_query")
    def test_execute_sql_query_success(self, mock_execute, client, sample_connection):
        """测试成功执行 SQL 查询。"""
        # 模拟查询结果
        mock_result = QueryResult(
            columns=[
                QueryColumn(name="id", dataType="integer"),
                QueryColumn(name="name", dataType="character varying"),
            ],
            rows=[
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ],
            rowCount=2,
            executionTimeMs=25,
            sql="SELECT * FROM users LIMIT 100",
        )
        mock_execute.return_value = mock_result

        response = client.post(
            "/api/v1/dbs/test_db/query",
            json={"sql": "SELECT * FROM users"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["columns"]) == 2
        assert data["columns"][0]["name"] == "id"
        assert data["rowCount"] == 2
        assert len(data["rows"]) == 2
        assert data["rows"][0]["name"] == "Alice"
        assert data["executionTimeMs"] == 25

        # 验证 execute_query 接收到正确参数
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]  # Positional args
        # 参数：session、database_name、url、sql、query_source
        assert call_args[1] == "test_db"  # database_name
        assert call_args[3] == "SELECT * FROM users"  # sql
        assert call_args[4] == QuerySource.MANUAL  # query_source

    def test_execute_sql_query_database_not_found(self, client):
        """测试数据库不存在时执行查询。"""
        response = client.post(
            "/api/v1/dbs/nonexistent/query",
            json={"sql": "SELECT * FROM users"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("app.api.v1.queries.execute_query")
    def test_execute_sql_query_validation_error(self, mock_execute, client, sample_connection):
        """测试发生 SQL 校验错误时执行查询。"""
        # 模拟校验错误
        mock_execute.side_effect = SqlValidationError("Only SELECT queries are allowed")

        response = client.post(
            "/api/v1/dbs/test_db/query",
            json={"sql": "INSERT INTO users VALUES (1, 'test')"},
        )

        assert response.status_code == 400
        assert "Only SELECT queries are allowed" in response.json()["detail"]

    @patch("app.api.v1.queries.execute_query")
    def test_execute_sql_query_execution_error(self, mock_execute, client, sample_connection):
        """测试发生数据库错误时执行查询。"""
        # 模拟执行错误
        mock_execute.side_effect = Exception("Table does not exist")

        response = client.post(
            "/api/v1/dbs/test_db/query",
            json={"sql": "SELECT * FROM invalid_table"},
        )

        assert response.status_code == 500
        assert "Query execution failed" in response.json()["detail"]
        assert "Table does not exist" in response.json()["detail"]

    @patch("app.api.v1.queries.execute_query")
    def test_execute_sql_query_empty_result(self, mock_execute, client, sample_connection):
        """测试查询返回空结果集。"""
        # 模拟空结果
        mock_result = QueryResult(
            columns=[],
            rows=[],
            rowCount=0,
            executionTimeMs=10,
            sql="SELECT * FROM users WHERE id = -1 LIMIT 100",
        )
        mock_execute.return_value = mock_result

        response = client.post(
            "/api/v1/dbs/test_db/query",
            json={"sql": "SELECT * FROM users WHERE id = -1"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rowCount"] == 0
        assert len(data["rows"]) == 0

    def test_execute_sql_query_missing_sql(self, client, sample_connection):
        """测试缺少 SQL 参数时执行查询。"""
        response = client.post(
            "/api/v1/dbs/test_db/query",
            json={},
        )

        assert response.status_code == 422  # Validation error


class TestGetQueryHistory:
    """测试查询历史获取端点。"""

    def test_get_query_history(self, client, sample_connection, test_session):
        """测试获取指定数据库的查询历史。"""
        # 创建若干历史条目
        for i in range(5):
            history = QueryHistory(
                database_name="test_db",
                sql_text=f"SELECT {i} FROM users",
                executed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                execution_time_ms=10 + i,
                row_count=i * 10,
                success=True,
                error_message=None,
                query_source=QuerySource.MANUAL,
            )
            test_session.add(history)

        test_session.commit()

        response = client.get("/api/v1/dbs/test_db/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
        assert all("id" in entry for entry in data)
        assert all("sqlText" in entry for entry in data)
        assert all("executedAt" in entry for entry in data)
        assert data[0]["databaseName"] == "test_db"

    def test_get_query_history_with_limit(self, client, sample_connection, test_session):
        """测试使用自定义限制值获取查询历史。"""
        # 创建 20 条历史记录
        for i in range(20):
            history = QueryHistory(
                database_name="test_db",
                sql_text=f"SELECT {i}",
                executed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                execution_time_ms=10,
                row_count=10,
                success=True,
                error_message=None,
                query_source=QuerySource.MANUAL,
            )
            test_session.add(history)

        test_session.commit()

        response = client.get("/api/v1/dbs/test_db/history?limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 10

    def test_get_query_history_empty(self, client, sample_connection):
        """测试没有查询记录时获取历史。"""
        response = client.get("/api/v1/dbs/test_db/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0
        assert data == []

    def test_get_query_history_database_not_found(self, client):
        """测试获取不存在数据库的查询历史。"""
        response = client.get("/api/v1/dbs/nonexistent/history")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_query_history_includes_errors(self, client, sample_connection, test_session):
        """测试历史记录同时包含成功和失败的查询。"""
        # 创建成功查询
        success_history = QueryHistory(
            database_name="test_db",
            sql_text="SELECT * FROM users",
            executed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            execution_time_ms=20,
            row_count=10,
            success=True,
            error_message=None,
            query_source=QuerySource.MANUAL,
        )
        test_session.add(success_history)

        # 创建失败查询
        failed_history = QueryHistory(
            database_name="test_db",
            sql_text="SELECT * FROM invalid_table",
            executed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            execution_time_ms=5,
            row_count=None,
            success=False,
            error_message="Table does not exist",
            query_source=QuerySource.NATURAL_LANGUAGE,
        )
        test_session.add(failed_history)

        test_session.commit()

        response = client.get("/api/v1/dbs/test_db/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # 在结果中查找失败查询
        failed = next(entry for entry in data if not entry["success"])
        assert failed["errorMessage"] == "Table does not exist"
        assert failed["rowCount"] is None
        assert failed["querySource"] == "natural_language"


class TestNaturalLanguageToSql:
    """测试自然语言转 SQL 端点。"""

    @patch("app.api.v1.queries.nl2sql_service.generate_sql")
    def test_natural_language_to_sql(self, mock_generate, client, sample_connection, sample_metadata):
        """测试将自然语言转换为 SQL。"""
        # 模拟 SQL 生成
        mock_generate.return_value = {
            "sql": "SELECT * FROM public.users LIMIT 100",
            "explanation": "Generated SQL from: Show me all users",
        }

        response = client.post(
            "/api/v1/dbs/test_db/query/natural",
            json={"prompt": "Show me all users"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sql"] == "SELECT * FROM public.users LIMIT 100"
        assert "explanation" in data
        assert "Show me all users" in data["explanation"]

        # 验证已调用 generate_sql
        mock_generate.assert_called_once_with(
            "Show me all users",
            sample_metadata,
        )

    def test_natural_language_to_sql_database_not_found(self, client):
        """测试数据库不存在时执行自然语言转 SQL。"""
        response = client.post(
            "/api/v1/dbs/nonexistent/query/natural",
            json={"prompt": "Show all data"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_natural_language_to_sql_no_metadata(self, client, sample_connection):
        """测试元数据不存在时执行自然语言转 SQL。"""
        response = client.post(
            "/api/v1/dbs/test_db/query/natural",
            json={"prompt": "Show me all users"},
        )

        assert response.status_code == 404
        assert "Metadata not found" in response.json()["detail"]
        assert "refresh metadata" in response.json()["detail"]

    @patch("app.api.v1.queries.nl2sql_service.generate_sql")
    def test_natural_language_to_sql_generation_error(self, mock_generate, client, sample_connection, sample_metadata):
        """测试自然语言转 SQL 生成失败。"""
        # 模拟生成错误
        mock_generate.side_effect = Exception("OpenAI API error")

        response = client.post(
            "/api/v1/dbs/test_db/query/natural",
            json={"prompt": "Show me all users"},
        )

        assert response.status_code == 500
        assert "Failed to generate SQL" in response.json()["detail"]

    def test_natural_language_to_sql_short_prompt(self, client, sample_connection):
        """测试使用过短提示词执行自然语言转 SQL。"""
        response = client.post(
            "/api/v1/dbs/test_db/query/natural",
            json={"prompt": "test"},
        )

        # 应因 min_length=5 而校验失败
        assert response.status_code == 422

    def test_natural_language_to_sql_long_prompt(self, client, sample_connection):
        """测试使用过长提示词执行自然语言转 SQL。"""
        response = client.post(
            "/api/v1/dbs/test_db/query/natural",
            json={"prompt": "a" * 501},
        )

        # 应因 max_length=500 而校验失败
        assert response.status_code == 422

    @patch("app.api.v1.queries.nl2sql_service.generate_sql")
    def test_natural_language_to_sql_chinese(self, mock_generate, client, sample_connection, sample_metadata):
        """测试使用中文提示词执行自然语言转 SQL。"""
        # 模拟 SQL 生成
        mock_generate.return_value = {
            "sql": "SELECT * FROM public.users LIMIT 100",
            "explanation": "Generated SQL from: 显示所有用户",
        }

        response = client.post(
            "/api/v1/dbs/test_db/query/natural",
            json={"prompt": "显示所有用户"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "sql" in data
        assert "explanation" in data


class TestQueryHistoryEntry:
    """测试查询历史条目模型转换。"""

    def test_to_history_entry(self, test_session):
        """测试将 QueryHistory 转换为 QueryHistoryEntry 模型。"""
        from app.api.v1.queries import to_history_entry

        # 创建查询历史条目
        history = QueryHistory(
            database_name="test_db",
            sql_text="SELECT * FROM users",
            executed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            execution_time_ms=25,
            row_count=10,
            success=True,
            error_message=None,
            query_source=QuerySource.MANUAL,
        )
        test_session.add(history)
        test_session.commit()
        test_session.refresh(history)

        entry = to_history_entry(history)

        assert entry.id == history.id
        assert entry.database_name == "test_db"
        assert entry.sql_text == "SELECT * FROM users"
        assert entry.execution_time_ms == 25
        assert entry.row_count == 10
        assert entry.success is True
        assert entry.error_message is None
        assert entry.query_source == "manual"

    def test_to_history_entry_failed_query(self, test_session):
        """测试转换失败查询的历史记录。"""
        from app.api.v1.queries import to_history_entry

        history = QueryHistory(
            database_name="test_db",
            sql_text="SELECT * FROM invalid",
            executed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            execution_time_ms=5,
            row_count=None,
            success=False,
            error_message="Table not found",
            query_source=QuerySource.NATURAL_LANGUAGE,
        )
        test_session.add(history)
        test_session.commit()
        test_session.refresh(history)

        entry = to_history_entry(history)

        assert entry.success is False
        assert entry.error_message == "Table not found"
        assert entry.row_count is None
        assert entry.query_source == "natural_language"
