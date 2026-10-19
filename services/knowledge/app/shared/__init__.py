#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
共享工具模块。

避免在包导入阶段立即加载重型解析器依赖。
"""

from __future__ import annotations

__all__ = [
    "generate_request_id",
    "format_response",
    "validate_input",
    "FileParser",
    "QuickFileParser",
    "extract_json_from_content",
]


def __getattr__(name: str):
    if name in {"generate_request_id", "format_response", "validate_input"}:
        from .utils import format_response, generate_request_id, validate_input

        return {
            "generate_request_id": generate_request_id,
            "format_response": format_response,
            "validate_input": validate_input,
        }[name]

    if name in {"FileParser", "QuickFileParser"}:
        from .parsers import FileParser, QuickFileParser

        return {"FileParser": FileParser, "QuickFileParser": QuickFileParser}[name]

    if name == "extract_json_from_content":
        from .helpers import extract_json_from_content

        return extract_json_from_content

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
