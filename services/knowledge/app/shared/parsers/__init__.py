#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
文件解析器模块。
"""

from __future__ import annotations

import importlib

_LAZY_EXPORTS = {
    "Parser": ("app.shared.parsers.file_parse", "Parser"),
    "MineruParser": ("app.shared.parsers.file_parse", "MineruParser"),
    "DoclingParser": ("app.shared.parsers.file_parse", "DoclingParser"),
    "FileToMarkdown": ("app.shared.parsers.file_quckly_parse", "FileToMarkdown"),
    "EnhancedDocumentParser": ("app.shared.parsers.enhanced_parser", "EnhancedDocumentParser"),
    "OCR": ("app.shared.parsers.vision_parser", "OCR"),
    "LayoutRecognizer": ("app.shared.parsers.vision_parser", "LayoutRecognizer"),
    "TableStructureRecognizer": ("app.shared.parsers.vision_parser", "TableStructureRecognizer"),
    "VisionParser": ("app.shared.parsers.vision_parser", "VisionParser"),
    "SmartChunker": ("app.shared.parsers.smart_chunker", "SmartChunker"),
    "DeepDocumentParser": ("app.shared.parsers.deep_document_parser", "DeepDocumentParser"),
    "DeepOCR": ("app.shared.parsers.deep_document_parser", "DeepOCR"),
    "DeepLayoutRecognizer": ("app.shared.parsers.deep_document_parser", "DeepLayoutRecognizer"),
    "DeepTableStructureRecognizer": ("app.shared.parsers.deep_document_parser", "DeepTableStructureRecognizer"),
    "SemanticAnalyzer": ("app.shared.parsers.deep_document_parser", "SemanticAnalyzer"),
    "LLMEnhancedParser": ("app.shared.parsers.llm_enhanced_parser", "LLMEnhancedParser"),
    "LocalLLMParser": ("app.shared.parsers.llm_enhanced_parser", "LocalLLMParser"),
    "HybridParser": ("app.shared.parsers.llm_enhanced_parser", "HybridParser"),
}

_ALIASES = {
    "FileParser": "Parser",
    "QuickFileParser": "FileToMarkdown",
}


def __getattr__(name: str):
    target_name = _ALIASES.get(name, name)
    if target_name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, attr_name = _LAZY_EXPORTS[target_name]
    module = importlib.import_module(module_path)
    return getattr(module, attr_name)


__all__ = [
    "Parser",
    "MineruParser",
    "DoclingParser",
    "FileToMarkdown",
    "EnhancedDocumentParser",
    "OCR",
    "LayoutRecognizer",
    "TableStructureRecognizer",
    "VisionParser",
    "SmartChunker",
    "DeepDocumentParser",
    "DeepOCR",
    "DeepLayoutRecognizer",
    "DeepTableStructureRecognizer",
    "SemanticAnalyzer",
    "LLMEnhancedParser",
    "LocalLLMParser",
    "HybridParser",
    "FileParser",
    "QuickFileParser",
]
