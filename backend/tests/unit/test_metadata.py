"""元数据提取服务单元测试。"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, SQLModel, create_engine, select
from app.services.metadata import (
    extract_postgres_metadata,
    get_cached_metadata,
    cache_metadata,
    fetch_metadata,
)
from app.models.metadata import DatabaseMetadata


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


@pytest.fixture
def sample_metadata():
    """示例元数据字典。"""
    return {
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
                    },
                    {
                        "name": "name",
                        "dataType": "character varying",
                        "nullable": False,
                        "primaryKey": False,
                        "unique": False,
                        "defaultValue": None,
                    },
                ],
            }
        ],
        "views": [
            {
                "name": "user_summary",
                "type": "view",
                "schemaName": "public",
                "columns": [
                    {
                        "name": "total_users",
                        "dataType": "bigint",
                        "nullable": True,
                        "primaryKey": False,
                        "unique": False,
                        "defaultValue": None,
                    }
                ],
            }
        ],
    }


class TestExtractMetadata:
    """测试从 PostgreSQL 提取元数据。"""

    @pytest.mark.asyncio
    async def test_extract_metadata_tables(self, mock_pool):
        """测试从数据库提取表元数据。"""
        pool, conn = mock_pool

        # 模拟表查询结果
        conn.fetch.side_effect = [
            # 表查询
            [
                {"schemaname": "public", "tablename": "users", "type": "table"},
                {"schemaname": "public", "tablename": "orders", "type": "table"},
            ],
            # users 表的列
            [
                {
                    "column_name": "id",
                    "data_type": "integer",
                    "character_maximum_length": None,
                    "is_nullable": "NO",
                    "column_default": "nextval('users_id_seq'::regclass)",
                    "ordinal_position": 1,
                    "is_primary_key": True,
                    "is_unique": False,
                },
                {
                    "column_name": "email",
                    "data_type": "character varying",
                    "character_maximum_length": 255,
                    "is_nullable": "NO",
                    "column_default": None,
                    "ordinal_position": 2,
                    "is_primary_key": False,
                    "is_unique": True,
                },
            ],
            # orders 表的列
            [
                {
                    "column_name": "id",
                    "data_type": "integer",
                    "character_maximum_length": None,
                    "is_nullable": "NO",
                    "column_default": None,
                    "ordinal_position": 1,
                    "is_primary_key": True,
                    "is_unique": False,
                },
            ],
        ]

        # 模拟行数查询，asyncpg 返回支持索引访问的 Record 对象
        # 被测代码访问 count_result[0]，因此这里需要返回类似元组的对象
        mock_row_1 = MagicMock()
        mock_row_1.__getitem__ = lambda self, idx: 100
        mock_row_2 = MagicMock()
        mock_row_2.__getitem__ = lambda self, idx: 50
        conn.fetchrow.side_effect = [
            mock_row_1,  # users count
            mock_row_2,  # orders count
        ]

        metadata = await extract_postgres_metadata("test_db", pool)

        assert "tables" in metadata
        assert "views" in metadata
        assert len(metadata["tables"]) == 2

        # 检查第一张表
        users_table = metadata["tables"][0]
        assert users_table["name"] == "users"
        assert users_table["type"] == "table"
        assert users_table["schemaName"] == "public"
        assert users_table["rowCount"] == 100
        assert len(users_table["columns"]) == 2

        # 检查列元数据
        id_column = users_table["columns"][0]
        assert id_column["name"] == "id"
        assert id_column["dataType"] == "integer"
        assert id_column["nullable"] is False
        assert id_column["primaryKey"] is True

        email_column = users_table["columns"][1]
        assert email_column["name"] == "email"
        assert email_column["dataType"] == "character varying(255)"
        assert email_column["unique"] is True

    @pytest.mark.asyncio
    async def test_extract_metadata_with_views(self, mock_pool):
        """测试从数据库提取视图元数据。"""
        pool, conn = mock_pool

        # 模拟包含视图的表查询结果
        conn.fetch.side_effect = [
            # 表查询
            [
                {"schemaname": "public", "tablename": "user_stats", "type": "view"},
            ],
            # 视图的列
            [
                {
                    "column_name": "total",
                    "data_type": "bigint",
                    "character_maximum_length": None,
                    "is_nullable": "YES",
                    "column_default": None,
                    "ordinal_position": 1,
                    "is_primary_key": False,
                    "is_unique": False,
                },
            ],
        ]

        metadata = await extract_postgres_metadata("test_db", pool)

        assert len(metadata["views"]) == 1
        assert len(metadata["tables"]) == 0

        view = metadata["views"][0]
        assert view["name"] == "user_stats"
        assert view["type"] == "view"
        assert "rowCount" not in view  # Views don't have row counts

    @pytest.mark.asyncio
    async def test_extract_metadata_handles_count_errors(self, mock_pool):
        """测试元数据提取能够妥善处理行数统计错误。"""
        pool, conn = mock_pool

        # 模拟表查询
        conn.fetch.side_effect = [
            [{"schemaname": "public", "tablename": "test_table", "type": "table"}],
            [  # Columns
                {
                    "column_name": "id",
                    "data_type": "integer",
                    "character_maximum_length": None,
                    "is_nullable": "NO",
                    "column_default": None,
                    "ordinal_position": 1,
                    "is_primary_key": True,
                    "is_unique": False,
                },
            ],
        ]

        # 模拟行数统计抛出错误
        conn.fetchrow.side_effect = Exception("Permission denied")

        metadata = await extract_postgres_metadata("test_db", pool)

        # 应继续返回元数据，但不包含行数
        assert len(metadata["tables"]) == 1
        table = metadata["tables"][0]
        assert "rowCount" not in table or table["rowCount"] is None


class TestGetCachedMetadata:
    """测试缓存元数据获取。"""

    @pytest.mark.asyncio
    async def test_get_cached_metadata_returns_fresh(self, test_session, sample_metadata):
        """测试缓存会返回尚未过期的元数据。"""
        # 创建刚获取的最新元数据
        cached = DatabaseMetadata(
            database_name="test_db",
            metadata_json=json.dumps(sample_metadata),
            fetched_at=datetime.now(timezone.utc).replace(tzinfo=None),
            table_count=2,
        )
        test_session.add(cached)
        test_session.commit()

        result = await get_cached_metadata(test_session, "test_db")

        assert result is not None
        assert result.database_name == "test_db"
        assert result.is_stale is False

    @pytest.mark.asyncio
    async def test_get_cached_metadata_returns_none_when_stale(self, test_session, sample_metadata):
        """测试缓存元数据过期时返回 None。"""
        # 创建 25 小时前获取的过期元数据，默认缓存时间为 24 小时
        stale_time = (datetime.now(timezone.utc) - timedelta(hours=25)).replace(tzinfo=None)
        cached = DatabaseMetadata(
            database_name="test_db",
            metadata_json=json.dumps(sample_metadata),
            fetched_at=stale_time,
            table_count=2,
        )
        test_session.add(cached)
        test_session.commit()

        result = await get_cached_metadata(test_session, "test_db")

        # 缓存已过期，因此应返回 None
        assert result is None or result.is_stale is True

    @pytest.mark.asyncio
    async def test_get_cached_metadata_returns_none_when_not_exists(self, test_session):
        """测试缓存不存在时返回 None。"""
        result = await get_cached_metadata(test_session, "nonexistent_db")

        assert result is None


class TestCacheMetadata:
    """测试元数据缓存。"""

    @pytest.mark.asyncio
    async def test_cache_metadata_creates_new(self, test_session, sample_metadata):
        """测试创建新的元数据缓存条目。"""
        result = await cache_metadata(test_session, "test_db", sample_metadata)

        assert result.database_name == "test_db"
        assert result.table_count == 2  # 1 table + 1 view
        assert isinstance(result.fetched_at, datetime)

        # 验证已存储的 JSON
        stored_metadata = json.loads(result.metadata_json)
        assert stored_metadata == sample_metadata

        # 验证记录已写入数据库
        statement = select(DatabaseMetadata).where(DatabaseMetadata.database_name == "test_db")
        cached = test_session.exec(statement).first()
        assert cached is not None

    @pytest.mark.asyncio
    async def test_cache_metadata_updates_existing(self, test_session, sample_metadata):
        """测试更新现有元数据缓存。"""
        # 创建初始缓存
        old_metadata = {"tables": [], "views": []}
        initial = DatabaseMetadata(
            database_name="test_db",
            metadata_json=json.dumps(old_metadata),
            fetched_at=(datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None),
            table_count=0,
        )
        test_session.add(initial)
        test_session.commit()
        old_id = initial.id

        # 更新缓存
        result = await cache_metadata(test_session, "test_db", sample_metadata)

        # 更新后 ID 应保持不变，而不是新建记录
        assert result.id == old_id
        assert result.table_count == 2
        assert json.loads(result.metadata_json) == sample_metadata

        # 验证只有一条记录
        statement = select(DatabaseMetadata).where(DatabaseMetadata.database_name == "test_db")
        all_entries = test_session.exec(statement).all()
        assert len(all_entries) == 1


class TestFetchMetadata:
    """测试带缓存的元数据获取。"""

    @pytest.mark.asyncio
    async def test_fetch_metadata_uses_cache(self, test_session, sample_metadata):
        """测试存在未过期缓存时会直接使用缓存。"""
        # 创建未过期缓存
        cached = DatabaseMetadata(
            database_name="test_db",
            metadata_json=json.dumps(sample_metadata),
            fetched_at=datetime.now(timezone.utc).replace(tzinfo=None),
            table_count=2,
        )
        test_session.add(cached)
        test_session.commit()

        # 模拟 get_connection_pool，确保不会调用
        with patch("app.services.metadata.get_connection_pool") as mock_pool:
            result = await fetch_metadata(
                test_session,
                "test_db",
                "postgresql://localhost/test",
                force_refresh=False,
            )

            # 不应调用 get_connection_pool
            mock_pool.assert_not_called()

        assert result == sample_metadata

    @pytest.mark.asyncio
    async def test_fetch_metadata_refreshes_when_stale(self, test_session, sample_metadata, mock_pool):
        """测试缓存过期时会重新获取元数据。"""
        pool, conn = mock_pool

        # 创建过期缓存
        stale_time = (datetime.now(timezone.utc) - timedelta(hours=25)).replace(tzinfo=None)
        cached = DatabaseMetadata(
            database_name="test_db",
            metadata_json=json.dumps({"tables": [], "views": []}),
            fetched_at=stale_time,
            table_count=0,
        )
        test_session.add(cached)
        test_session.commit()

        # 模拟 extract_metadata
        with patch("app.services.metadata.get_connection_pool", return_value=pool):
            with patch("app.services.metadata.extract_postgres_metadata", return_value=sample_metadata) as mock_extract:
                result = await fetch_metadata(
                    test_session,
                    "test_db",
                    "postgresql://localhost/test",
                    force_refresh=False,
                )

                # 应调用 extract_metadata
                mock_extract.assert_called_once()

        assert result == sample_metadata

    @pytest.mark.asyncio
    async def test_fetch_metadata_force_refresh(self, test_session, sample_metadata, mock_pool):
        """测试 force_refresh 会绕过缓存。"""
        pool, conn = mock_pool

        # 创建未过期缓存
        cached = DatabaseMetadata(
            database_name="test_db",
            metadata_json=json.dumps({"tables": [], "views": []}),
            fetched_at=datetime.now(timezone.utc).replace(tzinfo=None),
            table_count=0,
        )
        test_session.add(cached)
        test_session.commit()

        # 模拟 extract_metadata
        with patch("app.services.metadata.get_connection_pool", return_value=pool):
            with patch("app.services.metadata.extract_postgres_metadata", return_value=sample_metadata) as mock_extract:
                result = await fetch_metadata(
                    test_session,
                    "test_db",
                    "postgresql://localhost/test",
                    force_refresh=True,
                )

                # 即使缓存未过期也应调用 extract_metadata
                mock_extract.assert_called_once()

        assert result == sample_metadata

    @pytest.mark.asyncio
    async def test_fetch_metadata_no_cache(self, test_session, sample_metadata, mock_pool):
        """测试缓存不存在时获取元数据。"""
        pool, conn = mock_pool

        # 模拟 extract_metadata
        with patch("app.services.metadata.get_connection_pool", return_value=pool):
            with patch("app.services.metadata.extract_postgres_metadata", return_value=sample_metadata) as mock_extract:
                result = await fetch_metadata(
                    test_session,
                    "test_db",
                    "postgresql://localhost/test",
                    force_refresh=False,
                )

                # 应调用 extract_metadata
                mock_extract.assert_called_once()

        assert result == sample_metadata

        # 验证已创建缓存
        statement = select(DatabaseMetadata).where(DatabaseMetadata.database_name == "test_db")
        cached = test_session.exec(statement).first()
        assert cached is not None
        assert json.loads(cached.metadata_json) == sample_metadata
