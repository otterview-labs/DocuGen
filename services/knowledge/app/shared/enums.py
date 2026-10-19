#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
共享枚举类型定义
"""

from enum import Enum


class ModelType(str, Enum):
    """模型类型枚举"""
    LLM = "LLM"  # 大语言模型
    EMBEDDING = "Embedding"  # 向量化模型
    RERANK = "Rerank"  # 重排序模型
    ASR = "ASR"  # 语音识别模型
    TTS = "TTS"  # 语音合成模型
    IMAGE2TEXT = "Image2Text"  # 图像理解模型


class StatusEnum(str, Enum):
    """状态枚举"""
    DISABLED = "0"  # 禁用
    ENABLED = "1"  # 启用
