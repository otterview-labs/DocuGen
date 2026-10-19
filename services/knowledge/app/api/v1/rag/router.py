#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库系统路由配置
将所有知识库相关的接口统一组织管理
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

_route_import_errors: dict[str, str] = {}


def _include_optional_router(
    module_path: str,
    *,
    prefix: str,
    tags: list[str],
    responses: dict[int, dict[str, str]] | None = None,
) -> None:
    """按需导入子路由；缺少可选依赖时跳过对应功能。"""

    try:
        module = importlib.import_module(module_path)
        child_router = getattr(module, "router")
        router.include_router(
            child_router,
            prefix=prefix,
            tags=tags,
            responses=responses or {},
        )
        logger.info("✅ 已注册路由: %s -> %s", prefix, module_path)
    except (ImportError, ModuleNotFoundError) as exc:
        error_message = f"{type(exc).__name__}: {exc}"
        _route_import_errors[module_path] = error_message
        logger.warning("⚠️ 跳过路由 %s，导入失败: %s", module_path, error_message)


def get_route_import_errors() -> dict[str, str]:
    return dict(_route_import_errors)


_ROUTE_SPECS: list[dict[str, Any]] = [
    {
        "module_path": "app.api.v1.rag.endpoints.collections",
        "prefix": "/collections",
        "tags": ["知识库-集合管理"],
        "responses": {404: {"description": "集合不存在"}},
    },
    {
        "module_path": "app.api.v1.rag.endpoints.multimodal_upload",
        "prefix": "/multimodal",
        "tags": ["知识库-文档上传"],
        "responses": {413: {"description": "文件过大"}},
    },
    {
        "module_path": "app.api.v1.rag.endpoints.simple_upload",
        "prefix": "/simple-upload",
        "tags": ["知识库-简单上传"],
        "responses": {413: {"description": "文件过大"}},
    },
    {
        "module_path": "app.api.v1.rag.endpoints.document_operations",
        "prefix": "/documents",
        "tags": ["知识库-文档操作"],
    },
    {
        "module_path": "app.api.v1.rag.endpoints.resource_parse",
        "prefix": "/resource-parse",
        "tags": ["知识库-批量解析"],
        "responses": {400: {"description": "请求参数错误"}},
    },
    {
        "module_path": "app.api.v1.rag.endpoints.chunking_pipeline",
        "prefix": "/chunking",
        "tags": ["知识库-分块策略"],
        "responses": {400: {"description": "请求参数错误"}},
    },
    {
        "module_path": "app.api.v1.rag.endpoints.unified_search",
        "prefix": "/search",
        "tags": ["知识库-智能搜索"],
        "responses": {400: {"description": "查询参数错误"}},
    },
    {
        "module_path": "app.api.v1.rag.endpoints.kg",
        "prefix": "/kg",
        "tags": ["知识库-知识图谱"],
    },
    {
        "module_path": "app.api.v1.rag.endpoints.kg_extract",
        "prefix": "/kg",
        "tags": ["知识库-知识图谱"],
    },
    {
        "module_path": "app.api.v1.rag.endpoints.kg_visualization",
        "prefix": "/kg",
        "tags": ["知识库-知识图谱"],
    },
    {
        "module_path": "app.api.v1.rag.endpoints.content_analysis",
        "prefix": "/content-analysis",
        "tags": ["知识库-内容分析"],
    },
    {
        "module_path": "app.api.v1.rag.endpoints.search_methods",
        "prefix": "/search",
        "tags": ["知识库-搜索方法"],
    },
    {
        "module_path": "app.api.v1.rag.endpoints.qa_import",
        "prefix": "/qa",
        "tags": ["知识库-问答对导入"],
        "responses": {400: {"description": "请求参数错误"}},
    },
]


for route_spec in _ROUTE_SPECS:
    _include_optional_router(**route_spec)


# ==========================================
#            已移除的功能
# ==========================================
# 以下功能已在系统精简过程中移除：
# - 演示搜索（demo_search）
# - 统一上传（unified_upload）- 已整合到multimodal_upload
# - 文档状态（document_status）- 冗余功能
# - 文档状态监控（document_status_monitor）- JAIP协议相关，已移除
# - 向量管理（vector）- 底层操作，无实际用途
# - 系统统计（stats）- 冗余的统计功能
