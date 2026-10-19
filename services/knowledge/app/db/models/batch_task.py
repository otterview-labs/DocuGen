#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量任务数据库模型
"""

from sqlalchemy import Column, String, Integer, Text, DateTime, Float, JSON, Boolean
from sqlalchemy.sql import func
from app.db.models.base import BaseModel


class BatchTask(BaseModel):
    """批量处理任务模型"""

    __tablename__ = "batch_tasks"
    id = None  # task_id is the primary key; do not inherit an integer composite key.

    # 基本信息
    task_id = Column(String(64), primary_key=True, comment="任务唯一ID")
    progress_token = Column(String(128), unique=True, index=True, comment="进度令牌")
    task_type = Column(String(32), default="standard", comment="任务类型: standard, chunked")

    # 任务状态
    status = Column(String(32), default="pending", index=True, comment="任务状态")
    current_stage = Column(String(32), default="upload", comment="当前处理阶段")
    overall_progress = Column(Float, default=0.0, comment="总体进度 0-100")

    # 文件统计
    total_files = Column(Integer, default=0, comment="总文件数")
    processed_files = Column(Integer, default=0, comment="已处理文件数")
    failed_files = Column(Integer, default=0, comment="失败文件数")

    # 配置选项
    auto_rag = Column(Boolean, default=True, comment="自动RAG处理")
    auto_kg = Column(Boolean, default=True, comment="自动知识图谱")

    # 时间信息
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    started_at = Column(DateTime(timezone=True), comment="开始时间")
    completed_at = Column(DateTime(timezone=True), comment="完成时间")

    # 结果统计
    results_summary = Column(JSON, comment="处理结果汇总")
    error_message = Column(Text, comment="错误信息")

    # 元数据
    files_info = Column(JSON, comment="文件信息列表")
    processing_logs = Column(JSON, comment="处理日志")


class BatchTaskFile(BaseModel):
    """批量任务文件模型"""

    __tablename__ = "batch_task_files"
    id = None

    # 基本信息
    file_id = Column(String(64), primary_key=True, comment="文件唯一ID")
    task_id = Column(String(64), index=True, comment="关联的任务ID")

    # 文件信息
    original_name = Column(String(255), comment="原始文件名")
    saved_name = Column(String(255), comment="保存后的文件名")
    file_path = Column(String(512), comment="文件保存路径")
    file_size = Column(Integer, comment="文件大小(字节)")
    file_extension = Column(String(256), comment="文件扩展名")
    file_hash = Column(String(128), index=True, comment="文件哈希值")

    # 处理状态
    status = Column(String(32), default="pending", index=True, comment="处理状态")
    current_stage = Column(String(32), default="upload", comment="当前阶段")
    progress = Column(Float, default=0.0, comment="文件处理进度")

    # 处理结果
    upload_result = Column(JSON, comment="上传阶段结果")
    parse_result = Column(JSON, comment="解析阶段结果")
    rag_result = Column(JSON, comment="RAG阶段结果")
    kg_result = Column(JSON, comment="知识图谱阶段结果")

    # 时间信息
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    started_at = Column(DateTime(timezone=True), comment="开始处理时间")
    completed_at = Column(DateTime(timezone=True), comment="完成时间")

    # 错误信息
    error_message = Column(Text, comment="错误信息")
    retry_count = Column(Integer, default=0, comment="重试次数")


class BatchProcessingLog(BaseModel):
    """批量处理日志模型"""

    __tablename__ = "batch_processing_logs"
    id = None

    log_id = Column(String(64), primary_key=True, comment="日志ID")
    task_id = Column(String(64), index=True, comment="任务ID")
    file_id = Column(String(64), index=True, nullable=True, comment="文件ID")

    # 日志内容
    level = Column(String(16), comment="日志级别: DEBUG, INFO, WARNING, ERROR")
    stage = Column(String(32), comment="处理阶段")
    message = Column(Text, comment="日志消息")

    # 额外信息
    extra_data = Column(JSON, comment="额外数据")

    # 时间
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")


# 创建索引以优化查询性能
def create_indexes(engine):
    """创建额外的索引"""
    from sqlalchemy import Index

    # 批量任务查询索引
    Index('idx_batch_tasks_status_created', BatchTask.status, BatchTask.created_at)
    Index('idx_batch_tasks_progress_token', BatchTask.progress_token)

    # 文件查询索引
    Index('idx_batch_files_task_status', BatchTaskFile.task_id, BatchTaskFile.status)
    Index('idx_batch_files_hash', BatchTaskFile.file_hash)

    # 日志查询索引
    Index('idx_batch_logs_task_level', BatchProcessingLog.task_id, BatchProcessingLog.level)
    Index('idx_batch_logs_created', BatchProcessingLog.created_at)
