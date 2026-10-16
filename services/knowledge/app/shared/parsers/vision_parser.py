#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视觉解析器 - 参考深度的vision模块
支持OCR、布局识别、表格结构识别等功能
"""

import os
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cv2

# OCR相关
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

# 布局识别相关
try:
    import torch
    import torchvision
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


class OCR:
    """OCR文本识别 - 参考深度的OCR模块"""

    def __init__(self, languages=['ch_sim', 'en']):
        self.languages = languages
        self.reader = None

        if EASYOCR_AVAILABLE:
            try:
                self.reader = easyocr.Reader(languages, gpu=torch.cuda.is_available() if TORCH_AVAILABLE else False)
                logger.info("EasyOCR初始化成功")
            except Exception as e:
                logger.warning(f"EasyOCR初始化失败: {e}")
        else:
            logger.warning("EasyOCR未安装，OCR功能不可用")

    def extract_text(self, image_path: str) -> Dict[str, Any]:
        """
        从图像中提取文本

        Args:
            image_path: 图像文件路径

        Returns:
            OCR结果字典
        """
        try:
            if not self.reader:
                return {"error": "OCR引擎未初始化"}

            # 读取图像
            image = cv2.imread(image_path)
            if image is None:
                return {"error": "无法读取图像文件"}

            # 执行OCR
            results = self.reader.readtext(image)

            # 处理结果
            extracted_text = []
            for (bbox, text, confidence) in results:
                if confidence > 0.5:  # 置信度阈值
                    extracted_text.append({
                        "text": text,
                        "bbox": bbox,
                        "confidence": confidence
                    })

            return {
                "success": True,
                "text_blocks": extracted_text,
                "full_text": " ".join([block["text"] for block in extracted_text]),
                "total_blocks": len(extracted_text),
                "average_confidence": np.mean([block["confidence"] for block in extracted_text]) if extracted_text else 0
            }

        except Exception as e:
            logger.error(f"OCR提取失败: {e}")
            return {"error": str(e)}

    def extract_text_from_pil(self, image: Image.Image) -> Dict[str, Any]:
        """
        从PIL图像中提取文本

        Args:
            image: PIL图像对象

        Returns:
            OCR结果字典
        """
        try:
            if not self.reader:
                return {"error": "OCR引擎未初始化"}

            # 转换为OpenCV格式
            image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

            # 执行OCR
            results = self.reader.readtext(image_cv)

            # 处理结果
            extracted_text = []
            for (bbox, text, confidence) in results:
                if confidence > 0.5:
                    extracted_text.append({
                        "text": text,
                        "bbox": bbox,
                        "confidence": confidence
                    })

            return {
                "success": True,
                "text_blocks": extracted_text,
                "full_text": " ".join([block["text"] for block in extracted_text]),
                "total_blocks": len(extracted_text),
                "average_confidence": np.mean([block["confidence"] for block in extracted_text]) if extracted_text else 0
            }

        except Exception as e:
            logger.error(f"OCR提取失败: {e}")
            return {"error": str(e)}


class LayoutRecognizer:
    """布局识别器 - 参考深度的布局识别模块"""

    def __init__(self):
        self.model = None
        self.available = False

        # 布局类型定义
        self.layout_types = {
            0: "Text",
            1: "Title",
            2: "Figure",
            3: "Figure caption",
            4: "Table",
            5: "Table caption",
            6: "Header",
            7: "Footer",
            8: "Reference",
            9: "Equation"
        }

        # 尝试初始化模型
        self._init_model()

    def _init_model(self):
        """初始化布局识别模型"""
        try:
            # 这里可以集成预训练的布局识别模型
            # 目前使用简单的规则基础方法
            self.available = True
            logger.info("布局识别器初始化成功")
        except Exception as e:
            logger.warning(f"布局识别模型初始化失败: {e}")
            self.available = False

    def recognize_layout(self, image_path: str) -> Dict[str, Any]:
        """
        识别图像中的布局结构

        Args:
            image_path: 图像文件路径

        Returns:
            布局识别结果
        """
        try:
            if not self.available:
                return {"error": "布局识别器未初始化"}

            # 读取图像
            image = cv2.imread(image_path)
            if image is None:
                return {"error": "无法读取图像文件"}

            # 简化的布局识别逻辑
            layout_blocks = self._simple_layout_detection(image)

            return {
                "success": True,
                "layout_blocks": layout_blocks,
                "total_blocks": len(layout_blocks),
                "layout_types": list(set([block["type"] for block in layout_blocks]))
            }

        except Exception as e:
            logger.error(f"布局识别失败: {e}")
            return {"error": str(e)}

    def _simple_layout_detection(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """简化的布局检测"""
        blocks = []

        # 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 边缘检测
        edges = cv2.Canny(gray, 50, 150)

        # 查找轮廓
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            # 计算边界框
            x, y, w, h = cv2.boundingRect(contour)

            # 过滤小区域
            if w < 50 or h < 20:
                continue

            # 分析区域类型
            block_type = self._analyze_block_type(image[y:y+h, x:x+w])

            blocks.append({
                "bbox": [x, y, x+w, y+h],
                "type": block_type,
                "area": w * h,
                "aspect_ratio": w / h if h > 0 else 0
            })

        return blocks

    def _analyze_block_type(self, block_image: np.ndarray) -> str:
        """分析块类型"""
        try:
            # 简化的类型分析
            gray = cv2.cvtColor(block_image, cv2.COLOR_BGR2GRAY)

            # 计算特征
            height, width = gray.shape
            aspect_ratio = width / height if height > 0 else 0

            # 基于形状和大小判断类型
            if aspect_ratio > 3:  # 很宽的块
                return "Text"
            elif aspect_ratio < 0.5:  # 很高的块
                return "Title"
            elif width > 200 and height > 200:  # 大块
                return "Figure"
            else:
                return "Text"

        except Exception:
            return "Text"


class TableStructureRecognizer:
    """表格结构识别器 - 参考深度的表格识别模块"""

    def __init__(self):
        self.available = True
        logger.info("表格结构识别器初始化成功")

    def recognize_table_structure(self, image_path: str) -> Dict[str, Any]:
        """
        识别表格结构

        Args:
            image_path: 图像文件路径

        Returns:
            表格结构识别结果
        """
        try:
            # 读取图像
            image = cv2.imread(image_path)
            if image is None:
                return {"error": "无法读取图像文件"}

            # 简化的表格检测
            table_structure = self._simple_table_detection(image)

            return {
                "success": True,
                "table_structure": table_structure,
                "has_table": len(table_structure["cells"]) > 0
            }

        except Exception as e:
            logger.error(f"表格结构识别失败: {e}")
            return {"error": str(e)}

    def _simple_table_detection(self, image: np.ndarray) -> Dict[str, Any]:
        """简化的表格检测"""
        structure = {
            "cells": [],
            "rows": [],
            "columns": [],
            "headers": []
        }

        # 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 边缘检测
        edges = cv2.Canny(gray, 50, 150)

        # 查找水平线和垂直线
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))

        horizontal_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, horizontal_kernel)
        vertical_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, vertical_kernel)

        # 合并线条
        table_lines = cv2.addWeighted(horizontal_lines, 1, vertical_lines, 1, 0)

        # 查找轮廓
        contours, _ = cv2.findContours(table_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            # 过滤小区域
            if w < 30 or h < 30:
                continue

            structure["cells"].append({
                "bbox": [x, y, x+w, y+h],
                "type": "cell",
                "area": w * h
            })

        return structure


class VisionParser:
    """综合视觉解析器"""

    def __init__(self):
        self.ocr = OCR()
        self.layout_recognizer = LayoutRecognizer()
        self.table_recognizer = TableStructureRecognizer()

    def parse_image(self, image_path: str) -> Dict[str, Any]:
        """
        综合解析图像

        Args:
            image_path: 图像文件路径

        Returns:
            综合解析结果
        """
        try:
            result = {
                "ocr_result": {},
                "layout_result": {},
                "table_result": {},
                "metadata": {}
            }

            # OCR文本提取
            ocr_result = self.ocr.extract_text(image_path)
            result["ocr_result"] = ocr_result

            # 布局识别
            layout_result = self.layout_recognizer.recognize_layout(image_path)
            result["layout_result"] = layout_result

            # 表格结构识别
            table_result = self.table_recognizer.recognize_table_structure(image_path)
            result["table_result"] = table_result

            # 元数据
            try:
                with Image.open(image_path) as img:
                    result["metadata"] = {
                        "format": img.format,
                        "mode": img.mode,
                        "size": img.size,
                        "width": img.width,
                        "height": img.height
                    }
            except Exception as e:
                logger.warning(f"获取图像元数据失败: {e}")

            return result

        except Exception as e:
            logger.error(f"图像解析失败: {e}")
            return {"error": str(e)}

    def extract_text_from_image(self, image_path: str) -> str:
        """
        从图像中提取文本

        Args:
            image_path: 图像文件路径

        Returns:
            提取的文本
        """
        try:
            ocr_result = self.ocr.extract_text(image_path)
            if "error" in ocr_result:
                return ""

            return ocr_result.get("full_text", "")

        except Exception as e:
            logger.error(f"文本提取失败: {e}")
            return ""

    def get_layout_blocks(self, image_path: str) -> List[Dict[str, Any]]:
        """
        获取布局块信息

        Args:
            image_path: 图像文件路径

        Returns:
            布局块列表
        """
        try:
            layout_result = self.layout_recognizer.recognize_layout(image_path)
            if "error" in layout_result:
                return []

            return layout_result.get("layout_blocks", [])

        except Exception as e:
            logger.error(f"布局块获取失败: {e}")
            return []
