"""数据库高层服务（外观模式 + tenacity 指数退避重试）。"""
import asyncio, logging, time
from typing import Tuple, Optional
from tenacity import AsyncRetrying, RetryError, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter
from app.config import settings
from app.models.database import DatabaseType
from app.adapters.base import ConnectionConfig, QueryResult, MetadataResult
from app.adapters.registry import DatabaseAdapterRegistry, adapter_registry
from app.services.sql_validator import validate_and_transform_sql, SqlValidationError

logger = logging.getLogger(__name__)
_TRANSIENT_EXCEPTIONS = (asyncio.TimeoutError, ConnectionRefusedError, ConnectionResetError, BrokenPipeError, OSError)

def _is_retryable(exc):
    if isinstance(exc, _TRANSIENT_EXCEPTIONS): return True
    cls = type(exc).__name__.lower()
    return any(k in cls for k in ("connect", "connection", "pool", "timeout", "reset", "refused", "broken"))

class DatabaseService:
    def __init__(self, registry):
        self.registry = registry
        logger.info("Initialized DatabaseService with tenacity retry policy")

    async def _with_retry(self, operation, desc):
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(settings.retry_max_attempts),
                wait=wait_exponential_jitter(initial=settings.retry_min_wait_seconds, max=settings.retry_max_wait_seconds),
                retry=retry_if_exception_type(Exception), reraise=True,
            ):
                with attempt: return await operation()
        except RetryError as e:
            last = e.last_attempt.exception() if e.last_attempt else e
            logger.error("[retry] %s exhausted: %s", desc, last); raise

    async def test_connection(self, db_type, url):
        config = ConnectionConfig(url=url, name="connection_test")
        adapter = self.registry.create_adapter(db_type, config)
        try: return await adapter.test_connection()
        finally: await adapter.close_connection_pool()

    async def execute_query(self, db_type, name, url, sql, limit=1000):
        validated_sql = validate_and_transform_sql(sql, limit=limit, db_type=db_type)
        config = ConnectionConfig(url=url, name=name)
        adapter = self.registry.get_adapter(db_type, config)
        start = time.time()
        async def _run(): return await adapter.execute_query(validated_sql)
        try:
            try: result = await self._with_retry(_run, f"execute_query::{name}")
            except Exception as exc:
                if _is_retryable(exc):
                    logger.warning("Transient on %s, refresh pool: %s", name, exc)
                    await self.registry.close_adapter(db_type, name)
                    adapter = self.registry.get_adapter(db_type, config)
                    result = await adapter.execute_query(validated_sql)
                else: raise
            ms = int((time.time() - start) * 1000)
            logger.info("Query ok on %s: %d rows in %dms", name, result.row_count, ms)
            return result, ms
        except Exception:
            ms = int((time.time() - start) * 1000)
            logger.error("Query failed on %s after %dms", name, ms, exc_info=True); raise

    async def extract_metadata(self, db_type, name, url):
        config = ConnectionConfig(url=url, name=name)
        adapter = self.registry.get_adapter(db_type, config)
        return await self._with_retry(lambda: adapter.extract_metadata(), f"extract_metadata::{name}")

    async def close_connection(self, db_type, name):
        await self.registry.close_adapter(db_type, name)

database_service = DatabaseService(adapter_registry)
