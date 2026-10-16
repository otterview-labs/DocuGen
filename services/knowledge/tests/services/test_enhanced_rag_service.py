from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from tests.helpers import REPO_ROOT, clear_modules, load_module_from_path, make_package_stub, make_stub_module


pytestmark = pytest.mark.unit


def _build_settings(
    *,
    provider: str = "openai",
    openai_model: str = "text-embedding-3-small",
    openai_key: str = "",
    openai_base: str = "https://api.openai.com/v1",
    local_url: str = "",
    local_model: str = "",
    openai_auth_mode: str = "bearer",
    openai_username: str = "",
    openai_password: str = "",
    local_auth_mode: str = "none",
    local_api_key: str = "",
    local_username: str = "",
    local_password: str = "",
):
    return SimpleNamespace(
        embedding=SimpleNamespace(
            PROVIDER=provider,
            OPENAI_EMBEDDING_MODEL=openai_model,
            LOCAL_EMBEDDING_URL=local_url,
            LOCAL_EMBEDDING_MODEL=local_model,
            LOCAL_EMBEDDING_AUTH_MODE=local_auth_mode,
            LOCAL_EMBEDDING_API_KEY=local_api_key,
            LOCAL_EMBEDDING_USERNAME=local_username,
            LOCAL_EMBEDDING_PASSWORD=local_password,
        ),
        llm=SimpleNamespace(
            OPENAI_API_KEY=openai_key,
            OPENAI_API_BASE=openai_base,
            OPENAI_API_AUTH_MODE=openai_auth_mode,
            OPENAI_API_USERNAME=openai_username,
            OPENAI_API_PASSWORD=openai_password,
        ),
    )


def _load_service_module(monkeypatch, settings_obj):
    clear_modules(prefixes=("app", "_test"))

    app_pkg = make_package_stub("app")
    core_pkg = make_package_stub("app.core")
    core_llm_pkg = make_package_stub("app.core.llm", create_rerank_model=lambda: None)
    core_llm_embedding_module = make_stub_module(
        "app.core.llm.embedding_model",
        create_embedding_model=lambda **kwargs: None,
    )
    core_rag_pkg = make_package_stub("app.core.rag")
    core_rag_vector_db_module = make_stub_module(
        "app.core.rag.vector_db",
        get_vector_db=lambda: None,
    )
    core_rag_utils_pkg = make_package_stub("app.core.rag.utils")
    collection_mapper_module = make_stub_module(
        "app.core.rag.utils.collection_mapper",
        collection_mapper=SimpleNamespace(),
    )
    core_kg_pkg = make_package_stub("app.core.kg")
    core_kg_manager_module = make_stub_module(
        "app.core.kg.manager",
        KnowledgeGraphManager=type("KnowledgeGraphManager", (), {}),
    )
    db_pkg = make_package_stub("app.db")
    db_models_pkg = make_package_stub("app.db.models")
    db_rag_module = make_stub_module(
        "app.db.models.rag",
        RAGCollection=type("RAGCollection", (), {}),
        RAGCollectionContent=type("RAGCollectionContent", (), {}),
        RAGChunk=type("RAGChunk", (), {}),
        RAGContent=type("RAGContent", (), {}),
        RAGMediaAsset=type("RAGMediaAsset", (), {}),
        RAGQuery=type("RAGQuery", (), {}),
        RAGVisualRegion=type("RAGVisualRegion", (), {}),
    )
    db_session_module = make_stub_module("app.db.session", get_db=lambda: iter(()))
    shared_pkg = make_package_stub("app.shared")
    shared_parsers_pkg = make_package_stub(
        "app.shared.parsers",
        LLMEnhancedParser=type("LLMEnhancedParser", (), {}),
    )
    smart_chunker_module = make_stub_module(
        "app.shared.parsers.smart_chunker",
        SmartChunker=type("SmartChunker", (), {}),
    )
    shared_utils_pkg = make_package_stub("app.shared.utils")
    visual_regions_module = make_stub_module(
        "app.shared.utils.visual_regions",
        build_full_region_definition=lambda *args, **kwargs: None,
        crop_image_by_normalized_bbox=lambda *args, **kwargs: None,
        load_image_size=lambda *args, **kwargs: (0, 0),
        normalize_external_visual_regions=lambda *args, **kwargs: [],
        resolve_upload_file_path=lambda *args, **kwargs: "",
    )
    logger_util_module = make_stub_module(
        "app.shared.utils.logger_util",
        get_logger=lambda **kwargs: SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
            debug=lambda *args, **kwargs: None,
        ),
    )
    config_module = make_stub_module("app.config", settings=settings_obj)
    sqlalchemy_module = make_package_stub("sqlalchemy")
    sqlalchemy_orm_module = make_stub_module(
        "sqlalchemy.orm",
        Session=type("Session", (), {}),
    )

    app_pkg.core = core_pkg
    app_pkg.db = db_pkg
    app_pkg.shared = shared_pkg
    core_pkg.llm = core_llm_pkg
    core_pkg.rag = core_rag_pkg
    core_pkg.kg = core_kg_pkg
    core_llm_pkg.embedding_model = core_llm_embedding_module
    core_rag_pkg.vector_db = core_rag_vector_db_module
    core_rag_pkg.utils = core_rag_utils_pkg
    core_rag_utils_pkg.collection_mapper = collection_mapper_module
    core_kg_pkg.manager = core_kg_manager_module
    db_pkg.models = db_models_pkg
    db_pkg.session = db_session_module
    db_models_pkg.rag = db_rag_module
    shared_pkg.parsers = shared_parsers_pkg
    shared_pkg.utils = shared_utils_pkg
    shared_parsers_pkg.smart_chunker = smart_chunker_module
    shared_utils_pkg.visual_regions = visual_regions_module
    shared_utils_pkg.logger_util = logger_util_module

    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "app.core", core_pkg)
    monkeypatch.setitem(sys.modules, "app.core.llm", core_llm_pkg)
    monkeypatch.setitem(sys.modules, "app.core.llm.embedding_model", core_llm_embedding_module)
    monkeypatch.setitem(sys.modules, "app.core.rag", core_rag_pkg)
    monkeypatch.setitem(sys.modules, "app.core.rag.vector_db", core_rag_vector_db_module)
    monkeypatch.setitem(sys.modules, "app.core.rag.utils", core_rag_utils_pkg)
    monkeypatch.setitem(sys.modules, "app.core.rag.utils.collection_mapper", collection_mapper_module)
    monkeypatch.setitem(sys.modules, "app.core.kg", core_kg_pkg)
    monkeypatch.setitem(sys.modules, "app.core.kg.manager", core_kg_manager_module)
    monkeypatch.setitem(sys.modules, "app.db", db_pkg)
    monkeypatch.setitem(sys.modules, "app.db.models", db_models_pkg)
    monkeypatch.setitem(sys.modules, "app.db.models.rag", db_rag_module)
    monkeypatch.setitem(sys.modules, "app.db.session", db_session_module)
    monkeypatch.setitem(sys.modules, "app.shared", shared_pkg)
    monkeypatch.setitem(sys.modules, "app.shared.parsers", shared_parsers_pkg)
    monkeypatch.setitem(sys.modules, "app.shared.parsers.smart_chunker", smart_chunker_module)
    monkeypatch.setitem(sys.modules, "app.shared.utils", shared_utils_pkg)
    monkeypatch.setitem(sys.modules, "app.shared.utils.visual_regions", visual_regions_module)
    monkeypatch.setitem(sys.modules, "app.shared.utils.logger_util", logger_util_module)
    monkeypatch.setitem(sys.modules, "app.config", config_module)
    monkeypatch.setitem(sys.modules, "sqlalchemy", sqlalchemy_module)
    monkeypatch.setitem(sys.modules, "sqlalchemy.orm", sqlalchemy_orm_module)

    return load_module_from_path(
        "_test_enhanced_rag_service",
        REPO_ROOT / "app/services/enhanced_rag_service.py",
    )


