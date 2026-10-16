from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from tests.helpers import REPO_ROOT, clear_modules, load_module_from_path, make_package_stub, make_stub_module


pytestmark = pytest.mark.unit


def _load_service_module(monkeypatch):
    clear_modules(prefixes=("app", "_test"))

    app_pkg = make_package_stub("app")
    services_pkg = make_package_stub("app.services")
    core_pkg = make_package_stub("app.core")
    core_kg_pkg = make_package_stub("app.core.kg")
    core_rag_pkg = make_package_stub("app.core.rag")
    core_rag_utils_pkg = make_package_stub("app.core.rag.utils")
    db_pkg = make_package_stub("app.db")
    db_models_pkg = make_package_stub("app.db.models")

    app_pkg.services = services_pkg
    app_pkg.core = core_pkg
    app_pkg.db = db_pkg
    core_pkg.kg = core_kg_pkg
    core_pkg.rag = core_rag_pkg
    core_rag_pkg.utils = core_rag_utils_pkg
    db_pkg.models = db_models_pkg

    enhanced_rag_module = make_stub_module(
        "app.services.enhanced_rag_service",
        get_enhanced_rag_service=lambda: None,
    )
    kg_manager_module = make_stub_module(
        "app.core.kg.manager",
        KnowledgeGraphManager=type("KnowledgeGraphManager", (), {}),
    )
    rag_models_module = make_stub_module(
        "app.db.models.rag",
        RAGContent=type("RAGContent", (), {}),
    )
    config_module = make_stub_module(
        "app.config",
        settings=SimpleNamespace(
            vector_db=SimpleNamespace(VECTOR_DB_TYPE="faiss"),
            graph_db=SimpleNamespace(is_configured=False, GRAPH_NAMESPACE="default"),
        ),
    )
    collection_mapper_module = make_stub_module(
        "app.core.rag.utils.collection_mapper",
        collection_mapper=SimpleNamespace(),
    )
    loguru_module = make_stub_module(
        "loguru",
        logger=SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
            debug=lambda *args, **kwargs: None,
        ),
    )
    redis_module = make_stub_module(
        "redis",
        Redis=type("Redis", (), {}),
        from_url=lambda *args, **kwargs: None,
    )
    numpy_module = make_stub_module("numpy")
    sqlalchemy_module = make_package_stub(
        "sqlalchemy",
        and_=lambda *args, **kwargs: None,
        or_=lambda *args, **kwargs: None,
    )
    sqlalchemy_orm_module = make_stub_module(
        "sqlalchemy.orm",
        Session=type("Session", (), {}),
    )

    services_pkg.enhanced_rag_service = enhanced_rag_module
    core_kg_pkg.manager = kg_manager_module
    core_rag_utils_pkg.collection_mapper = collection_mapper_module
    db_models_pkg.rag = rag_models_module

    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "app.services", services_pkg)
    monkeypatch.setitem(sys.modules, "app.services.enhanced_rag_service", enhanced_rag_module)
    monkeypatch.setitem(sys.modules, "app.core", core_pkg)
    monkeypatch.setitem(sys.modules, "app.core.kg", core_kg_pkg)
    monkeypatch.setitem(sys.modules, "app.core.kg.manager", kg_manager_module)
    monkeypatch.setitem(sys.modules, "app.core.rag", core_rag_pkg)
    monkeypatch.setitem(sys.modules, "app.core.rag.utils", core_rag_utils_pkg)
    monkeypatch.setitem(sys.modules, "app.core.rag.utils.collection_mapper", collection_mapper_module)
    monkeypatch.setitem(sys.modules, "app.db", db_pkg)
    monkeypatch.setitem(sys.modules, "app.db.models", db_models_pkg)
    monkeypatch.setitem(sys.modules, "app.db.models.rag", rag_models_module)
    monkeypatch.setitem(sys.modules, "app.config", config_module)
    monkeypatch.setitem(sys.modules, "loguru", loguru_module)
    monkeypatch.setitem(sys.modules, "redis", redis_module)
    monkeypatch.setitem(sys.modules, "numpy", numpy_module)
    monkeypatch.setitem(sys.modules, "sqlalchemy", sqlalchemy_module)
    monkeypatch.setitem(sys.modules, "sqlalchemy.orm", sqlalchemy_orm_module)

    return load_module_from_path(
        "_test_unified_search_service",
        REPO_ROOT / "app/services/unified_search_service.py",
    )


