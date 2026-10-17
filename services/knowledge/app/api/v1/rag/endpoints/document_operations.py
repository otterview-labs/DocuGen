#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档操作API接口
提供文档的更新、删除、下载、复制、移动等操作
"""

from app.shared.utils.logger_util import get_logger

logger = get_logger(__name__)

from typing import Dict, Optional, List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import false
from pathlib import Path
import os
import json
import io
from sqlalchemy import func, or_

from app.db.session import get_db
from app.api.v1.deps import get_optional_request_user, get_request_user, is_auth_enforced
from app.db.models.rag import RAGContent, RAGResourceRelation, RAGChunk, RAGCollectionContent, RAGCollection
from app.db.models.user import User
from app.db.models.operation_log import OperationLog, OperationType, ResourceType, OperationStatus
from app.schemas.documents import (
    BatchDeleteRequest,
    BatchToggleStatusRequest,
    DocumentDeleteRequest,
    DocumentDownloadRequest,
    DocumentDuplicateRequest,
    DocumentGetRequest,
    DocumentMoveRequest,
    DocumentUpdateRequest,
    RelationItem,
    ReindexRequest,
)
from app.shared.response_models import ResponseHelper
from app.schemas.pagination import PageRequest, StandardResponse
from app.shared.helpers.pagination import paginate_and_response
from app.services.enhanced_rag_service import get_enhanced_rag_service
from app.core.rag.vector_db import get_vector_db
import time

router = APIRouter()


def _apply_document_read_access_filter(query, current_user: Optional[User] = None):
    if current_user:
        return query.filter(
            (RAGContent.user_id == str(current_user.id)) |
            (RAGContent.is_public == True)
        )
    if is_auth_enforced():
        return query.filter(RAGContent.is_public == True)
    return query


def _apply_document_owner_filter(query, current_user: Optional[User] = None):
    if current_user:
        return query.filter(RAGContent.user_id == str(current_user.id))
    if is_auth_enforced():
        return query.filter(false())
    return query


def _build_document_read_query(db: Session, document_id: str, current_user: Optional[User] = None):
    query = db.query(RAGContent).filter((RAGContent.id == document_id) | (RAGContent.resource_id == document_id))
    return _apply_document_read_access_filter(query, current_user)


def _build_owned_document_query(db: Session, document_id: str, current_user: Optional[User] = None):
    query = db.query(RAGContent).filter((RAGContent.id == document_id) | (RAGContent.resource_id == document_id))
    return _apply_document_owner_filter(query, current_user)

def _resolve_existing_file_path(file_path: Optional[str]) -> Optional[Path]:
    """
    将数据库中的 file_path 解析为磁盘可读的绝对路径（若存在）。
    - DB 里既可能存相对路径(如 storage/static/...)也可能存绝对路径。
    - 兼容历史数据：尝试按 basename 在常见上传目录中回退查找。
    """
    if not file_path:
        return None

    try:
        from app.config import settings
    except Exception:
        settings = None

    raw = str(file_path).strip()
    if not raw:
        return None

    p = Path(raw)
    if p.is_absolute() and p.exists():
        return p

    # 1) 相对项目根目录（jetlinks-knowledge）解析
    if settings:
        project_root = Path(settings.storage.STORAGE_ROOT).parent
        candidate = (project_root / p).resolve()
        if candidate.exists():
            return candidate

    # 2) 相对当前工作目录解析（兜底）
    candidate = Path(os.getcwd()) / p
    if candidate.exists():
        return candidate.resolve()

    # 3) 按文件名在常见目录中搜索（兼容旧数据）
    basename = p.name
    if not basename:
        return None

    candidate_dirs: List[Path] = []
    if settings:
        candidate_dirs.extend([
            Path(settings.storage.STATIC_DIR) / "uploads",
            Path(settings.storage.UPLOADS_DIR),
            Path(settings.storage.TEMP_DIR),
        ])

    # 额外兜底（避免 settings 读取失败）
    candidate_dirs.append(Path("storage/static/uploads").resolve())

    for d in candidate_dirs:
        try:
            fp = d / basename
            if fp.exists():
                return fp.resolve()
        except Exception:
            continue

    return None


def _to_public_url(abs_path: Path) -> Optional[str]:
    """
    将磁盘路径转换为可访问URL。
    - 用户上传文件：优先映射为 `/uploads/...`（支持子路径，如 temp/xxx）
    - 静态资源：回退为 `/static/...`
    """
    try:
        from app.config import settings
        static_dir = Path(settings.storage.STATIC_DIR).resolve()
        p = abs_path.resolve()
        uploads_root = (static_dir / "uploads").resolve()
        try:
            rel_upload = p.relative_to(uploads_root).as_posix()
            return f"/uploads/{rel_upload}"
        except ValueError:
            pass
        try:
            rel = p.relative_to(static_dir).as_posix()
        except ValueError:
            return None
        return f"/static/{rel}"
    except Exception:
        pass
    return None


def _safe_download_filename(name: str, fallback: str) -> str:
    name = (name or "").strip()
    if not name:
        return fallback
    # 防止路径穿越
    return os.path.basename(name)


# 添加通用文档查询接口
@router.post("")
async def list_all_documents(
    page_request: PageRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_request_user),
):
    """
    获取所有文档列表（标准分页格式）

    返回系统中的所有文档，支持分页和筛选。
    """
    try:
        # 构建基础查询
        query = _apply_document_read_access_filter(db.query(RAGContent), current_user)

        # 如果请求中包含collection_id，添加筛选条件
        if hasattr(page_request, 'collection_id') and page_request.collection_id:
            query = query.filter(RAGContent.vector_collection == page_request.collection_id)

        # 数据转换函数
        def _get_version(meta):
            try:
                data = json.loads(meta) if meta and isinstance(meta, str) else (meta or {})
                return int(data.get("version", 1))
            except Exception:
                return 1

        def transform_document(doc: RAGContent) -> dict:
            return {
                "resource_id": doc.resource_id,
                "collection_id": doc.vector_collection,
                "version": _get_version(doc.content_metadata),
                "name": doc.title,
                "description": doc.description,
                "type": doc.content_type,
                "status": doc.status,
                "processing_status": doc.processing_status,
                "processing_message": doc.processing_message,
                "upload_type": "本地上传",
                "created_at": int(doc.create_time.timestamp() * 1000) if doc.create_time else None,
                "tags": (doc.content_tags if not isinstance(doc.content_tags, str)
                         else (json.loads(doc.content_tags) if doc.content_tags else ["文档"])),
                "summary": doc.content_summary,
                "file_size": doc.file_size,
                "file_name": doc.file_name,
                "mime_type": doc.mime_type,
                "debug": {"internal": {"content_id": doc.id}}
            }

        # 使用标准分页
        return paginate_and_response(
            db=db,
            model_class=RAGContent,
            page_request=page_request,
            base_query=query,
            item_transformer=transform_document,
            message="获取文档列表成功"
        )

    except Exception as e:
        return ResponseHelper.error_response(
            message=f"获取文档列表失败: {str(e)}",
            status=500
        )


@router.post("/reindex", response_model=Dict)
async def rebuild_embeddings(
    request: ReindexRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_request_user),
):
    """
    为已有文档执行一次向量重建（写入 Milvus/FAISS）。
    - 默认仅处理 content_text 非空、状态为启用(status=1) 的文档。
    - 可按集合过滤。
    - 不会删除旧向量，但会回写首个 vector_id 以便兼容旧字段。
    """
    try:
        q = _apply_document_owner_filter(
            db.query(RAGContent).filter(RAGContent.status == "1"),
            current_user,
        )
        if request.collection_id:
            q = q.filter(RAGContent.vector_collection == request.collection_id)
        # 只处理有文本内容的记录
        q = q.filter(RAGContent.content_text.isnot(None))
        docs = q.order_by(RAGContent.create_time.desc()).limit(request.limit or 200).all()

        rag = get_enhanced_rag_service()
        ok = 0
        fail = 0
        errors: List[Dict[str, str]] = []

        for d in docs:
            try:
                success = await rag.add_document_to_vector_db(d, db)
                if success:
                    ok += 1
                else:
                    fail += 1
                    errors.append({"id": d.id, "reason": "add_document_to_vector_db returned False"})
            except Exception as e:
                fail += 1
                errors.append({"id": d.id, "reason": str(e)})

        return ResponseHelper.success_response(
            result={
                "requested_collection": request.collection_id,
                "processed": len(docs),
                "ok": ok,
                "failed": fail,
                "errors": errors[:20]  # 最多返回前20条错误详情
            },
            message="重建完成"
        )
    except Exception as e:
        return ResponseHelper.error_response(message=f"重建失败: {e}", status=500)


@router.post("/update", response_model=Dict)
async def update_document(
    request: DocumentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_request_user),
):
    """
    更新文档信息

    更新文档的标题、描述、标签等元数据信息。
    """
    try:
        # 查找文档
        # 兼容以内容ID或资源ID更新：优先内容ID，不存在则按resource_id选最新版本
        owner_query = _apply_document_owner_filter(db.query(RAGContent), current_user)
        document = owner_query.filter(RAGContent.id == request.document_id).first()
        if not document:
            document = owner_query.filter(
                RAGContent.resource_id == request.document_id
            ).order_by(RAGContent.update_time.desc()).first()

        if not document:
            return ResponseHelper.error_response(
                message=f"文档不存在: {request.document_id}",
                status=404
            )

        # 更新字段
        if request.title is not None:
            document.title = request.title
        if request.description is not None:
            document.description = request.description
        if request.tags is not None:
            # 直接存 List，更自然；兼容字符串时尝试解析
            if isinstance(request.tags, str):
                try:
                    document.content_tags = json.loads(request.tags)
                except Exception:
                    document.content_tags = [request.tags]
            else:
                document.content_tags = list(request.tags)
            document.tags_manually_modified = True
        if request.bindings is not None:
            # 覆盖原值
            document.bindings = request.bindings

        # 同步资源关系（替换策略）
        if request.relation is not None:
            try:
                import uuid as _uuid
                source_resource_id = document.resource_id  # 确认所有文档存在 resource_id
                # 删除旧关系
                db.query(RAGResourceRelation).filter(
                    RAGResourceRelation.source_resource_id == source_resource_id
                ).delete()
                # 插入新关系
                for item in request.relation:
                    rel = RAGResourceRelation(
                        id=str(_uuid.uuid4()),
                        source_resource_id=source_resource_id,
                        target_type=item.type,
                        target_id=item.id,
                        confidence=item.confidence,
                        relation_desc=item.relation,
                        expands=item.expands,
                        status="1"
                    )
                    db.add(rel)
            except Exception as rel_err:
                logger.warning(f"更新资源关系失败: {rel_err}")

        db.commit()
        db.refresh(document)

        # 元数据（title/desc/tags/summary）变更后，同步更新 doc-profile 向量（用于候选文档语义排序）
        try:
            rag_service = get_enhanced_rag_service()
            await rag_service.upsert_doc_profile_vector(document)
        except Exception as e:
            logger.warning(f"更新文档概要向量失败（已忽略）: {e}")

        # 解析版本
        try:
            meta = document.content_metadata
            meta_obj = meta if isinstance(meta, dict) else (json.loads(meta) if meta else {})
            version = int(meta_obj.get("version", 1))
        except Exception:
            version = 1

        return ResponseHelper.success_response(
            result={
                "resource_id": document.resource_id,
                "collection_id": document.vector_collection,
                "version": version,
                "title": document.title,
                "description": document.description,
                "tags": (document.content_tags if not isinstance(document.content_tags, str)
                          else (json.loads(document.content_tags) if document.content_tags else [])),
                "bindings": document.bindings,
                "debug": {"internal": {"content_id": document.id}}
            },
            message="文档更新成功"
        )

    except Exception as e:
        db.rollback()
        return ResponseHelper.error_response(
            message=f"更新文档失败: {str(e)}",
            status=500
        )


@router.post("/delete", response_model=Dict)
async def delete_document(
    request: DocumentDeleteRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_request_user),
):
    """
    删除文档

    删除指定的文档记录和相关文件（级联删除所有关联数据）。
    """
    start_time = time.time()
    document = None
    operation_status = OperationStatus.FAILED
    error_msg = None
    delete_result = {}

    try:
        # 查找文档
        owner_query = _apply_document_owner_filter(db.query(RAGContent), current_user)
        document = owner_query.filter(RAGContent.id == request.document_id).first()
        if not document:
            document = owner_query.filter(
                RAGContent.resource_id == request.document_id
            ).order_by(RAGContent.update_time.desc()).first()

        if not document:
            # 资源不存在：返回 205，带可机判的错误码
            error_msg = "文档不存在或已被删除"

            # 记录操作日志（失败）
            _log_operation(
                db=db,
                operation_type=OperationType.DELETE,
                resource_type=ResourceType.DOCUMENT,
                resource_id=request.document_id,
                resource_name="未知文档",
                status=OperationStatus.FAILED,
                details={"error": error_msg},
                error_message=error_msg,
                duration_ms=int((time.time() - start_time) * 1000)
            )
            db.commit()

            return ResponseHelper.reset_content_response(
                result={
                    "resource_id": request.document_id,
                    "deleted": False,
                    "error_code": "RESOURCE_NOT_FOUND",
                    "message": error_msg
                },
                message=error_msg
            )

        # 保存删除前状态
        before_state = {
            "id": document.id,
            "resource_id": document.resource_id,
            "title": document.title,
            "file_path": document.file_path,
            "vector_collection": document.vector_collection
        }

        # 使用级联删除
        delete_result = await _cascade_delete_document(document, db, delete_files=True)

        # 提交事务
        db.commit()

        # 确定操作状态
        if delete_result.get("errors"):
            operation_status = OperationStatus.PARTIAL
            error_msg = "; ".join(delete_result["errors"])
        else:
            operation_status = OperationStatus.SUCCESS

        # 计算耗时
        duration_ms = int((time.time() - start_time) * 1000)

        # 记录操作日志（成功或部分成功）
        _log_operation(
            db=db,
            operation_type=OperationType.DELETE,
            resource_type=ResourceType.DOCUMENT,
            resource_id=before_state["id"],
            resource_name=before_state["title"],
            status=operation_status,
            details=delete_result,
            error_message=error_msg,
            duration_ms=duration_ms,
            collection_id=before_state["vector_collection"],
            before_state=before_state
        )
        db.commit()

        # 解析版本
        try:
            _meta = before_state.get("content_metadata", {})
            _meta_obj = _meta if isinstance(_meta, dict) else (json.loads(_meta) if _meta else {})
            _ver = int(_meta_obj.get("version", 1))
        except Exception:
            _ver = 1

        return ResponseHelper.success_response(
            result={
                "resource_id": before_state["resource_id"],
                "collection_id": before_state["vector_collection"],
                "version": _ver,
                "debug": {
                    "internal": {
                        "content_id": before_state["id"],
                        "delete_details": delete_result
                    }
                }
            },
            message="文档删除成功"
        )

    except Exception as e:
        db.rollback()
        error_msg = str(e)
        duration_ms = int((time.time() - start_time) * 1000)

        # 记录操作日志（失败）
        try:
            _log_operation(
                db=db,
                operation_type=OperationType.DELETE,
                resource_type=ResourceType.DOCUMENT,
                resource_id=request.document_id,
                resource_name=document.title if document else "未知文档",
                status=OperationStatus.FAILED,
                details=delete_result if delete_result else {"error": error_msg},
                error_message=error_msg,
                duration_ms=duration_ms
            )
            db.commit()
        except Exception as log_err:
            logger.error(f"记录删除失败日志时出错: {log_err}")

        return ResponseHelper.error_response(
            message=f"删除文档失败: {error_msg}",
            status=500
        )


# @router.post("/download", response_model=Dict)
# async def download_document_post(
#     request: Dict,
#     db: Session = Depends(get_db)
# ):
#     """
#     下载文档文件（POST方式）

