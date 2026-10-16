#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识图谱抽取与写入接口。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.core.kg.manager import KnowledgeGraphManager
from app.db.models.rag import RAGContent
from app.db.session import get_db
from app.shared.response_models import ResponseHelper
from app.shared.utils.logger_util import get_logger

logger = get_logger(__name__)

router = APIRouter()

_TYPE_TO_CATEGORY = {
    "技术": 0,
    "概念": 1,
    "应用领域": 2,
    "人物": 3,
    "组织": 4,
    "时间": 5,
    "地点": 6,
    "事件": 7,
}

_CATEGORY_COLORS = {
    0: "#7FB069",
    1: "#F4C430",
    2: "#D18B8B",
    3: "#8B4A8C",
    4: "#69B3D1",
    5: "#F4A460",
    6: "#98D982",
    7: "#DDA0DD",
}


class KGExtractionRequest(BaseModel):
    """知识图谱抽取请求。"""

    content_id: Optional[str] = Field(None, description="文档内容ID")
    text_content: Optional[str] = Field(None, description="直接提供的文本内容")
    extraction_type: str = Field("both", description="抽取类型：entities, relations, both")
    max_entities: int = Field(50, description="最大实体数量", ge=1, le=200)
    max_relations: int = Field(100, description="最大关系数量", ge=1, le=500)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text_content": "人工智能是一门研究如何让计算机模拟人类智能的科学。",
                "extraction_type": "both",
                "max_entities": 50,
                "max_relations": 100,
            }
        }
    )


class GetEntitiesRequest(BaseModel):
    """文档实体查询请求。"""

    content_id: str = Field(..., description="文档ID")

    model_config = ConfigDict(
        json_schema_extra={"example": {"content_id": "eaac3b67-16eb-48d1-8687-31e3d41c5a09"}}
    )


def _build_kg_manager() -> KnowledgeGraphManager:
    namespace = (getattr(settings.graph_db, "GRAPH_NAMESPACE", None) or "default").strip() or "default"
    return KnowledgeGraphManager(namespace=namespace)


def _convert_to_echarts_format(entities: List[Dict[str, Any]], relations: List[Dict[str, Any]]) -> Dict[str, Any]:
    nodes = []
    entity_id_map: Dict[str, str] = {}

    for index, entity in enumerate(entities):
        entity_type = entity.get("type", "概念")
        category = _TYPE_TO_CATEGORY.get(entity_type, 1)
        importance = float(entity.get("confidence", 0.8) or 0.8)
        nodes.append(
            {
                "id": str(index),
                "name": entity.get("name", f"实体{index}"),
                "symbolSize": max(30, min(80, int(importance * 100))),
                "value": int(importance * 100),
                "category": category,
                "itemStyle": {"color": _CATEGORY_COLORS.get(category, "#95A5A6")},
                "description": entity.get("description", ""),
                "type": entity_type,
                "confidence": importance,
            }
        )
        entity_id_map[str(entity.get("name"))] = str(index)

    links = []
    for relation in relations:
        source_id = entity_id_map.get(str(relation.get("source")))
        target_id = entity_id_map.get(str(relation.get("target")))
        if not source_id or not target_id:
            continue
        links.append(
            {
                "source": source_id,
                "target": target_id,
                "relation": relation.get("type", relation.get("relation", "相关")),
                "description": relation.get("description", ""),
                "confidence": float(relation.get("confidence", 0.8) or 0.8),
            }
        )

    return {"nodes": nodes, "links": links}


def _build_statistics(entities: List[Dict[str, Any]], relations: List[Dict[str, Any]]) -> Dict[str, Any]:
    entity_types: Dict[str, int] = {}
    for entity in entities:
        entity_type = str(entity.get("type", "未知"))
        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
    return {
        "total_entities": len(entities),
        "total_relations": len(relations),
        "entity_types": entity_types,
    }


async def _load_source_text(request: KGExtractionRequest, db: Session) -> tuple[Optional[RAGContent], str]:
    if request.content_id:
        content = db.query(RAGContent).filter(RAGContent.id == request.content_id).first()
        if not content:
            raise ValueError("文档不存在")
        text_content = content.content_text or content.title or ""
        return content, text_content

    if request.text_content:
        return None, request.text_content

    raise ValueError("必须提供content_id或text_content")


