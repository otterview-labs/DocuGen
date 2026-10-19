#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VLM配置模块

统一收口为：
- openai: 远端 OpenAI-compatible 视觉模型
- local: 本地/内网 OpenAI-compatible 视觉模型
- disabled: 关闭视觉模型分析
"""

from __future__ import annotations

import os
from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.shared.utils.http_auth import normalize_auth_mode


def _resolve_vlm_provider_from_env() -> str:
    raw = (os.getenv("VLM_PROVIDER") or os.getenv("VLM_MODEL_TYPE") or "").strip().lower()
    if not raw:
        return "disabled"

    mapping = {
        "openai": "openai",
        "openai-vision": "openai",
        "remote": "openai",
        "local": "local",
        "disabled": "disabled",
        "disable": "disabled",
        "none": "disabled",
        "off": "disabled",
        "false": "disabled",
        "0": "disabled",
        # 兼容旧值。若用户仍保留 qwen-vl，需要同时改成 OpenAI-compatible endpoint。
        "qwen-vl": "openai",
    }
    return mapping.get(raw, "disabled")


class VLMConfig(BaseModel):
    """VLM配置类"""

    provider: Literal["openai", "local", "disabled"] = Field(
        default="disabled",
        validation_alias=AliasChoices("provider", "model_type"),
        description="视觉模型提供商：openai/local/disabled",
    )
    model_name: str = Field(default="", description="具体模型名称")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    api_base: Optional[str] = Field(default=None, description="API基础URL")
    auth_mode: Literal["none", "bearer", "basic"] = Field(default="none", description="HTTP认证模式")
    username: Optional[str] = Field(default=None, description="Basic Auth 用户名")
    password: Optional[str] = Field(default=None, description="Basic Auth 密码")

    max_images_per_batch: int = Field(default=10, description="每批最大图片数")
    batch_timeout: int = Field(default=60, description="批处理超时时间（秒）")

    max_retries: int = Field(default=3, description="最大重试次数")
    retry_delay: float = Field(default=1.0, description="重试延迟基数")

    output_format: str = Field(default="json", description="输出格式: json, text, structured")
    language: str = Field(default="zh", description="输出语言: zh, en")
    system_prompt: str = Field(
        default="你是一个视觉分析助手，请准确描述图像内容。",
        description="系统提示词",
    )

    model_config = ConfigDict(extra="ignore")

    @property
    def model_type(self) -> str:
        """兼容旧接口命名。"""
        return self.provider

    @field_validator("provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: object) -> str:
        raw = "" if value is None else str(value).strip().lower()
        if not raw:
            return "disabled"
        mapping = {
            "openai": "openai",
            "openai-vision": "openai",
            "remote": "openai",
            "local": "local",
            "disabled": "disabled",
            "disable": "disabled",
            "none": "disabled",
            "off": "disabled",
            "false": "disabled",
            "0": "disabled",
            "qwen-vl": "openai",
        }
        return mapping.get(raw, "disabled")

    @field_validator("auth_mode", mode="before")
    @classmethod
    def normalize_auth_mode_value(cls, value: object) -> str:
        return normalize_auth_mode(str(value) if value is not None else None, default="none")

    @classmethod
    def from_env(cls) -> "VLMConfig":
        """从环境变量创建配置。"""
        provider = _resolve_vlm_provider_from_env()
        api_base = (
            os.getenv("VLM_API_BASE")
            or (os.getenv("LOCAL_LLM_ENDPOINT") if provider == "local" else os.getenv("OPENAI_API_BASE"))
            or ""
        ).strip() or None
        model_name = (
            os.getenv("VLM_MODEL_NAME")
            or (os.getenv("LOCAL_LLM_MODEL_NAME") if provider == "local" else os.getenv("OPENAI_MODEL_NAME"))
            or "gpt-4.1-mini"
        ).strip()

        if provider == "local":
            default_auth_mode = os.getenv("LOCAL_LLM_AUTH_MODE") or "none"
            api_key = os.getenv("VLM_API_KEY") or os.getenv("LOCAL_LLM_API_KEY")
            username = os.getenv("VLM_API_USERNAME") or os.getenv("LOCAL_LLM_USERNAME")
            password = os.getenv("VLM_API_PASSWORD") or os.getenv("LOCAL_LLM_PASSWORD")
        else:
            default_auth_mode = os.getenv("OPENAI_API_AUTH_MODE") or "bearer"
            api_key = os.getenv("VLM_API_KEY") or os.getenv("OPENAI_API_KEY")
            username = os.getenv("VLM_API_USERNAME") or os.getenv("OPENAI_API_USERNAME")
            password = os.getenv("VLM_API_PASSWORD") or os.getenv("OPENAI_API_PASSWORD")

        return cls(
            provider=provider,
            model_name=model_name,
            api_base=api_base,
            api_key=(api_key or "").strip() or None,
            auth_mode=os.getenv("VLM_API_AUTH_MODE") or default_auth_mode,
            username=(username or "").strip() or None,
            password=(password or "").strip() or None,
            max_images_per_batch=int(os.getenv("VLM_MAX_IMAGES_PER_BATCH", "10")),
            batch_timeout=int(os.getenv("VLM_BATCH_TIMEOUT", "60")),
            max_retries=int(os.getenv("VLM_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("VLM_RETRY_DELAY", "1.0")),
            output_format=os.getenv("VLM_OUTPUT_FORMAT", "json"),
            language=os.getenv("VLM_LANGUAGE", "zh"),
            system_prompt=os.getenv("VLM_SYSTEM_PROMPT", "你是一个视觉分析助手，请准确描述图像内容。"),
        )


default_vlm_config = VLMConfig.from_env()
