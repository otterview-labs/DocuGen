#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档处理状态管理工具
提供文档处理状态的更新和查询功能
"""

from app.shared.utils.logger_util import get_logger

logger = get_logger(__name__)

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.models.rag import RAGContent
from app.db.session import get_db

class DocumentProcessingStatusManager:
    """文档处理状态管理器"""

    # 基础状态常量
    STATUS_PENDING = "pending"              # 等待处理
    STATUS_PROCESSING = "processing"        # 处理中
    STATUS_COMPLETED = "completed"          # 处理完成
    STATUS_FAILED = "failed"               # 处理失败

    # 细分处理状态
    STATUS_UPLOADING = "uploading"          # 上传中
    STATUS_PARSING = "parsing"              # 解析中（文本提取）
    STATUS_ANALYZING = "analyzing"          # 分析中（内容分析、摘要生成）
    STATUS_CHUNKING = "chunking"            # 分块中
    STATUS_EMBEDDING = "embedding"          # 向量化中
    STATUS_INDEXING = "indexing"            # 索引中（存储到向量数据库）
    STATUS_REVIEWING = "reviewing"          # 人工审核中
    STATUS_APPROVED = "approved"            # 已审核通过
    STATUS_REJECTED = "rejected"            # 已拒绝
    STATUS_ARCHIVED = "archived"            # 已归档
    STATUS_EXPIRED = "expired"              # 已过期
    STATUS_DELETED = "deleted"              # 已删除

    # 状态分组
    PENDING_STATUSES = [STATUS_PENDING, STATUS_UPLOADING]
    PROCESSING_STATUSES = [STATUS_PROCESSING, STATUS_PARSING, STATUS_ANALYZING,
                          STATUS_CHUNKING, STATUS_EMBEDDING, STATUS_INDEXING]
    SUCCESS_STATUSES = [STATUS_COMPLETED, STATUS_APPROVED]
    FAILED_STATUSES = [STATUS_FAILED, STATUS_REJECTED, STATUS_EXPIRED]
    FINAL_STATUSES = [STATUS_COMPLETED, STATUS_FAILED, STATUS_APPROVED,
                     STATUS_REJECTED, STATUS_ARCHIVED, STATUS_DELETED]

    # 状态描述映射
    STATUS_DESCRIPTIONS = {
        STATUS_PENDING: "等待处理",
        STATUS_UPLOADING: "文件上传中",
        STATUS_PROCESSING: "处理中",
        STATUS_PARSING: "正在解析文档内容",
        STATUS_ANALYZING: "正在分析文档并生成摘要",
        STATUS_CHUNKING: "正在进行文档分块",
        STATUS_EMBEDDING: "正在生成向量嵌入",
        STATUS_INDEXING: "正在建立索引",
        STATUS_COMPLETED: "处理完成",
        STATUS_FAILED: "处理失败",
        STATUS_REVIEWING: "等待人工审核",
        STATUS_APPROVED: "审核通过",
        STATUS_REJECTED: "审核拒绝",
        STATUS_ARCHIVED: "已归档",
        STATUS_EXPIRED: "已过期",
        STATUS_DELETED: "已删除"
    }

    @classmethod
    def update_status(cls,
                     db: Session,
                     document_id: str,
                     status: str,
                     message: Optional[str] = None) -> bool:
        """
        更新文档处理状态

        Args:
            db: 数据库会话
            document_id: 文档ID
            status: 新状态 (pending, processing, completed, failed)
            message: 状态消息

        Returns:
            bool: 更新是否成功
        """
        try:
            document = db.query(RAGContent).filter(
                RAGContent.id == document_id
            ).first()

            if not document:
                return False

            # 验证状态值
            valid_statuses = list(cls.STATUS_DESCRIPTIONS.keys())
            if status not in valid_statuses:
                raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

            # 更新状态
            document.processing_status = status
            if message:
                document.processing_message = message

            # 根据处理状态自动更新主状态
            if status in cls.SUCCESS_STATUSES:
                document.status = "1"  # 启用
            elif status in cls.FAILED_STATUSES:
                document.status = "0"  # 禁用
            # 处理中状态保持原有主状态不变

            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.error(f"更新文档状态失败: {e}")
            return False

    @classmethod
    def get_status(cls, db: Session, document_id: str) -> Optional[Dict[str, Any]]:
        """
        获取文档处理状态

        Args:
            db: 数据库会话
            document_id: 文档ID

        Returns:
            dict: 状态信息 或 None
        """
        try:
            document = db.query(RAGContent).filter(
                RAGContent.id == document_id
            ).first()

            if not document:
                return None

            return {
                "document_id": document.id,
                "processing_status": document.processing_status,
                "processing_message": document.processing_message,
                "main_status": document.status,
                "title": document.title,
                "file_name": document.file_name,
                "create_time": document.create_time,
                "update_time": document.update_time
            }

        except Exception as e:
            logger.error(f"获取文档状态失败: {e}")
            return None

    @classmethod
    def batch_update_status(cls,
                           db: Session,
                           document_ids: List[str],
                           status: str,
                           message: Optional[str] = None) -> Dict[str, Any]:
        """
        批量更新文档处理状态

        Args:
            db: 数据库会话
            document_ids: 文档ID列表
            status: 新状态
            message: 状态消息

        Returns:
            dict: 更新结果统计
        """
        try:
            # 验证状态
            valid_statuses = list(cls.STATUS_DESCRIPTIONS.keys())
            if status not in valid_statuses:
                raise ValueError(f"Invalid status: {status}")

            # 批量更新
            update_data = {"processing_status": status}
            if message:
                update_data["processing_message"] = message

            # 根据处理状态设置主状态
            if status in cls.SUCCESS_STATUSES:
                update_data["status"] = "1"
            elif status in cls.FAILED_STATUSES:
                update_data["status"] = "0"

            result = db.query(RAGContent).filter(
                RAGContent.id.in_(document_ids)
            ).update(update_data, synchronize_session=False)

            db.commit()

            return {
                "success": True,
                "updated_count": result,
                "total_requested": len(document_ids),
                "status": status,
                "message": message
            }

        except Exception as e:
            db.rollback()
            return {
                "success": False,
                "error": str(e),
                "updated_count": 0,
                "total_requested": len(document_ids)
            }

    @classmethod
    def get_status_statistics(cls,
                             db: Session,
                             collection_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取处理状态统计

        Args:
            db: 数据库会话
            collection_id: 可选的集合ID过滤

        Returns:
            dict: 状态统计信息
        """
        try:
            query = """
            SELECT processing_status, COUNT(*) as count
            FROM rag_contents
            """
            params = {}

            if collection_id:
                query += " WHERE vector_collection = :collection_id"
                params["collection_id"] = collection_id

            query += " GROUP BY processing_status"

            result = db.execute(text(query), params).fetchall()

            statistics = {
                "total": 0,
                "by_status": {},
                "collection_id": collection_id
            }

            for row in result:
                statistics["by_status"][row.processing_status] = row.count
                statistics["total"] += row.count

            # 计算百分比
            if statistics["total"] > 0:
                statistics["percentages"] = {
                    status: round((count / statistics["total"]) * 100, 2)
                    for status, count in statistics["by_status"].items()
                }

            return statistics

        except Exception as e:
            logger.error(f"获取状态统计失败: {e}")
            return {"error": str(e)}

    @classmethod
    def get_documents_by_status(cls,
                               db: Session,
                               status: str,
                               limit: int = 100,
                               collection_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        根据处理状态获取文档列表

        Args:
            db: 数据库会话
            status: 处理状态
            limit: 返回数量限制
            collection_id: 可选的集合ID过滤

        Returns:
            list: 文档列表
        """
        try:
            query = db.query(RAGContent).filter(
                RAGContent.processing_status == status
            )

            if collection_id:
                query = query.filter(RAGContent.vector_collection == collection_id)

            documents = query.limit(limit).all()

            return [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "file_name": doc.file_name,
                    "processing_status": doc.processing_status,
                    "processing_message": doc.processing_message,
                    "collection_id": doc.vector_collection,
                    "create_time": doc.create_time.isoformat() if doc.create_time else None,
                    "update_time": doc.update_time.isoformat() if doc.update_time else None
                }
                for doc in documents
            ]

        except Exception as e:
            logger.error(f"根据状态获取文档列表失败: {e}")
            return []


    @classmethod
    def get_status_description(cls, status: str) -> str:
        """获取状态描述"""
        return cls.STATUS_DESCRIPTIONS.get(status, "未知状态")

    @classmethod
    def is_processing(cls, status: str) -> bool:
        """判断是否为处理中状态"""
        return status in cls.PROCESSING_STATUSES

    @classmethod
    def is_final_status(cls, status: str) -> bool:
        """判断是否为最终状态"""
        return status in cls.FINAL_STATUSES

    @classmethod
    def is_success_status(cls, status: str) -> bool:
        """判断是否为成功状态"""
        return status in cls.SUCCESS_STATUSES

    @classmethod
    def is_failed_status(cls, status: str) -> bool:
        """判断是否为失败状态"""
        return status in cls.FAILED_STATUSES

    @classmethod
    def get_next_status(cls, current_status: str) -> str:
        """获取下一个应该的状态（处理流程）"""
        status_flow = {
            cls.STATUS_PENDING: cls.STATUS_UPLOADING,
            cls.STATUS_UPLOADING: cls.STATUS_PARSING,
            cls.STATUS_PARSING: cls.STATUS_ANALYZING,
            cls.STATUS_ANALYZING: cls.STATUS_CHUNKING,
            cls.STATUS_CHUNKING: cls.STATUS_EMBEDDING,
            cls.STATUS_EMBEDDING: cls.STATUS_INDEXING,
            cls.STATUS_INDEXING: cls.STATUS_COMPLETED,
            cls.STATUS_PROCESSING: cls.STATUS_COMPLETED,  # 通用处理状态
            cls.STATUS_REVIEWING: cls.STATUS_APPROVED,   # 审核流程
        }
        return status_flow.get(current_status, current_status)

    @classmethod
    def get_all_statuses(cls) -> Dict[str, str]:
        """获取所有状态及其描述"""
        return cls.STATUS_DESCRIPTIONS.copy()

    @classmethod
    def get_status_groups(cls) -> Dict[str, List[str]]:
        """获取状态分组"""
        return {
            "pending": cls.PENDING_STATUSES,
            "processing": cls.PROCESSING_STATUSES,
            "success": cls.SUCCESS_STATUSES,
            "failed": cls.FAILED_STATUSES,
            "final": cls.FINAL_STATUSES
        }


# 便捷函数
def update_document_status(document_id: str, status: str, message: str = None) -> bool:
    """便捷的状态更新函数"""
    db = next(get_db())
    try:
        return DocumentProcessingStatusManager.update_status(db, document_id, status, message)
    finally:
        db.close()

def get_document_status(document_id: str) -> Optional[Dict[str, Any]]:
    """便捷的状态查询函数"""
    db = next(get_db())
    try:
        return DocumentProcessingStatusManager.get_status(db, document_id)
    finally:
        db.close()
