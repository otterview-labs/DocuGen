"""Quill's bounded text ingestion API for the private knowledge engine."""
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import get_request_user
from app.db.models import RAGCollection, RAGContent
from app.db.session import get_db

router = APIRouter(tags=["Quill ingestion"])


class TextRequest(BaseModel):
    collection_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=200000)


@router.post("/text")
async def ingest_text(body: TextRequest, db: Session = Depends(get_db), user=Depends(get_request_user)):
    collection = db.query(RAGCollection).filter(RAGCollection.id == body.collection_id).first()
    if not collection or (user and collection.user_id != str(user.id)):
        raise HTTPException(404, "集合不存在或无权写入")
    resource_id = uuid4().hex
    record = RAGContent(id=uuid4().hex, resource_id=resource_id, user_id=collection.user_id,
                        content_type="text", resource_type="text", title=body.title,
                        content_text=body.content, vector_collection=collection.id,
                        is_public=collection.is_public, processing_status="completed", status="1")
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
