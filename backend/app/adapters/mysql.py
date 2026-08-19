"""MySQL 数据库适配器。"""

# #region debug-point A:instrumentation-imports
import json
import time
import urllib.request
from contextlib import suppress
# #endregion

import aiomysql
from typing import Dict, List, Any, Tuple, Optional
from urllib.parse import unquote, urlparse
from datetime import datetime

from app.adapters.base import (
    DatabaseAdapter,
    ConnectionConfig,
    QueryResult,
    MetadataResult,
)


class MySQLAdapter(DatabaseAdapter):
    """基于 aiomysql 的 MySQL 数据库适配器。"""

    def _parse_url(self, url: str) -> Dict[str, Any]:
        """解析 MySQL 连接 URL。"""
        parsed = urlparse(url)
        return {
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 3306,
            'user': unquote(parsed.username) if parsed.username else 'root',
            'password': unquote(parsed.password) if parsed.password else '',
            'db': unquote(parsed.path.lstrip('/')) if parsed.path else None,
        }

    async def test_connection(self) -> Tuple[bool, Optional[str]]:
        """测试 MySQL 连接。"""
        # #region debug-point E:connection-start
        _debug_trace_id = f"mysql-{time.time_ns()}"
        _debug_started_at = time.perf_counter()
        with suppress(Exception): urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:7777/event", data=json.dumps({"sessionId": "mysql-connect-failure", "runId": "post-fix", "hypothesisId": "E", "traceId": _debug_trace_id, "location": "backend/app/adapters/mysql.py:test_connection", "msg": "[DEBUG] MySQL 连接测试开始", "data": {}, "ts": int(time.time() * 1000)}).encode(), headers={"Content-Type": "application/json"}), timeout=0.5).read()
        # #endregion
        try:
            params = self._parse_url(self.config.url)
            # #region debug-point C:parsed-params
            with suppress(Exception): urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:7777/event", data=json.dumps({"sessionId": "mysql-connect-failure", "runId": "post-fix", "hypothesisId": "C", "traceId": _debug_trace_id, "location": "backend/app/adapters/mysql.py:test_connection", "msg": "[DEBUG] MySQL URL 解析完成", "data": {"host": params["host"], "port": params["port"], "database": params["db"], "username": params["user"], "passwordLength": len(params["password"]), "passwordHasLeadingWhitespace": params["password"][:1].isspace(), "passwordHasTrailingWhitespace": params["password"][-1:].isspace()}, "ts": int(time.time() * 1000)}).encode(), headers={"Content-Type": "application/json"}), timeout=0.5).read()
            # #endregion
            conn = await aiomysql.connect(**params)
            # #region debug-point D:handshake-success
            with suppress(Exception): urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:7777/event", data=json.dumps({"sessionId": "mysql-connect-failure", "runId": "post-fix", "hypothesisId": "D", "traceId": _debug_trace_id, "location": "backend/app/adapters/mysql.py:test_connection", "msg": "[DEBUG] MySQL 握手成功", "data": {"elapsedMs": round((time.perf_counter() - _debug_started_at) * 1000, 2)}, "ts": int(time.time() * 1000)}).encode(), headers={"Content-Type": "application/json"}), timeout=0.5).read()
            # #endregion
            await conn.ensure_closed()
            return True, None
        except Exception as e:
            # #region debug-point A:connection-failure
            with suppress(Exception): urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:7777/event", data=json.dumps({"sessionId": "mysql-connect-failure", "runId": "post-fix", "hypothesisId": "A", "traceId": _debug_trace_id, "location": "backend/app/adapters/mysql.py:test_connection", "msg": "[DEBUG] MySQL 连接失败", "data": {"elapsedMs": round((time.perf_counter() - _debug_started_at) * 1000, 2), "errorType": type(e).__name__, "errorArgs": [str(arg) for arg in e.args], "errno": getattr(e, "errno", None), "causeType": type(e.__cause__).__name__ if e.__cause__ else None, "cause": str(e.__cause__) if e.__cause__ else None, "contextType": type(e.__context__).__name__ if e.__context__ else None, "context": str(e.__context__) if e.__context__ else None}, "ts": int(time.time() * 1000)}).encode(), headers={"Content-Type": "application/json"}), timeout=0.5).read()
            # #endregion
            return False, str(e)

    async def get_connection_pool(self) -> aiomysql.Pool:
        """获取或创建 aiomysql 连接池。"""
        if self._pool is None:
            params = self._parse_url(self.config.url)
            self._pool = await aiomysql.create_pool(
                host=params['host'],
                port=params['port'],
                user=params['user'],
                password=params['password'],
                db=params['db'],
                minsize=self.config.min_pool_size,
                maxsize=self.config.max_pool_size,
                autocommit=True,
            )
        return self._pool

    async def close_connection_pool(self) -> None:
        """关闭 MySQL 连接池。"""
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    async def extract_metadata(self) -> MetadataResult:
        """从 INFORMATION_SCHEMA 提取 MySQL 元数据。"""
        pool = await self.get_connection_pool()

        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 从当前连接获取实际数据库名称
                await cursor.execute("SELECT DATABASE()")
                result = await cursor.fetchone()
                db_name = result["DATABASE()"]

                if not db_name:
                    return MetadataResult(tables=[], views=[])

                # 获取全部表和视图
                tables_query = """
                    SELECT
                        TABLE_SCHEMA as schemaname,
                        TABLE_NAME as tablename,
                        TABLE_TYPE as type
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_SCHEMA = %s
                    ORDER BY TABLE_SCHEMA, TABLE_NAME
                """
                await cursor.execute(tables_query, (db_name,))
                tables_rows = await cursor.fetchall()

                tables: List[Dict[str, Any]] = []
                views: List[Dict[str, Any]] = []

                for row in tables_rows:
                    schema_name = row["schemaname"]
                    table_name = row["tablename"]
                    table_type = "table" if row["type"] == "BASE TABLE" else "view"

                    # 获取当前表或视图的列
                    columns = await self._get_columns(cursor, schema_name, table_name)

                    # 仅统计表的行数，视图不统计
                    row_count = None
                    if table_type == "table":
                        row_count = await self._get_row_count(cursor, schema_name, table_name)

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
        self, cursor, schema_name: str, table_name: str
    ) -> List[Dict[str, Any]]:
        """获取表或视图的列元数据。"""
        columns_query = """
            SELECT
                c.COLUMN_NAME as column_name,
                c.DATA_TYPE as data_type,
                c.CHARACTER_MAXIMUM_LENGTH as character_maximum_length,
                c.IS_NULLABLE as is_nullable,
                c.COLUMN_DEFAULT as column_default,
                c.ORDINAL_POSITION as ordinal_position,
                c.COLUMN_KEY as column_key,
                c.EXTRA as extra
            FROM INFORMATION_SCHEMA.COLUMNS c
            WHERE c.TABLE_SCHEMA = %s
                AND c.TABLE_NAME = %s
            ORDER BY c.ORDINAL_POSITION
        """
        await cursor.execute(columns_query, (schema_name, table_name))
        columns_rows = await cursor.fetchall()

        # 获取主键和唯一约束
        constraints_query = """
            SELECT
                kcu.COLUMN_NAME,
                tc.CONSTRAINT_TYPE
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
                ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
                AND tc.TABLE_NAME = kcu.TABLE_NAME
            WHERE tc.TABLE_SCHEMA = %s
                AND tc.TABLE_NAME = %s
                AND tc.CONSTRAINT_TYPE IN ('PRIMARY KEY', 'UNIQUE')
        """
        await cursor.execute(constraints_query, (schema_name, table_name))
        constraints_rows = await cursor.fetchall()

        # 构建约束映射
        primary_keys = set()
        unique_cols = set()
        for constraint in constraints_rows:
            if constraint["CONSTRAINT_TYPE"] == "PRIMARY KEY":
                primary_keys.add(constraint["COLUMN_NAME"])
            elif constraint["CONSTRAINT_TYPE"] == "UNIQUE":
                unique_cols.add(constraint["COLUMN_NAME"])

        # 构建列元数据
        columns: List[Dict[str, Any]] = []
        for col_row in columns_rows:
            data_type = col_row["data_type"]
            if col_row["character_maximum_length"]:
                data_type = f"{data_type}({col_row['character_maximum_length']})"

            column_meta = {
                "name": col_row["column_name"],
                "dataType": data_type,
                "nullable": col_row["is_nullable"] == "YES",
                "primaryKey": col_row["column_name"] in primary_keys,
                "unique": col_row["column_name"] in unique_cols,
                "defaultValue": col_row["column_default"],
            }
            columns.append(column_meta)

        return columns

    async def _get_row_count(
        self, cursor, schema_name: str, table_name: str
    ) -> Optional[int]:
        """获取表的行数。"""
        try:
            count_query = f"SELECT COUNT(*) as count FROM `{schema_name}`.`{table_name}`"
            await cursor.execute(count_query)
            count_result = await cursor.fetchone()
            if count_result:
                return count_result["count"]
        except Exception:
            # 行数统计失败时返回 None
            pass
        return None

    async def execute_query(self, sql: str) -> QueryResult:
        """在 MySQL 上执行查询。"""
        pool = await self.get_connection_pool()

        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # 执行查询
                await cursor.execute(sql)

                # 获取全部数据行
                rows = await cursor.fetchall()

                # 从游标描述中获取列元数据
                columns: List[Dict[str, str]] = []
                if cursor.description:
                    for desc in cursor.description:
                        column_name = desc[0]
                        type_code = desc[1]
                        data_type = self._map_mysql_type(type_code)
                        columns.append({"name": column_name, "dataType": data_type})

                # 将数据行转换为字典列表
                result_rows: List[Dict[str, Any]] = []
                for row in rows:
                    # 将日期时间对象转为字符串，以便进行 JSON 序列化
                    processed_row = {}
                    for key, value in row.items():
                        if isinstance(value, datetime):
                            processed_row[key] = value.isoformat()
                        else:
                            processed_row[key] = value
                    result_rows.append(processed_row)

                return QueryResult(
                    columns=columns,
                    rows=result_rows,
                    row_count=len(result_rows)
                )

    def get_dialect_name(self) -> str:
        """返回 MySQL 方言名称。"""
        return "mysql"

    def get_identifier_quote_char(self) -> str:
        """返回 MySQL 标识符使用的反引号。"""
        return "`"

    @staticmethod
    def _map_mysql_type(type_code: int) -> str:
        """将 MySQL 类型代码映射为可读的类型名称。"""
        type_map = {
            0: "DECIMAL",
            1: "TINY",
            2: "SHORT",
            3: "LONG",
            4: "FLOAT",
            5: "DOUBLE",
            6: "NULL",
            7: "TIMESTAMP",
            8: "LONGLONG",
            9: "INT24",
            10: "DATE",
            11: "TIME",
            12: "DATETIME",
            13: "YEAR",
            14: "NEWDATE",
            15: "VARCHAR",
            16: "BIT",
            245: "JSON",
            246: "NEWDECIMAL",
            247: "ENUM",
            248: "SET",
            249: "TINY_BLOB",
            250: "MEDIUM_BLOB",
            251: "LONG_BLOB",
            252: "BLOB",
            253: "VAR_STRING",
            254: "STRING",
            255: "GEOMETRY",
        }
        return type_map.get(type_code, f"UNKNOWN({type_code})")
