"""Start DocuGen and the text/keyword knowledge engine on loopback without Docker."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
data = ROOT / "data"
data.mkdir(exist_ok=True)
config = {**dotenv_values(ROOT / ".env"), **os.environ}
engine_env = {
    **os.environ,
    "JETLINKS_KNOWLEDGE_ENV": str(data / "local-engine.env"),
    "DB_DATABASE_TYPE": "sqlite",
    "SQLITE_DATABASE": str(data / "knowledge.db"),
    "VECTOR_DB_TYPE": "faiss",
    "STARTUP_CHECK_DATABASE_ON_STARTUP": "true",
    "STARTUP_INITIALIZE_DATABASE_ON_STARTUP": "true",
    "STARTUP_RUN_DATABASE_MIGRATIONS_ON_STARTUP": "false",
    "STARTUP_SEED_LLM_CONFIG_ON_STARTUP": "false",
    "SKIP_AUTH": "true",
    "DEV_MODE": "true",
    "GRAPH_DB_ENABLED": "false",
    "API_LOGGING_ENABLED": "false",
    "OPENAI_API_BASE": config.get("QUILL_LLM_BASE_URL", "https://api.openai.com/v1"),
    "OPENAI_API_KEY": config.get("QUILL_LLM_API_KEY", ""),
    "OPENAI_MODEL_NAME": config.get("QUILL_LLM_MODEL", ""),
}
processes = []


def shutdown(*_):
    for process in processes:
        if process.poll() is None:
            process.terminate()


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)
try:
    processes.append(subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8006"],
        cwd=ROOT / "services/knowledge", env=engine_env))
    processes.append(subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "quill.main:app", "--host", "127.0.0.1", "--port", "8080", "--workers", "1"],
        cwd=ROOT, env={**os.environ, "QUILL_KNOWLEDGE_URL": "http://127.0.0.1:8006"}))
    print("DocuGen: http://127.0.0.1:8080 — local SQLite / keyword profile", flush=True)
    while all(process.poll() is None for process in processes):
        time.sleep(0.5)
finally:
    shutdown()
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
