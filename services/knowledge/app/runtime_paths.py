from __future__ import annotations

import filecmp
import os
import shutil
import sys
from pathlib import Path


def get_application_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _native_executable_mode() -> bool:
    return bool(getattr(sys, "frozen", False) or os.getenv("NUITKA_ONEFILE_PARENT"))


def get_runtime_root() -> Path:
    explicit_root = (
        os.getenv("JETLINKS_KNOWLEDGE_HOME")
        or os.getenv("JETLINKS_RUNTIME_HOME")
        or os.getenv("APP_HOME")
    )
    if explicit_root:
        return Path(explicit_root).expanduser().resolve()

    if _native_executable_mode():
        argv0 = Path(sys.argv[0]).expanduser()
        if str(argv0):
            return argv0.resolve().parent
        return Path.cwd().resolve()

    return get_application_root()


def _copy_tree_if_changed(source: Path, target: Path) -> None:
    if not source.exists():
        return

    for src_path in source.rglob("*"):
        if src_path.is_dir():
            continue
        rel_path = src_path.relative_to(source)
        dst_path = target / rel_path
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if dst_path.exists() and filecmp.cmp(src_path, dst_path, shallow=False):
            continue
        shutil.copy2(src_path, dst_path)


def prepare_native_runtime() -> Path:
    runtime_root = get_runtime_root()
    app_root = get_application_root()

    for relative_dir in (
        "storage/indices",
        "storage/data",
        "storage/uploads",
        "storage/temp",
        "storage/logs",
        "storage/static",
        "storage/static/uploads",
        "storage/workspace",
        "logs",
    ):
        (runtime_root / relative_dir).mkdir(parents=True, exist_ok=True)

    _copy_tree_if_changed(app_root / "storage" / "static", runtime_root / "storage" / "static")

    env_example = app_root / ".env.example"
    target_env_example = runtime_root / ".env.example"
    if env_example.exists() and not target_env_example.exists():
        shutil.copy2(env_example, target_env_example)

    native_env_example = app_root / "deploy" / "native.env.example"
    target_native_env_example = runtime_root / "native.env.example"
    if native_env_example.exists() and not target_native_env_example.exists():
        shutil.copy2(native_env_example, target_native_env_example)

    return runtime_root
