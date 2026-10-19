#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAISS向量库实现
"""

import os
import json
import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import faiss
from datetime import datetime

from app.core.rag.vector_db.base import VectorDBBase
from app.config import settings

logger = logging.getLogger(__name__)


class FaissVectorDB(VectorDBBase):
    """FAISS向量库实现"""

    def __init__(self):
        self.index_path = settings.vector_db.FAISS_INDEX_PATH
        self.index_type = settings.vector_db.FAISS_INDEX_TYPE
        self.dimension = settings.vector_db.VECTOR_DB_DIMENSION

        # 确保索引目录存在
        os.makedirs(self.index_path, exist_ok=True)

        # 内存中的索引和元数据
        self._indices = {}
        self._metadata = {}
        self._collection_info = {}

        # 加载现有集合
        self._load_existing_collections()

    def _get_index_path(self, collection_name: str) -> str:
        """获取索引文件路径"""
        return os.path.join(self.index_path, f"{collection_name}.index")

    def _get_metadata_path(self, collection_name: str) -> str:
        """获取元数据文件路径"""
        return os.path.join(self.index_path, f"{collection_name}_metadata.json")

    def _get_collection_info_path(self, collection_name: str) -> str:
        """获取集合信息文件路径"""
        return os.path.join(self.index_path, f"{collection_name}_info.json")

    def _load_existing_collections(self):
        """加载现有集合"""
        try:
            if os.path.exists(self.index_path):
                for filename in os.listdir(self.index_path):
                    if filename.endswith('.index'):
                        collection_name = filename[:-6]  # 去掉.index后缀
                        self._load_collection(collection_name)
        except Exception as e:
            logger.error(f"加载现有集合失败: {e}")

    def _load_collection(self, collection_name: str) -> bool:
        """加载集合"""
        try:
            # 加载索引
            index_path = self._get_index_path(collection_name)
            if os.path.exists(index_path):
                self._indices[collection_name] = faiss.read_index(index_path)

            # 加载元数据
            metadata_path = self._get_metadata_path(collection_name)
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    self._metadata[collection_name] = json.load(f)

            # 加载集合信息
            info_path = self._get_collection_info_path(collection_name)
            if os.path.exists(info_path):
                with open(info_path, 'r', encoding='utf-8') as f:
                    self._collection_info[collection_name] = json.load(f)

            return True
        except Exception as e:
            logger.error(f"加载集合 {collection_name} 失败: {e}")
            return False

    def _save_collection(self, collection_name: str) -> bool:
        """保存集合"""
        try:
            # 保存索引
            if collection_name in self._indices:
                index_path = self._get_index_path(collection_name)
                faiss.write_index(self._indices[collection_name], index_path)

            # 保存元数据
            if collection_name in self._metadata:
                metadata_path = self._get_metadata_path(collection_name)
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(self._metadata[collection_name], f, ensure_ascii=False, indent=2)

            # 保存集合信息
            if collection_name in self._collection_info:
                info_path = self._get_collection_info_path(collection_name)
                with open(info_path, 'w', encoding='utf-8') as f:
                    json.dump(self._collection_info[collection_name], f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            logger.error(f"保存集合 {collection_name} 失败: {e}")
            return False

    def create_collection(self, collection_name: str, dimension: int = 1536, **kwargs) -> bool:
        """创建集合"""
        try:
            if self.collection_exists(collection_name):
                logger.warning(f"集合 {collection_name} 已存在")
                return True

            # 创建FAISS索引
            if self.index_type == "Flat":
                index = faiss.IndexFlatIP(dimension)  # 内积索引
            elif self.index_type == "IVF":
                nlist = kwargs.get('nlist', 100)
                index = faiss.IndexIVFFlat(faiss.IndexFlatIP(dimension), dimension, nlist)
            elif self.index_type == "HNSW":
                M = kwargs.get('M', 32)
                index = faiss.IndexHNSWFlat(dimension, M)
            else:
                index = faiss.IndexFlatIP(dimension)

            # 初始化集合
            self._indices[collection_name] = index
            self._metadata[collection_name] = {}
            self._collection_info[collection_name] = {
                "name": collection_name,
                "dimension": dimension,
                "index_type": self.index_type,
                "created_at": datetime.now().isoformat(),
                "vector_count": 0
            }

            # 保存集合
            self._save_collection(collection_name)

            logger.info(f"创建集合 {collection_name} 成功")
            return True

        except Exception as e:
            logger.error(f"创建集合 {collection_name} 失败: {e}")
            return False

    def collection_exists(self, collection_name: str) -> bool:
        """检查集合是否存在"""
        return collection_name in self._indices

    def list_collections(self) -> List[str]:
        """列出所有集合"""
        return list(self._indices.keys())

    def delete_collection(self, collection_name: str) -> bool:
        """删除集合"""
        try:
            # 删除内存中的数据
            if collection_name in self._indices:
                del self._indices[collection_name]
            if collection_name in self._metadata:
                del self._metadata[collection_name]
            if collection_name in self._collection_info:
                del self._collection_info[collection_name]

            # 删除文件
            index_path = self._get_index_path(collection_name)
            metadata_path = self._get_metadata_path(collection_name)
            info_path = self._get_collection_info_path(collection_name)

            for path in [index_path, metadata_path, info_path]:
                if os.path.exists(path):
                    os.remove(path)

            logger.info(f"删除集合 {collection_name} 成功")
            return True

        except Exception as e:
            logger.error(f"删除集合 {collection_name} 失败: {e}")
            return False

    def add_vectors(self, collection_name: str, vectors: np.ndarray,
                   metadata: List[Dict[str, Any]], ids: Optional[List[str]] = None) -> List[str]:
        """添加向量"""
        try:
            if not self.collection_exists(collection_name):
                raise ValueError(f"集合 {collection_name} 不存在")

            # 生成ID
            if ids is None:
                ids = [str(uuid.uuid4()) for _ in range(len(vectors))]

            # 添加向量到索引
            index = self._indices[collection_name]
            index.add(vectors)

            # 保存元数据
            for i, (vector_id, meta) in enumerate(zip(ids, metadata)):
                self._metadata[collection_name][vector_id] = {
                    **meta,
                    "id": vector_id,
                    "index": index.ntotal - len(vectors) + i,
                    "created_at": datetime.now().isoformat()
                }

            # 更新集合信息
            self._collection_info[collection_name]["vector_count"] = index.ntotal

            # 保存集合
            self._save_collection(collection_name)

            logger.info(f"向集合 {collection_name} 添加 {len(vectors)} 个向量成功")
            return ids

        except Exception as e:
            logger.error(f"添加向量到集合 {collection_name} 失败: {e}")
            raise

    def search(self, collection_name: str, query_vector: np.ndarray,
              top_k: int = 5, filter_condition: Optional[Dict] = None) -> Tuple[List[str], List[float], List[Dict]]:
        """搜索向量"""
        try:
            if not self.collection_exists(collection_name):
                raise ValueError(f"集合 {collection_name} 不存在")

            index = self._indices[collection_name]

            # 为了避免“僵尸向量”（FAISS不支持物理删除）影响结果，检索放大候选数量
            search_limit = min(max(top_k * 5, top_k), index.ntotal if hasattr(index, 'ntotal') else top_k)
            scores, indices = index.search(query_vector.reshape(1, -1), search_limit)

            # 获取结果（确保分数与ID对齐）
            ids: List[str] = []
            result_metadata: List[Dict] = []
            kept_scores: List[float] = []

            row_scores = scores[0]
            row_indices = indices[0]

            for score, idx in zip(row_scores, row_indices):
                if idx == -1:
                    continue
                # 根据索引找到对应的ID和元数据
                matched_id = None
                matched_meta = None
                for vector_id, meta in self._metadata[collection_name].items():
                    if meta.get("index") == int(idx):
                        matched_id = vector_id
                        matched_meta = meta
                        break
                if not matched_id:
                    # 可能是已删除的向量（仅从索引中仍存在），跳过
                    continue
                # 应用过滤条件
                if filter_condition and not self._match_filter(matched_meta, filter_condition):
                    continue
                ids.append(matched_id)
                result_metadata.append(matched_meta)
                kept_scores.append(float(score))
                if len(ids) >= top_k:
                    break

            return ids, kept_scores, result_metadata

        except Exception as e:
            logger.error(f"在集合 {collection_name} 中搜索失败: {e}")
            raise

    def _match_filter(self, metadata: Dict, filter_condition: Dict) -> bool:
        """匹配过滤条件"""
        for key, value in filter_condition.items():
            if key not in metadata or metadata[key] != value:
                return False
        return True

    def delete_vectors(self, collection_name: str, ids: List[str]) -> bool:
        """删除向量"""
        try:
            if not self.collection_exists(collection_name):
                raise ValueError(f"集合 {collection_name} 不存在")

            # FAISS不支持直接删除，这里只是从元数据中删除
            for vector_id in ids:
                if vector_id in self._metadata[collection_name]:
                    del self._metadata[collection_name][vector_id]

            # 保存集合
            self._save_collection(collection_name)

            logger.info(f"从集合 {collection_name} 删除 {len(ids)} 个向量成功")
            return True

        except Exception as e:
            logger.error(f"删除向量失败: {e}")
            return False

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """获取集合信息"""
        if collection_name not in self._collection_info:
            return {}

        info = self._collection_info[collection_name].copy()
        # 额外返回活跃向量数量（基于元数据），用于衡量已删除但未压缩的条目
        info["metadata_count"] = len(self._metadata.get(collection_name, {}))
        info["active_vector_count"] = info["metadata_count"]
        return info

    def update_metadata(self, collection_name: str, id: str, metadata: Dict[str, Any]) -> bool:
        """更新元数据"""
        try:
            if not self.collection_exists(collection_name):
                raise ValueError(f"集合 {collection_name} 不存在")

            if id in self._metadata[collection_name]:
                self._metadata[collection_name][id].update(metadata)
                self._metadata[collection_name][id]["updated_at"] = datetime.now().isoformat()

                # 保存集合
                self._save_collection(collection_name)
                return True

            return False

        except Exception as e:
            logger.error(f"更新元数据失败: {e}")
            return False
