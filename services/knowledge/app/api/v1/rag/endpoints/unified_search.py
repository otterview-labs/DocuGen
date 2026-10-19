#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一智能检索接口 - 七模式检索系统

对外公开 7 个检索模式：
- intelligent（默认）
- semantic
- keyword
- kg
- file
- image
- image_to_image
"""

from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from app.api.v1.deps import get_request_user
from app.db.session import get_db
from app.db.models.user import User
from app.schemas.search import SearchRequest, SearchResponse
from app.services.unified_search_service import get_unified_search_service
from app.shared.response_models import ResponseHelper

router = APIRouter()


@router.post("/unified", response_model=SearchResponse)
async def unified_search(
    request: SearchRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_request_user),
):
    """
    统一智能检索接口 🔍

    ## 🎯 检索模式（对外公开 7 种）

    ### 1. **intelligent** - 智能检索 (推荐)
    系统根据查询内容自动选择最优检索策略：
    - 实体词汇/关系描述 → 语义检索
    - 概念描述 → 语义检索
    - 具体关键词 → 关键词检索
    - 复杂查询 → 混合检索（KG 不参与主排序）

    ### 2. **semantic** - 语义检索
    基于AI理解的深度语义匹配：
    - 支持同义词和上下文理解
    - 适合概念性和描述性查询
    - 使用当前配置的 OpenAI-compatible / local Embedding 模型

    ### 3. **keyword** - 关键词检索
    传统精确文本匹配：
    - 高精度的字面匹配
    - 适合已知术语查询
    - 支持多字段匹配

    ### 4. **kg** - 知识图谱检索
    直接查询知识图谱中的实体和关系节点：
    - 适合显式的图谱检索/实体检索场景
    - `intelligent` 不会再优先把这类查询自动路由到 KG
    - 支持通过 `resource_id` 将检索范围约束到指定文档构建出的图谱
    - 可配合 `kg_config.search_type` 控制 entity/relation/path 检索类型

    ### 5. **file** - 文件级检索
    先选出最相关的文件，再（可选）基于该文件生成严格受控的回答：
    - 使用 `max_files` 控制选中文件数量
    - `answer_with_file=true` 将严格基于这些文件内容作答
    - 未配置LLM时仅返回文件，不生成回答
    - 可用 `selected_file_ids` 显式指定文件ID，直接用于结果/回答
    - `return_citations=true` 时会返回结构化引用（doc_id、title、snippet、offset、highlights）
    - `use_chunk_retrieval=true` 开启段落级向量检索，`per_file_citations` 控制每文件片段数量
    - `field_semantic_select=true` 将使用语义相似度在 标题/摘要/标签 上选择更相关的文件，可配合 `field_weights`
    - `insert_citation_markers=true` 会在答案文本尾部追加"（参考 [1][2]）"；`append_references=true` 会附带参考资料清单

    ### 6. **image** - 图搜索 🖼️
    图片转文本智能搜索：
    - 支持上传图片作为查询输入（base64/URL/本地路径）
    - 使用当前配置的视觉模型分析图片内容
    - 自动提取图片描述并转换为文本查询
    - 支持图文混合查询（同时提供text和image）
    - 图片描述自动缓存24小时（提升性能）
    - 适合：以图搜文档、截图搜索、产品图片查询等场景

    ### 7. **image_to_image** - 视觉相似检索 🖼️
    图片直接生成视觉向量并检索图片内容：
    - `image` 字段仍然必填，但 `query` 可为空
    - 检索命中的是图片内容本身，不再先转成文本描述
    - 支持整图检索，也支持命中外部上传时附带的 bbox region
    - 内部实现名为 `visual_similarity`，对外兼容名为 `image_to_image`

    ## 🔐 权限控制
    - 自动根据用户权限筛选结果
    - 支持`bindings`细粒度控制
    - 按分类、资源类型和 `resource_id` 过滤

    ## 🎨 使用示例

    ```bash
    # 智能检索 (推荐)
    curl -X POST "/api/v1/rag/search/unified" \\
      -d '{
        "query": "人工智能系统架构",
        "search_mode": "intelligent",
        "top_k": 10,
        "classify_ids": ["tech_docs"]  # [已废弃] 请使用 "collection_ids" 替代
      }'

    # 语义检索
    curl -X POST "/api/v1/rag/search/unified" \\
      -d '{
        "query": "JetLinks系统架构设计",
        "search_mode": "semantic",
        "top_k": 10
      }'

    # 知识图谱检索（限定到指定资源）
    curl -X POST "/api/v1/rag/search/unified" \\
      -d '{
        "query": "设备和网关之间的关系",
        "search_mode": "kg",
        "resource_id": "res_001",
        "kg_config": {"search_type": "relation", "max_depth": 2},
        "top_k": 10
      }'

    # 文件级检索并基于文件回答
    curl -X POST "/api/v1/rag/search/unified" \\
      -d '{
        "query": "请根据规范给出系统启动流程",
        "search_mode": "file",
        "max_files": 1,
        "answer_with_file": true,
        "return_citations": true
      }'

    # 直接指定文件ID进行回答
    curl -X POST "/api/v1/rag/search/unified" \\
      -d '{
        "query": "这个文档中的安全策略是什么？",
        "search_mode": "file",
        "selected_file_ids": ["<doc_id_1>", "<doc_id_2>"],
        "answer_with_file": true,
        "return_citations": true
      }'

    # 🖼️ 图搜索：纯图片查询
    curl -X POST "/api/v1/rag/search/unified" \\
      -H 'Content-Type: application/json' \\
      -d '{
        "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
        "search_mode": "image",
        "top_k": 10
      }'

    # 🖼️ 图搜索：图片URL
    curl -X POST "/api/v1/rag/search/unified" \\
      -d '{
        "image": "https://example.com/product.jpg",
        "image_prompt": "识别图片中的产品型号和关键信息",
        "search_mode": "image",
        "top_k": 5
      }'

    # 🖼️ 图搜图：纯视觉相似检索
    curl -X POST "/api/v1/rag/search/unified" \\
      -H 'Content-Type: application/json' \\
      -d '{
        "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
        "search_mode": "image_to_image",
        "top_k": 5
      }'
    ```
    """
    try:
        # 获取统一检索服务
        search_service = get_unified_search_service()

        # 从用户上下文补充权限信息
        if current_user and hasattr(current_user, 'permissions') and not request.bindings:
            request.bindings = getattr(current_user, 'permissions', [])

        # 执行检索
        search_result = await search_service.search(
            request=request,
            user_id=getattr(current_user, 'id', None),
            db=db
        )

        # 处理query显示（图搜索时可能被修改）
        display_query = request.query or "图片查询"

        return SearchResponse(
            query=display_query,
            search_mode=search_result.get("execution_info", {}).get("search_mode_used", request.search_mode),
            total=len(search_result.get('results', [])),
            results=search_result.get('results', []),
            execution_info=search_result.get('execution_info', {}),
            suggestions=search_result.get('suggestions'),
            answer=search_result.get('answer'),
            citations=search_result.get('citations')
        )

    except Exception as e:
        logger.error(f"统一检索失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检索失败: {str(e)}"
        )


# 已删除重复的 POST / 接口，统一使用 /unified
# @router.post("/", response_model=SearchResponse)
# async def unified_search_entry(
#     request: SearchRequest,
#     db: Session = Depends(get_db)
# ):
#     """统一检索入口别名：POST /api/v1/rag/search
#
#     行为与 /api/v1/rag/search/unified 一致，便于统一入口文档与对接。
#     """
#     try:
#         search_service = get_unified_search_service()
#         if hasattr(current_user, 'permissions') and not request.bindings:
#             request.bindings = getattr(current_user, 'permissions', [])
#         search_result = await search_service.search(
#             request=request,
#           user_id=getattr(current_user, 'id', None),
#           db=db
#       )
#       return SearchResponse(
#           query=request.query,
#           search_mode=request.search_mode,
#           total=len(search_result.get('results', [])),
#           results=search_result.get('results', []),
#           execution_info=search_result.get('execution_info', {}),
#           suggestions=search_result.get('suggestions'),
#           answer=search_result.get('answer'),
#           citations=search_result.get('citations')
#       )
#   except Exception as e:
#       logger.error(f"统一检索失败: {e}")
#       raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"检索失败: {str(e)}")

