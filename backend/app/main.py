import logging, time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from app.adapters.registry import adapter_registry
from app.api.v1 import databases, queries
from app.api.v1.metrics import router as metrics_router
from app.api.v1.metrics import _request_counts, _error_counts, _total_latency_ms, _active_requests
from app.config import settings
from app.database import init_db
from app.services.security import SecurityViolationError

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app.main")
init_db()

limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute} per minute"], storage_uri="memory://")
app = FastAPI(title="智能数据库查询工具 API", version="1.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(SlowAPIMiddleware)

@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    global _active_requests
    _active_requests += 1
    start = time.time()
    path = request.scope.get("path", "unknown")
    try:
        response = await call_next(request)
        latency_ms = (time.time() - start) * 1000
        _request_counts[path] += 1
        _total_latency_ms[path] += latency_ms
        if response.status_code >= 400: _error_counts[path] += 1
        response.headers["X-Request-Latency-Ms"] = f"{latency_ms:.2f}"
        return response
    except SecurityViolationError as e:
        latency_ms = (time.time() - start) * 1000
        _request_counts[path] += 1; _total_latency_ms[path] += latency_ms; _error_counts[path] += 1
        logger.warning("Security violation on %s: %s", path, e)
        return JSONResponse(status_code=403, content={"detail": str(e), "category": "security_policy", "info": e.detail}, headers={"X-Request-Latency-Ms": f"{latency_ms:.2f}"})
    except Exception:
        latency_ms = (time.time() - start) * 1000
        _request_counts[path] += 1; _total_latency_ms[path] += latency_ms; _error_counts[path] += 1
        logger.exception("Unhandled error"); raise
    finally: _active_requests -= 1

app.include_router(databases.router)
app.include_router(queries.router)
app.include_router(metrics_router)

@app.get("/health")
async def health_check(): return {"status": "healthy", "version": "1.1.0"}

@app.on_event("startup")
async def startup_event(): init_db(); logger.info("App started v1.1.0")

@app.on_event("shutdown")
async def shutdown_event(): await adapter_registry.close_all_adapters(); logger.info("Shutdown")