def _apply_extraction_filter(
    extraction_type: str,
    entities: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    normalized_type = (extraction_type or "both").strip().lower()
    if normalized_type == "entities":
        return entities, []
    if normalized_type == "relations":
        referenced_names = {
            str(item.get("source"))
            for item in relations
        } | {
            str(item.get("target"))
            for item in relations
        }
        filtered_entities = [entity for entity in entities if str(entity.get("name")) in referenced_names]
        return filtered_entities, relations
    return entities, relations


@router.post("/extract", response_model=Dict)
async def extract_knowledge_graph(
    request: KGExtractionRequest,
    db: Session = Depends(get_db),
):
    """从文本中抽取实体和关系。"""

    try:
        _, text_content = await _load_source_text(request, db)
        if not text_content:
            return ResponseHelper.error("文本内容为空", status=400)

        kg_manager = _build_kg_manager()
        extraction_result = await kg_manager.extract_entities_and_relations(text_content)

        entities = extraction_result.get("entities", [])[: request.max_entities]
        relations = extraction_result.get("relations", [])[: request.max_relations]
        entities, relations = _apply_extraction_filter(request.extraction_type, entities, relations)

        result = {
            "extraction_type": request.extraction_type,
            "text_length": len(text_content),
            "entities": entities,
            "relations": relations,
            "echarts_data": _convert_to_echarts_format(entities, relations),
            "statistics": _build_statistics(entities, relations),
        }

        if request.content_id and kg_manager.is_enabled():
            result["graph_storage"] = await kg_manager.store_extracted_graph(
                entities,
                relations,
                doc_id=request.content_id,
            )

        return ResponseHelper.success(result=result, message="知识图谱抽取成功")
    except ValueError as exc:
        return ResponseHelper.error(str(exc), status=400 if "必须提供" in str(exc) or "为空" in str(exc) else 404)
    except Exception as exc:
        logger.error("知识图谱抽取失败: %s", exc, exc_info=True)
        return ResponseHelper.error(f"知识图谱抽取失败: {exc}", status=500)


@router.post("/build-graph", response_model=Dict)
async def build_knowledge_graph(
    request: KGExtractionRequest,
    db: Session = Depends(get_db),
):
    """抽取并写入知识图谱存储。"""

    try:
        _, text_content = await _load_source_text(request, db)
        if not text_content:
            return ResponseHelper.error("文本内容为空", status=400)

        kg_manager = _build_kg_manager()
        extraction_result = await kg_manager.extract_entities_and_relations(text_content)

        entities = extraction_result.get("entities", [])[: request.max_entities]
        relations = extraction_result.get("relations", [])[: request.max_relations]
        entities, relations = _apply_extraction_filter(request.extraction_type, entities, relations)

        graph_storage = await kg_manager.store_extracted_graph(
            entities,
            relations,
            doc_id=request.content_id,
        )
        echarts_data = _convert_to_echarts_format(entities, relations)

        return ResponseHelper.success(
            result={
                "content_id": request.content_id,
                "extraction_type": request.extraction_type,
                "text_length": len(text_content),
                "entities": entities,
                "relations": relations,
                "echarts_data": echarts_data,
                "statistics": _build_statistics(entities, relations),
                "graph_storage": graph_storage,
            },
            message="知识图谱构建成功",
        )
    except ValueError as exc:
        return ResponseHelper.error(str(exc), status=400 if "必须提供" in str(exc) or "为空" in str(exc) else 404)
    except Exception as exc:
        logger.error("知识图谱构建失败: %s", exc, exc_info=True)
        return ResponseHelper.error(f"知识图谱构建失败: {exc}", status=500)


@router.post("/get-entities", response_model=Dict)
async def get_content_entities(
    request: GetEntitiesRequest,
    db: Session = Depends(get_db),
):
    """获取指定文档的实体信息。"""

    try:
        content = db.query(RAGContent).filter(RAGContent.id == request.content_id).first()
        if not content:
            return ResponseHelper.error("文档不存在", status=404)

        kg_manager = _build_kg_manager()
        if not kg_manager.is_enabled():
            return ResponseHelper.success(
                result={
                    "content_id": request.content_id,
                    "content_title": content.title,
                    "entities": [],
                    "total_entities": 0,
                },
                message="知识图谱服务未启用",
            )

        entities = await kg_manager.list_document_entities(
            request.content_id,
            content_name=content.title or "",
            limit=50,
        )

        return ResponseHelper.success(
            result={
                "content_id": request.content_id,
                "content_title": content.title,
                "entities": entities,
                "total_entities": len(entities),
            },
            message="获取文档实体成功",
        )
    except Exception as exc:
        logger.error("获取文档实体失败: %s", exc, exc_info=True)
        return ResponseHelper.error(f"获取文档实体失败: {exc}", status=500)
