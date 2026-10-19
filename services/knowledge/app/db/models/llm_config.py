#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM配置模型 - 支持用户自定义模型配置
参考深度设计，支持多种模型类型
"""

from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, Float
from sqlalchemy.sql import func
from app.db.models.base import BaseModel


class ModelProvider(BaseModel):
    """模型提供商表"""
    __tablename__ = "model_providers"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False, unique=True, index=True)
    display_name = Column(String(128), nullable=False)
    logo = Column(Text, nullable=True, comment="提供商logo base64")
    description = Column(Text, nullable=True)
    supported_types = Column(String(255), nullable=False, comment="支持的模型类型: LLM,Embedding,Rerank,ASR,TTS,Image2Text")
    status = Column(String(1), nullable=False, default="1", comment="状态: 0-禁用, 1-启用")


class ModelTemplate(BaseModel):
    """模型模板表"""
    __tablename__ = "model_templates"

    id = Column(String(64), primary_key=True)
    provider_id = Column(String(64), nullable=False, index=True)
    model_name = Column(String(128), nullable=False, index=True)
    model_type = Column(String(32), nullable=False, index=True, comment="模型类型: LLM,Embedding,Rerank,ASR,TTS,Image2Text")
    display_name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    max_tokens = Column(Integer, default=8192, comment="最大token数")
    tags = Column(String(255), nullable=True, comment="标签: 32k,128k,工具调用等")
    is_tools_supported = Column(Boolean, default=False, comment="是否支持工具调用")
    status = Column(String(1), nullable=False, default="1", comment="状态: 0-禁用, 1-启用")


class UserModelConfig(BaseModel):
    """用户模型配置表"""
    __tablename__ = "user_model_configs"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    provider_id = Column(String(64), nullable=False, index=True)
    model_type = Column(String(32), nullable=False, index=True, comment="模型类型")
    model_name = Column(String(128), nullable=False, index=True)
    display_name = Column(String(128), nullable=True, comment="用户自定义显示名称")

    # API配置
    api_key = Column(String(2048), nullable=True, comment="API密钥")
    api_base = Column(String(255), nullable=True, comment="API基础URL")
    api_version = Column(String(32), nullable=True, comment="API版本")

    # 模型参数
    max_tokens = Column(Integer, default=8192, comment="最大token数")
    temperature = Column(Float, default=0.7, comment="温度参数")
    top_p = Column(Float, default=0.9, comment="Top-p参数")

    # 使用统计
    used_tokens = Column(Integer, default=0, comment="已使用token数")
    total_requests = Column(Integer, default=0, comment="总请求数")

    # 状态
    is_default = Column(Boolean, default=False, comment="是否为默认模型")
    status = Column(String(1), nullable=False, default="1", comment="状态: 0-禁用, 1-启用")

    # 时间戳
    last_used_time = Column(DateTime, nullable=True, comment="最后使用时间")


class UserDefaultConfig(BaseModel):
    """用户默认配置表"""
    __tablename__ = "user_default_configs"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, unique=True, index=True)

    # 默认模型配置
    default_llm_id = Column(String(64), nullable=True, comment="默认LLM模型ID")
    default_embedding_id = Column(String(64), nullable=True, comment="默认Embedding模型ID")
    default_rerank_id = Column(String(64), nullable=True, comment="默认Rerank模型ID")
    default_asr_id = Column(String(64), nullable=True, comment="默认ASR模型ID")
    default_tts_id = Column(String(64), nullable=True, comment="默认TTS模型ID")
    default_image2text_id = Column(String(64), nullable=True, comment="默认Image2Text模型ID")

    # 全局参数
    similarity_threshold = Column(Float, default=0.2, comment="相似度阈值")
    vector_similarity_weight = Column(Float, default=0.3, comment="向量相似度权重")
    top_k = Column(Integer, default=1024, comment="检索数量")
    top_n = Column(Integer, default=6, comment="返回数量")

    # 时间戳
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())
