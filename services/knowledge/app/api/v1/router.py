#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API v1 主路由配置
管理所有 v1 版本的 API 模块
"""

from fastapi import APIRouter
import logging
from app.api.v1.rag import router as rag_router
from app.api.v1.llm.router import router as llm_router
# from app.api.v1.knowledge_graph_router import router as knowledge_graph_router

# 创建 v1 版本主路由
router = APIRouter()

# ==========================================
#            知识库系统模块
# ==========================================
# 注册知识库系统的所有接口
# 知识库系统包含：集合管理、文档上传、智能搜索、知识图谱等功能
router.include_router(
    rag_router,
    prefix="/rag",
    # 不在这里设置tags，让子路由自己管理tags
)

logging.info("✅ 知识库系统路由已成功注册")

# ==========================================
#               LLM 聊天模块
# ==========================================
router.include_router(
    llm_router,
    prefix="/llm",
)
logging.info("✅ LLM 聊天路由已注册 (/api/v1/llm)")

# ==========================================
#           知识图谱可视化模块
# ==========================================
# router.include_router(
#     knowledge_graph_router,
#     prefix="/knowledge-graph",
# )
logging.info("✅ 知识图谱可视化路由已注册 (/api/v1/knowledge-graph)")
