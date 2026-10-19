#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
辅助工具模块
"""

from .extract_json import extract_json_from_content
from .get_request_id import generate_request_id

__all__ = [
    "extract_json_from_content",
    "generate_request_id"
]
