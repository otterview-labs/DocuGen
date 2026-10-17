#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资源批量解析API接口
用于批量解析和处理多个资源文件，支持并发处理和进度追踪
"""

import asyncio
import aiohttp
import aiofiles
import hashlib
import uuid
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from app.db.session import get_db
from app.db.models.rag import RAGContent, RAGCollection
from app.shared.response_models import ResponseHelper

router = APIRouter()

# 全局批量任务状态存储
BATCH_TASKS: Dict[str, Dict[str, Any]] = {}


class ResourceContent(BaseModel):
    """资源内容"""
    url: str = Field(..., description="文件URL")
    length: Optional[int] = Field(None, description="文件大小（字节）")
    md5: Optional[str] = Field(None, description="文件MD5值")


class ResourceParseRequest(BaseModel):
    """单个资源解析请求"""
    id: str = Field(..., description="资源ID")
    classifyId: str = Field(..., description="资源分类ID（集合ID）")
    name: str = Field(..., description="资源名称")
    description: str = Field(..., description="描述")
    type: str = Field(..., description="类型：file文件")
    content: ResourceContent = Field(..., description="内容")
    tags: List[str] = Field(default_factory=list, description="标签")
    bindings: List[str] = Field(default_factory=list, description="权限绑定key列表")
    parseOptions: Optional[Dict[str, Any]] = Field(None, description="可选解析配置，支持 visual.regions")


class BatchResourceParseRequest(BaseModel):
    """批量资源解析请求"""
    resources: List[ResourceParseRequest] = Field(..., description="资源列表")


class BatchStatusRequest(BaseModel):
    """批量状态查询请求"""
    batch_id: str = Field(..., description="批量任务ID")


async def ensure_collection_exists(collection_id: str, db: Session) -> bool:
    """
    确保集合存在，如果不存在则自动创建
    """
    try:
        # 检查集合是否已存在
        existing_collection = db.query(RAGCollection).filter(
            RAGCollection.id == collection_id
        ).first()

        if existing_collection:
            logger.info(f"集合已存在: {collection_id} ({existing_collection.name})")
            return True

        # 集合不存在，自动创建
        logger.info(f"集合不存在，自动创建: {collection_id}")

        new_collection = RAGCollection(
            id=collection_id,
            name=f"资源集合_{collection_id[:8]}",
            description=f"通过资源批量解析自动创建的集合",
            collection_type="multimodal",
            user_id="system",
            status="1",
            is_public=True,
            create_time=datetime.utcnow(),
            update_time=datetime.utcnow()
        )

        db.add(new_collection)
        db.commit()
        db.refresh(new_collection)

        logger.info(f"集合自动创建成功: {collection_id}")
        return True

    except Exception as e:
        logger.error(f"创建集合失败: {e}")
        db.rollback()
        return False


async def download_and_validate_resource(url: str) -> tuple[str, Dict[str, Any]]:
    """下载并验证资源文件"""
    try:
        import os
        import mimetypes
        from urllib.parse import unquote, urlparse

        # 添加详细的URL日志
        logger.info(f"[资源下载] 接收到URL: {url}")
        logger.info(f"[资源下载] URL长度: {len(url)}")
        logger.info(f"[资源下载] URL前100字符: {url[:100]}")
        logger.info(f"[资源下载] URL后100字符: {url[-100:] if len(url) > 100 else url}")

        # 创建临时下载目录
        temp_dir = Path("storage/temp/resource_downloads")
        temp_dir.mkdir(parents=True, exist_ok=True)

        parsed = urlparse(url)
        logger.info(f"[资源下载] 解析后的URL - scheme: {parsed.scheme}, netloc: {parsed.netloc}, path: {parsed.path}")

        # 处理相对路径（本地上传的文件）
        if not parsed.scheme or parsed.scheme == "":
            # 相对路径，如 /uploads/xxx.pdf
            # 转换为绝对路径
            if url.startswith('/'):
                # 基于项目根目录的绝对路径
                local_path = Path("storage/static" + url)
            else:
                # 相对路径
                local_path = Path("storage/static") / url

            logger.info(f"[资源下载] 处理本地相对路径: {url} -> {local_path}")

            if not local_path.exists() or not local_path.is_file():
                logger.error(f"[资源下载] 本地文件不存在: {local_path}")
                raise HTTPException(status_code=404, detail=f"本地文件不存在: {url}")

            # 目标文件名与路径
            file_name = local_path.name
            file_path = temp_dir / file_name

            # 读取源文件并计算哈希
            md5_hash = hashlib.md5()
            total_size = 0
            async with aiofiles.open(local_path, 'rb') as src, aiofiles.open(file_path, 'wb') as dst:
                while True:
                    chunk = await src.read(8192)
                    if not chunk:
                        break
                    await dst.write(chunk)
                    md5_hash.update(chunk)
                    total_size += len(chunk)

            content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            file_info = {
                "file_name": file_path.name,
                "file_size": total_size,
                "content_type": content_type,
                "md5": md5_hash.hexdigest(),
                "download_time": datetime.now().isoformat()
            }
            logger.info(f"本地文件复制完成: {file_path.name} ({total_size} bytes)")
            return str(file_path), file_info

        # 处理 http/https 下载
        elif parsed.scheme in ("http", "https"):
            # 生成文件名，移除URL参数
            raw_file_name = url.split("/")[-1] or f"resource_{uuid.uuid4().hex[:8]}"
            # 移除URL参数（?后的内容）
            if "?" in raw_file_name:
                raw_file_name = raw_file_name.split("?")[0]
            file_name = unquote(raw_file_name)
            # 如果文件名为空或只是参数，生成默认文件名
            if not file_name or file_name == "":
                file_name = f"resource_{uuid.uuid4().hex[:8]}"
            file_path = temp_dir / file_name

            logger.info(f"开始下载资源: {url}")

            async with aiohttp.ClientSession() as session:
                logger.info(f"[资源下载] 开始HTTP请求: {url}")
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                    logger.info(f"[资源下载] HTTP响应状态: {response.status}")
                    logger.info(f"[资源下载] HTTP响应头: {dict(response.headers)}")

                    if response.status != 200:
                        response_text = await response.text()
                        logger.error(f"[资源下载] 下载失败 - 状态码: {response.status}")
                        logger.error(f"[资源下载] 响应内容前500字符: {response_text[:500]}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"文件下载失败: HTTP {response.status}"
                        )

                    content_type = response.headers.get("content-type", "application/octet-stream")

                    md5_hash = hashlib.md5()
                    total_size = 0

                    async with aiofiles.open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                            md5_hash.update(chunk)
                            total_size += len(chunk)

                    file_info = {
                        "file_name": file_name,
                        "file_size": total_size,
                        "content_type": content_type,
                        "md5": md5_hash.hexdigest(),
                        "download_time": datetime.now().isoformat()
                    }

                    logger.info(f"文件下载完成: {file_name} ({total_size} bytes)")
                    return str(file_path), file_info

        # 处理本地文件路径: file://...
        elif parsed.scheme == "file":
            local_path = unquote(parsed.path)
            if not os.path.exists(local_path) or not os.path.isfile(local_path):
                raise HTTPException(status_code=404, detail=f"本地文件不存在: {local_path}")

            # 目标文件名与路径
            file_name = os.path.basename(local_path) or f"resource_{uuid.uuid4().hex[:8]}"
            file_path = temp_dir / file_name

            # 读取源文件并计算哈希
            md5_hash = hashlib.md5()
            total_size = 0
            async with aiofiles.open(local_path, 'rb') as src, aiofiles.open(file_path, 'wb') as dst:
                while True:
                    chunk = await src.read(8192)
                    if not chunk:
                        break
                    await dst.write(chunk)
                    md5_hash.update(chunk)
                    total_size += len(chunk)

            content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            file_info = {
                "file_name": file_path.name,
                "file_size": total_size,
                "content_type": content_type,
                "md5": md5_hash.hexdigest(),
                "download_time": datetime.now().isoformat()
            }
            logger.info(f"本地文件复制完成: {file_path.name} ({total_size} bytes)")
            return str(file_path), file_info

        # 处理 data URI: data:text/markdown;base64,xxx
        elif parsed.scheme == "data":
            import base64
            import re

            logger.info(f"[资源下载] 处理 data URI")

            # 解析 data URI: data:[<mediatype>][;base64],<data>
            # 示例: data:text/markdown;base64,SGVsbG8gV29ybGQ=
            match = re.match(r'data:([^;,]+)?(;base64)?,(.+)', url)
            if not match:
                raise HTTPException(status_code=400, detail="无效的 data URI 格式")

            content_type = match.group(1) or "text/plain"
            is_base64 = match.group(2) is not None
            data_part = match.group(3)

            # 解码数据
            if is_base64:
                try:
                    file_data = base64.b64decode(data_part)
                    logger.info(f"[资源下载] Base64解码成功，数据长度: {len(file_data)} bytes")
                except Exception as decode_error:
                    logger.error(f"[资源下载] Base64解码失败: {decode_error}")
                    raise HTTPException(status_code=400, detail=f"Base64解码失败: {str(decode_error)}")
            else:
                # URL编码的数据
                from urllib.parse import unquote
                file_data = unquote(data_part).encode('utf-8')
                logger.info(f"[资源下载] URL解码成功，数据长度: {len(file_data)} bytes")

            # 生成文件名（根据 MIME 类型）
            extension_map = {
                "text/markdown": ".md",
                "text/plain": ".txt",
                "application/pdf": ".pdf",
                "image/png": ".png",
                "image/jpeg": ".jpg",
            }
            file_ext = extension_map.get(content_type, ".dat")
            file_name = f"data_uri_{uuid.uuid4().hex[:12]}{file_ext}"
            file_path = temp_dir / file_name

            # 写入文件
            md5_hash = hashlib.md5()
            md5_hash.update(file_data)

            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_data)

            file_info = {
                "file_name": file_name,
                "file_size": len(file_data),
                "content_type": content_type,
                "md5": md5_hash.hexdigest(),
                "download_time": datetime.now().isoformat(),
                "source": "data_uri"
            }

            logger.info(f"[资源下载] data URI处理完成: {file_name} ({len(file_data)} bytes)")

            # ⚠️ 如果文件大小为0，记录警告
            if len(file_data) == 0:
                logger.warning(f"⚠️ data URI 解码后的文件大小为 0！可能是空文件或解码错误")

            return str(file_path), file_info

        else:
            raise HTTPException(status_code=400, detail=f"不支持的URL协议: {parsed.scheme}")

    except Exception as e:
        logger.error(f"[资源下载] 下载资源失败 - URL: {url}")
        logger.error(f"[资源下载] 错误类型: {type(e).__name__}")
        logger.error(f"[资源下载] 错误详情: {str(e)}")
        import traceback
        logger.error(f"[资源下载] 错误堆栈:\n{traceback.format_exc()}")
        raise


async def store_to_rag_system(
    resource_info: ResourceParseRequest,
    file_path: str,
    file_info: Dict[str, Any],
    db: Session
) -> str:
    """使用多模态服务存储到RAG系统"""
    try:
        logger.info(f"[存储RAG] 准备存储: resource_id={resource_info.id}, file={file_path}")
        logger.info(f"[存储RAG] collection_id={resource_info.classifyId}, title={resource_info.name}")

        # 使用多模态上传服务
        from app.services.multimodal_upload_service import process_multimodal_upload

        # 调用服务进行处理
        logger.info(f"[存储RAG] 调用多模态上传服务...")
        result = await process_multimodal_upload(
            file_path=file_path,
            content_type=file_info.get("content_type", "application/octet-stream"),
            user_id="system",
            db=db,
            title=resource_info.name,
            collection_id=resource_info.classifyId,
            parse_options=resource_info.parseOptions,
            resource_id=resource_info.id  # 传递资源ID
        )
        logger.info(f"[存储RAG] 多模态服务返回: success={result.get('success')}, result={result}")

        if result.get("success"):
            content_id = result.get("document_id") or result.get("content_id")
            if not content_id:
                logger.error(f"[存储RAG] 多模态服务返回缺少内容ID: {result}")
                raise Exception("多模态服务返回缺少内容ID")

            logger.info(f"[存储RAG] 获取到content_id={content_id}, 开始更新元数据...")

            # 更新资源特定的元数据
            content = db.query(RAGContent).filter(RAGContent.id == content_id).first()
            if content:
                logger.info(f"[存储RAG] 找到内容记录, 更新元数据和resource_id...")
                # 合并资源特定信息
                # ✅ 修复：JSON列从数据库读取时已经是dict，不需要json.loads
                existing_metadata = content.content_metadata if isinstance(content.content_metadata, dict) else {}
                resource_metadata = {
                    "resource_info": {
                        "resource_id": resource_info.id,
                        "resource_tags": resource_info.tags,
                        "resource_bindings": resource_info.bindings,
                        "original_url": resource_info.content.url
                    },
                    **file_info
                }

                existing_metadata.update(resource_metadata)
                # ✅ 修复：JSON列自动处理序列化，直接赋值字典即可
                content.content_metadata = existing_metadata

                # 更新关键字段
                content.resource_id = resource_info.id
                content.file_md5 = file_info.get("md5")
                from app.services.quill_files import retain_original
                retain_original(content, Path(file_path))

                # 更新权限绑定
                if resource_info.bindings:
                    content.bindings = resource_info.bindings

                db.commit()
                logger.info(f"[存储RAG] 内容元数据已更新: content_id={content_id}, resource_id={resource_info.id}")
                logger.info(f"[存储RAG] collection_id={content.vector_collection}, status={content.status}")
            else:
                logger.warning(f"[存储RAG] 未找到content_id={content_id}的内容记录")

            return content_id
        else:
            error_msg = result.get("error", "多模态服务处理失败")
            logger.error(f"[存储RAG] 多模态服务失败: {error_msg}")
            raise Exception(error_msg)

    except Exception as e:
        logger.exception(f"[存储RAG] 存储到RAG系统失败: {e}")
        db.rollback()  # 回滚事务，避免会话处于异常状态
        raise


async def process_batch_resources_real(
    batch_id: str,
    resources: List[ResourceParseRequest],
    db: Session
):
    """批量资源处理的实际执行函数"""
    try:
        logger.info(f"开始处理批量任务: {batch_id}, 资源数量: {len(resources)}")

        # 更新任务状态
        BATCH_TASKS[batch_id]["status"] = "processing"

        # 创建新的数据库会话（后台任务）
        from app.db.session import SessionLocal
        db = SessionLocal()

        # 并发控制
        max_concurrent = 3
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_single_resource(resource: ResourceParseRequest):
            async with semaphore:
                resource_id = resource.id
                # 为每个资源创建独立的数据库会话
                from app.db.session import SessionLocal
                resource_db = SessionLocal()

                try:
                    logger.info(f"[单个资源处理] 开始处理资源: {resource_id} - {resource.name}")
                    logger.info(f"[单个资源处理] URL: {resource.content.url}")
                    logger.info(f"[单个资源处理] URL长度: {len(resource.content.url)}")

                    # 更新状态
                    BATCH_TASKS[batch_id]["resources"][resource_id] = {
                        "status": "processing",
                        "message": "正在处理..."
                    }
                    BATCH_TASKS[batch_id]["processing"] += 1

                    # 确保集合存在
                    collection_created = await ensure_collection_exists(resource.classifyId, resource_db)
                    if not collection_created:
                        raise Exception(f"集合创建失败: {resource.classifyId}")

                    # MD5校验 - 已禁用，允许用户重新生成
                    # 用户主动发起的重新生成请求应该被处理
                    # 下载文件
                    BATCH_TASKS[batch_id]["resources"][resource_id]["message"] = "正在下载..."
                    logger.info(f"[{resource_id}] 开始下载文件: {resource.content.url}")
                    file_path, file_info = await download_and_validate_resource(resource.content.url)
                    logger.info(f"[{resource_id}] 文件下载成功: {file_path}, 大小: {file_info.get('file_size')} bytes")

                    # 验证MD5
                    if resource.content.md5 and file_info.get("md5") != resource.content.md5:
                        logger.error(f"[{resource_id}] MD5校验失败: 期望={resource.content.md5}, 实际={file_info.get('md5')}")
                        Path(file_path).unlink(missing_ok=True)
                        raise Exception(f"MD5校验失败")
                    logger.info(f"[{resource_id}] MD5校验通过")

                    # 存储到RAG系统
                    BATCH_TASKS[batch_id]["resources"][resource_id]["message"] = "正在解析存储..."
                    logger.info(f"[{resource_id}] 开始存储到RAG系统, collection_id={resource.classifyId}")
                    content_id = await store_to_rag_system(
                        resource_info=resource,
                        file_path=file_path,
                        file_info=file_info,
                        db=resource_db
                    )
                    logger.info(f"[{resource_id}] RAG存储成功, content_id={content_id}")

                    # ✅ 查询文档详细信息
                    content_info = None
                    try:
                        content_record = resource_db.query(RAGContent).filter(RAGContent.id == content_id).first()
                        if content_record:
                            # 处理 tags（可能是JSON数组或字符串）
                            tags = content_record.content_tags
                            if isinstance(tags, str):
                                try:
                                    tags = json.loads(tags)
                                except:
                                    tags = [t.strip() for t in tags.split(',') if t.strip()] if tags else []
                            elif not tags:
                                tags = []

                            content_info = {
                                "resource_id": content_record.resource_id,
                                "content_id": content_record.id,
                                "title": content_record.title,
                                "summary": content_record.content_summary,  # ✅ 添加摘要
                                "tags": tags,  # ✅ 添加标签
                                "collection_id": content_record.vector_collection,
                                "resource_type": content_record.resource_type,
                                "file_name": content_record.file_name,
                                "file_size": content_record.file_size,
                                "mime_type": content_record.mime_type,
                                "status": content_record.status,
                                "create_time": content_record.create_time.isoformat() if content_record.create_time else None
                            }
                    except Exception as info_error:
                        logger.warning(f"[{resource_id}] 获取文档详细信息失败: {info_error}")

                    # 清理临时文件
                    Path(file_path).unlink(missing_ok=True)

                    # 更新成功状态（包含详细信息）
                    BATCH_TASKS[batch_id]["resources"][resource_id] = {
                        "status": "completed",
                        "message": "处理成功",
                        "content_id": content_id,
                        "content_info": content_info  # ✅ 添加文档详细信息
                    }
                    BATCH_TASKS[batch_id]["processing"] -= 1
                    BATCH_TASKS[batch_id]["completed"] += 1

                    logger.info(f"资源 {resource.name} 处理成功")
                    return {
                        "resource_id": resource_id,
                        "content_id": content_id,
                        "content_info": content_info,  # ✅ 返回结果中也包含详细信息
                        "status": "success"
                    }

                except Exception as e:
                    # 处理失败
                    BATCH_TASKS[batch_id]["resources"][resource_id] = {
                        "status": "failed",
                        "message": f"处理失败: {str(e)}"
                    }
                    BATCH_TASKS[batch_id]["processing"] -= 1
                    BATCH_TASKS[batch_id]["failed"] += 1

                    logger.error(f"资源 {resource.name} 处理失败: {e}")
                    resource_db.rollback()  # 回滚失败的事务
                    return {
                        "resource_id": resource_id,
                        "status": "failed",
                        "error": str(e)
                    }
                finally:
                    # 关闭资源独立的数据库会话
                    try:
                        resource_db.close()
                    except:
                        pass

        # 并发处理所有资源
        tasks = [process_single_resource(resource) for resource in resources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 保存结果
        BATCH_TASKS[batch_id]["results"] = [
            r for r in results if not isinstance(r, Exception)
        ]

        # 更新最终状态
        BATCH_TASKS[batch_id]["status"] = "completed"
        BATCH_TASKS[batch_id]["end_time"] = datetime.now()

        logger.info(f"批量处理完成: {batch_id}")

    except Exception as e:
        logger.error(f"批量处理异常: {e}")
        BATCH_TASKS[batch_id]["status"] = "failed"
        BATCH_TASKS[batch_id]["error"] = str(e)
    finally:
        try:
            db.close()
        except:
            pass


@router.post("/batch-parse")
async def batch_parse_resources(
    request: BatchResourceParseRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    批量解析资源接口

    支持并发下载和解析多个资源文件，自动创建集合，追踪处理进度
    """
    try:
        batch_id = str(uuid.uuid4())
        logger.info(f"启动批量解析任务: {batch_id}, 资源数量: {len(request.resources)}")

        # 记录每个资源的URL
        for idx, resource in enumerate(request.resources):
            logger.info(f"[批量解析] 资源{idx+1} - ID: {resource.id}, 名称: {resource.name}")
            logger.info(f"[批量解析] 资源{idx+1} - URL: {resource.content.url}")
            logger.info(f"[批量解析] 资源{idx+1} - URL长度: {len(resource.content.url)}")
            if len(resource.content.url) < 200:
                logger.info(f"[批量解析] 资源{idx+1} - 完整URL: {resource.content.url}")
            else:
                logger.info(f"[批量解析] 资源{idx+1} - URL前100字符: {resource.content.url[:100]}")
                logger.info(f"[批量解析] 资源{idx+1} - URL后100字符: {resource.content.url[-100:]}")

        # 初始化任务状态
        BATCH_TASKS[batch_id] = {
            "batch_id": batch_id,
            "status": "started",
            "total": len(request.resources),
            "completed": 0,
            "failed": 0,
            "processing": 0,
            "start_time": datetime.now(),
            "resources": {
                resource.id: {"status": "pending", "message": "等待处理"}
                for resource in request.resources
            },
            "results": []
        }

        # 启动后台处理
        background_tasks.add_task(
            process_batch_resources_real,
            batch_id=batch_id,
            resources=request.resources,
            db=db
        )

        return ResponseHelper.success(
            result={
                "batch_id": batch_id,
                "total_resources": len(request.resources),
                "status": "started",
                "message": "批量解析任务已启动"
            },
            message="批量解析任务已启动"
        )

    except Exception as e:
        logger.error(f"批量解析启动失败: {e}")
        return ResponseHelper.error(f"启动失败: {str(e)}", status=500)


