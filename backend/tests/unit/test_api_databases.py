"""数据库 API 端点单元测试。"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from app.main import app
from app.database import get_session
from app.models.database import DatabaseConnection, ConnectionStatus
from app.models.metadata import DatabaseMetadata
from app.models.query import QueryHistory, QuerySource
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


class TestCreateDatabaseConnection:
    """测试创建数据库连接。"""

    @patch("app.api.v1.databases.test_connection")
    def test_create_database_connection(self, mock_test_conn, client):
        """测试成功创建新的数据库连接。"""
        # 模拟连接测试成功
        mock_test_conn.return_value = (True, None)

        response = client.put(
            "/api/v1/dbs/my_database",
            json={
                "url": "postgresql://user:pass@localhost/mydb",
                "description": "My test database",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "my_database"
        assert data["url"] == "postgresql://user:pass@localhost/mydb"
        assert data["description"] == "My test database"
        assert data["status"] == "active"
        assert "createdAt" in data
        assert "updatedAt" in data

        # 验证已调用 test_connection
        mock_test_conn.assert_called_once_with("postgresql://user:pass@localhost/mydb")

    @patch("app.api.v1.databases.test_connection")
    def test_create_database_connection_invalid_name(self, mock_test_conn, client):
        """测试无效数据库名称会被拒绝。"""
        response = client.put(
            "/api/v1/dbs/invalid@name!",
            json={"url": "postgresql://localhost/test"},
        )

        assert response.status_code == 400
        assert "alphanumeric" in response.json()["detail"]

    @patch("app.api.v1.databases.test_connection")
    def test_create_database_connection_test_fails(self, mock_test_conn, client):
        """测试连接测试失败时无法创建连接。"""
        # 模拟连接测试失败
        mock_test_conn.return_value = (False, "Connection refused")

        response = client.put(
            "/api/v1/dbs/failing_db",
            json={"url": "postgresql://localhost/baddb"},
        )

        assert response.status_code == 400
        assert "Connection test failed" in response.json()["detail"]
        assert "Connection refused" in response.json()["detail"]

    @patch("app.api.v1.databases.test_connection")
    def test_update_existing_database_connection(self, mock_test_conn, client, sample_connection):
        """测试更新现有数据库连接。"""
        # 模拟连接测试成功
        mock_test_conn.return_value = (True, None)

        response = client.put(
            "/api/v1/dbs/test_db",
            json={
                "url": "postgresql://newuser:newpass@localhost/newdb",
                "description": "Updated description",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test_db"
        assert data["url"] == "postgresql://newuser:newpass@localhost/newdb"
        assert data["description"] == "Updated description"

    @patch("app.api.v1.databases.test_connection")
    def test_create_database_connection_with_hyphen_underscore(self, mock_test_conn, client):
        """测试名称允许包含连字符和下划线。"""
        mock_test_conn.return_value = (True, None)

        response = client.put(
            "/api/v1/dbs/test-db_name",
            json={"url": "postgresql://localhost/test"},
        )

        assert response.status_code == 200


class TestListDatabases:
    """测试列出数据库连接。"""

    def test_list_databases(self, client, sample_connection):
        """测试列出全部数据库连接。"""
        # 创建另一个连接
        conn2 = DatabaseConnection(
            name="another_db",
            url="postgresql://localhost/another",
            description="Another database",
            status=ConnectionStatus.ACTIVE,
        )
        client.app.dependency_overrides[get_session]().add(conn2)
        client.app.dependency_overrides[get_session]().commit()

        response = client.get("/api/v1/dbs")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert any(db["name"] == "test_db" for db in data)
        assert any(db["name"] == "another_db" for db in data)

    def test_list_databases_empty(self, client):
        """测试不存在连接时列出数据库。"""
        response = client.get("/api/v1/dbs")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0
        assert data == []


class TestGetDatabaseMetadata:
    """测试获取数据库元数据。"""

    @patch("app.api.v1.databases.fetch_metadata")
    def test_get_database_metadata(self, mock_fetch, client, sample_connection):
        """测试获取数据库元数据。"""
        # 模拟元数据响应
        mock_metadata = {
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
        mock_fetch.return_value = mock_metadata

        # 创建缓存元数据
        cached = DatabaseMetadata(
            database_name="test_db",
            metadata_json=json.dumps(mock_metadata),
            fetched_at=datetime.now(timezone.utc).replace(tzinfo=None),
            table_count=1,
        )
        client.app.dependency_overrides[get_session]().add(cached)
        client.app.dependency_overrides[get_session]().commit()

        response = client.get("/api/v1/dbs/test_db")

        assert response.status_code == 200
        data = response.json()
        assert data["databaseName"] == "test_db"
        assert len(data["tables"]) == 1
        assert data["tables"][0]["name"] == "users"
        assert len(data["views"]) == 0
        assert "fetchedAt" in data
        assert "isStale" in data

    def test_get_database_metadata_not_found(self, client):
        """测试获取不存在数据库的元数据。"""
        response = client.get("/api/v1/dbs/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("app.api.v1.databases.fetch_metadata")
    def test_get_database_metadata_with_refresh(self, mock_fetch, client, sample_connection):
        """测试强制刷新后获取元数据。"""
        mock_metadata = {"tables": [], "views": []}
        mock_fetch.return_value = mock_metadata

        # 创建缓存元数据
        cached = DatabaseMetadata(
            database_name="test_db",
            metadata_json=json.dumps(mock_metadata),
            fetched_at=datetime.now(timezone.utc).replace(tzinfo=None),
            table_count=0,
        )
        client.app.dependency_overrides[get_session]().add(cached)
        client.app.dependency_overrides[get_session]().commit()

        response = client.get("/api/v1/dbs/test_db?refresh=true")

        assert response.status_code == 200
        # 验证 force_refresh 已传给 fetch_metadata
        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args[1]
        assert call_args["force_refresh"] is True


class TestDeleteDatabase:
    """测试删除数据库连接。"""

    @patch("app.api.v1.databases.close_connection_pool")
    def test_delete_database(self, mock_close_pool, client, sample_connection):
        """测试删除数据库连接。"""
        response = client.delete("/api/v1/dbs/test_db")

        assert response.status_code == 204

        # 验证连接池已关闭
        mock_close_pool.assert_called_once_with("test_db")

        # 验证数据库连接记录已删除
        get_response = client.get("/api/v1/dbs")
        databases = get_response.json()
        assert len(databases) == 0

    def test_delete_database_not_found(self, client):
        """测试删除不存在的数据库连接。"""
        response = client.delete("/api/v1/dbs/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestRefreshDatabaseMetadata:
    """测试刷新数据库元数据。"""

    @patch("app.api.v1.databases.fetch_metadata")
    def test_refresh_database_metadata(self, mock_fetch, client, sample_connection):
        """测试强制刷新元数据。"""
        # 模拟最新元数据
        fresh_metadata = {
            "tables": [
                {
                    "name": "new_table",
                    "type": "table",
                    "schemaName": "public",
                    "columns": [],
                }
            ],
            "views": [],
        }
        mock_fetch.return_value = fresh_metadata

        # 创建缓存元数据
        old_metadata = {"tables": [], "views": []}
        cached = DatabaseMetadata(
            database_name="test_db",
            metadata_json=json.dumps(old_metadata),
            fetched_at=(datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None),
            table_count=0,
        )
        client.app.dependency_overrides[get_session]().add(cached)
        client.app.dependency_overrides[get_session]().commit()

        response = client.post("/api/v1/dbs/test_db/refresh")

        assert response.status_code == 200
        data = response.json()
        assert data["databaseName"] == "test_db"
        assert len(data["tables"]) == 1
        assert data["tables"][0]["name"] == "new_table"
        assert data["isStale"] is False

        # 验证已使用 force_refresh
        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args[1]
        assert call_args["force_refresh"] is True

    def test_refresh_database_metadata_not_found(self, client):
        """测试刷新不存在数据库的元数据。"""
        response = client.post("/api/v1/dbs/nonexistent/refresh")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestDatabaseResponseSchema:
    """测试数据库响应模型转换。"""

    def test_to_response(self, sample_connection):
        """测试将 DatabaseConnection 转换为响应模型。"""
        from app.api.v1.databases import to_response

        response = to_response(sample_connection)

        assert response.name == "test_db"
        assert response.url == "postgresql://user:pass@localhost/testdb"
        assert response.description == "Test database"
        assert response.status == "active"
        assert isinstance(response.created_at, datetime)
        assert isinstance(response.updated_at, datetime)
        assert isinstance(response.last_connected_at, datetime)