#     提供文档文件的下载功能，使用POST请求传参。

#     **请求示例：**
#     ```bash
#     curl -X POST 'http://localhost:8000/api/v1/rag/documents/download' \
#       -H 'Content-Type: application/json' \
#       -d '{"document_id": "your-document-id"}'
#     ```
#     """
#     try:
#         document_id = request.get("document_id")
#         if not document_id:
#             return ResponseHelper.error(
#                 message="缺少必要参数: document_id",
#                 status=400
#             )

        # 查找文档
#         document = db.query(RAGContent).filter(
#             RAGContent.id == document_id
#         ).first()

#         if not document:
#             return ResponseHelper.error(
#                 message=f"文档不存在: {document_id}",
#                 status=404
#             )

#         if not document.file_path or not os.path.exists(document.file_path):
#             return ResponseHelper.error(
#                 message="文档文件不存在或已被删除",
#                 status=404
#             )

        # 返回文件响应
#         return FileResponse(
#             path=document.file_path,
#             filename=document.file_name or f"document_{document_id}",
#             media_type=document.mime_type or "application/octet-stream"
#         )

#     except Exception as e:
#         return ResponseHelper.error(
#             message=f"下载文档失败: {str(e)}",
#             status=500
#         )


async def _download_document_internal(document_id: str, db: Session, current_user: Optional[User] = None):
    document = _build_document_read_query(db, document_id, current_user).first()
    if not document:
        raise HTTPException(status_code=404, detail=f"文档不存在: {document_id}")

    fp = _resolve_existing_file_path(document.file_path)
    if fp and fp.exists():
        filename = _safe_download_filename(
            document.file_name or fp.name,
            fallback=f"document_{document_id}",
        )
        media_type = document.mime_type or "application/octet-stream"
        return FileResponse(path=str(fp), filename=filename, media_type=media_type)

    # 文件不存在时：对文本类内容提供“可下载”的降级（至少能看到内容）
    if document.content_text:
        filename = _safe_download_filename(
            document.file_name or f"document_{document_id}.txt",
            fallback=f"document_{document_id}.txt",
        )
        if not os.path.splitext(filename)[1]:
            filename = filename + ".txt"
        data = document.content_text.encode("utf-8")
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return StreamingResponse(io.BytesIO(data), media_type="text/plain; charset=utf-8", headers=headers)

    raise HTTPException(status_code=404, detail="文档文件不存在且无可回退的文本内容")


