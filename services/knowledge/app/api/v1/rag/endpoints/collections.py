#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG集合API接口
"""

from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import false
import uuid
import json
from datetime import datetime

from app.api.v1.deps import get_optional_request_user, get_request_user, is_auth_enforced
from app.db.session import get_db
from app.db.models import RAGCollection, RAGContent, User
# from app.db.models.rag import RAGCollectionContent  # 已废弃，统一使用vector_collection字段
from app.schemas.collections import CollectionCreate, CollectionDeleteRequest, CollectionDocumentsRequest
from app.shared.response_models import ResponseHelper
from app.schemas.pagination import PageRequest, StandardResponse
from app.shared.helpers.pagination import paginate_and_response
from app.core.rag.vector_db import get_vector_db
try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=Dict)
async def create_collection(
    collection: CollectionCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_request_user),
):
    """
    创建或更新RAG集合接口（Upsert操作）

    创建一个新的RAG集合，或更新已存在的集合。

    **功能特点：**
    - 支持文本和多模态集合类型
    - 可自定义嵌入模型和重排序模型
    - 自动创建向量索引
    - 支持集合级别的权限管理
    - 支持Upsert操作：
      * 提供collection_id且存在：更新该集合
      * 提供collection_id但不存在：使用该ID创建新集合
      * 不提供collection_id：自动生成ID创建新集合

    **请求示例：**

    1. 创建新集合（自动生成ID）：
    ```bash
    curl -X POST "http://localhost:8006/api/v1/rag/collections/" \
      -H "Authorization: Bearer your_token" \
      -H "Content-Type: application/json" \
      -d '{
        "name": "技术文档集合",
        "description": "存储技术文档和API说明",
        "collection_type": "text",
        "embedding_model": "text-embedding-ada-002",
        "rerank_model": "BAAI/bge-reranker-v2-m3"
      }'
    ```

    2. 使用指定ID创建新集合：
    ```bash
    curl -X POST "http://localhost:8006/api/v1/rag/collections/" \
      -H "Content-Type: application/json" \
      -d '{
        "collection_id": "custom-collection-001",
        "name": "自定义集合",
        "description": "使用自定义ID的集合",
        "collection_type": "multimodal"
      }'
    ```

    3. 更新已存在的集合：
    ```bash
    curl -X POST "http://localhost:8006/api/v1/rag/collections/" \
      -H "Content-Type: application/json" \
      -d '{
        "collection_id": "custom-collection-001",
        "name": "更新后的集合名称",
        "description": "更新后的描述"
      }'
    ```

    **响应示例：**
    ```json
    {
        "success": true,
        "data": {
            "id": "collection_123",
            "name": "技术文档集合",
            "description": "存储技术文档和API说明",
            "collection_type": "text"
        }
    }
    ```
    """
    try:
        # 如果提供 collection_id：检查是否存在
        if collection.collection_id:
            existing_by_id = db.query(RAGCollection).filter(RAGCollection.id == collection.collection_id)
            if current_user:
                existing_by_id = existing_by_id.filter(RAGCollection.user_id == str(current_user.id))
            existing = existing_by_id.first()
            if existing:
                # 更新现有集合：名称如变化需校验唯一性
                if collection.name and collection.name != existing.name:
                    name_dup = db.query(RAGCollection).filter(
                        RAGCollection.name == collection.name,
                        RAGCollection.id != existing.id
                    ).first()
                    if name_dup:
                        raise HTTPException(status_code=400, detail=f"集合名称 '{collection.name}' 已存在")
                    existing.name = collection.name
                existing.description = collection.description
                existing.collection_type = collection.collection_type
                existing.embedding_model = collection.embedding_model
                existing.rerank_model = collection.rerank_model
                existing.update_time = datetime.utcnow()
                db.commit()
                db.refresh(existing)
                return ResponseHelper.success_response(
                    result={
                        "id": existing.id,
                        "name": existing.name,
                        "description": existing.description,
                        "collection_type": existing.collection_type,
                        "embedding_model": existing.embedding_model,
                        "rerank_model": existing.rerank_model,
                        "create_time": existing.create_time.isoformat() if existing.create_time else None,
                        "update_time": existing.update_time.isoformat() if existing.update_time else None,
                        "status": existing.status,
                        "is_public": existing.is_public
                    },
                    message="集合已更新"
                )
            else:
                # collection_id不存在，使用该ID创建新集合
                # 先检查名称是否已存在
                existing_by_name = db.query(RAGCollection).filter(RAGCollection.name == collection.name).first()
                if existing_by_name:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                      detail=f"集合名称 '{collection.name}' 已被其他集合使用")

                # 使用指定的collection_id创建新集合
                new_collection = RAGCollection(
                    id=collection.collection_id,
                    name=collection.name,
                    description=collection.description,
                    collection_type=collection.collection_type,
                    embedding_model=collection.embedding_model,
                    rerank_model=collection.rerank_model,
                    user_id=str(current_user.id) if current_user else "anonymous",
                    status="1",
                    is_public=True if not current_user else False,
                    create_time=datetime.utcnow(),
                    update_time=datetime.utcnow()
                )
                db.add(new_collection)
                db.commit()
                db.refresh(new_collection)

                # 创建对应的Milvus集合
                try:
                    vector_db = get_vector_db()
                    if vector_db:
                        # 使用集合ID创建Milvus集合（会自动处理命名规则）
                        success = vector_db.create_collection(
                            collection_name=new_collection.id,
                            dimension=1536
                        )
                        if success:
                            logger.info(f"成功创建Milvus集合: {new_collection.id}")
                        else:
                            logger.warning(f"Milvus集合创建返回False: {new_collection.id}")
                except Exception as e:
                    logger.error(f"创建Milvus集合失败: {e}")
                    # 不影响MySQL记录的创建，继续返回成功

                return ResponseHelper.created_response(
                    result={
                        "id": new_collection.id,
                        "name": new_collection.name,
                        "description": new_collection.description,
                        "collection_type": new_collection.collection_type,
                        "embedding_model": new_collection.embedding_model,
                        "rerank_model": new_collection.rerank_model,
                        "create_time": new_collection.create_time.isoformat(),
                        "update_time": new_collection.update_time.isoformat(),
                        "status": new_collection.status,
                        "is_public": new_collection.is_public
                    },
                    message="集合创建成功（使用指定ID）"
                )

        # 未提供 collection_id：检查名称是否重复
        existing_by_name = db.query(RAGCollection).filter(RAGCollection.name == collection.name).first()
        if existing_by_name:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                              detail=f"集合名称 '{collection.name}' 已存在，请提供不同的名称或使用已存在的 collection_id 进行更新")

        # 创建新集合（自动生成ID）
        new_collection = RAGCollection(
            id=str(uuid.uuid4()),
            name=collection.name,
            description=collection.description,
            collection_type=collection.collection_type,
            embedding_model=collection.embedding_model,
            rerank_model=collection.rerank_model,
            user_id=str(current_user.id) if current_user else "anonymous",
            status="1",
            is_public=True if not current_user else False,
            create_time=datetime.utcnow(),
            update_time=datetime.utcnow()
        )
        db.add(new_collection)
        db.commit()
        db.refresh(new_collection)

        # 创建对应的Milvus集合
        try:
            vector_db = get_vector_db()
            if vector_db:
                # 使用集合ID创建Milvus集合（会自动处理命名规则）
                success = vector_db.create_collection(
                    collection_name=new_collection.id,
                    dimension=1536
                )
                if success:
                    logger.info(f"成功创建Milvus集合: {new_collection.id}")
                else:
                    logger.warning(f"Milvus集合创建返回False: {new_collection.id}")
        except Exception as e:
            logger.error(f"创建Milvus集合失败: {e}")
            # 不影响MySQL记录的创建，继续返回成功

        return ResponseHelper.created_response(
            result={
                "id": new_collection.id,
                "name": new_collection.name,
                "description": new_collection.description,
                "collection_type": new_collection.collection_type,
                "embedding_model": new_collection.embedding_model,
                "rerank_model": new_collection.rerank_model,
                "create_time": new_collection.create_time.isoformat(),
                "update_time": new_collection.update_time.isoformat(),
                "status": new_collection.status,
                "is_public": new_collection.is_public
            },
            message="集合创建成功"
        )
    except HTTPException:
        # 重新抛出HTTP异常（比如重名检查失败）
        raise
    except Exception as e:
        return ResponseHelper.error_response(
            message=f"创建集合失败: {str(e)}",
            status=500
        )


@router.post("/search", response_model=StandardResponse)
async def search_collections(
    page_request: PageRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_request_user),
):
    """
    搜索RAG集合 - 标准分页格式

    支持按名称、描述、类型等条件搜索知识库集合。

    **请求示例：**
    ```bash
    curl -X POST "http://localhost:8006/api/v1/rag/collections/search" \
      -H "Content-Type: application/json" \
      -d '{
        "pageIndex": 0,
        "pageSize": 12,
        "sorts": [{"name": "createTime", "order": "desc"}],
        "terms": [
          {"column": "name", "value": "技术", "termType": "like"},
          {"column": "collection_type", "value": "text", "termType": "eq"}
        ]
      }'
    ```

    **支持的搜索条件：**
    - `name`: 按集合名称搜索（支持模糊匹配）
    - `description`: 按描述搜索（支持模糊匹配）
    - `collection_type`: 按类型筛选（精确匹配）
    - `status`: 按状态筛选
    """
    try:
        # 构建基础查询
        query = _apply_read_access_filter(db.query(RAGCollection), RAGCollection, current_user)

        # 处理搜索条件
        for term in page_request.terms:
            field = term.get("column")
            value = term.get("value")
            term_type = term.get("termType", "eq")

            if field == "name":
                if term_type == "like":
                    query = query.filter(RAGCollection.name.like(f"%{value}%"))
                else:
                    query = query.filter(RAGCollection.name == value)
            elif field == "description":
                if term_type == "like":
                    query = query.filter(RAGCollection.description.like(f"%{value}%"))
                else:
                    query = query.filter(RAGCollection.description == value)
            elif field == "collection_type":
                query = query.filter(RAGCollection.collection_type == value)
            elif field == "status":
                query = query.filter(RAGCollection.status == value)

        # 集合数据转换函数
        def transform_collection(collection: RAGCollection) -> dict:
            # 计算该集合的文档数量
            doc_count = db.query(RAGContent).filter(
                RAGContent.vector_collection == collection.id
            ).count()

            return {
                "id": collection.id,
                "name": collection.name,
                "description": collection.description,
                "collection_type": collection.collection_type,
                "embedding_model": collection.embedding_model,
                "rerank_model": collection.rerank_model,
                "config": {},
                "status": 1 if collection.status == "1" else 0,
                "document_count": doc_count,
                "createTime": int(collection.create_time.timestamp() * 1000) if collection.create_time else None,
                "modifyTime": int(collection.update_time.timestamp() * 1000) if collection.update_time else None,
                "creatorId": collection.user_id,
                "creatorName": "用户",
                "is_public": collection.is_public if hasattr(collection, 'is_public') else False
            }

        return paginate_and_response(
            db=db,
            model_class=RAGCollection,
            page_request=page_request,
            base_query=query,
            item_transformer=transform_collection,
            message="搜索集合成功"
        )

    except Exception as e:
        return ResponseHelper.error_response(f"搜索集合失败: {str(e)}", status=500)


@router.post("/find", response_model=Dict)
async def find_collections(
    request: Dict,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_request_user),
):
    """
    简单查找集合接口

    快速查找集合，支持关键词搜索。

    **请求示例：**
    ```bash
    curl -X POST "http://localhost:8006/api/v1/rag/collections/find" \
      -H "Content-Type: application/json" \
      -d '{
        "keyword": "技术文档",
        "collection_type": "text",
        "limit": 10
      }'
    ```
    """
    try:
        keyword = request.get("keyword", "")
        collection_type = request.get("collection_type")
        limit = min(request.get("limit", 10), 50)  # 最多返回50个

        # 构建查询
        query = _apply_read_access_filter(db.query(RAGCollection), RAGCollection, current_user)

        # 关键词搜索
        if keyword:
            query = query.filter(
                (RAGCollection.name.like(f"%{keyword}%")) |
                (RAGCollection.description.like(f"%{keyword}%"))
            )

        # 类型筛选
        if collection_type:
            query = query.filter(RAGCollection.collection_type == collection_type)

        # 执行查询
        collections = query.order_by(
            RAGCollection.update_time.desc()
        ).limit(limit).all()

        # 格式化结果
        results = []
        for collection in collections:
            # 计算文档数量
            doc_count = db.query(RAGContent).filter(
                RAGContent.vector_collection == collection.id
            ).count()

            results.append({
                "id": collection.id,
                "name": collection.name,
                "description": collection.description,
                "collection_type": collection.collection_type,
                "document_count": doc_count,
                "create_time": collection.create_time.isoformat() if collection.create_time else None,
                "update_time": collection.update_time.isoformat() if collection.update_time else None,
                "is_public": collection.is_public,
                "status": collection.status
            })

        return ResponseHelper.success_response(
            result={
                "collections": results,
                "total": len(results),
                "keyword": keyword,
                "collection_type": collection_type
            },
            message=f"找到 {len(results)} 个集合"
        )

    except Exception as e:
        return ResponseHelper.error_response(
            message=f"查找集合失败: {str(e)}",
            status=500
        )


@router.post("/list", response_model=StandardResponse)
async def get_collections_paginated(
    page_request: PageRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_request_user),
):
    """
    获取RAG集合列表 - 标准分页格式
    """
    try:
        # 构建基础查询
        query = _apply_read_access_filter(db.query(RAGCollection), RAGCollection, current_user)

        # 从terms中提取查询条件
        for term in page_request.terms:
            field = term.get("column")
            value = term.get("value")
            if field == "collection_type":
                query = query.filter(RAGCollection.collection_type == value)
            elif field == "name":
                query = query.filter(RAGCollection.name.like(f"%{value}%"))

        # 集合数据转换函数
        def transform_collection(collection: RAGCollection) -> dict:
            # 查询该集合的文档数量
            doc_count = db.query(RAGContent).filter(
                RAGContent.vector_collection == collection.id
            ).count()

            return {
                "id": collection.id,
                "name": collection.name,
                "description": collection.description,
                "collection_type": collection.collection_type,
                "embedding_model": collection.embedding_model,
                "rerank_model": collection.rerank_model,
                "config": {},  # 如果需要config字段，可以添加到模型中
                "status": 1 if collection.status == "1" else 0,
                "document_count": doc_count,  # 使用实际查询的文档数量
                "doc_count": doc_count,  # 兼容前端使用的字段名
                "createTime": int(collection.create_time.timestamp() * 1000) if collection.create_time else None,
                "modifyTime": int(collection.update_time.timestamp() * 1000) if collection.update_time else None,
                "creatorId": collection.user_id,
                "creatorName": "用户",
                "is_public": collection.is_public if hasattr(collection, 'is_public') else False
            }

        return paginate_and_response(
            db=db,
            model_class=RAGCollection,
            page_request=page_request,
            base_query=query,
            item_transformer=transform_collection,
            message="success"
        )

    except Exception as e:
        return ResponseHelper.error_response(f"获取集合列表失败: {str(e)}", status=500)


def _apply_read_access_filter(query, model_class, current_user: Optional[User] = None):
    if current_user:
        return query.filter(
            (model_class.user_id == str(current_user.id)) |
            (model_class.is_public == True)
        )
    if is_auth_enforced():
        return query.filter(model_class.is_public == True)
    return query


def _apply_owner_filter(query, model_class, current_user: Optional[User] = None):
    if current_user:
        return query.filter(model_class.user_id == str(current_user.id))
    if is_auth_enforced():
        return query.filter(false())
    return query


def _build_collection_read_query(
    db: Session,
    collection_id: str,
    current_user: Optional[User] = None
):
    query = db.query(RAGCollection).filter(RAGCollection.id == collection_id)
    return _apply_read_access_filter(query, RAGCollection, current_user)


def _build_owned_collection_query(
    db: Session,
    collection_id: str,
    current_user: Optional[User] = None
):
    query = db.query(RAGCollection).filter(RAGCollection.id == collection_id)
    return _apply_owner_filter(query, RAGCollection, current_user)


def _serialize_collection(db: Session, collection: RAGCollection) -> dict:
    doc_count = db.query(RAGContent).filter(
        RAGContent.vector_collection == collection.id
    ).count()

    return {
        "id": collection.id,
        "name": collection.name,
        "description": collection.description,
        "collection_type": collection.collection_type,
        "embedding_model": collection.embedding_model,
        "rerank_model": collection.rerank_model,
        "config": {},
        "status": int(collection.status) if str(collection.status).isdigit() else collection.status,
        "document_count": doc_count,
        "doc_count": doc_count,
        "createTime": int(collection.create_time.timestamp() * 1000) if collection.create_time else None,
        "modifyTime": int(collection.update_time.timestamp() * 1000) if collection.update_time else None,
        "creatorId": collection.user_id,
        "creatorName": "用户",
        "is_public": collection.is_public
    }


async def _delete_collection_by_id(
    collection_id: str,
    db: Session,
    current_user: Optional[User] = None
):
    if not collection_id:
        raise HTTPException(status_code=400, detail="缺少必要参数: collection_id")

    collection = _build_owned_collection_query(db, collection_id, current_user).first()
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="集合不存在或无权限删除"
        )

    from app.api.v1.rag.endpoints.document_operations import _cascade_delete_document
    documents = db.query(RAGContent).filter(RAGContent.vector_collection == collection_id).all()
    deleted_docs = 0
    failed_docs = 0
    cleanup_errors = []
    for document in documents:
        result = await _cascade_delete_document(document, db, delete_files=True)
        cleanup_errors.extend(result.get("errors", []))
        deleted_docs += 1
    db.flush()

    try:
        vector_db = get_vector_db()
        if vector_db.collection_exists(collection_id):
            vector_db.delete_collection(collection_id)
    except Exception:
        pass

    try:
        collection_name = collection.name
        db.delete(collection)
        db.commit()
    except Exception as exc:
        db.rollback()
        return ResponseHelper.error_response(
            message=f"删除集合记录失败: {str(exc)}",
            status=500
        )

    return ResponseHelper.success_response(
        result={
            "deleted_collection_id": collection_id,
            "deleted_documents_count": deleted_docs,
            "failed_documents_count": failed_docs,
            "cleanup_errors": cleanup_errors
        },
        message=f"集合 '{collection_name}' 删除完成，文档成功 {deleted_docs} 个，失败 {failed_docs} 个"
    )


@router.post("/documents", response_model=StandardResponse)
async def get_collection_documents(
    request: CollectionDocumentsRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_request_user),
):
    """
    获取指定集合的文档列表（标准分页格式）

    使用标准分页格式返回指定集合中的所有文档，支持多种状态筛选。

    **请求示例：**

    1. 获取所有文档：
    ```bash
    curl -X POST "http://localhost:8006/api/v1/rag/collections/documents" \
      -H "Content-Type: application/json" \
      -d '{
        "pageIndex": 0,
        "pageSize": 100,
        "sorts": [],
        "terms": [],
        "collection_id": "d8d052bd-f875-48d8-96ba-6de8cddecc4f"
      }'
    ```

    2. 只获取处理中的文档：
    ```bash
    curl -X POST "http://localhost:8006/api/v1/rag/collections/documents" \
      -H "Content-Type: application/json" \
      -d '{
        "pageIndex": 0,
        "pageSize": 100,
        "sorts": [],
        "terms": [
          {"column": "processing_status", "value": "processing", "termType": "eq"}
        ],
        "collection_id": "d8d052bd-f875-48d8-96ba-6de8cddecc4f"
      }'
    ```

    3. 获取处理完成和失败的文档：
    ```bash
    curl -X POST "http://localhost:8006/api/v1/rag/collections/documents" \
      -H "Content-Type: application/json" \
      -d '{
        "pageIndex": 0,
        "pageSize": 100,
        "sorts": [],
        "terms": [
          {"column": "processing_status", "value": ["completed", "failed"], "termType": "in"}
        ],
        "collection_id": "d8d052bd-f875-48d8-96ba-6de8cddecc4f"
      }'
    ```

    **支持的筛选条件：**
    - `processing_status`: 处理状态筛选
      - 支持操作: `eq`(等于), `ne`(不等于), `in`(包含于列表)
      - 值: `pending`, `processing`, `completed`, `failed`
    - `status`: 基本状态筛选 (0-禁用, 1-启用)
    - `content_type`: 内容类型筛选 (支持 `eq`, `in`)
    - `title` 或 `name`: 标题/名称搜索
      - 支持操作: `eq`(精确匹配), `ne`(不等于), `like`(模糊匹配)
    - `file_name`: 文件名搜索 (支持 `eq`, `like`)
    - `description`: 描述搜索 (支持 `like`)
    - `file_size`: 文件大小筛选 (支持 `eq`, `gt`, `lt`)
    - `tags`: 标签筛选 (基于content_tags字段)
      - 支持操作: `like`(包含), `not_like`(不包含), `eq`(精确匹配), `ne`(排除)
      - 注意: 标签存储为JSON数组格式，所有操作都支持字符串和数组两种value格式
      - `like`: 模糊匹配
        - 字符串: `"火"` 匹配包含"火"的任意标签
        - 数组: `["火", "消防"]` 匹配包含"火"或"消防"的标签（OR逻辑，相当于in）
      - `not_like`: 不包含匹配
        - 字符串: `"测试"` 排除包含"测试"的文档
        - 数组: `["测试", "demo"]` 排除包含"测试"且包含"demo"的文档（AND逻辑）
      - `eq`: 精确查找标签
        - 字符串: `"火灾"` 匹配标签列表中的完整"火灾"标签
        - 数组: `["火灾", "水灾"]` 匹配包含"火灾"或"水灾"精确标签的文档（OR逻辑）
      - `ne`: 排除精确标签
        - 字符串: `"火灾"` 排除包含精确"火灾"标签的文档
        - 数组: `["火灾", "水灾"]` 排除包含"火灾"且排除"水灾"的文档（AND逻辑）

    **LIKE 查询通配符处理：**
    - 如果 value 包含 `%`，将直接使用 (如: `"%test%"`, `"test%"`, `"%test"`)
    - 如果 value 不包含 `%`，自动添加前后通配符 (如: `"test"` → `"%test%"`)

    **逻辑操作符支持：**
    - 使用 `type` 字段指定条件组合逻辑: `"and"`(默认) 或 `"or"`
    - 支持嵌套条件分组

    **复杂查询示例：**

    4. 自定义 LIKE 通配符位置：
    ```bash
    curl -X POST "http://localhost:8006/api/v1/rag/collections/documents" \
      -H "Content-Type: application/json" \
      -d '{
        "pageIndex": 0,
        "pageSize": 12,
        "terms": [
          {
            "terms": [
              {"column": "title", "termType": "like", "value": "%test%", "type": "or"}
            ]
          }
        ],
        "collection_id": "22cda501-80dc-4d06-b5e3-0192ad55dd71"
      }'
    ```

    5. OR 条件查询：
    ```bash
    curl -X POST "http://localhost:8006/api/v1/rag/collections/documents" \
      -H "Content-Type: application/json" \
      -d '{
        "terms": [
          {
            "type": "or",
            "terms": [
              {"column": "title", "termType": "like", "value": "文档"},
              {"column": "file_name", "termType": "like", "value": ".pdf"}
            ]
          }
        ],
        "collection_id": "your-collection-id"
      }'
    ```

    6. 复杂混合条件 (AND + OR)：
    ```bash
    curl -X POST "http://localhost:8006/api/v1/rag/collections/documents" \
      -H "Content-Type: application/json" \
      -d '{
        "terms": [
          {"column": "processing_status", "termType": "eq", "value": "completed"},
          {
            "type": "or",
            "terms": [
              {"column": "title", "termType": "like", "value": "技术"},
              {"column": "content_type", "termType": "eq", "value": "document"}
            ]
          }
        ],
        "collection_id": "your-collection-id"
      }'
    ```

    7. 标签筛选示例（字符串）：
    ```bash
    curl -X POST "http://localhost:8006/api/v1/rag/collections/documents" \
      -H "Content-Type: application/json" \
      -d '{
        "terms": [
          {"column": "tags", "termType": "like", "value": "火"}
        ],
        "collection_id": "your-collection-id"
      }'
    ```

    8. 标签筛选示例（数组，相当于in）：
    ```bash
    curl -X POST "http://localhost:8006/api/v1/rag/collections/documents" \
      -H "Content-Type: application/json" \
      -d '{
        "terms": [
          {"column": "tags", "termType": "like", "value": ["火灾", "消防"]}
        ],
        "collection_id": "your-collection-id"
      }'
    ```

    9. 排除标签示例（数组）：
    ```bash
    curl -X POST "http://localhost:8006/api/v1/rag/collections/documents" \
      -H "Content-Type: application/json" \
      -d '{
        "terms": [
          {"column": "tags", "termType": "not_like", "value": ["测试", "demo"]}
        ],
        "collection_id": "your-collection-id"
      }'
    ```

    **生成的 SQL 逻辑：**
    - 示例4: `title LIKE '%test%'`
    - 示例5: `(title LIKE '%文档%' OR file_name LIKE '%.pdf%')`
    - 示例6: `processing_status = 'completed' AND (title LIKE '%技术%' OR content_type = 'document')`
    - 示例7: `content_tags LIKE '%火%'`
    - 示例8: `(content_tags LIKE '%火灾%' OR content_tags LIKE '%消防%')`
    - 示例9: `content_tags NOT LIKE '%测试%' AND content_tags NOT LIKE '%demo%'`

    **支持嵌套terms结构：**
    ```json
    {
      "terms": [
        {
          "terms": [
            {"column": "name", "termType": "like", "value": "test"}
          ]
        }
      ]
    }
    ```

    **或直接结构：**
    ```json
    {
      "terms": [
        {"column": "name", "termType": "like", "value": "test"}
      ]
    }
    ```

    **返回状态字段说明：**
    - `status`: 基本启用状态（0/1）
    - `processing_status`: 处理状态（pending/processing/completed/failed）
    - `processing_status_text`: 状态中文描述
    - `processing_message`: 处理消息（错误信息或进度）
    - `is_processing`: 是否在处理中（boolean）
    - `is_completed`: 是否处理完成（boolean）
    - `is_failed`: 是否处理失败（boolean）
    - `has_vectors`: 是否已生成向量（boolean）
    - `file_url`: 媒体文件访问URL（仅图片和视频类型包含此字段）

    **媒体文件访问：**
    - 对于 `content_type` 为 "image" 或 "video" 的文档，响应中会包含 `file_url` 字段
    - `file_url` 提供直接访问媒体文件的URL路径
    - 用户可通过此URL在浏览器中查看图片或播放视频
    - URL格式：`/uploads/{md5_hash}{file_extension}` (为了安全性，文件名使用MD5哈希)
    - 示例：`/uploads/abc123def456.jpg`, `/uploads/789xyz012.mp4`
    """
    try:
        from app.db.models.rag import RAGContent

        collection = _build_collection_read_query(db, request.collection_id, current_user).first()
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="集合不存在或无权限访问"
            )

        # 构建基础查询
        query = _apply_read_access_filter(
            db.query(RAGContent).filter(
                RAGContent.vector_collection == request.collection_id
            ),
            RAGContent,
            current_user,
        )

        # 处理筛选条件（支持嵌套terms结构和逻辑操作符）
        def process_terms(terms_list, query, logic_type="and"):
            """
            递归处理嵌套的terms结构，支持AND/OR逻辑

            Args:
                terms_list: 条件列表
                query: SQLAlchemy查询对象
                logic_type: 逻辑类型 "and" 或 "or"
            """
            import logging
            from sqlalchemy import or_, and_
            logger = logging.getLogger(__name__)

            if not terms_list:
                return query

            # 收集当前级别的所有条件
            conditions = []

            for term in terms_list:
                # 检查是否有嵌套的terms结构
                if "terms" in term and isinstance(term["terms"], list):
                    nested_logic_type = term.get("type", "and").lower()
                    logger.info(f"处理嵌套terms: {term['terms']}, 逻辑类型: {nested_logic_type}")

                    # 对于嵌套条件，我们需要构建子查询条件
                    nested_conditions = []
                    for nested_term in term["terms"]:
                        condition = build_single_condition(nested_term, logger)
                        if condition is not None:
                            nested_conditions.append(condition)

                    # 根据逻辑类型组合嵌套条件
                    if nested_conditions:
                        if nested_logic_type == "or":
                            combined_condition = or_(*nested_conditions)
                        else:
                            combined_condition = and_(*nested_conditions)
                        conditions.append(combined_condition)
                    continue

                # 处理单个条件
                condition = build_single_condition(term, logger)
                if condition is not None:
                    conditions.append(condition)

            # 应用当前级别的条件
            if conditions:
                if logic_type == "or":
                    query = query.filter(or_(*conditions))
                    logger.info(f"应用OR条件组: {len(conditions)}个条件")
                else:
                    query = query.filter(and_(*conditions))
                    logger.info(f"应用AND条件组: {len(conditions)}个条件")

            return query

        def build_single_condition(term, logger):
            """构建单个查询条件"""
            from sqlalchemy import or_, and_

            field = term.get("column")
            value = term.get("value")
            term_type = term.get("termType", "eq")

            logger.info(f"构建筛选条件: field={field}, value={value}, term_type={term_type}")

            if not field or value is None:
                logger.warning(f"跳过无效的筛选条件: {term}")
                return None

            try:
                if field == "processing_status":
                    # 处理状态筛选
                    if term_type == "eq":
                        condition = RAGContent.processing_status == value
                        logger.info(f"构建处理状态筛选: processing_status == {value}")
                        return condition
                    elif term_type == "in" and isinstance(value, list):
                        condition = RAGContent.processing_status.in_(value)
                        logger.info(f"构建处理状态筛选: processing_status in {value}")
                        return condition
                    elif term_type == "ne":
                        condition = RAGContent.processing_status != value
                        logger.info(f"构建处理状态筛选: processing_status != {value}")
                        return condition

                elif field == "status":
                    # 基本状态筛选
                    condition = RAGContent.status == str(value)
                    logger.info(f"构建基本状态筛选: status == {value}")
                    return condition

                elif field == "content_type":
                    # 内容类型筛选
                    if term_type == "eq":
                        condition = RAGContent.content_type == value
                        logger.info(f"构建内容类型筛选: content_type == {value}")
                        return condition
                    elif term_type == "in" and isinstance(value, list):
                        condition = RAGContent.content_type.in_(value)
                        logger.info(f"构建内容类型筛选: content_type in {value}")
                        return condition

                elif field in ["title", "name"]:  # 同时支持title和name字段
                    # 标题/名称搜索
                    if term_type == "like":
                        # 如果值中已包含%，直接使用；否则自动添加
                        if "%" in value:
                            like_value = value
                        else:
                            like_value = f"%{value}%"
                        condition = RAGContent.title.like(like_value)
                        logger.info(f"构建标题模糊筛选: title LIKE '{like_value}'")
                        return condition
                    elif term_type == "eq":
                        condition = RAGContent.title == value
                        logger.info(f"构建标题精确筛选: title == '{value}'")
                        return condition
                    elif term_type == "ne":
                        condition = RAGContent.title != value
                        logger.info(f"构建标题排除筛选: title != '{value}'")
                        return condition

                elif field == "file_name":
                    # 文件名搜索
                    if term_type == "like":
                        # 如果值中已包含%，直接使用；否则自动添加
                        if "%" in value:
                            like_value = value
                        else:
                            like_value = f"%{value}%"
                        condition = RAGContent.file_name.like(like_value)
                        logger.info(f"构建文件名模糊筛选: file_name LIKE '{like_value}'")
                        return condition
                    elif term_type == "eq":
                        condition = RAGContent.file_name == value
                        logger.info(f"构建文件名精确筛选: file_name == '{value}'")
                        return condition

                elif field == "description":
                    # 描述搜索
                    if term_type == "like":
                        if "%" in value:
                            like_value = value
                        else:
                            like_value = f"%{value}%"
                        condition = RAGContent.description.like(like_value)
                        logger.info(f"构建描述模糊筛选: description LIKE '{like_value}'")
                        return condition

                elif field == "file_size":
                    # 文件大小筛选
                    if term_type == "gt":
                        condition = RAGContent.file_size > int(value)
                        logger.info(f"构建文件大小筛选: file_size > {value}")
                        return condition
                    elif term_type == "lt":
                        condition = RAGContent.file_size < int(value)
                        logger.info(f"构建文件大小筛选: file_size < {value}")
                        return condition
                    elif term_type == "eq":
                        condition = RAGContent.file_size == int(value)
                        logger.info(f"构建文件大小筛选: file_size == {value}")
                        return condition

                elif field == "tags":
                    # 标签筛选 - 使用JSON函数（兼容字符串存储回退）
                    from sqlalchemy import or_, and_
                    import json as _json

                    def json_contains(tag: str):
                        return or_(
                            func.JSON_CONTAINS(RAGContent.content_tags, _json.dumps(tag)),
                            RAGContent.content_tags.like(f'%"{tag}"%'),
                            RAGContent.content_tags.like(f'%{tag}%')
                        )

                    def json_search(pattern: str):
                        return or_(
                            func.JSON_SEARCH(RAGContent.content_tags, 'one', pattern) != None,
                            RAGContent.content_tags.like(pattern)
                        )

                    if term_type == "like":
                        if isinstance(value, list):
                            return or_(*[json_search(f'%{tag}%') for tag in value])
                        else:
                            like_value = value if "%" in value else f"%{value}%"
                            return json_search(like_value)
                    elif term_type == "not_like":
                        if isinstance(value, list):
                            return and_(*[~json_search(f'%{tag}%') for tag in value])
                        else:
                            like_value = value if "%" in value else f"%{value}%"
                            return ~json_search(like_value)
                    elif term_type == "eq":
                        if isinstance(value, list):
                            return or_(*[json_contains(tag) for tag in value])
                        else:
                            return json_contains(value)
                    elif term_type == "ne":
                        if isinstance(value, list):
                            return and_(*[~json_contains(tag) for tag in value])
                        else:
                            return ~json_contains(value)
                    elif term_type == "in" and isinstance(value, list):
                        return or_(*[json_contains(tag) for tag in value])

                else:
                    logger.warning(f"不支持的筛选字段: {field}")
                    return None

            except Exception as e:
                logger.error(f"构建筛选条件时出错: {e}, term: {term}")
                return None

            return None

        # 应用筛选条件
        query = process_terms(request.terms, query)

        # 数据转换函数
        def transform_document(doc: RAGContent) -> dict:
            try:
                import os
                import json

                # 处理状态映射
                status_mapping = {
                    "pending": "等待处理",
                    "processing": "处理中",
                    "completed": "处理完成",
                    "failed": "处理失败"
                }

                # 生成文件访问URL（针对图片和视频）
                file_url = None
                if doc.file_path and doc.content_type in ["image", "video"]:
                    import hashlib
                    filename = os.path.basename(doc.file_path)

                    # 获取文件扩展名
                    _, ext = os.path.splitext(filename)

                    # 生成MD5哈希作为文件名
                    md5_hash = hashlib.md5(filename.encode('utf-8')).hexdigest()
                    safe_filename = f"{md5_hash}{ext}"

                    file_url = f"/uploads/{safe_filename}"

                # 安全地解析JSON标签
                try:
                    tags = json.loads(doc.content_tags) if doc.content_tags else ["文档"]
                except (json.JSONDecodeError, TypeError):
                    tags = ["文档"]

                result = {
                    "id": doc.id or "",
                    "name": doc.title or "",
                    "description": doc.description or "",
                    "category": request.collection_id or "",
                    "type": doc.content_type or "document",
                    "status": doc.status or "1",  # 基本状态：0-禁用, 1-启用
                    "processing_status": doc.processing_status or "pending",  # 处理状态
                    "processing_status_text": status_mapping.get(doc.processing_status, doc.processing_status or "pending"),  # 状态中文描述
                    "processing_message": doc.processing_message or "",  # 处理消息
                    "is_processing": (doc.processing_status or "pending") in ["pending", "processing"],  # 是否在处理中
                    "is_completed": (doc.processing_status or "pending") == "completed",  # 是否处理完成
                    "is_failed": (doc.processing_status or "pending") == "failed",  # 是否处理失败
                    "upload_type": "本地上传",
                    "created_at": int(doc.create_time.timestamp() * 1000) if doc.create_time else None,
                    "updated_at": int(doc.update_time.timestamp() * 1000) if doc.update_time else None,
                    "tags": tags,
                    "summary": doc.content_summary or "",
                    "file_size": doc.file_size or 0,
                    "file_name": doc.file_name or "",
                    "mime_type": doc.mime_type or "",
                    # 添加向量处理信息
                    "vector_id": doc.vector_id or "",
                    "has_vectors": bool(doc.vector_id)
                }

                # 如果有文件URL，添加到结果中
                if file_url:
                    result["file_url"] = file_url

                return result
            except Exception as e:
                # 如果转换失败，返回一个基本的结果
                return {
                    "id": getattr(doc, 'id', ''),
                    "name": getattr(doc, 'title', ''),
                    "description": getattr(doc, 'description', ''),
                    "category": request.collection_id or "",
                    "type": getattr(doc, 'content_type', 'document'),
                    "status": getattr(doc, 'status', '1'),
                    "processing_status": getattr(doc, 'processing_status', 'pending'),
                    "processing_status_text": "未知状态",
                    "processing_message": f"转换错误: {str(e)}",
                    "is_processing": False,
                    "is_completed": False,
                    "is_failed": True,
                    "upload_type": "本地上传",
                    "created_at": None,
                    "updated_at": None,
                    "tags": ["文档"],
                    "summary": "",
                    "file_size": 0,
                    "file_name": "",
                    "mime_type": "",
                    "vector_id": "",
                    "has_vectors": False
                }

        # 使用标准分页
        page_request = PageRequest(
            pageIndex=request.page_index,
            pageSize=request.page_size,
            sorts=request.sorts,
            terms=request.terms,
            collection_id=request.collection_id  # 添加collection_id
        )

        return paginate_and_response(
            db=db,
            model_class=RAGContent,
            page_request=page_request,
            base_query=query,  # 恢复使用预筛选的查询
            item_transformer=transform_document,
            message=f"获取集合文档成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        return ResponseHelper.error_response(
            message=f"获取集合文档失败: {str(e)}",
            status=500
        )


@router.post("/delete", response_model=Dict)
async def delete_collection(
    request: CollectionDeleteRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_request_user),
):
    """
    删除RAG集合

    删除指定的RAG集合，同时删除该集合下的所有文档。

    **请求示例：**
    ```bash
    curl -X POST "http://localhost:8006/api/v1/rag/collections/delete" \
      -H "Content-Type: application/json" \
      -d '{
        "collection_id": "d8d052bd-f875-48d8-96ba-6de8cddecc4f"
      }'
    ```

    **响应示例：**
    ```json
    {
        "success": true,
        "result": {
            "deleted_collection_id": "d8d052bd-f875-48d8-96ba-6de8cddecc4f",
            "deleted_documents_count": 5
        },
        "message": "集合 '技术文档' 及其 5 个文档已删除"
    }
    ```
    """
    try:
        return await _delete_collection_by_id(request.collection_id, db, current_user)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        return ResponseHelper.error_response(
            message=f"删除集合失败: {str(e)}",
            status=500
        )


@router.delete("/{collection_id}", response_model=Dict)
async def delete_collection_by_path(
    collection_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_request_user),
):
    try:
        return await _delete_collection_by_id(collection_id, db, current_user)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        return ResponseHelper.error_response(
            message=f"删除集合失败: {str(e)}",
            status=500
        )


@router.post("/update", response_model=Dict)
async def update_collection(
    request: dict,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_request_user),
):
    """
    更新RAG集合信息
    """
    try:
        # 获取集合ID和更新数据
        collection_id = request.get("collection_id")
        if not collection_id:
            raise HTTPException(status_code=400, detail="缺少必要参数: collection_id")

        collection_data = {k: v for k, v in request.items() if k != "collection_id"}

        # 查找集合
        query = _build_owned_collection_query(db, collection_id, current_user)

        collection = query.first()
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="集合不存在或无权限更新"
            )

        # 更新字段
        if "name" in collection_data:
            # 检查名称是否重复
            existing = db.query(RAGCollection).filter(
                RAGCollection.name == collection_data["name"],
                RAGCollection.id != collection_id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"集合名称 '{collection_data['name']}' 已存在"
                )
            collection.name = collection_data["name"]

        if "description" in collection_data:
            collection.description = collection_data["description"]

        for field in ("collection_type", "embedding_model", "rerank_model"):
            if field in collection_data:
                if field == "collection_type" and collection_data[field] not in {"text", "multimodal"}:
                    raise HTTPException(422, "集合类型只能是 text 或 multimodal")
                setattr(collection, field, collection_data[field])

        if "is_active" in collection_data:
            collection.status = "1" if collection_data["is_active"] else "0"

        if "status" in collection_data:
            collection.status = collection_data["status"]

        if "is_public" in collection_data:
            collection.is_public = collection_data["is_public"]

        collection.update_time = datetime.utcnow()

        db.commit()
        db.refresh(collection)

        return ResponseHelper.success_response(
            result={
                "id": collection.id,
                "name": collection.name,
                "description": collection.description,
                "status": collection.status,
                "is_public": collection.is_public,
                "update_time": collection.update_time.isoformat()
            },
            message="集合更新成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        return ResponseHelper.error_response(
            message=f"更新集合失败: {str(e)}",
            status=500
        )


@router.get("/{collection_id}", response_model=Dict)
async def get_collection_by_id(
    collection_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_request_user),
):
    try:
        collection = _build_collection_read_query(db, collection_id, current_user).first()
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="集合不存在或无权限访问"
            )

        return ResponseHelper.success_response(
            result=_serialize_collection(db, collection),
            message="获取集合详情成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        return ResponseHelper.error_response(
            message=f"获取集合详情失败: {str(e)}",
            status=500
        )