def test_clone_request_with_search_mode_preserves_validated_fields(monkeypatch) -> None:
    module = _load_service_module(monkeypatch)

    class _Request(BaseModel):
        query: str
        search_mode: str = "semantic"
        top_k: int = 5

    request = _Request(query="系统架构")

    cloned_request = module._clone_request_with_search_mode(
        request,
        module.SearchMode.THREE_LAYER_SEMANTIC,
    )

    assert cloned_request.query == "系统架构"
    assert cloned_request.top_k == 5
    assert cloned_request.search_mode == module.SearchMode.THREE_LAYER_SEMANTIC
    assert request.search_mode == "semantic"


def test_intelligent_mode_prefers_semantic_over_kg_for_entity_queries(monkeypatch) -> None:
    module = _load_service_module(monkeypatch)
    service = object.__new__(module.UnifiedSearchService)

    mode = asyncio.run(
        module.UnifiedSearchService._analyze_and_select_mode(
            service,
            "海尔公司和设备之间的关系",
            module.SearchMode.INTELLIGENT,
        )
    )

    assert mode == module.SearchMode.SEMANTIC


def test_hybrid_search_skips_kg_when_weight_is_zero(monkeypatch) -> None:
    module = _load_service_module(monkeypatch)
    service = object.__new__(module.UnifiedSearchService)
    service.kg_manager = object()
    service.three_layer_search = None

    async def _semantic_search(request, permission_filter, db):  # noqa: ANN001, ARG001
        return [{"id": "semantic-1", "similarity_score": 0.9}]

    async def _keyword_search(request, permission_filter, db):  # noqa: ANN001, ARG001
        return [{"id": "keyword-1", "similarity_score": 0.7}]

    async def _kg_search(request, permission_filter, db):  # noqa: ANN001, ARG001
        raise AssertionError("KG 搜索在权重为 0 时不应被调度")

    service._semantic_search = _semantic_search
    service._keyword_search = _keyword_search
    service._kg_search = _kg_search

    results = asyncio.run(
        module.UnifiedSearchService._hybrid_search(
            service,
            SimpleNamespace(query="设备管理", top_k=5),
            {},
            None,
        )
    )

    assert module.KG_HYBRID_SOURCE_WEIGHT == 0.0
    assert {item["id"] for item in results} == {"semantic-1", "keyword-1"}
    assert all(item.get("original_search_mode") != "kg" for item in results)


def test_kg_mode_remains_public_and_is_not_aliased(monkeypatch) -> None:
    module = _load_service_module(monkeypatch)

    assert module.SearchMode.KG in module.PUBLIC_SEARCH_MODES
    assert module.SEARCH_MODE_ALIASES.get(module.SearchMode.KG, module.SearchMode.KG) == module.SearchMode.KG


def test_visual_similarity_mode_maps_to_public_image_to_image(monkeypatch) -> None:
    module = _load_service_module(monkeypatch)

    assert module.SearchMode.IMAGE_TO_IMAGE in module.PUBLIC_SEARCH_MODES
    assert module.SEARCH_MODE_ALIASES[module.SearchMode.VISUAL_SIMILARITY] == module.SearchMode.IMAGE_TO_IMAGE
    assert module.RUNTIME_SEARCH_MODE_MAP[module.SearchMode.IMAGE_TO_IMAGE] == module.SearchMode.VISUAL_SIMILARITY


