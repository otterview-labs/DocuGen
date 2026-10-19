#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深度文档解析器 - 实现深度级别的文档理解能力
支持OCR、布局识别、表格结构识别、语义分析等深度功能
集成LLM模型实现真正的语义理解
"""

import os
import re
import logging
import numpy as np
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path
import cv2
from PIL import Image, ImageDraw, ImageFont
import json

# 深度学习相关
try:
    import torch
    import torchvision
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# OCR相关
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

# 文本处理
import jieba
import jieba.posseg as pseg
from collections import Counter

# LLM增强功能
try:
    from .llm_enhanced_parser import LLMEnhancedParser, LocalLLMParser, HybridParser
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

logger = logging.getLogger(__name__)


class DeepDocumentParser:
    """深度文档解析器 - 实现深度级别的文档理解能力"""

    def __init__(self, enable_llm: bool = True, llm_model: str = "gpt-3.5-turbo"):
        # 初始化各个组件
        self.ocr = DeepOCR()
        self.layout_recognizer = DeepLayoutRecognizer()
        self.table_recognizer = DeepTableStructureRecognizer()
        self.semantic_analyzer = SemanticAnalyzer()

        # 初始化LLM增强功能
        self.enable_llm = enable_llm and LLM_AVAILABLE
        if self.enable_llm:
            self.llm_parser = LLMEnhancedParser(model_name=llm_model)
            self.local_llm = LocalLLMParser()
            self.hybrid_parser = HybridParser(use_llm=True, llm_parser=self.llm_parser)
            logger.info(f"LLM增强功能已启用，使用模型: {llm_model}")
        else:
            logger.info("LLM增强功能未启用，将使用规则基础分析")

        # 布局类型定义（参考深度）
        self.layout_types = {
            "text": "Text",
            "title": "Title",
            "figure": "Figure",
            "figure_caption": "Figure caption",
            "table": "Table",
            "table_caption": "Table caption",
            "header": "Header",
            "footer": "Footer",
            "reference": "Reference",
            "equation": "Equation"
        }

        logger.info("深度文档解析器初始化完成")

    def parse_document(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """
        深度解析文档

        Args:
            file_path: 文件路径
            **kwargs: 额外参数

        Returns:
            深度解析结果
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                return {"error": f"文件不存在: {file_path}"}

            # 根据文件类型选择解析策略
            if file_path.suffix.lower() in ['.pdf', '.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                return self._parse_image_document(file_path, **kwargs)
            else:
                return self._parse_text_document(file_path, **kwargs)

        except Exception as e:
            logger.error(f"深度解析文档失败: {e}")
            return {"error": str(e)}

    def _parse_image_document(self, file_path: Path, **kwargs) -> Dict[str, Any]:
        """解析图像类文档（PDF、图像等）"""
        try:
            result = {
                "content": "",
                "structure": {
                    "pages": [],
                    "layout_blocks": [],
                    "tables": [],
                    "figures": [],
                    "semantic_sections": []
                },
                "metadata": {
                    "file_path": str(file_path),
                    "file_name": file_path.name,
                    "file_size": file_path.stat().st_size,
                    "parser_type": "deep_parser"
                },
                "analysis": {
                    "ocr_results": [],
                    "layout_analysis": {},
                    "table_analysis": {},
                    "semantic_analysis": {},
                    "llm_analysis": {}  # 新增LLM分析结果
                }
            }

            # 如果是PDF，先转换为图像
            if file_path.suffix.lower() == '.pdf':
                images = self._pdf_to_images(file_path)
            else:
                images = [Image.open(file_path)]

            # 逐页处理
            for page_num, image in enumerate(images):
                page_result = self._process_single_page(image, page_num, **kwargs)
                result["structure"]["pages"].append(page_result)

                # 合并内容
                if page_result.get("content"):
                    result["content"] += f"\n\n--- 第{page_num + 1}页 ---\n\n{page_result['content']}"

            # 语义分析
            if result["content"]:
                # 规则基础语义分析
                semantic_analysis = self.semantic_analyzer.analyze_document(result["content"])
                result["analysis"]["semantic_analysis"] = semantic_analysis
                result["structure"]["semantic_sections"] = semantic_analysis.get("sections", [])

                # LLM增强分析
                if self.enable_llm:
                    llm_analysis = self._perform_llm_analysis(result["content"])
                    result["analysis"]["llm_analysis"] = llm_analysis

            return result

        except Exception as e:
            logger.error(f"图像文档解析失败: {e}")
            return {"error": f"图像文档解析失败: {str(e)}"}

    def _parse_text_document(self, file_path: Path, **kwargs) -> Dict[str, Any]:
        """解析文本类文档"""
        try:
            result = {
                "content": "",
                "structure": {
                    "sections": [],
                    "semantic_blocks": []
                },
                "metadata": {
                    "file_path": str(file_path),
                    "file_name": file_path.name,
                    "file_size": file_path.stat().st_size,
                    "parser_type": "deep_parser"
                },
                "analysis": {
                    "semantic_analysis": {},
                    "llm_analysis": {}  # 新增LLM分析结果
                }
            }

            # 读取文本内容
            content = self._read_text_file(file_path)
            result["content"] = content

            # 语义分析
            if content:
                # 规则基础语义分析
                semantic_analysis = self.semantic_analyzer.analyze_document(content)
                result["analysis"]["semantic_analysis"] = semantic_analysis
                result["structure"]["semantic_blocks"] = semantic_analysis.get("blocks", [])

                # LLM增强分析
                if self.enable_llm:
                    llm_analysis = self._perform_llm_analysis(content)
                    result["analysis"]["llm_analysis"] = llm_analysis

            return result

        except Exception as e:
            logger.error(f"文本文档解析失败: {e}")
            return {"error": f"文本文档解析失败: {str(e)}"}

    def _perform_llm_analysis(self, content: str) -> Dict[str, Any]:
        """执行LLM增强分析"""
        try:
            if not self.enable_llm:
                return {"error": "LLM功能未启用"}

            # 尝试使用OpenAI LLM
            if self.llm_parser.client:
                logger.info("使用OpenAI LLM进行深度分析")
                return self.llm_parser.comprehensive_analysis(content)

            # 尝试使用本地LLM
            elif self.local_llm.available:
                logger.info("使用本地LLM进行深度分析")
                local_result = self.local_llm.analyze_semantics(content)
                return {
                    "success": True,
                    "comprehensive_analysis": {
                        "semantic_analysis": local_result
                    },
                    "model_used": "local_llm"
                }

            # 使用混合解析器
            else:
                logger.info("使用混合解析器进行分析")
                return self.hybrid_parser.analyze_document(content)

        except Exception as e:
            logger.error(f"LLM分析失败: {e}")
            return {"error": f"LLM分析失败: {str(e)}"}

    def _process_single_page(self, image: Image.Image, page_num: int, **kwargs) -> Dict[str, Any]:
        """处理单页图像"""
        try:
            page_result = {
                "page_number": page_num + 1,
                "content": "",
                "layout_blocks": [],
                "tables": [],
                "figures": [],
                "metadata": {}
            }

            # 1. OCR文本识别
            ocr_result = self.ocr.extract_text_from_image(image)
            if ocr_result.get("success"):
                page_result["content"] = ocr_result.get("full_text", "")
                page_result["metadata"]["ocr_confidence"] = ocr_result.get("average_confidence", 0)

            # 2. 布局识别
            layout_result = self.layout_recognizer.recognize_layout_from_image(image)
            if layout_result.get("success"):
                page_result["layout_blocks"] = layout_result.get("layout_blocks", [])

                # 根据布局类型分类内容
                for block in page_result["layout_blocks"]:
                    if block["type"] == "table":
                        page_result["tables"].append(block)
                    elif block["type"] in ["figure", "figure_caption"]:
                        page_result["figures"].append(block)

            # 3. 表格结构识别
            if page_result["tables"]:
                for table in page_result["tables"]:
                    table_structure = self.table_recognizer.recognize_table_structure(image, table["bbox"])
                    table["structure"] = table_structure

            return page_result

        except Exception as e:
            logger.error(f"单页处理失败: {e}")
            return {"error": str(e)}

    def _pdf_to_images(self, pdf_path: Path) -> List[Image.Image]:
        """将PDF转换为图像列表"""
        try:
            import pdfplumber
            images = []

            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    # 转换为图像
                    img = page.to_image()
                    images.append(img.original)

            return images

        except Exception as e:
            logger.error(f"PDF转图像失败: {e}")
            return []

    def _read_text_file(self, file_path: Path) -> str:
        """读取文本文件"""
        try:
            # 尝试不同编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']

            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue

            return ""

        except Exception as e:
            logger.error(f"读取文本文件失败: {e}")
            return ""


class DeepOCR:
    """深度OCR引擎"""

    def __init__(self):
        self.reader = None

        if EASYOCR_AVAILABLE:
            try:
                self.reader = easyocr.Reader(['ch_sim', 'en'], gpu=torch.cuda.is_available() if TORCH_AVAILABLE else False)
                logger.info("深度OCR引擎初始化成功")
            except Exception as e:
                logger.warning(f"深度OCR引擎初始化失败: {e}")
        else:
            logger.warning("EasyOCR未安装，深度OCR功能不可用")

    def extract_text_from_image(self, image: Image.Image) -> Dict[str, Any]:
        """从图像中提取文本"""
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
                if confidence > 0.5:  # 置信度阈值
                    extracted_text.append({
                        "text": text,
                        "bbox": bbox,
                        "confidence": confidence,
                        "center": self._calculate_center(bbox)
                    })

            # 按位置排序（从上到下，从左到右）
            extracted_text.sort(key=lambda x: (x["center"][1], x["center"][0]))

            return {
                "success": True,
                "text_blocks": extracted_text,
                "full_text": " ".join([block["text"] for block in extracted_text]),
                "total_blocks": len(extracted_text),
                "average_confidence": np.mean([block["confidence"] for block in extracted_text]) if extracted_text else 0
            }

        except Exception as e:
            logger.error(f"深度OCR提取失败: {e}")
            return {"error": str(e)}

    def _calculate_center(self, bbox) -> Tuple[float, float]:
        """计算边界框中心点"""
        x_coords = [point[0] for point in bbox]
        y_coords = [point[1] for point in bbox]
        return (np.mean(x_coords), np.mean(y_coords))


class DeepLayoutRecognizer:
    """深度布局识别器"""

    def __init__(self):
        self.available = True
        logger.info("深度布局识别器初始化成功")

    def recognize_layout_from_image(self, image: Image.Image) -> Dict[str, Any]:
        """从图像中识别布局"""
        try:
            # 转换为OpenCV格式
            image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

            # 简化的布局识别逻辑
            layout_blocks = self._detect_layout_blocks(image_cv)

            return {
                "success": True,
                "layout_blocks": layout_blocks,
                "total_blocks": len(layout_blocks)
            }

        except Exception as e:
            logger.error(f"深度布局识别失败: {e}")
            return {"error": str(e)}

    def _detect_layout_blocks(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """检测布局块"""
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
                "aspect_ratio": w / h if h > 0 else 0,
                "center": (x + w//2, y + h//2)
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
                return "text"
            elif aspect_ratio < 0.5:  # 很高的块
                return "title"
            elif width > 200 and height > 200:  # 大块
                return "figure"
            elif self._has_table_structure(block_image):
                return "table"
            else:
                return "text"

        except Exception:
            return "text"

    def _has_table_structure(self, image: np.ndarray) -> bool:
        """检测是否有表格结构"""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # 查找水平线和垂直线
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
            vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))

            horizontal_lines = cv2.morphologyEx(gray, cv2.MORPH_OPEN, horizontal_kernel)
            vertical_lines = cv2.morphologyEx(gray, cv2.MORPH_OPEN, vertical_kernel)

            # 合并线条
            table_lines = cv2.addWeighted(horizontal_lines, 1, vertical_lines, 1, 0)

            # 计算线条密度
            line_density = np.sum(table_lines > 0) / (image.shape[0] * image.shape[1])

            return line_density > 0.01  # 阈值

        except Exception:
            return False


class DeepTableStructureRecognizer:
    """深度表格结构识别器"""

    def __init__(self):
        self.available = True
        logger.info("深度表格结构识别器初始化成功")

    def recognize_table_structure(self, image: Image.Image, bbox: List[int]) -> Dict[str, Any]:
        """识别表格结构"""
        try:
            # 裁剪表格区域
            x1, y1, x2, y2 = bbox
            table_image = image.crop((x1, y1, x2, y2))

            # 转换为OpenCV格式
            table_cv = cv2.cvtColor(np.array(table_image), cv2.COLOR_RGB2BGR)

            # 识别表格结构
            structure = self._detect_table_structure(table_cv)

            return {
                "success": True,
                "structure": structure,
                "bbox": bbox
            }

        except Exception as e:
            logger.error(f"表格结构识别失败: {e}")
            return {"error": str(e)}

    def _detect_table_structure(self, image: np.ndarray) -> Dict[str, Any]:
        """检测表格结构"""
        try:
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

        except Exception as e:
            logger.error(f"表格结构检测失败: {e}")
            return {"error": str(e)}


class SemanticAnalyzer:
    """语义分析器"""

    def __init__(self):
        logger.info("语义分析器初始化成功")

    def analyze_document(self, content: str) -> Dict[str, Any]:
        """分析文档语义"""
        try:
            analysis = {
                "sections": [],
                "blocks": [],
                "keywords": [],
                "summary": "",
                "semantic_score": 0.0
            }

            # 分段分析
            sections = self._extract_sections(content)
            analysis["sections"] = sections

            # 语义块分析
            blocks = self._extract_semantic_blocks(content)
            analysis["blocks"] = blocks

            # 关键词提取
            keywords = self._extract_keywords(content)
            analysis["keywords"] = keywords

            # 生成摘要
            summary = self._generate_summary(content)
            analysis["summary"] = summary

            # 计算语义分数
            semantic_score = self._calculate_semantic_score(content)
            analysis["semantic_score"] = semantic_score

            return analysis

        except Exception as e:
            logger.error(f"语义分析失败: {e}")
            return {"error": str(e)}

    def _extract_sections(self, content: str) -> List[Dict[str, Any]]:
        """提取文档章节"""
        sections = []

        lines = content.split('\n')
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测标题
            if line.startswith('#') or (len(line) < 100 and line.isupper()):
                if current_section:
                    sections.append(current_section)

                current_section = {
                    "title": line,
                    "content": "",
                    "level": len(line) - len(line.lstrip('#')),
                    "type": "section"
                }
            elif current_section:
                current_section["content"] += line + "\n"

        if current_section:
            sections.append(current_section)

        return sections

    def _extract_semantic_blocks(self, content: str) -> List[Dict[str, Any]]:
        """提取语义块"""
        blocks = []

        # 按段落分割
        paragraphs = content.split('\n\n')

        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                continue

            # 分析段落类型
            block_type = self._analyze_block_type(para)

            blocks.append({
                "id": i,
                "content": para,
                "type": block_type,
                "length": len(para),
                "semantic_score": self._calculate_paragraph_score(para)
            })

        return blocks

    def _extract_keywords(self, content: str) -> List[str]:
        """提取关键词"""
        try:
            # 使用jieba分词
            words = jieba.lcut(content)

            # 过滤停用词和短词
            filtered_words = [word for word in words if len(word) > 1 and word not in ['的', '了', '在', '是', '有', '和', '与', '或']]

            # 统计词频
            word_freq = Counter(filtered_words)

            # 返回前10个高频词
            return [word for word, freq in word_freq.most_common(10)]

        except Exception:
            return []

    def _generate_summary(self, content: str) -> str:
        """生成文档摘要"""
        try:
            # 简化的摘要生成
            sentences = re.split(r'[。！？.!?]', content)
            sentences = [s.strip() for s in sentences if s.strip()]

            if len(sentences) <= 3:
                return content

            # 选择前3个句子作为摘要
            return "。".join(sentences[:3]) + "。"

        except Exception:
            return content[:200] + "..." if len(content) > 200 else content

    def _calculate_semantic_score(self, content: str) -> float:
        """计算语义分数"""
        try:
            # 基于多个特征计算语义分数
            features = {
                "length": min(len(content) / 1000, 1.0),  # 长度特征
                "diversity": len(set(content.split())) / len(content.split()) if content.split() else 0,  # 词汇多样性
                "structure": len(re.findall(r'[。！？.!?]', content)) / max(len(content.split()), 1),  # 句子结构
                "keywords": len(self._extract_keywords(content)) / 10  # 关键词密度
            }

            # 加权平均
            weights = [0.3, 0.3, 0.2, 0.2]
            score = sum(f * w for f, w in zip(features.values(), weights))

            return min(score, 1.0)

        except Exception:
            return 0.5

    def _analyze_block_type(self, text: str) -> str:
        """分析文本块类型"""
        if not text:
            return "empty"

        # 标题检测
        if text.startswith('#') or (len(text) < 100 and text.isupper()):
            return "header"

        # 列表检测
        if re.match(r'^[\s]*[•\-\*\d]+\.?\s', text):
            return "list"

        # 表格检测
        if '\t' in text or '|' in text:
            return "table"

        # 代码检测
        if text.startswith('```') or text.startswith('    '):
            return "code"

        # 长文本
        if len(text) > 500:
            return "paragraph"

        return "text"

    def _calculate_paragraph_score(self, paragraph: str) -> float:
        """计算段落语义分数"""
        try:
            # 简化的段落评分
            words = jieba.lcut(paragraph)
            unique_words = len(set(words))
            total_words = len(words)

            if total_words == 0:
                return 0.0

            diversity = unique_words / total_words
            length_score = min(len(paragraph) / 200, 1.0)

            return (diversity * 0.6 + length_score * 0.4)

        except Exception:
            return 0.5
