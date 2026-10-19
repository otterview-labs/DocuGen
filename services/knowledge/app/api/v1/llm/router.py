#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 简易聊天接口
提供最小可用的 REST 聊天与文本向量化端点，便于前端页面直连。
"""

from typing import List, Dict, Optional, Any
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field
try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from app.core.llm.unified_service import (
    get_unified_llm_service, LLMRequest
)
from app.core.llm.unified_config import TaskType, LLMProvider, get_unified_llm_config
from app.shared.response_models import ResponseHelper


router = APIRouter(tags=["LLM"])


class ChatMessage(BaseModel):
    role: str = Field(..., description="消息角色：system/user/assistant")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    stream: bool = Field(False, description="是否流式返回（当前不支持SSE，忽略）")
    task: str = Field("simple", description="任务类型：simple 或 agent")
    temperature: Optional[float] = Field(0.2, ge=0.0, le=1.0)
    max_tokens: Optional[int] = Field(800, ge=1, le=4000)
    system_message: Optional[str] = Field(None, description="自定义 system 提示语")


class ChatResponse(BaseModel):
    success: bool
    message: str
    result: Dict[str, Any]


class EmbeddingRequest(BaseModel):
    text: Optional[str] = Field(
        None,
        description="单条待向量化文本；与 texts 二选一",
        json_schema_extra={"examples": ["知识库如何做权限隔离？"]},
    )
    texts: Optional[List[str]] = Field(
        None,
        description="批量待向量化文本；与 text 二选一",
        json_schema_extra={"examples": [["第一段文本", "第二段文本"]]},
    )
    provider: Optional[str] = Field(
        None,
        description="Embedding提供商：openai/local，默认读取服务配置",
        json_schema_extra={"examples": ["openai"]},
    )


class EmbeddingResult(BaseModel):
    embeddings: List[List[float]]
    dimensions: int
    count: int
    provider: str
    model_name: str


class EmbeddingResponse(BaseModel):
    success: bool
    message: str
    result: Optional[EmbeddingResult]
    status: int
    timestamp: int


EMBED_REQUEST_EXAMPLES = {
    "single_text": {
        "summary": "单条文本转向量",
        "description": "最常见的调用方式，传入一条文本，按当前环境默认的 Embedding 提供商处理。",
        "value": {
            "text": "知识库如何做权限隔离？",
        },
    },
    "batch_texts": {
        "summary": "批量文本转向量",
        "description": "一次提交多条文本，返回同顺序的向量数组。",
        "value": {
            "texts": [
                "设备离线告警如何处理？",
                "边缘网关连接异常怎么排查？",
            ],
            "provider": "openai",
        },
    },
}


EMBED_RESPONSE_EXAMPLES = {
    200: {
        "description": "文本向量化成功",
        "content": {
            "application/json": {
                "example": {
                    "success": True,
                    "message": "ok",
                    "result": {
                        "embeddings": [
                            [0.0123, -0.0456, 0.0789]
                        ],
                        "dimensions": 3,
                        "count": 1,
                        "provider": "openai",
                        "model_name": "text-embedding-3-small",
                    },
                    "status": 200,
                    "timestamp": 1744099200000,
                }
            }
        },
    },
    400: {
        "description": "请求参数错误，例如同时传入 text 和 texts",
        "model": EmbeddingResponse,
        "content": {
            "application/json": {
                "example": {
                    "success": False,
                    "message": "text 和 texts 不能同时传入，请二选一",
                    "result": None,
                    "status": 400,
                    "timestamp": 1744099200000,
                }
            }
        },
    },
    500: {
        "description": "Embedding 后端调用失败",
        "model": EmbeddingResponse,
        "content": {
            "application/json": {
                "example": {
                    "success": False,
                    "message": "文本向量化失败: embedding backend unavailable",
                    "result": None,
                    "status": 500,
                    "timestamp": 1744099200000,
                }
            }
        },
    },
}


def _normalize_embedding_texts(req: EmbeddingRequest) -> List[str]:
    has_text = isinstance(req.text, str) and bool(req.text.strip())
    has_texts = req.texts is not None

    if has_text and has_texts:
        raise ValueError("text 和 texts 不能同时传入，请二选一")

    if has_text:
        return [req.text]

    if not has_texts:
        raise ValueError("text 和 texts 至少需要传入一个")

    if not req.texts:
        raise ValueError("texts 不能为空数组")

    invalid_items = [text for text in req.texts if not isinstance(text, str) or not text.strip()]
    if invalid_items:
        raise ValueError("texts 中不能包含空字符串")

    return req.texts


def _resolve_embedding_provider(provider: Optional[str]) -> LLMProvider:
    config_manager = get_unified_llm_config()
    if not provider or not provider.strip():
        return config_manager.get_default_embedding_provider()

    provider_map = {
        "openai": LLMProvider.OPENAI,
        "local": LLMProvider.LOCAL,
    }

    normalized = provider.strip().lower()
    resolved_provider = provider_map.get(normalized)
    if resolved_provider is None:
        supported = ", ".join(provider_map.keys())
        raise ValueError(f"不支持的 provider: {provider}，当前仅支持 {supported}")

    return resolved_provider


@router.post("/chat", response_model=ChatResponse, summary="统一 LLM 聊天")
async def chat(req: ChatRequest):
    """调用统一 LLM 服务完成一次聊天交互。

    示例：
    curl -X POST \
      -H 'Content-Type: application/json' \
      -d '{"messages":[{"role":"user","content":"你好"}]}' \
      http://localhost:8006/api/v1/llm/chat
    """
    try:
        service = get_unified_llm_service()

        task_type = TaskType.AGENT_CHAT if (req.task or "").lower().startswith("agent") else TaskType.SIMPLE_CHAT

        request = LLMRequest(
            messages=[m.model_dump() for m in req.messages],
            task_type=task_type,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            system_message=req.system_message,
        )

        resp = await service.chat(request)
        return ChatResponse(
            success=True,
            message="ok",
            result={
                "content": resp.content,
                "model_name": resp.model_name,
                "usage": resp.usage,
                "finish_reason": resp.finish_reason,
            }
        )

    except Exception as e:
        logger.error(f"LLM聊天失败: {e}")
        raise HTTPException(status_code=500, detail=f"LLM聊天失败: {e}")


@router.post(
    "/embed",
    response_model=EmbeddingResponse,
    summary="文本转向量",
    description=(
        "将单条或多条文本编码为向量。\n\n"
        "- `text` 与 `texts` 必须二选一\n"
        "- `provider` 可选，支持 `openai`、`local`\n"
        "- 不传 `provider` 时，默认读取 `EMBEDDING_PROVIDER` 配置"
    ),
    response_description="返回向量结果、维度、条数以及实际使用的 Embedding 模型信息",
    responses=EMBED_RESPONSE_EXAMPLES,
)
async def embed(
    req: EmbeddingRequest = Body(
        ...,
        description="文本向量化请求体。单条输入用 text，批量输入用 texts。",
        openapi_examples=EMBED_REQUEST_EXAMPLES,
    )
):
    """调用统一 Embedding 服务完成文本向量化。"""
    try:
        texts = _normalize_embedding_texts(req)
        provider = _resolve_embedding_provider(req.provider)

        service = get_unified_llm_service()
        embeddings = await service.embed(texts, provider=provider)

        embedding_config = get_unified_llm_config().to_embedding_config(provider)
        dimensions = len(embeddings[0]) if embeddings else 0

        return ResponseHelper.success_response(
            result={
                "embeddings": embeddings,
                "dimensions": dimensions,
                "count": len(embeddings),
                "provider": provider.value,
                "model_name": embedding_config.get("model_name", ""),
            },
            message="ok",
        )
    except ValueError as e:
        logger.warning(f"文本向量化请求参数无效: {e}")
        return ResponseHelper.bad_request_response(e.args[0] if e.args else "无效的请求参数")
    except Exception as e:
        logger.error(f"文本向量化失败: {e}")
        return ResponseHelper.error_response(message=f"文本向量化失败: {e}", status=500)
