#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库模块。

避免在包导入阶段触发 session / init_db / 业务依赖的级联导入。
"""

from __future__ import annotations

from app.db.base_class import Base

__all__ = [
    "Base",
    "RAGCollection",
    "RAGChunk",
    "RAGContent",
    "RAGCollectionContent",
    "RAGQuery",
    "ModelProvider",
    "ModelTemplate",
    "UserModelConfig",
    "UserDefaultConfig",
    "SessionLocal",
    "engine",
    "create_initial_data",
    "test_db_connection",
    "DatabaseOperations",
    "init_database",
    "create_admin_user",
    "test_admin_login",
]


def __getattr__(name: str):
    if name in {
        "RAGCollection",
        "RAGChunk",
        "RAGContent",
        "RAGCollectionContent",
        "RAGQuery",
        "ModelProvider",
        "ModelTemplate",
        "UserModelConfig",
        "UserDefaultConfig",
    }:
        from app.db.models import (
            ModelProvider,
            ModelTemplate,
            RAGChunk,
            RAGCollection,
            RAGCollectionContent,
            RAGContent,
            RAGQuery,
            UserDefaultConfig,
            UserModelConfig,
        )

        return {
            "RAGCollection": RAGCollection,
            "RAGChunk": RAGChunk,
            "RAGContent": RAGContent,
            "RAGCollectionContent": RAGCollectionContent,
            "RAGQuery": RAGQuery,
            "ModelProvider": ModelProvider,
            "ModelTemplate": ModelTemplate,
            "UserModelConfig": UserModelConfig,
            "UserDefaultConfig": UserDefaultConfig,
        }[name]

    if name in {"SessionLocal", "engine", "create_initial_data", "test_db_connection"}:
        from app.db.session import SessionLocal, create_initial_data, engine, test_db_connection

        return {
            "SessionLocal": SessionLocal,
            "engine": engine,
            "create_initial_data": create_initial_data,
            "test_db_connection": test_db_connection,
        }[name]

    if name == "DatabaseOperations":
        from app.db.operations import DatabaseOperations

        return DatabaseOperations

    if name in {"init_database", "create_admin_user", "test_admin_login"}:
        from app.db.init_db import create_admin_user, init_database, test_admin_login

        return {
            "init_database": init_database,
            "create_admin_user": create_admin_user,
            "test_admin_login": test_admin_login,
        }[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
