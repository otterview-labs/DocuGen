#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
服务层模块
"""

from __future__ import annotations

__all__ = ["RAGService"]


def __getattr__(name: str):
    if name == "RAGService":
        from .enhanced_rag_service import EnhancedRAGService as RAGService

        return RAGService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
