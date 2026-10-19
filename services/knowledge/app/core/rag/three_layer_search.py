#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可配置的三层知识图谱搜索系统
用户可选择搜索深度：关键词搜索、语义搜索、文档搜索
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple, Set
from enum import Enum
import numpy as np
from dataclasses import dataclass
import logging
import re
import os
import json
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from app.db.models.rag import RAGContent, RAGChunk, RAGCollection
from app.db.session import get_db
from app.core.cache.redis_cache import get_redis_cache

logger = logging.getLogger(__name__)


class SearchMode(Enum):
    """搜索模式枚举"""
    KEYWORD = "keyword"      # 关键词搜索 - Level 3 词汇层（最快）
    SEMANTIC = "semantic"    # 语义搜索 - Level 2 分块层（平衡）
    DOCUMENT = "document"    # 文档搜索 - 全部三层（最全面）


@dataclass
class SearchConfig:
    """搜索配置"""
    mode: SearchMode = SearchMode.SEMANTIC
    top_k: int = 10
    use_cache: bool = True
    use_rerank: bool = True
    expand_context: bool = True
    include_relations: bool = False

    # 集合配置
    collection_name: Optional[str] = None  # 指定搜索的集合，None表示使用default

    # 知识图谱配置
    max_graph_hops: int = 2  # 知识图谱最大跳数
    enable_graph_expansion: bool = False  # 是否启用图扩展搜索

    # 各层权重配置
    weights: Dict[str, float] = None

    def __post_init__(self):
        if self.weights is None:
            # 根据模式设置默认权重
            if self.mode == SearchMode.KEYWORD:
                self.weights = {
                    "term": 1.0,
                    "chunk": 0.0,
                    "document": 0.0
                }
            elif self.mode == SearchMode.SEMANTIC:
                self.weights = {
                    "term": 0.2,
                    "chunk": 0.8,
                    "document": 0.0
                }
            else:  # DOCUMENT
                self.weights = {
                    "term": 0.2,
                    "chunk": 0.5,
                    "document": 0.3
                }


@dataclass
class SearchResult:
    """搜索结果"""
    content: str
    score: float
    doc_id: str
    chunk_id: Optional[str] = None
    metadata: Dict[str, Any] = None
    context: Optional[str] = None
    relations: Optional[List[str]] = None
    search_path: Optional[str] = None  # 显示使用了哪些层


