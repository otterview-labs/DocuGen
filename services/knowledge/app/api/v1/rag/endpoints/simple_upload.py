#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单文档上传和处理接口
提供一个简化的上传接口，自动处理文档并返回content_id
"""

import json
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pathlib import Path
import os
import uuid
import aiofiles

from app.db.session import get_db
from app.services.multimodal_upload_service import multimodal_service, process_multimodal_upload
from app.shared.response_models import ResponseHelper
from app.shared.utils.logger_util import get_logger

logger = get_logger("SimpleUploadAPI")
router = APIRouter()

# 临时上传目录
TEMP_UPLOAD_DIR = Path("storage/static/uploads/temp")
TEMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/process", summary="上传并处理文档")
async def upload_and_process(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    collection_id: Optional[str] = Form(default="default"),
    enable_audio: bool = Form(default=False),
    parse_options_json: Optional[str] = Form(default=None, description="可选解析配置JSON，支持 visual.regions"),
    db: Session = Depends(get_db)
):
    """
    上传文件并立即处理，返回content_id

    这个接口会：
    1. 接收上传的文件
    2. 保存到临时目录
    3. 调用处理服务进行向量化和存储
    4. 返回content_id用于后续查询
    """
    try:
        if not file or not file.filename:
            return ResponseHelper.error("未选择文件", status=400)

        # 保存文件到临时目录
        temp_filename = f"{uuid.uuid4().hex}_{Path(file.filename).name}"
        temp_path = TEMP_UPLOAD_DIR / temp_filename

        async with aiofiles.open(temp_path, "wb") as out:
            content = await file.read()
            await out.write(content)

        logger.info(f"文件已保存到临时目录: {temp_path}")

        # 获取文件信息
        file_size = temp_path.stat().st_size
        content_type = file.content_type or "application/octet-stream"

        # 使用默认标题
        if not title:
            title = Path(file.filename).stem

        # 生成resource_id
        resource_id = str(uuid.uuid4())

        parse_options = None
        if parse_options_json:
            try:
                parse_options = json.loads(parse_options_json)
            except Exception as exc:
                return ResponseHelper.error(f"parse_options_json 不是合法JSON: {exc}", status=400)

        # 调用处理服务
        result = await process_multimodal_upload(
            file_path=str(temp_path),
            content_type=content_type,
            user_id="default_user",  # 使用默认用户
            db=db,
            title=title,
            collection_id=collection_id,
            enable_audio=enable_audio,
            parse_options=parse_options,
            resource_id=resource_id  # 传递resource_id
        )

        # 清理临时文件
        try:
            os.remove(temp_path)
        except:
            pass

        if result and result.get("success"):
            return ResponseHelper.success(
                result={
                    "content_id": result.get("content_id"),
                    "resource_id": result.get("resource_id"),
                    "title": title,
                    "collection_id": collection_id,
                    "message": "文档处理成功"
                },
                message="上传并处理成功"
            )
        else:
            error_msg = result.get("error", "处理失败") if result else "处理结果为空"
            return ResponseHelper.error(f"文档处理失败: {error_msg}", status=500)

    except Exception as e:
        logger.error(f"上传处理失败: {e}")
        # 清理临时文件
        if 'temp_path' in locals() and temp_path.exists():
            try:
                os.remove(temp_path)
            except:
                pass
        return ResponseHelper.error(f"上传处理失败: {str(e)}", status=500)


@router.post("/process-url", summary="通过URL处理文档")
async def process_from_url(
    url: str = Form(...),
    title: Optional[str] = Form(None),
    collection_id: Optional[str] = Form(default="default"),
    parse_options_json: Optional[str] = Form(default=None, description="可选解析配置JSON，支持 visual.regions"),
    db: Session = Depends(get_db)
):
    """
    从已上传的URL处理文档

    适用于文件已经通过 /multimodal/upload 上传的情况
    """
    try:
        # 从URL提取文件路径
        # URL格式: /uploads/xxx.ext
        if not url.startswith("/uploads/"):
            return ResponseHelper.error("无效的文件URL", status=400)

        filename = url.replace("/uploads/", "")
        file_path = Path("storage/static/uploads") / filename

        if not file_path.exists():
            return ResponseHelper.error("文件不存在", status=404)

        # 推断content_type
        suffix = file_path.suffix.lower()
        content_type_map = {
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.mp4': 'video/mp4',
            '.avi': 'video/avi',
            '.mov': 'video/mov',
        }
        content_type = content_type_map.get(suffix, 'application/octet-stream')

        # 使用默认标题
        if not title:
            title = file_path.stem

        parse_options = None
        if parse_options_json:
            try:
                parse_options = json.loads(parse_options_json)
            except Exception as exc:
                return ResponseHelper.error(f"parse_options_json 不是合法JSON: {exc}", status=400)

        # 调用处理服务
        result = await process_multimodal_upload(
            file_path=str(file_path),
            content_type=content_type,
            user_id="default_user",
            db=db,
            title=title,
            collection_id=collection_id,
            parse_options=parse_options,
            enable_audio=False
        )

        if result and result.get("success"):
            return ResponseHelper.success(
                result={
                    "content_id": result.get("content_id"),
                    "resource_id": result.get("resource_id"),
                    "title": title,
                    "collection_id": collection_id,
                    "message": "文档处理成功"
                },
                message="处理成功"
            )
        else:
            error_msg = result.get("error", "处理失败") if result else "处理结果为空"
            return ResponseHelper.error(f"文档处理失败: {error_msg}", status=500)

    except Exception as e:
        logger.error(f"URL处理失败: {e}")
        return ResponseHelper.error(f"URL处理失败: {str(e)}", status=500)