@router.get("/raw/{document_id}", summary="获取文档原文（文本回退）")
async def get_document_raw(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_request_user),
):
    """
    返回文档的原始/提取文本（text/plain）。
    - 优先返回数据库中的 content_text
    - 若 content_text 为空且文件存在，则返回文件内容（由浏览器按类型决定渲染/下载）
    """
    document = _build_document_read_query(db, document_id, current_user).first()
    if not document:
        raise HTTPException(status_code=404, detail=f"文档不存在: {document_id}")

    if document.content_text:
        return PlainTextResponse(document.content_text, media_type="text/plain; charset=utf-8")

    fp = _resolve_existing_file_path(document.file_path)
    if fp and fp.exists():
        media_type = document.mime_type or "application/octet-stream"
        return FileResponse(path=str(fp), filename=fp.name, media_type=media_type)

    raise HTTPException(status_code=404, detail="无可展示原文")


@router.get("/download", summary="下载文档（GET）")
async def download_document_get(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_request_user),
):
    """支持直接点击下载链接：`/api/v1/rag/documents/download?document_id=...`"""
    return await _download_document_internal(document_id, db, current_user)


@router.post("/download", summary="下载文档（POST）")
async def download_document_post(
    request: DocumentDownloadRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_request_user),
):
    """兼容旧页面：POST JSON `{document_id: ...}`"""
    return await _download_document_internal(request.document_id, db, current_user)


