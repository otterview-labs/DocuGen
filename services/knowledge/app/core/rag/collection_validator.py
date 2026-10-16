#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集合名称验证和处理工具
确保集合名称符合Milvus的命名规则
"""

import re
import hashlib
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def validate_and_fix_collection_name(name: str) -> str:
    """
    验证并修正集合名称，使其符合Milvus的命名规则

    Milvus集合名称规则：
    - 必须以字母或下划线开头
    - 只能包含字母、数字、下划线
    - 长度在1-255之间
    - 不能是纯数字

    Args:
        name: 原始集合名称

    Returns:
        合法的集合名称
    """
    if not name:
        return "default"

    # 如果是纯数字ID（如：1967830124693413888），添加前缀
    if name.isdigit():
        # 对于纯数字ID，使用col_前缀+哈希值的前8位
        hash_suffix = hashlib.md5(name.encode()).hexdigest()[:8]
        fixed_name = f"col_{hash_suffix}"
        logger.info(f"纯数字集合名 {name} 转换为 {fixed_name}")
        return fixed_name

    # 如果以数字开头，添加前缀
    if name[0].isdigit():
        name = f"col_{name}"

    # 替换非法字符为下划线
    clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)

    # 确保以字母或下划线开头
    if clean_name and not (clean_name[0].isalpha() or clean_name[0] == '_'):
        clean_name = f"col_{clean_name}"

    # 限制长度
    if len(clean_name) > 255:
        clean_name = clean_name[:255]

    # 如果处理后为空，使用默认值
    if not clean_name:
        clean_name = "default"

    if clean_name != name:
        logger.debug(f"集合名称 {name} 修正为 {clean_name}")

    return clean_name


def get_milvus_collection_name(original_name: str, use_mapping: bool = True) -> str:
    """
    获取Milvus中实际使用的集合名称

    Args:
        original_name: 原始集合名称（可能是数字ID）
        use_mapping: 是否使用映射表（保持向后兼容）

    Returns:
        Milvus中的实际集合名称
    """
    # 如果启用映射，维护一个映射表
    if use_mapping:
        # 常见的数字ID映射
        id_mapping = {
            "1967830124693413888": "col_19678301",
            "1967800725524832256": "col_19678007",
            # 可以添加更多映射
        }

        if original_name in id_mapping:
            return id_mapping[original_name]

    # 使用标准验证
    return validate_and_fix_collection_name(original_name)


def ensure_collection_name_valid(collection_id: Optional[str]) -> str:
    """
    确保集合名称有效，如果无效则返回默认值

    Args:
        collection_id: 原始集合ID

    Returns:
        有效的集合名称
    """
    if not collection_id:
        return "default"

    return validate_and_fix_collection_name(collection_id)
