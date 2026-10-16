#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG路由集成 - 添加文档处理进度推送端点
"""

from fastapi import APIRouter
from app.api.v1.rag.endpoints import document_progress

# 在现有的rag router中添加进度推送路由
def add_progress_routes(router: APIRouter):
    """添加进度推送相关路由"""
    router.include_router(
        document_progress.router,
        prefix="/document-progress",
        tags=["Document Progress"],
    )