@router.post("/get", response_model=Dict)
async def get_document_by_post(
    request: DocumentGetRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_request_user),
):
    """
    获取单个文档详情（POST方法）

    根据文档ID获取文档的详细信息，包括内容、元数据等。
    支持Markdown格式内容显示，图片和视频返回访问路径。

    **请求示例：**
    ```bash
    curl -X POST "http://localhost:8006/api/v1/rag/documents/get" \
      -H "Content-Type: application/json" \
      -d '{"document_id": "doc_123456"}'
    ```
    """
    return await _get_document_internal(request.document_id, db, current_user)


async def _get_document_internal(document_id: str, db: Session, current_user):
    """内部文档获取逻辑，供GET和POST方法共用"""
    try:
        # 查找文档
        document = _build_document_read_query(db, document_id, current_user).first()

        if not document:
            return ResponseHelper.error_response(
                message=f"文档不存在: {document_id}",
                status=404
            )

        # 根据文档类型处理内容显示
        content_data = {}
        display_content = ""
        file_url = None

        # 处理文本内容
        if document.content_text:
            # 判断是否为Markdown格式
            if document.file_name and document.file_name.endswith('.md'):
                content_data = {
                    "text": document.content_text,
                    "format": "markdown"
                }
                display_content = document.content_text
            else:
                content_data = {
                    "text": document.content_text,
                    "format": "plain"
                }
                display_content = document.content_text

        # 处理文件路径和URL（兼容历史数据：文件可能已清理 / 路径可能不在 static 下）
        resolved_fp = _resolve_existing_file_path(document.file_path)
        if resolved_fp:
            file_url = _to_public_url(resolved_fp)

        # 优先尝试使用 static/uploads 下的同名文件（常见：文件已被复制到公开目录）
        if not file_url and document.file_name:
            public_fp = _resolve_existing_file_path(f"storage/static/uploads/{document.file_name}")
            if public_fp:
                file_url = _to_public_url(public_fp)

        if not file_url and document.file_path:
            basename = os.path.basename(document.file_path)
            if basename:
                public_fp = _resolve_existing_file_path(f"storage/static/uploads/{basename}")
                if public_fp:
                    file_url = _to_public_url(public_fp)

        # 若文件不存在但有文本内容，则提供可访问的文本回退URL（避免“原文件 404”）
        # 注意：图片/视频不应降级到文本URL，否则前端会尝试以媒体方式渲染失败
        if not file_url and document.content_text and document.content_type not in ("image", "video"):
            file_url = f"/api/v1/rag/documents/raw/{document.id}"

        # 图片/视频优先按URL渲染
        if file_url and document.content_type == "image":
            display_content = f"![{document.title or document.file_name}]({file_url})"
            content_data = {
                "type": "image",
                "url": file_url,
                "alt": document.title or document.file_name
            }
        elif file_url and document.content_type == "video":
            display_content = f"视频文件：{document.file_name}\n访问路径：{file_url}"
            content_data = {
                "type": "video",
                "url": file_url,
                "title": document.title or document.file_name
            }

        # 如果没有文本内容，根据文档类型提供默认显示
        if not display_content:
            if document.content_type == "image":
                display_content = f"图片文件：{document.file_name or '未知'}"
            elif document.content_type == "video":
                display_content = f"视频文件：{document.file_name or '未知'}"
            elif document.content_type == "document":
                display_content = f"文档文件：{document.file_name or '未知'}"
            else:
                display_content = "暂无内容"

        # 构建完整响应
        result = {
            "id": document.id,
            "title": document.title,
            "description": document.description,
            "content_type": document.content_type,

            # 内容相关
            "content": content_data,
            "display_content": display_content,
            "raw_content": document.content_text,  # 原始文本内容

            # 元数据
            "summary": document.content_summary,
            "tags": (document.content_tags if not isinstance(document.content_tags, str)
                      else (json.loads(document.content_tags) if document.content_tags else [])),

            # 文件信息
            "file_info": {
                "name": document.file_name,
                "size": document.file_size,
                "mime_type": document.mime_type,
                "path": document.file_path,
                "url": file_url,
                "download_url": f"/api/v1/rag/documents/download?document_id={document.id}"
            },

            # 系统信息
            "collection_id": document.vector_collection,
            "status": document.status,
            "processing_status": document.processing_status,
            "processing_message": document.processing_message,
            "create_time": document.create_time.isoformat() if document.create_time else None,
            "update_time": document.update_time.isoformat() if document.update_time else None,
            "user_id": document.user_id
        }

        return ResponseHelper.success_response(
            result=result,
            message="获取文档详情成功"
        )

    except Exception as e:
        return ResponseHelper.error_response(
            message=f"获取文档失败: {str(e)}",
            status=500
        )


