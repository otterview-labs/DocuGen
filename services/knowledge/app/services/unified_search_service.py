#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一检索服务 - 七模式对外接口

对外公开 7 个检索模式：
- intelligent（默认）
- semantic
- keyword
- kg
- file
- image
- image_to_image

其它模式（hybrid/three_layer_*）作为内部/兼容模式保留，但不再建议前端直接暴露。
"""

from __future__ import annotations

import copy
import re
import os
import json
import time
import redis
import numpy as np
import asyncio
import concurrent.futures
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from app.services.enhanced_rag_service import get_enhanced_rag_service
from app.core.kg.manager import KnowledgeGraphManager
from app.db.models.rag import RAGContent
from app.config import settings
from app.core.rag.utils.collection_mapper import collection_mapper


class SearchMode:
    """检索模式常量"""
    INTELLIGENT = "intelligent"
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    KG = "kg"
    HYBRID = "hybrid"
    FILE = "file"  # 先选文件，再基于文件回答
    IMAGE = "image"  # 图搜索：图片转文本再搜索
    IMAGE_TO_IMAGE = "image_to_image"  # API兼容名：图搜图
    VISUAL_SIMILARITY = "visual_similarity"  # 内部名：视觉相似检索
    # 三层搜索模式
    THREE_LAYER_KEYWORD = "three_layer_keyword"  # 三层架构-关键词模式
    THREE_LAYER_SEMANTIC = "three_layer_semantic"  # 三层架构-语义模式
    THREE_LAYER_DOCUMENT = "three_layer_document"  # 三层架构-文档模式


PUBLIC_SEARCH_MODES = {
    SearchMode.INTELLIGENT,
    SearchMode.SEMANTIC,
    SearchMode.KEYWORD,
    SearchMode.KG,
    SearchMode.FILE,
    SearchMode.IMAGE,
    SearchMode.IMAGE_TO_IMAGE,
}

# 兼容旧/高级模式：输入时做归一化（kg 重新作为公开模式保留）
SEARCH_MODE_ALIASES = {
    SearchMode.HYBRID: SearchMode.INTELLIGENT,
    SearchMode.VISUAL_SIMILARITY: SearchMode.IMAGE_TO_IMAGE,
    SearchMode.THREE_LAYER_KEYWORD: SearchMode.KEYWORD,
    SearchMode.THREE_LAYER_SEMANTIC: SearchMode.SEMANTIC,
    SearchMode.THREE_LAYER_DOCUMENT: SearchMode.SEMANTIC,
}

RUNTIME_SEARCH_MODE_MAP = {
    SearchMode.IMAGE_TO_IMAGE: SearchMode.VISUAL_SIMILARITY,
}

# KG 检索当前效果不稳定，因此不再参与 intelligent 的优先路由；
# hybrid 中也默认不给排序权重。
KG_HYBRID_SOURCE_WEIGHT = 0.0


def _clone_request_with_search_mode(request: Any, search_mode: str) -> Any:
    """复制已校验的请求对象，并切换为内部搜索模式。"""
    if hasattr(request, "model_copy"):
        return request.model_copy(update={"search_mode": search_mode}, deep=True)

    if hasattr(request, "copy"):
        try:
            return request.copy(update={"search_mode": search_mode}, deep=True)
        except TypeError:
            cloned_request = request.copy()
            setattr(cloned_request, "search_mode", search_mode)
            return cloned_request

    cloned_request = copy.deepcopy(request)
    setattr(cloned_request, "search_mode", search_mode)
    return cloned_request


def _normalize_str_list(value: Any) -> List[str]:
    """将单值/列表归一化为去重后的字符串列表。"""
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = [value]

    normalized: List[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if item is None:
            continue
        item_text = str(item).strip()
        if not item_text or item_text in seen:
            continue
        seen.add(item_text)
        normalized.append(item_text)
    return normalized


def _extract_result_content_id(result: Dict[str, Any]) -> Optional[str]:
    """从统一检索结果中提取关联的 rag_contents.id。"""
    meta = result.get("metadata") or {}
    content_id = (
        meta.get("doc_id")
        or meta.get("content_id")
        or meta.get("linked_content_id")
        or meta.get("source_doc")
        or result.get("doc_id")
        or result.get("content_id")
        or result.get("linked_content_id")
        or result.get("source_doc")
    )
    if not content_id and result.get("content_type") != "knowledge_graph":
        content_id = result.get("id")
    return str(content_id) if content_id else None


def _extract_result_resource_id(result: Dict[str, Any]) -> Optional[str]:
    """从统一检索结果中提取 resource_id。"""
    meta = result.get("metadata") or {}
    kg_properties = meta.get("kg_properties") or {}
    kg_nested_properties = kg_properties.get("properties") or {}

    resource_id = (
        result.get("resource_id")
        or meta.get("resource_id")
        or meta.get("linked_resource_id")
        or result.get("linked_resource_id")
        or kg_properties.get("resource_id")
        or kg_nested_properties.get("resource_id")
    )
    return str(resource_id) if resource_id else None


class UnifiedSearchService:
    """统一检索服务"""

    def __init__(self):
        self.enhanced_rag = get_enhanced_rag_service()
        self.kg_manager = None
        self._init_kg_manager()

        # 初始化Redis缓存（性能优化）
        self.redis_client = self._init_redis()

        # 初始化Milvus并预加载集合（性能优化）
        self.milvus_db = None
        vector_db_type = (getattr(settings.vector_db, "VECTOR_DB_TYPE", "faiss") or "faiss").lower()
        if vector_db_type == "milvus":
            self._init_milvus()
        else:
            logger.info(f"VECTOR_DB_TYPE={vector_db_type}，跳过 Milvus 初始化")

        # 初始化三层搜索引擎
        self.three_layer_search = None
        self._init_three_layer_search()

        # 初始化VisionAnalyzer（图搜索）
        self.vision_analyzer = None
        self._init_vision_analyzer()

        # 延迟引入以避免循环依赖
        try:
            from app.core.llm.unified_service import get_unified_llm_service, LLMRequest
            from app.core.llm.unified_config import TaskType
            self.llm_service_getter = get_unified_llm_service
            self.LLMRequest = LLMRequest
            self.TaskType = TaskType
        except Exception:
            self.llm_service_getter = None
            self.LLMRequest = None
            self.TaskType = None

    def _init_kg_manager(self):
        """初始化知识图谱管理器"""
        try:
            if settings.graph_db.is_configured:
                # 统一走 KnowledgeGraphManager（可在 neo4j/postgres 间切换）
                self.kg_manager = KnowledgeGraphManager(namespace=settings.graph_db.GRAPH_NAMESPACE)
                if self.kg_manager.is_enabled():
                    logger.info("知识图谱管理器初始化成功")
                else:
                    logger.warning("知识图谱未启用或配置无效，知识图谱检索不可用")
            else:
                logger.warning("知识图谱未启用/未配置，知识图谱检索不可用")
        except Exception as e:
            logger.warning(f"知识图谱管理器初始化失败: {e}")

    def _init_redis(self) -> Optional[redis.Redis]:
        """初始化Redis连接（性能优化）"""
        try:
            redis_cfg = getattr(settings, "redis", None)
            if not redis_cfg or not getattr(redis_cfg, "is_configured", False):
                logger.info("Redis 未配置，跳过缓存初始化")
                return None

            redis_url = (getattr(redis_cfg, "REDIS_URL", "") or "").strip()
            decode_responses = bool(getattr(redis_cfg, "REDIS_DECODE_RESPONSES", True))
            socket_timeout = float(getattr(redis_cfg, "REDIS_SOCKET_TIMEOUT", 5.0))
            socket_connect_timeout = float(getattr(redis_cfg, "REDIS_SOCKET_CONNECT_TIMEOUT", 5.0))
            retry_on_timeout = bool(getattr(redis_cfg, "REDIS_RETRY_ON_TIMEOUT", True))

            if redis_url:
                logger.info("使用 REDIS_URL 连接 Redis")
                client = redis.from_url(
                    redis_url,
                    decode_responses=decode_responses,
                    socket_timeout=socket_timeout,
                    socket_connect_timeout=socket_connect_timeout,
                    retry_on_timeout=retry_on_timeout,
                )
            else:
                redis_host = (getattr(redis_cfg, "REDIS_HOST", "") or "").strip()
                if not redis_host:
                    logger.info("Redis 未配置 REDIS_HOST/REDIS_URL，跳过缓存初始化")
                    return None
                redis_port = int(getattr(redis_cfg, "REDIS_PORT", 6379))
                redis_password = (getattr(redis_cfg, "REDIS_PASSWORD", "") or "").strip() or None
                redis_db = int(getattr(redis_cfg, "REDIS_DB", 0))

                logger.info(f"连接到Redis: {redis_host}:{redis_port}")
                client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    password=redis_password,
                    db=redis_db,
                    decode_responses=decode_responses,
                    socket_timeout=socket_timeout,
                    socket_connect_timeout=socket_connect_timeout,
                    retry_on_timeout=retry_on_timeout,
                )

            # 测试连接
            client.ping()
            logger.info("✅ Redis连接成功")
            return client

        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            return None

    def _load_content_record_maps(
        self,
        results: List[Dict[str, Any]],
        db: Session,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """批量加载结果关联的内容记录映射。"""
        content_ids: List[str] = []
        seen_content_ids: set[str] = set()
        resource_ids: List[str] = []
        seen_resource_ids: set[str] = set()

        for result in results:
            content_id = _extract_result_content_id(result)
            if content_id and content_id not in seen_content_ids:
                seen_content_ids.add(content_id)
                content_ids.append(content_id)

            resource_id = _extract_result_resource_id(result) or content_id
            if resource_id and resource_id not in seen_resource_ids:
                seen_resource_ids.add(resource_id)
                resource_ids.append(resource_id)

        content_records_by_id: Dict[str, Any] = {}
        if content_ids:
            content_records = db.query(RAGContent).filter(RAGContent.id.in_(content_ids)).all()
            content_records_by_id = {str(record.id): record for record in content_records}

        content_records_by_resource_id: Dict[str, Any] = {}
        if resource_ids:
            resource_records = db.query(RAGContent).filter(RAGContent.resource_id.in_(resource_ids)).all()
            for record in resource_records:
                resource_key = str(getattr(record, "resource_id", "") or "")
                if resource_key and resource_key not in content_records_by_resource_id:
                    content_records_by_resource_id[resource_key] = record

        return content_records_by_id, content_records_by_resource_id

    def _resolve_content_record_for_result(
        self,
        result: Dict[str, Any],
        content_records_by_id: Dict[str, Any],
        content_records_by_resource_id: Dict[str, Any],
    ) -> Any:
        """按 content_id/resource_id/legacy source_doc 解析结果对应的内容记录。"""
        content_id = _extract_result_content_id(result)
        if content_id:
            content_record = content_records_by_id.get(str(content_id))
            if content_record:
                return content_record

        resource_id = _extract_result_resource_id(result)
        if resource_id:
            content_record = content_records_by_resource_id.get(str(resource_id))
            if content_record:
                return content_record

        # 兼容旧 KG 数据：source_doc 可能实际存的是 resource_id
        if content_id:
            return content_records_by_resource_id.get(str(content_id))

        return None

    def _init_milvus(self):
        """初始化Milvus连接并预加载集合（性能优化）"""
        try:
            from app.core.rag.vector_db.milvus_db import MilvusVectorDB
            self.milvus_db = MilvusVectorDB()
            logger.info("✅ Milvus初始化成功")

            # 预加载常用集合
            collections = ['default', 'rag_collection']
            for collection_name in collections:
                try:
                    if self.milvus_db.collection_exists(collection_name):
                        # 确保集合已加载到内存
                        from pymilvus import Collection, utility
                        collection = Collection(collection_name)
                        # 使用 utility.load_state 替代 is_loaded 属性
                        try:
                            load_state = utility.load_state(collection_name)
                            if load_state == "NotLoad":
                                collection.load()
                                logger.info(f"✅ 预加载集合: {collection_name}")
                        except:
                            # 如果 load_state 不可用，尝试加载
                            try:
                                collection.load()
                            except Exception as load_err:
                                if "already been loaded" not in str(load_err):
                                    raise load_err
                except Exception as e:
                    logger.warning(f"预加载集合 {collection_name} 失败: {e}")

        except Exception as e:
            logger.error(f"Milvus初始化失败: {e}")
            self.milvus_db = None

    def _init_three_layer_search(self):
        """初始化三层搜索引擎"""
        try:
            from app.core.rag.three_layer_search import ThreeLayerSearch
            self.three_layer_search = ThreeLayerSearch()
            logger.info("三层搜索引擎初始化成功")
        except Exception as e:
            logger.warning(f"三层搜索引擎初始化失败: {e}")
            self.three_layer_search = None

    def _init_vision_analyzer(self):
        """初始化VisionAnalyzer（图搜索）"""
        try:
            from app.shared.vlm.vision_analyzer import VisionAnalyzer
            self.vision_analyzer = VisionAnalyzer()
            logger.info("✅ VisionAnalyzer初始化成功")
        except Exception as e:
            logger.warning(f"VisionAnalyzer初始化失败: {e}")
            self.vision_analyzer = None

    async def search(self, request, user_id: Optional[str], db: Session, use_cache: bool = True) -> Dict[str, Any]:
        """执行统一检索（支持缓存）"""
        start_time = datetime.now()

        try:
            # 0) 归一化检索模式：对外公开 7 种（intelligent/semantic/keyword/kg/file/image/image_to_image）
            raw_mode = (getattr(request, "search_mode", None) or SearchMode.INTELLIGENT)
            normalized_mode = (str(raw_mode).strip().lower() or SearchMode.INTELLIGENT)
            normalized_mode = SEARCH_MODE_ALIASES.get(normalized_mode, normalized_mode)
            if normalized_mode not in PUBLIC_SEARCH_MODES:
                logger.warning(f"未识别的 search_mode={raw_mode}，已降级为 intelligent")
                normalized_mode = SearchMode.INTELLIGENT
            public_mode = normalized_mode
            try:
                request.search_mode = public_mode
            except Exception:
                pass

            # 1. 查询分析和模式选择（先选择模式，再决定是否处理图片）
            analyzed_mode = await self._analyze_and_select_mode(request.query, request.search_mode)
            actual_mode = RUNTIME_SEARCH_MODE_MAP.get(analyzed_mode, analyzed_mode)

            # 2. 按需图片处理逻辑
            if actual_mode == SearchMode.IMAGE:
                # IMAGE模式：必须提供图片，query作为图片解析要求
                if not hasattr(request, 'image') or not request.image:
                    raise ValueError("IMAGE模式需要提供图片参数")

                logger.info("🖼️ 执行图搜索模式...")

                # 确保query不为None，避免验证问题
                if not request.query:
                    request.query = "图片内容分析"

                # 构建图片分析提示词 - 使用详细描述模式
                if request.query and request.query != "图片内容分析":
                    # 用户提供了具体要求，使用用户要求，但引导详细描述
                    image_prompt = request.query + """

                    请提供详细的技术描述，包括设备型号、界面特征、技术规格等信息，
                    使用完整的句子和段落，便于后续的语义搜索和内容匹配。"""
                else:
                    # 默认使用详细描述模式，便于向量搜索
                    image_prompt = """请详细描述这张图片的内容，包括：

                    1. 主要物体和设备：识别所有可见的设备、界面、按钮、图标等
                    2. 场景环境：描述图片所处的环境、背景、布局等
                    3. 技术特征：说明技术规格、型号、协议、接口等技术信息
                    4. 功能用途：分析图片中系统的功能、应用场景、用途等
                    5. 交互方式：描述用户界面、操作流程、交互设计等

                    请使用完整的句子和段落进行描述，便于后续的语义搜索和内容匹配。
                    描述应该包含足够的技术细节和上下文信息，以便在技术文档库中找到相关内容。"""

                image_description = await self._process_image_to_text(
                    image_input=request.image,
                    prompt=image_prompt
                )

                if image_description:
                    # 直接使用完整图片描述进行向量搜索，不提取关键词
                    request.query = image_description
                    actual_mode = SearchMode.SEMANTIC  # 转换为语义搜索
                    logger.info("✅ 图片分析完成，使用完整描述进行向量搜索")
                    logger.info(f"图片描述: {image_description[:200]}...")
                else:
                    raise ValueError("图片分析失败，无法进行搜索")

            elif actual_mode == SearchMode.VISUAL_SIMILARITY:
                if not hasattr(request, 'image') or not request.image:
                    raise ValueError("IMAGE_TO_IMAGE 模式需要提供图片参数")

            elif hasattr(request, 'image') and request.image:
                # 其他模式：忽略图片输入，给出警告
                logger.warning("⚠️ 当前模式不支持图片处理，将忽略图片输入，仅使用文本查询")

            # 3. 验证查询内容
            if actual_mode != SearchMode.VISUAL_SIMILARITY and (not request.query or not request.query.strip()):
                raise ValueError("查询内容不能为空")

            # 4. 尝试从缓存获取结果
            cache_key = None
            if use_cache and self.redis_client:
                cache_key = self._build_cache_key(request, user_id)
                cached_result = self._get_from_cache(cache_key)
                if cached_result:
                    elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
                    logger.info(f"缓存命中，响应时间: {elapsed_ms:.2f}ms")
                    cached_result['cache_hit'] = True
                    cached_result['execution_time_ms'] = elapsed_ms
                    return cached_result

            # 3. 权限筛选预处理
            permission_filter = await self._build_permission_filter(request, user_id, db)

            # 4. 执行检索
            if actual_mode == SearchMode.INTELLIGENT:
                results = await self._intelligent_search(request, permission_filter, db)
            elif actual_mode == SearchMode.SEMANTIC:
                results = await self._semantic_search(request, permission_filter, db)
            elif actual_mode == SearchMode.KEYWORD:
                results = await self._keyword_search(request, permission_filter, db)
            elif actual_mode == SearchMode.KG:
                results = await self._kg_search(request, permission_filter, db)
            elif actual_mode == SearchMode.HYBRID:
                results = await self._hybrid_search(request, permission_filter, db)
            elif actual_mode == SearchMode.FILE:
                results = await self._file_level_search(request, permission_filter, db)
            elif actual_mode == SearchMode.VISUAL_SIMILARITY:
                results = await self._visual_similarity_search(request, permission_filter, db)
            # 三层搜索模式
            elif actual_mode in [SearchMode.THREE_LAYER_KEYWORD, SearchMode.THREE_LAYER_SEMANTIC, SearchMode.THREE_LAYER_DOCUMENT]:
                results = await self._three_layer_search(request, actual_mode, permission_filter, db)
            else:
                raise ValueError(f"不支持的检索模式: {actual_mode}")

            # 4.5 （可选）跨文档扩展：基于知识图谱补充相关文档候选（对外使用 enable_graph_expansion 控制）
            if getattr(request, "enable_graph_expansion", False) and public_mode in {
                SearchMode.INTELLIGENT,
                SearchMode.SEMANTIC,
                SearchMode.KEYWORD,
                SearchMode.IMAGE,
            }:
                try:
                    results = await self._expand_results_with_graph(
                        results=results,
                        db=db,
                        permission_filter=permission_filter,
                        max_hops=getattr(request, "max_graph_hops", 2),
                        top_k=getattr(request, "top_k", 10),
                    )
                except Exception as e:
                    logger.warning(f"跨文档扩展失败（已忽略）: {e}")

            # 4. 后处理
            logger.info(f"🔍 [DEBUG] 权限过滤前的结果数量: {len(results)}")
            processed_results = await self._post_process_results(results, request, db)
            logger.info(f"🔍 [DEBUG] 权限过滤后的结果数量: {len(processed_results)}")

            # 对外隐藏内部检索策略：统一返回 public_mode
            for r in processed_results:
                try:
                    r["search_mode"] = public_mode
                except Exception:
                    pass

            # 5. （可选）基于选中文件生成回答
            answer_text = None
            answer_citations = None
            if actual_mode == SearchMode.FILE and getattr(request, 'answer_with_file', False):
                try:
                    answer_text, answer_citations = await self._answer_with_selected_files(
                        query=request.query,
                        results=processed_results,
                        max_content_chars=getattr(request, 'max_content_chars', 6000),
                        db=db,
                        use_chunk_retrieval=getattr(request, 'use_chunk_retrieval', True),
                        per_file_citations=max(1, min(getattr(request, 'per_file_citations', 2), 10)),
                        highlight_keywords=getattr(request, 'highlight_keywords', True),
                        insert_citation_markers=getattr(request, 'insert_citation_markers', True),
                        append_references=getattr(request, 'append_references', True)
                    )
                except Exception as e:
                    logger.warning(f"文件级回答生成失败，返回选中文件但不返回回答: {e}")

            # 6. 生成执行信息
            execution_info = self._build_execution_info(
                start_time, public_mode, len(processed_results), request
            )

            result = {
                "results": processed_results,
                "execution_info": execution_info,
                "suggestions": await self._generate_suggestions(request.query, processed_results),
                "answer": answer_text,
                "citations": answer_citations if getattr(request, 'answer_with_file', False) and getattr(request, 'return_citations', True) else None,
                "cache_hit": False
            }

            # 7. 将结果存入缓存
            if use_cache and self.redis_client and cache_key:
                self._save_to_cache(cache_key, result)

            return result

        except Exception as e:
            logger.error(f"统一检索失败: {e}")
            raise

    async def _analyze_and_select_mode(self, query: str, requested_mode: str) -> str:
        """查询分析和智能模式选择"""
        if requested_mode != SearchMode.INTELLIGENT:
            return requested_mode

        # 对于IMAGE模式，直接返回，不需要分析文本特征
        if requested_mode == SearchMode.IMAGE:
            return SearchMode.IMAGE

        # 如果没有查询内容，返回默认的语义搜索
        if not query or not query.strip():
            return SearchMode.SEMANTIC

        # 智能分析查询特征
        query_lower = query.lower()

        # 实体词汇特征 (人名、地名、专有名词)
        entity_patterns = [
            r'[\u4e00-\u9fa5]{2,4}(?:公司|有限公司|科技|系统)',  # 公司名
            r'[\u4e00-\u9fa5]{2,3}(?:市|省|区|县)',  # 地名
            r'[A-Z][a-z]+\s+[A-Z][a-z]+',  # 英文姓名
            r'[\u4e00-\u9fa5]{2,3}(?:先生|女士|总|经理|部长)'  # 职位人名
        ]

        has_entity = any(re.search(pattern, query) for pattern in entity_patterns)

        # 关系查询特征
        relation_keywords = ['关系', '连接', '关联', '相关', '属于', '包含', '影响']
        has_relation = any(keyword in query_lower for keyword in relation_keywords)

        # 概念查询特征
        concept_keywords = ['是什么', '如何', '原理', '方法', '流程', '架构', '设计']
        has_concept = any(keyword in query_lower for keyword in concept_keywords)

        # 精确查询特征
        exact_keywords = ['编号', '代码', '序号', '型号', '版本', 'ID']
        has_exact = any(keyword in query_lower for keyword in exact_keywords)

        # 数字/代码模式检测（如纯数字、编号格式等）
        numeric_patterns = [
            r'^\d{4,}$',  # 纯数字（4位以上）
            r'^[A-Z0-9]{4,}$',  # 大写字母数字组合
            r'^\d+[-_]\d+$',  # 数字-数字格式
            r'^[A-Z]{2,}-\d+$'  # 字母-数字格式
        ]
        is_numeric_pattern = any(re.match(pattern, query.strip()) for pattern in numeric_patterns)

        # 智能选择策略
        if has_exact or is_numeric_pattern:
            return SearchMode.KEYWORD  # 精确匹配（包括数字模式）
        elif has_entity or has_relation or has_concept:
            return SearchMode.SEMANTIC  # 实体/关系/概念类查询统一走语义
        else:
            return SearchMode.HYBRID  # 混合检索

    async def _file_level_search(self, request, permission_filter: Dict, db: Session) -> List[Dict[str, Any]]:
        """文件级检索：先选出文件，再返回文件粒度结果。
        策略：使用混合检索/语义检索得到候选 -> 去重为文件级 -> 取前N个文件。
        """
        try:
            # 如果明确指定了文件ID，则直接使用这些文件
            selected_ids = getattr(request, 'selected_file_ids', None) or []
            max_files = max(1, min(getattr(request, 'max_files', 1), 10))

            if selected_ids:
                ordered_ids = []
                seen_ids = set()
                for doc_id in selected_ids:
                    if not doc_id:
                        continue
                    doc_id_s = str(doc_id)
                    if doc_id_s in seen_ids:
                        continue
                    seen_ids.add(doc_id_s)
                    ordered_ids.append(doc_id_s)

                # 基于“文档概要向量”在候选 doc_ids 内做语义排序（方案3：预先存 doc-level 向量）
                score_map: Dict[str, float] = {}
                prioritized_ids = list(ordered_ids)

                try:
                    if (
                        len(ordered_ids) > 1
                        and self.enhanced_rag
                        and hasattr(self.enhanced_rag, "rank_doc_ids_by_doc_profile")
                        and getattr(self.enhanced_rag, "embedding_model", None) is not None
                        and getattr(self.enhanced_rag, "vector_db", None) is not None
                    ):
                        candidate_ids = list(ordered_ids)

                        # 若请求指定了集合，则先按集合过滤候选 doc_ids（避免跨集合干扰）
                        if permission_filter.get("collection_ids"):
                            allowed = set()
                            for cid in permission_filter["collection_ids"]:
                                if not cid:
                                    continue
                                allowed.add(cid)
                                allowed.add(cid.replace("_", "-"))
                                allowed.add(cid.replace("-", "_"))
                                try:
                                    allowed.add(collection_mapper.to_milvus_name(cid))
                                except Exception:
                                    pass

                            rows = (
                                db.query(RAGContent.id, RAGContent.vector_collection)
                                .filter(RAGContent.id.in_(candidate_ids))
                                .all()
                            )
                            allowed_ids = {str(rid) for rid, vc in rows if (vc or "") in allowed}
                            candidate_ids = [d for d in candidate_ids if d in allowed_ids]

                        ranked = await self.enhanced_rag.rank_doc_ids_by_doc_profile(
                            query=request.query,
                            doc_ids=candidate_ids,
                            top_k=min(len(candidate_ids), max(max_files * 20, max_files)),
                        )
                        score_map = {str(r["doc_id"]): float(r["score"]) for r in (ranked or []) if r.get("doc_id")}
                        ranked_ids = [str(r["doc_id"]) for r in (ranked or []) if r.get("doc_id")]
                        ranked_set = set(ranked_ids)
                        prioritized_ids = ranked_ids + [d for d in candidate_ids if d not in ranked_set]
                except Exception as e:
                    logger.warning(f"候选文档 doc-profile 向量排序失败（已忽略）: {e}")

                # 批量查库补齐文件信息（按优先级取一个窗口，避免权限过滤后不够）
                fetch_window = min(len(prioritized_ids), max(max_files * 20, max_files))
                fetch_ids = prioritized_ids[:fetch_window]
                records = (
                    db.query(RAGContent).filter(RAGContent.id.in_(fetch_ids)).all() if fetch_ids else []
                )
                record_map = {str(r.id): r for r in records}

                file_results: List[Dict[str, Any]] = []
                for doc_id in fetch_ids:
                    content_record = record_map.get(doc_id)
                    if not content_record:
                        continue
                    file_results.append(
                        {
                            "id": doc_id,
                            "title": content_record.title,
                            "description": content_record.description,
                            "content_type": content_record.content_type,
                            "similarity_score": (
                                score_map.get(doc_id, 1.0 if len(fetch_ids) == 1 else 0.0)
                            ),
                            "snippet": content_record.content_summary
                            or (content_record.content_text or "")[:200],
                            "search_mode": SearchMode.FILE,
                            "file_name": content_record.file_name,
                            "metadata": {
                                "content_summary": content_record.content_summary,
                                "content_tags": content_record.content_tags,
                                "vector_collection": content_record.vector_collection,
                                "file_size": content_record.file_size,
                                "create_time": content_record.create_time.isoformat()
                                if content_record.create_time
                                else None,
                            },
                            "file_selected": True,
                        }
                    )

                # 权限过滤
                file_results = await self._apply_permission_filter(file_results, permission_filter, db)
                # 若 doc-profile 有分数，按分数排序；否则按需走字段级语义重排
                if score_map:
                    file_results.sort(key=lambda x: x.get("similarity_score", 0.0), reverse=True)
                    return file_results[:max_files]
                if getattr(request, 'field_semantic_select', False):
                    file_results = await self._rerank_by_field_semantics(request.query, file_results, request, db)
                return file_results[:max_files]

            # 否则，先走混合或语义检索拿候选（包含相似度）
            # 支持多集合搜索：直接传递整个collection_id列表
            collection_id = permission_filter.get("collection_ids", None)
            candidate_k = min(max(getattr(request, 'top_k', 10) * 3, 10), 100)
            candidates = await self.enhanced_rag.hybrid_search(
                query=request.query,
                collection_id=collection_id,  # 传递列表，支持多集合
                top_k=candidate_k
            )

            # 过滤权限
            candidates = await self._apply_permission_filter(candidates, permission_filter, db)

            # 根据 doc_id 去重并补全文件信息（批量查库，避免 N+1；兼容语义检索返回 chunk_id）
            max_files = max(1, min(getattr(request, 'max_files', 1), 10))
            ordered_doc_ids: List[str] = []
            best_item_by_doc: Dict[str, Dict[str, Any]] = {}
            seen = set()
            for item in candidates:
                meta = item.get("metadata") or {}
                doc_id = (
                    item.get("doc_id")
                    or meta.get("doc_id")
                    or meta.get("content_id")
                    or item.get("id")
                )
                if not doc_id:
                    continue
                doc_id_s = str(doc_id)
                if doc_id_s in seen:
                    continue
                seen.add(doc_id_s)
                ordered_doc_ids.append(doc_id_s)
                best_item_by_doc[doc_id_s] = item

            records = (
                db.query(RAGContent).filter(RAGContent.id.in_(ordered_doc_ids)).all() if ordered_doc_ids else []
            )
            record_map = {str(r.id): r for r in records}

            file_results: List[Dict[str, Any]] = []
            for doc_id in ordered_doc_ids:
                if len(file_results) >= max_files:
                    break
                content_record = record_map.get(doc_id)
                if not content_record:
                    continue
                item = best_item_by_doc.get(doc_id) or {}
                file_results.append(
                    {
                        "id": doc_id,
                        "title": content_record.title or item.get("title"),
                        "description": content_record.description or item.get("description"),
                        "content_type": content_record.content_type,
                        "similarity_score": float(item.get("similarity_score", 0.0) or 0.0),
                        "snippet": item.get("snippet"),
                        "search_mode": SearchMode.FILE,
                        "file_name": content_record.file_name,
                        "metadata": {
                            "content_summary": content_record.content_summary,
                            "content_tags": content_record.content_tags,
                            "vector_collection": content_record.vector_collection,
                            "file_size": content_record.file_size,
                            "create_time": content_record.create_time.isoformat()
                            if content_record.create_time
                            else None,
                        },
                        "file_selected": True,
                    }
                )

            # 文件级结果按相似度排序
            # 可选：基于标题/摘要/标签进行语义重排
            if getattr(request, 'field_semantic_select', False):
                file_results = await self._rerank_by_field_semantics(request.query, file_results, request, db)
            else:
                file_results.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
            return file_results

        except Exception as e:
            logger.error(f"文件级检索失败: {e}")
            # 兜底为语义检索
            return await self._semantic_search(request, permission_filter, db)

    async def _three_layer_search(self, request, actual_mode: SearchMode, permission_filter: Dict, db: Session) -> List[Dict[str, Any]]:
        """
        三层架构搜索

        Args:
            request: 搜索请求
            actual_mode: 具体的三层搜索模式
            permission_filter: 权限过滤器
            db: 数据库会话

        Returns:
            搜索结果列表
        """
        try:
            if not self.three_layer_search:
                logger.warning("三层搜索引擎未初始化，降级到语义搜索")
                return await self._semantic_search(request, permission_filter, db)

            # 导入三层搜索相关类
            from app.core.rag.three_layer_search import SearchConfig, SearchMode as ThreeLayerMode

            # 映射统一搜索模式到三层搜索模式
            mode_mapping = {
                SearchMode.THREE_LAYER_KEYWORD: ThreeLayerMode.KEYWORD,
                SearchMode.THREE_LAYER_SEMANTIC: ThreeLayerMode.SEMANTIC,
                SearchMode.THREE_LAYER_DOCUMENT: ThreeLayerMode.DOCUMENT
            }

            three_layer_mode = mode_mapping.get(actual_mode, ThreeLayerMode.SEMANTIC)

            # 构建三层搜索配置
            search_config = SearchConfig(
                mode=three_layer_mode,
                top_k=request.top_k,
                use_cache=True,  # 默认启用缓存
                use_rerank=True,  # 默认启用重排序
                expand_context=getattr(request, 'expand_context', False),
                include_relations=getattr(request, 'include_relations', False),
                weights=getattr(request, 'weights', None),
                max_graph_hops=getattr(request, 'max_graph_hops', 2),  # 支持多跳配置
                enable_graph_expansion=getattr(request, 'enable_graph_expansion', False)  # 支持图扩展
            )

            # 执行三层搜索
            logger.info(f"执行三层搜索: mode={three_layer_mode.value}, query={request.query[:50]}...")
            search_results = await self.three_layer_search.search(request.query, search_config)

            # 转换结果格式以匹配统一搜索的响应格式
            formatted_results = []
            for result in search_results:
                # 获取文档的详细信息
                doc_content = db.query(RAGContent).filter(
                    RAGContent.id == result.doc_id
                ).first() if result.doc_id else None

                formatted_result = {
                    "id": result.doc_id or "",
                    "chunk_id": result.chunk_id or "",
                    "content": result.content,
                    "similarity_score": result.score,
                    "search_path": result.search_path,
                    "metadata": result.metadata or {},
                    "context": result.context,
                    "relations": result.relations
                }

                # 添加文档级信息
                if doc_content:
                    formatted_result.update({
                        "title": doc_content.title,
                        "file_name": doc_content.file_name,
                        "resource_type": doc_content.resource_type,
                        "collection_id": doc_content.vector_collection,
                        "create_time": doc_content.create_time.isoformat() if doc_content.create_time else None
                    })

                # 应用权限过滤
                if permission_filter:
                    # 检查集合权限
                    if 'collection_ids' in permission_filter and doc_content:
                        if (doc_content.vector_collection or "") not in permission_filter['collection_ids']:
                            continue

                    # 检查资源类型
                    if 'resource_types' in permission_filter and doc_content:
                        if doc_content.resource_type not in permission_filter['resource_types']:
                            continue

                formatted_results.append(formatted_result)

            # 按相似度排序并限制结果数量
            formatted_results.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
            formatted_results = formatted_results[:request.top_k]

            logger.info(f"三层搜索完成，返回 {len(formatted_results)} 个结果")
            return formatted_results

        except Exception as e:
            logger.error(f"三层搜索失败: {e}", exc_info=True)
            # 降级到语义搜索
            logger.info("降级到语义搜索")
            return await self._semantic_search(request, permission_filter, db)

    async def _rerank_by_field_semantics(self, query: str, docs: List[Dict[str, Any]], request, db: Session) -> List[Dict[str, Any]]:
        """使用语义匹配（标题/摘要/标签）对候选文档重排。"""
        try:
            if not docs:
                return docs
            if not getattr(self.enhanced_rag, 'embedding_model', None):
                return docs

            # 构造字段文本
            doc_ids = [d.get('id') for d in docs]
            records = {c.id: c for c in db.query(RAGContent).filter(RAGContent.id.in_(doc_ids)).all()}
            titles, summaries, tags_texts, valid_idx = [], [], [], []
            for i, d in enumerate(docs):
                rec = records.get(d.get('id'))
                if not rec:
                    continue
                titles.append(rec.title or "")
                summaries.append((rec.content_summary or ""))
                # tags 可能是 JSON/list/str
                tag_val = rec.content_tags
                if isinstance(tag_val, list):
                    tags_texts.append(", ".join([str(t) for t in tag_val]))
                elif isinstance(tag_val, str):
                    tags_texts.append(tag_val)
                else:
                    try:
                        tags_texts.append(", ".join([str(t) for t in (tag_val or [])]))
                    except Exception:
                        tags_texts.append("")
                valid_idx.append(i)

            if not valid_idx:
                return docs

            # 查询向量
            qvec, _ = self.enhanced_rag.embedding_model.encode_queries(query)

            # 批量编码字段
            title_emb, _ = self.enhanced_rag.embedding_model.encode(titles) if titles else (None, 0)
            summary_emb, _ = self.enhanced_rag.embedding_model.encode(summaries) if summaries else (None, 0)
            tags_emb, _ = self.enhanced_rag.embedding_model.encode(tags_texts) if tags_texts else (None, 0)

            # 权重
            weights = getattr(request, 'field_weights', None) or {}
            w_title = float(weights.get('title', 0.4))
            w_summary = float(weights.get('summary', 0.5))
            w_tags = float(weights.get('tags', 0.1))
            # 归一化权重
            total_w = max(1e-6, w_title + w_summary + w_tags)
            w_title, w_summary, w_tags = w_title/total_w, w_summary/total_w, w_tags/total_w

            # 计算相似度（内积）
            def dot(a):
                try:
                    return float(np.dot(a, qvec))
                except Exception:
                    return 0.0

            field_scores = [0.0 for _ in docs]
            for idx_i, di in enumerate(valid_idx):
                s = 0.0
                if title_emb is not None:
                    s += w_title * dot(title_emb[idx_i])
                if summary_emb is not None:
                    s += w_summary * dot(summary_emb[idx_i])
                if tags_emb is not None:
                    s += w_tags * dot(tags_emb[idx_i])
                field_scores[di] = s

            # 写回并排序
            for i, d in enumerate(docs):
                d['field_similarity'] = field_scores[i]
            docs.sort(key=lambda x: x.get('field_similarity', 0.0), reverse=True)
            # 只保留请求的文件数
            max_files = max(1, min(getattr(request, 'max_files', 1), 10))
            return docs[:max_files]
        except Exception as e:
            logger.warning(f"字段级语义重排失败: {e}")
            return docs

    async def _answer_with_selected_files(self, query: str, results: List[Dict[str, Any]],
                                          max_content_chars: int, db: Session,
                                          use_chunk_retrieval: bool = True,
                                          per_file_citations: int = 2,
                                          highlight_keywords: bool = True,
                                          insert_citation_markers: bool = True,
                                          append_references: bool = True) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
        """使用选中的文件内容进行严格的基于文件回答。
        如果未配置LLM或调用失败，返回None。
        """
        if not results:
            return None, None

        if not self.llm_service_getter or not self.LLMRequest or not self.TaskType:
            return None, None

        try:
            llm_service = self.llm_service_getter()
        except Exception:
            return None, None

        # 组装上下文，仅使用选中文件内容（支持段落级/片段级选择）
        docs_context_parts: List[str] = []
        total_chars = 0
        citations: List[Dict[str, Any]] = []
        # 预处理查询关键词用于高亮
        highlight_terms = self._extract_terms_for_highlight(query) if highlight_keywords else []
        # 查询向量
        query_vec = None
        if use_chunk_retrieval and getattr(self.enhanced_rag, 'embedding_model', None):
            try:
                query_vec, _ = self.enhanced_rag.embedding_model.encode_queries(query)
            except Exception:
                query_vec = None

        for r in results:
            try:
                content = db.query(RAGContent).filter(RAGContent.id == r.get("id")).first()
                if not content:
                    continue
                title = content.title or ''
                summary = (content.content_summary or "").strip()
                body = (content.content_text or "").strip()

                # 当启用片段级检索时，从正文中选取与查询最相关的段落/句子
                if use_chunk_retrieval and body and query_vec is not None and getattr(self.enhanced_rag, 'embedding_model', None):
                    segments = self._split_into_segments(body)
                    # 选取 topN 片段
                    selected = await self._select_relevant_segments(query_vec, segments, per_file_citations)
                    # 将片段拼入上下文，并生成精细引用
                    if selected:
                        header = f"[Document]\nTitle: {title}\n\n"
                        if max_content_chars > 0:
                            remain = max_content_chars - total_chars
                            if remain <= 0:
                                break
                            # 先计入标题空间
                            header = header[:remain]
                            total_chars += len(header)
                        docs_context_parts.append(header)

                        for seg in selected:
                            seg_text = seg["text"]
                            seg_entry = f"[Segment]\n{seg_text}\n\n"
                            if max_content_chars > 0:
                                remain = max_content_chars - total_chars
                                if remain <= 0:
                                    break
                                seg_entry = seg_entry[:remain]
                                total_chars += len(seg_entry)
                            docs_context_parts.append(seg_entry)

                            # 生成引用，包含 offset 与高亮位置
                            highlights = self._highlight_positions(seg_text, highlight_terms) if highlight_terms else []
                            citations.append({
                                "doc_id": content.id,
                                "title": title,
                                "snippet": seg_text[:300] + ('...' if len(seg_text) > 300 else ''),
                                "score": seg["score"],
                                "offset": {"start": seg["start"], "end": seg["end"]},
                                "highlights": highlights,
                                "collection": content.vector_collection,
                                "file_name": content.file_name
                            })
                        continue  # 已按片段模式完成

                # 否则，使用摘要+正文（回退模式）
                piece = f"[Title]\n{title}\n\n[Summary]\n{summary[:1500]}\n\n[Body]\n{body}"
                if max_content_chars > 0:
                    remain = max_content_chars - total_chars
                    if remain <= 0:
                        break
                    piece = piece[:remain]
                    total_chars += len(piece)
                docs_context_parts.append(piece)

                # 回退引用片段：优先摘要，否则内容前200字
                snippet_source = summary if summary else body
                citation_snippet = (snippet_source[:300] + '...') if len(snippet_source) > 300 else snippet_source
                highlights = self._highlight_positions(citation_snippet, highlight_terms) if highlight_terms else []
                citations.append({
                    "doc_id": content.id,
                    "title": title,
                    "snippet": citation_snippet,
                    "score": 1.0,
                    "offset": None,
                    "highlights": highlights,
                    "collection": content.vector_collection,
                    "file_name": content.file_name
                })
            except Exception:
                continue

        if not docs_context_parts:
            return None, None

        context_text = "\n\n-----\n\n".join(docs_context_parts)
        system_message = (
            "你是一个严谨的企业知识库问答助手。严格只依据提供的文档内容回答问题，"
            "不要引入文档外的信息。若文档中没有答案，请明确说明‘根据提供的文档无法确定答案’。"
        )

        request = self.LLMRequest(
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": f"以下是可用文档：\n\n{context_text}\n\n问题：{query}\n请基于以上文档作答，并给出引用的要点。"}
            ],
            task_type=self.TaskType.DOCUMENT_ANALYSIS,
            temperature=0.2,
            max_tokens=800
        )

        try:
            resp = await llm_service.chat(request)
            answer_text = resp.content if resp and resp.content else None
            # 注入 [1][2] 小标与参考列表
            if answer_text and citations:
                markers = ''.join([f"[{i+1}]" for i in range(len(citations))])
                if insert_citation_markers:
                    answer_text = f"{answer_text}\n\n（参考 {markers}）"
                if append_references:
                    refs_lines = ["参考资料:"]
                    for i, c in enumerate(citations, start=1):
                        title = c.get('title') or c.get('file_name') or c.get('doc_id')
                        refs_lines.append(f"[{i}] {title}")
                    answer_text = f"{answer_text}\n\n" + "\n".join(refs_lines)
            return answer_text, citations
        except Exception as e:
            logger.warning(f"LLM基于文件回答失败: {e}")
            return None, citations if citations else None

    def _split_into_segments(self, text: str) -> List[Dict[str, Any]]:
        """将正文划分为段落/句子片段，并返回带全局偏移的列表。"""
        segments: List[Dict[str, Any]] = []
        if not text:
            return segments
        # 先按段落分割
        parts = re.split(r"\n\s*\n+", text)
        offset = 0
        for p in parts:
            p = p.strip()
            if not p:
                offset += 1
                continue
            # 若段落过长，再按句子分割
            if len(p) > 800:
                # 按中文标点与英文标点分句
                sentences = re.split(r"(?<=[。！？.!?])\s+", p)
                local = 0
                for s in sentences:
                    s_strip = s.strip()
                    if not s_strip:
                        local += len(s) + 1
                        continue
                    start = offset + local
                    end = start + len(s_strip)
                    segments.append({"text": s_strip, "start": start, "end": end})
                    local += len(s) + 1
                offset += len(p) + 2
            else:
                start = offset
                end = start + len(p)
                segments.append({"text": p, "start": start, "end": end})
                offset += len(p) + 2
        return segments

    async def _select_relevant_segments(self, query_vec: np.ndarray, segments: List[Dict[str, Any]], k: int) -> List[Dict[str, Any]]:
        """使用向量相似度从片段中选取Top-k。"""
        if not segments:
            return []
        # 选取最多前N段进行计算（避免过大计算量）
        max_candidates = min(len(segments), 200)
        candidate_texts = [segments[i]["text"] for i in range(max_candidates)]
        try:
            emb, _ = self.enhanced_rag.embedding_model.encode(candidate_texts)
            # 计算内积分数
            q = query_vec.reshape(1, -1)
            scores = (emb @ query_vec).tolist()
        except Exception:
            # 编码失败，退化为长度/关键词启发式
            scores = [len(t) for t in candidate_texts]

        ranked = sorted(
            [{"score": float(scores[i]), **segments[i]} for i in range(max_candidates)],
            key=lambda x: x["score"], reverse=True
        )
        return ranked[:k]

    def _extract_terms_for_highlight(self, query: str) -> List[str]:
        """从查询中提取用于高亮的词（简单启发式）。"""
        terms = set()
        # 英文/数字词
        for w in re.findall(r"[A-Za-z0-9_\-]{2,}", query):
            terms.add(w.lower())
        # 简单中文词（长度>=2）
        cn_words = re.findall(r"[\u4e00-\u9fa5]{2,}", query)
        terms.update(cn_words)
        return list(terms)

    def _highlight_positions(self, text: str, terms: List[str]) -> List[Dict[str, Any]]:
        """返回每个term在文本段中的位置区间。"""
        highlights: List[Dict[str, Any]] = []
        lower = text.lower()
        for term in terms:
            if not term:
                continue
            if re.match(r"^[A-Za-z0-9_\-]+$", term):
                # 英文大小写不敏感
                start = 0
                while True:
                    idx = lower.find(term.lower(), start)
                    if idx == -1:
                        break
                    highlights.append({"term": term, "start": idx, "end": idx + len(term)})
                    start = idx + len(term)
            else:
                # 中文按原样查找
                start = 0
                while True:
                    idx = text.find(term, start)
                    if idx == -1:
                        break
                    highlights.append({"term": term, "start": idx, "end": idx + len(term)})
                    start = idx + len(term)
        return highlights

    async def _build_permission_filter(self, request, user_id: Optional[str], db: Session) -> Dict[str, Any]:
        """构建权限过滤器"""
        filter_conditions = {
            "user_permissions": _normalize_str_list(getattr(request, 'bindings', None)),
            "collection_ids": _normalize_str_list(getattr(request, 'collection_id', None)),
            "resource_ids": _normalize_str_list(getattr(request, 'resource_id', None)),
            "resource_types": _normalize_str_list(getattr(request, 'resource_types', None)),
        }

        logger.info(f"🔍 [DEBUG] 权限过滤器: {filter_conditions}")

        # 如果没有明确权限，可根据环境决定是否赋默认权限
        # 在开发/跳过认证模式下，不赋默认权限，避免误过滤
        # 在生产环境可按需补充（此处保持为空）
        try:
            from app.config import settings
            dev_mode = getattr(settings, 'DEV_MODE', True)
            skip_auth = getattr(settings, 'SKIP_AUTH', True)
        except Exception:
            dev_mode, skip_auth = True, True
        if not filter_conditions["user_permissions"]:
            if not (dev_mode or skip_auth):
                # 生产环境可设置最小权限，这里保持为空，交由上层传入
                pass

        return filter_conditions

    async def _resolve_resource_ids_to_content_ids(self, resource_ids: List[str], db: Session) -> List[str]:
        """将 resource_id 过滤项映射为 rag_contents.id。"""
        normalized_ids = _normalize_str_list(resource_ids)
        if not normalized_ids:
            return []

        try:
            content_records = (
                db.query(RAGContent)
                .filter(RAGContent.resource_id.in_(normalized_ids))
                .all()
            )
        except Exception as e:
            logger.warning(f"resource_id 映射 content_id 失败: {e}")
            return []

        content_ids: List[str] = []
        seen: set[str] = set()
        for record in content_records:
            content_id = getattr(record, "id", None)
            if not content_id:
                continue
            content_id = str(content_id)
            if content_id in seen:
                continue
            seen.add(content_id)
            content_ids.append(content_id)

        return content_ids

    async def _intelligent_search(self, request, permission_filter: Dict, db: Session) -> List[Dict]:
        """智能检索 - 根据查询特征自动选择最优策略"""
        # 实际会调用_analyze_and_select_mode选择的具体模式
        actual_mode = await self._analyze_and_select_mode(request.query, SearchMode.INTELLIGENT)

        if actual_mode == SearchMode.KG:
            return await self._kg_search(request, permission_filter, db)
        elif actual_mode == SearchMode.SEMANTIC:
            return await self._semantic_search(request, permission_filter, db)
        elif actual_mode == SearchMode.KEYWORD:
            return await self._keyword_search(request, permission_filter, db)
        else:
            return await self._hybrid_search(request, permission_filter, db)

    async def _semantic_search(self, request, permission_filter: Dict, db: Session) -> List[Dict]:
        """语义检索"""
        try:
            # 语义检索：支持多集合搜索，直接传递集合ID列表
            collection_id = permission_filter.get("collection_ids") or None

            results = await self.enhanced_rag.semantic_search(
                query=request.query,
                collection_id=collection_id,  # 传递列表，支持多集合
                top_k=request.top_k,
                similarity_threshold=request.similarity_threshold
            )

            # 应用权限过滤
            logger.info(f"🔍 [DEBUG] 语义搜索权限过滤前: {len(results)} 个结果")
            filtered_results = await self._apply_permission_filter(results, permission_filter, db)
            logger.info(f"🔍 [DEBUG] 语义搜索权限过滤后: {len(filtered_results)} 个结果")

            # 添加检索模式标记
            for result in filtered_results:
                result["search_mode"] = SearchMode.SEMANTIC

            # 若语义检索为空，自动降级到关键词检索
            if not filtered_results:
                kw = await self._keyword_search(request, permission_filter, db)
                return kw
            return filtered_results

        except Exception as e:
            logger.error(f"语义检索失败: {e}")
            return []

    async def _keyword_search(self, request, permission_filter: Dict, db: Session) -> List[Dict]:
        """关键词检索"""
        try:
            # 关键词检索：支持多集合搜索，直接传递集合ID列表
            collection_id = permission_filter.get("collection_ids") or None

            results = await self.enhanced_rag._fallback_keyword_search(
                query=request.query,
                collection_id=collection_id,  # 传递列表，支持多集合
                top_k=request.top_k
            )

            # 应用权限过滤
            filtered_results = await self._apply_permission_filter(results, permission_filter, db)

            # 添加检索模式标记
            for result in filtered_results:
                result["search_mode"] = SearchMode.KEYWORD

            return filtered_results

        except Exception as e:
            logger.error(f"关键词检索失败: {e}")
            return []

    async def _visual_similarity_search(self, request, permission_filter: Dict, db: Session) -> List[Dict]:
        """视觉相似检索：图片直接生成视觉向量后召回图片内容。"""
        image_input = getattr(request, "image", None)
        if not image_input:
            return []

        image_path: Optional[str] = None
        try:
            image_path = await self._prepare_image_file(image_input)
            if not image_path:
                raise ValueError("无法准备视觉检索图片文件")

            from app.core.rag.vector_db.pgvector_visual_db import PgVectorVisualStore
            from app.db.models.rag import RAGMediaAsset, RAGVisualRegion
            from app.shared.vlm.visual_embedding import get_visual_image_embedder

            embedder = get_visual_image_embedder()
            query_vector = await asyncio.to_thread(embedder.embed_image_file, image_path)

            store = PgVectorVisualStore()
            raw_hits = store.search(
                query_vector=query_vector,
                top_k=max(int(getattr(request, "top_k", 5) or 5) * 5, 10),
                collection_ids=permission_filter.get("collection_ids") or None,
            )
            if not raw_hits:
                return []

            region_ids = [str(item["region_id"]) for item in raw_hits if item.get("region_id")]
            asset_ids = [str(item["asset_id"]) for item in raw_hits if item.get("asset_id")]
            content_ids = [str(item["content_id"]) for item in raw_hits if item.get("content_id")]

            region_map = {
                str(region.id): region
                for region in db.query(RAGVisualRegion).filter(RAGVisualRegion.id.in_(region_ids)).all()
            } if region_ids else {}
            asset_map = {
                str(asset.id): asset
                for asset in db.query(RAGMediaAsset).filter(RAGMediaAsset.id.in_(asset_ids)).all()
            } if asset_ids else {}
            content_map = {
                str(content.id): content
                for content in db.query(RAGContent).filter(RAGContent.id.in_(content_ids)).all()
            } if content_ids else {}

            best_by_content: Dict[str, Dict[str, Any]] = {}
            for hit in raw_hits:
                content_id = str(hit.get("content_id") or "")
                if not content_id:
                    continue

                content_record = content_map.get(content_id)
                if not content_record:
                    continue

                score = float(hit.get("score") or 0.0)
                region = region_map.get(str(hit.get("region_id") or ""))
                asset = asset_map.get(str(hit.get("asset_id") or ""))

                result = {
                    "id": content_id,
                    "doc_id": content_id,
                    "title": content_record.title or "",
                    "description": content_record.description or "",
                    "content": content_record.content_summary or content_record.description or (content_record.content_text or "")[:1000],
                    "content_type": content_record.content_type or "image",
                    "similarity_score": score,
                    "snippet": (
                        (region.region_text if region and getattr(region, "region_text", None) else None)
                        or content_record.content_summary
                        or content_record.description
                        or (content_record.content_text or "")[:200]
                    ),
                    "metadata": {
                        "doc_id": content_id,
                        "content_id": content_id,
                        "vector_collection": content_record.vector_collection,
                        "visual_match": {
                            "region_id": str(region.id) if region else str(hit.get("region_id") or ""),
                            "asset_id": str(asset.id) if asset else str(hit.get("asset_id") or ""),
                            "region_type": getattr(region, "region_type", None),
                            "bbox": getattr(region, "bbox_normalized", None),
                            "label": getattr(region, "label", None),
                            "source": getattr(region, "source", None),
                            "source_system": getattr(region, "source_system", None),
                            "score": score,
                        },
                    },
                }

                existing = best_by_content.get(content_id)
                if existing is None or score > float(existing.get("similarity_score") or 0.0):
                    best_by_content[content_id] = result

            content_level_results = sorted(
                best_by_content.values(),
                key=lambda item: float(item.get("similarity_score") or 0.0),
                reverse=True,
            )

            filtered_results = await self._apply_permission_filter(content_level_results, permission_filter, db)
            for result in filtered_results:
                result["search_mode"] = SearchMode.VISUAL_SIMILARITY

            return filtered_results[: getattr(request, "top_k", 5)]
        except Exception as e:
            logger.error(f"视觉相似检索失败: {e}")
            return []
        finally:
            if image_path:
                try:
                    await self._cleanup_temp_image(image_path, image_input)
                except Exception:
                    pass

    async def _kg_search(self, request, permission_filter: Dict, db: Session) -> List[Dict]:
        """知识图谱检索"""
        try:
            if not self.kg_manager or not getattr(self.kg_manager, "is_enabled", lambda: False)():
                logger.warning("知识图谱不可用，降级到语义搜索")
                return await self._semantic_search(request, permission_filter, db)

            # 初始化（幂等）
            await self.kg_manager.initialize()

            # 解析KG配置
            kg_config = request.kg_config or {
                "search_type": "entity",
                "max_depth": 3,
                "include_relations": True
            }

            document_ids = await self._resolve_resource_ids_to_content_ids(
                permission_filter.get("resource_ids") or [],
                db,
            )
            if permission_filter.get("resource_ids") and not document_ids:
                logger.info("KG 检索收到 resource_id 过滤，但未映射到任何内容记录")
                return []

            # 执行KG搜索
            kg_results = await self._execute_kg_query(
                request.query,
                kg_config,
                document_ids=document_ids or None,
            )

            # 将KG结果转换为统一格式
            unified_results = await self._convert_kg_results(kg_results, db, query=request.query)

            # 应用权限过滤
            filtered_results = await self._apply_permission_filter(unified_results, permission_filter, db)

            # 添加检索模式标记
            for result in filtered_results:
                result["search_mode"] = SearchMode.KG

            return filtered_results[:request.top_k]

        except Exception as e:
            logger.error(f"知识图谱检索失败: {e}")
            # 降级到语义搜索
            return await self._semantic_search(request, permission_filter, db)

    async def _hybrid_search(self, request, permission_filter: Dict, db: Session) -> List[Dict]:
        """混合检索 - 优化的并行执行（带超时控制）"""
        try:
            results_dict = {}

            # 使用ThreadPoolExecutor并行执行同步操作
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                # 创建异步任务
                loop = asyncio.get_event_loop()

                # 语义搜索任务（30秒超时）
                semantic_future = loop.create_task(
                    asyncio.wait_for(
                        self._semantic_search(request, permission_filter, db),
                        timeout=30.0
                    )
                )

                # 关键词搜索任务（10秒超时）
                keyword_future = loop.create_task(
                    asyncio.wait_for(
                        self._keyword_search(request, permission_filter, db),
                        timeout=10.0
                    )
                )

                # 知识图谱搜索任务：当前默认不参与 hybrid 主排序，权重为 0 时直接跳过
                kg_future = None
                if self.kg_manager and KG_HYBRID_SOURCE_WEIGHT > 0:
                    kg_future = loop.create_task(
                        asyncio.wait_for(
                            self._kg_search(request, permission_filter, db),
                            timeout=30.0
                        )
                    )

                # 等待结果（带异常处理）
                try:
                    results_dict["semantic"] = await semantic_future
                except asyncio.TimeoutError:
                    logger.warning("语义搜索超时")
                    results_dict["semantic"] = []
                except Exception as e:
                    logger.warning(f"语义搜索失败: {e}")
                    results_dict["semantic"] = []

                try:
                    results_dict["keyword"] = await keyword_future
                except asyncio.TimeoutError:
                    logger.warning("关键词搜索超时")
                    results_dict["keyword"] = []
                except Exception as e:
                    logger.warning(f"关键词搜索失败: {e}")
                    results_dict["keyword"] = []

                if kg_future:
                    try:
                        results_dict["kg"] = await kg_future
                    except asyncio.TimeoutError:
                        logger.warning("知识图谱搜索超时")
                        results_dict["kg"] = []
                    except Exception as e:
                        logger.warning(f"知识图谱搜索失败: {e}")
                        results_dict["kg"] = []

            # 三层语义搜索（如果可用）
            if self.three_layer_search:
                try:
                    # 复用已校验请求，避免重新实例化时触发 query/image 必填校验
                    three_layer_request = _clone_request_with_search_mode(
                        request,
                        SearchMode.THREE_LAYER_SEMANTIC,
                    )

                    three_layer_future = loop.create_task(
                        asyncio.wait_for(
                            self._three_layer_search(three_layer_request, SearchMode.THREE_LAYER_SEMANTIC, permission_filter, db),
                            timeout=30.0
                        )
                    )
                    results_dict["three_layer"] = await three_layer_future
                except asyncio.TimeoutError:
                    logger.warning("三层搜索超时")
                    results_dict["three_layer"] = []
                except Exception as e:
                    logger.warning(f"三层搜索失败: {e}")
                    results_dict["three_layer"] = []

            # 合并结果并去重
            combined_results = []
            seen_ids = set()
            search_stats = {}

            for search_name, results in results_dict.items():
                search_stats[search_name] = len(results) if results else 0

                for result in (results or []):
                    result_id = result.get("id") or result.get("chunk_id") or str(hash(str(result)))
                    if result_id not in seen_ids:
                        # 保留原始搜索模式信息
                        result["original_search_mode"] = search_name
                        combined_results.append(result)
                        seen_ids.add(result_id)

            # 智能评分和排序
            for result in combined_results:
                # 基础分数
                base_score = result.get("similarity_score", 0)

                # 根据来源增加权重
                source_weight = {
                    "kg": KG_HYBRID_SOURCE_WEIGHT,
                    "three_layer": 1.1,  # 三层搜索权重次高
                    "semantic": 1.0,     # 语义搜索标准权重
                    "file": 0.9,         # 文件级权重稍低
                    "keyword": 0.8       # 关键词权重最低
                }.get(result.get("original_search_mode", "unknown"), 0.7)

                # 更新分数
                result["hybrid_score"] = base_score * source_weight
                result["search_stats"] = search_stats

            # 按混合分数排序
            combined_results.sort(key=lambda x: x.get("hybrid_score", 0), reverse=True)

            # 添加混合搜索标记
            for result in combined_results:
                result["search_mode"] = "hybrid"
                result["search_sources"] = list(search_stats.keys())

            logger.info(f"混合搜索完成 - 搜索统计: {search_stats}, 总结果数: {len(combined_results)}")

            return combined_results[:request.top_k]

        except Exception as e:
            logger.error(f"混合检索失败: {e}", exc_info=True)
            # 降级到智能搜索
            return await self._intelligent_search(request, permission_filter, db)

    async def _execute_kg_query(
        self,
        query: str,
        kg_config: Dict,
        document_ids: Optional[List[str]] = None,
    ) -> List[Dict]:
        """执行知识图谱查询（后端无关：neo4j/postgres）"""
        if not self.kg_manager or not getattr(self.kg_manager, "is_enabled", lambda: False)():
            return []

        search_type = (kg_config.get("search_type") or "entity").lower()
        max_depth = int(kg_config.get("max_depth") or 3)
        limit = int(kg_config.get("limit") or 20)
        normalized_document_ids = _normalize_str_list(document_ids)

        # 统一返回格式：[{ "n": {..node..}, "types": [...], "similarity": 0.8 }]
        async def to_node_records(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            records: List[Dict[str, Any]] = []
            for node in nodes or []:
                props = node.get("properties") if isinstance(node, dict) else {}
                props = props or {}

                node_id = node.get("id") if isinstance(node, dict) else None
                if not node_id:
                    node_id = props.get("entity_id") or props.get("id") or props.get("name")

                name = node.get("name") if isinstance(node, dict) else None
                if not name:
                    name = props.get("name") or node_id or "未命名实体"

                description = node.get("description") if isinstance(node, dict) else None
                if not description:
                    description = props.get("description") or ""

                labels = node.get("labels") if isinstance(node, dict) else None
                if not labels:
                    labels = props.get("labels") or []

                node_data = {**props, "id": node_id, "name": name, "description": description}
                records.append(
                    {
                        "n": node_data,
                        "types": labels,
                        "similarity": float(node.get("similarity", 0.8)) if isinstance(node, dict) else 0.8,
                    }
                )
            return records

        def dedupe_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            deduped: List[Dict[str, Any]] = []
            seen_keys: set[tuple[str, str]] = set()
            for record in records:
                node = record.get("n") or {}
                key = (
                    str(node.get("id") or ""),
                    str(node.get("source_doc") or ""),
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                deduped.append(record)
            return deduped

        async def query_nodes_for_documents() -> List[Dict[str, Any]]:
            records: List[Dict[str, Any]] = []
            for document_id in normalized_document_ids:
                nodes = await self.kg_manager.query_nodes(
                    query=query,
                    document_id=document_id,
                    limit=limit,
                )
                records.extend(await to_node_records(nodes))
            return dedupe_records(records)

        async def query_nodes_from_edges(edge_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            edge_node_ids: List[str] = []
            for edge in edge_rows or []:
                source_id = edge.get("source") or edge.get("source_id")
                target_id = edge.get("target") or edge.get("target_id")
                if source_id:
                    edge_node_ids.append(str(source_id))
                if target_id:
                    edge_node_ids.append(str(target_id))

            edge_node_ids = list(dict.fromkeys(edge_node_ids))
            if not edge_node_ids:
                return []

            nodes = await self.kg_manager.query_nodes(
                node_ids=edge_node_ids,
                limit=max(len(edge_node_ids), limit),
            )
            nodes_map = {
                str(node.get("id")): node
                for node in (nodes or [])
                if node.get("id") is not None
            }

            records: List[Dict[str, Any]] = []
            for edge in edge_rows or []:
                edge_source_doc = edge.get("source_doc")
                for node_id in (
                    edge.get("source") or edge.get("source_id"),
                    edge.get("target") or edge.get("target_id"),
                ):
                    if node_id is None:
                        continue
                    base_node = dict(nodes_map.get(str(node_id)) or {"id": str(node_id), "name": str(node_id)})
                    node_props = dict(base_node.get("properties") or {})
                    if edge_source_doc and not (base_node.get("source_doc") or node_props.get("source_doc")):
                        node_props["source_doc"] = edge_source_doc
                        base_node["source_doc"] = edge_source_doc
                    if node_props:
                        base_node["properties"] = node_props
                    records.extend(await to_node_records([base_node]))

            return dedupe_records(records)

        # 1) entity/nodes
        if search_type in {"entity", "nodes", "node", "mixed"}:
            if normalized_document_ids:
                return await query_nodes_for_documents()
            qres = await self.kg_manager.search_knowledge_graph(query, search_type="nodes", limit=limit)
            return await to_node_records(qres.nodes)

        # 2) relation/edges：将匹配到的边映射回相关节点（更适合统一检索结果展示）
        if search_type in {"relation", "edges", "edge"}:
            if normalized_document_ids:
                edge_rows: List[Dict[str, Any]] = []
                for document_id in normalized_document_ids:
                    edge_rows.extend(
                        await self.kg_manager.query_edges(
                            query=query,
                            document_id=document_id,
                            limit=limit,
                        )
                    )
                return await query_nodes_from_edges(edge_rows)
            qres = await self.kg_manager.search_knowledge_graph(query, search_type="edges", limit=limit)
            return await query_nodes_from_edges(qres.edges)

        # 3) path：回退为“围绕 query 的子图”节点集合
        if search_type == "path":
            if normalized_document_ids:
                return await query_nodes_for_documents()
            kg = await self.kg_manager.get_knowledge_graph(query, max_depth=max_depth, max_nodes=100)
            nodes = [
                {
                    "id": n.id,
                    "labels": n.labels,
                    "properties": n.properties,
                }
                for n in (kg.nodes or [])
            ]
            return await to_node_records(nodes)

        # fallback
        if normalized_document_ids:
            return await query_nodes_for_documents()
        qres = await self.kg_manager.search_knowledge_graph(query, search_type="nodes", limit=limit)
        return await to_node_records(qres.nodes)

    async def _convert_kg_results(self, kg_results: List[Dict], db: Session, query: str = "") -> List[Dict]:
        """将KG结果转换为统一格式"""
        unified_results = []

        logger.info(f"开始转换 {len(kg_results)} 条KG结果")

        for kg_result in kg_results:
            try:
                # 从KG节点提取信息
                node = kg_result.get('n')
                if node:
                    # node已经是字典了（在_execute_kg_query中已转换）
                    node_data = node if isinstance(node, dict) else dict(node)
                    logger.info(f"处理节点: {node_data.get('name', 'unknown')}")

                    # 尝试关联到RAG内容
                    content_record = None
                    node_props = node_data.get("properties") or {}
                    linked_content_id = (
                        node_data.get("content_id")
                        or node_data.get("resource_id")
                        or node_data.get("source_doc")
                        or node_props.get("content_id")
                        or node_props.get("resource_id")
                        or node_props.get("source_doc")
                    )
                    if linked_content_id:
                        content_record = db.query(RAGContent).filter(
                            (RAGContent.id == linked_content_id) | (RAGContent.resource_id == linked_content_id)
                        ).first()
                    resource_id = (
                        getattr(content_record, "resource_id", None)
                        or node_data.get("resource_id")
                        or node_props.get("resource_id")
                    )

                    # 构建统一结果
                    result = {
                        "id": node_data.get('id', f"kg_{node_data.get('name', 'unknown')}"),
                        "title": node_data.get('name', '未命名实体'),
                        "description": node_data.get('description', ''),
                        "content": content_record.content_text if content_record else '',
                        "content_type": "knowledge_graph",
                        "content_id": str(content_record.id) if content_record else (str(linked_content_id) if linked_content_id else None),
                        "resource_id": str(resource_id) if resource_id else None,
                        "source_doc": str(linked_content_id) if linked_content_id else None,
                        "similarity_score": self._calculate_kg_similarity(kg_result, query),  # 简化评分
                        "snippet": node_data.get('description', '')[:200] + "..." if node_data.get('description', '') else '',
                        "metadata": {
                            "kg_node_id": node_data.get('id'),
                            "kg_labels": kg_result.get('types', []),
                            "kg_properties": node_data,
                            "linked_content_id": content_record.id if content_record else (str(linked_content_id) if linked_content_id else None),
                            "resource_id": str(resource_id) if resource_id else None,
                            "source_doc": str(linked_content_id) if linked_content_id else None,
                        }
                    }
                    unified_results.append(result)
            except Exception as e:
                logger.warning(f"转换KG结果失败: {e}")
                continue

        return unified_results

    def _calculate_kg_similarity(self, kg_result: Dict, query: str) -> float:
        """计算KG结果的相似度分数"""
        # 简化的KG相似度计算
        base_score = 0.8  # KG结果基础分数

        # 可以根据节点类型、属性匹配度等调整分数
        node = kg_result.get('n')
        if node and query:
            # node已经是字典了（在_execute_kg_query中已转换）
            node_data = node if isinstance(node, dict) else dict(node)
            name = node_data.get('name', '').lower()
            query_lower = query.lower()

            if query_lower in name:
                base_score += 0.2
            elif any(word in name for word in query_lower.split()):
                base_score += 0.1

        return min(1.0, base_score)

    async def _apply_permission_filter(self, results: List[Dict], permission_filter: Dict, db: Session) -> List[Dict]:
        """应用权限和其他过滤条件"""
        if not results:
            return results

        logger.debug(f"权限过滤开始: 输入结果 {len(results)} 个")
        logger.debug(f"权限过滤器配置: {permission_filter}")

        filtered_results = []
        requested_resource_ids = set(_normalize_str_list(permission_filter.get("resource_ids")))
        requested_resource_types = set(_normalize_str_list(permission_filter.get("resource_types")))
        user_permissions = set(_normalize_str_list(permission_filter.get("user_permissions")))
        has_scope_filters = bool(
            requested_resource_ids
            or requested_resource_types
            or permission_filter.get("collection_ids")
        )

        # 批量获取所有需要的内容记录
        content_records_map, content_records_by_resource_id = self._load_content_record_maps(results, db)
        logger.debug(f"从数据库查询到 {len(content_records_map)} 个内容记录（按 content_id）")
        logger.debug(f"从数据库查询到 {len(content_records_by_resource_id)} 个内容记录（按 resource_id）")

        # 预计算集合白名单（避免每条结果重复构造）
        allowed_colls = None
        if permission_filter.get("collection_ids"):
            allowed_colls = set()
            for cid in permission_filter["collection_ids"]:
                if not cid:
                    continue
                allowed_colls.add(cid)
                allowed_colls.add(cid.replace("_", "-"))
                allowed_colls.add(cid.replace("-", "_"))
                try:
                    allowed_colls.add(collection_mapper.to_milvus_name(cid))
                except Exception:
                    pass

        for i, result in enumerate(results):
            try:
                # 从批量查询结果中获取内容记录
                content_record = self._resolve_content_record_for_result(
                    result,
                    content_records_map,
                    content_records_by_resource_id,
                )

                if not content_record:
                    result_resource_id = _extract_result_resource_id(result)
                    if (
                        result.get("content_type") == "knowledge_graph"
                        and requested_resource_ids
                        and result_resource_id
                        and result_resource_id in requested_resource_ids
                    ):
                        filtered_results.append(result)
                        continue
                    if result.get("content_type") == "knowledge_graph" and not has_scope_filters:
                        filtered_results.append(result)
                    continue

                # 权限过滤：公开内容直接放行；否则检查bindings交集
                if user_permissions and not getattr(content_record, 'is_public', True):
                    content_bindings = set(content_record.bindings or [])

                    # 如果有绑定权限要求，检查交集
                    if content_bindings and not content_bindings.intersection(user_permissions):
                        logger.warning(f"🔍 [DEBUG] 权限过滤: 用户权限 {user_permissions} 与内容绑定 {content_bindings} 无交集，过滤掉")
                        continue

                if requested_resource_ids and getattr(content_record, "resource_id", None) not in requested_resource_ids:
                    continue

                # 资源类型过滤
                if requested_resource_types:
                    if content_record.resource_type not in requested_resource_types:
                        continue

                # 集合过滤
                if allowed_colls is not None:
                    if content_record.vector_collection and content_record.vector_collection not in allowed_colls:
                        continue

                filtered_results.append(result)

            except Exception as e:
                logger.warning(f"过滤结果时出错: {e}")
                continue

        return filtered_results

    async def _expand_results_with_graph(
        self,
        *,
        results: List[Dict[str, Any]],
        db: Session,
        permission_filter: Dict[str, Any],
        max_hops: int = 2,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """基于知识图谱做跨文档扩展：从当前候选文档出发，补充相关文档到结果集。

        说明：
        - 这里的“图谱”指 doc -> entity 与 entity -> entity 关系网络（PG/Neo4j 后端由配置决定）
        - 仅补充“文档级”候选（不做二次向量检索），避免额外成本
        """
        if not results:
            return results
        if not self.kg_manager or not getattr(self.kg_manager, "is_enabled", lambda: False)():
            return results

        try:
            max_hops = int(max_hops or 0)
        except Exception:
            max_hops = 2
        try:
            top_k = int(top_k or 0)
        except Exception:
            top_k = 10
        if max_hops <= 0 or top_k <= 0:
            return results

        def _extract_doc_id(r: Dict[str, Any]) -> Optional[str]:
            meta = r.get("metadata") or {}
            cid = (
                meta.get("doc_id")
                or meta.get("content_id")
                or r.get("doc_id")
                or r.get("content_id")
                or (r.get("id") if r.get("content_type") != "knowledge_graph" else None)
            )
            return str(cid) if cid else None

        # 1) 选择种子文档（按每个文档的最高分）
        doc_best_score: Dict[str, float] = {}
        for r in results:
            doc_id = _extract_doc_id(r)
            if not doc_id:
                continue
            score = r.get("similarity_score", None)
            if score is None:
                score = r.get("score", 0.0)
            try:
                score_f = float(score or 0.0)
            except Exception:
                score_f = 0.0
            doc_best_score[doc_id] = max(doc_best_score.get(doc_id, 0.0), score_f)

        if not doc_best_score:
            return results

        seed_docs = sorted(doc_best_score.items(), key=lambda x: x[1], reverse=True)[:3]
        seed_doc_ids = [d for d, _ in seed_docs]
        existing_doc_ids = set(doc_best_score.keys())

        # 2) 批量拉取种子文档信息（用于 collection 隔离）
        seed_records = (
            db.query(RAGContent).filter(RAGContent.id.in_(seed_doc_ids)).all() if seed_doc_ids else []
        )
        seed_map = {str(r.id): r for r in seed_records}

        # 3) 通过图谱找相关文档
        candidates: Dict[str, Dict[str, Any]] = {}
        per_seed_limit = max(10, min(50, top_k * 3))
        for seed_doc_id, seed_score in seed_docs:
            rec = seed_map.get(seed_doc_id)
            vector_collection = (getattr(rec, "vector_collection", None) or "").strip() or None

            related = await self.kg_manager.find_related_documents(
                seed_doc_id,
                max_hops=max_hops,
                limit=per_seed_limit,
                vector_collection=vector_collection,
            )
            for rel in related or []:
                rid = (rel.get("doc_id") or "").strip()
                if not rid or rid in existing_doc_ids:
                    continue

                hop = int(rel.get("hop_distance") or 1)
                match_count = int(rel.get("match_count") or 0)
                via_entities = rel.get("via_entities") or []

                # 评分：以“种子文档得分”为主，叠加“重合实体数”并按 hop 衰减
                match_bonus = min(1.0, float(match_count) / 10.0)
                combined = (0.7 * float(seed_score) + 0.3 * match_bonus) / max(1, hop)

                prev = candidates.get(rid)
                if not prev or combined > float(prev.get("similarity_score", 0.0) or 0.0):
                    candidates[rid] = {
                        "doc_id": rid,
                        "similarity_score": float(combined),
                        "kg_hop_distance": hop,
                        "kg_match_count": match_count,
                        "kg_from_doc_id": seed_doc_id,
                        "kg_via_entities": via_entities[:10],
                    }

        if not candidates:
            return results

        # 4) 只取少量扩展结果，避免挤掉原始结果
        add_limit = max(1, min(len(candidates), max(3, top_k // 2)))
        sorted_candidates = sorted(
            candidates.values(), key=lambda x: x.get("similarity_score", 0.0), reverse=True
        )[:add_limit]
        candidate_doc_ids = [c["doc_id"] for c in sorted_candidates]

        # 5) 补齐文档内容并应用权限过滤
        docs = db.query(RAGContent).filter(RAGContent.id.in_(candidate_doc_ids)).all() if candidate_doc_ids else []
        doc_map = {str(d.id): d for d in docs}

        expanded: List[Dict[str, Any]] = []
        for c in sorted_candidates:
            doc = doc_map.get(str(c["doc_id"]))
            if not doc:
                continue

            content = (
                doc.content_summary
                or doc.description
                or (doc.content_text[:1000] if doc.content_text else "")
            )
            snippet = (doc.content_summary or doc.description or (doc.content_text or ""))[:200]

            expanded.append(
                {
                    "id": str(doc.id),  # 文档级候选，id 即 doc_id
                    "doc_id": str(doc.id),
                    "title": doc.title or "",
                    "description": doc.description or "",
                    "content": content or "",
                    "content_type": doc.content_type or "",
                    "similarity_score": float(c.get("similarity_score") or 0.0),
                    "snippet": snippet,
                    "metadata": {
                        "doc_id": str(doc.id),
                        "vector_collection": doc.vector_collection,
                        "kg": {
                            "hop_distance": int(c.get("kg_hop_distance") or 1),
                            "match_count": int(c.get("kg_match_count") or 0),
                            "from_doc_id": c.get("kg_from_doc_id"),
                            "via_entities": c.get("kg_via_entities") or [],
                        },
                    },
                }
            )

        expanded = await self._apply_permission_filter(expanded, permission_filter, db)
        if not expanded:
            return results

        merged = list(results) + expanded
        merged.sort(key=lambda x: x.get("similarity_score", x.get("score", 0.0)) or 0.0, reverse=True)
        return merged[:top_k]

    async def _post_process_results(self, results: List[Dict], request, db: Session) -> List[Dict]:
        """后处理结果"""
        processed_results = []

        content_records_map, content_records_by_resource_id = self._load_content_record_maps(results, db)

        for result in results:
            try:
                # 控制返回内容
                if not request.include_content:
                    result.pop("content", None)

                if not request.include_snippet:
                    result.pop("snippet", None)

                if not request.include_metadata:
                    result.pop("metadata", None)

                # 丰富元数据（如果需要）并统一外部标识
                original_id = result.get("id")
                content_id = _extract_result_content_id(result)
                fallback_resource_id = _extract_result_resource_id(result)
                content_record = self._resolve_content_record_for_result(
                    result,
                    content_records_map,
                    content_records_by_resource_id,
                )

                if request.include_metadata and "metadata" in result and content_record:
                    result["metadata"].update({
                        "resource_id": content_record.resource_id,
                        "resource_type": content_record.resource_type,
                        "bindings": content_record.bindings,
                        "vector_collection": content_record.vector_collection,
                        "create_time": content_record.create_time.isoformat() if content_record.create_time else None
                    })
                # 对外暴露 resource_id + collection_id + version，并保留 debug.internal.content_id
                if content_record:
                    try:
                        meta = content_record.content_metadata
                        meta_obj = meta if isinstance(meta, dict) else ({} if not meta else __import__('json').loads(meta))
                        version = int(meta_obj.get("version", 1))
                    except Exception:
                        version = 1
                    resolved_content_id = str(content_record.id)
                    result["resource_id"] = content_record.resource_id
                    result["collection_id"] = content_record.vector_collection
                    result["version"] = version
                    internal = result.setdefault("debug", {}).setdefault("internal", {})
                    internal["content_id"] = resolved_content_id
                    if original_id and str(original_id) != resolved_content_id:
                        internal.setdefault("vector_id", str(original_id))
                    # 隐藏内部 id
                    if "id" in result:
                        result.pop("id", None)
                elif fallback_resource_id:
                    result["resource_id"] = fallback_resource_id
                    if request.include_metadata and "metadata" in result:
                        result["metadata"].setdefault("resource_id", fallback_resource_id)

                processed_results.append(result)

            except Exception as e:
                logger.warning(f"后处理结果时出错: {e}")
                processed_results.append(result)  # 保留原结果

        return processed_results

    def _build_execution_info(self, start_time: datetime, mode: str, result_count: int, request) -> Dict:
        """构建执行信息"""
        execution_time = (datetime.now() - start_time).total_seconds()

        return {
            "execution_time_ms": int(execution_time * 1000),
            "search_mode_used": mode,
            "result_count": result_count,
            "query_analysis": {
                "original_mode": request.search_mode,
                "selected_mode": mode,
                "query_length": len(request.query or ""),
                "has_filters": bool(
                    getattr(request, "collection_id", None)
                    or getattr(request, "resource_id", None)
                    or getattr(request, "resource_types", None)
                )
            },
            "performance": {
                "vector_search_available": self.enhanced_rag.embedding_model is not None,
                "kg_search_available": bool(self.kg_manager and getattr(self.kg_manager, "is_enabled", lambda: False)()),
                "total_collections_searched": len(request.collection_id) if request.collection_id else 1
            }
        }

    async def _generate_suggestions(self, query: str, results: List[Dict]) -> Optional[List[str]]:
        """生成搜索建议"""
        try:
            query_text = (query or "").strip()
            suggestions = []

            # 基于结果生成相关建议
            if results:
                # 从标题和标签中提取关键词
                keywords = set()
                for result in results[:3]:  # 只看前3个结果
                    if result.get("title"):
                        keywords.update(result["title"].split()[:3])

                    metadata = result.get("metadata", {})
                    if metadata.get("content_tags"):
                        try:
                            tags = metadata["content_tags"]
                            if isinstance(tags, list):
                                keywords.update(tags[:2])
                        except:
                            pass

                # 生成相关查询建议
                for keyword in list(keywords)[:5]:
                    if len(keyword) <= 1:
                        continue
                    if query_text:
                        if keyword not in query_text:
                            suggestions.append(f"{query_text} {keyword}")
                    else:
                        suggestions.append(str(keyword))

            # 添加一些通用的搜索建议
            if "架构" in query_text:
                suggestions.extend(["系统架构设计", "技术架构文档", "架构最佳实践"])
            elif "配置" in query_text:
                suggestions.extend(["配置文档", "配置管理", "配置示例"])

            deduped = []
            seen = set()
            for item in suggestions:
                text = str(item).strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                deduped.append(text)

            return deduped[:5] or None  # 最多返回5个建议

        except Exception as e:
            logger.warning(f"生成搜索建议失败: {e}")
            return None

    async def get_suggestions(self, partial_query: str, limit: int, user_id: Optional[str]) -> List[str]:
        """获取搜索建议"""
        # 这里可以基于历史查询、热门搜索等生成建议
        # 简化实现
        common_queries = [
            "系统架构设计",
            "API接口文档",
            "数据库设计",
            "用户手册",
            "技术规范",
            "配置指南",
            "故障排除",
            "最佳实践"
        ]

        # 过滤匹配的建议
        suggestions = [q for q in common_queries if partial_query.lower() in q.lower()]
        return suggestions[:limit]

    def _visual_similarity_components_available(self) -> bool:
        try:
            import importlib

            importlib.import_module("app.shared.vlm.visual_embedding")
            importlib.import_module("app.core.rag.vector_db.pgvector_visual_db")
            return True
        except Exception:
            return False

    async def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        try:
            # 获取各组件状态
            enhanced_rag_stats = self.enhanced_rag.get_vector_db_stats()

            kg_available = False
            kg_stats = {}
            if self.kg_manager and getattr(self.kg_manager, "is_enabled", lambda: False)():
                try:
                    await self.kg_manager.initialize()
                    kg_available = True
                    # 具体统计在 KnowledgeGraphManager 内部按后端实现（失败则返回空）
                    kg_stats = await self.kg_manager.get_graph_statistics()
                except Exception as e:
                    logger.warning(f"获取KG统计失败: {e}")

            return {
                "search_modes": {
                    SearchMode.SEMANTIC: self.enhanced_rag.embedding_model is not None,
                    SearchMode.KEYWORD: True,  # 总是可用
                    SearchMode.KG: kg_available,
                    SearchMode.HYBRID: True,  # 总是可用
                    SearchMode.INTELLIGENT: True,  # 总是可用
                    SearchMode.IMAGE_TO_IMAGE: self._visual_similarity_components_available(),
                    SearchMode.THREE_LAYER_KEYWORD: self.three_layer_search is not None,
                    SearchMode.THREE_LAYER_SEMANTIC: self.three_layer_search is not None,
                    SearchMode.THREE_LAYER_DOCUMENT: self.three_layer_search is not None
                },
                "vector_db_stats": enhanced_rag_stats,
                "kg_stats": kg_stats,
                "system_info": {
                    "embedding_model": (
                        getattr(self.enhanced_rag.embedding_model, "model_name", None)
                        if self.enhanced_rag.embedding_model
                        else None
                    ),
                    "vector_db": "FAISS",
                    "graph_db": (getattr(settings.graph_db, "GRAPH_DB_TYPE", "postgres") if kg_available else None)
                }
            }

        except Exception as e:
            logger.error(f"获取系统统计失败: {e}")
            return {"error": str(e)}

    def _build_cache_key(self, request, user_id: Optional[str]) -> str:
        """构建缓存键"""
        query_text = (getattr(request, 'query', None) or '')
        key_parts = [
            "search",
            request.search_mode if hasattr(request, 'search_mode') else 'default',
            str(getattr(request, 'top_k', 10)),
            query_text[:50],  # 限制查询长度
            user_id if user_id else 'anonymous'
        ]

        # 添加集合ID如果存在
        if hasattr(request, 'collection_id') and request.collection_id:
            key_parts.append(",".join(sorted(request.collection_id)))

        resource_ids = _normalize_str_list(getattr(request, "resource_id", None))
        if resource_ids:
            key_parts.append("resource=" + ",".join(sorted(resource_ids)))

        resource_types = _normalize_str_list(getattr(request, "resource_types", None))
        if resource_types:
            key_parts.append("type=" + ",".join(sorted(resource_types)))

        image_input = getattr(request, "image", None)
        if image_input:
            image_hash = self._compute_image_hash(image_input)
            if image_hash:
                key_parts.append(f"img:{image_hash}")

        return ":".join(key_parts)

    def _extract_search_keywords(self, image_description: str) -> str:
        """
        从图片描述中提取适合搜索的关键词

        Args:
            image_description: 图片分析结果

        Returns:
            适合搜索的关键词字符串
        """
        try:
            import re

            # 1. 如果已经是关键词格式（逗号分隔），直接使用
            if '，' in image_description or ',' in image_description:
                # 清理格式，提取关键词
                keywords = []
                # 分割并清理
                for part in re.split(r'[，,]', image_description):
                    keyword = part.strip()
                    # 过滤掉过短或无意义的词
                    if len(keyword) >= 2 and len(keyword) <= 10:
                        keywords.append(keyword)

                if keywords:
                    return ' '.join(keywords[:10])  # 限制最多10个关键词

            # 2. 从长文本中提取关键词
            keywords = []

            # 技术术语模式
            tech_patterns = [
                r'[A-Za-z]{2,}\d{1,3}',  # 型号如 Camera 01
                r'[\u4e00-\u9fa5]{2,4}(?:系统|设备|软件|硬件|功能)',  # 技术系统
                r'[\u4e00-\u9fa5]{2,6}(?:监控|摄像|录像|界面)',  # 监控相关
                r'[\u4e00-\u9fa5]{2,4}(?:命令|操作|管理|配置)',  # 操作相关
            ]

            # 提取技术术语
            for pattern in tech_patterns:
                matches = re.findall(pattern, image_description)
                keywords.extend(matches)

            # 3. 提取中文词汇（2-4字）
            chinese_words = re.findall(r'[\u4e00-\u9fa5]{2,4}', image_description)
            keywords.extend(chinese_words)

            # 调试日志
            logger.info(f"关键词提取 - 技术术语数量: {len([k for k in keywords if any(t in k for t in ['系统','设备','功能','监控','摄像'])])}")
            logger.info(f"关键词提取 - 中文词汇数量: {len(chinese_words)}")
            logger.info(f"关键词提取 - 总词汇数量: {len(keywords)}")
            logger.info(f"关键词提取 - 前10个词汇: {keywords[:10]}")

            # 4. 过滤和清理
            filtered_keywords = []
            stop_words = {'的', '是', '在', '和', '与', '或', '但', '而', '有', '没有', '这个', '那个', '可以', '能够'}

            for keyword in keywords:
                keyword = keyword.strip()
                # 过滤条件
                if (len(keyword) >= 2 and
                    len(keyword) <= 8 and
                    keyword not in stop_words and
                    not keyword.isdigit() and
                    keyword not in filtered_keywords):
                    filtered_keywords.append(keyword)

            # 5. 返回最适合搜索的关键词（限制数量和长度）
            if filtered_keywords:
                # 优先选择技术术语和核心概念
                priority_keywords = []
                other_keywords = []

                for kw in filtered_keywords:
                    if any(x in kw for x in ['系统', '设备', '功能', '监控', '摄像', '管理', '配置']):
                        priority_keywords.append(kw)
                    else:
                        other_keywords.append(kw)

                # 组合结果（优先词在前）
                final_keywords = priority_keywords[:5] + other_keywords[:10]

                if final_keywords:
                    return ' '.join(final_keywords[:15])  # 最多15个关键词

            # 6. 如果没有提取到关键词，使用智能降级处理
            return self._smart_fallback_extraction(image_description)

        except Exception as e:
            logger.warning(f"关键词提取失败: {e}，使用智能降级处理")
            # 降级处理：使用智能降级提取
            return self._smart_fallback_extraction(image_description)

    def _smart_fallback_extraction(self, text: str) -> str:
        """
        智能降级关键词提取
        当正常提取失败时的备用方案
        """
        try:
            import re

            # 1. 直接检查是否已经是逗号分隔的关键词格式
            if '，' in text or ',' in text:
                keywords = []
                for part in re.split(r'[，,]', text):
                    keyword = part.strip()
                    if 2 <= len(keyword) <= 10 and keyword not in {'的', '是', '在', '和', '有', '一个'}:
                        keywords.append(keyword)
                if keywords:
                    return ' '.join(keywords[:10])

            # 2. 提取有价值的词汇，避免无意义的开头
            valuable_words = []

            # 常见的无意义开头词汇
            useless_prefixes = ['在您提供的', '图像中', '显示的是', '这是一张', '图片显示', '根据图片']

            # 分词处理
            words = text.split()

            # 跳过无意义的前缀
            skip_count = 0
            for word in words:
                for prefix in useless_prefixes:
                    if word.startswith(prefix) or prefix.startswith(word):
                        skip_count += 1
                        break
                else:
                    break

            # 从有意义的词汇开始提取
            meaningful_words = words[skip_count:skip_count+30]  # 取后面30个词

            # 提取技术相关词汇
            tech_keywords = []
            other_keywords = []

            stop_words = {'的', '是', '在', '和', '与', '或', '但', '而', '有', '没有', '这个', '那个', '可以', '能够', '通过', '基于', '根据'}

            for word in meaningful_words:
                word = word.strip('，,。！？；：""''（）【】')

                # 跳过停用词和过短的词
                if (len(word) < 2 or word in stop_words or word.isdigit()):
                    continue

                # 识别技术关键词
                if any(tech in word for tech in ['系统', '设备', '功能', '监控', '摄像', '管理', '配置', '命令', '操作', '界面', '录像', '刷新', '重置', 'Camera', '软件', '硬件']):
                    tech_keywords.append(word)
                elif len(word) >= 2 and len(word) <= 8:
                    other_keywords.append(word)

            # 组合结果：技术关键词优先
            final_keywords = tech_keywords[:8] + other_keywords[:7]

            if final_keywords:
                result = ' '.join(final_keywords)
                logger.info(f"智能降级提取成功: {result}")
                return result

            # 3. 最后的降级：返回文本中间部分（通常包含核心内容）
            if len(text) > 50:
                # 跳过开头，取中间部分
                middle_start = len(text) // 4
                middle_end = middle_start + 100
                middle_text = text[middle_start:middle_end]
                middle_words = re.findall(r'[\u4e00-\u9fa5]{2,8}|[A-Za-z]{2,10}', middle_text)
                if middle_words:
                    return ' '.join(middle_words[:10])

            # 4. 最终降级：返回前100个字符
            return text[:100]

        except Exception as e:
            logger.warning(f"智能降级提取也失败: {e}")
            return text[:100]

    def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        """从缓存获取结果"""
        try:
            cached = self.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.debug(f"缓存读取失败: {e}")
        return None

    def _save_to_cache(self, cache_key: str, result: Dict, ttl: int = 300):
        """保存结果到缓存"""
        try:
            # 清理大型对象避免缓存过大
            cache_result = result.copy()
            if 'results' in cache_result and len(cache_result['results']) > 50:
                cache_result['results'] = cache_result['results'][:50]

            self.redis_client.setex(
                cache_key,
                ttl,
                json.dumps(cache_result, ensure_ascii=False, default=str)
            )
        except Exception as e:
            logger.debug(f"缓存保存失败: {e}")

    def clear_cache(self, pattern: Optional[str] = None):
        """清除缓存"""
        if not self.redis_client:
            return 0

        try:
            if pattern:
                keys = self.redis_client.keys(f"search:*{pattern}*")
            else:
                keys = self.redis_client.keys("search:*")

            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")
            return 0

    # ==================== 图搜索相关方法 ====================

    async def _process_image_to_text(self, image_input: str, prompt: str) -> Optional[str]:
        """
        图片转文本：支持base64、URL、本地路径

        Args:
            image_input: 图片输入（base64/URL/本地路径）
            prompt: 图片分析提示词

        Returns:
            图片描述文本，失败返回None
        """
        try:
            # 1. 检查缓存（基于图片内容和提示词）
            image_hash = self._compute_image_hash(image_input)
            prompt_hash = self._compute_image_hash(prompt[:100]) if prompt else ""
            if image_hash and self.redis_client:
                cache_key = f"image_desc:{image_hash}:{prompt_hash}"
                try:
                    cached_desc = self.redis_client.get(cache_key)
                    if cached_desc:
                        logger.info(f"✅ 图片描述缓存命中: {image_hash[:16]}...")
                        return cached_desc
                except Exception as e:
                    logger.warning(f"读取图片描述缓存失败: {e}")

            # 2. 准备图片文件
            image_path = await self._prepare_image_file(image_input)
            if not image_path:
                logger.error("图片文件准备失败")
                return None

            # 3. 使用VisionAnalyzer分析图片
            if not self.vision_analyzer:
                logger.error("VisionAnalyzer未初始化")
                return None

            result = self.vision_analyzer.analyze_image(
                image_path=image_path,
                prompt=prompt
            )

            # 4. 提取描述
            if result.success and result.data:
                description = result.data.get("description", "")
                if description:
                    # 保存到缓存（24小时）
                    if image_hash and self.redis_client:
                        try:
                            self.redis_client.setex(cache_key, 86400, description)
                            logger.info(f"✅ 图片描述已缓存: {image_hash[:16]}...")
                        except Exception as e:
                            logger.warning(f"保存图片描述缓存失败: {e}")

                    # 清理临时文件
                    await self._cleanup_temp_image(image_path, image_input)
                    return description
                else:
                    logger.warning("图片分析返回空描述")
            else:
                logger.error(f"图片分析失败: {result.error}")

            # 清理临时文件
            await self._cleanup_temp_image(image_path, image_input)
            return None

        except Exception as e:
            logger.error(f"图片转文本失败: {e}")
            return None

    async def _prepare_image_file(self, image_input: str) -> Optional[str]:
        """
        准备图片文件

        Args:
            image_input: base64字符串、URL或本地路径

        Returns:
            本地图片路径，失败返回None
        """
        import tempfile
        import base64
        import requests
        from pathlib import Path

        try:
            # 情况1: 本地文件路径
            if Path(image_input).exists():
                return str(Path(image_input).resolve())

            # 情况2: HTTP(S) URL
            if image_input.startswith(('http://', 'https://')):
                logger.info(f"下载图片: {image_input[:100]}...")
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                response = requests.get(image_input, timeout=10)
                response.raise_for_status()
                temp_file.write(response.content)
                temp_file.close()
                logger.info(f"✅ 图片已下载: {temp_file.name}")
                return temp_file.name

            # 情况3: Base64编码
            if ';base64,' in image_input:
                # 格式: data:image/jpeg;base64,/9j/4AAQ...
                header, encoded = image_input.split(';base64,', 1)
                data = base64.b64decode(encoded)
            else:
                # 纯base64字符串
                data = base64.b64decode(image_input)

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_file.write(data)
            temp_file.close()
            logger.info(f"✅ Base64图片已解码: {temp_file.name}")
            return temp_file.name

        except Exception as e:
            logger.error(f"准备图片文件失败: {e}")
            return None

    def _compute_image_hash(self, image_input: str) -> Optional[str]:
        """计算图片哈希用于缓存"""
        import hashlib
        try:
            return hashlib.md5(image_input.encode()).hexdigest()
        except Exception:
            return None

    async def _cleanup_temp_image(self, image_path: str, original_input: str):
        """清理临时图片文件"""
        import os
        from pathlib import Path

        try:
            # 只清理临时文件，不清理原始本地文件
            if image_path != original_input and '/tmp/' in image_path:
                if os.path.exists(image_path):
                    os.remove(image_path)
                    logger.debug(f"已清理临时图片: {image_path}")
        except Exception as e:
            logger.warning(f"清理临时图片失败: {e}")


# 全局服务实例
_unified_search_service = None

def get_unified_search_service() -> UnifiedSearchService:
    """获取统一检索服务实例"""
    global _unified_search_service
    if _unified_search_service is None:
        _unified_search_service = UnifiedSearchService()
    return _unified_search_service
