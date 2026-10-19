#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM配置初始化数据
"""

import uuid
import logging
from sqlalchemy.orm import Session
from app.db.models import ModelProvider, ModelTemplate
from app.shared.enums import ModelType, StatusEnum

logger = logging.getLogger(__name__)


def init_model_providers(db: Session):
    """初始化模型提供商"""

    providers_data = [
        {
            "name": "DashScope",
            "display_name": "阿里云DashScope",
            "description": "阿里云通义千问系列模型",
            "supported_types": "LLM,Embedding,Rerank,ASR,TTS,Image2Text",
            "status": StatusEnum.ENABLED.value
        },
        {
            "name": "OpenAI",
            "display_name": "OpenAI",
            "description": "OpenAI GPT系列模型",
            "supported_types": "LLM,Embedding,ASR,TTS,Image2Text",
            "status": StatusEnum.ENABLED.value
        },
        {
            "name": "Local",
            "display_name": "本地模型",
            "description": "本地部署的开源模型",
            "supported_types": "LLM,Embedding,Rerank,ASR,TTS,Image2Text",
            "status": StatusEnum.ENABLED.value
        },
        {
            "name": "HuggingFace",
            "display_name": "HuggingFace",
            "description": "HuggingFace开源模型",
            "supported_types": "LLM,Embedding,Rerank,ASR,TTS,Image2Text",
            "status": StatusEnum.ENABLED.value
        }
    ]

    result_providers = {}

    for provider_data in providers_data:
        # 检查提供商是否已存在
        existing_provider = db.query(ModelProvider).filter(
            ModelProvider.name == provider_data["name"]
        ).first()

        if existing_provider:
            # 更新现有提供商
            for key, value in provider_data.items():
                if key != "name":  # name是主键，不更新
                    setattr(existing_provider, key, value)
            provider = existing_provider
            logger.info(f"更新现有提供商: {provider_data['name']}")
        else:
            # 创建新提供商
            provider = ModelProvider(
                id=str(uuid.uuid4()),
                **provider_data
            )
            db.add(provider)
            logger.info(f"创建新提供商: {provider_data['name']}")

        result_providers[provider_data["name"].lower()] = provider

    db.commit()

    return result_providers


def init_model_templates(db: Session, providers: dict):
    """初始化模型模板"""

    # DashScope模型模板
    dashscope_templates = [
        # LLM模型
        {
            "provider_id": providers["dashscope"].id,
            "model_name": "qwen-turbo",
            "model_type": ModelType.LLM.value,
            "display_name": "通义千问Turbo",
            "max_tokens": 8192,
            "tags": "聊天,对话",
            "is_tools_supported": True,
            "description": "通义千问Turbo版本，适合一般对话场景"
        },
        {
            "provider_id": providers["dashscope"].id,
            "model_name": "qwen-plus",
            "model_type": ModelType.LLM.value,
            "display_name": "通义千问Plus",
            "max_tokens": 32768,
            "tags": "聊天,对话,长文本",
            "is_tools_supported": True,
            "description": "通义千问Plus版本，支持更长文本"
        },
        {
            "provider_id": providers["dashscope"].id,
            "model_name": "qwen-max",
            "model_type": ModelType.LLM.value,
            "display_name": "通义千问Max",
            "max_tokens": 32768,
            "tags": "聊天,对话,长文本,高级",
            "is_tools_supported": True,
            "description": "通义千问Max版本，最高性能"
        },

        # Embedding模型
        {
            "provider_id": providers["dashscope"].id,
            "model_name": "text-embedding-v1",
            "model_type": ModelType.EMBEDDING.value,
            "display_name": "文本向量化模型",
            "max_tokens": 2048,
            "tags": "向量化,检索",
            "is_tools_supported": False,
            "description": "文本向量化模型，用于语义检索"
        },

        # Rerank模型
        {
            "provider_id": providers["dashscope"].id,
            "model_name": "gte-rerank",
            "model_type": ModelType.RERANK.value,
            "display_name": "重排序模型",
            "max_tokens": 2048,
            "tags": "重排序,检索优化",
            "is_tools_supported": False,
            "description": "重排序模型，用于优化检索结果"
        },

        # ASR模型
        {
            "provider_id": providers["dashscope"].id,
            "model_name": "speech-translation-v1",
            "model_type": ModelType.ASR.value,
            "display_name": "语音识别模型",
            "max_tokens": 0,
            "tags": "语音识别,转写",
            "is_tools_supported": False,
            "description": "语音识别模型，支持多种语言"
        },

        # TTS模型
        {
            "provider_id": providers["dashscope"].id,
            "model_name": "speech-synthesis",
            "model_type": ModelType.TTS.value,
            "display_name": "语音合成模型",
            "max_tokens": 0,
            "tags": "语音合成,朗读",
            "is_tools_supported": False,
            "description": "语音合成模型，支持多种音色"
        },

        # Image2Text模型
        {
            "provider_id": providers["dashscope"].id,
            "model_name": "qwen-vl-plus",
            "model_type": ModelType.IMAGE2TEXT.value,
            "display_name": "视觉语言模型",
            "max_tokens": 2048,
            "tags": "图像理解,视觉",
            "is_tools_supported": False,
            "description": "视觉语言模型，支持图像理解和描述"
        }
    ]

    # OpenAI模型模板
    openai_templates = [
        # LLM模型
        {
            "provider_id": providers["openai"].id,
            "model_name": "gpt-3.5-turbo",
            "model_type": ModelType.LLM.value,
            "display_name": "GPT-3.5 Turbo",
            "max_tokens": 4096,
            "tags": "聊天,对话",
            "is_tools_supported": True,
            "description": "GPT-3.5 Turbo模型，适合一般对话"
        },
        {
            "provider_id": providers["openai"].id,
            "model_name": "gpt-4",
            "model_type": ModelType.LLM.value,
            "display_name": "GPT-4",
            "max_tokens": 8192,
            "tags": "聊天,对话,高级",
            "is_tools_supported": True,
            "description": "GPT-4模型，更高性能"
        },

        # Embedding模型
        {
            "provider_id": providers["openai"].id,
            "model_name": "text-embedding-ada-002",
            "model_type": ModelType.EMBEDDING.value,
            "display_name": "Ada Embedding",
            "max_tokens": 8191,
            "tags": "向量化,检索",
            "is_tools_supported": False,
            "description": "OpenAI文本向量化模型"
        },

        # ASR模型
        {
            "provider_id": providers["openai"].id,
            "model_name": "whisper-1",
            "model_type": ModelType.ASR.value,
            "display_name": "Whisper语音识别",
            "max_tokens": 0,
            "tags": "语音识别,转写",
            "is_tools_supported": False,
            "description": "OpenAI Whisper语音识别模型"
        },

        # TTS模型
        {
            "provider_id": providers["openai"].id,
            "model_name": "tts-1",
            "model_type": ModelType.TTS.value,
            "display_name": "TTS语音合成",
            "max_tokens": 0,
            "tags": "语音合成,朗读",
            "is_tools_supported": False,
            "description": "OpenAI TTS语音合成模型"
        },

        # Image2Text模型
        {
            "provider_id": providers["openai"].id,
            "model_name": "gpt-4-vision-preview",
            "model_type": ModelType.IMAGE2TEXT.value,
            "display_name": "GPT-4 Vision",
            "max_tokens": 4096,
            "tags": "图像理解,视觉",
            "is_tools_supported": False,
            "description": "GPT-4 Vision模型，支持图像理解"
        }
    ]

    # 本地模型模板
    local_templates = [
        # LLM模型
        {
            "provider_id": providers["local"].id,
            "model_name": "llama-2-7b",
            "model_type": ModelType.LLM.value,
            "display_name": "Llama-2-7B",
            "max_tokens": 4096,
            "tags": "聊天,对话,开源",
            "is_tools_supported": False,
            "description": "本地部署的Llama-2-7B模型"
        },

        # Embedding模型
        {
            "provider_id": providers["local"].id,
            "model_name": "sentence-transformers/all-MiniLM-L6-v2",
            "model_type": ModelType.EMBEDDING.value,
            "display_name": "Sentence Transformers",
            "max_tokens": 256,
            "tags": "向量化,检索,开源",
            "is_tools_supported": False,
            "description": "本地部署的Sentence Transformers模型"
        }
    ]

    # 合并所有模板数据
    all_templates_data = dashscope_templates + openai_templates + local_templates

    # 使用upsert方式处理模板
    created_count = 0
    updated_count = 0

    for template_data in all_templates_data:
        # 检查模板是否已存在（基于provider_id + model_name + model_type）
        existing_template = db.query(ModelTemplate).filter(
            ModelTemplate.provider_id == template_data["provider_id"],
            ModelTemplate.model_name == template_data["model_name"],
            ModelTemplate.model_type == template_data["model_type"]
        ).first()

        if existing_template:
            # 更新现有模板
            for key, value in template_data.items():
                setattr(existing_template, key, value)
            updated_count += 1
        else:
            # 创建新模板
            template = ModelTemplate(
                id=str(uuid.uuid4()),
                **template_data
            )
            db.add(template)
            created_count += 1

    db.commit()

    logger.info(f"成功初始化模型模板: 创建 {created_count} 个，更新 {updated_count} 个")


def init_llm_config_data(db: Session):
    """初始化LLM配置数据"""
    try:
        logger.info("开始初始化LLM配置数据...")

        # 初始化模型提供商
        providers = init_model_providers(db)
        logger.info(f"成功初始化 {len(providers)} 个模型提供商")

        # 初始化模型模板
        init_model_templates(db, providers)

        logger.info("LLM配置数据初始化完成！")

    except Exception as e:
        logger.error(f"初始化LLM配置数据失败: {e}")
        db.rollback()

        # 提供更详细的错误信息
        if "Duplicate entry" in str(e) and "model_providers" in str(e):
            logger.info("提示: 检测到模型提供商表中有重复记录，这通常是因为之前的初始化已经成功。")
            logger.error("请运行数据库清理脚本或手动处理重复记录")

        raise