@router.post("/batch-toggle-status")
async def batch_toggle_status(
    request: BatchToggleStatusRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_request_user),
):
    """
    批量启用/禁用资源

    支持按资源ID或集合ID批量操作资源状态
    """
    try:
        results = []
        success_count = 0
        failed_count = 0

        if request.target_type == "resource_ids":
            # 按资源ID批量操作
            for resource_id in request.targets:
                try:
                    document = _build_owned_document_query(db, resource_id, current_user).first()
                    if not document:
                        results.append({
                            "id": resource_id,
                            "status": "failed",
                            "message": "资源不存在",
                            "error_code": "RESOURCE_NOT_FOUND"
                        })
                        failed_count += 1
                        continue

                    # 更新状态
                    new_status = "1" if request.action == "enable" else "0"
                    document.status = new_status
                    document.update_time = func.now()

                    results.append({
                        "id": resource_id,
                        "status": "success",
                        "action": request.action,
                        "new_status": new_status,
                        "name": document.title
                    })
                    success_count += 1

                except Exception as e:
                    results.append({
                        "id": resource_id,
                        "status": "failed",
                        "message": str(e)
                    })
                    failed_count += 1

        elif request.target_type == "collection_id":
            # 按集合ID批量操作
            for collection_id in request.targets:
                try:
                    documents = _apply_document_owner_filter(
                        db.query(RAGContent).filter(
                            RAGContent.vector_collection == collection_id
                        ),
                        current_user,
                    ).all()

                    if not documents:
                        results.append({
                            "collection_id": collection_id,
                            "status": "failed",
                            "message": "集合中没有找到资源"
                        })
                        failed_count += 1
                        continue

                    # 批量更新集合中的所有资源
                    new_status = "1" if request.action == "enable" else "0"
                    updated_count = 0

                    for doc in documents:
                        doc.status = new_status
                        doc.update_time = func.now()
                        updated_count += 1

                    results.append({
                        "collection_id": collection_id,
                        "status": "success",
                        "action": request.action,
                        "updated_count": updated_count,
                        "new_status": new_status
                    })
                    success_count += updated_count

                except Exception as e:
                    results.append({
                        "collection_id": collection_id,
                        "status": "failed",
                        "message": str(e)
                    })
                    failed_count += 1
        else:
            return ResponseHelper.error_response("不支持的target_type，必须是 resource_ids 或 collection_id", status=400)

        # 提交数据库更改
        db.commit()

        return ResponseHelper.success_response(
            result={
                "action": request.action,
                "target_type": request.target_type,
                "success_count": success_count,
                "failed_count": failed_count,
                "total_targets": len(request.targets),
                "reason": request.reason,
                "details": results
            },
            message=f"批量{request.action}操作完成：成功 {success_count} 个，失败 {failed_count} 个"
        )

    except Exception as e:
        db.rollback()
        return ResponseHelper.error_response(f"批量操作失败: {str(e)}", status=500)


