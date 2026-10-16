# Otterview Quill

A self-hosted knowledge and document workspace. Organize source material, retrieve evidence, fill Word templates, and generate documents section by section.

This repository integrates the JetLinks knowledge runtime with selected DocuGen template and Word rendering methods. It is an early local integration, version 0.1.0, for a **single shared workspace**. One access key protects its API and generated files; it does not provide per-user isolation or multi-tenancy.

See the [Chinese guide](README.md) for configuration and deployment details, and [provenance](docs/PROVENANCE.md) for upstream revisions and publication requirements.

## Run locally

```bash
uv venv --python 3.11
uv pip install --python .venv/bin/python -e '.[dev]'
cp .env.example .env
# Configure the OpenAI-compatible base URL, model, and credentials in .env.
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/uvicorn quill.main:app --host 127.0.0.1 --port 8080 --workers 1
```

Open http://127.0.0.1:8080. Enter the shared access key in the header if `QUILL_API_KEY` is set. The UI currently uses Chinese. Manual template filling works without a model. Manual reference text works without the knowledge service when a model is configured.

For the full local stack, set `QUILL_API_KEY` and `POSTGRES_PASSWORD`, then run `docker compose -p quill up -d --build`. Only the workspace binds to loopback. Keep the private knowledge engine and PostgreSQL off public networks. Semantic retrieval requires an embedding model with a matching configured dimension.

## Current boundaries

- DOCX templates, variable extraction, manual/AI filling, and authenticated Word downloads.
- Knowledge collections, text ingestion, and keyword/semantic/intelligent retrieval through an adapter.
- Outline generation, per-section evidence retrieval, persisted jobs, and source snapshots.
- Interrupted jobs retain existing content and can be regenerated; they do not automatically resume.
- One API process and one task worker; no horizontal scaling or concurrent API workers.
- Model output and document formatting require human review. Source snapshots are not a guarantee of factual correctness.
- Upstream OCR, video, graph, and advanced parsers are retained as source but are not verified default-profile features.

## Checks

```bash
.venv/bin/python -m pytest tests
.venv/bin/python -m ruff check quill tests
npm --prefix frontend run build
```

Tests use controlled provider responses and do not call paid models. Upstream knowledge tests run in a separate process from `services/knowledge` after installing its text runtime profile.
