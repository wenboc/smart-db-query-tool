"""PostgreSQL 数据库适配器。"""

import asyncpg
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime

from app.adapters.base import (
    DatabaseAdapter,
    ConnectionConfig,
    QueryResult,
    MetadataResult,
)


class PostgreSQLAdapter(DatabaseAdapter):
    """基于 asyncpg 的 PostgreSQL 数据库适配器。"""

    async def test_connection(self) -> Tuple[bool, Optional[str]]:
        """测试 PostgreSQL 连接。"""
        try:
            conn = await asyncpg.connect(self.config.url)
            await conn.close()
            return True, None
        except Exception as e:
            return False, str(e)

    async def get_connection_pool(self) -> asyncpg.Pool:
        """获取或创建 asyncpg 连接池。"""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.config.url,
                min_size=self.config.min_pool_size,
                max_size=self.config.max_pool_size,
                command_timeout=self.config.command_timeout,
            )
        return self._pool

    async def close_connection_pool(self) -> None:
        """关闭 PostgreSQL 连接池。"""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def extract_metadata(self) -> MetadataResult:
        """从 pg_catalog 提取 PostgreSQL 元数据。"""
        pool = await self.get_connection_pool()

        async with pool.acquire() as conn:
            # 获取全部表和视图
            tables_query = """
                SELECT
                    schemaname,
                    tablename,
                    'table' AS type
                FROM pg_tables
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                UNION ALL
                SELECT
                    schemaname,
                    viewname AS tablename,
                    'view' AS type
                FROM pg_views
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                ORDER BY schemaname, tablename
            """
            tables_rows = await conn.fetch(tables_query)

            tables: List[Dict[str, Any]] = []
            views: List[Dict[str, Any]] = []

            for row in tables_rows:
                schema_name = row["schemaname"]
                table_name = row["tablename"]
                table_type = row["type"]

                # 获取当前表或视图的列
                columns = await self._get_columns(conn, schema_name, table_name)

                # 仅统计表的行数，视图不统计
                row_count = None
                if table_type == "table":
                    row_count = await self._get_row_count(conn, schema_name, table_name)

                table_meta = {
                    "name": table_name,
                    "type": table_type,
                    "schemaName": schema_name,
                    "columns": columns,
                }
                if row_count is not None:
                    table_meta["rowCount"] = row_count

                if table_type == "table":
                    tables.append(table_meta)
                else:
                    views.append(table_meta)

        return MetadataResult(tables=tables, views=views)

    async def _get_columns(
        self, conn: asyncpg.Connection, schema_name: str, table_name: str
    ) -> List[Dict[str, Any]]:
        """获取表或视图的列元数据。"""
        columns_query = """
            SELECT
                c.column_name,
                c.data_type,
                c.character_maximum_length,
                c.is_nullable,
                c.column_default,
                c.ordinal_position,
                CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END AS is_primary_key,
                CASE WHEN uq.column_name IS NOT NULL THEN true ELSE false END AS is_unique
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                    AND tc.table_name = kcu.table_name
                WHERE tc.table_schema = $1
                    AND tc.table_name = $2
                    AND tc.constraint_type = 'PRIMARY KEY'
            ) pk ON c.column_name = pk.column_name
            LEFT JOIN (
                SELECT DISTINCT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                    AND tc.table_name = kcu.table_name
                WHERE tc.table_schema = $1
                    AND tc.table_name = $2
                    AND tc.constraint_type = 'UNIQUE'
            ) uq ON c.column_name = uq.column_name
            WHERE c.table_schema = $1
                AND c.table_name = $2
            ORDER BY c.ordinal_position
        """
        columns_rows = await conn.fetch(columns_query, schema_name, table_name)

        columns: List[Dict[str, Any]] = []
        for col_row in columns_rows:
            data_type = col_row["data_type"]
            if col_row["character_maximum_length"]:
                data_type = f"{data_type}({col_row['character_maximum_length']})"

            column_meta = {
                "name": col_row["column_name"],
                "dataType": data_type,
                "nullable": col_row["is_nullable"] == "YES",
                "primaryKey": col_row["is_primary_key"],
                "unique": col_row["is_unique"],
                "defaultValue": col_row["column_default"],
            }
            columns.append(column_meta)

        return columns

    async def _get_row_count(
        self, conn: asyncpg.Connection, schema_name: str, table_name: str
    ) -> Optional[int]:
        """获取表的行数。"""
        try:
            count_query = f'SELECT COUNT(*) FROM "{schema_name}"."{table_name}"'
            count_result = await conn.fetchrow(count_query)
            if count_result:
                return count_result[0]
        except Exception:
            # 行数统计失败时返回 None
            pass
        return None

    async def execute_query(self, sql: str) -> QueryResult:
        """在 PostgreSQL 上执行查询。"""
        pool = await self.get_connection_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(sql)

            # 转换为标准结果格式
            columns: List[Dict[str, str]] = []
            result_rows: List[Dict[str, Any]] = []

            if rows:
                # 从第一行推断列名和类型
                first_row = rows[0]
                for key, value in first_row.items():
                    data_type = self._infer_type(value)
                    columns.append({"name": key, "dataType": data_type})

                # 转换全部数据行
                for row in rows:
                    result_rows.append(dict(row))

            return QueryResult(
                columns=columns,
                rows=result_rows,
                row_count=len(result_rows)
            )

    def get_dialect_name(self) -> str:
        """返回 PostgreSQL 方言名称。"""
        return "postgres"

    def get_identifier_quote_char(self) -> str:
        """返回 PostgreSQL 标识符使用的双引号。"""
        return '"'

    @staticmethod
    def _infer_type(value: Any) -> str:
        """根据 Python 值推断 PostgreSQL 类型。"""
        if value is None:
            return "unknown"
        elif isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "double precision"
        elif isinstance(value, str):
            return "character varying"
        elif isinstance(value, datetime):
            return "timestamp"
        else:
            return str(type(value).__name__)
