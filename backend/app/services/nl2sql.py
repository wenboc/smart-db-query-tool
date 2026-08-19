"""基于 OpenAI 的自然语言转 SQL 服务。"""

from openai import AsyncOpenAI
from app.config import settings
from app.models.database import DatabaseType
import logging

logger = logging.getLogger(__name__)


class NaturalLanguageToSQLService:
    """使用 OpenAI 将自然语言查询转换为 SQL 的服务。"""

    def __init__(self):
        """初始化 OpenAI 客户端。"""
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o-mini"  # 兼顾 SQL 生成效果与调用成本

    def _build_prompt(
        self, user_prompt: str, metadata: dict, db_type: DatabaseType = DatabaseType.POSTGRESQL
    ) -> list[dict[str, str]]:
        """使用数据库元数据上下文构建 OpenAI 提示词。

        参数：
            user_prompt：用户输入的自然语言查询。
            metadata：数据库结构元数据字典。
            db_type：数据库类型，即 PostgreSQL 或 MySQL。

        返回：
            OpenAI 对话补全所需的消息列表。
        """
        # 构建数据库结构上下文
        schema_context = []
        for table in metadata.get("tables", []):
            columns_info = []
            for col in table.get("columns", []):
                col_desc = f"  - {col['name']} ({col['dataType']})"
                if col.get("primaryKey"):
                    col_desc += " PRIMARY KEY"
                if not col.get("nullable", True):
                    col_desc += " NOT NULL"
                if col.get("unique"):
                    col_desc += " UNIQUE"
                columns_info.append(col_desc)

            row_count = table.get("rowCount", "unknown")
            table_info = f"Table: {table['schemaName']}.{table['name']} ({row_count} rows)\n"
            table_info += "\n".join(columns_info)
            schema_context.append(table_info)

        for view in metadata.get("views", []):
            columns_info = [f"  - {col['name']} ({col['dataType']})" for col in view.get("columns", [])]
            view_info = f"View: {view['schemaName']}.{view['name']}\n"
            view_info += "\n".join(columns_info)
            schema_context.append(view_info)

        schema_text = "\n\n".join(schema_context)

        # 构建特定数据库的规则
        if db_type == DatabaseType.MYSQL:
            db_name = "MySQL"
            syntax_rules = """3. Use backticks for identifiers (e.g., `table_name`, `column_name`)
4. Return valid MySQL syntax
5. Use MySQL LIMIT syntax (LIMIT n)
6. Be aware of MySQL-specific features like AUTO_INCREMENT"""
        else:
            db_name = "PostgreSQL"
            syntax_rules = """3. Use proper schema qualification (schema.table)
4. Return valid PostgreSQL syntax
5. Use double quotes for identifiers if needed"""

        system_message = f"""You are an expert SQL query generator for {db_name} databases.

Database Schema:
{schema_text}

Rules:
1. Generate ONLY SELECT queries (no INSERT/UPDATE/DELETE/DROP)
2. Always include LIMIT clause (max 1000 rows)
{syntax_rules}
7. Handle both English and Chinese natural language
8. Be concise - return just the SQL query

Output format:
Return ONLY the SQL query, nothing else. No explanations, no markdown, just the SQL."""

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_prompt},
        ]

    async def generate_sql(
        self, user_prompt: str, metadata: dict, db_type: DatabaseType = DatabaseType.POSTGRESQL
    ) -> dict[str, str]:
        """将自然语言转换为 SQL 查询。

        参数：
            user_prompt：自然语言查询。
            metadata：数据库结构元数据字典。
            db_type：数据库类型，即 PostgreSQL 或 MySQL。

        返回：
            包含 'sql' 和 'explanation' 键的字典。

        异常：
            Exception：OpenAI API 调用失败。
        """
        try:
            messages = self._build_prompt(user_prompt, metadata, db_type)

            # 调用 OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,  # 使用较低温度以提高 SQL 生成的一致性
                max_tokens=500,
            )

            generated_sql = response.choices[0].message.content.strip()

            # 清理响应中可能存在的 Markdown 代码块
            if generated_sql.startswith("```sql"):
                generated_sql = generated_sql.replace("```sql", "").replace("```", "").strip()
            elif generated_sql.startswith("```"):
                generated_sql = generated_sql.replace("```", "").strip()

            # 生成说明
            explanation = f"Generated SQL from: {user_prompt}"

            logger.info(f"Generated SQL for prompt: {user_prompt[:50]}...")

            return {"sql": generated_sql, "explanation": explanation}

        except Exception as e:
            logger.error(f"Failed to generate SQL: {str(e)}")
            raise Exception(f"Failed to generate SQL: {str(e)}")


# 全局服务实例
nl2sql_service = NaturalLanguageToSQLService()
