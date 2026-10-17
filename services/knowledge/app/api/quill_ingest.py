"""Quill's bounded text ingestion API for the private knowledge engine."""
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.api.v1.deps import get_request_user
from app.db.models import RAGCollection, RAGContent
from app.db.session import get_db

router = APIRouter(tags=["Quill ingestion"])


class TextRequest(BaseModel):
    collection_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=200000)
    file_name: str | None = Field(None, max_length=255)
    file_size: int | None = Field(None, ge=0, le=104857600)
    mime_type: str | None = Field(None, max_length=100)
    file_sha256: str | None = Field(None, pattern=r"^[a-f0-9]{64}$")
    tags: list[str] = Field(default_factory=list, max_length=20)


def owned_collection(db, collection_id, user):
    collection = db.query(RAGCollection).filter(RAGCollection.id == collection_id).first()
    if not collection or (user and collection.user_id != str(user.id)):
        raise HTTPException(404, "集合不存在或无权访问")
    return collection


def resource(db, resource_id, user):
    record = db.query(RAGContent).filter(RAGContent.resource_id == resource_id).first()
    if not record:
        raise HTTPException(404, "资料不存在")
    owned_collection(db, record.vector_collection, user)
    return record


def serialize(record):
    name = record.file_name or ""
    kind = name.rsplit(".", 1)[-1].lower() if "." in name else "text"
    metadata = record.content_metadata if isinstance(record.content_metadata, dict) else {}
    return {
        "resource_id": record.resource_id, "content_id": record.id, "collection_id": record.vector_collection,
        "has_engine_original": bool(record.file_path and Path(record.file_path).is_file()),
        "enabled": str(record.status) == "1", "description": record.description or "", "summary": record.content_summary or "",
        "title": record.title, "file_name": record.file_name, "file_size": record.file_size,
        "kind": kind, "characters": len(record.content_text or ""),
        "tags": record.content_tags or [], "indexed": bool(record.vector_id),
        "bindings": record.bindings or [],
        "status": record.processing_status, "processing_message": record.processing_message, "version": metadata.get("version", 1),
        "created_at": record.create_time.isoformat() if record.create_time else None,
        "updated_at": record.update_time.isoformat() if record.update_time else None,
    }


@router.post("/text")
async def ingest_text(body: TextRequest, db: Session = Depends(get_db), user=Depends(get_request_user)):
    if not body.title.strip() or not body.content.strip():
        raise HTTPException(422, "资料标题和正文不能为空")
    collection = owned_collection(db, body.collection_id, user)
    if body.file_sha256:
        duplicate = db.query(RAGContent).filter(
            RAGContent.vector_collection == collection.id, RAGContent.file_sha256 == body.file_sha256
        ).first()
        if duplicate:
            return {"success": True, "result": {"resource_id": duplicate.resource_id,
                    "duplicate": True, "vector_indexed": bool(duplicate.vector_id), "message": "该文件已在知识库中"}}
    resource_id = uuid4().hex
    record = RAGContent(id=uuid4().hex, resource_id=resource_id, user_id=collection.user_id,
                        content_type="text", resource_type="text", title=body.title,
                        content_text=body.content, vector_collection=collection.id,
                        is_public=collection.is_public, processing_status="completed", status="1",
                        file_name=body.file_name, file_size=body.file_size, mime_type=body.mime_type,
                        file_sha256=body.file_sha256, content_tags=[tag.strip()[:40] for tag in body.tags if tag.strip()],
                        content_metadata={"origin": "quill", "version": 1})
    db.add(record)
    db.commit()
    # Keyword search remains usable without an embedding provider. Vector indexing is explicit.
    indexed = False
    try:
        from app.services.enhanced_rag_service import get_enhanced_rag_service
        service = get_enhanced_rag_service()
        if service.embedding_model and service.vector_db:
            indexed = bool(await service.add_document_to_vector_db(record, db))
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Vector indexing unavailable for %s", resource_id)
        db.rollback()
    return {"success": True, "result": {"resource_id": resource_id, "vector_indexed": indexed,
                                          "message": "资料已保存" if indexed else "资料已保存，可用关键词检索；向量索引尚未建立"}}


@router.post("/overview")
async def overview(db: Session = Depends(get_db), user=Depends(get_request_user)):
    query = db.query(RAGCollection).filter(RAGCollection.status == "1")
    if user:
        query = query.filter(RAGCollection.user_id == str(user.id))
    collections = query.order_by(RAGCollection.create_time.desc()).all()
    aggregates = db.query(
        RAGContent.vector_collection, func.count(RAGContent.id),
        func.coalesce(func.sum(func.length(RAGContent.content_text)), 0),
        func.sum(case((RAGContent.vector_id.isnot(None), 1), else_=0)),
        func.max(RAGContent.update_time),
    ).filter(RAGContent.vector_collection.in_([c.id for c in collections])).group_by(RAGContent.vector_collection).all()
    stats = {row[0]: row for row in aggregates}
    result = []
    for collection in collections:
        count = stats.get(collection.id, (collection.id, 0, 0, 0, None))
        result.append({"id": collection.id, "name": collection.name, "description": collection.description or "",
                       "document_count": count[1], "indexed_count": count[3] or 0,
                       "characters": count[2],
                       "updated_at": (count[4] or collection.update_time).isoformat()})
    return {"success": True, "result": {"collections": result,
            "document_count": sum(c["document_count"] for c in result),
            "characters": sum(c["characters"] for c in result),
            "indexed_count": sum(c["indexed_count"] for c in result)}}


class ListRequest(BaseModel):
    collection_id: str
    query: str = Field("", max_length=200)
    kind: str = "all"
    page: int = Field(0, ge=0)
    size: int = Field(20, ge=1, le=100)


