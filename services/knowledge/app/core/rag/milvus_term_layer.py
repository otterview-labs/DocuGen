#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Milvus-based Term Layer Implementation
Replaces the memory-based inverted index with scalable Milvus collections
"""

import re
import json
import logging
from typing import List, Dict, Set, Optional
from pymilvus import (
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
    connections
)
from app.core.rag.vector_db.milvus_db import MilvusVectorDB
from app.db.session import get_db
from app.db.models.rag import RAGChunk

logger = logging.getLogger(__name__)


class MilvusTermLayer:
    """
    使用Milvus实现的词汇层
    解决原有TermLayer的1000条记录限制问题
    """

    def __init__(self, collection_name: str = "term_index"):
        """
        初始化Milvus词汇索引

        Args:
            collection_name: Milvus集合名称
        """
        self.collection_name = collection_name
        self.milvus_db = MilvusVectorDB()
        self.collection = None
        self._initialize_collection()

    def _initialize_collection(self):
        """初始化或加载Milvus集合"""
        try:
            # 检查集合是否存在
            if utility.has_collection(self.collection_name):
                logger.info(f"加载现有词汇索引集合: {self.collection_name}")
                self.collection = Collection(self.collection_name)
                self.collection.load()
            else:
                logger.info(f"创建新的词汇索引集合: {self.collection_name}")
                self._create_collection()
                self._build_index()

        except Exception as e:
            logger.error(f"初始化Milvus词汇索引失败: {e}")
            raise

    def _create_collection(self):
        """创建Milvus集合用于词汇索引"""
        # 定义字段
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="word", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="content_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="chunk_index", dtype=DataType.INT32),
            FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="word_frequency", dtype=DataType.INT32),
        ]

        # 创建schema
        schema = CollectionSchema(
            fields=fields,
            description="Term inverted index for keyword search"
        )

        # 创建集合
        self.collection = Collection(
            name=self.collection_name,
            schema=schema,
            consistency_level="Strong"
        )

        # 创建索引
        # 为word字段创建倒排索引
        index_params = {
            "index_type": "INVERTED",
            "params": {}
        }
        self.collection.create_index(
            field_name="word",
            index_params=index_params
        )

        # 为chunk_id创建索引以便快速查找
        self.collection.create_index(
            field_name="chunk_id",
            index_params={"index_type": "INVERTED"}
        )

        logger.info(f"词汇索引集合创建成功: {self.collection_name}")

    def _build_index(self):
        """构建Milvus词汇索引（支持大规模数据）"""
        try:
            db = next(get_db())

            # 批量处理，每批1000条
            batch_size = 1000
            offset = 0
            total_processed = 0

            while True:
                # 分批加载数据
                chunks = db.query(RAGChunk).offset(offset).limit(batch_size).all()

                if not chunks:
                    break

                # 准备批量插入数据
                words_batch = []
                chunk_ids_batch = []
                content_ids_batch = []
                chunk_indices_batch = []
                chunk_texts_batch = []
                word_frequencies_batch = []

                for chunk in chunks:
                    if not chunk.chunk_text:
                        continue

                    # 分词
                    word_freq = self._tokenize_with_frequency(chunk.chunk_text)

                    # 为每个词创建索引记录
                    for word, freq in word_freq.items():
                        words_batch.append(word)
                        chunk_ids_batch.append(chunk.id)
                        content_ids_batch.append(chunk.content_id)
                        chunk_indices_batch.append(chunk.chunk_index or 0)
                        chunk_texts_batch.append(chunk.chunk_text[:65535])  # 截断以适应字段长度
                        word_frequencies_batch.append(freq)

                # 批量插入到Milvus
                if words_batch:
                    entities = [
                        words_batch,
                        chunk_ids_batch,
                        content_ids_batch,
                        chunk_indices_batch,
                        chunk_texts_batch,
                        word_frequencies_batch
                    ]

                    self.collection.insert(entities)
                    logger.info(f"插入 {len(words_batch)} 条词汇索引记录")

                total_processed += len(chunks)
                offset += batch_size

                logger.info(f"已处理 {total_processed} 个分块")

                # 每处理10000条刷新一次
                if total_processed % 10000 == 0:
                    self.collection.flush()

            # 最终刷新
            self.collection.flush()
            self.collection.load()

            logger.info(f"词汇索引构建完成，共处理 {total_processed} 个分块")

        except Exception as e:
            logger.error(f"构建Milvus词汇索引失败: {e}")
            raise
        finally:
            db.close()

    def _tokenize_with_frequency(self, text: str) -> Dict[str, int]:
        """分词并计算词频"""
        word_freq = {}

        # 转小写
        text = text.lower()

        # 提取英文单词
        english_words = re.findall(r'[a-z]+', text)
        for word in english_words:
            if len(word) > 1:  # 忽略单字符
                word_freq[word] = word_freq.get(word, 0) + 1

        # 提取中文词（2-4字词）
        chinese_text = ''.join(re.findall(r'[\u4e00-\u9fa5]+', text))
        for length in [2, 3, 4]:
            for i in range(len(chinese_text) - length + 1):
                word = chinese_text[i:i+length]
                word_freq[word] = word_freq.get(word, 0) + 1

        return word_freq

    def _tokenize(self, text: str) -> Set[str]:
        """简单的分词函数（用于查询）"""
        # 转小写
        text = text.lower()

        # 提取英文单词
        english_words = set(re.findall(r'[a-z]+', text))

        # 提取中文词（2-4字词）
        chinese_words = set()
        chinese_text = ''.join(re.findall(r'[\u4e00-\u9fa5]+', text))
        for length in [2, 3, 4]:
            for i in range(len(chinese_text) - length + 1):
                chinese_words.add(chinese_text[i:i+length])

        return english_words | chinese_words

    async def search(self, query: str, top_k: int) -> List[Dict]:
        """
        词汇搜索 - 基于Milvus倒排索引

        Args:
            query: 搜索查询
            top_k: 返回结果数量

        Returns:
            搜索结果列表
        """
        try:
            # 确保集合已加载
            if not self.collection:
                self._initialize_collection()

            # 分词
            query_words = list(self._tokenize(query))

            if not query_words:
                return []

            # 构建查询表达式
            # Milvus支持IN操作符进行批量词汇匹配
            word_conditions = [f'word == "{word}"' for word in query_words[:20]]  # 限制最多20个词
            expr = " || ".join(word_conditions)

            # 执行查询
            results = self.collection.query(
                expr=expr,
                output_fields=["chunk_id", "content_id", "chunk_index", "word", "word_frequency"],
                limit=top_k * 10  # 获取更多结果用于聚合
            )

            # 聚合结果按chunk_id
            chunk_scores = {}
            for result in results:
                chunk_id = result["chunk_id"]
                word = result["word"]
                freq = result.get("word_frequency", 1)

                if chunk_id not in chunk_scores:
                    chunk_scores[chunk_id] = {
                        "chunk_id": chunk_id,
                        "content_id": result["content_id"],
                        "chunk_index": result["chunk_index"],
                        "matched_words": set(),
                        "score": 0
                    }

                chunk_scores[chunk_id]["matched_words"].add(word)
                chunk_scores[chunk_id]["score"] += freq

            # 计算最终分数（匹配词数 * 词频总和）
            final_results = []
            for chunk_info in chunk_scores.values():
                # BM25风格的评分
                matched_ratio = len(chunk_info["matched_words"]) / len(query_words)
                final_score = matched_ratio * chunk_info["score"]

                final_results.append({
                    "chunk_id": chunk_info["chunk_id"],
                    "doc_id": chunk_info["content_id"],
                    "chunk_ids": [chunk_info["chunk_id"]],
                    "score": final_score,
                    "matched_words": list(chunk_info["matched_words"])
                })

            # 排序并返回top_k结果
            final_results.sort(key=lambda x: x["score"], reverse=True)
            return final_results[:top_k]

        except Exception as e:
            logger.error(f"Milvus词汇搜索失败: {e}")
            return []

    def update_index(self, chunks: List[RAGChunk]):
        """
        更新词汇索引（增量更新）

        Args:
            chunks: 新的分块列表
        """
        try:
            if not chunks:
                return

            # 准备批量插入数据
            words_batch = []
            chunk_ids_batch = []
            content_ids_batch = []
            chunk_indices_batch = []
            chunk_texts_batch = []
            word_frequencies_batch = []

            for chunk in chunks:
                if not chunk.chunk_text:
                    continue

                # 分词
                word_freq = self._tokenize_with_frequency(chunk.chunk_text)

                # 为每个词创建索引记录
                for word, freq in word_freq.items():
                    words_batch.append(word)
                    chunk_ids_batch.append(chunk.id)
                    content_ids_batch.append(chunk.content_id)
                    chunk_indices_batch.append(chunk.chunk_index or 0)
                    chunk_texts_batch.append(chunk.chunk_text[:65535])
                    word_frequencies_batch.append(freq)

            # 批量插入到Milvus
            if words_batch:
                entities = [
                    words_batch,
                    chunk_ids_batch,
                    content_ids_batch,
                    chunk_indices_batch,
                    chunk_texts_batch,
                    word_frequencies_batch
                ]

                self.collection.insert(entities)
                self.collection.flush()

                logger.info(f"增量更新 {len(words_batch)} 条词汇索引记录")

        except Exception as e:
            logger.error(f"更新Milvus词汇索引失败: {e}")

    def delete_chunk_index(self, chunk_id: str):
        """
        删除特定分块的索引

        Args:
            chunk_id: 分块ID
        """
        try:
            expr = f'chunk_id == "{chunk_id}"'
            self.collection.delete(expr)
            self.collection.flush()
            logger.info(f"删除分块 {chunk_id} 的词汇索引")
        except Exception as e:
            logger.error(f"删除词汇索引失败: {e}")

    def rebuild_index(self):
        """重建整个词汇索引"""
        try:
            # 删除现有集合
            if utility.has_collection(self.collection_name):
                utility.drop_collection(self.collection_name)
                logger.info(f"删除现有集合: {self.collection_name}")

            # 重新创建并构建索引
            self._create_collection()
            self._build_index()

        except Exception as e:
            logger.error(f"重建词汇索引失败: {e}")
            raise