class ThreeLayerSearch:
    """三层知识图谱搜索系统"""

    def __init__(self):
        self.cache = get_redis_cache()
        self.init_layers()

    def _make_cache_key(self, prefix: str, query: str, config: SearchConfig) -> str:
        """生成与 SearchConfig 绑定的缓存 key，避免不同配置/集合串缓存。"""
        payload = {
            "query": query,
            "mode": getattr(config.mode, "value", str(config.mode)),
            "top_k": config.top_k,
            "collection_name": config.collection_name,
            "use_cache": config.use_cache,
            "use_rerank": config.use_rerank,
            "expand_context": config.expand_context,
            "include_relations": config.include_relations,
            "max_graph_hops": config.max_graph_hops,
            "enable_graph_expansion": config.enable_graph_expansion,
            "weights": config.weights,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return f"search:{prefix}:{self._hash(raw)}"

    def init_layers(self):
        """初始化三层"""
        # Level 1: 文档层
        self.doc_layer = DocumentLayer()

        # Level 2: 分块层
        self.chunk_layer = ChunkLayer()

        # Level 3: 词汇层
        self.term_layer = TermLayer()

    async def search(self, query: str, config: Optional[SearchConfig] = None) -> List[SearchResult]:
        """
        统一搜索入口

        Args:
            query: 查询文本
            config: 搜索配置

        Returns:
            搜索结果列表
        """
        if config is None:
            config = SearchConfig()

        logger.info(f"搜索模式: {config.mode.value}, 查询: {query[:50]}...")

        # 根据模式选择搜索策略
        if config.mode == SearchMode.KEYWORD:
            return await self._keyword_search(query, config)
        elif config.mode == SearchMode.SEMANTIC:
            return await self._semantic_search(query, config)
        else:  # DOCUMENT
            return await self._document_search(query, config)

    async def _keyword_search(self, query: str, config: SearchConfig) -> List[SearchResult]:
        """
        关键词搜索 - 只使用词汇层（Level 3）
        最快，适合精确匹配
        延迟: 10-50ms
        """
        # 缓存检查
        if config.use_cache:
            cache_key = self._make_cache_key("keyword", query, config)
            cached_results = self.cache.get(cache_key)
            if cached_results:
                logger.debug("关键词搜索缓存命中")
                return cached_results

        # 词汇层检索
        term_results = await self.term_layer.search(query, config.top_k * 2)

        # 通过词汇找到相关分块
        chunk_ids = self._get_chunks_from_terms(term_results)
        chunks = await self.chunk_layer.get_chunks_by_ids(chunk_ids[:config.top_k])

        # 构建结果
        results = []
        for chunk in chunks:
            result = SearchResult(
                content=chunk.content,
                score=chunk.score,
                doc_id=chunk.doc_id,
                chunk_id=chunk.id,
                metadata=chunk.metadata,
                search_path="Term Layer Only"
            )
            results.append(result)

        # 缓存结果
        if config.use_cache:
            self.cache.set(cache_key, results, ttl=3600)

        logger.info(f"关键词搜索完成，返回 {len(results)} 个结果")
        return results

    async def _semantic_search(self, query: str, config: SearchConfig) -> List[SearchResult]:
        """
        语义搜索 - 主要使用分块层（Level 2）+ 轻量词汇增强
        平衡速度和效果
        延迟: 100-200ms
        """
        # 缓存检查
        if config.use_cache:
            cache_key = self._make_cache_key("semantic", query, config)
            cached_results = self.cache.get(cache_key)
            if cached_results:
                logger.debug("语义搜索缓存命中")
                return cached_results

        # 并行检索
        tasks = []

        # 主要：分块层向量检索
        tasks.append(self.chunk_layer.vector_search(
            query,
            config.top_k * 2,
            collection_name=config.collection_name  # ✅ 传递collection_name
        ))

        # 辅助：词汇层关键词匹配
        if config.weights["term"] > 0:
            tasks.append(self.term_layer.search(query, config.top_k))

        # 并行执行
        results = await asyncio.gather(*tasks)
        chunk_results = results[0]
        term_results = results[1] if len(results) > 1 else []

        # 融合结果
        fused_results = self._fusion_results(
            chunk_results=chunk_results,
            term_results=term_results,
            weights=config.weights,
            top_k=config.top_k
        )

        # Reranking
        if config.use_rerank:
            fused_results = await self._rerank(query, fused_results)

        # 上下文扩展
        if config.expand_context:
            fused_results = await self._expand_context(fused_results)

        # 构建最终结果
        final_results = []
        for item in fused_results[:config.top_k]:
            result = SearchResult(
                content=item['content'],
                score=item['score'],
                doc_id=item['doc_id'],
                chunk_id=item.get('chunk_id'),
                metadata=item.get('metadata'),
                context=item.get('context'),
                search_path="Chunk + Term Layers"
            )
            final_results.append(result)

        # 缓存结果
        if config.use_cache:
            self.cache.set(cache_key, final_results, ttl=1800)

        logger.info(f"语义搜索完成，返回 {len(final_results)} 个结果")
        return final_results

    async def _document_search(self, query: str, config: SearchConfig) -> List[SearchResult]:
        """
        文档搜索 - 使用完整三层架构
        最全面，适合复杂查询
        延迟: 300-500ms
        """
        # 缓存检查
        if config.use_cache:
            cache_key = self._make_cache_key("document", query, config)
            cached_results = self.cache.get(cache_key)
            if cached_results:
                logger.debug("文档搜索缓存命中")
                return cached_results

        # 三层并行检索
        tasks = [
            self.doc_layer.search(query, config.top_k),      # 文档层
            self.chunk_layer.vector_search(
                query,
                config.top_k * 2,
                collection_name=config.collection_name  # ✅ 传递collection_name
            ),  # 分块层
            self.term_layer.search(query, config.top_k * 2)   # 词汇层
        ]

        doc_results, chunk_results, term_results = await asyncio.gather(*tasks)

        # 三层融合
        fused_results = self._three_layer_fusion(
            doc_results=doc_results,
            chunk_results=chunk_results,
            term_results=term_results,
            weights=config.weights,
            top_k=config.top_k * 2
        )

        # 图关系增强
        if config.include_relations:
            fused_results = await self._enhance_with_graph(
                fused_results,
                max_hops=config.max_graph_hops
            )

            # 如果启用图扩展搜索，将相关文档也加入结果集
            if config.enable_graph_expansion:
                fused_results = await self._expand_with_graph(
                    fused_results,
                    config
                )

        # Reranking
        if config.use_rerank:
            fused_results = await self._rerank(query, fused_results)

        # 上下文扩展
        if config.expand_context:
            fused_results = await self._expand_context(fused_results)

        # 构建最终结果
        final_results = []
        for item in fused_results[:config.top_k]:
            result = SearchResult(
                content=item['content'],
                score=item['score'],
                doc_id=item['doc_id'],
                chunk_id=item.get('chunk_id'),
                metadata=item.get('metadata'),
                context=item.get('context'),
                relations=item.get('relations'),
                search_path="All Three Layers"
            )
            final_results.append(result)

        # 缓存结果
        if config.use_cache:
            self.cache.set(cache_key, final_results, ttl=1200)

        logger.info(f"文档搜索完成，返回 {len(final_results)} 个结果")
        return final_results

    def _fusion_results(self, chunk_results, term_results, weights, top_k):
        """融合多层结果"""
        score_map = {}

        # 处理分块结果
        for item in chunk_results:
            key = item.get('chunk_id', item.get('id'))
            if key not in score_map:
                score_map[key] = {
                    'content': item['content'],
                    'score': 0,
                    'doc_id': item['doc_id'],
                    'chunk_id': key,
                    'metadata': item.get('metadata', {})
                }
            score_map[key]['score'] += item['score'] * weights['chunk']

        # 处理词汇结果
        for item in term_results:
            # 词汇结果需要映射到分块
            chunk_ids = self._get_chunks_from_terms([item])
            for chunk_id in chunk_ids[:2]:  # 每个词汇最多影响2个分块
                if chunk_id in score_map:
                    score_map[chunk_id]['score'] += item['score'] * weights['term'] * 0.5

        # 排序返回
        sorted_results = sorted(score_map.values(), key=lambda x: x['score'], reverse=True)
        return sorted_results[:top_k]

    def _three_layer_fusion(self, doc_results, chunk_results, term_results, weights, top_k):
        """三层结果融合"""
        score_map = {}

        # 文档层
        for item in doc_results:
            doc_id = item['doc_id']
            # 文档分数传递给其所有分块
            doc_chunks = self._get_chunks_from_doc(doc_id)
            for chunk_id in doc_chunks:
                if chunk_id not in score_map:
                    score_map[chunk_id] = {'score': 0}
                score_map[chunk_id]['score'] += item['score'] * weights['document'] * 0.3

        # 分块层
        for item in chunk_results:
            chunk_id = item.get('chunk_id', item.get('id'))
            if chunk_id not in score_map:
                score_map[chunk_id] = {
                    'content': item['content'],
                    'score': 0,
                    'doc_id': item['doc_id'],
                    'chunk_id': chunk_id,
                    'metadata': item.get('metadata', {})
                }
            score_map[chunk_id]['score'] += item['score'] * weights['chunk']

        # 词汇层
        for item in term_results:
            chunk_ids = self._get_chunks_from_terms([item])
            for chunk_id in chunk_ids[:3]:
                if chunk_id in score_map:
                    score_map[chunk_id]['score'] += item['score'] * weights['term'] * 0.3

        # 排序返回
        sorted_results = sorted(score_map.values(), key=lambda x: x['score'], reverse=True)
        return sorted_results[:top_k]

    async def _rerank(self, query: str, results: List[Dict]) -> List[Dict]:
        """重排序结果"""
        try:
            # 尝试使用 reranker 模型
            from app.services.enhanced_rag_service import get_enhanced_rag_service
            rag_service = get_enhanced_rag_service()

            # 如果有嵌入模型，使用语义相似度重排序
            if rag_service.embedding_model and results:
                # 生成查询向量
                query_vector, _ = rag_service.embedding_model.encode_queries(query)

                # 获取所有结果的内容
                contents = [r.get('content', '') for r in results]

                # 生成内容向量
                if contents:
                    content_vectors, _ = rag_service.embedding_model.encode(contents)

                    # 计算相似度
                    similarities = np.dot(content_vectors, query_vector)

                    # 更新分数
                    for i, result in enumerate(results):
                        # 结合原始分数和语义相似度
                        original_score = result.get('score', 0)
                        semantic_score = float(similarities[i])
                        result['score'] = 0.5 * original_score + 0.5 * semantic_score

                # 重新排序
                results.sort(key=lambda x: x['score'], reverse=True)

            return results

        except Exception as e:
            logger.warning(f"重排序失败，返回原结果: {e}")
            return results

    async def _expand_context(self, results: List[Dict]) -> List[Dict]:
        """扩展上下文"""
        for result in results:
            if 'chunk_id' in result:
                # 获取前后分块
                context = await self.chunk_layer.get_context(
                    result['chunk_id'],
                    window=1
                )
                result['context'] = context
        return results

    async def _enhance_with_graph(self, results: List[Dict], max_hops: int = 2) -> List[Dict]:
        """
        图关系增强（支持多跳搜索）

        Args:
            results: 搜索结果
            max_hops: 最大跳数
        """
        for result in results:
            if 'doc_id' in result:
                # 获取多跳相关文档
                relations = await self.doc_layer.get_relations(
                    result['doc_id'],
                    max_hops=max_hops
                )
                result['relations'] = relations

                # 添加知识图谱路径信息
                if relations:
                    result['graph_info'] = {
                        'total_relations': len(relations),
                        'max_hop_distance': max([r['hop_distance'] for r in relations]),
                        'relation_types': list(set([r['relation_type'] for r in relations])),
                        'paths': [r['path'] for r in relations[:3]]  # 显示前3条路径
                    }
        return results

    async def _expand_with_graph(self, results: List[Dict], config: SearchConfig) -> List[Dict]:
        """
        图扩展搜索 - 将相关文档加入结果集

        这实现了真正的多跳搜索逻辑：
        1. 从初始搜索结果出发
        2. 通过知识图谱找到相关文档
        3. 将高相关性的文档加入结果集
        """
        expanded_results = list(results)  # 保留原始结果
        seen_doc_ids = {r.get('doc_id') for r in results if r.get('doc_id')}

        # 收集所有相关文档
        related_docs = []
        for result in results:
            if 'relations' in result and result['relations']:
                for relation in result['relations']:
                    if relation['doc_id'] not in seen_doc_ids:
                        # 添加相关文档，调整分数
                        related_doc = {
                            'doc_id': relation['doc_id'],
                            'title': relation['title'],
                            'content': '',  # 需要从数据库获取
                            'score': result.get('score', 0) * relation['score'],  # 传播分数
                            'hop_distance': relation['hop_distance'],
                            'from_doc': result.get('doc_id'),
                            'relation_type': relation['relation_type'],
                            'is_expanded': True,  # 标记为扩展结果
                            'expansion_path': relation['path']
                        }
                        related_docs.append(related_doc)
                        seen_doc_ids.add(relation['doc_id'])

        # 按分数排序相关文档
        related_docs.sort(key=lambda x: x['score'], reverse=True)

        # 只保留分数较高的相关文档
        threshold = 0.3  # 相关性阈值
        high_score_related = [
            doc for doc in related_docs
            if doc['score'] > threshold
        ][:config.top_k // 2]  # 最多添加一半的扩展结果

        # ✅ 补齐扩展结果内容（避免 content 为空导致后续 rerank/展示效果差）
        if high_score_related:
            try:
                db = next(get_db())
                try:
                    ids = [d.get("doc_id") for d in high_score_related if d.get("doc_id")]
                    docs = db.query(RAGContent).filter(RAGContent.id.in_(ids)).all() if ids else []
                    doc_map = {d.id: d for d in docs}
                finally:
                    db.close()

                for d in high_score_related:
                    doc = doc_map.get(d.get("doc_id"))
                    if not doc:
                        continue

                    if not d.get("title"):
                        d["title"] = doc.title or ""

                    if not d.get("content"):
                        content = (
                            doc.content_summary
                            or doc.description
                            or (doc.content_text[:500] if doc.content_text else "")
                        )
                        d["content"] = (content or "")[:500]

                    meta = d.get("metadata") or {}
                    meta.update(
                        {
                            "file_name": doc.file_name,
                            "content_summary": doc.content_summary,
                            "vector_collection": doc.vector_collection,
                        }
                    )
                    d["metadata"] = meta
            except Exception as e:
                logger.warning(f"图扩展结果补齐内容失败: {e}")

        # 合并结果
        expanded_results.extend(high_score_related)

        # 重新排序
        expanded_results.sort(key=lambda x: x.get('score', 0), reverse=True)

        logger.info(f"图扩展搜索: 原始结果 {len(results)} 个，扩展后 {len(expanded_results)} 个")

        return expanded_results

    def _get_chunks_from_terms(self, term_results) -> List[str]:
        """从词汇结果获取分块ID"""
        chunk_ids = []
        seen = set()

        for term in term_results:
            # 从词汇结果中提取分块ID
            term_chunk_ids = term.get('chunk_ids', [])
            if isinstance(term_chunk_ids, str):
                term_chunk_ids = [term_chunk_ids]

            for chunk_id in term_chunk_ids:
                if chunk_id not in seen:
                    chunk_ids.append(chunk_id)
                    seen.add(chunk_id)

        return chunk_ids

    def _get_chunks_from_doc(self, doc_id: str) -> List[str]:
        """获取文档的所有分块ID"""
        try:
            db = next(get_db())

            # 查询文档的所有分块
            chunks = db.query(RAGChunk).filter(
                RAGChunk.content_id == doc_id
            ).all()

            return [chunk.id for chunk in chunks]

        except Exception as e:
            logger.error(f"获取文档分块失败: {e}")
            return []
        finally:
            db.close()

    def _hash(self, text: str) -> str:
        """生成文本哈希"""
        import hashlib
        return hashlib.md5(text.encode()).hexdigest()


class DocumentLayer:
    """文档层（Level 1）"""

    def __init__(self):
        self._kg_manager = None
        try:
            from app.config import settings
            from app.core.kg.manager import KnowledgeGraphManager

            if settings.graph_db.is_configured:
                self._kg_manager = KnowledgeGraphManager(namespace=settings.graph_db.GRAPH_NAMESPACE)
        except Exception:
            self._kg_manager = None

    async def search(self, query: str, top_k: int) -> List[Dict]:
        """文档级搜索 - 搜索文档标题和摘要"""
        try:
            # 获取数据库连接
            db = next(get_db())

            # 搜索文档标题和摘要
            query_lower = query.lower()
            results = db.query(RAGContent).filter(
                or_(
                    func.lower(RAGContent.title).contains(query_lower),
                    func.lower(RAGContent.description).contains(query_lower),
                    func.lower(RAGContent.content_summary).contains(query_lower)
                )
            ).limit(top_k).all()

            # 转换为字典格式
            doc_results = []
            for doc in results:
                # 计算简单的相关性分数
                score = 0.0
                if doc.title and query_lower in doc.title.lower():
                    score += 0.5
                if doc.description and query_lower in doc.description.lower():
                    score += 0.3
                if doc.content_summary and query_lower in doc.content_summary.lower():
                    score += 0.2

                doc_results.append({
                    'doc_id': doc.id,
                    'title': doc.title or '',
                    'description': doc.description or '',
                    'content': doc.content_text[:500] if doc.content_text else '',
                    'score': score,
                    'metadata': {
                        'content_type': doc.content_type,
                        'file_name': doc.file_name,
                        'tags': doc.content_tags
                    }
                })

            # 按分数排序
            doc_results.sort(key=lambda x: x['score'], reverse=True)
            return doc_results[:top_k]

        except Exception as e:
            logger.error(f"文档层搜索失败: {e}")
            return []
        finally:
            db.close()

    async def get_relations(self, doc_id: str, max_hops: int = 2) -> List[Dict]:
        """
        获取文档关系（支持多跳查询）

        Args:
            doc_id: 文档ID
            max_hops: 最大跳数，默认2跳

        Returns:
            关系列表，包含关系类型和路径信息
        """
        try:
            # 获取数据库连接
            db = next(get_db())

            # 1) 优先走“知识图谱跨文档”关系（PG/Neo4j 由 KGManager 内部决定）
            if self._kg_manager and getattr(self._kg_manager, "is_enabled", lambda: False)():
                try:
                    doc_record = db.query(RAGContent).filter(RAGContent.id == doc_id).first()
                    vector_collection = (getattr(doc_record, "vector_collection", None) or "").strip() or None

                    related = await self._kg_manager.find_related_documents(
                        doc_id,
                        max_hops=max_hops,
                        limit=10,
                        vector_collection=vector_collection,
                    )
                    if related:
                        ids = [r.get("doc_id") for r in related if r.get("doc_id")]
                        docs = db.query(RAGContent).filter(RAGContent.id.in_(ids)).all() if ids else []
                        doc_map = {str(d.id): d for d in docs}

                        relations: List[Dict[str, Any]] = []
                        for item in related:
                            related_id = (item.get("doc_id") or "").strip()
                            if not related_id:
                                continue
                            related_doc = doc_map.get(related_id)
                            if not related_doc:
                                continue

                            hop = int(item.get("hop_distance") or 1)
                            match_count = int(item.get("match_count") or 0)
                            via_entities = item.get("via_entities") or []
                            via_text = ", ".join([str(v) for v in via_entities[:3] if v])

                            path = f"{doc_id} -> {related_id}" if hop == 1 else f"... -> {related_id}"
                            if via_text:
                                path = (
                                    f"{doc_id} --[{via_text}]--> {related_id}"
                                    if hop == 1
                                    else f"... --[{via_text}]--> {related_id}"
                                )

                            score = min(1.0, 0.2 * float(match_count)) / max(1, hop)

                            relations.append(
                                {
                                    "doc_id": related_id,
                                    "title": related_doc.title,
                                    "relation_type": "kg",
                                    "hop_distance": hop,
                                    "direction": "undirected",
                                    "path": path,
                                    "score": score,
                                    "via_entities": via_entities[:10],
                                }
                            )

                        relations.sort(key=lambda x: x.get("score", 0), reverse=True)
                        return relations[:10]
                except Exception as e:
                    logger.warning(f"通过知识图谱获取文档关系失败，降级到资源关系: {e}")

            # 2) 兜底：资源关系表（rag_resource_relations）多跳
            from app.db.models.rag import RAGResourceRelation

            # 存储访问过的节点，避免循环
            visited = set()
            visited.add(doc_id)

            # 结果列表
            all_relations = []

            # 当前层的文档ID
            current_level = [doc_id]

            # 多跳搜索
            for hop in range(1, max_hops + 1):
                next_level = []

                for current_doc_id in current_level:
                    # 查询直接关系
                    relations = db.query(RAGResourceRelation).filter(
                        or_(
                            RAGResourceRelation.source_resource_id == current_doc_id,
                            RAGResourceRelation.target_id == current_doc_id
                        )
                    ).all()

                    for rel in relations:
                        # 确定相关文档ID
                        if rel.source_resource_id == current_doc_id:
                            related_id = rel.target_id
                            direction = "outgoing"
                        else:
                            related_id = rel.source_resource_id
                            direction = "incoming"

                        # 跳过已访问的节点
                        if related_id in visited:
                            continue

                        visited.add(related_id)
                        next_level.append(related_id)

                        # 获取相关文档信息
                        related_doc = db.query(RAGContent).filter(
                            RAGContent.id == related_id
                        ).first()

                        if related_doc:
                            all_relations.append({
                                'doc_id': related_id,
                                'title': related_doc.title,
                                'relation_type': rel.relation_type if hasattr(rel, 'relation_type') else 'related',
                                'hop_distance': hop,
                                'direction': direction,
                                'path': f"{doc_id} -> {related_id}" if hop == 1 else f"... -> {related_id}",
                                'score': 1.0 / hop  # 距离越远，分数越低
                            })

                # 准备下一层
                current_level = next_level

                # 如果没有新节点，提前结束
                if not current_level:
                    break

            # 按分数排序
            all_relations.sort(key=lambda x: x['score'], reverse=True)
            return all_relations[:10]  # 最多返回10个相关文档

        except Exception as e:
            logger.error(f"获取文档关系失败: {e}")
            return []
        finally:
            db.close()


class ChunkLayer:
    """分块层（Level 2）"""

    async def vector_search(self, query: str, top_k: int, collection_name: Optional[str] = None) -> List[Dict]:
        """向量搜索

        Args:
            query: 查询文本
            top_k: 返回结果数量
            collection_name: 集合名称，None时使用"default"
        """
        try:
            # 使用现有的增强RAG服务
            from app.services.enhanced_rag_service import get_enhanced_rag_service
            rag_service = get_enhanced_rag_service()

            # 如果嵌入模型不可用，返回空
            if not rag_service.embedding_model:
                logger.warning("嵌入模型不可用，无法进行向量搜索")
                return []

            # 生成查询向量
            query_vector, _ = rag_service.embedding_model.encode_queries(query)

            # 使用向量数据库搜索
            if rag_service.vector_db:
                # ✅ 使用传入的collection_name，默认为"default"
                target_collection = collection_name or "default"
                ids, scores, metadatas = rag_service.vector_db.search(
                    collection_name=target_collection,
                    query_vector=query_vector,
                    top_k=top_k
                )

                # ✅ 构建结果（修复查询逻辑）
                results = []
                db = next(get_db())
                try:
                    id_list = [str(i) for i in ids]
                    chunks = (
                        db.query(RAGChunk).filter(RAGChunk.id.in_(id_list)).all() if id_list else []
                    )
                    chunk_map = {str(c.id): c for c in chunks}

                    for id, score, metadata in zip(id_list, scores, metadatas):
                        # 写入时 RAGChunk.id 已设置为 vector_id，因此可以直接匹配
                        chunk = chunk_map.get(str(id))

                        # 如果找到chunk，使用chunk_text；否则用metadata中的snippet
                        if chunk:
                            content = chunk.chunk_text
                            chunk_id = chunk.id
                            doc_id = chunk.content_id
                        else:
                            # 降级逻辑：从metadata中获取
                            logger.warning(f"未找到chunk记录，id={id}，使用metadata降级")
                            content = metadata.get('snippet', metadata.get('content', ''))
                            chunk_id = str(id)  # 使用Milvus的id作为chunk_id
                            doc_id = metadata.get('doc_id', '')

                        results.append({
                            'chunk_id': chunk_id,
                            'score': float(score),
                            'content': content[:500] if content else '',  # 限制内容长度
                            'doc_id': doc_id,
                            'metadata': metadata
                        })
                finally:
                    db.close()
                return results
            else:
                # 降级到数据库搜索
                return await self._fallback_db_search(query, top_k)

        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return await self._fallback_db_search(query, top_k)

    async def _fallback_db_search(self, query: str, top_k: int) -> List[Dict]:
        """降级的数据库搜索"""
        try:
            db = next(get_db())

            # 从RAGChunk表搜索
            query_lower = query.lower()
            chunks = db.query(RAGChunk).filter(
                func.lower(RAGChunk.chunk_text).contains(query_lower)
            ).limit(top_k).all()

            results = []
            for chunk in chunks:
                # 计算简单的相关性分数
                text_lower = chunk.chunk_text.lower() if chunk.chunk_text else ''
                score = text_lower.count(query_lower) / max(len(text_lower.split()), 1)

                results.append({
                    'chunk_id': str(chunk.id),  # ✅ 确保是字符串
                    'score': float(min(score, 1.0)),  # ✅ 确保是浮点数
                    'content': chunk.chunk_text[:500] if chunk.chunk_text else '',
                    'doc_id': str(chunk.content_id) if chunk.content_id else '',  # ✅ 确保是字符串
                    'metadata': {
                        'chunk_index': chunk.chunk_index,
                        'chunk_size': chunk.chunk_size
                    }
                })

            results.sort(key=lambda x: x['score'], reverse=True)
            return results

        except Exception as e:
            logger.error(f"数据库搜索失败: {e}")
            return []
        finally:
            db.close()

    async def get_chunks_by_ids(self, chunk_ids: List[str]) -> List[Dict]:
        """根据ID获取分块"""
        try:
            db = next(get_db())

            chunks = db.query(RAGChunk).filter(
                RAGChunk.id.in_(chunk_ids)
            ).all()

            results = []
            for chunk in chunks:
                results.append({
                    'id': chunk.id,
                    'content': chunk.chunk_text,
                    'doc_id': chunk.content_id,
                    'score': 1.0,
                    'metadata': {
                        'chunk_index': chunk.chunk_index,
                        'chunk_size': chunk.chunk_size
                    }
                })

            return results

        except Exception as e:
            logger.error(f"获取分块失败: {e}")
            return []
        finally:
            db.close()

    async def get_context(self, chunk_id: str, window: int = 1) -> str:
        """获取分块上下文"""
        try:
            db = next(get_db())

            # 获取当前分块
            current_chunk = db.query(RAGChunk).filter(
                RAGChunk.id == chunk_id
            ).first()

            if not current_chunk:
                return ""

            # 获取前后分块
            context_chunks = db.query(RAGChunk).filter(
                RAGChunk.content_id == current_chunk.content_id,
                RAGChunk.chunk_index >= current_chunk.chunk_index - window,
                RAGChunk.chunk_index <= current_chunk.chunk_index + window
            ).order_by(RAGChunk.chunk_index).all()

            # 拼接上下文
            context_texts = []
            for chunk in context_chunks:
                if chunk.id == chunk_id:
                    context_texts.append(f"[CURRENT] {chunk.chunk_text}")
                else:
                    context_texts.append(chunk.chunk_text)

            return "\n\n".join(context_texts)

        except Exception as e:
            logger.error(f"获取上下文失败: {e}")
            return ""
        finally:
            db.close()


class TermLayer:
    """词汇层（Level 3）
    支持内存索引和Milvus索引两种模式
    """

    def __init__(self):
        # 检查是否使用Milvus（优先走统一配置，兼容历史环境变量）
        try:
            from app.config import settings
            use_milvus = (getattr(settings.vector_db, "VECTOR_DB_TYPE", "faiss") or "faiss").lower() == "milvus"
        except Exception:
            # fallback：兼容旧变量名 VECTOR_VECTOR_DB_TYPE
            use_milvus = (os.getenv("VECTOR_DB_TYPE") or os.getenv("VECTOR_VECTOR_DB_TYPE") or "faiss").lower() == "milvus"

        if use_milvus:
            try:
                from app.core.rag.milvus_term_layer import MilvusTermLayer
                self.milvus_layer = MilvusTermLayer()
                self.use_milvus = True
                logger.info("使用Milvus词汇索引")
            except Exception as e:
                logger.warning(f"初始化Milvus词汇索引失败，降级到内存索引: {e}")
                self.use_milvus = False
                self.inverted_index = {}
                self._build_index()
        else:
            self.use_milvus = False
            self.inverted_index = {}  # 简单的内存倒排索引
            self._build_index()

    def _build_index(self):
        """构建倒排索引（简化版）"""
        if self.use_milvus:
            return  # Milvus模式不需要内存索引

        try:
            db = next(get_db())

            # 从数据库加载所有分块
            chunks = db.query(RAGChunk).limit(1000).all()  # 限制数量避免内存溢出

            for chunk in chunks:
                if not chunk.chunk_text:
                    continue

                # 分词（简单实现）
                words = self._tokenize(chunk.chunk_text)

                # 构建倒排索引
                for word in words:
                    if word not in self.inverted_index:
                        self.inverted_index[word] = []
                    self.inverted_index[word].append({
                        'chunk_id': chunk.id,
                        'doc_id': chunk.content_id,
                        'position': chunk.chunk_index
                    })

            logger.info(f"倒排索引构建完成，包含 {len(self.inverted_index)} 个词汇")

        except Exception as e:
            logger.error(f"构建倒排索引失败: {e}")
        finally:
            db.close()

    def _tokenize(self, text: str) -> Set[str]:
        """简单的分词函数"""
        # 转小写
        text = text.lower()

        # 提取英文单词
        english_words = set(re.findall(r'[a-z]+', text))

        # 提取中文词（简单的2-4字词）
        chinese_words = set()
        chinese_text = ''.join(re.findall(r'[\u4e00-\u9fa5]+', text))
        for length in [2, 3, 4]:
            for i in range(len(chinese_text) - length + 1):
                chinese_words.add(chinese_text[i:i+length])

        return english_words | chinese_words

    async def search(self, query: str, top_k: int) -> List[Dict]:
        """词汇搜索 - 基于倒排索引或Milvus"""
        try:
            # 如果使用Milvus，直接调用Milvus搜索
            if self.use_milvus:
                return await self.milvus_layer.search(query, top_k)

            # 否则使用内存索引
            # 分词
            query_words = self._tokenize(query)

            # 计算每个分块的得分
            chunk_scores = {}

            for word in query_words:
                if word in self.inverted_index:
                    for doc_info in self.inverted_index[word]:
                        chunk_id = doc_info['chunk_id']
                        if chunk_id not in chunk_scores:
                            chunk_scores[chunk_id] = {
                                'score': 0,
                                'doc_id': doc_info['doc_id'],
                                'chunk_ids': [chunk_id]
                            }
                        chunk_scores[chunk_id]['score'] += 1

            # 排序并返回
            results = []
            for chunk_id, info in chunk_scores.items():
                results.append({
                    'chunk_id': chunk_id,
                    'score': info['score'] / len(query_words),  # 归一化分数
                    'doc_id': info['doc_id'],
                    'chunk_ids': info['chunk_ids']
                })

            results.sort(key=lambda x: x['score'], reverse=True)
            return results[:top_k]

        except Exception as e:
            logger.error(f"词汇搜索失败: {e}")
            # 降级到数据库关键词搜索
            return await self._fallback_keyword_search(query, top_k)

    async def _fallback_keyword_search(self, query: str, top_k: int) -> List[Dict]:
        """降级的关键词搜索"""
        try:
            db = next(get_db())

            # 简单的关键词匹配
            query_lower = query.lower()
            chunks = db.query(RAGChunk).filter(
                func.lower(RAGChunk.chunk_text).contains(query_lower)
            ).limit(top_k * 2).all()

            results = []
            for chunk in chunks:
                # 计算关键词出现次数作为分数
                text_lower = chunk.chunk_text.lower() if chunk.chunk_text else ''
                score = text_lower.count(query_lower)

                results.append({
                    'chunk_id': chunk.id,
                    'score': min(score / 10.0, 1.0),  # 归一化分数
                    'doc_id': chunk.content_id,
                    'chunk_ids': [chunk.id]
                })

            results.sort(key=lambda x: x['score'], reverse=True)
            return results[:top_k]

        except Exception as e:
            logger.error(f"降级关键词搜索失败: {e}")
            return []
        finally:
            db.close()


# 使用示例
async def example_usage():
    """使用示例"""
    search_engine = ThreeLayerSearch()

    # 1. 快速关键词搜索
    keyword_config = SearchConfig(
        mode=SearchMode.KEYWORD,
        top_k=5,
        use_cache=True
    )
    keyword_results = await search_engine.search("Transformer", keyword_config)
    logger.info(f"关键词搜索: {len(keyword_results)} 个结果")

    # 2. 标准语义搜索
    semantic_config = SearchConfig(
        mode=SearchMode.SEMANTIC,
        top_k=10,
        use_rerank=True,
        expand_context=True
    )
    semantic_results = await search_engine.search("深度学习的注意力机制", semantic_config)
    logger.info(f"语义搜索: {len(semantic_results)} 个结果")

    # 3. 深度文档搜索
    document_config = SearchConfig(
        mode=SearchMode.DOCUMENT,
        top_k=10,
        include_relations=True,
        weights={
            "term": 0.2,
            "chunk": 0.5,
            "document": 0.3
        }
    )
    doc_results = await search_engine.search("如何构建知识图谱", document_config)
    logger.info(f"文档搜索: {len(doc_results)} 个结果")


if __name__ == "__main__":
    asyncio.run(example_usage())