@router.post("/batch-status")
async def get_batch_status(request: BatchStatusRequest, db: Session = Depends(get_db)):
    """
    获取批量处理状态

    返回任务整体进度和每个资源的处理状态
    """
    try:
        batch_id = request.batch_id

        if batch_id not in BATCH_TASKS:
            return ResponseHelper.error("批量任务不存在", status=404)

        task_info = BATCH_TASKS[batch_id]

        # 计算进度
        total = task_info["total"]
        completed = task_info["completed"]
        failed = task_info["failed"]
        processing = task_info["processing"]
        progress = (completed + failed) / total * 100 if total > 0 else 0

        # 构建资源状态列表
        resource_statuses = []
        for resource_id, resource_status in task_info["resources"].items():
            status_info = {
                "id": resource_id,
                "status": resource_status["status"],
                "message": resource_status.get("message", ""),
                "content_id": resource_status.get("content_id")
            }
            # ✅ 添加文档详细信息（如果存在）
            if "content_info" in resource_status and resource_status["content_info"]:
                status_info["content_info"] = resource_status["content_info"]

            resource_statuses.append(status_info)

        result = {
            "batch_id": batch_id,
            "status": task_info["status"],
            "total": total,
            "completed": completed,
            "failed": failed,
            "processing": processing,
            "progress": round(progress, 1),
            "start_time": task_info["start_time"].isoformat(),
            "end_time": task_info.get("end_time", "").isoformat() if task_info.get("end_time") else None,
            "resources": resource_statuses,
            "results": task_info.get("results", [])
        }

        return ResponseHelper.success(
            result=result,
            message="批量状态获取成功"
        )

    except Exception as e:
        logger.error(f"获取批量状态失败: {e}")
        return ResponseHelper.error(f"获取状态失败: {str(e)}", status=500)


