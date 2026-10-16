#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集合相关 schema。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .common import schema_config


class CollectionCreate(BaseModel):
    """创建或更新集合请求"""

    collection_id: Optional[str] = Field(
        None,
        description="集合ID（可选）：存在则更新；不存在则使用该ID创建；未提供则自动生成ID",
        alias="id",
    )
    name: str = Field(..., description="集合名称", json_schema_extra={"example": "技术文档集合"})
    description: Optional[str] = Field(
        None,
        description="集合描述",
        json_schema_extra={"example": "存储技术文档和API说明"},
    )
    collection_type: str = Field(
        "text",
        description="集合类型：text(文本), multimodal(多模态)",
        json_schema_extra={"example": "text"},
    )
    embedding_model: Optional[str] = Field(
        None,
        description="嵌入模型名称",
        json_schema_extra={"example": "text-embedding-ada-002"},
    )
    rerank_model: Optional[str] = Field(
        None,
        description="重排序模型名称",
        json_schema_extra={"example": "BAAI/bge-reranker-v2-m3"},
    )

    model_config = schema_config(
        populate_by_name=True,
        example={
            "name": "技术文档集合",
            "description": "存储技术文档和API说明",
            "collection_type": "text",
            "embedding_model": "text-embedding-ada-002",
            "rerank_model": "BAAI/bge-reranker-v2-m3",
        },
    )


class CollectionDocumentsRequest(BaseModel):
    """获取集合文档请求"""

    page_index: int = Field(0, ge=0, description="页索引，从0开始", alias="pageIndex")
    page_size: int = Field(100, ge=1, le=100, description="每页数量，最大100", alias="pageSize")
    sorts: List[Dict[str, Any]] = Field(default_factory=list, description="排序条件")
    terms: List[Dict[str, Any]] = Field(default_factory=list, description="查询条件")
    collection_id: str = Field(..., description="集合ID")

    model_config = schema_config(
        populate_by_name=True,
        example={
            "pageIndex": 0,
            "pageSize": 100,
            "sorts": [],
            "terms": [],
            "collection_id": "d8d052bd-f875-48d8-96ba-6de8cddecc4f",
        },
    )


class CollectionDeleteRequest(BaseModel):
    """删除集合请求"""

    collection_id: str = Field(..., description="要删除的集合ID")

    model_config = schema_config(
        example={"collection_id": "d8d052bd-f875-48d8-96ba-6de8cddecc4f"}
    )
