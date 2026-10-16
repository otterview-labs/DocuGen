#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
相关性评分器
提供多种评分策略，支持语义相似度、关键词匹配、位置权重等
"""

from typing import Dict, List, Optional, Any
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.llm.unified_service import get_embedding_service
from app.shared.utils.logger_util import get_logger

logger = get_logger("RelevanceScorer")


class RelevanceScorer:
    """相关性评分器"""

    def __init__(self):
        self.embedding_service = get_embedding_service()
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )

    async def fast_score(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        快速评分（基于关键词匹配）

        Args:
            query: 查询文本
            chunks: 文档片段列表

        Returns:
            评分后的片段列表
        """
        try:
            query_words = set(query.lower().split())
            scored_chunks = []

            for chunk in chunks:
                content = chunk["content"].lower()
                content_words = set(content.split())

                # 关键词匹配得分
                intersection = len(query_words.intersection(content_words))
                union = len(query_words.union(content_words))
                keyword_score = intersection / union if union > 0 else 0

                # 位置权重
                position_score = self._calculate_position_score(chunk)

                # 长度权重
                length_score = self._calculate_length_score(len(content))

                # 综合得分
                final_score = (
                    keyword_score * 0.6 +
                    position_score * 0.2 +
                    length_score * 0.2
                )

                scored_chunk = chunk.copy()
                scored_chunk.update({
                    "score": final_score,
                    "keyword_score": keyword_score,
                    "position_score": position_score,
                    "length_score": length_score,
                    "scoring_method": "fast"
                })

                scored_chunks.append(scored_chunk)

            return scored_chunks

        except Exception as e:
            logger.error(f"快速评分失败: {str(e)}")
            return [{**chunk, "score": 0.5, "scoring_method": "fast_fallback"}
                   for chunk in chunks]

    async def multi_dimensional_score(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        多维度评分（综合多种指标）

        Args:
            query: 查询文本
            chunks: 文档片段列表

        Returns:
            评分后的片段列表
        """
        try:
            # 获取查询嵌入
            query_embedding = await self.embedding_service.embed_query(query)

            # 获取内容嵌入
            contents = [chunk["content"] for chunk in chunks]
            content_embeddings = await self.embedding_service.embed_documents(contents)

            # 计算语义相似度
            semantic_scores = []
            for emb in content_embeddings:
                similarity = cosine_similarity([query_embedding], [emb])[0][0]
                semantic_scores.append(float(similarity))

            # 计算TF-IDF得分
            tfidf_scores = await self._calculate_tfidf_scores(query, contents)

            scored_chunks = []
            for i, chunk in enumerate(chunks):
                # 多维度得分
                semantic_score = semantic_scores[i]
                tfidf_score = tfidf_scores[i]
                keyword_score = await self._calculate_keyword_score(query, chunk["content"])
                position_score = self._calculate_position_score(chunk)
                length_score = self._calculate_length_score(len(chunk["content"]))

                # 权重组合
                final_score = (
                    semantic_score * 0.4 +
                    tfidf_score * 0.2 +
                    keyword_score * 0.2 +
                    position_score * 0.1 +
                    length_score * 0.1
                )

                scored_chunk = chunk.copy()
                scored_chunk.update({
                    "score": final_score,
                    "semantic_score": semantic_score,
                    "tfidf_score": tfidf_score,
                    "keyword_score": keyword_score,
                    "position_score": position_score,
                    "length_score": length_score,
                    "scoring_method": "multi_dimensional"
                })

                scored_chunks.append(scored_chunk)

            return scored_chunks

        except Exception as e:
            logger.error(f"多维度评分失败: {str(e)}")
            return await self.fast_score(query, chunks)

    async def smart_score(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        智能评分（自适应策略）

        Args:
            query: 查询文本
            chunks: 文档片段列表

        Returns:
            评分后的片段列表
        """
        try:
            # 分析查询类型
            query_type = self._analyze_query_type(query)

            # 根据查询类型选择评分策略
            if query_type == "simple":
                return await self.fast_score(query, chunks)
            elif query_type == "complex":
                return await self.multi_dimensional_score(query, chunks)
            else:
                # 混合策略
                fast_scores = await self.fast_score(query, chunks)
                deep_scores = await self.multi_dimensional_score(query, chunks)

                # 取平均值
                combined_scores = []
                for fast, deep in zip(fast_scores, deep_scores):
                    combined = fast.copy()
                    combined["score"] = (fast["score"] + deep["score"]) / 2
                    combined["scoring_method"] = "hybrid"
                    combined_scores.append(combined)

                return combined_scores

        except Exception as e:
            logger.error(f"智能评分失败: {str(e)}")
            return [{**chunk, "score": 0.5, "scoring_method": "smart_fallback"}
                   for chunk in chunks]

    async def _calculate_tfidf_scores(self, query: str, contents: List[str]) -> List[float]:
        """计算TF-IDF得分"""
        try:
            # 准备数据
            all_texts = [query] + contents

            # 计算TF-IDF
            tfidf_matrix = self.tfidf_vectorizer.fit_transform(all_texts)

            # 获取查询向量
            query_vector = tfidf_matrix[0:1]
            content_vectors = tfidf_matrix[1:]

            # 计算相似度
            similarities = cosine_similarity(query_vector, content_vectors)[0]

            return similarities.tolist()

        except Exception as e:
            logger.error(f"TF-IDF计算失败: {str(e)}")
            return [0.0] * len(contents)

    async def _calculate_keyword_score(self, query: str, content: str) -> float:
        """计算关键词得分"""
        try:
            query_words = set(query.lower().split())
            content_words = set(content.lower().split())

            # 精确匹配
            exact_matches = len(query_words.intersection(content_words))

            # 模糊匹配（子串匹配）
            fuzzy_matches = 0
            for q_word in query_words:
                for c_word in content_words:
                    if q_word in c_word or c_word in q_word:
                        fuzzy_matches += 1

            # 权重组合
            total_words = len(query_words)
            if total_words == 0:
                return 0.0

            score = (exact_matches * 1.0 + fuzzy_matches * 0.3) / total_words
            return min(score, 1.0)

        except Exception as e:
            logger.error(f"关键词评分计算失败: {str(e)}")
            return 0.0

    def _calculate_position_score(self, chunk: Dict[str, Any]) -> float:
        """计算位置权重得分"""
        try:
            position = chunk.get("position", 0)
            total_chunks = chunk.get("total_chunks", 100)

            # 文档开头的片段权重更高
            position_ratio = position / max(total_chunks, 1)

            # 使用指数衰减
            score = np.exp(-position_ratio * 2)

            return max(score, 0.1)  # 最小权重为0.1

        except Exception as e:
            logger.error(f"位置权重计算失败: {str(e)}")
            return 0.5

    def _calculate_length_score(self, length: int) -> float:
        """计算长度权重得分"""
        try:
            # 理想长度范围：200-800字符
            ideal_min = 200
            ideal_max = 800

            if ideal_min <= length <= ideal_max:
                return 1.0
            elif length < ideal_min:
                return length / ideal_min
            else:
                return max(1.0 - (length - ideal_max) / 1000, 0.1)

        except Exception as e:
            logger.error(f"长度权重计算失败: {str(e)}")
            return 0.5

    def _analyze_query_type(self, query: str) -> str:
        """分析查询类型"""
        query_lower = query.lower().strip()

        # 简单查询特征
        if len(query_lower.split()) <= 3:
            return "simple"

        # 复杂查询特征
        complex_indicators = [
            "为什么", "如何", "怎样", "解释", "分析", "比较",
            "why", "how", "explain", "analyze", "compare"
        ]

        for indicator in complex_indicators:
            if indicator in query_lower:
                return "complex"

        # 默认返回混合类型
        return "mixed"

    async def get_relevance_distribution(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取相关性分布统计"""
        try:
            scores = [chunk.get("score", 0) for chunk in chunks]

            if not scores:
                return {"error": "no_scores"}

            return {
                "count": len(scores),
                "mean": np.mean(scores),
                "median": np.median(scores),
                "std": np.std(scores),
                "min": np.min(scores),
                "max": np.max(scores),
                "percentiles": {
                    "25": np.percentile(scores, 25),
                    "75": np.percentile(scores, 75),
                    "90": np.percentile(scores, 90)
                }
            }

        except Exception as e:
            logger.error(f"相关性分布统计失败: {str(e)}")
            return {"error": str(e)}