# 已删除搜索建议和统计接口，统一使用 /unified
# @router.get("/suggest")
# async def get_search_suggestions(
#     query: str,
#     limit: int = 5
# ):
#     """
#     获取搜索建议
#
#     基于历史查询和内容分析，提供智能搜索建议
#     """
#     try:
#         search_service = get_unified_search_service()
#         suggestions = await search_service.get_suggestions(
#             partial_query=query,
#             limit=limit,
#             user_id=getattr(current_user, 'id', None)
#         )
#
#         return ResponseHelper.success(
#             result={"suggestions": suggestions},
#             message="搜索建议获取成功"
#         )
#
#     except Exception as e:
#         logger.error(f"获取搜索建议失败: {e}")
#         return ResponseHelper.error(f"获取建议失败: {str(e)}", status=500)


# @router.get("/stats")
# async def get_search_stats():
#     """
#     获取检索系统状态
#
#     返回各检索模式的可用性和统计信息
#     """
#     try:
#         search_service = get_unified_search_service()
#         stats = await search_service.get_system_stats()
#
#         return ResponseHelper.success(
#             result=stats,
#             message="检索系统状态获取成功"
#         )
#
#     except Exception as e:
#         logger.error(f"获取系统状态失败: {e}")
#         return ResponseHelper.error(f"获取状态失败: {str(e)}", status=500)


# 兼容性接口 - 已废弃，注释掉以删除
# @router.get("/text")
# async def search_text_legacy(
#     query: str,
#     collection_id: Optional[str] = None,
#     top_k: int = 5,
#     search_type: str = "hybrid"
# ):
#     """
#     传统文本搜索接口 (兼容性，建议使用 /unified)
#
#     ⚠️ 此接口将在未来版本中废弃，请使用 /unified 接口
#     """
#     try:
#         # 转换为新接口格式
#         search_request = SearchRequest(
#             query=query,
#             search_mode=search_type if search_type in ["semantic", "keyword", "hybrid"] else "hybrid",
#             collection_ids=[collection_id] if collection_id else None,
#             top_k=top_k
#         )
#
#         # 调用统一接口
#         result = await unified_search(search_request, get_db(), current_user)
#
#         # 转换为旧格式响应
#         return {
#             "success": True,
#             "data": {
#                 "query": result.query,
#                 "search_type": result.search_mode,
#                 "results": result.results,
#                 "total": result.total,
#                 "execution_info": result.execution_info
#             }
#         }
#
#     except Exception as e:
#         logger.error(f"兼容性搜索失败: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"搜索失败: {str(e)}"
#         )
