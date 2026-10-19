#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
处理进度管理器 - 文档处理进度实时追踪

**核心功能**：
- 阶段跟踪：记录文档处理的每个阶段
- 进度计算：实时计算处理进度百分比
- 状态管理：管理处理成功/失败状态
- 错误记录：记录处理过程中的错误信息

**处理阶段**（ProcessingStage）：
1. UPLOAD: 文件上传
2. VALIDATION: 文件验证
3. MARKDOWN_CONVERSION: Markdown转换
4. AI_ANALYSIS: AI摘要和标签分析
5. RAG_STORAGE: RAG向量化和存储
6. KNOWLEDGE_GRAPH: 知识图谱构建
7. EMBEDDING: 向量嵌入
8. STORING: 存储
9. FINALIZATION: 完成

**主要方法**：
- start_stage(): 开始某个处理阶段
- complete_stage(): 完成某个处理阶段
- fail_stage(): 标记阶段失败
- get_progress(): 获取当前处理进度

**被使用位置**：
- app/services/multimodal_upload_service.py: 文档上传进度追踪
- app/shared/parsers/unified_markdown_converter.py: 转换进度追踪
"""

import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
from sqlalchemy.orm import Session

from app.db.models.rag import RAGContent
from app.shared.utils.logger_util import get_logger

logger = get_logger("ProcessingProgressManager")


class ProcessingStage(Enum):
    """处理阶段枚举"""
    UPLOAD = "upload"                    # 文件上传
    VALIDATION = "validation"            # 文件验证
    MARKDOWN_CONVERSION = "markdown"     # Markdown转换
    AI_ANALYSIS = "ai_analysis"         # AI摘要和标签分析
    RAG_STORAGE = "rag_storage"         # RAG向量化和存储
    KNOWLEDGE_GRAPH = "knowledge_graph"  # 知识图谱导入
    FINALIZATION = "finalization"        # 最终完成
    EMBEDDING = "embedding"              # 向量嵌入
    STORING = "storing"                  # 存储
    ANALYZING = "analyzing"              # 分析


class ProcessingStatus(Enum):
    """处理状态枚举"""
    PENDING = "pending"       # 等待开始
    PROCESSING = "processing" # 处理中
    COMPLETED = "completed"   # 完成
    FAILED = "failed"        # 失败
    SKIPPED = "skipped"      # 跳过


class ProcessingProgressManager:
    """处理进度管理器"""

    def __init__(self, document_id: str = None, db: Session = None):
        """
        初始化进度管理器

        Args:
            document_id: 文档ID（可选）
            db: 数据库会话（可选）
        """
        self.document_id = document_id or str(time.time())
        self.db = db
        self.start_time = time.time()

        # 初始化处理阶段
        self.stages = {
            ProcessingStage.UPLOAD.value: {
                "name": "文件上传",
                "description": "接收和验证上传文件",
                "status": ProcessingStatus.PENDING.value,
                "progress": 0,
                "start_time": None,
                "end_time": None,
                "duration": 0,
                "message": "",
                "details": {}
            },
            ProcessingStage.VALIDATION.value: {
                "name": "文件验证",
                "description": "验证文件格式和大小",
                "status": ProcessingStatus.PENDING.value,
                "progress": 0,
                "start_time": None,
                "end_time": None,
                "duration": 0,
                "message": "",
                "details": {}
            },
            ProcessingStage.MARKDOWN_CONVERSION.value: {
                "name": "内容转换",
                "description": "将文档转换为Markdown格式",
                "status": ProcessingStatus.PENDING.value,
                "progress": 0,
                "start_time": None,
                "end_time": None,
                "duration": 0,
                "message": "",
                "details": {}
            },
            ProcessingStage.AI_ANALYSIS.value: {
                "name": "AI智能分析",
                "description": "生成摘要和提取标签",
                "status": ProcessingStatus.PENDING.value,
                "progress": 0,
                "start_time": None,
                "end_time": None,
                "duration": 0,
                "message": "",
                "details": {}
            },
            ProcessingStage.RAG_STORAGE.value: {
                "name": "知识库存储",
                "description": "向量化并存储到知识库",
                "status": ProcessingStatus.PENDING.value,
                "progress": 0,
                "start_time": None,
                "end_time": None,
                "duration": 0,
                "message": "",
                "details": {}
            },
            ProcessingStage.KNOWLEDGE_GRAPH.value: {
                "name": "知识图谱",
                "description": "构建知识图谱关系",
                "status": ProcessingStatus.PENDING.value,
                "progress": 0,
                "start_time": None,
                "end_time": None,
                "duration": 0,
                "message": "",
                "details": {}
            },
            ProcessingStage.FINALIZATION.value: {
                "name": "完成整理",
                "description": "最终数据整理和索引",
                "status": ProcessingStatus.PENDING.value,
                "progress": 0,
                "start_time": None,
                "end_time": None,
                "duration": 0,
                "message": "",
                "details": {}
            }
        }

    def create_task(self, *args, **kwargs):
        """创建任务（兼容方法）"""
        return self.document_id

    def update_progress(self, *args, **kwargs):
        """更新进度（兼容方法）"""
        pass

    def complete_task(self, *args, **kwargs):
        """完成任务（兼容方法）"""
        pass

    def fail_task(self, *args, **kwargs):
        """任务失败（兼容方法）"""
        pass

    def start_stage(self, stage: ProcessingStage, message: str = "", details: Dict[str, Any] = None):
        """开始处理阶段"""
        stage_key = stage.value
        current_time = time.time()

        self.stages[stage_key]["status"] = ProcessingStatus.PROCESSING.value
        self.stages[stage_key]["start_time"] = current_time
        self.stages[stage_key]["message"] = message
        self.stages[stage_key]["details"] = details or {}

        logger.info(f"文档 {self.document_id} 开始阶段: {self.stages[stage_key]['name']}")
        self._update_database()

    def update_stage_progress(self, stage: ProcessingStage, progress: int, message: str = "", details: Dict[str, Any] = None):
        """更新阶段进度"""
        stage_key = stage.value

        # 如果阶段不存在，创建一个默认阶段
        if stage_key not in self.stages:
            self.stages[stage_key] = {
                "name": stage_key,
                "description": "",
                "status": ProcessingStatus.PROCESSING.value,
                "progress": 0,
                "start_time": time.time(),
                "end_time": None,
                "duration": 0,
                "message": "",
                "details": {}
            }

        self.stages[stage_key]["progress"] = max(0, min(100, progress))
        if message:
            self.stages[stage_key]["message"] = message
        if details:
            self.stages[stage_key]["details"].update(details)

        logger.debug(f"文档 {self.document_id} 阶段进度: {self.stages[stage_key]['name']} - {progress}%")
        self._update_database()

    def complete_stage(self, stage: ProcessingStage, message: str = "", details: Dict[str, Any] = None):
        """完成处理阶段"""
        stage_key = stage.value
        current_time = time.time()

        if stage_key not in self.stages:
            self.stages[stage_key] = {
                "name": stage_key,
                "description": "",
                "status": ProcessingStatus.PENDING.value,
                "progress": 0,
                "start_time": current_time,
                "end_time": None,
                "duration": 0,
                "message": "",
                "details": {}
            }

        self.stages[stage_key]["status"] = ProcessingStatus.COMPLETED.value
        self.stages[stage_key]["progress"] = 100
        self.stages[stage_key]["end_time"] = current_time

        if self.stages[stage_key]["start_time"]:
            self.stages[stage_key]["duration"] = current_time - self.stages[stage_key]["start_time"]

        if message:
            self.stages[stage_key]["message"] = message
        if details:
            self.stages[stage_key]["details"].update(details)

        logger.info(f"文档 {self.document_id} 完成阶段: {self.stages[stage_key]['name']} (耗时: {self.stages[stage_key]['duration']:.2f}s)")
        self._update_database()

    def fail_stage(self, stage: ProcessingStage, error_message: str, details: Dict[str, Any] = None):
        """标记阶段失败"""
        stage_key = stage.value
        current_time = time.time()

        if stage_key not in self.stages:
            self.stages[stage_key] = {
                "name": stage_key,
                "description": "",
                "status": ProcessingStatus.PENDING.value,
                "progress": 0,
                "start_time": current_time,
                "end_time": None,
                "duration": 0,
                "message": "",
                "details": {}
            }

        self.stages[stage_key]["status"] = ProcessingStatus.FAILED.value
        self.stages[stage_key]["end_time"] = current_time
        self.stages[stage_key]["message"] = error_message

        if self.stages[stage_key]["start_time"]:
            self.stages[stage_key]["duration"] = current_time - self.stages[stage_key]["start_time"]

        if details:
            self.stages[stage_key]["details"].update(details)

        logger.error(f"文档 {self.document_id} 阶段失败: {self.stages[stage_key]['name']} - {error_message}")
        self._update_database()

    def skip_stage(self, stage: ProcessingStage, reason: str):
        """跳过处理阶段"""
        stage_key = stage.value

        if stage_key not in self.stages:
            self.stages[stage_key] = {
                "name": stage_key,
                "description": "",
                "status": ProcessingStatus.PENDING.value,
                "progress": 0,
                "start_time": None,
                "end_time": None,
                "duration": 0,
                "message": "",
                "details": {}
            }

        self.stages[stage_key]["status"] = ProcessingStatus.SKIPPED.value
        self.stages[stage_key]["progress"] = 100
        self.stages[stage_key]["message"] = f"跳过: {reason}"

        logger.info(f"文档 {self.document_id} 跳过阶段: {self.stages[stage_key]['name']} - {reason}")
        self._update_database()

    def get_overall_progress(self) -> Dict[str, Any]:
        """获取总体进度"""
        total_stages = len(self.stages)
        completed_stages = sum(1 for stage in self.stages.values()
                             if stage["status"] in [ProcessingStatus.COMPLETED.value, ProcessingStatus.SKIPPED.value])
        failed_stages = sum(1 for stage in self.stages.values() if stage["status"] == ProcessingStatus.FAILED.value)
        processing_stages = sum(1 for stage in self.stages.values() if stage["status"] == ProcessingStatus.PROCESSING.value)

        overall_progress = (completed_stages / total_stages * 100) if total_stages > 0 else 0

        # 计算当前阶段的详细进度
        current_stage_progress = 0
        current_stage_name = "准备开始"

        for stage_key, stage_info in self.stages.items():
            if stage_info["status"] == ProcessingStatus.PROCESSING.value:
                current_stage_progress = stage_info["progress"]
                current_stage_name = stage_info["name"]
                break

        return {
            "overall_progress": round(overall_progress, 1),
            "total_stages": total_stages,
            "completed_stages": completed_stages,
            "failed_stages": failed_stages,
            "processing_stages": processing_stages,
            "current_stage": current_stage_name,
            "current_stage_progress": current_stage_progress,
            "total_duration": time.time() - self.start_time,
            "stages": self.stages
        }

    def get_processing_status(self) -> str:
        """获取总体处理状态"""
        if any(stage["status"] == ProcessingStatus.FAILED.value for stage in self.stages.values()):
            return ProcessingStatus.FAILED.value
        elif any(stage["status"] == ProcessingStatus.PROCESSING.value for stage in self.stages.values()):
            return ProcessingStatus.PROCESSING.value
        elif all(stage["status"] in [ProcessingStatus.COMPLETED.value, ProcessingStatus.SKIPPED.value]
                for stage in self.stages.values()):
            return ProcessingStatus.COMPLETED.value
        else:
            return ProcessingStatus.PENDING.value

    def get_all_stage_details(self) -> Dict[str, Any]:
        """获取所有阶段的详细信息"""
        return {
            stage_key: {
                "name": stage_info["name"],
                "description": stage_info["description"],
                "status": stage_info["status"],
                "progress": stage_info["progress"],
                "message": stage_info["message"],
                "start_time": stage_info["start_time"],
                "end_time": stage_info["end_time"],
                "duration": stage_info["duration"],
                "details": stage_info["details"]
            }
            for stage_key, stage_info in self.stages.items()
        }

    def get_stage_summary(self) -> Dict[str, Any]:
        """获取阶段处理摘要"""
        summary = {}
        for stage_key, stage_info in self.stages.items():
            summary[stage_key] = {
                "name": stage_info["name"],
                "status": stage_info["status"],
                "progress": stage_info["progress"]
            }
        return summary

    def _update_database(self):
        """更新数据库中的处理进度"""
        try:
            if self.db and self.document_id:
                rag_content = self.db.query(RAGContent).filter(RAGContent.id == self.document_id).first()
                if rag_content:
                    # 更新处理状态
                    rag_content.processing_status = self.get_processing_status()

                    # 生成状态消息
                    current_progress = self.get_overall_progress()
                    rag_content.processing_message = f"{current_progress['current_stage']} ({current_progress['overall_progress']:.1f}%)"

                    # 更新详细进度
                    rag_content.processing_details = json.dumps(current_progress, ensure_ascii=False)

                    self.db.commit()

        except Exception as e:
            logger.error(f"更新数据库进度失败: {str(e)}")
            if self.db:
                self.db.rollback()
