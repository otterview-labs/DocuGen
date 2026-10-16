#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库初始化脚本
"""

import logging
from typing import Any, Dict, List

from app.db.session import engine, SessionLocal
from app.db.models import Base
from app.db.init_llm_config import init_llm_config_data


logger = logging.getLogger(__name__)


ONLINE_MIGRATIONS = [
    "app.db.migrations.20250911_alter_file_transaction_text",
    "app.db.migrations.20251020_create_api_request_logs",
]


def run_online_migrations() -> List[Dict[str, Any]]:
    """执行在线迁移脚本。"""

    import importlib

    results: List[Dict[str, Any]] = []
    for module_name in ONLINE_MIGRATIONS:
        try:
            migration_module = importlib.import_module(module_name)
            status = getattr(migration_module, "migrate")(engine)
            results.append({"module": module_name, "status": status or "ok"})
            logger.info("应用迁移 %s: %s", module_name, status or "ok")
        except Exception as migration_error:
            logger.warning("在线迁移执行失败(%s): %s", module_name, migration_error)
            results.append({"module": module_name, "status": "failed", "error": str(migration_error)})
    return results


def init_database(
    *,
    create_tables: bool = True,
    run_migrations: bool = True,
    initialize_seed_data: bool = True,
) -> Dict[str, Any]:
    """初始化数据库。"""

    summary: Dict[str, Any] = {
        "create_tables": create_tables,
        "run_migrations": run_migrations,
        "initialize_seed_data": initialize_seed_data,
        "migrations": [],
    }

    try:
        if create_tables:
            Base.metadata.create_all(bind=engine)
            logger.info("数据库表创建完成")

        if run_migrations:
            summary["migrations"] = run_online_migrations()

        if initialize_seed_data:
            db = SessionLocal()
            try:
                try:
                    init_llm_config_data(db)
                    summary["seed_data"] = "initialized"
                except Exception as llm_error:
                    logger.warning(f"LLM配置数据初始化跳过: {llm_error}")
                    summary["seed_data"] = f"skipped: {llm_error}"
            finally:
                db.close()
        else:
            summary["seed_data"] = "skipped"

        logger.info("数据库初始化完成")
        return summary

    except Exception as error:
        logger.error(f"数据库初始化失败: {error}")
        raise


if __name__ == "__main__":
    init_database()
