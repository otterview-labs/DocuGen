#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件上传接口（生成可访问URL）
仅负责接收文件并保存到静态目录，返回可直接访问的URL
"""

from typing import Dict, Optional, Any
from fastapi import APIRouter, UploadFile, File, Depends
from pydantic import BaseModel, Field
from pathlib import Path
import hashlib
import aiofiles
import json
import os
from datetime import datetime
from sqlalchemy.orm import Session

from app.shared.response_models import ResponseHelper
from app.shared.utils.logger_util import get_logger
from app.db.session import get_db
from app.db.models.rag import RAGContent
from app.services.multimodal_upload_service import multimodal_service, process_multimodal_upload
from app.shared.utils.file_detector import FileTypeDetector
file_detector = FileTypeDetector()

logger = get_logger("SimpleFileUploadAPI")
router = APIRouter()

UPLOAD_DIR = Path("storage/static/uploads").resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_BASE_DIR = "storage/static/uploads"

class FileUploadResponse(BaseModel):
    success: bool
    url: str = Field(..., description="文件可访问URL")
    file_name: str
    size: int
    md5: str
    sha256: str

class ProcessingStatusResponse(BaseModel):
    """处理状态响应模型"""
    success: bool
    result: Dict[str, Any]
    message: str


@router.post("/upload", response_model=Dict, summary="上传文件并返回URL")
async def upload_file(file: UploadFile = File(...)):
    """
    接收单个文件，将文件保存到 `static/uploads`，并返回可访问URL：`/uploads/<md5><ext>`
    """
    try:
        if not file or not file.filename:
            return ResponseHelper.error("未选择文件", status=400)

        # 计算哈希并保存到最终文件
        suffix = Path(file.filename).suffix.lower()
        md5 = hashlib.md5()
        sha256 = hashlib.sha256()

        temp_path = UPLOAD_DIR / ("._tmp_" + Path(file.filename).name)
        async with aiofiles.open(temp_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                await out.write(chunk)
                md5.update(chunk)
                sha256.update(chunk)

        file_md5 = md5.hexdigest()
        file_sha256 = sha256.hexdigest()
        final_name = f"{file_md5}{suffix}"
        final_path = UPLOAD_DIR / final_name
        # 如果目标已存在（同一文件重复上传），保留已存在文件，删除临时文件，避免报错
        if final_path.exists():
            try:
                await aiofiles.os.remove(temp_path)
            except Exception:
                pass
        else:
            temp_path.rename(final_path)

        url = f"/uploads/{final_name}"
        size = final_path.stat().st_size

        # 为了兼容前端页面（如 unified-resource-test.html）对 file_url 字段的读取，
        # 这里同时返回 url 和 file_url 两个键，其值相同。
        return ResponseHelper.success(
            result={
                "url": url,
                "file_url": url,
                "file_name": final_name,
                "size": size,
                "md5": file_md5,
                "sha256": file_sha256
            },
            message="上传成功"
        )
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        return ResponseHelper.error(f"上传失败: {str(e)}", status=500)

# 以下接口已删除，不再使用路径参数
# - GET /processing-status/{process_id} - 已删除
# - GET /content/{content_id}/raw - 已删除
# 如需这些功能，请使用POST方式的新接口

@router.get("/supported-formats",
           summary="获取支持的文件格式",
           description="获取当前支持的所有文件格式和限制")
async def get_supported_formats():
    """获取支持的文件格式信息"""

    # 使用统一的文件类型检测器获取支持格式
    supported_types = file_detector.get_supported_types()

    # 格式化输出
    formats_info = {
        "video": {
            "extensions": supported_types["video"]["extensions"],
            "max_size_mb": supported_types["video"]["max_size_mb"],
            "max_duration_hours": 2,
            "features": ["关键帧提取", "VLM视觉分析", "语音识别转录", "多模态时间轴"]
        },
        "document": {
            "extensions": supported_types["document"]["extensions"],
            "max_size_mb": supported_types["document"]["max_size_mb"],
            "features": ["文本提取", "结构化解析", "内容分析"]
        },
        "image": {
            "extensions": supported_types["image"]["extensions"],
            "max_size_mb": supported_types["image"]["max_size_mb"],
            "features": ["VLM图像分析", "内容描述生成", "文字识别"]
        }
    }

    return ResponseHelper.success(
        result=formats_info,
        message="支持格式信息获取成功"
    )

# 后台任务函数
async def _process_large_video_background(
    file_path: str, content_type: str, user_id: str,
    title: str, collection_id: Optional[str], enable_audio: bool,
    process_id: str, db: Session
):
    """后台处理大视频文件"""
    try:
        logger.info(f"开始后台处理大视频: {file_path}, 进程ID: {process_id}")

        # 创建处理状态目录
        process_dir = os.path.join(UPLOAD_BASE_DIR, "processed", process_id)
        os.makedirs(process_dir, exist_ok=True)

        # 写入处理状态
        status_file = os.path.join(process_dir, "status.json")
        with open(status_file, 'w', encoding='utf-8') as f:
            import json
            json.dump({"status": "processing", "start_time": datetime.now().isoformat()}, f)

        # 为后台任务创建新的数据库会话
        db_gen = get_db()
        bg_db = next(db_gen)

        try:
            # 启用RAG处理逻辑
            result = await process_multimodal_upload(
                file_path=file_path,
                content_type=content_type,
                user_id=user_id,
                db=bg_db,  # 使用后台数据库会话
                title=title,
                collection_id=collection_id,
                enable_audio=enable_audio
            )

            # 处理RAG结果并更新状态
            if result and result.get("success"):
                content_id = result.get("content_id")
                content_data = result.get("content_data", {})

                with open(status_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "status": "completed",
                        "content_id": content_id,
                        "document_id": content_id,
                        "content_type": content_data.get("content_type", "video"),
                        "title": content_data.get("title", title),
                        "summary": content_data.get("content_summary", ""),
                        "message": "文件处理完成，已转换为Markdown并存储到知识库",
                        "end_time": datetime.now().isoformat()
                    }, f)
            else:
                # 处理失败
                error_msg = result.get("error", "处理失败") if result else "处理结果为空"
                with open(status_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "status": "failed",
                        "error": f"RAG处理失败: {error_msg}",
                        "end_time": datetime.now().isoformat()
                    }, f)
        finally:
            # 确保关闭后台数据库会话
            bg_db.close()

        # 清理临时文件
        if os.path.exists(file_path):
            os.remove(file_path)

        logger.info(f"后台视频处理完成: {process_id}")

    except Exception as e:
        logger.error(f"后台视频处理失败: {str(e)}")

        # 写入错误状态
        try:
            status_file = os.path.join(process_dir, "status.json")
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "status": "error",
                    "error": f"后台处理异常: {str(e)}",
                    "end_time": datetime.now().isoformat()
                }, f)
        except:
            pass
