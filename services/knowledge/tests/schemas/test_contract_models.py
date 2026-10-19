from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.collections import CollectionCreate, CollectionDocumentsRequest
from app.schemas.documents import DocumentDeleteRequest, DocumentUpdateRequest
from app.schemas.search import SearchRequest, SearchResponse


pytestmark = pytest.mark.unit


def test_search_request_requires_query_or_image() -> None:
    with pytest.raises(ValidationError, match="query和image至少提供一个"):
        SearchRequest(search_mode="semantic")


def test_search_request_allows_image_only_for_image_mode() -> None:
    request = SearchRequest(
        image="data:image/png;base64,AAAA",
        search_mode="image",
    )

    assert request.query is None
    assert request.image.startswith("data:image/png")
    assert request.search_mode == "image"


def test_search_request_allows_image_only_for_image_to_image_mode() -> None:
    request = SearchRequest(
        image="data:image/png;base64,AAAA",
        search_mode="image_to_image",
    )

    assert request.query is None
    assert request.image.startswith("data:image/png")
    assert request.search_mode == "image_to_image"


def test_collection_create_accepts_legacy_id_alias() -> None:
    request = CollectionCreate(
        id="collection-001",
        name="技术文档集合",
        description="测试集合",
    )

    assert request.collection_id == "collection-001"
    assert request.name == "技术文档集合"


def test_collection_documents_request_accepts_legacy_pagination_aliases() -> None:
    request = CollectionDocumentsRequest(
        pageIndex=1,
        pageSize=20,
        collection_id="collection-001",
    )

    assert request.page_index == 1
    assert request.page_size == 20
    assert request.collection_id == "collection-001"


def test_document_update_request_supports_compat_aliases_and_relations() -> None:
    request = DocumentUpdateRequest(
        id="doc-001",
        name="更新后的标题",
        relation=[{"type": "device", "id": "device-001", "confidence": 0.9}],
    )

    assert request.document_id == "doc-001"
    assert request.title == "更新后的标题"
    assert request.relation is not None
    assert request.relation[0].type == "device"
    assert request.relation[0].id == "device-001"


def test_document_delete_request_accepts_resource_id_alias() -> None:
    request = DocumentDeleteRequest(resource_id="resource-001")

    assert request.document_id == "resource-001"


def test_search_response_preserves_explicit_result_contract_and_extra_fields() -> None:
    response = SearchResponse.model_validate(
        {
            "query": "设备和网关之间的关系",
            "search_mode": "kg",
            "total": 1,
            "results": [
                {
                    "title": "网关",
                    "content_type": "knowledge_graph",
                    "resource_id": "res-001",
                    "collection_id": "collection-a",
                    "version": 3,
                    "debug": {"internal": {"content_id": "content-001", "vector_id": "entity-001"}},
                    "custom_field": {"bbox": [0.1, 0.2, 0.3, 0.4]},
                }
            ],
            "execution_info": {
                "execution_time_ms": 12,
                "search_mode_used": "kg",
                "result_count": 1,
                "query_analysis": {"original_mode": "kg", "selected_mode": "kg", "query_length": 11, "has_filters": True},
            },
            "citations": [
                {
                    "doc_id": "content-001",
                    "title": "网关文档",
                    "snippet": "网关负责连接设备。",
                    "offset": {"start": 5, "end": 12},
                    "highlights": [{"term": "网关", "start": 0, "end": 2}],
                }
            ],
        }
    )

    assert response.results[0].resource_id == "res-001"
    assert response.results[0].collection_id == "collection-a"
    assert response.results[0].version == 3
    assert response.results[0].debug is not None
    assert response.results[0].debug.internal is not None
    assert response.results[0].debug.internal.content_id == "content-001"
    assert response.results[0].model_dump()["custom_field"]["bbox"] == [0.1, 0.2, 0.3, 0.4]
    assert response.citations is not None
    assert response.citations[0].offset is not None
    assert response.citations[0].offset.start == 5