@router.post("/resources/list")
async def list_resources(body: ListRequest, db: Session = Depends(get_db), user=Depends(get_request_user)):
    owned_collection(db, body.collection_id, user)
    query = db.query(RAGContent).filter(RAGContent.vector_collection == body.collection_id)
    if body.query:
        query = query.filter(or_(RAGContent.title.contains(body.query, autoescape=True),
                                 RAGContent.file_name.contains(body.query, autoescape=True)))
    if body.kind != "all":
        if body.kind == "text":
            query = query.filter(or_(RAGContent.file_name.is_(None), RAGContent.file_name.endswith(".txt")))
        else:
            query = query.filter(RAGContent.file_name.endswith("." + body.kind))
    total = query.count()
    records = query.order_by(RAGContent.create_time.desc()).offset(body.page * body.size).limit(body.size).all()
    return {"success": True, "result": {"items": [serialize(r) for r in records], "total": total,
                                         "page": body.page, "size": body.size}}


class ResourceRequest(BaseModel):
    resource_id: str = Field(min_length=1, max_length=64)


@router.post("/resources/get")
async def get_resource(body: ResourceRequest, db: Session = Depends(get_db), user=Depends(get_request_user)):
    record = resource(db, body.resource_id, user)
    text = record.content_text or ""
    segments = [{"start": start, "end": min(start + 800, len(text)), "content": text[start:start + 800]}
                for start in range(0, len(text), 700)]
    from app.db.models.rag import RAGResourceRelation
    relations = db.query(RAGResourceRelation).filter(RAGResourceRelation.source_resource_id == record.resource_id).all()
    return {"success": True, "result": {**serialize(record), "content": text, "segments": segments,
        "relation": [{"type": r.target_type, "id": r.target_id, "relation": r.relation_desc,
                      "confidence": r.confidence, "expands": r.expands or {}} for r in relations]}}


class UpdateRequest(ResourceRequest):
    title: str = Field(min_length=1, max_length=255)
    tags: list[str] = Field(default_factory=list, max_length=20)


@router.post("/resources/update")
async def update_resource(body: UpdateRequest, db: Session = Depends(get_db), user=Depends(get_request_user)):
    record = resource(db, body.resource_id, user)
    record.title = body.title.strip()
    record.content_tags = [tag.strip()[:40] for tag in body.tags if tag.strip()]
    record.update_time = datetime.now(timezone.utc)
    db.commit()
    return {"success": True, "result": serialize(record)}


@router.post("/resources/delete")
async def delete_resource(body: ResourceRequest, db: Session = Depends(get_db), user=Depends(get_request_user)):
    record = resource(db, body.resource_id, user)
    from app.api.v1.rag.endpoints.document_operations import _cascade_delete_document
    result = await _cascade_delete_document(record, db, delete_files=False)
    db.commit()
    return {"success": True, "result": {"deleted": True, "cleanup_pending": bool(result.get("errors"))}}


@router.post("/resources/reindex")
async def reindex_resource(body: ResourceRequest, db: Session = Depends(get_db), user=Depends(get_request_user)):
    record = resource(db, body.resource_id, user)
    from app.services.enhanced_rag_service import get_enhanced_rag_service
    service = get_enhanced_rag_service()
    if not service.embedding_model or not service.vector_db:
        raise HTTPException(409, "向量模型尚未就绪。资料仍可用关键词检索，请先配置 Embedding 模型。")
    if not await service.add_document_to_vector_db(record, db):
        raise HTTPException(502, "向量索引未建立，请检查模型和向量库配置后重试。")
    db.refresh(record)
    return {"success": True, "result": serialize(record)}


@router.get("/capabilities")
async def capabilities(request: Request):
    """Report registration and configured prerequisites, without calling model providers."""
    from app.config import settings
    paths = {route.path: sorted(route.methods or []) for route in request.app.routes if hasattr(route, "methods")}
    llm = settings.llm
    llm_configured = bool(llm.LOCAL_LLM_ENDPOINT and llm.LOCAL_LLM_MODEL_NAME) if llm.LLM_PROVIDER == "local" else bool(
        llm.OPENAI_MODEL_NAME and (llm.OPENAI_API_KEY or llm.OPENAI_API_AUTH_MODE == "none"))
    embedding = settings.embedding
    embedding_configured = bool(embedding.LOCAL_EMBEDDING_URL and embedding.LOCAL_EMBEDDING_MODEL) if embedding.PROVIDER == "local" else bool(
        llm.OPENAI_API_KEY or llm.OPENAI_API_AUTH_MODE == "none")
    return {"paths": paths, "configured": {"graph": settings.graph_db.GRAPH_DB_ENABLED,
        "llm": llm_configured, "embedding": embedding_configured},
        "vector_backend": settings.vector_db.VECTOR_DB_TYPE}


@router.post("/resources/chunks")
async def stored_chunks(body: ResourceRequest, db: Session = Depends(get_db), user=Depends(get_request_user)):
    from app.db.models.rag import RAGChunk
    record = resource(db, body.resource_id, user)
    chunks = db.query(RAGChunk).filter(RAGChunk.content_id == record.id).order_by(RAGChunk.chunk_index).all()
    return {"success": True, "result": {
        "resource_id": record.resource_id, "title": record.title, "total": len(chunks),
        "indexed": bool(record.vector_id),
        "message": "尚无存储分块。阅读预览分段不代表已建立向量索引。" if not chunks else "实际存储的分块记录",
        "chunks": [{"index": c.chunk_index, "content": c.chunk_text, "characters": c.chunk_size,
                    "start": c.start_position, "end": c.end_position, "strategy": c.chunking_strategy,
                    "indexed": bool(c.vector_id), "embedding_model": c.embedding_model} for c in chunks],
    }}
