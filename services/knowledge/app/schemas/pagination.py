#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一分页请求和响应模型
"""

from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


class SortRequest(BaseModel):
    """排序请求"""
    name: str = Field(..., description="排序字段名")
    order: str = Field("desc", description="排序方向: asc 或 desc")
    value: Optional[str] = Field(None, description="排序值")


class PageRequest(BaseModel):
    """标准分页请求"""
    pageIndex: int = Field(0, ge=0, description="页索引，从0开始")
    pageSize: int = Field(12, ge=1, le=100, description="每页数量，最大100")
    sorts: List[SortRequest] = Field(default_factory=list, description="排序条件")
    terms: List[Dict[str, Any]] = Field(default_factory=list, description="查询条件")
    collection_id: Optional[str] = Field(None, description="集合ID，用于筛选特定集合的文档")


class PageResponse(BaseModel):
    """标准分页响应"""
    pageIndex: int = Field(..., description="当前页索引")
    pageSize: int = Field(..., description="每页数量")
    total: int = Field(..., description="总记录数")
    data: List[Dict[str, Any]] = Field(..., description="数据列表")


class BaseResponse(BaseModel):
    """基础API响应"""
    message: str = Field(default="success", description="响应消息")
    result: Any = Field(..., description="响应结果")
    status: int = Field(default=200, description="响应状态码")
    timestamp: int = Field(..., description="时间戳")


class StandardResponse(BaseModel):
    """标准API响应"""
    message: str = Field(default="success", description="响应消息")
    result: PageResponse = Field(..., description="分页结果")
    status: int = Field(default=200, description="响应状态码")
    timestamp: int = Field(..., description="时间戳")
