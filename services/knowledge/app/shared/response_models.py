#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用API响应模型
"""

from typing import Generic, TypeVar, Optional, Any
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import time

T = TypeVar('T')

class UnifiedResponse(BaseModel, Generic[T]):
    """统一API响应格式"""
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(..., description="响应消息")
    result: Optional[T] = Field(None, description="响应数据")
    status: int = Field(..., description="状态码")
    timestamp: int = Field(..., description="时间戳(毫秒)")

class ResponseHelper:
    """响应辅助工具"""

    # StandardResponse for type hints
    StandardResponse = dict

    @staticmethod
    def success(result: Any = None, message: str = "success") -> dict:
        """创建成功响应"""
        return {
            "success": True,
            "message": message,
            "result": result,
            "status": 200,
            "timestamp": int(time.time() * 1000)
        }

    @staticmethod
    def error(message: str = "error", status: int = 500, result: Any = None) -> dict:
        """创建错误响应"""
        return {
            "success": False,
            "message": message,
            "result": result,
            "status": status,
            "timestamp": int(time.time() * 1000)
        }

    @staticmethod
    def created(result: Any = None, message: str = "created") -> dict:
        """创建成功响应"""
        return {
            "success": True,
            "message": message,
            "result": result,
            "status": 201,
            "timestamp": int(time.time() * 1000)
        }

    @staticmethod
    def reset_content(result: Any = None, message: str = "reset content") -> dict:
        """205 Reset Content 响应（用于幂等删除等场景）"""
        return {
            "success": True,
            "message": message,
            "result": result,
            "status": 205,
            "timestamp": int(time.time() * 1000)
        }

    @staticmethod
    def not_found(message: str = "not found") -> dict:
        """404响应"""
        return {
            "success": False,
            "message": message,
            "result": None,
            "status": 404,
            "timestamp": int(time.time() * 1000)
        }

    @staticmethod
    def bad_request(message: str = "bad request") -> dict:
        """400响应"""
        return {
            "success": False,
            "message": message,
            "result": None,
            "status": 400,
            "timestamp": int(time.time() * 1000)
        }

    @staticmethod
    def forbidden(message: str = "forbidden") -> dict:
        """403响应"""
        return {
            "success": False,
            "message": message,
            "result": None,
            "status": 403,
            "timestamp": int(time.time() * 1000)
        }

    @staticmethod
    def as_response(payload: dict) -> JSONResponse:
        """将响应载荷转换为真实 HTTP 响应。"""

        return JSONResponse(
            status_code=int(payload.get("status", 200)),
            content=jsonable_encoder(payload),
        )

    @classmethod
    def success_response(cls, result: Any = None, message: str = "success") -> JSONResponse:
        return cls.as_response(cls.success(result=result, message=message))

    @classmethod
    def error_response(cls, message: str = "error", status: int = 500, result: Any = None) -> JSONResponse:
        return cls.as_response(cls.error(message=message, status=status, result=result))

    @classmethod
    def created_response(cls, result: Any = None, message: str = "created") -> JSONResponse:
        return cls.as_response(cls.created(result=result, message=message))

    @classmethod
    def reset_content_response(cls, result: Any = None, message: str = "reset content") -> JSONResponse:
        return cls.as_response(cls.reset_content(result=result, message=message))

    @classmethod
    def not_found_response(cls, message: str = "not found") -> JSONResponse:
        return cls.as_response(cls.not_found(message=message))

    @classmethod
    def bad_request_response(cls, message: str = "bad request") -> JSONResponse:
        return cls.as_response(cls.bad_request(message=message))

    @classmethod
    def forbidden_response(cls, message: str = "forbidden") -> JSONResponse:
        return cls.as_response(cls.forbidden(message=message))
