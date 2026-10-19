#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API请求日志模型
记录所有API接口的请求和响应信息
"""

from sqlalchemy import Column, String, Text, Integer, Float, DateTime, Index
from sqlalchemy.sql import func
from app.db.models.base import BaseModel


class APIRequestLog(BaseModel):
    """
    API请求日志表
    记录每次API调用的详细信息
    """
    __tablename__ = "api_request_logs"

    # 请求基本信息
    method = Column(String(10), nullable=False, comment="请求方法: GET/POST/PUT/DELETE")
    endpoint = Column(String(500), nullable=False, comment="请求端点路径")
    client_ip = Column(String(50), comment="客户端IP地址")
    user_agent = Column(String(500), comment="用户代理")

    # 请求参数
    query_params = Column(Text, comment="URL查询参数(JSON格式)")
    request_body = Column(Text, comment="请求体内容(JSON格式)")

    # 响应信息
    status_code = Column(Integer, comment="HTTP响应状态码")
    response_body = Column(Text, comment="响应体内容(JSON格式)")
    response_time = Column(Float, comment="响应时间(毫秒)")

    # 错误信息
    error_message = Column(Text, comment="错误信息(如果有)")

    # 业务相关
    user_id = Column(String(100), comment="用户ID")
    collection_id = Column(String(100), comment="集合ID(RAG相关)")
    search_query = Column(Text, comment="搜索查询内容(RAG相关)")
    search_mode = Column(String(50), comment="搜索模式(RAG相关)")
    result_count = Column(Integer, comment="返回结果数量")

    # 索引
    __table_args__ = (
        Index('idx_endpoint_created', 'endpoint', 'created_at'),
        Index('idx_user_created', 'user_id', 'created_at'),
        Index('idx_collection_created', 'collection_id', 'created_at'),
        Index('idx_status_created', 'status_code', 'created_at'),
    )

    def __repr__(self):
        return f"<APIRequestLog(id={self.id}, endpoint={self.endpoint}, status={self.status_code})>"
