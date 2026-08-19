"""SQL 校验服务单元测试。"""

import pytest
from app.services.sql_validator import (
    validate_sql,
    add_limit_if_missing,
    validate_and_transform_sql,
    SqlValidationError,
)


class TestValidateSql:
    """测试 SQL 校验函数。"""

    def test_valid_select(self):
        """测试有效的 SELECT 语句可通过校验。"""
        is_valid, error = validate_sql("SELECT * FROM users")
        assert is_valid is True
        assert error is None

    def test_select_with_where(self):
        """测试带 WHERE 子句的 SELECT。"""
        is_valid, error = validate_sql("SELECT id, name FROM users WHERE id = 1")
        assert is_valid is True
        assert error is None

    def test_select_with_join(self):
        """测试带 JOIN 的 SELECT。"""
        is_valid, error = validate_sql(
            "SELECT u.id, u.name FROM users u JOIN orders o ON u.id = o.user_id"
        )
        assert is_valid is True
        assert error is None

    def test_reject_insert(self):
        """测试 INSERT 语句会被拒绝。"""
        is_valid, error = validate_sql("INSERT INTO users (name) VALUES ('test')")
        assert is_valid is False
        assert error is not None
        assert "SELECT" in error or "allowed" in error

    def test_reject_update(self):
        """测试 UPDATE 语句会被拒绝。"""
        is_valid, error = validate_sql("UPDATE users SET name = 'test' WHERE id = 1")
        assert is_valid is False
        assert error is not None

    def test_reject_delete(self):
        """测试 DELETE 语句会被拒绝。"""
        is_valid, error = validate_sql("DELETE FROM users WHERE id = 1")
        assert is_valid is False
        assert error is not None

    def test_invalid_sql(self):
        """测试无效 SQL 会被拒绝。"""
        is_valid, error = validate_sql("SELECT * FROM WHERE")
        assert is_valid is False
        assert error is not None


class TestAddLimitIfMissing:
    """测试 LIMIT 注入函数。"""

    def test_add_limit_when_missing(self):
        """测试缺少 LIMIT 时会自动补充。"""
        sql = "SELECT * FROM users"
        result = add_limit_if_missing(sql, limit=100)
        assert "LIMIT" in result.upper()
        assert "100" in result

    def test_keep_existing_limit(self):
        """测试已有的 LIMIT 会被保留。"""
        sql = "SELECT * FROM users LIMIT 50"
        result = add_limit_if_missing(sql, limit=100)
        assert "LIMIT" in result.upper()
        # 应保留原始限制值或使用指定值
        assert result.upper().count("LIMIT") == 1

    def test_limit_with_offset(self):
        """测试带 OFFSET 的 LIMIT。"""
        sql = "SELECT * FROM users OFFSET 10"
        result = add_limit_if_missing(sql, limit=100)
        assert "LIMIT" in result.upper()
        assert "OFFSET" in result.upper()


class TestValidateAndTransformSql:
    """测试组合校验与转换。"""

    def test_valid_sql_with_limit(self):
        """测试有效 SQL 会被补充 LIMIT。"""
        sql = "SELECT * FROM users"
        result = validate_and_transform_sql(sql, limit=100)
        assert "LIMIT" in result.upper()
        assert "100" in result

    def test_invalid_sql_raises_error(self):
        """测试无效 SQL 会抛出 SqlValidationError。"""
        with pytest.raises(SqlValidationError):
            validate_and_transform_sql("INSERT INTO users VALUES (1)")

    def test_select_with_existing_limit(self):
        """测试已有 LIMIT 的 SELECT。"""
        sql = "SELECT * FROM users LIMIT 50"
        result = validate_and_transform_sql(sql, limit=100)
        assert isinstance(result, str)
        assert "SELECT" in result.upper()
