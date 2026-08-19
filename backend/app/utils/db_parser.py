"""用于识别数据库类型的连接 URL 解析工具。"""

from urllib.parse import urlparse
from app.models.database import DatabaseType


def detect_database_type(url: str) -> DatabaseType:
    """
    根据连接 URL 识别数据库类型。

    参数：
        url：数据库连接 URL，例如 postgresql://... 或 mysql://...。

    返回：
        DatabaseType 枚举值。

    异常：
        ValueError：无法识别数据库类型或类型不受支持。
    """
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()

        # 处理常见的 PostgreSQL URL 协议
        if scheme in ("postgresql", "postgres"):
            return DatabaseType.POSTGRESQL

        # 处理常见的 MySQL URL 协议
        if scheme in ("mysql", "mysql+pymysql", "mysql+aiomysql"):
            return DatabaseType.MYSQL

        raise ValueError(
            f"Unsupported database type: {scheme}. "
            f"Supported types: postgresql, postgres, mysql"
        )

    except Exception as e:
        raise ValueError(f"Failed to parse database URL: {str(e)}")
