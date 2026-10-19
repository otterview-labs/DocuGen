#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
健康检查服务。
"""

from __future__ import annotations

import socket
from datetime import datetime, timezone
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

from app.config import settings
from app.db.session import test_db_connection


def _check_result(name: str, status: str, *, required: bool, detail: str, extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "name": name,
        "status": status,
        "required": required,
        "detail": detail,
    }
    if extra:
        payload.update(extra)
    return payload


def _tcp_ping(host: str, port: int, timeout: float) -> bool:
    with socket.create_connection((host, port), timeout=timeout):
        return True


def _check_database() -> Dict[str, Any]:
    healthy = test_db_connection()
    return _check_result(
        "database",
        "healthy" if healthy else "unhealthy",
        required=True,
        detail="数据库连接正常" if healthy else "数据库连接失败",
        extra={"database_type": settings.database.DB_DATABASE_TYPE},
    )


def _check_redis() -> Dict[str, Any]:
    if not settings.health.CHECK_REDIS:
        return _check_result("redis", "skipped", required=False, detail="Redis 健康检查已禁用")

    if not settings.redis.is_configured:
        return _check_result("redis", "disabled", required=False, detail="Redis 未配置")

    try:
        import redis

        if settings.redis.REDIS_URL:
            client = redis.from_url(
                settings.redis.REDIS_URL,
                decode_responses=settings.redis.REDIS_DECODE_RESPONSES,
                socket_timeout=settings.health.TIMEOUT_SECONDS,
                socket_connect_timeout=settings.health.TIMEOUT_SECONDS,
                retry_on_timeout=settings.redis.REDIS_RETRY_ON_TIMEOUT,
            )
        else:
            client = redis.Redis(
                host=settings.redis.REDIS_HOST,
                port=settings.redis.REDIS_PORT,
                password=settings.redis.REDIS_PASSWORD or None,
                db=settings.redis.REDIS_DB,
                decode_responses=settings.redis.REDIS_DECODE_RESPONSES,
                socket_timeout=settings.health.TIMEOUT_SECONDS,
                socket_connect_timeout=settings.health.TIMEOUT_SECONDS,
                retry_on_timeout=settings.redis.REDIS_RETRY_ON_TIMEOUT,
            )
        client.ping()
        return _check_result("redis", "healthy", required=False, detail="Redis 连接正常")
    except Exception as exc:
        return _check_result("redis", "unhealthy", required=False, detail=f"Redis 连接失败: {exc}")


def _check_vector_db(database_check: Dict[str, Any]) -> Dict[str, Any]:
    if not settings.health.CHECK_VECTOR_DB:
        return _check_result("vector_db", "skipped", required=True, detail="向量库健康检查已禁用")

    vector_type = (settings.vector_db.DB_TYPE or "faiss").lower()
    if vector_type == "faiss":
        return _check_result(
            "vector_db",
            "healthy",
            required=True,
            detail="FAISS 使用本地索引目录",
            extra={"type": vector_type, "index_path": settings.vector_db.FAISS_INDEX_PATH},
        )

    if vector_type == "pgvector":
        if database_check["status"] != "healthy":
            return _check_result("vector_db", "unhealthy", required=True, detail="pgvector 依赖主数据库，但数据库连接失败", extra={"type": vector_type})
        return _check_result("vector_db", "healthy", required=True, detail="pgvector 依赖主数据库，数据库连接正常", extra={"type": vector_type})

    try:
        if vector_type == "milvus":
            if settings.vector_db.MILVUS_URI:
                parsed = urlparse(settings.vector_db.MILVUS_URI)
                host = parsed.hostname or "localhost"
                port = parsed.port or (443 if parsed.scheme == "https" else 80)
            else:
                host = settings.vector_db.MILVUS_HOST
                port = settings.vector_db.MILVUS_PORT
            _tcp_ping(host, int(port), settings.health.TIMEOUT_SECONDS)
            return _check_result("vector_db", "healthy", required=True, detail="Milvus 连接正常", extra={"type": vector_type, "host": host, "port": port})

        if vector_type == "qdrant":
            _tcp_ping(settings.vector_db.QDRANT_HOST, settings.vector_db.QDRANT_PORT, settings.health.TIMEOUT_SECONDS)
            return _check_result(
                "vector_db",
                "healthy",
                required=True,
                detail="Qdrant 连接正常",
                extra={"type": vector_type, "host": settings.vector_db.QDRANT_HOST, "port": settings.vector_db.QDRANT_PORT},
            )
    except Exception as exc:
        return _check_result("vector_db", "unhealthy", required=True, detail=f"{vector_type} 连接失败: {exc}", extra={"type": vector_type})

    return _check_result("vector_db", "unknown", required=True, detail=f"未实现的向量库检查: {vector_type}", extra={"type": vector_type})


def _check_graph_db(database_check: Dict[str, Any]) -> Dict[str, Any]:
    if not settings.health.CHECK_GRAPH_DB:
        return _check_result("graph_db", "skipped", required=False, detail="知识图谱健康检查已禁用")

    if not settings.graph_db.GRAPH_DB_ENABLED:
        return _check_result("graph_db", "disabled", required=False, detail="知识图谱功能未启用")

    graph_type = (settings.graph_db.GRAPH_DB_TYPE or "postgres").lower()
    if graph_type == "postgres":
        if database_check["status"] != "healthy":
            return _check_result("graph_db", "unhealthy", required=False, detail="Postgres 图存储依赖主数据库，但数据库连接失败", extra={"type": graph_type})
        return _check_result("graph_db", "healthy", required=False, detail="Postgres 图存储依赖主数据库，数据库连接正常", extra={"type": graph_type})

    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            settings.graph_db.NEO4J_URI,
            auth=(settings.graph_db.NEO4J_USERNAME, settings.graph_db.NEO4J_PASSWORD),
            connection_timeout=settings.health.TIMEOUT_SECONDS,
        )
        try:
            driver.verify_connectivity()
        finally:
            driver.close()
        return _check_result("graph_db", "healthy", required=False, detail="Neo4j 兼容后端连接正常", extra={"type": graph_type})
    except Exception as exc:
        return _check_result("graph_db", "unhealthy", required=False, detail=f"Neo4j 兼容后端连接失败: {exc}", extra={"type": graph_type})


def build_health_report() -> Tuple[Dict[str, Any], int]:
    """构建健康检查结果。"""

    database_check = _check_database()
    vector_check = _check_vector_db(database_check)
    graph_check = _check_graph_db(database_check)
    redis_check = _check_redis()

    checks = {
        "database": database_check,
        "vector_db": vector_check,
        "graph_db": graph_check,
        "redis": redis_check,
    }

    required_failures = [check for check in checks.values() if check["required"] and check["status"] not in {"healthy", "disabled", "skipped"}]
    optional_failures = [check for check in checks.values() if not check["required"] and check["status"] not in {"healthy", "disabled", "skipped"}]

    if required_failures:
        overall_status = "unhealthy"
        status_code = 503
    elif optional_failures:
        overall_status = "degraded"
        status_code = 200
    else:
        overall_status = "healthy"
        status_code = 200

    payload = {
        "status": overall_status,
        "service": "JetLinksAI Knowledge",
        "environment": settings.ENVIRONMENT,
        "mode": "development" if settings.is_development else "production" if settings.is_production else "test",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return payload, status_code
