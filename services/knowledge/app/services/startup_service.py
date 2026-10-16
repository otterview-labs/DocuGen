#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用启动编排服务。
"""

from __future__ import annotations

from typing import Any, Dict

from app.config import settings
from app.db.init_database import init_database
from app.db.session import test_db_connection
from app.shared.utils.logger_util import get_logger

logger = get_logger(__name__)


async def initialize_runtime_services() -> Dict[str, Any]:
    """执行启动期检查和可选的数据库初始化。"""

    startup_summary: Dict[str, Any] = {
        "database_connection_checked": False,
        "database_connection_ok": None,
        "database_initialized": False,
        "database_init_summary": None,
        "fail_fast": settings.startup.FAIL_FAST_ON_STARTUP_ERROR,
    }

    if settings.startup.CHECK_DATABASE_ON_STARTUP:
        startup_summary["database_connection_checked"] = True
        database_ok = test_db_connection()
        startup_summary["database_connection_ok"] = database_ok
        if not database_ok:
            message = "数据库连接检查失败"
            if settings.startup.FAIL_FAST_ON_STARTUP_ERROR:
                raise RuntimeError(message)
            logger.warning(message)

    should_initialize_database = any(
        [
            settings.startup.INITIALIZE_DATABASE_ON_STARTUP,
            settings.startup.RUN_DATABASE_MIGRATIONS_ON_STARTUP,
            settings.startup.SEED_LLM_CONFIG_ON_STARTUP,
        ]
    )

    if should_initialize_database:
        logger.info(
            "执行启动期数据库动作: create_tables=%s, run_migrations=%s, seed_llm=%s",
            settings.startup.INITIALIZE_DATABASE_ON_STARTUP,
            settings.startup.RUN_DATABASE_MIGRATIONS_ON_STARTUP,
            settings.startup.SEED_LLM_CONFIG_ON_STARTUP,
        )
        init_summary = init_database(
            create_tables=settings.startup.INITIALIZE_DATABASE_ON_STARTUP,
            run_migrations=settings.startup.RUN_DATABASE_MIGRATIONS_ON_STARTUP,
            initialize_seed_data=settings.startup.SEED_LLM_CONFIG_ON_STARTUP,
        )
        startup_summary["database_initialized"] = True
        startup_summary["database_init_summary"] = init_summary
    else:
        logger.info("已跳过启动期数据库初始化；如需执行，请配置 STARTUP_* 开关")

    return startup_summary
