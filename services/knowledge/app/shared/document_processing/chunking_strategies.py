#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分片策略库
提供多种智能分片策略，支持语义分片、固定分片、段落分片等
"""

from typing import Dict, List, Optional, Any
import re
from datetime import datetime

from app.shared.utils.logger_util import get_logger

logger = get_logger("ChunkingStrategies")


class ChunkingStrategies:
    """分片策略库"""

    def __init__(self):
        self.default_config = {
            "max_chunk_size": 500,
            "min_chunk_size": 100,
            "overlap_size": 75,
            "strategy": "semantic"
        }

    async def semantic_chunking(self, content: str,
                              config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        语义分片策略
        基于语义边界进行智能分片
        """
        config = {**self.default_config, **(config or {})}

        try:
            # 1. 段落边界检测
            paragraphs = self._detect_paragraph_boundaries(content)

            # 2. 句子边界检测
            sentences = self._detect_sentence_boundaries(content)

            # 3. 语义边界合并
            boundaries = self._merge_boundaries(paragraphs, sentences)

            # 4. 创建分片
            chunks = await self._create_semantic_chunks(content, boundaries, config)

            return chunks

        except Exception as e:
            logger.error(f"语义分片失败: {str(e)}")
            return await self.fixed_size_chunking(content, config)

    async def fixed_size_chunking(self, content: str,
                                config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        固定大小分片策略
        按固定字符数进行分片
        """
        config = {**self.default_config, **(config or {})}

        try:
            chunk_size = config["max_chunk_size"]
            overlap = config["overlap_size"]

            chunks = []
            start = 0
            chunk_id = 0

            while start < len(content):
                end = min(start + chunk_size, len(content))

                # 尽量在句子边界处结束
                if end < len(content):
                    sentence_end = self._find_nearest_sentence_end(content, end)
                    if sentence_end and sentence_end - start >= config["min_chunk_size"]:
                        end = sentence_end

                chunk_content = content[start:end].strip()

                if chunk_content:
                    chunks.append({
                        "content": chunk_content,
                        "start": start,
                        "end": end,
                        "position": chunk_id,
                        "chunk_id": chunk_id,
                        "size": len(chunk_content),
                        "strategy": "fixed_size"
                    })

                start = end - overlap
                chunk_id += 1

                if end == len(content):
                    break

            return chunks

        except Exception as e:
            logger.error(f"固定大小分片失败: {str(e)}")
            return await self.paragraph_chunking(content, config)

    async def paragraph_chunking(self, content: str,
                               config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        段落分片策略
        以段落为边界进行分片
        """
        config = {**self.default_config, **(config or {})}

        try:
            # 按段落分割
            paragraphs = self._split_by_paragraphs(content)

            chunks = []
            current_chunk = ""
            current_start = 0
            chunk_id = 0

            for para_start, para_end, paragraph in paragraphs:
                # 如果段落太长，按句子分割
                if len(paragraph) > config["max_chunk_size"]:
                    sub_chunks = self._split_long_paragraph(paragraph, para_start, config)
                    chunks.extend(sub_chunks)
                else:
                    # 合并小段落到合理大小
                    if len(current_chunk) + len(paragraph) <= config["max_chunk_size"]:
                        if current_chunk:
                            current_chunk += "\n\n" + paragraph
                        else:
                            current_chunk = paragraph
                    else:
                        if current_chunk:
                            chunks.append({
                                "content": current_chunk,
                                "start": current_start,
                                "end": para_start - 1,
                                "position": chunk_id,
                                "chunk_id": chunk_id,
                                "size": len(current_chunk),
                                "strategy": "paragraph"
                            })
                            chunk_id += 1

                        current_chunk = paragraph
                        current_start = para_start

            # 添加最后一个分片
            if current_chunk:
                chunks.append({
                    "content": current_chunk,
                    "start": current_start,
                    "end": len(content),
                    "position": chunk_id,
                    "chunk_id": chunk_id,
                    "size": len(current_chunk),
                    "strategy": "paragraph"
                })

            return chunks

        except Exception as e:
            logger.error(f"段落分片失败: {str(e)}")
            return await self.sentence_chunking(content, config)

    async def sentence_chunking(self, content: str,
                              config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        句子分片策略
        以句子为边界进行分片
        """
        config = {**self.default_config, **(config or {})}

        try:
            sentences = self._split_by_sentences(content)

            chunks = []
            current_chunk = ""
            current_start = 0
            chunk_id = 0

            for sent_start, sent_end, sentence in sentences:
                if len(current_chunk) + len(sentence) <= config["max_chunk_size"]:
                    if current_chunk:
                        current_chunk += " " + sentence
                    else:
                        current_chunk = sentence
                else:
                    if current_chunk:
                        chunks.append({
                            "content": current_chunk,
                            "start": current_start,
                            "end": sent_start - 1,
                            "position": chunk_id,
                            "chunk_id": chunk_id,
                            "size": len(current_chunk),
                            "strategy": "sentence"
                        })
                        chunk_id += 1

                    current_chunk = sentence
                    current_start = sent_start

            # 添加最后一个分片
            if current_chunk:
                chunks.append({
                    "content": current_chunk,
                    "start": current_start,
                    "end": len(content),
                    "position": chunk_id,
                    "chunk_id": chunk_id,
                    "size": len(current_chunk),
                    "strategy": "sentence"
                })

            return chunks

        except Exception as e:
            logger.error(f"句子分片失败: {str(e)}")
            return await self.hybrid_chunking(content, config)

    async def hybrid_chunking(self, content: str,
                            config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        混合分片策略
        结合多种策略的优点
        """
        config = {**self.default_config, **(config or {})}

        try:
            # 先按段落分片
            paragraphs = self._split_by_paragraphs(content)

            chunks = []
            chunk_id = 0

            for para_start, para_end, paragraph in paragraphs:
                para_length = len(paragraph)

                if para_length <= config["max_chunk_size"]:
                    # 短段落直接作为一个分片
                    chunks.append({
                        "content": paragraph,
                        "start": para_start,
                        "end": para_end,
                        "position": chunk_id,
                        "chunk_id": chunk_id,
                        "size": para_length,
                        "strategy": "hybrid_paragraph"
                    })
                    chunk_id += 1
                else:
                    # 长段落按句子分片
                    sub_chunks = self._split_long_paragraph(paragraph, para_start, config)
                    for sub_chunk in sub_chunks:
                        sub_chunk["strategy"] = "hybrid_sentence"
                        sub_chunk["chunk_id"] = chunk_id
                        chunks.append(sub_chunk)
                        chunk_id += 1

            return chunks

        except Exception as e:
            logger.error(f"混合分片失败: {str(e)}")
            # 最终降级到固定大小
            return await self.fixed_size_chunking(content, config)

    def _detect_paragraph_boundaries(self, content: str) -> List[tuple]:
        """检测段落边界"""
        # 按空行分割段落
        paragraphs = re.split(r'\n\s*\n', content)

        boundaries = []
        start = 0

        for para in paragraphs:
            if para.strip():
                para_start = content.find(para, start)
                para_end = para_start + len(para)
                boundaries.append((para_start, para_end, para.strip()))
                start = para_end

        return boundaries

    def _detect_sentence_boundaries(self, content: str) -> List[tuple]:
        """检测句子边界"""
        # 按句子分割
        sentence_pattern = r'[^.!?]*[.!?]+'
        sentences = re.finditer(sentence_pattern, content)

        boundaries = []
        for match in sentences:
            sentence = match.group().strip()
            if sentence:
                boundaries.append((match.start(), match.end(), sentence))

        return boundaries

    def _merge_boundaries(self, paragraphs: List[tuple], sentences: List[tuple]) -> List[int]:
        """合并边界"""
        # 优先使用段落边界，段落内使用句子边界
        boundaries = set()

        # 添加段落边界
        for start, end, _ in paragraphs:
            boundaries.add(start)
            boundaries.add(end)

        # 添加句子边界（在段落内）
        for start, end, _ in sentences:
            boundaries.add(start)
            boundaries.add(end)

        return sorted(list(boundaries))

    async def _create_semantic_chunks(self, content: str, boundaries: List[int],
                                     config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """创建语义分片"""
        if not boundaries:
            return await self.fixed_size_chunking(content, config)

        chunks = []
        chunk_id = 0

        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            chunk_content = content[start:end].strip()

            if chunk_content and len(chunk_content) >= config["min_chunk_size"]:
                chunks.append({
                    "content": chunk_content,
                    "start": start,
                    "end": end,
                    "position": chunk_id,
                    "chunk_id": chunk_id,
                    "size": len(chunk_content),
                    "strategy": "semantic"
                })
                chunk_id += 1

        return chunks

    def _split_by_paragraphs(self, content: str) -> List[tuple]:
        """按段落分割"""
        paragraphs = re.split(r'\n\s*\n', content)

        result = []
        start = 0

        for para in paragraphs:
            if para.strip():
                para_start = content.find(para, start)
                para_end = para_start + len(para)
                result.append((para_start, para_end, para.strip()))
                start = para_end

        return result

    def _split_by_sentences(self, content: str) -> List[tuple]:
        """按句子分割"""
        # 更精确的句子分割
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])|(?<=[。！？])\s+(?=[\u4e00-\u9fff])'
        sentences = re.split(sentence_pattern, content)

        result = []
        start = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                sent_start = content.find(sentence, start)
                sent_end = sent_start + len(sentence)
                result.append((sent_start, sent_end, sentence))
                start = sent_end

        return result

    def _split_long_paragraph(self, paragraph: str, para_start: int,
                            config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """分割长段落"""
        sentences = self._split_by_sentences(paragraph)

        chunks = []
        current_chunk = ""
        current_start = para_start
        chunk_id = 0

        for sent_start, sent_end, sentence in sentences:
            # 调整起始位置
            adjusted_start = para_start + sent_start
            adjusted_end = para_start + sent_end

            if len(current_chunk) + len(sentence) <= config["max_chunk_size"]:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
            else:
                if current_chunk:
                    chunks.append({
                        "content": current_chunk,
                        "start": current_start,
                        "end": adjusted_start - 1,
                        "position": chunk_id,
                        "chunk_id": chunk_id,
                        "size": len(current_chunk),
                        "strategy": "long_paragraph_split"
                    })
                    chunk_id += 1

                current_chunk = sentence
                current_start = adjusted_start

        # 添加最后一个分片
        if current_chunk:
            chunks.append({
                "content": current_chunk,
                "start": current_start,
                "end": para_start + len(paragraph),
                "position": chunk_id,
                "chunk_id": chunk_id,
                "size": len(current_chunk),
                "strategy": "long_paragraph_split"
            })

        return chunks

    def _find_nearest_sentence_end(self, content: str, position: int) -> Optional[int]:
        """找到最近的句子结束位置"""
        # 向前查找句子结束符
        sentence_ends = [m.end() for m in re.finditer(r'[.!?。！？]', content[:position+50])]
        if sentence_ends:
            return max(sentence_ends)
        return position
