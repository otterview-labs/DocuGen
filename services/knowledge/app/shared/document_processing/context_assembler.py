#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上下文组装器
负责将评分后的文档片段组装成最优上下文
"""

from typing import Dict, List, Optional, Any
import math
from datetime import datetime

from app.shared.utils.logger_util import get_logger

logger = get_logger("ContextAssembler")


class ContextAssembler:
    """上下文组装器"""

    def __init__(self):
        self.max_context_ratio = 0.9  # 最大上下文使用比例
        self.diversity_threshold = 0.3  # 多样性阈值
        self.coherence_bonus = 0.1     # 连贯性奖励

    def assemble_optimal_context(self,
                               query: str,
                               scored_chunks: List[Dict[str, Any]],
                               max_tokens: int) -> Dict[str, Any]:
        """
        组装最优上下文

        Args:
            query: 用户查询
            scored_chunks: 评分后的文档片段
            max_tokens: 最大令牌数

        Returns:
            组装后的上下文信息
        """
        try:
            # 1. 预处理和排序
            processed_chunks = self._preprocess_chunks(scored_chunks)

            # 2. 智能选择策略
            selected_chunks = self._smart_selection(processed_chunks, max_tokens)

            # 3. 优化排列顺序
            ordered_chunks = self._optimize_order(selected_chunks)

            # 4. 生成最终上下文
            context_text = self._generate_context_text(ordered_chunks)

            # 5. 生成元数据
            metadata = self._generate_metadata(query, ordered_chunks, max_tokens)

            return {
                "context": context_text,
                "chunks": ordered_chunks,
                "token_count": self._estimate_tokens(context_text),
                "metadata": metadata,
                "scores": [chunk.get("final_score", 0) for chunk in ordered_chunks],
                "assembly_strategy": "smart_selection",
                "coherence_score": self._calculate_context_coherence(ordered_chunks)
            }

        except Exception as e:
            logger.error(f"上下文组装失败: {str(e)}")
            return self._fallback_assembly(scored_chunks, max_tokens)

    def _preprocess_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """预处理分片数据"""
        try:
            processed = []

            for chunk in chunks:
                # 确保必要字段存在
                processed_chunk = {
                    **chunk,
                    "final_score": chunk.get("score", 0) or chunk.get("final_score", 0),
                    "content": chunk.get("content", ""),
                    "token_estimate": self._estimate_tokens(chunk.get("content", "")),
                    "position": chunk.get("position", 0)
                }

                # 计算最终评分（综合多个维度）
                final_score = self._calculate_final_score(processed_chunk)
                processed_chunk["final_score"] = final_score

                processed.append(processed_chunk)

            # 按最终评分排序
            return sorted(processed, key=lambda x: x["final_score"], reverse=True)

        except Exception as e:
            logger.error(f"分片预处理失败: {str(e)}")
            return chunks

    def _calculate_final_score(self, chunk: Dict[str, Any]) -> float:
        """计算最终评分"""
        try:
            base_score = chunk.get("score", 0) or 0.5

            # 质量评分加成
            analysis = chunk.get("analysis", {})
            quality_bonus = analysis.get("overall_score", 0.5) * 0.2

            # 位置加成
            position_bonus = analysis.get("position_score", 0.5) * 0.1

            # 长度惩罚（过长或过短的片段）
            token_count = chunk.get("token_estimate", 100)
            length_penalty = 0
            if token_count < 20:
                length_penalty = 0.1
            elif token_count > 800:
                length_penalty = 0.05

            final_score = base_score + quality_bonus + position_bonus - length_penalty

            return max(0.0, min(1.0, final_score))

        except Exception:
            return chunk.get("score", 0.5)

    def _smart_selection(self, chunks: List[Dict[str, Any]], max_tokens: int) -> List[Dict[str, Any]]:
        """智能选择策略"""
        try:
            selected = []
            total_tokens = 0
            max_usable_tokens = int(max_tokens * self.max_context_ratio)

            # 贪心选择高分片段
            for chunk in chunks:
                estimated_tokens = chunk.get("token_estimate", 0)

                if total_tokens + estimated_tokens <= max_usable_tokens:
                    selected.append(chunk)
                    total_tokens += estimated_tokens
                else:
                    # 检查是否可以部分包含
                    remaining_tokens = max_usable_tokens - total_tokens
                    if remaining_tokens > 50:  # 至少保留50个token的片段
                        truncated_chunk = self._truncate_chunk(chunk, remaining_tokens)
                        if truncated_chunk:
                            selected.append(truncated_chunk)
                    break

            # 确保多样性
            selected = self._ensure_diversity(selected)

            return selected

        except Exception as e:
            logger.error(f"智能选择失败: {str(e)}")
            # 简单选择前几个
            return chunks[:5]

    def _ensure_diversity(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """确保内容多样性"""
        try:
            if len(chunks) <= 3:
                return chunks

            diverse_chunks = [chunks[0]]  # 保留最高分的

            for chunk in chunks[1:]:
                # 检查与已选择片段的相似度
                if self._is_diverse_enough(chunk, diverse_chunks):
                    diverse_chunks.append(chunk)

            return diverse_chunks

        except Exception:
            return chunks

    def _is_diverse_enough(self, chunk: Dict[str, Any],
                          existing_chunks: List[Dict[str, Any]]) -> bool:
        """检查多样性"""
        try:
            chunk_keywords = set(chunk.get("features", {}).get("top_keywords", []))

            for existing in existing_chunks:
                existing_keywords = set(existing.get("features", {}).get("top_keywords", []))

                if chunk_keywords and existing_keywords:
                    overlap = len(chunk_keywords.intersection(existing_keywords))
                    similarity = overlap / max(len(chunk_keywords), len(existing_keywords))

                    if similarity > (1 - self.diversity_threshold):
                        return False

            return True

        except Exception:
            return True

    def _optimize_order(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """优化排列顺序"""
        try:
            if len(chunks) <= 2:
                return chunks

            # 策略1：按文档位置排序（保持逻辑顺序）
            position_ordered = sorted(chunks, key=lambda x: (
                x.get("doc_id", ""),
                x.get("position", 0)
            ))

            # 策略2：按重要性排序
            importance_ordered = sorted(chunks, key=lambda x: x.get("final_score", 0), reverse=True)

            # 混合策略：重要片段优先，但保持一定的位置逻辑
            optimized = []
            used_indices = set()

            # 先添加最重要的片段
            for chunk in importance_ordered[:len(chunks)//2]:
                optimized.append(chunk)
                used_indices.add(id(chunk))

            # 再按位置顺序添加剩余片段
            for chunk in position_ordered:
                if id(chunk) not in used_indices:
                    optimized.append(chunk)

            return optimized

        except Exception:
            return chunks

    def _generate_context_text(self, chunks: List[Dict[str, Any]]) -> str:
        """生成最终上下文文本"""
        try:
            context_parts = []

            for i, chunk in enumerate(chunks):
                content = chunk.get("content", "").strip()
                if not content:
                    continue

                # 添加分片标识
                doc_id = chunk.get("doc_id", f"doc_{i}")
                chunk_id = chunk.get("chunk_id", f"chunk_{i}")

                # 格式化内容
                formatted_content = f"[文档片段 {i+1}] (来源: {doc_id})\n{content}"
                context_parts.append(formatted_content)

            return "\n\n" + "="*50 + "\n\n".join(context_parts)

        except Exception as e:
            logger.error(f"上下文文本生成失败: {str(e)}")
            # 简单拼接
            return "\n\n".join([chunk.get("content", "") for chunk in chunks])

    def _generate_metadata(self, query: str, chunks: List[Dict[str, Any]],
                          max_tokens: int) -> Dict[str, Any]:
        """生成元数据"""
        try:
            return {
                "query": query,
                "total_chunks": len(chunks),
                "total_token_estimate": sum(chunk.get("token_estimate", 0) for chunk in chunks),
                "max_tokens": max_tokens,
                "utilization_ratio": sum(chunk.get("token_estimate", 0) for chunk in chunks) / max_tokens,
                "avg_chunk_score": sum(chunk.get("final_score", 0) for chunk in chunks) / len(chunks) if chunks else 0,
                "source_documents": list(set(chunk.get("doc_id", "") for chunk in chunks)),
                "assembly_timestamp": datetime.now().isoformat(),
                "assembly_strategy": "smart_selection_with_diversity"
            }

        except Exception:
            return {"query": query, "total_chunks": len(chunks)}

    def _calculate_context_coherence(self, chunks: List[Dict[str, Any]]) -> float:
        """计算上下文连贯性"""
        try:
            if len(chunks) <= 1:
                return 1.0

            coherence_scores = []

            for i in range(len(chunks) - 1):
                current_chunk = chunks[i]
                next_chunk = chunks[i + 1]

                # 检查逻辑连接
                current_keywords = set(current_chunk.get("features", {}).get("top_keywords", []))
                next_keywords = set(next_chunk.get("features", {}).get("top_keywords", []))

                keyword_overlap = len(current_keywords.intersection(next_keywords))
                max_keywords = max(len(current_keywords), len(next_keywords))

                if max_keywords > 0:
                    coherence_score = keyword_overlap / max_keywords
                else:
                    coherence_score = 0.5

                coherence_scores.append(coherence_score)

            return sum(coherence_scores) / len(coherence_scores)

        except Exception:
            return 0.5

    def _truncate_chunk(self, chunk: Dict[str, Any], max_tokens: int) -> Optional[Dict[str, Any]]:
        """截断分片以适应token限制"""
        try:
            content = chunk.get("content", "")
            if not content:
                return None

            # 简单的截断策略：保留前部分
            words = content.split()
            # 估算每个词约1.3个token
            max_words = int(max_tokens / 1.3)

            if len(words) <= max_words:
                return chunk

            truncated_content = " ".join(words[:max_words]) + "..."
            truncated_chunk = chunk.copy()
            truncated_chunk["content"] = truncated_content
            truncated_chunk["token_estimate"] = max_tokens
            truncated_chunk["truncated"] = True

            return truncated_chunk

        except Exception:
            return None

    def _estimate_tokens(self, text: str) -> int:
        """估算文本token数量"""
        try:
            # 简单估算：中文字符约1token，英文单词约1.3token
            chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
            english_words = len(text.split()) - chinese_chars

            return int(chinese_chars + english_words * 1.3)

        except Exception:
            return len(text.split())

    def _fallback_assembly(self, chunks: List[Dict[str, Any]],
                          max_tokens: int) -> Dict[str, Any]:
        """降级组装方案"""
        try:
            # 简单选择前几个最高分的片段
            sorted_chunks = sorted(chunks, key=lambda x: x.get("score", 0), reverse=True)
            selected = sorted_chunks[:5]

            context = "\n\n".join([chunk.get("content", "") for chunk in selected])

            return {
                "context": context,
                "chunks": selected,
                "token_count": self._estimate_tokens(context),
                "metadata": {"method": "fallback", "total_chunks": len(selected)},
                "scores": [chunk.get("score", 0) for chunk in selected],
                "assembly_strategy": "simple_fallback",
                "coherence_score": 0.5
            }

        except Exception:
            return {
                "context": "",
                "chunks": [],
                "token_count": 0,
                "metadata": {"method": "error"},
                "scores": [],
                "assembly_strategy": "error",
                "coherence_score": 0.0
            }
