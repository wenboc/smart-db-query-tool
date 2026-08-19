"""自然语言转 SQL 服务单元测试。"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.nl2sql import NaturalLanguageToSQLService


@pytest.fixture
def nl2sql_service():
    """创建 NaturalLanguageToSQLService 实例。"""
    return NaturalLanguageToSQLService()


@pytest.fixture
def sample_metadata():
    """示例数据库元数据。"""
    return {
        "tables": [
            {
                "name": "users",
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
                    {
                        "name": "email",
                        "dataType": "character varying",
                        "nullable": False,
                        "primaryKey": False,
                        "unique": True,
                        "defaultValue": None,
                    },
                ],
            },
            {
                "name": "orders",
                "schemaName": "public",
                "rowCount": 500,
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
                        "name": "user_id",
                        "dataType": "integer",
                        "nullable": False,
                        "primaryKey": False,
                        "unique": False,
                        "defaultValue": None,
                    },
                    {
                        "name": "total",
                        "dataType": "numeric",
                        "nullable": False,
                        "primaryKey": False,
                        "unique": False,
                        "defaultValue": None,
                    },
                ],
            },
        ],
        "views": [
            {
                "name": "user_summary",
                "schemaName": "public",
                "columns": [
                    {"name": "total_users", "dataType": "bigint"},
                ],
            }
        ],
    }


class TestGenerateSql:
    """测试根据自然语言生成 SQL。"""

    @pytest.mark.asyncio
    async def test_generate_sql_basic_query(self, nl2sql_service, sample_metadata):
        """测试根据基础自然语言查询生成 SQL。"""
        # 模拟 OpenAI 响应
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="SELECT * FROM public.users LIMIT 100"
                )
            )
        ]

        with patch.object(
            nl2sql_service.client.chat.completions,
            "create",
            new=AsyncMock(return_value=mock_response),
        ) as mock_create:
            result = await nl2sql_service.generate_sql(
                user_prompt="Show me all users",
                metadata=sample_metadata,
            )

            # 验证已调用 OpenAI
            mock_create.assert_called_once()
            call_args = mock_create.call_args

            # 验证结果结构
            assert "sql" in result
            assert "explanation" in result
            assert result["sql"] == "SELECT * FROM public.users LIMIT 100"
            assert "Show me all users" in result["explanation"]

            # 验证 OpenAI 调用参数
            assert call_args.kwargs["model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_generate_sql_removes_markdown(self, nl2sql_service, sample_metadata):
        """测试生成的 SQL 会移除 Markdown 代码块。"""
        # 模拟包含 Markdown 的 OpenAI 响应
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="```sql\nSELECT * FROM public.users LIMIT 100\n```"
                )
            )
        ]

        with patch.object(
            nl2sql_service.client.chat.completions,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await nl2sql_service.generate_sql(
                user_prompt="Show me all users",
                metadata=sample_metadata,
            )

            # 应已移除 Markdown 标记
            assert result["sql"] == "SELECT * FROM public.users LIMIT 100"
            assert "```" not in result["sql"]

    @pytest.mark.asyncio
    async def test_generate_sql_removes_generic_markdown(self, nl2sql_service, sample_metadata):
        """测试移除通用 Markdown 代码块。"""
        # 模拟包含通用 Markdown 代码块的 OpenAI 响应
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="```\nSELECT id, name FROM public.users WHERE id > 10 LIMIT 50\n```"
                )
            )
        ]

        with patch.object(
            nl2sql_service.client.chat.completions,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await nl2sql_service.generate_sql(
                user_prompt="Get users with id greater than 10",
                metadata=sample_metadata,
            )

            assert result["sql"] == "SELECT id, name FROM public.users WHERE id > 10 LIMIT 50"
            assert "```" not in result["sql"]

    @pytest.mark.asyncio
    async def test_generate_sql_with_chinese_prompt(self, nl2sql_service, sample_metadata):
        """测试根据中文自然语言生成 SQL。"""
        # 模拟 OpenAI 响应
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="SELECT * FROM public.users LIMIT 100"
                )
            )
        ]

        with patch.object(
            nl2sql_service.client.chat.completions,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await nl2sql_service.generate_sql(
                user_prompt="显示所有用户",
                metadata=sample_metadata,
            )

            assert "sql" in result
            assert result["sql"] == "SELECT * FROM public.users LIMIT 100"

    @pytest.mark.asyncio
    async def test_generate_sql_with_join(self, nl2sql_service, sample_metadata):
        """测试生成带 JOIN 的 SQL。"""
        # 模拟包含 JOIN 的 OpenAI 响应
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="SELECT u.name, o.total FROM public.users u JOIN public.orders o ON u.id = o.user_id LIMIT 100"
                )
            )
        ]

        with patch.object(
            nl2sql_service.client.chat.completions,
            "create",
            new=AsyncMock(return_value=mock_response),
        ):
            result = await nl2sql_service.generate_sql(
                user_prompt="Show me users with their orders",
                metadata=sample_metadata,
            )

            assert "JOIN" in result["sql"]
            assert "users" in result["sql"]
            assert "orders" in result["sql"]

    @pytest.mark.asyncio
    async def test_generate_sql_handles_api_error(self, nl2sql_service, sample_metadata):
        """测试 API 错误会被正确抛出。"""
        # 模拟 OpenAI 抛出错误
        with patch.object(
            nl2sql_service.client.chat.completions,
            "create",
            new=AsyncMock(side_effect=Exception("OpenAI API error")),
        ):
            with pytest.raises(Exception) as exc_info:
                await nl2sql_service.generate_sql(
                    user_prompt="Show me all users",
                    metadata=sample_metadata,
                )

            assert "Failed to generate SQL" in str(exc_info.value)
            assert "OpenAI API error" in str(exc_info.value)


class TestBuildPrompt:
    """测试 OpenAI 提示词构建。"""

    def test_build_prompt_includes_schema(self, nl2sql_service, sample_metadata):
        """测试提示词包含数据库结构信息。"""
        messages = nl2sql_service._build_prompt(
            user_prompt="Show me all users",
            metadata=sample_metadata,
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Show me all users"

        # 检查系统消息包含数据库结构
        system_message = messages[0]["content"]
        assert "users" in system_message
        assert "orders" in system_message
        assert "public" in system_message
        assert "100 rows" in system_message
        assert "500 rows" in system_message

        # 检查列信息
        assert "id" in system_message
        assert "name" in system_message
        assert "email" in system_message
        assert "PRIMARY KEY" in system_message
        assert "UNIQUE" in system_message

    def test_build_prompt_includes_views(self, nl2sql_service, sample_metadata):
        """测试提示词包含视图信息。"""
        messages = nl2sql_service._build_prompt(
            user_prompt="Query views",
            metadata=sample_metadata,
        )

        system_message = messages[0]["content"]
        assert "View:" in system_message
        assert "user_summary" in system_message
        assert "total_users" in system_message

    def test_build_prompt_includes_rules(self, nl2sql_service, sample_metadata):
        """测试提示词包含生成规则。"""
        messages = nl2sql_service._build_prompt(
            user_prompt="Test query",
            metadata=sample_metadata,
        )

        system_message = messages[0]["content"]
        assert "Rules:" in system_message
        assert "SELECT" in system_message
        assert "LIMIT" in system_message
        assert "PostgreSQL" in system_message
        assert "English and Chinese" in system_message

    def test_build_prompt_with_nullable_columns(self, nl2sql_service):
        """测试使用可空与非空列构建提示词。"""
        metadata = {
            "tables": [
                {
                    "name": "products",
                    "schemaName": "public",
                    "rowCount": 50,
                    "columns": [
                        {
                            "name": "id",
                            "dataType": "integer",
                            "nullable": False,
                            "primaryKey": True,
                            "unique": False,
                        },
                        {
                            "name": "description",
                            "dataType": "text",
                            "nullable": True,
                            "primaryKey": False,
                            "unique": False,
                        },
                    ],
                }
            ],
            "views": [],
        }

        messages = nl2sql_service._build_prompt(
            user_prompt="Test",
            metadata=metadata,
        )

        system_message = messages[0]["content"]
        assert "NOT NULL" in system_message
        # nullable=True 时不应添加 NOT NULL

    def test_build_prompt_empty_metadata(self, nl2sql_service):
        """测试使用空元数据构建提示词。"""
        metadata = {"tables": [], "views": []}

        messages = nl2sql_service._build_prompt(
            user_prompt="Test query",
            metadata=metadata,
        )

        assert len(messages) == 2
        system_message = messages[0]["content"]
        assert "Database Schema:" in system_message

    def test_build_prompt_with_default_values(self, nl2sql_service):
        """测试构建提示词时包含默认值。"""
        metadata = {
            "tables": [
                {
                    "name": "settings",
                    "schemaName": "public",
                    "rowCount": 10,
                    "columns": [
                        {
                            "name": "enabled",
                            "dataType": "boolean",
                            "nullable": False,
                            "primaryKey": False,
                            "unique": False,
                            "defaultValue": "true",
                        },
                    ],
                }
            ],
            "views": [],
        }

        messages = nl2sql_service._build_prompt(
            user_prompt="Test",
            metadata=metadata,
        )

        system_message = messages[0]["content"]
        assert "settings" in system_message
        assert "enabled" in system_message
        assert "boolean" in system_message
