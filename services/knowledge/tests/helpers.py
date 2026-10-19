from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent


def clear_modules(prefixes: Iterable[str] = ("app", "main", "_test_main")) -> None:
    targets = tuple(prefixes)
    for module_name in list(sys.modules):
        if any(module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in targets):
            sys.modules.pop(module_name, None)


def make_stub_module(name: str, **attrs: Any) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def make_package_stub(name: str, **attrs: Any) -> types.ModuleType:
    module = make_stub_module(name, **attrs)
    module.__path__ = []  # type: ignore[attr-defined]
    return module


def load_module_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法从路径加载模块: {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def collect_route_paths(router: Any) -> set[str]:
    paths: set[str] = set()

    def _join(prefix: str, path: str) -> str:
        if path == "/":
            return prefix or "/"
        return f"{prefix.rstrip('/')}/{path.lstrip('/')}"

    def _walk(routes: Iterable[Any], prefix: str = "") -> None:
        for route in routes:
            if hasattr(route, "path"):
                paths.add(_join(prefix, route.path))
                continue

            original_router = getattr(route, "original_router", None)
            include_context = getattr(route, "include_context", None)
            if original_router is None or include_context is None:
                continue

            _walk(
                getattr(original_router, "routes", []),
                _join(prefix, getattr(include_context, "prefix", "")),
            )

    _walk(getattr(router, "routes", []))
    return paths


def _env_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def configure_runtime_env(monkeypatch, tmp_path: Path, **overrides: Any) -> dict[str, Path]:
    runtime_root = tmp_path / "runtime"
    storage_root = runtime_root / "storage"

    paths = {
        "runtime_root": runtime_root,
        "storage_root": storage_root,
        "data_dir": storage_root / "data",
        "static_dir": storage_root / "static",
        "uploads_dir": storage_root / "uploads",
        "indices_dir": storage_root / "indices",
        "logs_dir": storage_root / "logs",
        "temp_dir": storage_root / "temp",
        "workspace_dir": storage_root / "workspace",
    }

    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)

    (paths["static_dir"] / "uploads").mkdir(parents=True, exist_ok=True)
    (paths["static_dir"] / "index.html").write_text("<html><body>knowledge index</body></html>", encoding="utf-8")
    (paths["static_dir"] / "knowledge-base.html").write_text(
        "<html><body>knowledge base</body></html>",
        encoding="utf-8",
    )
    (paths["static_dir"] / "uploads" / "hello.txt").write_text("knowledge upload", encoding="utf-8")

    defaults: dict[str, Any] = {
        "ENVIRONMENT": "test",
        "DB_DATABASE_TYPE": "sqlite",
        "SQLITE_DATABASE": paths["data_dir"] / "knowledge.sqlite3",
        "VECTOR_DB_TYPE": "faiss",
        "GRAPH_DB_ENABLED": False,
        "HEALTH_CHECK_REDIS": False,
        "HEALTH_CHECK_GRAPH_DB": False,
        "HEALTH_CHECK_VECTOR_DB": True,
        "REDIS_URL": "",
        "REDIS_HOST": "",
        "STARTUP_CHECK_DATABASE_ON_STARTUP": True,
        "STARTUP_INITIALIZE_DATABASE_ON_STARTUP": False,
        "STARTUP_RUN_DATABASE_MIGRATIONS_ON_STARTUP": False,
        "STARTUP_SEED_LLM_CONFIG_ON_STARTUP": False,
        "STARTUP_FAIL_FAST_ON_STARTUP_ERROR": True,
        "STORAGE_ROOT": paths["storage_root"],
        "STORAGE_DATA_DIR": paths["data_dir"],
        "STORAGE_STATIC_DIR": paths["static_dir"],
        "STORAGE_UPLOADS_DIR": paths["uploads_dir"],
        "STORAGE_INDICES_DIR": paths["indices_dir"],
        "STORAGE_LOGS_DIR": paths["logs_dir"],
        "STORAGE_TEMP_DIR": paths["temp_dir"],
        "STORAGE_WORKSPACE_DIR": paths["workspace_dir"],
    }

    defaults.update(overrides)

    for key, value in defaults.items():
        monkeypatch.setenv(key, _env_value(value))

    return paths


class FakeQuery:
    def __init__(self, results: list[Any] | None = None) -> None:
        self._results = list(results or [])
        self.filters: list[Any] = []
        self.orderings: list[Any] = []
        self.limit_value: int | None = None
        self.offset_value: int | None = None

    def filter(self, *criteria: Any):
        self.filters.extend(criteria)
        return self

    def order_by(self, *orderings: Any):
        self.orderings.extend(orderings)
        return self

    def limit(self, value: int):
        self.limit_value = value
        return self

    def offset(self, value: int):
        self.offset_value = value
        return self

    def first(self) -> Any | None:
        return self._results[0] if self._results else None

    def all(self) -> list[Any]:
        return list(self._results)

    def delete(self) -> int:
        deleted = len(self._results)
        self._results = []
        return deleted


class FakeSession:
    def __init__(self, query_results: list[Any] | None = None) -> None:
        self._query_results = list(query_results or [])
        self.queries: list[FakeQuery] = []
        self.added: list[Any] = []
        self.refreshed: list[Any] = []
        self.deleted: list[Any] = []
        self.commits = 0
        self.rollbacks = 0

    def query(self, _model: Any) -> FakeQuery:
        next_result = self._query_results.pop(0) if self._query_results else []
        if isinstance(next_result, FakeQuery):
            query = next_result
        elif next_result is None:
            query = FakeQuery([])
        elif isinstance(next_result, list):
            query = FakeQuery(next_result)
        else:
            query = FakeQuery([next_result])
        self.queries.append(query)
        return query

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def refresh(self, obj: Any) -> None:
        self.refreshed.append(obj)

    def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1
