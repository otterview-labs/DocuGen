#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资源分块查询接口
提供查询资源在Milvus和MySQL中的分块信息
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.rag import RAGContent, RAGChunk
from app.shared.response_models import ResponseHelper
from app.shared.utils.logger_util import get_logger
from app.config import settings

logger = get_logger("ResourceChunksAPI")
router = APIRouter()


@router.get("/{resource_id}/chunks", summary="查询资源的所有分块")
async def get_resource_chunks(
    resource_id: str,
    db: Session = Depends(get_db)
):
    """
    查询资源在Milvus和MySQL中的所有分块信息

    参数:
        resource_id: 资源ID或内容ID

    返回:
        - document: 文档基本信息
        - mysql_chunks: MySQL中的分块记录
        - milvus_chunks: Milvus中的向量记录
        - consistency: 数据一致性检查结果
    """
    try:
        # 1. 查询文档基本信息
        doc = db.query(RAGContent).filter(
            (RAGContent.id == resource_id) | (RAGContent.resource_id == resource_id)
        ).first()

        if not doc:
            return ResponseHelper.error(f"未找到文档: {resource_id}", status=404)

        content_id = doc.id
        collection_name = doc.vector_collection or 'default'

        # 文档基本信息
        doc_info = {
            "content_id": doc.id,
            "resource_id": doc.resource_id,
            "title": doc.title,
            "collection": collection_name,
            "processing_status": doc.processing_status,
            "created_at": doc.created_at.isoformat() if doc.created_at else None
        }

        # 2. 查询MySQL中的分块
        mysql_chunks = db.query(RAGChunk).filter(
            RAGChunk.content_id == content_id
        ).order_by(RAGChunk.chunk_index).all()

        mysql_chunks_data = []
        for chunk in mysql_chunks:
            mysql_chunks_data.append({
                "id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "chunk_size": chunk.chunk_size,
                "vector_id": chunk.vector_id,
                "chunking_strategy": chunk.chunking_strategy,
                "overlap_size": chunk.overlap_size,
                "chunk_preview": chunk.chunk_text[:100] if chunk.chunk_text else ""
            })

        # 3. 查询Milvus中的向量
        milvus_chunks_data = []
        milvus_error = None

        try:
            from pymilvus import Collection, connections, utility

            # 连接Milvus
            milvus_host = settings.vector_db.MILVUS_HOST
            milvus_port = settings.vector_db.MILVUS_PORT

            connections.connect(
                alias="resource_query",
                host=milvus_host,
                port=milvus_port
            )

            full_collection_name = f"jetlinks_{collection_name}"

            # 检查集合是否存在
            if utility.has_collection(full_collection_name):
                collection = Collection(full_collection_name)
                collection.load()

                # 查询向量
                results = collection.query(
                    expr=f'metadata["doc_id"] == "{content_id}"',
                    output_fields=["id", "metadata"],
                    limit=1000
                )

                for result in results:
                    metadata = result.get('metadata', {})
                    milvus_chunks_data.append({
                        "milvus_id": result['id'],
                        "doc_id": metadata.get('doc_id'),
                        "chunk_index": metadata.get('chunk_index'),
                        "title": metadata.get('title'),
                        "snippet": metadata.get('snippet', '')[:100]
                    })
            else:
                milvus_error = f"Milvus集合不存在: {full_collection_name}"

            # 断开连接
            connections.disconnect("resource_query")

        except Exception as e:
            logger.error(f"Milvus查询失败: {e}")
            milvus_error = str(e)
        finally:
            try:
                connections.disconnect("resource_query")
            except Exception:
                pass

        # 4. 数据一致性检查
        mysql_count = len(mysql_chunks_data)
        milvus_count = len(milvus_chunks_data)

        consistency = {
            "mysql_count": mysql_count,
            "milvus_count": milvus_count,
            "is_consistent": mysql_count == milvus_count,
            "difference": abs(mysql_count - milvus_count)
        }

        if mysql_count != milvus_count:
            # 找出缺失的分块
            milvus_ids = {chunk['milvus_id'] for chunk in milvus_chunks_data}
            missing_chunks = [
                chunk for chunk in mysql_chunks_data
                if chunk['vector_id'] not in milvus_ids
            ]
            consistency["missing_in_milvus"] = [
                {"chunk_index": c["chunk_index"], "vector_id": c["vector_id"]}
                for c in missing_chunks
            ]

        # 5. 分块索引分析
        if milvus_chunks_data:
            indices = [c.get('chunk_index', -1) for c in milvus_chunks_data]
            indices = [i for i in indices if i >= 0]

            if indices:
                indices.sort()
                expected = set(range(min(indices), max(indices) + 1))
                actual = set(indices)
                missing_indices = expected - actual

                consistency["index_analysis"] = {
                    "min_index": min(indices),
                    "max_index": max(indices),
                    "total_count": len(indices),
                    "is_continuous": len(missing_indices) == 0,
                    "missing_indices": sorted(missing_indices) if missing_indices else []
                }

        return ResponseHelper.success(
            result={
                "document": doc_info,
                "mysql_chunks": mysql_chunks_data,
                "milvus_chunks": milvus_chunks_data,
                "consistency": consistency,
                "milvus_error": milvus_error
            },
            message="查询成功"
        )

    except Exception as e:
        logger.exception(f"查询资源分块失败: {resource_id}")
        return ResponseHelper.error(f"查询失败: {str(e)}", status=500)