class MarkdownFetchRequest(BaseModel):
    """获取资源Markdown全文请求"""
    resource_id: str = Field(..., description="资源ID")
    collection_id: Optional[str] = Field(None, description="可选的集合ID，用于限定范围")
    include_metadata: Optional[bool] = Field(False, description="是否同时返回metadata")


@router.post("/markdown")
async def get_resource_markdown(
    request: MarkdownFetchRequest,
    db: Session = Depends(get_db)
):
    """
    获取解析后的Markdown全文

    根据资源ID获取已解析的Markdown内容，支持：
    - 获取纯文本内容
    - 可选返回元数据
    - 支持多集合场景下的集合筛选
    """
    try:
        resource_id = request.resource_id
        collection_id = request.collection_id
        include_metadata = request.include_metadata or False

        if not resource_id or not resource_id.strip():
            return ResponseHelper.error("resource_id 不能为空", status=400)

        # 查询内容
        query = db.query(RAGContent).filter(RAGContent.resource_id == resource_id)
        if collection_id:
            query = query.filter(RAGContent.vector_collection == collection_id)

        content_obj = query.order_by(RAGContent.update_time.desc()).first()
        if not content_obj:
            return ResponseHelper.error("未找到资源对应的内容", status=404)

        # 解析标签
        raw_tags = content_obj.content_tags
        if isinstance(raw_tags, str):
            try:
                parsed_tags = json.loads(raw_tags)
            except Exception:
                parsed_tags = [t.strip() for t in raw_tags.split(',') if t.strip()] if raw_tags else []
        else:
            parsed_tags = raw_tags or []

        # 解析元数据
        try:
            meta = content_obj.content_metadata if isinstance(content_obj.content_metadata, dict) else (
                json.loads(content_obj.content_metadata) if content_obj.content_metadata else {}
            )
        except Exception:
            meta = {}

        file_type = (meta.get("file_type") if isinstance(meta, dict) else None) or content_obj.content_type or content_obj.mime_type

        result = {
            "resource_id": content_obj.resource_id,
            "content_id": content_obj.id,
            "collection_id": content_obj.vector_collection,
            "file_name": content_obj.file_name,
            "title": content_obj.title,
            "summary": content_obj.content_summary,
            "tags": parsed_tags,
            "file_type": file_type,
            "markdown_content": content_obj.content_text or "",
        }

        if include_metadata:
            result["metadata"] = meta

        return ResponseHelper.success(
            result=result,
            message="获取Markdown内容成功"
        )

    except Exception as e:
        logger.error(f"获取资源Markdown失败: {e}")
        return ResponseHelper.error(f"查询失败: {str(e)}", status=500)
