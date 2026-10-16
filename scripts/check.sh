#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${QUILL_PYTHON:-$PWD/.venv/bin/python}"
"$PYTHON" -m pytest tests "$@"
"$PYTHON" -m ruff check quill tests
(cd services/knowledge && "$PYTHON" -m pytest tests)
(cd frontend && npm run build)
