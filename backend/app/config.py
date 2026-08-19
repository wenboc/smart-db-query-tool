"""使用 Pydantic Settings 管理应用配置。"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """应用配置。"""

    # OpenAI API 配置
    openai_api_key: str

    # 数据目录
    db_explorer_data_dir: str = str(Path.home() / ".db_explorer")

    # 日志配置
    log_level: str = "INFO"

    # 跨域资源共享配置
    cors_origins: str = "*"

    # 查询配置
    query_default_limit: int = 1000
    query_history_retention: int = 50

    # 数据库连接池配置
    db_pool_min_size: int = 1
    db_pool_max_size: int = 5
    db_pool_command_timeout: int = 60

    # 元数据缓存配置
    metadata_cache_hours: int = 24

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """将跨域来源配置解析为列表。"""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def db_path(self) -> Path:
        """返回 SQLite 数据库路径。"""
        data_dir = Path(self.db_explorer_data_dir).expanduser()
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "db_explorer.db"


settings = Settings()
