"""FastAPI 应用入口。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.api.v1 import databases, queries
from app.services.db_connection import close_all_connection_pools

# 初始化本地数据库
init_db()

# 创建 FastAPI 应用
app = FastAPI(
    title="智能数据库查询工具 API",
    description="智能数据库查询工具 — 管理 PostgreSQL/MySQL 连接并执行查询",
    version="1.0.0",
)

# 配置跨域资源共享
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(databases.router)
app.include_router(queries.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """提供健康检查端点。"""
    return {"status": "healthy", "version": "1.0.0"}


@app.on_event("startup")
async def startup_event() -> None:
    """在应用启动时初始化数据库。"""
    init_db()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """在应用关闭时清理资源。"""
    await close_all_connection_pools()