def _log_operation(
    db: Session,
    operation_type: OperationType,
    resource_type: ResourceType,
    resource_id: str,
    resource_name: str,
    status: OperationStatus,
    details: Dict[str, Any],
    error_message: str = None,
    duration_ms: int = None,
    collection_id: str = None,
    before_state: Dict[str, Any] = None
):
    """
    记录操作日志到数据库

    Args:
        db: 数据库会话
        operation_type: 操作类型
        resource_type: 资源类型
        resource_id: 资源ID
        resource_name: 资源名称
        status: 操作状态
        details: 操作详情
        error_message: 错误信息
        duration_ms: 操作耗时（毫秒）
        collection_id: 集合ID
        before_state: 操作前状态
    """
    try:
        operation_log = OperationLog(
            operation_type=operation_type,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            status=status,
            error_message=error_message,
            details=details,
            before_state=before_state,
            collection_id=collection_id,
            duration_ms=duration_ms,
            # client_ip 和 user_agent 可以从请求中获取，这里暂时为空
            # 后续可以通过 FastAPI 的 Request 对象获取
        )
        db.add(operation_log)
        db.flush()  # 确保日志写入，但不提交事务
        logger.info(f"操作日志已记录: {operation_type.value} {resource_type.value} {resource_id}")
    except Exception as e:
        logger.error(f"记录操作日志失败: {e}")
        # 不影响主业务流程，只记录错误


async def _cascade_delete_document(document: RAGContent, db: Session, delete_files: bool = True) -> Dict[str, Any]:
    """
    级联删除单个文档及其关联数据

    删除顺序：
    0. 删除集合关联记录（RAGCollectionContent）
    1. 删除RAGChunks记录
    2. 删除Milvus向量数据
    3. 删除知识图谱数据（默认 PG，Neo4j 兼容后端）
    4. 删除物理文件
    5. 删除主库 RAGContent 记录

    Returns:
        Dict包含删除结果统计
    """
    from pathlib import Path

    result = {
        "content_id": document.id,
        "collection_contents_deleted": 0,
        "chunks_deleted": 0,
        "vectors_deleted": 0,
        "kg_entities_deleted": 0,
        "file_deleted": False,
        "errors": []
    }

    try:
        # Remove resource links in either direction before deleting their source content.
        result["resource_relations_deleted"] = db.query(RAGResourceRelation).filter(
            (RAGResourceRelation.source_resource_id == document.resource_id) |
            ((RAGResourceRelation.target_type == "resource") &
             RAGResourceRelation.target_id.in_([document.resource_id, document.id]))
        ).delete(synchronize_session=False)

        # 0. 删除集合关联记录（必须先删除，避免外键约束）
        try:
            collection_contents = db.query(RAGCollectionContent).filter(RAGCollectionContent.content_id == document.id).all()
            cc_count = len(collection_contents)
            for cc in collection_contents:
                db.delete(cc)
            result["collection_contents_deleted"] = cc_count
            logger.info(f"删除{cc_count}条集合关联记录: content_id={document.id}")
        except Exception as e:
            logger.warning(f"删除集合关联失败: {e}")
            result["errors"].append(f"删除集合关联失败: {str(e)}")

        # 1. 删除RAGChunks记录
        try:
            chunks = db.query(RAGChunk).filter(RAGChunk.content_id == document.id).all()
            chunks_count = len(chunks)
            for chunk in chunks:
                db.delete(chunk)
            result["chunks_deleted"] = chunks_count
            logger.info(f"删除{chunks_count}条分块记录: content_id={document.id}")
        except Exception as e:
            logger.warning(f"删除RAGChunks失败: {e}")
            result["errors"].append(f"删除分块记录失败: {str(e)}")

        # 2. 删除向量数据（Milvus/pgvector/FAISS）
        try:
            vector_db = get_vector_db()
            collection_name = document.vector_collection
            if collection_name:
                # ✅ 修复：使用doc_id而不是content_id（与写入时的metadata字段名一致）
                deleted_count = vector_db.delete_by_metadata(collection_name, {"doc_id": document.id})
                result["vectors_deleted"] = deleted_count
                logger.info(f"从向量库删除向量: collection={collection_name}, doc_id={document.id}, 删除数量={deleted_count}")
        except Exception as e:
            logger.warning(f"删除向量失败: {e}")
            result["errors"].append(f"删除向量数据失败: {str(e)}")

        # 3. 删除知识图谱数据（统一走 KnowledgeGraphManager / storage）
        try:
            from app.config import settings
            from app.core.kg.manager import KnowledgeGraphManager

            if settings.graph_db.is_configured:
                namespace = getattr(settings.graph_db, "GRAPH_NAMESPACE", "default") or "default"
                kg_manager = KnowledgeGraphManager(namespace=namespace)

                if kg_manager.is_enabled():
                    await kg_manager.initialize()
                    try:
                        storage = getattr(kg_manager, "storage", None)
                        if storage is not None:
                            doc_nodes = await kg_manager.query_nodes(document_id=document.id, limit=5000)
                            node_ids = {str(node["id"]) for node in doc_nodes}

                            doc_root = await storage.get_node(f"doc_{document.id}")
                            if doc_root:
                                node_ids.add(f"doc_{document.id}")

                            edges = await kg_manager.query_edges(
                                document_id=document.id,
                                node_ids=list(node_ids) or None,
                                limit=max(len(node_ids) * 20, 500),
                            )

                            deleted_edges = 0
                            seen_pairs = set()
                            for edge in edges:
                                source_id = str(edge.get("source") or "")
                                target_id = str(edge.get("target") or "")
                                if not source_id or not target_id:
                                    continue
                                pair = (source_id, target_id)
                                if pair in seen_pairs:
                                    continue
                                seen_pairs.add(pair)
                                if await storage.delete_edge(source_id, target_id):
                                    deleted_edges += 1

                            deleted_nodes = 0
                            for node_id in node_ids:
                                if await storage.delete_node(str(node_id)):
                                    deleted_nodes += 1

                            result["kg_entities_deleted"] = deleted_nodes
                            logger.info(
                                "从知识图谱删除文档关联数据: doc_id=%s, backend=%s, 删除节点=%s, 删除关系=%s",
                                document.id,
                                (getattr(settings.graph_db, "GRAPH_DB_TYPE", "postgres") or "postgres").lower(),
                                deleted_nodes,
                                deleted_edges,
                            )
                    finally:
                        await kg_manager.finalize()
        except Exception as e:
            logger.warning(f"删除知识图谱失败: {e}")
            result["errors"].append(f"删除知识图谱失败: {str(e)}")

        # 4. 删除物理文件
        if delete_files and document.file_path:
            try:
                file_path = Path(document.file_path)
                if file_path.exists():
                    file_path.unlink()
                    result["file_deleted"] = True
                    logger.info(f"删除文件: {document.file_path}")
            except Exception as e:
                logger.warning(f"删除文件失败 {document.file_path}: {e}")
                result["errors"].append(f"删除文件失败: {str(e)}")

        # 5. 删除主库 RAGContent记录
        db.delete(document)
        logger.info(f"删除RAGContent记录: {document.id}")

    except Exception as e:
        logger.error(f"级联删除文档失败: {e}")
        result["errors"].append(f"级联删除失败: {str(e)}")

    return result


