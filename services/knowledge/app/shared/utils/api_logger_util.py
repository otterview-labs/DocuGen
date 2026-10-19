#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API请求日志工具
用于记录所有API请求和响应到数据库
"""

import json
import time
from typing import Optional, Dict, Any
from fastapi import Request
from sqlalchemy.orm import Session

from app.db.models.api_log import APIRequestLog
from app.shared.utils.logger_util import get_logger

logger = get_logger(
    name=__name__,
    file_name="app.log",
    color_console=True
)


class APILogger:
    """API请求日志记录器"""

    def __init__(self, db: Session, request: Request):
        """
        初始化API日志记录器

        Args:
            db: 数据库会话
            request: FastAPI请求对象
        """
        self.db = db
        self.request = request
        self.start_time = time.time()
        self.log_entry = None

    async def log_request(
        self,
        request_body: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ):
        """
        记录请求信息

        Args:
            request_body: 请求体（字典格式）
            user_id: 用户ID
        """
        try:
            # 提取请求信息
            client_ip = self.request.client.host if self.request.client else "unknown"
            user_agent = self.request.headers.get("user-agent", "")

            # 提取查询参数
            query_params = dict(self.request.query_params) if self.request.query_params else None

            # 创建日志记录
            self.log_entry = APIRequestLog(
                method=self.request.method,
                endpoint=str(self.request.url.path),
                client_ip=client_ip,
                user_agent=user_agent[:500] if user_agent else None,  # 限制长度
                query_params=json.dumps(query_params, ensure_ascii=False) if query_params else None,
                request_body=json.dumps(request_body, ensure_ascii=False)[:10000] if request_body else None,  # 限制10KB
                user_id=user_id,
            )

        except Exception as e:
            logger.error(f"记录API请求失败: {e}")

    def log_response(
        self,
        status_code: int,
        response_body: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        collection_id: Optional[str] = None,
        search_query: Optional[str] = None,
        search_mode: Optional[str] = None,
        result_count: Optional[int] = None
    ):
        """
        记录响应信息并保存到数据库

        Args:
            status_code: HTTP状态码
            response_body: 响应体（字典格式）
            error_message: 错误信息
            collection_id: 集合ID（RAG相关）
            search_query: 搜索查询（RAG相关）
            search_mode: 搜索模式（RAG相关）
            result_count: 结果数量
        """
        try:
            if not self.log_entry:
                logger.warning("未找到请求日志记录，跳过响应日志")
                return

            # 计算响应时间
            response_time = (time.time() - self.start_time) * 1000  # 转换为毫秒

            # 更新日志记录
            self.log_entry.status_code = status_code
            self.log_entry.response_time = round(response_time, 2)
            self.log_entry.error_message = error_message[:2000] if error_message else None  # 限制长度

            # 只保存响应摘要，不保存完整内容（避免数据库过大）
            if response_body:
                response_summary = {
                    "total": response_body.get("total"),
                    "success": response_body.get("success"),
                    "message": response_body.get("message"),
                }
                self.log_entry.response_body = json.dumps(response_summary, ensure_ascii=False)[:5000]  # 限制5KB

            # RAG相关信息
            self.log_entry.collection_id = collection_id
            self.log_entry.search_query = search_query[:1000] if search_query else None
            self.log_entry.search_mode = search_mode
            self.log_entry.result_count = result_count

            # 保存到数据库
            self.db.add(self.log_entry)
            self.db.commit()

            logger.debug(
                f"API日志已保存: {self.log_entry.method} {self.log_entry.endpoint} "
                f"[{status_code}] {response_time:.2f}ms"
            )

        except Exception as e:
            logger.error(f"保存API响应日志失败: {e}")
            self.db.rollback()


def create_api_logger(db: Session, request: Request) -> APILogger:
    """
    创建API日志记录器的便捷函数

    Args:
        db: 数据库会话
        request: FastAPI请求对象

    Returns:
        APILogger实例
    """
    return APILogger(db, request)
