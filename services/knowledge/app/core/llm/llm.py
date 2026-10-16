#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM模型模块
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from app.shared.utils.http_auth import (
    HTTPAuthConfig,
    apply_auth_headers,
    build_requests_auth,
)


logger = logging.getLogger(__name__)


def _normalize_chat_endpoint(api_base: Optional[str]) -> str:
    value = (api_base or "https://api.openai.com/v1").strip().rstrip("/")
    if value.endswith("/chat/completions"):
        return value
    if not value.endswith("/v1"):
        value = f"{value}/v1"
    return f"{value}/chat/completions"


class BaseLLM:
    """基础LLM类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    async def chat(self, messages: list, **kwargs) -> str:
        """聊天方法"""
        raise NotImplementedError

    async def chat_stream(self, messages: list, **kwargs):
        """流式聊天方法"""
        raise NotImplementedError


class OpenAICompatibleLLM(BaseLLM):
    """通用 OpenAI-compatible LLM 实现。"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model_name = config.get("model_name", "gpt-3.5-turbo")
        self.base_url = _normalize_chat_endpoint(config.get("api_base"))
        self.max_tokens = config.get("max_tokens", 2000)
        self.temperature = config.get("temperature", 0.3)
        self.auth_config = HTTPAuthConfig.build(
            mode=config.get("auth_mode"),
            api_key=config.get("api_key"),
            username=config.get("username"),
            password=config.get("password"),
            default_mode="bearer",
        )

        if self.auth_config.mode == "bearer" and not self.auth_config.api_key:
            logger.warning("未配置可用的 LLM API 凭证，将使用模拟模式")
        else:
            logger.info("OpenAI-compatible LLM初始化完成，模型: %s, auth_mode: %s", self.model_name, self.auth_config.mode)

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """聊天方法"""
        if self.auth_config.mode == "bearer" and not self.auth_config.api_key:
            last_message = messages[-1] if messages else {"content": "你好"}
            return f"这是模拟LLM的响应: {last_message.get('content', '')}"

        data = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "top_p": kwargs.get("top_p", 0.8),
        }
        headers = apply_auth_headers({"Content-Type": "application/json"}, self.auth_config)

        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=data,
                timeout=90,
                auth=build_requests_auth(self.auth_config),
            )

            if response.status_code != 200:
                logger.error("OpenAI-compatible LLM调用失败: %s - %s", response.status_code, response.text)
                return f"API调用失败: HTTP {response.status_code}"

            result = response.json()
            choices = result.get("choices") or []
            if not choices:
                logger.error("OpenAI-compatible LLM返回异常: %s", result)
                return "API调用失败: 响应缺少 choices"

            content = choices[0].get("message", {}).get("content", "")
            logger.debug("OpenAI-compatible LLM响应成功，内容长度: %s", len(content))
            return content
        except Exception as e:
            logger.error("OpenAI-compatible LLM调用异常: %s", e)
            return f"调用异常: {e}"

    async def chat_stream(self, messages: List[Dict[str, str]], **kwargs):
        """流式聊天方法"""
        response = await self.chat(messages, **kwargs)
        yield {"content": response}


class MockLLM(BaseLLM):
    """模拟LLM类，用于测试"""

    async def chat(self, messages: list, **kwargs) -> str:
        """模拟聊天响应"""
        last_message = messages[-1] if messages else {"content": "你好"}
        return f"这是模拟LLM的响应: {last_message.get('content', '')}"

    async def chat_stream(self, messages: list, **kwargs):
        """模拟流式聊天响应"""
        last_message = messages[-1] if messages else {"content": "你好"}
        response = f"这是模拟LLM的流式响应: {last_message.get('content', '')}"
        for char in response:
            yield {"content": char}


def create_llm_model(config: Optional[Dict[str, Any]] = None) -> BaseLLM:
    """
    创建LLM模型

    Args:
        config: 模型配置

    Returns:
        LLM模型实例
    """
    return OpenAICompatibleLLM(config or {})
