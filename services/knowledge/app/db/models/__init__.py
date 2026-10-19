#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库模型模块 - 仅保留知识库相关模型
"""

# 导入基础类
from app.db.models.base import Base

# 导入用户模型（基础认证需要）
from app.db.models.user import User

# 导入RAG知识库模型（核心功能）
from app.db.models.rag import (
    RAGCollection,
    RAGChunk,
    RAGContent,
    RAGCollectionContent,
    RAGMediaAsset,
    RAGQuery,
    RAGVisualRegion,
    RAGResourceRelation
)

# 导入批量处理模型（文档批量上传需要）
from app.db.models.batch_task import (
    BatchTask,
    BatchTaskFile,
    BatchProcessingLog
)

# 导入LLM配置模型（内容分析需要）
from app.db.models.llm_config import (
    ModelProvider,
    ModelTemplate,
    UserModelConfig,
    UserDefaultConfig
)

# 导入API日志模型（请求日志记录）
from app.db.models.api_log import APIRequestLog

# 导入操作日志模型（操作审计）
from app.db.models.operation_log import (
    OperationLog,
    OperationType,
    ResourceType,
    OperationStatus
)

__all__ = [
    # 基础类
    "Base",

    # 用户相关
    "User",

    # RAG知识库相关（核心）
    "RAGCollection",
    "RAGChunk",
    "RAGContent",
    "RAGCollectionContent",
    "RAGMediaAsset",
    "RAGQuery",
    "RAGVisualRegion",
    "RAGResourceRelation",

    # 批量处理相关（需要）
    "BatchTask",
    "BatchTaskFile",
    "BatchProcessingLog",

    # LLM配置相关（需要）
    "ModelProvider",
    "ModelTemplate",
    "UserModelConfig",
    "UserDefaultConfig",

    # API日志相关
    "APIRequestLog",

    # 操作日志相关
    "OperationLog",
    "OperationType",
    "ResourceType",
    "OperationStatus",
]