@router.post("/batch-delete", response_model=Dict)
async def batch_delete_resources(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_request_user),
):
    """
    批量删除资源

    支持按资源ID或集合ID批量删除资源及其关联文件
    """
    try:
        import os
        from pathlib import Path

        results = []
        success_count = 0
        failed_count = 0
        deleted_files_count = 0

        if request.target_type == "resource_ids":
            # 按资源ID批量删除
            for resource_id in request.targets:
                try:
                    id_type = (request.id_type or "").lower()
                    if id_type == "resource_id":
                        # 根据资源ID删除：可能有多个版本，全部删除
                        documents = _apply_document_owner_filter(
                            db.query(RAGContent).filter(RAGContent.resource_id == resource_id),
                            current_user,
                        ).all()
                        if not documents:
                            results.append({
                                "id": resource_id,
                                "status": "failed",
                                "message": "资源不存在",
                                "error_code": "RESOURCE_NOT_FOUND"
                            })
                            failed_count += 1
                            continue
                        for document in documents:
                            # 使用级联删除
                            delete_result = await _cascade_delete_document(document, db, request.delete_files)
                            if delete_result["file_deleted"]:
                                deleted_files_count += 1
                            success_count += 1
                        results.append({
                            "id": resource_id,
                            "status": "success",
                            "deleted_count": len(documents)
                        })
                    elif id_type == "content_id":
                        # 默认按内容ID删除
                        document = _build_owned_document_query(db, resource_id, current_user).first()
                        if not document:
                            results.append({
                                "id": resource_id,
                                "status": "failed",
                                "message": "资源不存在",
                                "error_code": "RESOURCE_NOT_FOUND"
                            })
                            failed_count += 1
                            continue
                        # 使用级联删除
                        delete_result = await _cascade_delete_document(document, db, request.delete_files)
                        if delete_result["file_deleted"]:
                            deleted_files_count += 1
                        results.append({
                            "id": resource_id,
                            "status": "success",
                            "name": document.title,
                            "file_deleted": delete_result["file_deleted"],
                            "file_path": document.file_path,
                            "chunks_deleted": delete_result["chunks_deleted"],
                            "vectors_deleted": delete_result["vectors_deleted"]
                        })
                        success_count += 1
                    else:
                        # 未指定 id_type：自动识别，先按内容ID，找不到再按资源ID（删除该资源ID的所有记录）
                        document = _build_owned_document_query(db, resource_id, current_user).first()
                        if document:
                            # 使用级联删除
                            delete_result = await _cascade_delete_document(document, db, request.delete_files)
                            if delete_result["file_deleted"]:
                                deleted_files_count += 1
                            results.append({
                                "id": resource_id,
                                "status": "success",
                                "name": document.title,
                                "file_deleted": delete_result["file_deleted"],
                                "file_path": document.file_path
                            })
                            success_count += 1
                        else:
                            # fallback: 作为资源ID处理
                            documents = _apply_document_owner_filter(
                                db.query(RAGContent).filter(RAGContent.resource_id == resource_id),
                                current_user,
                            ).all()
                            if not documents:
                                results.append({
                                    "id": resource_id,
                                    "status": "failed",
                                    "message": "资源不存在",
                                    "error_code": "RESOURCE_NOT_FOUND"
                                })
                                failed_count += 1
                                continue
                            for doc in documents:
                                # 使用级联删除
                                delete_result = await _cascade_delete_document(doc, db, request.delete_files)
                                if delete_result["file_deleted"]:
                                    deleted_files_count += 1
                                success_count += 1
                            results.append({
                                "id": resource_id,
                                "status": "success",
                                "deleted_count": len(documents)
                            })

                except Exception as e:
                    results.append({
                        "id": resource_id,
                        "status": "failed",
                        "message": str(e)
                    })
                    failed_count += 1

        elif request.target_type == "collection_id":
            # 按集合ID批量删除
            for collection_id in request.targets:
                try:
                    collection_query = db.query(RAGCollection).filter(RAGCollection.id == collection_id)
                    if current_user:
                        collection_query = collection_query.filter(RAGCollection.user_id == str(current_user.id))
                    elif is_auth_enforced():
                        collection_query = collection_query.filter(false())
                    collection = collection_query.first()

                    if not collection:
                        results.append({
                            "collection_id": collection_id,
                            "status": "failed",
                            "message": "集合不存在"
                        })
                        failed_count += 1
                        continue

                    documents = _apply_document_owner_filter(
                        db.query(RAGContent).filter(
                            RAGContent.vector_collection == collection_id
                        ),
                        current_user,
                    ).all()

                    if not documents:
                        results.append({
                            "collection_id": collection_id,
                            "status": "success",
                            "deleted_count": 0,
                            "files_deleted_count": 0,
                            "message": "集合中没有资源，无需删除"
                        })
                        continue

                    # 批量删除集合中的所有资源
                    collection_deleted_count = 0
                    collection_files_deleted = 0

                    for doc in documents:
                        # 使用级联删除
                        delete_result = await _cascade_delete_document(doc, db, request.delete_files)
                        if delete_result["file_deleted"]:
                            collection_files_deleted += 1
                        collection_deleted_count += 1

                    results.append({
                        "collection_id": collection_id,
                        "status": "success",
                        "deleted_count": collection_deleted_count,
                        "files_deleted_count": collection_files_deleted
                    })
                    success_count += collection_deleted_count
                    deleted_files_count += collection_files_deleted

                except Exception as e:
                    results.append({
                        "collection_id": collection_id,
                        "status": "failed",
                        "message": str(e)
                    })
                    failed_count += 1
        else:
            return ResponseHelper.error_response("不支持的target_type，必须是 resource_ids 或 collection_id", status=400)

        # 提交数据库更改
        db.commit()

        return ResponseHelper.success_response(
            result={
                "target_type": request.target_type,
                "success_count": success_count,
                "failed_count": failed_count,
                "deleted_files_count": deleted_files_count,
                "total_targets": len(request.targets),
                "delete_files": request.delete_files,
                "reason": request.reason,
                "details": results
            },
            message=f"批量删除完成：成功删除 {success_count} 个资源，{deleted_files_count} 个文件"
        )

    except Exception as e:
        db.rollback()
        return ResponseHelper.error_response(f"批量删除失败: {str(e)}", status=500)


