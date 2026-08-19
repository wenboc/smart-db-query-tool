"""Pytest 配置与共享夹具。"""

import pytest


# 在测试收集阶段导入全部模型，确保填充 SQLModel 元数据
def pytest_configure(config):
    """在测试收集前运行的 Pytest 配置钩子。"""
    # 导入全部模型并注册到 SQLModel.metadata
    from app.models.database import DatabaseConnection
    from app.models.metadata import DatabaseMetadata
    from app.models.query import QueryHistory
