#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
支持多种分段策略和智能内容分析
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import jieba
import jieba.posseg as pseg
from collections import Counter

logger = logging.getLogger(__name__)


class SmartChunker:
    """智能分段器 """

    def __init__(self):
        # 分段策略配置
        self.chunk_strategies = {
            "semantic": self._semantic_chunking,
            "fixed_size": self._fixed_size_chunking,
            "paragraph": self._paragraph_chunking,
            "sentence": self._sentence_chunking,
            "hybrid": self._hybrid_chunking,
            "markdown": self._markdown_chunking
        }

        # 默认配置 - 优化后的分块参数，提高检索准确性
        # ✅ 2025-10-20: 减小overlap避免相邻chunks内容重叠导致搜索混淆
        self.default_config = {
            "max_chunk_size": 800,    # 增大分块大小，包含更完整的章节内容
            "min_chunk_size": 150,    # 提高最小值，保证信息完整性
            "overlap_size": 40,       # 减小重叠（从75→40），避免相邻chunks内容重叠
            "strategy": "semantic",   # 使用语义分块，保证边界质量
            # markdown 专用参数：按哪一级标题切分（1-6），默认按二级标题划分章节
            "split_level": 2,
            # markdown 长章节的二次切分备用策略：sentence/fixed_size
            "fallback_strategy": "sentence",
            "preserve_structure": True,
            "include_metadata": True
        }

    def chunk_content(self, content: str, config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        智能分段内容

        Args:
            content: 要分段的内容
            config: 分段配置

        Returns:
            分段结果列表
        """
        try:
            if not content:
                return []

            # 合并配置
            chunk_config = {**self.default_config, **(config or {})}
            strategy = chunk_config["strategy"]

            if strategy not in self.chunk_strategies:
                logger.warning(f"未知的分段策略: {strategy}，使用默认策略")
                strategy = "hybrid"

            # 执行分段
            chunk_func = self.chunk_strategies[strategy]
            chunks = chunk_func(content, chunk_config)

            # 后处理
            chunks = self._post_process_chunks(chunks, chunk_config)

            return chunks

        except Exception as e:
            logger.error(f"分段失败: {e}")
            return []

    def _semantic_chunking(self, content: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """语义分段 - 基于语义相似度"""
        chunks = []

        # 按段落分割
        paragraphs = content.split('\n\n')

        current_chunk = ""
        current_chunk_info = {
            "start_index": 0,
            "paragraphs": [],
            "semantic_score": 0.0
        }

        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                continue

            # 计算段落语义分数
            semantic_score = self._calculate_semantic_score(para)

            # 判断是否需要开始新块
            if (len(current_chunk) + len(para) > config["max_chunk_size"] or
                abs(semantic_score - current_chunk_info["semantic_score"]) > 0.3):

                if current_chunk:
                    chunks.append({
                        "content": current_chunk.strip(),
                        "type": "semantic",
                        "metadata": current_chunk_info.copy()
                    })

                current_chunk = para
                current_chunk_info = {
                    "start_index": i,
                    "paragraphs": [i],
                    "semantic_score": semantic_score
                }
            else:
                current_chunk += "\n\n" + para
                current_chunk_info["paragraphs"].append(i)
                current_chunk_info["semantic_score"] = (current_chunk_info["semantic_score"] + semantic_score) / 2

        # 添加最后一个块
        if current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "type": "semantic",
                "metadata": current_chunk_info
            })

        return chunks

    def _fixed_size_chunking(self, content: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """固定大小分段"""
        chunks = []
        max_size = config["max_chunk_size"]
        overlap = config["overlap_size"]

        start = 0
        while start < len(content):
            end = start + max_size

            # 尝试在句子边界分割
            if end < len(content):
                # 寻找最近的句子结束位置
                sentence_end = content.rfind('.', start, end)
                if sentence_end > start + max_size * 0.7:  # 如果句子结束位置在合理范围内
                    end = sentence_end + 1

            chunk_content = content[start:end]

            chunks.append({
                "content": chunk_content.strip(),
                "type": "fixed_size",
                "metadata": {
                    "start_pos": start,
                    "end_pos": end,
                    "size": len(chunk_content)
                }
            })

            # 计算下一个起始位置（考虑重叠）
            start = max(start + 1, end - overlap)

        return chunks

    def _paragraph_chunking(self, content: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """段落分段"""
        chunks = []
        paragraphs = content.split('\n\n')

        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                continue

            # 如果段落太长，进一步分割
            if len(para) > config["max_chunk_size"]:
                sub_chunks = self._split_long_paragraph(para, config)
                for j, sub_chunk in enumerate(sub_chunks):
                    chunks.append({
                        "content": sub_chunk,
                        "type": "paragraph",
                        "metadata": {
                            "paragraph_index": i,
                            "sub_index": j,
                            "is_split": True
                        }
                    })
            else:
                chunks.append({
                    "content": para,
                    "type": "paragraph",
                    "metadata": {
                        "paragraph_index": i,
                        "is_split": False
                    }
                })

        return chunks

    def _sentence_chunking(self, content: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """句子分段"""
        chunks = []

        # 分割句子
        sentences = re.split(r'[。！？.!?]', content)

        current_chunk = ""
        sentence_count = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # 如果当前块加上新句子会超过限制，开始新块
            if len(current_chunk) + len(sentence) > config["max_chunk_size"] and current_chunk:
                chunks.append({
                    "content": current_chunk.strip(),
                    "type": "sentence",
                    "metadata": {
                        "sentence_count": sentence_count,
                        "avg_sentence_length": len(current_chunk) / sentence_count if sentence_count > 0 else 0
                    }
                })
                current_chunk = sentence
                sentence_count = 1
            else:
                current_chunk += sentence + "。"
                sentence_count += 1

        # 添加最后一个块
        if current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "type": "sentence",
                "metadata": {
                    "sentence_count": sentence_count,
                    "avg_sentence_length": len(current_chunk) / sentence_count if sentence_count > 0 else 0
                }
            })

        return chunks

    def _hybrid_chunking(self, content: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """混合分段策略"""
        chunks = []

        # 首先按段落分割
        paragraphs = content.split('\n\n')

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果段落很短，直接作为一个块
            if len(para) <= config["min_chunk_size"]:
                chunks.append({
                    "content": para,
                    "type": "paragraph",
                    "metadata": {"size": "small"}
                })
            # 如果段落适中，按句子分割
            elif len(para) <= config["max_chunk_size"]:
                sentence_chunks = self._sentence_chunking(para, config)
                chunks.extend(sentence_chunks)
            # 如果段落很长，按固定大小分割
            else:
                fixed_chunks = self._fixed_size_chunking(para, config)
                chunks.extend(fixed_chunks)

        return chunks

    def _split_long_paragraph(self, paragraph: str, config: Dict[str, Any]) -> List[str]:
        """分割长段落"""
        chunks = []
        max_size = config["max_chunk_size"]

        # 按句子分割
        sentences = re.split(r'[。！？.!?]', paragraph)

        current_chunk = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if len(current_chunk) + len(sentence) > max_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += sentence + "。"

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _markdown_chunking(self, content: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """基于Markdown标题的章节分段（增强版）。

        新增功能：
        1. 构建完整的标题层级路径（heading_path）
        2. 保留父子章节关系
        3. 二次切分时保留段落完整性
        4. 章节间添加上下文关联信息

        规则：按 split_level（默认2级##）作为章节边界，章节内容包含该标题至下一同级或更高层标题之前的所有文本。
        若章节过长（> max_chunk_size），按 fallback_strategy（paragraph/sentence/fixed_size）在章节内部二次切分。
        """
        import re
        chunks: List[Dict[str, Any]] = []
        if not content:
            return chunks

        split_level = max(1, min(int(config.get("split_level", 2) or 2), 6))
        max_size = int(config.get("max_chunk_size", 500) or 500)
        fallback = (config.get("fallback_strategy") or "paragraph").strip()  # 默认改为paragraph
        if fallback not in ("paragraph", "sentence", "fixed_size"):
            fallback = "paragraph"

        # 查找所有标题
        pattern = re.compile(r"^(?P<hash>#{1,6})\s+(?P<title>.+?)\s*$", re.MULTILINE)
        matches = list(pattern.finditer(content))

        # 如果没有标题，退回到段落/句子混合
        if not matches:
            return self._hybrid_chunking(content, config)

        # 构建所有标题的完整信息（包括层级路径）
        headings = []
        for m in matches:
            level = len(m.group("hash"))
            headings.append({
                "level": level,
                "title": m.group("title").strip(),
                "pos": m.start()
            })

        # ✅ 构建标题层级路径（heading_path）
        heading_paths = self._build_heading_hierarchy(headings)

        # 收集按 split_level 的大章节范围（使用增强的层级信息）
        major_sections = []
        n = len(content)

        # 使用 heading_paths 而不是 headings
        for i, h_info in enumerate(heading_paths):
            if h_info["level"] > split_level:
                continue

            start = h_info["pos"]
            # 下一个同级或更高层标题作为结束
            end = n
            for j in range(i + 1, len(heading_paths)):
                if heading_paths[j]["level"] <= split_level:
                    end = heading_paths[j]["pos"]
                    break

            major_sections.append({
                "title": h_info["title"],
                "level": h_info["level"],
                "start": start,
                "end": end,
                # ✅ 添加层级信息
                "heading_path": h_info["path"],
                "parent_title": h_info["parent_title"],
                "parent_level": h_info["parent_level"],
                "prev_sibling": h_info["prev_sibling"],
                "next_sibling": h_info["next_sibling"],
                "section_index": len([s for s in major_sections if s["level"] == h_info["level"]]),
            })

        # 如果没有任何 <= split_level 的标题，则退回到按所有标题切（最细到1-6）
        if not major_sections:
            for i, h_info in enumerate(heading_paths):
                start = h_info["pos"]
                end = heading_paths[i + 1]["pos"] if i + 1 < len(heading_paths) else n
                major_sections.append({
                    "title": h_info["title"],
                    "level": h_info["level"],
                    "start": start,
                    "end": end,
                    "heading_path": h_info["path"],
                    "parent_title": h_info["parent_title"],
                    "parent_level": h_info["parent_level"],
                    "prev_sibling": h_info["prev_sibling"],
                    "next_sibling": h_info["next_sibling"],
                    "section_index": i,
                })

        # 生成章节块，过长则二次切分
        overlap_size = int(config.get("overlap_size", 75) or 75)

        for sec_idx, sec in enumerate(major_sections):
            section_text = content[sec["start"]:sec["end"]].strip()
            if not section_text:
                continue

            if len(section_text) <= max_size:
                # ✅ 添加overlap：包含前后章节的部分内容
                chunk_content = section_text

                # 向上overlap：添加前一个章节的结尾
                if sec_idx > 0 and overlap_size > 0:
                    prev_sec = major_sections[sec_idx - 1]
                    prev_text = content[prev_sec["start"]:prev_sec["end"]].strip()
                    if prev_text:
                        # 取前一个章节的最后overlap_size个字符
                        overlap_prefix = prev_text[-overlap_size:] if len(prev_text) > overlap_size else prev_text
                        chunk_content = overlap_prefix + "\n\n" + chunk_content

                # 向下overlap：添加后一个章节的开头
                if sec_idx < len(major_sections) - 1 and overlap_size > 0:
                    next_sec = major_sections[sec_idx + 1]
                    next_text = content[next_sec["start"]:next_sec["end"]].strip()
                    if next_text:
                        # 取后一个章节的前overlap_size个字符
                        overlap_suffix = next_text[:overlap_size] if len(next_text) > overlap_size else next_text
                        chunk_content = chunk_content + "\n\n" + overlap_suffix

                # ✅ 增强元数据：包含完整的层级信息和上下文
                chunks.append({
                    "content": chunk_content,
                    "type": "markdown",
                    "metadata": {
                        # 当前标题信息
                        "heading": sec["title"],
                        "heading_level": sec["level"],
                        "heading_path": sec["heading_path"],  # ✅ 完整路径 ["第1章", "1.1 概述"]

                        # 父级信息
                        "parent_heading": sec["parent_title"],
                        "parent_level": sec["parent_level"],

                        # 兄弟章节信息
                        "prev_sibling": sec["prev_sibling"],
                        "next_sibling": sec["next_sibling"],

                        # 章节索引
                        "section_index": sec["section_index"],
                        "total_sections": len(major_sections),

                        # 位置信息
                        "start_pos": sec["start"],
                        "end_pos": sec["end"],
                        "split_level": split_level,

                        # overlap信息
                        "has_prev_overlap": sec_idx > 0 and overlap_size > 0,
                        "has_next_overlap": sec_idx < len(major_sections) - 1 and overlap_size > 0,
                        "overlap_size": overlap_size,

                        # 是否完整章节
                        "is_complete_section": True,
                        "is_subsection": False
                    }
                })
            else:
                # ✅ 二次切分：优先使用 paragraph_aware，保留段落完整性
                if fallback == "paragraph":
                    sub_chunks = self._paragraph_aware_chunking(section_text, config)
                elif fallback == "sentence":
                    sub_chunks = self._sentence_chunking(section_text, config)
                else:
                    sub_chunks = self._fixed_size_chunking(section_text, config)

                # 附加完整的父章节元数据
                for sub_idx, sc in enumerate(sub_chunks):
                    sc.setdefault("metadata", {})
                    sc["metadata"].update({
                        # 父章节完整信息
                        "parent_heading": sec["title"],
                        "parent_level": sec["level"],
                        "parent_heading_path": sec["heading_path"],  # ✅ 父章节完整路径

                        # 祖先信息（如果有）
                        "ancestor_heading": sec["parent_title"],
                        "ancestor_level": sec["parent_level"],

                        # 兄弟章节信息
                        "parent_prev_sibling": sec["prev_sibling"],
                        "parent_next_sibling": sec["next_sibling"],

                        # 子块信息
                        "subsection_index": sub_idx,
                        "total_subsections": len(sub_chunks),
                        "section_index": sec["section_index"],

                        # 标记
                        "split_level": split_level,
                        "is_complete_section": False,
                        "is_subsection": True,
                        "subsection_strategy": fallback
                    })
                    sc["type"] = "markdown"
                chunks.extend(sub_chunks)

        return chunks

    def _build_heading_hierarchy(self, headings: List[Dict]) -> List[Dict]:
        """构建标题层级结构

        为每个标题构建完整的层级路径，例如：
        # 第1章
        ## 1.1 概述
        ### 1.1.1 背景

        返回：
        [
            {
                "level": 1,
                "title": "第1章",
                "path": ["第1章"],
                "parent_title": None,
                "parent_level": None
            },
            {
                "level": 2,
                "title": "1.1 概述",
                "path": ["第1章", "1.1 概述"],
                "parent_title": "第1章",
                "parent_level": 1
            },
            ...
        ]
        """
        if not headings:
            return []

        hierarchy = []
        # 用栈记录当前路径上每一级的标题
        level_stack = [None] * 7  # 支持1-6级标题，索引0不用

        for i, h in enumerate(headings):
            level = h["level"]
            title = h["title"]
            pos = h["pos"]

            # 清理比当前级别更深的栈
            for deeper_level in range(level + 1, 7):
                level_stack[deeper_level] = None

            # 设置当前级别
            level_stack[level] = title

            # 构建路径（从1级到当前级）
            path = [level_stack[l] for l in range(1, level + 1) if level_stack[l] is not None]

            # 查找父标题（上一级标题）
            parent_title = None
            parent_level = None
            for parent_lv in range(level - 1, 0, -1):
                if level_stack[parent_lv] is not None:
                    parent_title = level_stack[parent_lv]
                    parent_level = parent_lv
                    break

            # 查找兄弟章节（前一个同级标题和后一个同级标题）
            prev_sibling = None
            next_sibling = None

            # 前一个同级标题
            for j in range(i - 1, -1, -1):
                if headings[j]["level"] == level:
                    prev_sibling = headings[j]["title"]
                    break
                elif headings[j]["level"] < level:
                    break

            # 后一个同级标题
            for j in range(i + 1, len(headings)):
                if headings[j]["level"] == level:
                    next_sibling = headings[j]["title"]
                    break
                elif headings[j]["level"] < level:
                    break

            hierarchy.append({
                "level": level,
                "title": title,
                "pos": pos,
                "path": path,
                "parent_title": parent_title,
                "parent_level": parent_level,
                "prev_sibling": prev_sibling,
                "next_sibling": next_sibling,
                "index": i  # 全局索引
            })

        return hierarchy

    def _paragraph_aware_chunking(self, content: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """保留段落完整性的分块（用于长章节的二次切分）

        相比 _sentence_chunking，这个方法：
        1. 按段落边界切分（而不是句子）
        2. 保留段落的完整性
        3. 记录段落索引信息
        """
        chunks = []
        max_size = config.get("max_chunk_size", 500)
        overlap_size = config.get("overlap_size", 75)

        # 按双换行符分割段落
        paragraphs = content.split('\n\n')

        current_chunk = ""
        para_indices = []

        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                continue

            # 如果加上这个段落会超出限制
            if current_chunk and len(current_chunk) + len(para) + 2 > max_size:
                # 保存当前块
                chunks.append({
                    "content": current_chunk.strip(),
                    "type": "paragraph_aware",
                    "metadata": {
                        "paragraph_indices": para_indices.copy(),
                        "paragraph_count": len(para_indices),
                        "is_paragraph_complete": True,
                        "start_para": para_indices[0] if para_indices else 0,
                        "end_para": para_indices[-1] if para_indices else 0
                    }
                })

                # 添加overlap（取上一个块的最后一个段落）
                if overlap_size > 0 and para_indices:
                    # 获取上一个块的最后一个段落作为overlap
                    last_para_idx = para_indices[-1]
                    last_para = paragraphs[last_para_idx] if last_para_idx < len(paragraphs) else ""
                    current_chunk = last_para.strip() + "\n\n" + para
                    para_indices = [last_para_idx, i]
                else:
                    current_chunk = para
                    para_indices = [i]
            else:
                # 追加到当前块
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
                para_indices.append(i)

        # 添加最后一个块
        if current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "type": "paragraph_aware",
                "metadata": {
                    "paragraph_indices": para_indices.copy(),
                    "paragraph_count": len(para_indices),
                    "is_paragraph_complete": True,
                    "start_para": para_indices[0] if para_indices else 0,
                    "end_para": para_indices[-1] if para_indices else 0
                }
            })

        return chunks

    def _calculate_semantic_score(self, text: str) -> float:
        """计算文本的语义分数"""
        try:
            # 使用jieba分词
            words = jieba.lcut(text)

            # 计算词汇多样性
            word_count = len(words)
            unique_words = len(set(words))
            diversity = unique_words / word_count if word_count > 0 else 0

            # 计算平均词长度
            avg_word_length = sum(len(word) for word in words) / word_count if word_count > 0 else 0

            # 计算标点符号密度
            punctuation_count = len(re.findall(r'[，。！？、；：""''（）【】]', text))
            punctuation_density = punctuation_count / len(text) if text else 0

            # 综合分数
            score = (diversity * 0.4 +
                    min(avg_word_length / 10, 1.0) * 0.3 +
                    min(punctuation_density * 10, 1.0) * 0.3)

            return min(score, 1.0)

        except Exception as e:
            logger.warning(f"语义分数计算失败: {e}")
            return 0.5

    def _post_process_chunks(self, chunks: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """后处理分段结果"""
        processed_chunks = []

        for i, chunk in enumerate(chunks):
            # 添加通用元数据
            if config["include_metadata"]:
                chunk["metadata"].update({
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "content_length": len(chunk["content"]),
                    "word_count": len(chunk["content"].split()),
                    "char_count": len(chunk["content"])
                })

            # 过滤太短的块（但保留markdown标题章节，它们是完整的语义单元）
            is_markdown_section = (
                chunk.get("type") == "markdown" and
                chunk.get("metadata", {}).get("heading")
            )
            if not is_markdown_section and len(chunk["content"]) < config["min_chunk_size"]:
                continue

            # 清理内容
            chunk["content"] = chunk["content"].strip()

            processed_chunks.append(chunk)

        return processed_chunks

    def analyze_content_structure(self, content: str) -> Dict[str, Any]:
        """分析内容结构"""
        try:
            analysis = {
                "total_length": len(content),
                "paragraph_count": len([p for p in content.split('\n\n') if p.strip()]),
                "sentence_count": len(re.findall(r'[。！？.!?]', content)),
                "word_count": len(content.split()),
                "char_count": len(content),
                "structure_types": []
            }

            # 分析结构类型
            if re.search(r'^#+\s', content, re.MULTILINE):
                analysis["structure_types"].append("markdown")

            if re.search(r'^\d+\.\s', content, re.MULTILINE):
                analysis["structure_types"].append("numbered_list")

            if re.search(r'^[-*•]\s', content, re.MULTILINE):
                analysis["structure_types"].append("bullet_list")

            if re.search(r'\t|,{3,}', content):
                analysis["structure_types"].append("table")

            if re.search(r'```', content):
                analysis["structure_types"].append("code")

            return analysis

        except Exception as e:
            logger.error(f"内容结构分析失败: {e}")
            return {}

    def get_chunking_strategies(self) -> List[str]:
        """获取可用的分段策略"""
        return list(self.chunk_strategies.keys())

    def get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return self.default_config.copy()
