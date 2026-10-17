"""Question/answer imports persist through Quill's collection-aware ingestion contract."""
import csv
import io
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.quill_ingest import TextRequest, ingest_text, owned_collection
from app.api.v1.deps import get_request_user
from app.db.models.rag import RAGContent
from app.db.session import get_db

router = APIRouter()


async def save_pair(db, user, collection_id, question, answer, title=None, metadata=None):
    if not isinstance(question, str) or not isinstance(answer, str) or not question.strip() or not answer.strip():
        raise HTTPException(422, "问题和答案不能为空")
    result = await ingest_text(TextRequest(collection_id=collection_id, title=title or question[:255],
        content=f"问题：{question.strip()}\n\n答案：{answer.strip()}"), db, user)
    record = db.query(RAGContent).filter(RAGContent.resource_id == result["result"]["resource_id"]).one()
    record.content_type = "qa"
    record.content_summary = answer.strip()
    record.content_metadata = {**(record.content_metadata or {}), "question": question.strip(),
                               "answer": answer.strip(), "qa_metadata": metadata or {}}
    db.commit()
    return {**result["result"], "content_id": record.id, "title": record.title}


@router.post("/single", summary="添加问答对")
async def single(question: str = Form(...), answer: str = Form(...), title: str = Form(""),
                 metadata: str = Form("{}"), collection_id: str = Form(...),
                 db: Session = Depends(get_db), user=Depends(get_request_user)):
    owned_collection(db, collection_id, user)
    try:
        extra = json.loads(metadata)
        if not isinstance(extra, dict):
            raise ValueError()
    except ValueError:
        raise HTTPException(422, "补充元数据必须是 JSON 对象") from None
    result = await save_pair(db, user, collection_id, question, answer, title, extra)
    return {"success": True, "result": result, "message": "问答对已保存"}


@router.post("/batch", summary="批量导入问答对")
async def batch(file: UploadFile = File(...), collection_id: str = Form(...),
                db: Session = Depends(get_db), user=Depends(get_request_user)):
    owned_collection(db, collection_id, user)
    data = await file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "问答文件不能超过 10 MB")
    try:
        text = data.decode("utf-8-sig")
        if (file.filename or "").lower().endswith(".json"):
            pairs = json.loads(text)
        elif (file.filename or "").lower().endswith(".csv"):
            pairs = list(csv.DictReader(io.StringIO(text)))
        else:
            raise HTTPException(422, "请选择 JSON 或 CSV 文件")
    except (UnicodeError, ValueError, csv.Error):
        raise HTTPException(422, "无法读取 UTF-8 问答文件，请检查格式") from None
    if not isinstance(pairs, list) or not pairs or len(pairs) > 1000:
        raise HTTPException(422, "问答文件应包含 1 至 1000 条记录")
    failures, saved = [], []
    for index, item in enumerate(pairs, 1):
        try:
            if not isinstance(item, dict):
                raise HTTPException(422, "问答记录必须是对象")
            saved.append(await save_pair(db, user, collection_id, item.get("question"), item.get("answer"),
                                         item.get("title"), item.get("metadata")))
        except HTTPException as exc:
            db.rollback()
            failures.append({"index": index, "reason": str(exc.detail)})
    return {"success": True, "message": f"已导入 {len(saved)} 条，失败 {len(failures)} 条", "result": {
        "total": len(pairs), "success": len(saved), "failed": len(failures), "failed_items": failures,
        "items": saved, "collection_id": collection_id}}


@router.get("/template", summary="下载问答导入模板")
async def template(format: str = "json"):
    example = [{"question": "示例：项目验收周期？", "answer": "示例：交付后 30 天。"}]
    if format == "json":
        data, mime = json.dumps(example, ensure_ascii=False, indent=2), "application/json"
    elif format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["question", "answer"])
        writer.writeheader()
        writer.writerows(example)
        data, mime = "\ufeff" + buffer.getvalue(), "text/csv"
    else:
        raise HTTPException(422, "模板格式只能是 json 或 csv")
    return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="qa-template.{format}"'})
