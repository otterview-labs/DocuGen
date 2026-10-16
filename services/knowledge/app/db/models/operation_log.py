#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
操作日志模型
记录所有重要操作（文档删除、上传、更新等）的详细信息
"""

from sqlalchemy import Column, String, Text, Integer, Boolean, Enum, Index, JSON
from app.db.models.base import BaseModel
import enum


class OperationType(str, enum.Enum):
    """操作类型枚举"""
    CREATE = "CREATE"  # 创建
    UPDATE = "UPDATE"  # 更新
    DELETE = "DELETE"  # 删除
    UPLOAD = "UPLOAD"  # 上传
    DOWNLOAD = "DOWNLOAD"  # 下载


class ResourceType(str, enum.Enum):
    """资源类型枚举"""
    DOCUMENT = "DOCUMENT"  # 文档
    COLLECTION = "COLLECTION"  # 集合
    CHUNK = "CHUNK"  # 分块
    VECTOR = "VECTOR"  # 向量
    KG_ENTITY = "KG_ENTITY"  # 知识图谱实体


class OperationStatus(str, enum.Enum):
    """操作状态枚举"""
    SUCCESS = "SUCCESS"  # 成功
    FAILED = "FAILED"  # 失败
    PARTIAL = "PARTIAL"  # 部分成功


class OperationLog(BaseModel):
    """
    操作日志表
    记录所有重要操作的详细信息，便于问题排查和审计
    """
    __tablename__ = "operation_logs"

    # 操作基本信息
    operation_type = Column(Enum(OperationType), nullable=False, comment="操作类型")
    resource_type = Column(Enum(ResourceType), nullable=False, comment="资源类型")
    resource_id = Column(String(100), nullable=False, comment="资源ID")
    resource_name = Column(String(500), comment="资源名称")

    # 操作结果
    status = Column(Enum(OperationStatus), nullable=False, comment="操作状态")
    error_message = Column(Text, comment="错误信息（如果失败）")

    # 操作详情（JSON格式存储）
    details = Column(JSON, comment="操作详情（如删除的分块数、向量数等）")

    # 操作前后状态（可选）
    before_state = Column(JSON, comment="操作前状态快照")
    after_state = Column(JSON, comment="操作后状态快照")

    # 用户和请求信息
    user_id = Column(String(100), comment="用户ID")
    client_ip = Column(String(50), comment="客户端IP地址")
    user_agent = Column(String(500), comment="用户代理")

    # 关联信息
    collection_id = Column(String(100), comment="关联集合ID（如果适用）")
    parent_resource_id = Column(String(100), comment="父资源ID（如果有层级关系）")

    # 性能信息
    duration_ms = Column(Integer, comment="操作耗时（毫秒）")

    # 索引
    __table_args__ = (
        Index('idx_operation_resource', 'operation_type', 'resource_type', 'created_at'),
        Index('idx_resource_id_created', 'resource_id', 'created_at'),
        Index('idx_operation_status_created', 'status', 'created_at'),
        Index('idx_operation_user_created', 'user_id', 'created_at'),
        Index('idx_operation_collection_created', 'collection_id', 'created_at'),
    )

    def __repr__(self):
        return (
            f"<OperationLog(id={self.id}, "
            f"operation={self.operation_type.value}, "
            f"resource={self.resource_type.value}, "
            f"status={self.status.value})>"
        )
