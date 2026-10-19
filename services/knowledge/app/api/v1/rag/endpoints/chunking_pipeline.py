#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档分块策略接口
提供分块策略查询和配置功能
"""

from typing import Dict, List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from app.db.session import get_db
from app.shared.response_models import ResponseHelper
from app.shared.parsers.smart_chunker import SmartChunker

router = APIRouter()


@router.get("/strategies", response_model=Dict)
async def get_chunking_strategies():
    """
    获取可用的分块策略信息

    返回所有支持的分块策略及其详细信息，包括：
    - 策略名称和描述
    - 适用场景
    - 优缺点
    - 默认配置
    """
    try:
        chunker = SmartChunker()
        strategies = chunker.get_chunking_strategies()
        default_config = chunker.get_default_config()

        strategy_descriptions = {
            "semantic": {
                "name": "语义分块",
                "description": "基于语义相似度的智能分块，适合复杂文档",
                "best_for": ["技术文档", "学术论文", "复杂报告"],
                "pros": ["保持语义完整性", "智能边界识别"],
                "cons": ["计算复杂度较高", "需要较多计算资源"]
            },
            "fixed_size": {
                "name": "固定大小分块",
                "description": "固定字符数分块，处理均匀",
                "best_for": ["简单文本", "一致性要求高的场景"],
                "pros": ["处理速度快", "内存使用可预测"],
                "cons": ["可能切断语义单元", "不适合复杂结构"]
            },
            "paragraph": {
                "name": "段落分块",
                "description": "按段落进行分块，保持结构完整",
                "best_for": ["文章", "博客", "书籍章节"],
                "pros": ["保持段落完整性", "结构清晰"],
                "cons": ["段落大小不均", "可能产生过大分块"]
            },
            "sentence": {
                "name": "句子分块",
                "description": "按句子进行分块，精细化处理",
                "best_for": ["对话文本", "问答数据", "精细分析"],
                "pros": ["粒度精细", "便于精确匹配"],
                "cons": ["分块过小", "上下文信息丢失"]
            },
            "hybrid": {
                "name": "混合策略",
                "description": "结合多种策略的优势，自动选择最佳方法",
                "best_for": ["通用场景", "混合内容", "未知文档类型"],
                "pros": ["自适应性强", "平衡各种需求"],
                "cons": ["逻辑较复杂", "参数调优困难"]
            }
        }

        result = {
            "available_strategies": strategies,
            "default_config": default_config,
            "strategy_details": {
                strategy: strategy_descriptions.get(strategy, {
                    "name": strategy,
                    "description": f"{strategy}分块策略"
                })
                for strategy in strategies
            },
            "recommendations": {
                "general": "hybrid",
                "technical_docs": "semantic",
                "simple_text": "fixed_size",
                "structured_text": "paragraph",
                "qa_data": "sentence"
            },
            "config_parameters": {
                "max_chunk_size": {
                    "description": "最大分块大小（字符数）",
                    "default": default_config.get("max_chunk_size", 500),
                    "range": [100, 2000]
                },
                "min_chunk_size": {
                    "description": "最小分块大小（字符数）",
                    "default": default_config.get("min_chunk_size", 120),
                    "range": [50, 500]
                },
                "overlap_size": {
                    "description": "分块重叠大小（字符数）",
                    "default": default_config.get("overlap_size", 75),
                    "range": [0, 200]
                },
                "preserve_structure": {
                    "description": "是否保持文档结构",
                    "default": default_config.get("preserve_structure", True),
                    "type": "boolean"
                },
                "include_metadata": {
                    "description": "是否包含元数据",
                    "default": default_config.get("include_metadata", True),
                    "type": "boolean"
                }
            }
        }

        return ResponseHelper.success(
            result=result,
            message="分块策略信息获取成功"
        )

    except Exception as e:
        logger.error(f"获取分块策略失败: {e}")
        return ResponseHelper.error(f"获取分块策略失败: {str(e)}", status=500)
