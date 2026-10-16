#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一的LLM服务接口管理系统
"""

import logging
from typing import Dict, Any, Optional, List, Union, AsyncGenerator
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.llm.unified_config import (
    get_unified_llm_config, TaskType, LLMProvider, ModelConfig
)
from app.shared.utils.http_auth import HTTPAuthConfig, build_httpx_auth

logger = logging.getLogger(__name__)


@dataclass
class LLMRequest:
    """LLM请求数据类"""
    messages: List[Dict[str, str]]
    task_type: TaskType
    model_name: Optional[str] = None
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    system_message: Optional[str] = None
    tools: Optional[List[Dict]] = None
    context: Optional[Dict[str, Any]] = None


@dataclass
class LLMResponse:
    """LLM响应数据类"""
    content: str
    model_name: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    context: Optional[Dict[str, Any]] = None


class BaseLLMAdapter(ABC):
    """LLM适配器基类"""

    def __init__(self, config: ModelConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def chat(self, request: LLMRequest) -> LLMResponse:
        """基础聊天接口"""
        pass

    @abstractmethod
    async def chat_stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """流式聊天接口"""
        pass

    async def embed(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """文本嵌入接口"""
        raise NotImplementedError("当前适配器不支持嵌入功能")


class LLMAdapterFactory:
    """LLM适配器工厂"""

    @staticmethod
    def create_adapter(config: ModelConfig, use_agent: bool = False) -> BaseLLMAdapter:
        """创建适配器"""
        if config.provider in {LLMProvider.OPENAI, LLMProvider.LOCAL}:
            return OpenAIChatAdapter(config)

        raise ValueError(f"不支持的 LLM provider: {config.provider}")


class SmartLLMRouter:
    """智能LLM路由器"""

    def __init__(self):
        self.config_manager = get_unified_llm_config()
        self.logger = logging.getLogger(self.__class__.__name__)

    def should_use_agent(self, request: LLMRequest) -> bool:
        """判断是否应该使用智能体模式"""

        # 强制指定的任务类型
        agent_tasks = {
            TaskType.AGENT_CHAT,
            TaskType.TOOL_CALLING,
            TaskType.CODE_GENERATION,
            TaskType.DOCUMENT_ANALYSIS
        }

        if request.task_type in agent_tasks:
            return True

        # 基于复杂度评估
        if request.context and 'task_description' in request.context:
            complexity = self.config_manager.get_task_complexity_score(
                request.context['task_description'],
                request.task_type
            )
            return complexity > 0.7

        # 基于消息内容长度和工具使用
        total_length = sum(len(msg.get('content', '')) for msg in request.messages)
        has_tools = bool(request.tools)

        return total_length > 1000 or has_tools

    def select_model(self, request: LLMRequest) -> str:
        """选择最适合的模型配置ID（不是实际 model_name）。"""

        # 1) 如果指定了 model_name：优先按「配置ID」解析；其次按「实际模型名」回查
        if request.model_name:
            if self.config_manager.get_config(request.model_name):
                return request.model_name
            config_id = self.config_manager.find_config_id_by_model_name(request.model_name)
            if config_id:
                return config_id

        # 2) 根据 LLM_PROVIDER + 任务类型选择默认
        return self.config_manager.get_default_model_id(request.task_type)


class UnifiedLLMService:
    """统一的LLM服务"""

    def __init__(self):
        self.config_manager = get_unified_llm_config()
        self.router = SmartLLMRouter()
        self.adapters_cache = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def _get_adapter(self, model_id: str, use_agent: bool = False) -> BaseLLMAdapter:
        """获取或创建适配器（带缓存）"""
        cache_key = f"{model_id}_{use_agent}"

        if cache_key not in self.adapters_cache:
            config = self.config_manager.get_config(model_id)
            if not config:
                raise ValueError(f"模型配置不存在: {model_id}")

            adapter = LLMAdapterFactory.create_adapter(config, use_agent)
            self.adapters_cache[cache_key] = adapter

        return self.adapters_cache[cache_key]

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """统一聊天接口"""
        try:
            # 路由决策
            model_id = self.router.select_model(request)
            use_agent = self.router.should_use_agent(request)

            cfg = self.config_manager.get_config(model_id)
            actual_model_name = cfg.model_name if cfg else model_id
            self.logger.info(
                f"选择模型: {actual_model_name} (id={model_id}), 使用智能体: {use_agent}, 任务类型: {request.task_type}"
            )

            # 获取适配器并调用
            adapter = self._get_adapter(model_id, use_agent)
            request.model_name = model_id  # 统一使用配置ID

            return await adapter.chat(request)

        except Exception as e:
            self.logger.error(f"统一聊天服务失败: {e}")
            # 降级处理：使用基础模式重试
            if use_agent:
                self.logger.warning("智能体模式失败，降级到基础模式")
                adapter = self._get_adapter(model_id, use_agent=False)
                return await adapter.chat(request)
            raise

    async def chat_stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """统一流式聊天接口"""
        model_id = self.router.select_model(request)
        use_agent = self.router.should_use_agent(request)

        adapter = self._get_adapter(model_id, use_agent)
        request.model_name = model_id

        async for chunk in adapter.chat_stream(request):
            yield chunk

    async def embed(self, texts: Union[str, List[str]], provider: Optional[LLMProvider] = None) -> List[List[float]]:
        """统一嵌入接口"""
        try:
            # 使用现有的嵌入模型
            from app.core.llm.embedding_model import create_embedding_model

            config = self.config_manager.to_embedding_config(provider)
            embedding_model = create_embedding_model(**config)

            if isinstance(texts, str):
                texts = [texts]

            embeddings, _ = embedding_model.encode(texts)
            return embeddings.tolist()

        except Exception as e:
            self.logger.error(f"文本嵌入失败: {e}")
            raise

    async def simple_chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """简化的聊天接口（向下兼容）"""
        request = LLMRequest(
            messages=messages,
            task_type=TaskType.SIMPLE_CHAT,
            **kwargs
        )
        response = await self.chat(request)
        return response.content

    async def agent_chat(self, messages: List[Dict[str, str]], agent_type: str = "general", **kwargs) -> str:
        """智能体聊天接口（向下兼容）"""
        request = LLMRequest(
            messages=messages,
            task_type=TaskType.AGENT_CHAT,
            context={"agent_type": agent_type},
            **kwargs
        )
        response = await self.chat(request)
        return response.content

    def get_service_stats(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        return {
            "available_models": self.config_manager.get_available_models(),
            "cached_adapters": len(self.adapters_cache),
            "openai_models": self.config_manager.get_available_models(LLMProvider.OPENAI),
            "local_models": self.config_manager.get_available_models(LLMProvider.LOCAL),
            "config_status": {
                model: self.config_manager.is_model_available(model)
                for model in self.config_manager.get_available_models()
            }
        }


class OpenAIChatAdapter(BaseLLMAdapter):
    """OpenAI / OpenAI-compatible Chat 适配器（含本地服务）。"""

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        try:
            from openai import AsyncOpenAI
            import httpx
        except Exception as e:
            raise RuntimeError(f"openai SDK 不可用: {e}")

        auth_config = HTTPAuthConfig.build(
            mode=config.auth_mode,
            api_key=config.api_key,
            username=config.username,
            password=config.password,
            default_mode="bearer",
        )
        base_url = self._normalize_openai_base_url(config.api_base)
        if not base_url:
            raise ValueError("OpenAI-compatible base_url 未配置（OPENAI_API_BASE/LOCAL_LLM_ENDPOINT）")

        self._http_client = httpx.AsyncClient(
            auth=build_httpx_auth(auth_config),
            timeout=config.timeout,
        )
        self._client = AsyncOpenAI(
            api_key=auth_config.sdk_api_key,
            base_url=base_url,
            http_client=self._http_client,
        )

    @staticmethod
    def _normalize_openai_base_url(base_url: Optional[str]) -> str:
        """标准化为 OpenAI SDK 可用的 base_url（一般应以 /v1 结尾）。"""
        if not base_url:
            return ""
        u = str(base_url).strip().rstrip("/")

        # 若用户填的是完整 endpoints，这里回退到 API 根
        for suffix in ("/chat/completions", "/completions", "/v1/chat/completions", "/v1/completions"):
            if u.endswith(suffix):
                u = u[: -len(suffix)].rstrip("/")
                break

        # OpenAI SDK 期望 base_url 包含 /v1
        if not u.endswith("/v1"):
            u = f"{u}/v1"
        return u

    def _build_messages(self, request: LLMRequest) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        if request.system_message:
            messages.append({"role": "system", "content": request.system_message})
        messages.extend(request.messages or [])
        return messages

    async def chat(self, request: LLMRequest) -> LLMResponse:
        try:
            messages = self._build_messages(request)
            resp = await self._client.chat.completions.create(
                model=self.config.model_name,
                messages=messages,
                temperature=request.temperature if request.temperature is not None else self.config.temperature,
                max_tokens=request.max_tokens if request.max_tokens is not None else self.config.max_tokens,
            )

            content = ""
            try:
                content = resp.choices[0].message.content or ""
            except Exception:
                content = ""

            usage = None
            try:
                if resp.usage:
                    usage = {
                        "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
                        "completion_tokens": getattr(resp.usage, "completion_tokens", None),
                        "total_tokens": getattr(resp.usage, "total_tokens", None),
                    }
            except Exception:
                usage = None

            return LLMResponse(
                content=content,
                model_name=self.config.model_name,
                usage=usage,
                finish_reason=getattr(resp.choices[0], "finish_reason", None) if resp.choices else None,
                context=request.context,
            )
        except Exception as e:
            self.logger.error(f"OpenAIChatAdapter聊天失败: {e}")
            raise

    async def chat_stream(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        # 当前项目接口主要走非流式；这里实现一个最小流式兼容
        messages = self._build_messages(request)
        stream = await self._client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            temperature=request.temperature if request.temperature is not None else self.config.temperature,
            max_tokens=request.max_tokens if request.max_tokens is not None else self.config.max_tokens,
            stream=True,
        )
        async for event in stream:
            try:
                delta = event.choices[0].delta
                chunk = getattr(delta, "content", None)
                if chunk:
                    yield chunk
            except Exception:
                continue


# 全局服务实例
_unified_service = None

def get_unified_llm_service() -> UnifiedLLMService:
    """获取统一LLM服务的单例实例"""
    global _unified_service
    if _unified_service is None:
        _unified_service = UnifiedLLMService()
    return _unified_service


# 便捷函数
async def unified_chat(messages: List[Dict[str, str]], task_type: TaskType = TaskType.SIMPLE_CHAT, **kwargs) -> str:
    """便捷函数：统一聊天"""
    service = get_unified_llm_service()
    request = LLMRequest(messages=messages, task_type=task_type, **kwargs)
    response = await service.chat(request)
    return response.content


async def unified_embed(texts: Union[str, List[str]], provider: Optional[LLMProvider] = None) -> List[List[float]]:
    """便捷函数：统一嵌入"""
    service = get_unified_llm_service()
    return await service.embed(texts, provider)
