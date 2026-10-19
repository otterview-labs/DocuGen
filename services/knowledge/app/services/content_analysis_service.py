#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一内容分析服务 - 智能内容理解和标签生成

**核心功能**：
- 内容摘要：自动生成文档摘要
- 标签提取：智能提取关键标签
- 批量分析：支持多文档批量处理
- 结果缓存：避免重复分析

**分析能力**：
- 文本内容分析
- 文档结构理解
- 关键信息提取
- 主题识别

**主要方法**：
- analyze_content(): 分析单个文档内容
- batch_analyze(): 批量分析多个文档
- get_analysis_result(): 获取分析结果

**被使用位置**：
- app/api/v1/rag/endpoints/content_analysis.py: 内容分析API
- app/services/multimodal_upload_service.py: 文档上传后自动分析

**注意**：
- 使用占位符函数（Agent系统已删除）
- 当前返回基础信息，待集成LLM分析能力
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pathlib import Path
import asyncio

# from app.core.agents.system_agent import get_content_analysis_agent
# from app.services.hybrid_agent_service import HybridAgentManager

# 创建占位符
def get_content_analysis_agent():
    """占位符函数"""
    return None

class HybridAgentManager:
    """占位符类"""
    pass
from app.db.models.rag import RAGContent
from app.db.session import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ContentAnalysisService:
    """统一的内容分析服务"""

    def __init__(self):
        self.content_analysis_agent = get_content_analysis_agent()
        self.hybrid_agent_manager = HybridAgentManager()

    async def analyze_content_smart(self,
                                  content: Union[str, RAGContent],
                                  content_type: str,
                                  analysis_type: str = "both",
                                  use_multimodal: bool = True) -> Dict[str, Any]:
        """
        智能内容分析 - 支持文本、文档、视频的高质量分析

        Args:
            content: 文本内容或RAGContent对象
            content_type: 内容类型 (text, document, image, video)
            analysis_type: 分析类型 (summary, tags, both)
            use_multimodal: 是否使用多模态分析（视频/图片）

        Returns:
            分析结果字典
        """
        try:
            # 获取分析内容
            if isinstance(content, RAGContent):
                analysis_text = await self._extract_content_from_rag_object(content)
                file_path = content.file_path
            else:
                analysis_text = str(content)
                file_path = None

            if not analysis_text or len(analysis_text.strip()) < 10:
                return {
                    "success": False,
                    "error": "内容过短或为空，无法进行有效分析"
                }

            # 根据内容类型选择分析策略
            if content_type == "video" and use_multimodal and file_path:
                return await self._analyze_video_content_enhanced(file_path, analysis_text, analysis_type)
            elif content_type == "image" and use_multimodal and file_path:
                return await self._analyze_image_content_enhanced(file_path, analysis_text, analysis_type)
            else:
                return await self._analyze_text_content_enhanced(analysis_text, content_type, analysis_type)

        except Exception as e:
            logger.error(f"智能内容分析失败: {str(e)}")
            return {
                "success": False,
                "error": f"内容分析失败: {str(e)}"
            }

    async def _extract_content_from_rag_object(self, rag_content: RAGContent) -> str:
        """从RAGContent对象提取用于分析的文本内容"""
        content_parts = []

        # 优先使用已处理的文本内容
        if rag_content.content_text:
            content_parts.append(rag_content.content_text)

        # 如果没有处理过的文本，尝试从文件读取
        elif rag_content.file_path and os.path.exists(rag_content.file_path):
            try:
                file_content = await self._extract_text_from_file(
                    rag_content.file_path,
                    rag_content.file_name or ""
                )
                content_parts.append(file_content)
            except Exception as e:
                logger.warning(f"从文件提取内容失败: {e}")

        # 添加其他可用信息
        if rag_content.title:
            content_parts.insert(0, f"标题: {rag_content.title}")

        if rag_content.description:
            content_parts.append(f"描述: {rag_content.description}")

        return "\n".join(content_parts)

    async def _extract_text_from_file(self, file_path: str, file_name: str) -> str:
        """从文件中提取文本内容 - 增强版本"""
        file_ext = Path(file_name).suffix.lower()

        try:
            if file_ext == '.txt':
                # 支持多种编码的文本文件
                encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin1']
                for encoding in encodings:
                    try:
                        with open(file_path, 'r', encoding=encoding) as f:
                            return f.read()
                    except UnicodeDecodeError:
                        continue
                raise Exception("无法识别文件编码")

            elif file_ext == '.md':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()

            elif file_ext in ['.docx', '.doc']:
                try:
                    from docx import Document
                    doc = Document(file_path)
                    text_content = ""
                    for paragraph in doc.paragraphs:
                        text_content += paragraph.text + "\n"
                    return text_content
                except ImportError:
                    return f"Word文档: {file_name} (需要安装python-docx库)"
                except Exception as e:
                    return f"Word文档读取失败: {str(e)}"

            elif file_ext == '.pdf':
                try:
                    import pdfplumber
                    text_content = ""
                    with pdfplumber.open(file_path) as pdf:
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            if page_text:
                                text_content += page_text + "\n"
                    return text_content
                except ImportError:
                    try:
                        import PyPDF2
                        with open(file_path, 'rb') as f:
                            reader = PyPDF2.PdfReader(f)
                            text_content = ""
                            for page in reader.pages:
                                text_content += page.extract_text() + "\n"
                        return text_content
                    except ImportError:
                        return f"PDF文档: {file_name} (需要安装pdfplumber或PyPDF2库)"
                except Exception as e:
                    return f"PDF文档读取失败: {str(e)}"

            else:
                # 其他文件类型尝试作为文本读取
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        return f.read()
                except Exception:
                    return f"文档: {file_name} (文件类型: {file_ext})"

        except Exception as e:
            logger.error(f"文件读取失败 {file_path}: {e}")
            return f"文档: {file_name} (读取时发生错误: {str(e)})"

    async def _analyze_text_content_enhanced(self, content: str, content_type: str, analysis_type: str) -> Dict[str, Any]:
        """增强的文本内容分析 - 使用LLM模型进行智能分析"""
        try:
            import os
            import json

            # 限制内容长度，避免超过token限制
            content_text = content[:3000] if content else ""

            # 构建分析提示词
            prompt = f"""请对以下{content_type}内容进行专业分析，提取摘要、标签和关键点。

内容：
{content_text}

请按照以下JSON格式返回分析结果：
{{
    "summary": "简洁而准确的内容摘要，100-200字，概括主要内容和价值",
    "tags": ["标签1", "标签2", "标签3", "标签4", "标签5"],
    "key_points": ["关键点1", "关键点2", "关键点3"],
    "content_category": "技术文档/产品说明/教程指南/新闻资讯/其他"
}}

要求：
1. 摘要要准确反映文档的核心内容和主要价值
2. 标签要具体、专业、有意义，涵盖技术栈、领域、用途等
3. 关键点要提取最重要的3个信息点
4. 内容分类要准确
5. 只返回JSON，不要其他文字"""

            try:
                from app.shared.parsers.llm_enhanced_parser import LLMEnhancedParser

                llm_parser = LLMEnhancedParser()
                llm_result = await asyncio.to_thread(
                    llm_parser.call_llm_api,
                    prompt,
                    1200,  # max_tokens
                    0.2,   # temperature
                )

                if not llm_result.get("success") or not llm_result.get("content"):
                    logger.warning(f"LLM API调用失败: {llm_result.get('error', '未知错误')}")
                    return await self._fallback_to_content_analysis_agent(content, content_type, analysis_type)

                response_text = llm_result["content"]

                # 尝试解析JSON
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_text = json_match.group(0)
                    analysis_data = json.loads(json_text)

                    return {
                        "success": True,
                        "ai_summary": analysis_data.get("summary", ""),
                        "ai_tags": analysis_data.get("tags", [])[:8],  # 限制最多8个标签
                        "key_points": analysis_data.get("key_points", [])[:5],  # 限制最多5个关键点
                        "content_category": analysis_data.get("content_category", content_type),
                        "confidence": 0.9,
                        "analysis_method": "llm_enhanced"
                    }

                # 如果JSON解析失败，使用原始文本作为摘要
                return {
                    "success": True,
                    "ai_summary": response_text[:300],
                    "ai_tags": [content_type],
                    "key_points": [],
                    "content_category": content_type,
                    "confidence": 0.6,
                    "analysis_method": "llm_text_only"
                }

            except json.JSONDecodeError as e:
                logger.warning(f"JSON解析失败: {e}")
                # 降级到备用方案
                return await self._fallback_to_content_analysis_agent(content, content_type, analysis_type)
            except Exception as e:
                logger.error(f"LLM API调用异常: {e}")
                # 降级到备用方案
                return await self._fallback_to_content_analysis_agent(content, content_type, analysis_type)

        except Exception as e:
            logger.error(f"增强文本分析失败: {e}")
            return await self._fallback_to_content_analysis_agent(content, content_type, analysis_type)

    async def _fallback_to_content_analysis_agent(self, content: str, content_type: str, analysis_type: str) -> Dict[str, Any]:
        """备用方案：简单的内容分析"""
        try:
            # 简单的内容分析逻辑
            summary = ""
            tags = []

            if isinstance(content, str):
                # 提取前200个字符作为摘要
                content_text = content.strip()
                if content_text:
                    # 清理Markdown格式
                    import re
                    clean_text = re.sub(r'[#*`\[\]()]', '', content_text)
                    clean_text = re.sub(r'\n+', ' ', clean_text)
                    summary = clean_text[:200] + "..." if len(clean_text) > 200 else clean_text

                    # 根据内容类型生成标签
                    if content_type == "image":
                        tags = ["图片", "多模态内容"]
                    elif content_type == "video":
                        tags = ["视频", "多模态内容"]
                    elif content_type == "document":
                        tags = ["文档", "知识库"]
                    else:
                        tags = ["文本", "知识库"]

                    # 尝试从内容中提取更多标签
                    keywords = ["docker", "kubernetes", "api", "python", "java", "数据库", "配置", "部署"]
                    for keyword in keywords:
                        if keyword.lower() in content_text.lower():
                            tags.append(keyword)

                    tags = list(set(tags))[:5]  # 去重并限制最多5个标签

            return {
                "success": True,
                "ai_summary": summary or f"这是一个{content_type}类型的内容",
                "ai_tags": tags,
                "key_points": [],
                "content_category": content_type,
                "confidence": 0.5,
                "analysis_method": "simple_fallback"
            }

        except Exception as e:
            logger.error(f"备用分析方案失败: {e}")
            return {
                "success": False,
                "error": f"备用分析失败: {str(e)}"
            }

    async def _analyze_video_content_enhanced(self, file_path: str, markdown_content: str, analysis_type: str) -> Dict[str, Any]:
        """增强的视频内容分析 - 结合视觉和文本信息"""
        try:
            # 视频分析需要结合多模态信息
            video_prompt = f"""请分析这个视频内容，视频已经过多模态处理转换为Markdown格式：

Markdown内容：
{markdown_content[:6000]}  # 视频内容通常较长

请生成专业的视频内容分析：

{{
    "summary": "视频内容的完整摘要，包括主要场景、讲解内容、关键信息等",
    "tags": ["视频主题相关标签"],
    "key_points": ["视频中的关键知识点或重要信息"],
    "content_category": "视频类型分类（如：教育、娱乐、新闻等）",
    "video_features": {{
        "has_speech": true/false,
        "scene_count": "估计的场景数量",
        "duration_category": "short/medium/long"
    }},
    "confidence": 0.95
}}"""

            # 使用增强的智能体分析
            result = await self.hybrid_agent_manager.run_agent_async(
                agent_name="document_analyzer",
                user_input=video_prompt,
                context={"content_type": "video", "analysis_type": analysis_type, "file_path": file_path}
            )

            if result.get("success") and result.get("response"):
                try:
                    import re
                    response_text = result["response"]
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)

                    if json_match:
                        analysis_data = json.loads(json_match.group(0))

                        # 为视频添加特殊标签
                        tags = analysis_data.get("tags", [])
                        if "视频内容" not in tags:
                            tags.append("视频内容")
                        if "多模态分析" not in tags:
                            tags.append("多模态分析")

                        return {
                            "success": True,
                            "ai_summary": analysis_data.get("summary", ""),
                            "ai_tags": tags,
                            "key_points": analysis_data.get("key_points", []),
                            "content_category": analysis_data.get("content_category", "video"),
                            "video_features": analysis_data.get("video_features", {}),
                            "confidence": analysis_data.get("confidence", 0.8),
                            "analysis_method": "video_multimodal_enhanced"
                        }
                except Exception as e:
                    logger.warning(f"视频分析JSON解析失败: {e}")

            # 降级到文本分析
            return await self._analyze_text_content_enhanced(markdown_content, "video", analysis_type)

        except Exception as e:
            logger.error(f"视频内容分析失败: {e}")
            return {
                "success": False,
                "error": f"视频分析失败: {str(e)}"
            }

    async def _analyze_image_content_enhanced(self, file_path: str, content: str, analysis_type: str) -> Dict[str, Any]:
        """增强的图片内容分析"""
        try:
            # 图片分析暂时使用文本分析，未来可集成VLM
            result = await self._analyze_text_content_enhanced(content, "image", analysis_type)

            # 为图片添加特殊标签
            if result.get("success"):
                tags = result.get("ai_tags", [])
                if "图片内容" not in tags:
                    tags.append("图片内容")
                result["ai_tags"] = tags
                result["analysis_method"] = "image_text_enhanced"

            return result

        except Exception as e:
            logger.error(f"图片内容分析失败: {e}")
            return {
                "success": False,
                "error": f"图片分析失败: {str(e)}"
            }

    async def batch_analyze_contents(self, contents: List[Dict], analysis_type: str = "both") -> Dict[str, Any]:
        """批量内容分析"""
        results = []

        for item in contents:
            try:
                content_id = item.get("id")
                content_text = item.get("content", "")
                content_type = item.get("content_type", "text")

                # 使用智能分析
                analysis_result = await self.analyze_content_smart(
                    content=content_text,
                    content_type=content_type,
                    analysis_type=analysis_type,
                    use_multimodal=True
                )

                if analysis_result.get("success"):
                    results.append({
                        "item_id": content_id,
                        "success": True,
                        "data": {
                            "summary": analysis_result.get("ai_summary"),
                            "tags": analysis_result.get("ai_tags", []),
                            "key_points": analysis_result.get("key_points", []),
                            "content_category": analysis_result.get("content_category"),
                            "confidence": analysis_result.get("confidence", 0.8)
                        }
                    })
                else:
                    results.append({
                        "item_id": content_id,
                        "success": False,
                        "error": analysis_result.get("error", "分析失败")
                    })

                # 避免过快请求
                await asyncio.sleep(0.1)

            except Exception as e:
                results.append({
                    "item_id": item.get("id"),
                    "success": False,
                    "error": f"批量分析项目失败: {str(e)}"
                })

        success_count = len([r for r in results if r["success"]])

        return {
            "success": True,
            "results": results,
            "total": len(contents),
            "success_count": success_count,
            "failed_count": len(results) - success_count
        }


# 单例实例
_content_analysis_service = None

def get_content_analysis_service() -> ContentAnalysisService:
    """获取内容分析服务的单例实例"""
    global _content_analysis_service

    if _content_analysis_service is None:
        _content_analysis_service = ContentAnalysisService()

    return _content_analysis_service
