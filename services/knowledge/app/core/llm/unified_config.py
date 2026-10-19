#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一的LLM配置管理系统
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from app.config import settings

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """LLM提供商枚举"""
    OPENAI = "openai"
    LOCAL = "local"


class TaskType(Enum):
    """任务类型枚举"""
    SIMPLE_CHAT = "simple_chat"
    AGENT_CHAT = "agent_chat"
    EMBEDDING = "embedding"
    RERANK = "rerank"
    TOOL_CALLING = "tool_calling"
    CODE_GENERATION = "code_generation"
    DOCUMENT_ANALYSIS = "document_analysis"
    KNOWLEDGE_EXTRACTION = "knowledge_extraction"


@dataclass
class ModelConfig:
    """模型配置数据类"""
    # 基础配置
    provider: LLMProvider
    model_name: str
    api_key: str
    api_base: Optional[str] = None
    auth_mode: str = "bearer"
    username: Optional[str] = None
    password: Optional[str] = None

    # 生成参数
    temperature: float = 0.7
    top_p: float = 0.8
    max_tokens: int = 2000

    # 高级配置
    timeout: int = 30
    retry_times: int = 3

    # 特定功能配置
    supports_tools: bool = True
    supports_streaming: bool = True
    supports_system_message: bool = True


class UnifiedLLMConfig:
    """统一的LLM配置管理器"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._load_configurations()

    def _load_configurations(self):
        """加载所有配置"""
        # 运行时配置（由 .env / 环境变量驱动）
        llm_provider = (getattr(settings.llm, "LLM_PROVIDER", "") or "openai").strip().lower()
        openai_model = (getattr(settings.llm, "OPENAI_MODEL_NAME", "") or "gpt-3.5-turbo").strip()
        openai_api_key = (getattr(settings.llm, "OPENAI_API_KEY", "") or "").strip()
        openai_api_base = (getattr(settings.llm, "OPENAI_API_BASE", "") or "").strip()
        openai_auth_mode = (getattr(settings.llm, "OPENAI_API_AUTH_MODE", "") or "bearer").strip().lower()
        openai_username = (getattr(settings.llm, "OPENAI_API_USERNAME", "") or "").strip() or None
        openai_password = (getattr(settings.llm, "OPENAI_API_PASSWORD", "") or "").strip() or None
        local_model = (getattr(settings.llm, "LOCAL_LLM_MODEL_NAME", "") or "").strip()
        local_api_base = (getattr(settings.llm, "LOCAL_LLM_ENDPOINT", "") or "").strip()
        local_auth_mode = (getattr(settings.llm, "LOCAL_LLM_AUTH_MODE", "") or "none").strip().lower()
        local_api_key = (getattr(settings.llm, "LOCAL_LLM_API_KEY", "") or "").strip()
        local_username = (getattr(settings.llm, "LOCAL_LLM_USERNAME", "") or "").strip() or None
        local_password = (getattr(settings.llm, "LOCAL_LLM_PASSWORD", "") or "").strip() or None

        self.configs = {
            # OpenAI（兼容 OpenAI API）模型配置
            # - 可用于 OpenAI 官方，也可用于本地 OpenAI-compatible 服务（base_url 指向本地 /v1）
            "openai-default": ModelConfig(
                provider=LLMProvider.OPENAI,
                model_name=openai_model,
                api_key=openai_api_key,
                api_base=openai_api_base,
                auth_mode=openai_auth_mode,
                username=openai_username,
                password=openai_password,
                temperature=0.7,
                top_p=0.8,
                max_tokens=2000,
                supports_tools=True,
                supports_streaming=True
            ),

            # 本地模型配置
            "local-llm": ModelConfig(
                provider=LLMProvider.LOCAL,
                model_name=local_model or openai_model,
                api_key=local_api_key,
                api_base=local_api_base or openai_api_base,
                auth_mode=local_auth_mode,
                username=local_username,
                password=local_password,
                temperature=0.7,
                max_tokens=2000,
                supports_tools=False,
                supports_streaming=True
            )
        }

        self.logger.info(f"加载了 {len(self.configs)} 个模型配置 (LLM_PROVIDER={llm_provider})")

    def get_config(self, model_name: str) -> Optional[ModelConfig]:
        """获取指定模型的配置"""
        return self.configs.get(model_name)

    def find_config_id_by_model_name(self, model_name: str) -> Optional[str]:
        """通过实际模型名查找配置ID（兼容外部直接传入 model id）。"""
        if not model_name:
            return None
        for config_id, config in self.configs.items():
            if config.model_name == model_name:
                return config_id
        return None

    def get_default_model_id(self, task_type: TaskType) -> str:
        """根据任务类型 + LLM_PROVIDER 选择默认的配置ID。"""
        provider = (getattr(settings.llm, "LLM_PROVIDER", "") or "openai").strip().lower()

        if provider == "local":
            return "local-llm"

        # 默认 openai
        return "openai-default"

    def get_default_config(self, task_type: TaskType) -> ModelConfig:
        """根据任务类型获取默认配置"""
        model_id = self.get_default_model_id(task_type)
        return self.get_config(model_id)

    def get_default_embedding_provider(self) -> LLMProvider:
        """获取默认的Embedding提供商配置。"""
        provider = (
            (getattr(settings.embedding, "PROVIDER", "") or "").strip().lower()
            or (getattr(settings.llm, "LLM_PROVIDER", "") or "").strip().lower()
            or "openai"
        )

        mapping = {
            "openai": LLMProvider.OPENAI,
            "local": LLMProvider.LOCAL,
        }
        return mapping.get(provider, LLMProvider.OPENAI)

    def to_embedding_config(self, provider: Optional[LLMProvider] = None) -> Dict[str, Any]:
        """转换为embedding模型配置"""
        provider = provider or self.get_default_embedding_provider()
        if provider == LLMProvider.OPENAI:
            return {
                "model_type": "OpenAI",
                "key": settings.llm.OPENAI_API_KEY,
                "auth_mode": settings.llm.OPENAI_API_AUTH_MODE,
                "username": settings.llm.OPENAI_API_USERNAME,
                "password": settings.llm.OPENAI_API_PASSWORD,
                "model_name": settings.embedding.OPENAI_EMBEDDING_MODEL,
                "base_url": settings.llm.OPENAI_API_BASE
            }
        if provider == LLMProvider.LOCAL:
            return {
                "model_type": "Local",
                "base_url": settings.embedding.LOCAL_EMBEDDING_URL,
                "model_name": settings.embedding.LOCAL_EMBEDDING_MODEL,
                "key": settings.embedding.LOCAL_EMBEDDING_API_KEY,
                "auth_mode": settings.embedding.LOCAL_EMBEDDING_AUTH_MODE,
                "username": settings.embedding.LOCAL_EMBEDDING_USERNAME,
                "password": settings.embedding.LOCAL_EMBEDDING_PASSWORD,
            }
        raise ValueError(f"不支持的Embedding provider: {provider}")

    def get_available_models(self, provider: Optional[LLMProvider] = None) -> List[str]:
        """获取可用的模型列表"""
        if provider:
            return [name for name, config in self.configs.items()
                   if config.provider == provider]
        return list(self.configs.keys())

    def is_model_available(self, model_name: str) -> bool:
        """检查模型是否可用"""
        config = self.get_config(model_name)
        if not config:
            return False

        # 检查API密钥是否配置
        if config.provider == LLMProvider.OPENAI:
            if config.auth_mode == "none":
                return bool(config.api_base)
            if config.auth_mode == "basic":
                return bool(config.api_base)
            return bool(config.api_key)
        if config.provider == LLMProvider.LOCAL:
            return bool(config.api_base)

        return True

    def get_task_complexity_score(self, task_description: str, task_type: TaskType) -> float:
        """评估任务复杂度分数 (0.0-1.0)"""
        complexity_keywords = {
            "high": ["分析", "推理", "复杂", "多步骤", "创造", "设计"],
            "medium": ["总结", "翻译", "转换", "整理", "提取"],
            "low": ["查询", "简单", "基础", "直接"]
        }

        description_lower = task_description.lower()

        # 基于任务类型的基础复杂度
        base_complexity = {
            TaskType.SIMPLE_CHAT: 0.2,
            TaskType.AGENT_CHAT: 0.8,
            TaskType.EMBEDDING: 0.1,
            TaskType.TOOL_CALLING: 0.9,
            TaskType.CODE_GENERATION: 0.8,
            TaskType.DOCUMENT_ANALYSIS: 0.6,
            TaskType.KNOWLEDGE_EXTRACTION: 0.7
        }

        complexity = base_complexity.get(task_type, 0.5)

        # 基于关键词调整
        for level, keywords in complexity_keywords.items():
            for keyword in keywords:
                if keyword in description_lower:
                    if level == "high":
                        complexity = min(1.0, complexity + 0.2)
                    elif level == "medium":
                        complexity = min(1.0, complexity + 0.1)
                    elif level == "low":
                        complexity = max(0.1, complexity - 0.1)

        return complexity

    def update_config(self, model_name: str, **kwargs):
        """动态更新模型配置"""
        if model_name not in self.configs:
            raise ValueError(f"模型 {model_name} 不存在")

        config = self.configs[model_name]
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
                self.logger.info(f"更新模型 {model_name} 的配置: {key} = {value}")

    def add_custom_config(self, model_name: str, config: ModelConfig):
        """添加自定义模型配置"""
        self.configs[model_name] = config
        self.logger.info(f"添加自定义模型配置: {model_name}")


# 全局配置实例
_unified_config = None

def get_unified_llm_config() -> UnifiedLLMConfig:
    """获取统一LLM配置的单例实例"""
    global _unified_config
    if _unified_config is None:
        _unified_config = UnifiedLLMConfig()
    return _unified_config


# 便捷函数
def get_model_config(model_name: str) -> Optional[ModelConfig]:
    """便捷函数：获取模型配置"""
    return get_unified_llm_config().get_config(model_name)

def get_embedding_config(provider: Optional[LLMProvider] = None) -> Dict[str, Any]:
    """便捷函数：获取embedding配置"""
    return get_unified_llm_config().to_embedding_config(provider)