def test_resolve_embedding_runtime_config_prefers_settings_model(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_EMBED_MODEL", "legacy-openai-model")
    module = _load_service_module(
        monkeypatch,
        _build_settings(
            provider="openai",
            openai_model="configured-openai-model",
            openai_key="openai-key",
        ),
    )

    runtime_config = module._resolve_embedding_runtime_config()

    assert runtime_config["provider"] == "openai"
    assert runtime_config["openai_model"] == "configured-openai-model"


def test_init_embedding_model_prefers_configured_provider_over_other_available_backends(monkeypatch) -> None:
    module = _load_service_module(
        monkeypatch,
        _build_settings(
            provider="openai",
            openai_model="configured-openai-model",
            openai_key="openai-key",
            openai_base="https://openai.example.com/v1",
        ),
    )
    captured: list[dict[str, object]] = []

    def _fake_create_embedding_model(**kwargs):
        captured.append(dict(kwargs))
        return SimpleNamespace(model_name=kwargs.get("model_name"))

    monkeypatch.setattr(module, "create_embedding_model", _fake_create_embedding_model)

    service = object.__new__(module.EnhancedRAGService)
    service.embedding_model = None

    module.EnhancedRAGService._init_embedding_model(service)

    assert service.embedding_model is not None
    assert captured[0]["model_type"] == "OpenAI"
    assert captured[0]["model_name"] == "configured-openai-model"
    assert captured[0]["base_url"] == "https://openai.example.com/v1"


def test_init_embedding_model_passes_local_basic_auth_credentials(monkeypatch) -> None:
    module = _load_service_module(
        monkeypatch,
        _build_settings(
            provider="local",
            local_url="http://127.0.0.1:8001/v1",
            local_model="bge-m3",
            local_auth_mode="basic",
            local_username="tester",
            local_password="secret",
        ),
    )
    captured: list[dict[str, object]] = []

    def _fake_create_embedding_model(**kwargs):
        captured.append(dict(kwargs))
        return SimpleNamespace(model_name=kwargs.get("model_name"))

    monkeypatch.setattr(module, "create_embedding_model", _fake_create_embedding_model)

    service = object.__new__(module.EnhancedRAGService)
    service.embedding_model = None

    module.EnhancedRAGService._init_embedding_model(service)

    assert service.embedding_model is not None
    assert captured[0]["model_type"] == "Local"
    assert captured[0]["auth_mode"] == "basic"
    assert captured[0]["username"] == "tester"
    assert captured[0]["password"] == "secret"
