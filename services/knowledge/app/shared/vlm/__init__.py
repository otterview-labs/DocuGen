#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用视觉语言模型（VLM）组件。

保持导出为懒加载，避免 minimal 安装下因可选视觉依赖导致顶层导入失败。
"""

from __future__ import annotations

import importlib

_LAZY_EXPORTS = {
    "VisionAnalyzer": ("app.shared.vlm.vision_analyzer", "VisionAnalyzer"),
    "VLMConfig": ("app.shared.vlm.config", "VLMConfig"),
    "VisualImageEmbedder": ("app.shared.vlm.visual_embedding", "VisualImageEmbedder"),
    "get_visual_image_embedder": ("app.shared.vlm.visual_embedding", "get_visual_image_embedder"),
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_path, attr_name = _LAZY_EXPORTS[name]
    module = importlib.import_module(module_path)
    return getattr(module, attr_name)


__all__ = list(_LAZY_EXPORTS.keys())
