import os
import subprocess
import sys
from pathlib import Path


def test_qa_status_chunks_settings_and_collection_cleanup(tmp_path):
    script = '''
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.db.init_database import init_database
from app.db.session import SessionLocal
from app.db.models.rag import RAGCollection, RAGContent, RAGChunk, RAGResourceRelation
from app.api.quill_ingest import router
from app.api.v1.rag.endpoints.qa_import import router as qa
from app.api.v1.rag.endpoints.collections import router as collections
from app.api.v1.rag.endpoints.document_operations import router as documents
from app.api.v1.rag.endpoints.content_analysis import router as analysis
init_database(create_tables=True, run_migrations=False, initialize_seed_data=False)
with SessionLocal() as db:
    db.add(RAGCollection(id="collection", user_id="anonymous", name="Example", status="1", is_public=True))
    db.commit()
app=FastAPI()
app.include_router(router)
app.include_router(qa,prefix="/qa")
app.include_router(collections,prefix="/collections")
app.include_router(documents,prefix="/documents")
app.include_router(analysis,prefix="/analysis")
with TestClient(app) as client:
    response=client.post("/qa/single",data={"collection_id":"collection","question":"Acceptance period?","answer":"30 days"})
    assert response.status_code==200,response.text
    rid=response.json()["result"]["resource_id"]
    cid=response.json()["result"]["content_id"]
    assert client.post("/resources/list",json={"collection_id":"collection"}).json()["result"]["total"]==1
    detail=client.post("/resources/get",json={"resource_id":rid}).json()["result"]
    assert detail["content_id"]==cid and detail["enabled"]
    assert detail["summary"]=="30 days"
    response=client.post("/qa/batch",data={"collection_id":"collection"},files={"file":("qa.json",b'[{"question":"Q2","answer":"A2"},{"question":"","answer":"A"}]',"application/json")})
    assert response.status_code==200,response.text
    assert response.json()["result"]["success"]==1 and response.json()["result"]["failed"]==1
    assert client.post("/qa/single",data={"collection_id":"missing","question":"Q","answer":"A"}).status_code==404
    status=client.post("/documents/batch-toggle-status",json={"targets":[rid],"target_type":"resource_ids","action":"disable"})
    assert status.json()["result"]["success_count"]==1,status.text
    assert client.post("/resources/get",json={"resource_id":rid}).json()["result"]["enabled"] is False
    with SessionLocal() as db:
        db.add(RAGResourceRelation(id="relation",source_resource_id=rid,target_type="resource",target_id=rid))
        db.add(RAGChunk(id="chunk",content_id=cid,chunk_index=0,chunk_text="real chunk",chunk_size=10,chunking_strategy="fixed"))
        db.query(RAGContent).filter(RAGContent.id==cid).update({"content_tags":["saved-tag"]})
        db.commit()
    chunks=client.post("/resources/chunks",json={"resource_id":rid}).json()["result"]
    assert chunks["total"]==1 and chunks["chunks"][0]["content"]=="real chunk"
    analysis=client.post("/analysis/get-result",json={"content_id":cid}).json()
    assert analysis["data"]["tags"]==["saved-tag"]
    response=client.post("/collections/update",json={"collection_id":"collection","collection_type":"multimodal","embedding_model":"example-model"})
    assert response.json()["success"],response.text
    result=client.get("/collections/collection").json()["result"]
    assert result["collection_type"]=="multimodal" and result["embedding_model"]=="example-model"
    response=client.post("/collections/delete",json={"collection_id":"collection"})
    assert response.json()["success"],response.text
    with SessionLocal() as db:
        assert db.query(RAGCollection).count()==0
        assert db.query(RAGContent).count()==0
        assert db.query(RAGChunk).count()==0
        assert db.query(RAGResourceRelation).count()==0
'''
    result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[2],
        env=os.environ | {"DB_DATABASE_TYPE":"sqlite","SQLITE_DATABASE":str(tmp_path/'tools.db'),
            "JETLINKS_KNOWLEDGE_ENV":str(tmp_path/'no-env'),"VECTOR_DB_TYPE":"faiss","SKIP_AUTH":"true",
            "DEV_MODE":"true","GRAPH_DB_ENABLED":"false","OPENAI_API_KEY":"","LLM_API_KEY":"",
            "EMBEDDING_PROVIDER":"openai"}, capture_output=True,text=True)
    assert result.returncode == 0, result.stdout + result.stderr
