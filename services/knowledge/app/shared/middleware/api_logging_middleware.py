#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API请求日志中间件
自动记录所有API请求和响应到数据库
"""

import time
import json
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse

from app.db.session import SessionLocal
from app.shared.utils.api_logger_util import create_api_logger
from app.shared.utils.logger_util import get_logger

logger = get_logger(
    name=__name__,
    file_name="app.log",
    color_console=True
)


class APILoggingMiddleware(BaseHTTPMiddleware):
    """
    API请求日志中间件
    自动记录所有API请求和响应到数据库
    """

    # 排除不需要记录的路径
    EXCLUDED_PATHS = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/static",
        "/uploads",
        "/temp/uploads",
        "/optimized_frames",
        "/favicon.ico",
        "/api/v1/rag/search/unified",  # 这个接口已经有详细的日志记录
    ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        处理每个请求

        Args:
            request: FastAPI请求对象
            call_next: 下一个处理函数

        Returns:
            响应对象
        """
        # 检查是否需要记录该路径
        if self._should_skip_logging(request.url.path):
            return await call_next(request)

        # 记录开始时间
        start_time = time.time()

        # 创建数据库会话
        db = SessionLocal()
        api_logger = None

        try:
            # 创建API日志记录器
            api_logger = create_api_logger(db, request)

            # 读取请求体
            request_body = await self._get_request_body(request)

            # 记录请求
            await api_logger.log_request(
                request_body=request_body,
                user_id=None  # 可以从request.state中获取用户信息
            )

            # 执行请求
            response = await call_next(request)

            # 计算响应时间
            response_time = (time.time() - start_time) * 1000

            # 提取RAG相关信息（如果有）
            rag_info = self._extract_rag_info(request_body, request.url.path)

            # 记录响应
            api_logger.log_response(
                status_code=response.status_code,
                response_body={
                    "status_code": response.status_code,
                    "success": response.status_code < 400
                },
                collection_id=rag_info.get("collection_id"),
                search_query=rag_info.get("search_query"),
                search_mode=rag_info.get("search_mode"),
                result_count=None  # 无法从中间件获取，需要在具体接口中设置
            )

            return response

        except Exception as e:
            # 计算响应时间
            response_time = (time.time() - start_time) * 1000

            # 记录错误
            logger.error(f"API请求处理失败: {e}")

            if api_logger:
                try:
                    api_logger.log_response(
                        status_code=500,
                        error_message=str(e),
                        collection_id=None,
                        search_query=None,
                        search_mode=None,
                        result_count=0
                    )
                except Exception as log_error:
                    logger.error(f"记录错误日志失败: {log_error}")

            # 重新抛出异常，让其他异常处理器处理
            raise

        finally:
            # 关闭数据库会话
            db.close()

    def _should_skip_logging(self, path: str) -> bool:
        """
        检查是否应该跳过日志记录

        Args:
            path: 请求路径

        Returns:
            True表示跳过，False表示记录
        """
        for excluded_path in self.EXCLUDED_PATHS:
            if path.startswith(excluded_path):
                return True
        return False

    async def _get_request_body(self, request: Request) -> dict:
        """
        获取请求体内容

        Args:
            request: FastAPI请求对象

        Returns:
            请求体字典
        """
        try:
            # 获取原始请求体
            body = await request.body()

            # 如果是JSON格式，解析它
            if body:
                try:
                    return json.loads(body.decode())
                except json.JSONDecodeError:
                    # 如果不是JSON，返回原始字符串
                    return {"raw_body": body.decode()[:1000]}  # 限制长度

            return None

        except Exception as e:
            logger.warning(f"获取请求体失败: {e}")
            return None

    def _extract_rag_info(self, request_body: dict, path: str) -> dict:
        """
        提取RAG相关信息

        Args:
            request_body: 请求体
            path: 请求路径

        Returns:
            包含RAG信息的字典
        """
        rag_info = {
            "collection_id": None,
            "search_query": None,
            "search_mode": None
        }

        if not request_body:
            return rag_info

        # 检查是否是搜索相关的请求
        if "/search" in path or "/rag" in path:
            # 提取搜索查询
            if "query" in request_body:
                rag_info["search_query"] = request_body.get("query")

            # 提取搜索模式
            if "search_mode" in request_body:
                rag_info["search_mode"] = request_body.get("search_mode")

            # 提取集合ID
            if "collection_id" in request_body:
                collection_ids = request_body.get("collection_id")
                if isinstance(collection_ids, list) and collection_ids:
                    rag_info["collection_id"] = collection_ids[0]
                elif isinstance(collection_ids, str):
                    rag_info["collection_id"] = collection_ids

        return rag_info
