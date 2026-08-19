"""基于 sqlglot 的 SQL 校验服务。"""
from __future__ import annotations

import sqlglot
from sqlglot import exp
from app.models.database import DatabaseType


class SqlValidationError(Exception):
    """SQL 校验失败时抛出的异常。"""

    pass


def validate_sql(sql: str, db_type: DatabaseType = DatabaseType.POSTGRESQL) -> tuple[bool, str | None]:
    """
    使用 sqlglot 校验 SQL 查询。

    参数：
        sql：待校验的 SQL 查询字符串。
        db_type：数据库类型，即 PostgreSQL 或 MySQL。

    返回：
        由 (is_valid, error_message) 组成的元组。
    """
    try:
        # 确定 SQL 方言
        dialect = "postgres" if db_type == DatabaseType.POSTGRESQL else "mysql"

        # 解析 SQL
        parsed = sqlglot.parse_one(sql, dialect=dialect)
        if parsed is None:
            return False, "Failed to parse SQL query"

        # 检查根表达式是否为 SELECT 语句
        if not isinstance(parsed, exp.Select):
            return False, "Only SELECT statements are allowed"

        return True, None
    except sqlglot.errors.ParseError as e:
        return False, f"SQL parse error: {str(e)}"
    except Exception as e:
        return False, f"SQL validation error: {str(e)}"


def add_limit_if_missing(sql: str, limit: int = 1000, db_type: DatabaseType = DatabaseType.POSTGRESQL) -> str:
    """
    在 SELECT 语句缺少 LIMIT 时补充该子句。

    参数：
        sql：SQL 查询字符串。
        limit：最多返回的行数，默认为 1000。
        db_type：数据库类型，即 PostgreSQL 或 MySQL。

    返回：
        必要时已补充 LIMIT 子句的 SQL 查询。
    """
    try:
        # 确定 SQL 方言
        dialect = "postgres" if db_type == DatabaseType.POSTGRESQL else "mysql"

        parsed = sqlglot.parse_one(sql, dialect=dialect)
        if parsed is None:
            return sql

        # 检查是否已有 LIMIT 子句
        if parsed.find(exp.Limit):
            return sql

        # 添加 LIMIT 子句
        parsed.set("limit", exp.Limit(expression=exp.Literal.number(limit)))
        return parsed.sql(dialect=dialect)
    except Exception:
        # 解析失败时返回原始 SQL
        return sql


def validate_and_transform_sql(sql: str, limit: int = 1000, db_type: DatabaseType = DatabaseType.POSTGRESQL) -> str:
    """
    校验 SQL，并在缺少 LIMIT 时自动补充。

    参数：
        sql：SQL 查询字符串。
        limit：最多返回的行数，默认为 1000。
        db_type：数据库类型，即 PostgreSQL 或 MySQL。

    返回：
        已校验并转换的 SQL 查询。

    异常：
        SqlValidationError：SQL 校验失败。
    """
    is_valid, error_message = validate_sql(sql, db_type)
    if not is_valid:
        raise SqlValidationError(error_message or "Invalid SQL query")

    return add_limit_if_missing(sql, limit, db_type)
