#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分页查询辅助函数
"""

import time
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, text, func
from sqlalchemy.orm.query import Query

from app.schemas.pagination import PageRequest, PageResponse, StandardResponse, SortRequest


def apply_sorts_to_query(query: Query, model_class, sorts: List[SortRequest]) -> Query:
    """
    将排序条件应用到SQLAlchemy查询

    Args:
        query: SQLAlchemy查询对象
        model_class: 模型类
        sorts: 排序条件列表

    Returns:
        应用排序后的查询对象
    """
    for sort_req in sorts:
        if hasattr(model_class, sort_req.name):
            field = getattr(model_class, sort_req.name)
            if sort_req.order.lower() == "asc":
                query = query.order_by(asc(field))
            else:
                query = query.order_by(desc(field))
        # 如果字段不存在，跳过该排序条件

    return query


def apply_terms_to_query(query: Query, model_class, terms: List[Dict[str, Any]]) -> Query:
    """
    将查询条件应用到SQLAlchemy查询

    Args:
        query: SQLAlchemy查询对象
        model_class: 模型类
        terms: 查询条件列表

    Returns:
        应用查询条件后的查询对象
    """
    for term in terms:
        field_name = term.get("name") or term.get("column")  # 支持两种字段名格式
        value = term.get("value")
        operator = term.get("termType", "eq")  # 默认为等于

        if not field_name or value is None:
            continue

        if not hasattr(model_class, field_name):
            continue

        field = getattr(model_class, field_name)

        # 根据操作符类型应用条件
        if operator == "eq":
            query = query.filter(field == value)
        elif operator == "like":
            query = query.filter(field.like(f"%{value}%"))
        elif operator == "gt":
            query = query.filter(field > value)
        elif operator == "gte":
            query = query.filter(field >= value)
        elif operator == "lt":
            query = query.filter(field < value)
        elif operator == "lte":
            query = query.filter(field <= value)
        elif operator == "in":
            if isinstance(value, list):
                query = query.filter(field.in_(value))
        elif operator == "not":
            query = query.filter(field != value)
        # 可以根据需要添加更多操作符

    return query


def paginate_query(
    query: Query,
    page_request: PageRequest,
    model_class = None
) -> Tuple[List[Any], int]:
    """
    对查询进行分页处理

    Args:
        query: SQLAlchemy查询对象
        page_request: 分页请求参数
        model_class: 模型类（用于排序和筛选）

    Returns:
        (items, total) 元组，包含当前页数据和总数量
    """
    # 应用查询条件
    if model_class and page_request.terms:
        query = apply_terms_to_query(query, model_class, page_request.terms)

    # 计算总数
    total = query.count()

    # 应用排序
    if model_class and page_request.sorts:
        query = apply_sorts_to_query(query, model_class, page_request.sorts)

    # 应用分页
    offset = page_request.pageIndex * page_request.pageSize
    items = query.offset(offset).limit(page_request.pageSize).all()

    return items, total


def create_page_response(
    items: List[Any],
    total: int,
    page_request: PageRequest,
    item_transformer = None
) -> PageResponse:
    """
    创建标准分页响应

    Args:
        items: 数据项列表
        total: 总数量
        page_request: 分页请求参数
        item_transformer: 数据转换函数，将模型对象转换为字典

    Returns:
        标准分页响应对象
    """
    # 转换数据格式
    if item_transformer:
        data = [item_transformer(item) for item in items]
    else:
        # 默认转换：如果对象有dict()方法就使用，否则转换为基本字典
        data = []
        for item in items:
            if hasattr(item, 'dict'):
                data.append(item.dict())
            elif hasattr(item, '__dict__'):
                # 过滤掉SQLAlchemy内部属性
                item_dict = {}
                for key, value in item.__dict__.items():
                    if not key.startswith('_'):
                        # 处理特殊值类型
                        if hasattr(value, 'isoformat'):  # datetime对象
                            item_dict[key] = int(value.timestamp() * 1000)  # 转换为毫秒时间戳
                        else:
                            item_dict[key] = value
                data.append(item_dict)
            else:
                data.append(dict(item))

    return PageResponse(
        pageIndex=page_request.pageIndex,
        pageSize=page_request.pageSize,
        total=total,
        data=data
    )


def create_standard_response(
    items: List[Any],
    total: int,
    page_request: PageRequest,
    item_transformer = None,
    message: str = "success"
) -> StandardResponse:
    """
    创建标准API响应

    Args:
        items: 数据项列表
        total: 总数量
        page_request: 分页请求参数
        item_transformer: 数据转换函数
        message: 响应消息

    Returns:
        标准API响应对象
    """
    page_response = create_page_response(items, total, page_request, item_transformer)

    return StandardResponse(
        message=message,
        result=page_response,
        status=200,
        timestamp=int(time.time() * 1000)
    )


# 便捷函数：直接从数据库查询并返回标准响应
def paginate_and_response(
    db: Session,
    model_class,
    page_request: PageRequest,
    base_query: Optional[Query] = None,
    item_transformer = None,
    message: str = "success"
) -> StandardResponse:
    """
    便捷函数：执行分页查询并返回标准响应

    Args:
        db: 数据库会话
        model_class: 模型类
        page_request: 分页请求
        base_query: 基础查询（可选，如果不提供则查询所有记录）
        item_transformer: 数据转换函数
        message: 响应消息

    Returns:
        标准API响应
    """
    if base_query is None:
        base_query = db.query(model_class)

    items, total = paginate_query(base_query, page_request, model_class)

    return create_standard_response(
        items=items,
        total=total,
        page_request=page_request,
        item_transformer=item_transformer,
        message=message
    )
