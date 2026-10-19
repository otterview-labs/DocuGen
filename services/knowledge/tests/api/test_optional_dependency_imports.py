from __future__ import annotations

import builtins
import sys

import pytest

from tests.helpers import REPO_ROOT, clear_modules, collect_route_paths, configure_runtime_env, load_module_from_path


pytestmark = pytest.mark.api

_BLOCKED_OPTIONAL_MODULES = {
    "cv2",
    "easyocr",
    "librosa",
    "pdf2image",
    "pytesseract",
    "torch",
    "torchvision",
    "transformers",
}


def _block_optional_imports(monkeypatch) -> None:
    real_import = builtins.__import__

    def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: ANN001
        root_name = name.split(".")[0]
        if root_name in _BLOCKED_OPTIONAL_MODULES:
            raise ModuleNotFoundError(f"No module named '{root_name}'")
        return real_import(name, globals, locals, fromlist, level)

    for module_name in list(sys.modules):
        if module_name.split(".")[0] in _BLOCKED_OPTIONAL_MODULES:
            sys.modules.pop(module_name, None)

    monkeypatch.setattr(builtins, "__import__", _fake_import)


def test_unified_markdown_converter_imports_without_optional_media_dependencies(monkeypatch, tmp_path) -> None:
    configure_runtime_env(monkeypatch, tmp_path)
    clear_modules(prefixes=("app", "main", "_test"))
    _block_optional_imports(monkeypatch)

    module = load_module_from_path(
        "_test_unified_markdown_converter_optional_imports",
        REPO_ROOT / "app/shared/parsers/unified_markdown_converter.py",
    )

    converter = module.UnifiedMarkdownConverter()

    assert converter._media_processor is None
    assert converter._paraformer_transcriber is None
    assert converter._vlm_agent is None


def test_rag_router_keeps_upload_routes_when_optional_media_dependencies_are_missing(monkeypatch, tmp_path) -> None:
    configure_runtime_env(monkeypatch, tmp_path)
    clear_modules(prefixes=("app", "main", "_test"))
    _block_optional_imports(monkeypatch)

    router_module = load_module_from_path(
        "_test_rag_router_optional_media_dependencies",
        REPO_ROOT / "app/api/v1/rag/router.py",
    )

    paths = collect_route_paths(router_module.router)
    errors = router_module.get_route_import_errors()

    assert any(path.startswith("/multimodal") for path in paths)
    assert any(path.startswith("/simple-upload") for path in paths)
    assert "app.api.v1.rag.endpoints.multimodal_upload" not in errors
    assert "app.api.v1.rag.endpoints.simple_upload" not in errors


def test_visual_embedding_defaults_to_disabled_without_explicit_provider(monkeypatch, tmp_path) -> None:
    configure_runtime_env(monkeypatch, tmp_path)
    clear_modules(prefixes=("app", "main", "_test"))

    for env_name in (
        "VISUAL_EMBEDDING_PROVIDER",
        "CLIP_PROVIDER",
        "VISUAL_EMBEDDING_API_BASE",
        "CLIP_API_BASE",
        "OPENAI_API_BASE",
    ):
        monkeypatch.delenv(env_name, raising=False)

    module = load_module_from_path(
        "_test_visual_embedding_default_provider",
        REPO_ROOT / "app/shared/vlm/visual_embedding.py",
    )

    config = module._get_visual_embedding_config()
    assert config.provider == "disabled"
