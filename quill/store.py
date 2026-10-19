"""Persistent metadata for a single shared workspace; user documents stay outside Git."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        for name in ("templates", "downloads", "knowledge-files"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.path = self.root / "quill.db"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS templates (id TEXT PRIMARY KEY, name TEXT UNIQUE, body TEXT)"
            )
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, body TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS artifacts (filename TEXT PRIMARY KEY, body TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS knowledge_files (resource_id TEXT PRIMARY KEY, body TEXT)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def add_template(self, name: str, variables: list[dict], template_id: str) -> dict:
        body = {
            "id": template_id,
            "name": name,
            "variables": variables,
            "category": "通用",
            "description": "自定义 Word 模板",
            "created_at": now(),
        }
        with self.connect() as db:
            db.execute("INSERT INTO templates VALUES (?, ?, ?)", (template_id, name, json.dumps(body)))
        return body

    def templates(self) -> list[dict]:
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT body FROM templates ORDER BY name")]

    def update_template_variables(self, template_id: str, variables: list[dict]) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT body FROM templates WHERE id=?", (template_id,)).fetchone()
            if row is None:
                raise ValueError("模板不存在。")
            body = json.loads(row[0])
            body.update(variables=variables, updated_at=now())
            db.execute("UPDATE templates SET body=? WHERE id=?", (json.dumps(body), template_id))
        return body

    def template(self, name: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT body FROM templates WHERE name=? OR id=?", (name, name)).fetchone()
        return json.loads(row[0]) if row else None

    def save_job(self, body: dict) -> dict:
        body["updated_at"] = now()
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO jobs VALUES (?, ?)", (body["id"], json.dumps(body)))
        return body

    def new_job(self, request: dict) -> dict:
        return self.save_job(
            {
                "id": uuid4().hex,
                "status": "queued",
                "request": request,
                "created_at": now(),
                "content": "",
                "sources": [],
                "progress": 0,
            }
        )

    def jobs(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT body FROM jobs ORDER BY rowid DESC LIMIT 100").fetchall()
        return [json.loads(row[0]) for row in rows]

    def job(self, job_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT body FROM jobs WHERE id=?", (job_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def recover(self) -> None:
        with self.connect() as db:
            rows = db.execute("SELECT body FROM jobs").fetchall()
        for row in rows:
            job = json.loads(row[0])
            if job["status"] in {"queued", "running"}:
                job.update(status="interrupted", error="服务已重启。已生成内容保留，可重新发起任务。")
                self.save_job(job)

    def artifact(self, filename: str, metadata: dict[str, Any] | None = None) -> dict | None:
        with self.connect() as db:
            if metadata is not None:
                db.execute("INSERT INTO artifacts VALUES (?, ?)", (filename, json.dumps(metadata)))
                return metadata
            row = db.execute("SELECT body FROM artifacts WHERE filename=?", (filename,)).fetchone()
        return json.loads(row[0]) if row else None

    def knowledge_file(self, resource_id: str, metadata: dict | None = None) -> dict | None:
        with self.connect() as db:
            if metadata is not None:
                db.execute(
                    "INSERT OR IGNORE INTO knowledge_files VALUES (?, ?)", (resource_id, json.dumps(metadata))
                )
            row = db.execute(
                "SELECT body FROM knowledge_files WHERE resource_id=?", (resource_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def delete_knowledge_file(self, resource_id: str) -> None:
        metadata = self.knowledge_file(resource_id)
        if metadata:
            (self.root / "knowledge-files" / metadata["stored_name"]).unlink(missing_ok=True)
        with self.connect() as db:
            db.execute("DELETE FROM knowledge_files WHERE resource_id=?", (resource_id,))
