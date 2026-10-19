#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档操作相关 schema。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .common import schema_config


class RelationItem(BaseModel):
    """资源关系项"""

    type: str = Field(..., description="对象类型：device/resource/user等")
    id: str = Field(..., description="对象ID")
    confidence: float = Field(1.0, description="置信度")
    relation: Optional[str] = Field(None, description="关系描述")
    expands: Dict[str, Any] = Field(default_factory=dict, description="扩展属性")


class DocumentUpdateRequest(BaseModel):
    """文档更新请求（兼容字段）"""

    document_id: str = Field(..., alias="id", description="文档ID")
    title: Optional[str] = Field(None, alias="name", description="新标题")
    description: Optional[str] = Field(None, description="新描述")
    tags: Optional[List[Any]] = Field(None, description="新标签")
    bindings: Optional[List[str]] = Field(None, description="权限绑定key列表")
    relation: Optional[List[RelationItem]] = Field(None, description="资源关系列表")

    model_config = schema_config(
        populate_by_name=True,
        example={
            "id": "doc_123456",
            "name": "更新后的标题",
            "description": "更新后的描述",
            "tags": ["标签1", "标签2"],
            "bindings": ["admin", "editor"],
            "relation": [
                {
                    "type": "device",
                    "id": "device-002",
                    "confidence": 0.95,
                    "relation": "相关设备",
                    "expands": {"priority": "high"},
                }
            ],
        },
    )


class DocumentDeleteRequest(BaseModel):
    """文档删除请求"""

    document_id: str = Field(..., alias="resource_id", description="资源ID/文档ID")

    model_config = schema_config(
        populate_by_name=True,
        example={"resource_id": "res_123456"},
    )


class DocumentMoveRequest(BaseModel):
    """文档移动请求"""

    document_id: str = Field(..., alias="resource_id", description="资源ID/文档ID")
    target_collection_id: str = Field(..., description="目标集合ID")

    model_config = schema_config(
        populate_by_name=True,
        example={"resource_id": "res_123456", "target_collection_id": "collection_789"},
    )


class DocumentDuplicateRequest(BaseModel):
    """文档复制请求"""

    document_id: str = Field(..., alias="resource_id", description="资源ID/文档ID")
    target_collection_id: Optional[str] = Field(None, description="目标集合ID，不指定则复制到同一集合")

    model_config = schema_config(
        populate_by_name=True,
        example={"resource_id": "res_123456", "target_collection_id": "collection_789"},
    )


class ReindexRequest(BaseModel):
    """向量重建请求"""

    collection_id: Optional[str] = Field(None, description="仅重建该集合下的文档；为空则重建全部")
    limit: Optional[int] = Field(200, ge=1, le=5000, description="最多处理的文档条数")
    overwrite: Optional[bool] = Field(False, description="是否覆盖已存在向量（总是重建）")


class DocumentGetRequest(BaseModel):
    """获取文档请求"""

    document_id: str = Field(..., alias="resource_id", description="资源ID/文档ID")

    model_config = schema_config(
        populate_by_name=True,
        example={"resource_id": "res_123456"},
    )


class DocumentDownloadRequest(BaseModel):
    """下载文档请求（兼容字段）"""

    document_id: str = Field(..., alias="resource_id", description="资源ID/文档ID")

    model_config = schema_config(
        populate_by_name=True,
        example={"resource_id": "res_123456"},
    )


class BatchToggleStatusRequest(BaseModel):
    """批量切换状态请求"""

    action: str = Field(..., description="操作类型: enable/disable")
    target_type: str = Field(..., description="目标类型: resource_ids/collection_id")
    targets: list = Field(..., description="目标ID列表")
    reason: Optional[str] = Field(None, description="操作原因")


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""

    target_type: str = Field(..., description="目标类型: resource_ids/collection_id")
    targets: list = Field(..., description="目标ID列表")
    delete_files: bool = Field(True, description="是否同时删除关联文件")
    reason: Optional[str] = Field(None, description="删除原因")
    id_type: Optional[str] = Field("content_id", description="当 target_type=resource_ids 时的ID类型: content_id/resource_id")