@router.post("/chunks", response_model=Dict)
async def get_document_chunks(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_request_user),
):
    """
    获取文档的分块信息

    从Milvus向量库中查询文档的所有分块
    """
    try:
        document_id = request.get("document_id") or request.get("resource_id")
        if not document_id:
            return ResponseHelper.error("缺少document_id参数")

        # 查询文档是否存在
        document = _apply_document_read_access_filter(
            db.query(RAGContent).filter(
                (RAGContent.id == document_id) | (RAGContent.resource_id == document_id)
            ),
            current_user,
        ).first()

        if not document:
            return ResponseHelper.error("文档不存在")

        # 从Milvus查询分块
        try:
            from pymilvus import connections, Collection
            from app.config import settings
            from app.core.rag.collection_validator import validate_and_fix_collection_name

            # 直接使用pymilvus连接
            try:
                connections.connect(
                    alias="chunks_query",
                    host=settings.vector_db.MILVUS_HOST,
                    port=settings.vector_db.MILVUS_PORT
                )
            except:
                # 如果已连接，跳过
                pass

            # 构造集合名称 - 使用验证函数获取正确的集合名
            collection_id = document.vector_collection
            collection_name = validate_and_fix_collection_name(collection_id)

            # 获取集合
            collection = Collection(collection_name, using="chunks_query")
            collection.load()

            # 查询该文档的所有分块
            # 由于Milvus不支持JSON字段查询，需要获取所有数据后在Python中过滤
            chunks = []
            search_ids = [document.resource_id, document.id]

            try:
                # 查询所有记录
                all_results = collection.query(
                    expr="",  # 空表达式返回所有记录
                    output_fields=["id", "metadata"],
                    limit=10000
                )

                # 在Python中过滤匹配的文档
                import json
                for result in all_results:
                    metadata = result.get('metadata', {})
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except:
                            continue

                    # 检查doc_id是否匹配
                    doc_id = metadata.get('doc_id') or metadata.get('document_id')
                    if doc_id in search_ids:
                        chunks.append(result)

                logger.info(f"从Milvus查询到 {len(chunks)} 个分块（文档ID: {document_id}）")

            except Exception as qe:
                logger.error(f"Milvus查询失败: {qe}")
                raise

            if not chunks:
                return ResponseHelper.success({
                    "document_id": document_id,
                    "document_name": document.title,
                    "chunks": [],
                    "total": 0,
                    "message": "该文档暂无分块数据或向量库中不存在该文档"
                })

            # 格式化分块数据
            formatted_chunks = []
            for i, chunk in enumerate(chunks):
                metadata = chunk.get("metadata", {})
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except:
                        metadata = {}

                # 从metadata中提取内容
                content = metadata.get("snippet", metadata.get("content", ""))
                chunk_index = metadata.get("chunk_index", i)

                formatted_chunks.append({
                    "chunk_index": chunk_index,
                    "chunk_id": chunk.get("id"),
                    "content": content[:500] if len(content) > 500 else content,
                    "content_length": len(content),
                    "metadata": metadata
                })

            return ResponseHelper.success({
                "document_id": document_id,
                "document_name": document.title,
                "chunks": formatted_chunks,
                "total": len(formatted_chunks)
            })

        except Exception as ve:
            logger.error(f"Milvus查询失败: {str(ve)}")
            # Milvus查询失败，返回友好提示
            return ResponseHelper.success({
                "document_id": document_id,
                "document_name": document.title,
                "chunks": [],
                "total": 0,
                "message": f"向量库暂不可用，请检查Milvus服务状态"
            })

    except Exception as e:
        logger.error(f"查询文档分块失败: {str(e)}")
        return ResponseHelper.error(f"查询失败: {str(e)}", status=500)
