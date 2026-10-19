import os
import subprocess
import sys
from pathlib import Path


def test_knowledge_resource_management_on_real_sqlite(tmp_path):
    script = '''
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.db.init_database import init_database
from app.db.session import SessionLocal
from app.db.models import RAGCollection
from app.api.quill_ingest import router
init_database(create_tables=True, run_migrations=False, initialize_seed_data=False)
with SessionLocal() as db:
    db.add(RAGCollection(id="collection", user_id="anonymous", name="Example", status="1", is_public=True))
    db.commit()
app=FastAPI()
app.include_router(router)
with TestClient(app) as client:
    payload={"collection_id":"collection","title":"Acceptance","content":"Acceptance period 30 days", "file_name":"source.pdf", "file_sha256":"a"*64}
    response=client.post("/text",json=payload)
    assert response.status_code==200,response.text
    rid=response.json()["result"]["resource_id"]
    assert client.post("/text",json=payload).json()["result"]["duplicate"]
    overview=client.post("/overview").json()["result"]
    assert overview["document_count"]==1
    assert overview["characters"]==len(payload["content"])
    assert overview["indexed_count"]==0
    result=client.post("/resources/list",json={"collection_id":"collection","kind":"pdf"}).json()["result"]
    assert result["total"]==1
    assert result["items"][0]["kind"]=="pdf"
    doc=client.post("/resources/get",json={"resource_id":rid}).json()["result"]
    assert doc["content"]==payload["content"]
    assert doc["segments"][0]["start"]==0
    assert client.post("/resources/update",json={"resource_id":rid,"title":"Updated", "tags":["handoff"]}).status_code==200
    doc=client.post("/resources/get",json={"resource_id":rid}).json()["result"]
    assert doc["title"]=="Updated" and doc["tags"]==["handoff"]
    assert client.post("/resources/reindex",json={"resource_id":rid}).status_code==409
    assert client.post("/resources/delete",json={"resource_id":rid}).status_code==200
    assert client.post("/resources/get",json={"resource_id":rid}).status_code==404
    assert client.post("/overview").json()["result"]["document_count"]==0
'''
    result = subprocess.run([sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2], env=os.environ | {
            "DB_DATABASE_TYPE": "sqlite", "SQLITE_DATABASE": str(tmp_path / "workspace.db"),
            "JETLINKS_KNOWLEDGE_ENV": str(tmp_path / "no-env"), "VECTOR_DB_TYPE": "faiss",
            "SKIP_AUTH": "true", "DEV_MODE": "true", "GRAPH_DB_ENABLED": "false",
            "OPENAI_API_KEY": "", "LLM_API_KEY": "", "EMBEDDING_PROVIDER": "openai",
        }, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