def test_kg_search_passes_resource_scoped_document_ids(monkeypatch) -> None:
    module = _load_service_module(monkeypatch)
    service = object.__new__(module.UnifiedSearchService)

    class _KGManager:
        def is_enabled(self) -> bool:
            return True

        async def initialize(self) -> None:
            return None

    captured: dict[str, object] = {}
    service.kg_manager = _KGManager()

    async def _resolve_resource_ids_to_content_ids(resource_ids, db):  # noqa: ANN001, ARG002
        captured["resource_ids"] = list(resource_ids)
        return ["content-001"]

    async def _execute_kg_query(query, kg_config, document_ids=None):  # noqa: ANN001
        captured["query"] = query
        captured["document_ids"] = list(document_ids or [])
        captured["kg_config"] = dict(kg_config)
        return [{"n": {"id": "entity-001", "name": "网关", "source_doc": "content-001"}}]

    async def _convert_kg_results(kg_results, db, query=""):  # noqa: ANN001, ARG002
        captured["kg_results"] = list(kg_results)
        return [{"id": "entity-001", "content_type": "knowledge_graph", "content_id": "content-001"}]

    async def _apply_permission_filter(results, permission_filter, db):  # noqa: ANN001, ARG002
        captured["permission_filter"] = dict(permission_filter)
        return list(results)

    service._resolve_resource_ids_to_content_ids = _resolve_resource_ids_to_content_ids
    service._execute_kg_query = _execute_kg_query
    service._convert_kg_results = _convert_kg_results
    service._apply_permission_filter = _apply_permission_filter

    results = asyncio.run(
        module.UnifiedSearchService._kg_search(
            service,
            SimpleNamespace(query="设备和网关之间的关系", kg_config=None, top_k=5),
            {"resource_ids": ["res-001"]},
            None,
        )
    )

    assert captured["resource_ids"] == ["res-001"]
    assert captured["document_ids"] == ["content-001"]
    assert results[0]["search_mode"] == module.SearchMode.KG


class _Expr:
    def __init__(self, op: str, value) -> None:  # noqa: ANN001
        self.op = op
        self.value = value

    def __or__(self, other):  # noqa: ANN001
        return ("or", self, other)


class _Field:
    def in_(self, values):  # noqa: ANN001
        return _Expr("in", tuple(values))

    def __eq__(self, other):  # noqa: ANN001
        return _Expr("eq", other)


class _Query:
    def __init__(self, records):  # noqa: ANN001
        self._records = list(records)

    def filter(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def all(self):
        return list(self._records)

    def first(self):
        return self._records[0] if self._records else None


class _DB:
    def __init__(self, query_results):  # noqa: ANN001
        self._query_results = list(query_results)

    def query(self, _model):  # noqa: ANN001
        records = self._query_results.pop(0) if self._query_results else []
        return _Query(records)


def test_post_process_kg_result_resolves_resource_id_from_legacy_source_doc(monkeypatch) -> None:
    module = _load_service_module(monkeypatch)
    service = object.__new__(module.UnifiedSearchService)
    module.RAGContent = SimpleNamespace(id=_Field(), resource_id=_Field())

    content_record = SimpleNamespace(
        id="content-001",
        resource_id="res-001",
        resource_type="file",
        bindings=["viewer"],
        vector_collection="collection-a",
        create_time=datetime(2026, 4, 11, 12, 0, 0),
        content_metadata={"version": 3},
    )
    db = _DB([[], [content_record]])
    request = SimpleNamespace(include_content=True, include_snippet=True, include_metadata=True)

    results = asyncio.run(
        module.UnifiedSearchService._post_process_results(
            service,
            [
                {
                    "id": "entity-001",
                    "title": "网关",
                    "content_type": "knowledge_graph",
                    "metadata": {
                        "source_doc": "res-001",
                        "kg_properties": {"source_doc": "res-001"},
                    },
                }
            ],
            request,
            db,
        )
    )

    assert results[0]["resource_id"] == "res-001"
    assert results[0]["collection_id"] == "collection-a"
    assert results[0]["version"] == 3
    assert results[0]["debug"]["internal"]["content_id"] == "content-001"
    assert "id" not in results[0]


def test_post_process_kg_result_keeps_explicit_resource_id_without_content_record(monkeypatch) -> None:
    module = _load_service_module(monkeypatch)
    service = object.__new__(module.UnifiedSearchService)
    module.RAGContent = SimpleNamespace(id=_Field(), resource_id=_Field())

    db = _DB([[], []])
    request = SimpleNamespace(include_content=True, include_snippet=True, include_metadata=True)

    results = asyncio.run(
        module.UnifiedSearchService._post_process_results(
            service,
            [
                {
                    "id": "entity-001",
                    "title": "网关",
                    "content_type": "knowledge_graph",
                    "resource_id": "res-explicit-001",
                    "metadata": {},
                }
            ],
            request,
            db,
        )
    )

    assert results[0]["resource_id"] == "res-explicit-001"
    assert results[0]["metadata"]["resource_id"] == "res-explicit-001"
