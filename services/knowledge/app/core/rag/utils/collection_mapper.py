#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集合名称映射工具类
统一处理MySQL集合ID与Milvus集合名称之间的转换
"""

import re
from typing import Optional
try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)


class CollectionMapper:
    """
    集合名称映射器
    负责统一处理MySQL集合ID和Milvus集合名称之间的双向转换

    映射规则：
    1. MySQL集合ID（业务层）：可以包含任意字符，如 "milvus-web-test"
    2. Milvus集合名（存储层）：只能包含字母、数字、下划线，如 "milvus_web_test"
    3. 转换规则：将所有非法字符替换为下划线
    """

    @staticmethod
    def to_milvus_name(mysql_collection_id: str) -> str:
        """
        将MySQL集合ID转换为Milvus集合名称

        Args:
            mysql_collection_id: MySQL中的集合ID（可能包含横线等特殊字符）

        Returns:
            str: Milvus兼容的集合名称（只包含字母、数字、下划线）

        Examples:
            >>> CollectionMapper.to_milvus_name("milvus-web-test")
            'milvus_web_test'
            >>> CollectionMapper.to_milvus_name("user@123-collection")
            'user_123_collection'
        """
        if not mysql_collection_id:
            return "default"

        # 将所有非字母、数字、下划线的字符替换为下划线
        safe_name = re.sub(r"[^A-Za-z0-9_]", "_", mysql_collection_id)

        # 移除连续的下划线
        safe_name = re.sub(r"_{2,}", "_", safe_name)

        # 确保不以下划线开头或结尾（Milvus要求）
        safe_name = safe_name.strip("_")

        # 如果处理后为空，返回默认值
        if not safe_name:
            safe_name = "default"

        logger.debug(f"集合名称映射: {mysql_collection_id} -> {safe_name}")
        return safe_name

    @staticmethod
    def normalize_collection_id(collection_id: str) -> str:
        """
        规范化集合ID（用于MySQL存储）
        保持原始格式，只进行基本的清理

        Args:
            collection_id: 原始集合ID

        Returns:
            str: 规范化的集合ID
        """
        if not collection_id:
            return ""

        # 移除首尾空白
        normalized = collection_id.strip()

        # 限制长度（MySQL varchar(255)）
        if len(normalized) > 255:
            normalized = normalized[:255]

        return normalized

    @staticmethod
    def is_valid_milvus_name(name: str) -> bool:
        """
        检查是否为有效的Milvus集合名称

        Args:
            name: 要检查的名称

        Returns:
            bool: 是否有效
        """
        if not name:
            return False

        # Milvus只允许字母、数字、下划线
        pattern = r"^[A-Za-z0-9_]+$"
        return bool(re.match(pattern, name))

    @staticmethod
    def ensure_mapping_consistency(mysql_id: str, milvus_name: Optional[str] = None) -> tuple[str, str]:
        """
        确保MySQL ID和Milvus名称的一致性

        Args:
            mysql_id: MySQL集合ID
            milvus_name: 可选的Milvus集合名称

        Returns:
            tuple: (规范化的MySQL ID, 对应的Milvus名称)
        """
        # 规范化MySQL ID
        normalized_mysql_id = CollectionMapper.normalize_collection_id(mysql_id)

        # 如果提供了Milvus名称，验证其有效性
        if milvus_name:
            if not CollectionMapper.is_valid_milvus_name(milvus_name):
                logger.warning(f"提供的Milvus名称 {milvus_name} 无效，将自动生成")
                milvus_name = CollectionMapper.to_milvus_name(normalized_mysql_id)
        else:
            # 自动生成Milvus名称
            milvus_name = CollectionMapper.to_milvus_name(normalized_mysql_id)

        return normalized_mysql_id, milvus_name


# 全局实例
collection_mapper = CollectionMapper()
