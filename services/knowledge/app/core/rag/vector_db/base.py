#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
向量库抽象基类
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import numpy as np


class VectorDBBase(ABC):
    """向量库抽象基类"""

    @abstractmethod
    def create_collection(self, collection_name: str, dimension: int = 1536, **kwargs) -> bool:
        """创建集合"""
        pass

    @abstractmethod
    def collection_exists(self, collection_name: str) -> bool:
        """检查集合是否存在"""
        pass

    @abstractmethod
    def list_collections(self) -> List[str]:
        """列出所有集合"""
        pass

    @abstractmethod
    def delete_collection(self, collection_name: str) -> bool:
        """删除集合"""
        pass

    @abstractmethod
    def add_vectors(self, collection_name: str, vectors: np.ndarray,
                   metadata: List[Dict[str, Any]], ids: Optional[List[str]] = None) -> List[str]:
        """添加向量"""
        pass

    @abstractmethod
    def search(self, collection_name: str, query_vector: np.ndarray,
              top_k: int = 5, filter_condition: Optional[Dict] = None) -> Tuple[List[str], List[float], List[Dict]]:
        """搜索向量"""
        pass

    @abstractmethod
    def delete_vectors(self, collection_name: str, ids: List[str]) -> bool:
        """删除向量"""
        pass

    @abstractmethod
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """获取集合信息"""
        pass

    @abstractmethod
    def update_metadata(self, collection_name: str, id: str, metadata: Dict[str, Any]) -> bool:
        """更新元数据"""
        pass
