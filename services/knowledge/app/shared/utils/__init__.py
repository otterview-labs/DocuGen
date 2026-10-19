#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
工具模块
"""

from .image_utils import ImageUtils

# 为了兼容性，提供一些通用函数
def generate_request_id():
    """生成请求ID"""
    import uuid
    return str(uuid.uuid4())

def format_response(data, message="success", code=200):
    """格式化响应"""
    return {
        "code": code,
        "message": message,
        "data": data
    }

def validate_input(data, required_fields=None):
    """验证输入数据"""
    if required_fields:
        for field in required_fields:
            if field not in data:
                return False, f"缺少必需字段: {field}"
    return True, "验证通过"

__all__ = [
    "ImageUtils",
    "generate_request_id",
    "format_response",
    "validate_input"
]
