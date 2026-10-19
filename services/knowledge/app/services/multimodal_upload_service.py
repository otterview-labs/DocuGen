#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多模态内容上传处理服务

**核心功能**：
- 多格式支持：视频、文档、图片的统一处理
- Markdown转换：自动生成标准化Markdown格式
- 进度追踪：实时反馈处理进度
- 知识图谱：自动构建实体和关系

**支持的文件类型**：
- 视频：.mp4, .avi, .mov, .mkv, .webm (≤200MB, ≤2小时)
- 文档：.pdf, .docx, .txt, .md (≤50MB)
- 图片：.jpg, .jpeg, .png, .gif, .webp (≤10MB)

**处理流程**：
1. 文件上传和验证
2. 格式识别和转换
3. Markdown生成
4. 向量化存储
5. 知识图谱构建（可选）

**被使用位置**：
- app/api/v1/rag/endpoints/multimodal_upload.py: 多模态上传API
- app/api/v1/rag/endpoints/resource_parse.py: 资源解析API
- app/api/v1/rag/endpoints/document_progress.py: 进度查询API
"""

import os
import uuid
import json
import asyncio
import functools
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import IntegrityError

from app.services.processing_progress_manager import ProcessingProgressManager, ProcessingStage
from app.config import settings
from app.shared.audio_processor.media_processor import is_video_processable
from app.db.models.rag import RAGContent
from app.shared.response_models import ResponseHelper
from app.services.content_analysis_service import get_content_analysis_service
from app.shared.utils.file_detector import file_detector
from app.shared.utils.logger_util import get_logger
from app.shared.utils.visual_regions import load_image_size, normalize_external_visual_regions

logger = get_logger("MultimodalUploadService")


def get_metadata_dict(rag_content) -> Dict[str, Any]:
    """
    安全地获取content_metadata字典
    兼容旧数据（JSON字符串）和新数据（字典）
    """
    if not rag_content.content_metadata:
        return {}

    # 如果已经是字典，直接返回
    if isinstance(rag_content.content_metadata, dict):
        return rag_content.content_metadata

    # 如果是字符串，尝试解析（兼容旧数据）
    if isinstance(rag_content.content_metadata, str):
        try:
            parsed = json.loads(rag_content.content_metadata)
            # 双重编码的情况：解析后仍是字符串
            if isinstance(parsed, str):
                return json.loads(parsed)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"无法解析content_metadata: {rag_content.id}")
            return {}

    return {}


class MultimodalUploadService:
    """多模态上传处理服务"""

    def __init__(self):
        self._converter = None
        self.upload_base_dir = Path("storage/static/uploads").resolve()
        self.upload_base_dir.mkdir(parents=True, exist_ok=True)
        self.content_analysis_service = get_content_analysis_service()

        # 支持的文件类型配置
        self.supported_types = {
            "video": {
                "mime_types": ["video/mp4", "video/avi", "video/mov", "video/mkv", "video/webm"],
                "extensions": [".mp4", ".avi", ".mov", ".mkv", ".webm"],
                "max_size": 200 * 1024 * 1024,  # 200MB
                "max_duration": 7200  # 2小时
            },
            "document": {
                "mime_types": ["application/pdf", "text/plain", "text/markdown",
                              "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
                "extensions": [".pdf", ".txt", ".md", ".docx"],
                "max_size": 50 * 1024 * 1024   # 50MB
            },
            "image": {
                "mime_types": ["image/jpeg", "image/png", "image/gif", "image/webp"],
                "extensions": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
                "max_size": 10 * 1024 * 1024    # 10MB
            }
        }

    @property
    def converter(self):
        """按需初始化转换器，避免可选解析依赖影响服务启动。"""
        if self._converter is None:
            from app.shared.parsers.unified_markdown_converter import UnifiedMarkdownConverter

            self._converter = UnifiedMarkdownConverter()
        return self._converter

    def validate_file(self, file_path: str, content_type: str) -> Dict[str, Any]:
        """
        验证上传文件 - 使用统一的文件类型检测器

        Returns:
            验证结果
        """
        try:
            # 使用统一的文件类型检测器
            result = file_detector.validate_file(file_path, content_type)

            # 检查ResponseHelper格式的返回结果
            if result.get('status') != 200 or result.get('message') != 'success':
                return {
                    "valid": False,
                    "error": result.get('message', '文件验证失败')
                }

            # 提取文件数据
            file_data = result.get('result', {})
            file_type = file_data.get('type')

            # 额外验证视频文件
            if file_type == 'video':
                processable, message = is_video_processable(
                    str(file_path), self.supported_types["video"]["max_duration"]
                )
                if not processable:
                    return {
                        "valid": False,
                        "error": message
                    }

            # 返回验证成功结果
            return {
                "valid": True,
                "type": file_type,
                "extension": file_data.get('extension'),
                "size": file_data.get('size'),
                "mime_type": file_data.get('mime_type'),
                "file_hash": file_data.get('file_hash')
            }

        except Exception as e:
            logger.error(f"文件验证失败: {str(e)}")
            return {
                "valid": False,
                "error": f"文件验证异常: {str(e)}"
            }

    async def process_uploaded_file_with_progress(self, file_path: str, content_type: str,
                                   user_id: str, db: Session, title: Optional[str] = None,
                                   collection_id: Optional[str] = None,
                                   parse_options: Optional[Dict[str, Any]] = None,
                                   resource_id: Optional[str] = None) -> Dict[str, Any]:
        """
        带详细进度跟踪的文件处理方法

        Args:
            file_path: 文件路径
            content_type: MIME类型
            user_id: 用户ID
            db: 数据库会话
            title: 自定义标题
            collection_id: 可选的集合ID

        Returns:
            处理结果
        """
        # 1. 生成内容ID并创建进度管理器
        content_id = str(uuid.uuid4())
        progress_manager = ProcessingProgressManager(content_id, db)
        logger.info(f"[Upload] 开始处理文件: content_id={content_id}, path={file_path}, content_type={content_type}, title={title}")

        # 确保集合ID不为空，使用default作为默认值
        final_collection_id = collection_id or "default"

        # 确保default集合存在
        if final_collection_id == "default":
            from app.db.models.rag import RAGCollection
            default_collection = db.query(RAGCollection).filter(RAGCollection.name == "default").first()
            if not default_collection:
                # 创建default集合
                default_collection_data = {
                    "id": "default",
                    "name": "default",
                    "description": "默认知识库集合，用于存储未指定集合的文档",
                    "user_id": user_id,
                    "collection_type": "standard",
                    "create_time": datetime.now(),
                    "update_time": datetime.now()
                }
                default_collection = RAGCollection(**default_collection_data)
                db.add(default_collection)
                db.commit()
                logger.info("创建default集合成功")

        # 首先在数据库中创建记录
        initial_content_data = {
            "id": content_id,
            "resource_id": resource_id or content_id,  # 使用content_id作为默认resource_id
            "user_id": user_id,
            "content_type": "document",  # 临时设置，后续会更新
            "title": title or Path(file_path).stem,
            "description": "正在处理中...",
            "file_path": file_path,
            "file_name": Path(file_path).name,
            "processing_status": "processing",
            "processing_message": "开始处理",
            "vector_collection": final_collection_id,  # 确保使用默认集合
            "create_time": datetime.now(),
            "update_time": datetime.now()
        }

        # 创建或更新数据库记录（upsert逻辑）
        existing_content = db.query(RAGContent).filter(
            RAGContent.resource_id == resource_id
        ).first()

        if existing_content:
            # 更新现有记录
            for key, value in initial_content_data.items():
                if key != 'id':  # 不更新主键
                    setattr(existing_content, key, value)
            rag_content = existing_content
            logger.info(f"更新现有记录: {resource_id}")
        else:
            # 创建新记录
            rag_content = RAGContent(**initial_content_data)
            db.add(rag_content)
            logger.info(f"创建新记录: {resource_id}")
        # 提交（并发安全：处理唯一键冲突后回退为更新）
        try:
            db.commit()
            db.refresh(rag_content)
        except IntegrityError as ie:
            db.rollback()
            logger.warning(
                f"[Upload] 捕获唯一键冲突(resource_id={resource_id})，尝试转为更新: {ie}"
            )
            # 可能存在并发插入，转为更新已有记录
            concurrent_existing = db.query(RAGContent).filter(
                RAGContent.resource_id == resource_id
            ).first()
            if concurrent_existing:
                for key, value in initial_content_data.items():
                    if key != 'id':
                        setattr(concurrent_existing, key, value)
                rag_content = concurrent_existing
                db.commit()
                db.refresh(rag_content)
            else:
                # 未找到则抛出原异常
                raise

        try:
            # 2. 开始上传阶段
            progress_manager.start_stage(ProcessingStage.UPLOAD, "开始处理文件上传")
            progress_manager.update_stage_progress(ProcessingStage.UPLOAD, 50, "文件已接收")
            progress_manager.complete_stage(ProcessingStage.UPLOAD, "文件上传完成")

            # 3. 文件验证阶段
            progress_manager.start_stage(ProcessingStage.VALIDATION, "验证文件格式和大小")
            validation = self.validate_file(file_path, content_type)
            logger.info(f"[Upload] 文件验证结果: valid={validation.get('valid')}, type={validation.get('type')}, size={validation.get('size')}, mime={validation.get('mime_type')}")
            if not validation["valid"]:
                progress_manager.fail_stage(ProcessingStage.VALIDATION, validation["error"])
                logger.error(f"[Upload] 文件验证失败: {validation.get('error')}")
                return {"success": False, "error": validation["error"], "content_id": content_id}

            file_type = validation["type"]
            file_name = Path(file_path).name
            title = title or Path(file_path).stem

            progress_manager.complete_stage(ProcessingStage.VALIDATION, f"验证完成，文件类型: {file_type}")

            # 4. Markdown转换阶段
            progress_manager.start_stage(ProcessingStage.MARKDOWN_CONVERSION, f"开始{file_type}内容转换")
            logger.info(f"[Upload] 进入Markdown转换阶段: file_type={file_type}, name={file_name}, title={title}")

            # 创建处理目录
            process_id = uuid.uuid4().hex[:12]
            output_dir = os.path.join(self.upload_base_dir, "processed", process_id)
            os.makedirs(output_dir, exist_ok=True)

            # 根据文件类型进行处理
            markdown_result = None

            # 解析多模态/文本分块配置
            parse_options = parse_options or {}
            multimodal_cfg = (parse_options.get('multimodal') if isinstance(parse_options, dict) else None) or {}
            text_cfg = (parse_options.get('text') if isinstance(parse_options, dict) else None) or {}
            # 记录文本分块策略（仅写入metadata，实际切分在向量化阶段生效）。默认采用 markdown 章节分块
            raw_strategy = str(text_cfg.get('strategy', '')).strip() if isinstance(text_cfg, dict) else ''
            # 兼容别名
            alias_map = {
                'fixed-size-chunking': 'fixed_size',
                'semantic-chunking': 'semantic',
                'chapter-chunking': 'markdown',
            }
            text_strategy = alias_map.get(raw_strategy.lower(), raw_strategy.lower()) if raw_strategy else 'markdown'
            # 根据模式控制是否启用音频（fast/basic 关闭音频，以提高速度）
            mode = str(multimodal_cfg.get('mode', 'intelligent')).lower()
            enable_audio_flag = multimodal_cfg.get('enable_audio')
            if enable_audio_flag is None:
                enable_audio_flag = False if mode in ("fast", "basic") else True
            # 动态调整关键帧间隔
            try:
                kfi = float(multimodal_cfg.get('keyframe_interval')) if multimodal_cfg.get('keyframe_interval') is not None else None
                if kfi and kfi > 0:
                    self.converter.config['video']['keyframe_interval'] = kfi
            except Exception:
                pass

            if file_type == "video":
                progress_manager.update_stage_progress(ProcessingStage.MARKDOWN_CONVERSION, 25, "解析视频信息")
                markdown_result = await self._process_video_async(file_path, output_dir, title, enable_audio_flag)
            elif file_type == "document":
                progress_manager.update_stage_progress(ProcessingStage.MARKDOWN_CONVERSION, 25, "提取文档内容")
                # 在异步上下文中处理同步方法
                loop = asyncio.get_event_loop()
                # 使用functools.partial来正确传递关键字参数
                markdown_result = await loop.run_in_executor(
                    None,
                    functools.partial(self.converter.convert_document_to_markdown, title=title),
                    file_path
                )
            elif file_type == "image":
                progress_manager.update_stage_progress(ProcessingStage.MARKDOWN_CONVERSION, 25, "分析图像内容")
                # 在异步上下文中处理同步方法
                loop = asyncio.get_event_loop()
                # 使用functools.partial来正确传递关键字参数
                markdown_result = await loop.run_in_executor(
                    None,
                    functools.partial(self.converter.convert_image_to_markdown, title=title),
                    file_path
                )
            elif file_type == "audio":
                progress_manager.update_stage_progress(ProcessingStage.MARKDOWN_CONVERSION, 25, "处理音频文件")
                # 音频文件处理：转录为文本
                loop = asyncio.get_event_loop()
                markdown_result = await loop.run_in_executor(
                    None,
                    functools.partial(self.converter.convert_audio_to_markdown, title=title),
                    file_path
                )
            else:
                logger.warning(f"[Upload] 未识别的文件类型，按文档处理: file_type={file_type}")
                loop = asyncio.get_event_loop()
                markdown_result = await loop.run_in_executor(
                    None,
                    functools.partial(self.converter.convert_document_to_markdown, title=title),
                    file_path
                )

            if not markdown_result or not markdown_result.get('success'):
                error_msg = markdown_result.get('error') if markdown_result else '转换失败'
                progress_manager.fail_stage(ProcessingStage.MARKDOWN_CONVERSION, f"内容转换失败: {error_msg}")
                logger.error(f"[Upload] Markdown转换失败: content_id={content_id}, error={error_msg}")
                return {"success": False, "error": f"内容处理失败: {error_msg}", "content_id": content_id}

            # 如果图像VLM阶段出现降级/错误，将关键信息写入进度 details，便于状态接口展示
            try:
                md_meta = markdown_result.get("metadata", {}) or {}
                md_details = {}
                if isinstance(md_meta, dict):
                    if md_meta.get("vlm_error"):
                        md_details["vlm_error"] = md_meta.get("vlm_error")
                    if md_meta.get("fallback") is True:
                        md_details["vlm_fallback"] = True
                    if md_meta.get("vlm_events_count") is not None:
                        md_details["vlm_events_count"] = md_meta.get("vlm_events_count")
                    # 提供简短描述预览（避免过长）
                    if isinstance(md_meta.get("description"), str) and md_meta.get("description"):
                        md_details["vlm_description_preview"] = md_meta["description"][:160]
                if md_details:
                    progress_manager.update_stage_progress(
                        ProcessingStage.MARKDOWN_CONVERSION,
                        60,
                        "内容转换完成（含VLM诊断）",
                        details=md_details
                    )
                else:
                    progress_manager.update_stage_progress(ProcessingStage.MARKDOWN_CONVERSION, 75, "内容转换完成")
            except Exception:
                progress_manager.update_stage_progress(ProcessingStage.MARKDOWN_CONVERSION, 75, "内容转换完成")
            content_text = markdown_result["markdown_content"]
            # 将诊断信息一并写入完成阶段 details（若有）
            try:
                md_meta = markdown_result.get("metadata", {}) or {}
                md_details_final = {}
                if isinstance(md_meta, dict):
                    if md_meta.get("vlm_error"):
                        md_details_final["vlm_error"] = md_meta.get("vlm_error")
                    if md_meta.get("vlm_events_count") is not None:
                        md_details_final["vlm_events_count"] = md_meta.get("vlm_events_count")
                progress_manager.complete_stage(
                    ProcessingStage.MARKDOWN_CONVERSION,
                    f"成功转换为Markdown，内容长度: {len(content_text)}字符",
                    details=md_details_final if md_details_final else None
                )
            except Exception:
                progress_manager.complete_stage(
                    ProcessingStage.MARKDOWN_CONVERSION,
                    f"成功转换为Markdown，内容长度: {len(content_text)}字符"
                )
            logger.info(f"[Upload] Markdown转换完成: content_id={content_id}, md_len={len(content_text)}, meta_keys={list(markdown_result.get('metadata',{}).keys())}, fallback={markdown_result.get('metadata',{}).get('fallback', False)}")

            # ⚠️ 检查 content_text 是否为空
            if not content_text or len(content_text.strip()) == 0:
                logger.error(f"❌ [Upload] content_text 为空！content_id={content_id}, file_path={file_path}, file_type={file_type}")
                logger.error(f"❌ [Upload] markdown_result keys: {list(markdown_result.keys())}")
                logger.error(f"❌ [Upload] markdown_content value: {repr(markdown_result.get('markdown_content')[:200] if markdown_result.get('markdown_content') else None)}")
                logger.warning(f"⚠️ [Upload] 将继续处理，但数据库中的 content_text 将为空！")

            # 5. AI智能分析阶段
            progress_manager.start_stage(ProcessingStage.AI_ANALYSIS, "开始AI摘要和标签分析")

            try:
                ai_analysis = await self.content_analysis_service.analyze_content_smart(
                    content=content_text,
                    content_type=file_type,
                    analysis_type="both",
                    use_multimodal=True
                )

                progress_manager.update_stage_progress(ProcessingStage.AI_ANALYSIS, 50, "AI分析中...")

                # 处理分析结果
                if ai_analysis.get("success") and ai_analysis.get("ai_summary"):
                    content_summary = ai_analysis["ai_summary"]
                    # 直接List存储标签
                    content_tags = [t for t in ai_analysis.get("ai_tags", []) if isinstance(t, str) and t.strip()]

                    ai_metadata = {
                        "ai_analysis": {
                            "key_points": ai_analysis.get("key_points", []),
                            "content_category": ai_analysis.get("content_category", ""),
                            "analysis_confidence": ai_analysis.get("confidence", 0.8),
                            "analysis_method": ai_analysis.get("analysis_method", "enhanced_service"),
                            "analysis_timestamp": datetime.now().isoformat()
                        }
                    }
                    progress_manager.complete_stage(ProcessingStage.AI_ANALYSIS, f"AI分析完成，生成摘要和{len(ai_analysis.get('ai_tags', []))}个标签")
                    logger.info(f"[Upload] AI分析完成: content_id={content_id}, method={ai_metadata['ai_analysis'].get('analysis_method')}, tags={len(content_tags)}")
                else:
                    # 降级到基础摘要
                    content_summary = self._generate_content_summary(markdown_result)
                    content_tags = [file_type, "多模态内容"]
                    ai_metadata = {"enhanced_analysis_failed": ai_analysis.get("error", "未知原因")}
                    progress_manager.complete_stage(ProcessingStage.AI_ANALYSIS, "使用基础分析完成摘要生成")
                    logger.warning(f"[Upload] AI分析降级: content_id={content_id}, reason={ai_analysis.get('error')}")

            except Exception as e:
                content_summary = self._generate_content_summary(markdown_result)
                content_tags = [file_type, "多模态内容"]
                ai_metadata = {"analysis_error": str(e)}
                progress_manager.fail_stage(ProcessingStage.AI_ANALYSIS, f"AI分析失败: {str(e)}")
                logger.exception(f"[Upload] AI分析异常: content_id={content_id}")

            # 6. RAG存储阶段
            progress_manager.start_stage(ProcessingStage.RAG_STORAGE, "准备存储到知识库")

            normalized_visual_regions = []
            visual_cfg = (parse_options.get('visual') if isinstance(parse_options, dict) else None) or {}
            visual_metadata: Dict[str, Any] = {}
            if file_type == "image" and isinstance(visual_cfg, dict):
                try:
                    width, height = load_image_size(file_path)
                    normalized_visual_regions = normalize_external_visual_regions(
                        visual_cfg.get("regions"),
                        width=width,
                        height=height,
                        default_source_system=visual_cfg.get("source_system"),
                    )
                    visual_metadata = {
                        "mode": "external_regions" if normalized_visual_regions else "full_image_only",
                        "source_system": visual_cfg.get("source_system"),
                        "regions": normalized_visual_regions,
                        "image_width": width,
                        "image_height": height,
                    }
                except Exception as visual_error:
                    logger.warning(f"视觉 region 预处理失败，已忽略: {visual_error}")
                    visual_metadata = {
                        "mode": "full_image_only",
                        "region_error": str(visual_error),
                    }

            # 更新完整的文档数据
            content_data = {
                "content_type": file_type,
                "title": title,
                "description": f"通过多模态转换器处理的{file_type}内容",
                "file_name": file_name,
                "file_size": validation["size"],
                "mime_type": content_type,
                "content_text": content_text,
                "content_summary": content_summary,
                "content_tags": content_tags,
                "content_metadata": {
                    "processing_method": "unified_markdown_converter",
                    "file_type": file_type,
                    "process_id": process_id,
                    "processing_time": datetime.now().isoformat(),
                    # 记录解析配置，供后续向量分片等使用
                    "chunking": {
                        # 根据策略提供更合理的默认值（markdown 默认更小的块）
                        "size": int(text_cfg.get('chunk_size', 600 if text_strategy == 'markdown' else 800)) if isinstance(text_cfg.get('chunk_size', 0), (int, float)) and text_cfg.get('chunk_size') else (600 if text_strategy == 'markdown' else 800),
                        "overlap": int(text_cfg.get('overlap', 80 if text_strategy == 'markdown' else 100)) if isinstance(text_cfg.get('overlap', 0), (int, float)) and text_cfg.get('overlap') else (80 if text_strategy == 'markdown' else 100),
                        "min_size": int(text_cfg.get('min_size', 120)) if isinstance(text_cfg.get('min_size', 0), (int, float)) and text_cfg.get('min_size') else 120,
                        "strategy": text_strategy or "markdown",
                        # 透传/设定 markdown 分块参数（split_level 默认2，fallback 默认 sentence）
                        **({"split_level": int(text_cfg.get('split_level'))} if str(text_cfg.get('split_level', '')).isdigit() else ({"split_level": 2} if text_strategy == 'markdown' else {})),
                        **({"fallback_strategy": str(text_cfg.get('fallback_strategy')).strip()} if isinstance(text_cfg.get('fallback_strategy'), str) and str(text_cfg.get('fallback_strategy')).strip() else ({"fallback_strategy": "sentence"} if text_strategy == 'markdown' else {}))
                    },
                    "multimodal_mode": mode,
                    **({"visual": visual_metadata} if visual_metadata else {}),
                    **markdown_result.get("metadata", {}),
                    **ai_metadata
                },
                "processing_status": "processing",
                "processing_message": "正在存储到知识库",
                "update_time": datetime.now()
            }

            # 更新数据库记录
            for key, value in content_data.items():
                setattr(rag_content, key, value)

            progress_manager.update_stage_progress(ProcessingStage.RAG_STORAGE, 50, "数据已更新到数据库")

            # 向量化存储逻辑
            try:
                from app.services.enhanced_rag_service import EnhancedRAGService
                rag_service = EnhancedRAGService()

                progress_manager.update_stage_progress(ProcessingStage.RAG_STORAGE, 60, "开始向量化处理...")

                # 提交数据库变更以确保RAGContent记录存在
                db.commit()
                db.refresh(rag_content)

                # 添加到向量数据库
                vector_success = await rag_service.add_document_to_vector_db(rag_content, db)

                if vector_success:
                    progress_manager.update_stage_progress(ProcessingStage.RAG_STORAGE, 85, "向量化存储成功")
                    # 更新处理元数据
                    metadata = get_metadata_dict(rag_content)
                    metadata["vector_storage"] = {
                        "status": "completed",
                        "timestamp": datetime.now().isoformat(),
                        "vector_db_type": "enhanced_rag_service"
                    }
                    rag_content.content_metadata = metadata
                    logger.info(f"文档 {rag_content.resource_id} 向量化存储成功")
                else:
                    progress_manager.update_stage_progress(ProcessingStage.RAG_STORAGE, 75, "向量化存储失败，使用基础存储")
                    # 更新处理元数据（失败情况）
                    metadata = get_metadata_dict(rag_content)
                    metadata["vector_storage"] = {
                        "status": "failed",
                        "timestamp": datetime.now().isoformat(),
                        "error": "向量化存储失败，但基础数据已保存"
                    }
                    rag_content.content_metadata = metadata
                    logger.warning(f"文档 {rag_content.resource_id} 向量化存储失败，但基础数据已保存")

            except Exception as vector_error:
                logger.error(f"向量化存储异常: {str(vector_error)}")
                progress_manager.update_stage_progress(ProcessingStage.RAG_STORAGE, 75, f"向量化异常: {str(vector_error)}")

                # 更新处理元数据（异常情况）
                metadata = get_metadata_dict(rag_content)
                metadata["vector_storage"] = {
                    "status": "error",
                    "timestamp": datetime.now().isoformat(),
                    "error": str(vector_error)
                }
                rag_content.content_metadata = metadata

            progress_manager.complete_stage(ProcessingStage.RAG_STORAGE, "成功存储到知识库")

            # 7. 知识图谱构建（默认开启，可配置）
            progress_manager.start_stage(ProcessingStage.KNOWLEDGE_GRAPH, "检查知识图谱构建需求")
            try:
                from app.core.kg.manager import KnowledgeGraphManager
                kg_namespace = (getattr(settings.graph_db, "GRAPH_NAMESPACE", None) or "default").strip() or "default"
                kg_manager = KnowledgeGraphManager(namespace=kg_namespace)

                # 1) 流水线开关判断
                if not settings.kg_pipeline.ENABLED:
                    metadata = get_metadata_dict(rag_content)
                    metadata["knowledge_graph"] = {
                        "status": "skipped",
                        "timestamp": datetime.now().isoformat(),
                        "reason": "KG已在配置中禁用"
                    }
                    rag_content.content_metadata = metadata
                    progress_manager.skip_stage(ProcessingStage.KNOWLEDGE_GRAPH, "配置禁用，跳过知识图谱构建")
                # 2) 文本可用性与长度阈值
                elif not content_text or not str(content_text).strip():
                    metadata = get_metadata_dict(rag_content)
                    metadata["knowledge_graph"] = {
                        "status": "skipped",
                        "timestamp": datetime.now().isoformat(),
                        "reason": "内容为空，跳过知识图谱构建"
                    }
                    rag_content.content_metadata = metadata
                    progress_manager.skip_stage(ProcessingStage.KNOWLEDGE_GRAPH, "内容为空，跳过知识图谱构建")
                elif len(content_text) < int(settings.kg_pipeline.MIN_TEXT_LENGTH or 0):
                    metadata = get_metadata_dict(rag_content)
                    metadata["knowledge_graph"] = {
                        "status": "skipped",
                        "timestamp": datetime.now().isoformat(),
                        "reason": f"内容过短(<{settings.kg_pipeline.MIN_TEXT_LENGTH})，跳过知识图谱构建"
                    }
                    rag_content.content_metadata = metadata
                    progress_manager.skip_stage(ProcessingStage.KNOWLEDGE_GRAPH, "内容过短，跳过知识图谱构建")
                elif kg_manager.is_enabled():
                    progress_manager.update_stage_progress(ProcessingStage.KNOWLEDGE_GRAPH, 25, "分析文档结构")
                    progress_manager.update_stage_progress(ProcessingStage.KNOWLEDGE_GRAPH, 40, "开始实体关系抽取")

                    # 构建知识图谱并写入 doc->entity（用于跨文档检索/扩展）
                    kg_result = await kg_manager.add_document_to_graph(
                        doc_id=content_id,
                        content=content_text,
                        metadata={
                            "vector_collection": final_collection_id,
                            "resource_id": getattr(rag_content, "resource_id", None),
                            "resource_type": getattr(rag_content, "resource_type", None),
                            "file_name": getattr(rag_content, "file_name", None),
                            "content_type": getattr(rag_content, "content_type", None),
                            "user_id": getattr(rag_content, "user_id", None),
                        },
                    )

                    progress_manager.update_stage_progress(ProcessingStage.KNOWLEDGE_GRAPH, 75, "构建实体关系")

                    graph_result = (kg_result or {}).get("graph_result") if isinstance(kg_result, dict) else None
                    if graph_result and not graph_result.get("error"):
                        metadata = get_metadata_dict(rag_content)
                        metadata["knowledge_graph"] = {
                            "status": "completed",
                            "timestamp": datetime.now().isoformat(),
                            "node_count": graph_result.get("node_count", 0),
                            "edge_count": graph_result.get("edge_count", 0),
                            "kg_namespace": kg_namespace,
                            "graph_db_type": (getattr(settings.graph_db, "GRAPH_DB_TYPE", "") or "").lower() or "postgres",
                        }
                        rag_content.content_metadata = metadata
                        flag_modified(rag_content, 'content_metadata')
                        progress_manager.complete_stage(ProcessingStage.KNOWLEDGE_GRAPH, f"知识图谱构建完成 - 节点:{graph_result.get('node_count', 0)}, 边:{graph_result.get('edge_count', 0)}")
                        logger.info(f"内容 {content_id} 知识图谱构建成功: {graph_result.get('node_count', 0)}个节点, {graph_result.get('edge_count', 0)}条边")
                    else:
                        error_msg = "构建结果为空"
                        if isinstance(kg_result, dict):
                            error_msg = kg_result.get("error") or (graph_result or {}).get("error") or error_msg
                        metadata = get_metadata_dict(rag_content)
                        metadata["knowledge_graph"] = {
                            "status": "failed",
                            "timestamp": datetime.now().isoformat(),
                            "error": error_msg
                        }
                        rag_content.content_metadata = metadata
                        flag_modified(rag_content, 'content_metadata')
                        progress_manager.fail_stage(ProcessingStage.KNOWLEDGE_GRAPH, f"知识图谱构建失败: {error_msg}")
                        logger.warning(f"内容 {content_id} 知识图谱构建失败: {error_msg}")
                else:
                    # 图存储未配置，跳过
                    metadata = get_metadata_dict(rag_content)
                    metadata["knowledge_graph"] = {
                        "status": "skipped",
                        "timestamp": datetime.now().isoformat(),
                        "reason": "知识图谱未启用/未配置"
                    }
                    rag_content.content_metadata = metadata
                    flag_modified(rag_content, 'content_metadata')
                    progress_manager.skip_stage(ProcessingStage.KNOWLEDGE_GRAPH, "知识图谱未启用/未配置，跳过知识图谱构建")
                    logger.info(f"内容 {content_id} 跳过知识图谱构建: 知识图谱未启用/未配置")
            except Exception as kg_error:
                logger.error(f"知识图谱构建异常: {str(kg_error)}")

                # 更新处理元数据（异常情况）
                metadata = get_metadata_dict(rag_content)
                metadata["knowledge_graph"] = {
                    "status": "error",
                    "timestamp": datetime.now().isoformat(),
                    "error": str(kg_error)
                }
                rag_content.content_metadata = metadata
                flag_modified(rag_content, 'content_metadata')

                progress_manager.fail_stage(ProcessingStage.KNOWLEDGE_GRAPH, f"知识图谱构建异常: {str(kg_error)}")

            # 8. 最终完成阶段
            progress_manager.start_stage(ProcessingStage.FINALIZATION, "整理最终结果")

            # 🔧 创建集合关联关系（RAGCollectionContent）
            try:
                from app.db.models.rag import RAGCollection, RAGCollectionContent

                # ✅ 关键修复：先验证 content_id 是否真实存在（防止外键约束错误）
                # 刷新会话，确保能看到最新的数据库状态
                db.flush()
                content_exists = db.query(RAGContent).filter(RAGContent.id == content_id).first()

                if not content_exists:
                    logger.error(f"❌ 无法创建集合关联: content_id={content_id} 在rag_contents表中不存在")
                    logger.error(f"   可能原因：1) 之前的事务已回滚 2) content_id生成错误")
                    # 不抛出异常，只记录警告，让流程继续
                    logger.warning(f"⚠️  跳过集合关联创建，继续完成其他流程")
                else:
                    # 检查集合是否存在
                    collection = db.query(RAGCollection).filter(RAGCollection.id == final_collection_id).first()
                    if collection:
                        # 检查关联关系是否已存在
                        existing_relation = db.query(RAGCollectionContent).filter(
                            RAGCollectionContent.collection_id == final_collection_id,
                            RAGCollectionContent.content_id == content_id
                        ).first()

                        if not existing_relation:
                            # 创建新的关联关系
                            collection_content = RAGCollectionContent(
                                id=str(uuid.uuid4()),
                                collection_id=final_collection_id,
                                content_id=content_id,
                                weight=1.0,
                                create_time=datetime.now()
                            )
                            db.add(collection_content)
                            db.commit()  # 立即提交集合关联
                            logger.info(f"✅ 创建集合关联成功: collection={final_collection_id}, content={content_id}")
                        else:
                            logger.debug(f"集合关联已存在: collection={final_collection_id}, content={content_id}")
                    else:
                        logger.warning(f"集合不存在，无法创建关联: collection_id={final_collection_id}")

            except Exception as relation_error:
                logger.error(f"❌ 创建集合关联失败: {relation_error}")
                logger.exception("详细错误信息：")
                # 仅记录错误，不阻塞主流程（因为这不是核心功能）

            # 更新最终状态
            rag_content.processing_status = "completed"
            rag_content.processing_message = "所有处理阶段完成"
            db.commit()
            logger.info(f"[Upload] RAG存储完成: content_id={content_id}, collection={final_collection_id}, size={validation['size']}")

            progress_manager.complete_stage(ProcessingStage.FINALIZATION, "文档处理完全完成")
            logger.info(f"[Upload] 处理完成: content_id={content_id}, type={file_type}, title={title}")

            return {
                "success": True,
                "content_id": content_id,
                "resource_id": rag_content.resource_id,  # ✅ 添加resource_id
                "content_data": content_data,
                "markdown_content": markdown_result["markdown_content"],
                "assets": markdown_result.get("assets", {}),
                "processing_info": {
                    "type": file_type,
                    "process_id": process_id,
                    "output_dir": output_dir,
                    "progress_details": progress_manager.get_overall_progress()
                }
            }

        except Exception as e:
            logger.exception(f"[Upload] 文件处理失败: content_id={content_id}")

            # 更新失败状态
            rag_content.processing_status = "failed"
            rag_content.processing_message = f"处理异常: {str(e)}"
            db.commit()

            return {"success": False, "error": f"处理异常: {str(e)}", "content_id": content_id}

    async def _process_video_async(self, video_path: str, output_dir: str, title: str, enable_audio: bool = True) -> Dict[str, Any]:
        """异步处理视频文件"""
        try:
            # 在线程池中运行视频处理（因为是CPU密集型任务）
            loop = asyncio.get_event_loop()
            # 直接异步调用，不使用executor
            result = await self.converter.convert_video_to_markdown(
                video_path, output_dir, title, enable_audio  # 根据配置启用音频
            )
            return result
        except Exception as e:
            logger.error(f"异步视频处理失败: {str(e)}")
            return {"success": False, "error": str(e)}

    def _generate_content_summary(self, markdown_result: Dict[str, Any]) -> str:
        """根据处理结果生成内容摘要"""
        try:
            markdown_content = markdown_result.get("markdown_content", "")
            metadata = markdown_result.get("metadata", {})

            # 简单的摘要生成逻辑
            if "keyframes_count" in metadata:
                # 视频摘要
                duration = metadata.get("processing_time", "未知")
                keyframes = metadata.get("keyframes_count", 0)
                has_audio = metadata.get("has_audio", False)

                summary = f"视频内容包含{keyframes}个关键场景"
                if has_audio:
                    summary += "，包含语音转录"
                summary += f"。处理时间：{duration}"
            else:
                # 从Markdown内容生成简单摘要
                lines = markdown_content.split('\n')
                content_lines = [line for line in lines if line.strip() and not line.startswith('#')]
                if content_lines:
                    summary = content_lines[0][:200] + "..." if len(content_lines[0]) > 200 else content_lines[0]
                else:
                    summary = "多模态内容"

            return summary

        except Exception as e:
            logger.error(f"摘要生成失败: {str(e)}")
            return "多模态内容，摘要生成失败"

    def save_to_database(self, db: Session, content_data: Dict[str, Any]) -> RAGContent:
        """保存到数据库（支持upsert）"""
        try:
            # 检查是否已存在
            resource_id = content_data.get('resource_id')
            existing_content = None

            if resource_id:
                existing_content = db.query(RAGContent).filter(
                    RAGContent.resource_id == resource_id
                ).first()

            if existing_content:
                # 更新现有记录
                for key, value in content_data.items():
                    if key != 'id':  # 不更新主键
                        setattr(existing_content, key, value)
                rag_content = existing_content
                logger.info(f"更新现有内容: {resource_id}")
            else:
                # 创建新记录
                rag_content = RAGContent(**content_data)
                db.add(rag_content)
                logger.info(f"创建新内容: {resource_id}")

            # 保存到数据库（并发安全：处理唯一键冲突）
            try:
                db.commit()
                db.refresh(rag_content)
            except IntegrityError as ie:
                db.rollback()
                logger.warning(
                    f"[Upload] 保存内容时发生唯一键冲突(resource_id={resource_id})，尝试转为更新: {ie}"
                )
                concurrent_existing = db.query(RAGContent).filter(
                    RAGContent.resource_id == resource_id
                ).first()
                if concurrent_existing:
                    for key, value in content_data.items():
                        if key != 'id':
                            setattr(concurrent_existing, key, value)
                    rag_content = concurrent_existing
                    db.commit()
                    db.refresh(rag_content)
                else:
                    raise

            logger.info(f"内容已保存到数据库: {rag_content.resource_id}")
            return rag_content

        except Exception as e:
            logger.error(f"数据库保存失败: {str(e)}")
            db.rollback()
            raise

    def get_processing_status(self, process_id: str) -> Dict[str, Any]:
        """获取处理状态（用于长时间处理的任务）"""
        try:
            # 检查处理目录状态
            process_dir = os.path.join(self.upload_base_dir, "processed", process_id)

            if not os.path.exists(process_dir):
                return {"status": "not_found", "message": "处理任务不存在"}

            # 检查状态文件
            status_file = os.path.join(process_dir, "status.json")
            if os.path.exists(status_file):
                try:
                    with open(status_file, 'r', encoding='utf-8') as f:
                        status_data = json.load(f)

                    status = status_data.get("status", "unknown")

                    if status == "completed":
                        return {
                            "status": "completed",
                            "message": "处理完成",
                            "content_id": status_data.get("content_id"),
                            "document_id": status_data.get("document_id"),
                            "end_time": status_data.get("end_time")
                        }
                    elif status == "failed":
                        return {
                            "status": "failed",
                            "message": status_data.get("error", "处理失败")
                        }
                    elif status == "error":
                        return {
                            "status": "error",
                            "message": status_data.get("error", "处理异常")
                        }
                    elif status == "processing":
                        return {
                            "status": "processing",
                            "message": "正在处理中...",
                            "start_time": status_data.get("start_time")
                        }
                    else:
                        return {"status": status, "message": "处理状态未知"}

                except json.JSONDecodeError:
                    logger.warning(f"状态文件格式错误: {status_file}")
                    return {"status": "error", "message": "状态文件格式错误"}

            # 兼容旧格式 - 检查是否有Markdown文件（表示完成）
            markdown_file = os.path.join(process_dir, "video_content.md")
            if os.path.exists(markdown_file):
                return {"status": "completed", "message": "处理完成"}

            # 兼容旧格式 - 检查是否有错误日志
            error_file = os.path.join(process_dir, "error.log")
            if os.path.exists(error_file):
                with open(error_file, 'r', encoding='utf-8') as f:
                    error_msg = f.read()
                return {"status": "failed", "message": error_msg}

            # 默认为处理中
            return {"status": "processing", "message": "正在处理中..."}

        except Exception as e:
            logger.error(f"状态查询失败: {str(e)}")
            return {"status": "error", "message": f"状态查询异常: {str(e)}"}

# 全局服务实例
multimodal_service = MultimodalUploadService()

# 便捷函数
async def process_multimodal_upload(file_path: str, content_type: str, user_id: str,
                                   db: Session, **kwargs) -> Dict[str, Any]:
    """便捷的多模态上传处理函数"""
    try:
        # 过滤支持的参数
        supported_params = {
            'title': kwargs.get('title'),
            'collection_id': kwargs.get('collection_id'),
            'parse_options': kwargs.get('parse_options'),
            'resource_id': kwargs.get('resource_id')  # 添加resource_id支持
        }
        # 移除None值
        supported_params = {k: v for k, v in supported_params.items() if v is not None}

        # 处理文件 - 使用带详细进度跟踪的方法
        result = await multimodal_service.process_uploaded_file_with_progress(
            file_path, content_type, user_id, db, **supported_params
        )

        # 数据库记录已在 process_uploaded_file_with_progress 方法中创建
        if result["success"]:
            result["content_id"] = result["content_id"]  # 保持一致

        return result

    except Exception as e:
        logger.error(f"多模态上传处理失败: {str(e)}")
        return {"success": False, "error": f"处理失败: {str(e)}"}

if __name__ == "__main__":
    # 测试示例
    import asyncio

    async def test_service():
        service = MultimodalUploadService()

        # 测试视频处理
        test_video = "test_video.mp4"
        if os.path.exists(test_video):
            result = await service.process_uploaded_file(
                test_video, "video/mp4", "test_user", "测试视频"
            )
            logger.info(f"处理结果: {result['success']}")
            if result["success"]:
                logger.info(f"Markdown长度: {len(result['markdown_content'])}")
        else:
            logger.debug("使用简单Markdown处理")

    # 运行测试
    # asyncio.run(test_service())


# 全局服务实例
multimodal_upload_service = MultimodalUploadService()
