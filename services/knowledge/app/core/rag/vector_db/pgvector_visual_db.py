#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pgvector 视觉向量存储。

说明：
- 与文本向量 `rag_vectors` 分离，避免维度与检索语义混用。
- 当前面向 visual_similarity / image_to_image。
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from app.db.session import engine as default_engine
from app.shared.utils.logger_util import get_logger

logger = get_logger("PgVectorVisualStore")

VISUAL_VECTOR_TABLE = (os.getenv("VISUAL_VECTOR_TABLE") or "rag_visual_vectors").strip() or "rag_visual_vectors"
VISUAL_VECTOR_PREFIX = "visual_region:"


def _visual_dimension() -> int:
    try:
        return int(
            (
                # 统一视觉维度主配置名；CLIP_* 仅保留兼容 fallback。
                os.getenv("VISUAL_VECTOR_DIMENSION")
                or os.getenv("CLIP_VECTOR_DIMENSION")
                or "512"
            ).strip()
        )
    except Exception:
        return 512


def visual_vector_id_for_region_id(region_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{VISUAL_VECTOR_PREFIX}{region_id}"))


class PgVectorVisualStore:
    def __init__(self, engine: Engine = None):
        self.engine = engine or default_engine
        self.table = VISUAL_VECTOR_TABLE
        self.dimension = _visual_dimension()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        ddl = f"""
        CREATE EXTENSION IF NOT EXISTS vector;

        CREATE TABLE IF NOT EXISTS {self.table} (
            id UUID PRIMARY KEY,
            region_id TEXT NOT NULL UNIQUE,
            asset_id TEXT NOT NULL,
            content_id TEXT NOT NULL,
            vector_collection TEXT NOT NULL,
            provider TEXT NOT NULL,
            model_name TEXT NOT NULL,
            vector vector({self.dimension}) NOT NULL,
            metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_{self.table}_content_id ON {self.table} (content_id);
        CREATE INDEX IF NOT EXISTS idx_{self.table}_asset_id ON {self.table} (asset_id);
        CREATE INDEX IF NOT EXISTS idx_{self.table}_collection ON {self.table} (vector_collection);
        """
        with self.engine.begin() as conn:
            conn.execute(text(ddl))

        try:
            self._ensure_vector_index()
        except Exception as exc:
            logger.warning(f"视觉向量索引创建失败（已忽略）: {exc}")

    def _ensure_vector_index(self) -> None:
        auto_index = (os.getenv("PGVECTOR_AUTO_INDEX") or "1").strip().lower()
        if auto_index in {"0", "false", "no", "off"}:
            return

        hnsw_m = int((os.getenv("PGVECTOR_HNSW_M") or "16").strip())
        hnsw_ef_construction = int((os.getenv("PGVECTOR_HNSW_EF_CONSTRUCTION") or "64").strip())
        ivfflat_lists = int(
            (
                os.getenv("PGVECTOR_IVFFLAT_LISTS_VISUAL")
                or os.getenv("PGVECTOR_IVFFLAT_LISTS_IMAGES")
                or os.getenv("PGVECTOR_IVFFLAT_LISTS")
                or "200"
            ).strip()
        )

        with self.engine.begin() as conn:
            rows = conn.execute(
                text("SELECT amname FROM pg_am WHERE amname IN ('hnsw','ivfflat') ORDER BY amname")
            ).fetchall()
            methods = {row[0] for row in rows}

            if "hnsw" in methods:
                conn.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table}_vector_hnsw "
                        f"ON {self.table} USING hnsw (vector vector_cosine_ops) "
                        f"WITH (m={hnsw_m}, ef_construction={hnsw_ef_construction})"
                    )
                )
                conn.execute(text(f"ANALYZE {self.table}"))
                return

            if "ivfflat" in methods:
                conn.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.table}_vector_ivfflat "
                        f"ON {self.table} USING ivfflat (vector vector_cosine_ops) "
                        f"WITH (lists={ivfflat_lists})"
                    )
                )
                conn.execute(text(f"ANALYZE {self.table}"))
                return

    @staticmethod
    def _normalize_vector(vector: np.ndarray) -> np.ndarray:
        array = np.asarray(vector, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(array) + 1e-12)
        return (array / norm).astype(np.float32)

    def upsert_vector(
        self,
        *,
        region_id: str,
        asset_id: str,
        content_id: str,
        vector_collection: str,
        vector: np.ndarray,
        provider: str,
        model_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not region_id:
            raise ValueError("region_id 不能为空")

        normalized = self._normalize_vector(vector)
        if normalized.shape[0] != self.dimension:
            raise ValueError(f"视觉向量维度不匹配：期望 {self.dimension}，实际 {normalized.shape[0]}")

        vector_id = visual_vector_id_for_region_id(region_id)
        vec_str = "[" + ",".join(map(str, normalized.tolist())) + "]"

        sql = f"""
        INSERT INTO {self.table}
            (id, region_id, asset_id, content_id, vector_collection, provider, model_name, vector, metadata, updated_at)
        VALUES
            (:id, :region_id, :asset_id, :content_id, :vector_collection, :provider, :model_name, (:vector)::vector, (:metadata)::jsonb, NOW())
        ON CONFLICT (region_id) DO UPDATE SET
            asset_id = EXCLUDED.asset_id,
            content_id = EXCLUDED.content_id,
            vector_collection = EXCLUDED.vector_collection,
            provider = EXCLUDED.provider,
            model_name = EXCLUDED.model_name,
            vector = EXCLUDED.vector,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        """
        with self.engine.begin() as conn:
            conn.execute(
                text(sql),
                {
                    "id": vector_id,
                    "region_id": region_id,
                    "asset_id": asset_id,
                    "content_id": content_id,
                    "vector_collection": (vector_collection or "").strip() or "default",
                    "provider": provider,
                    "model_name": model_name,
                    "vector": vec_str,
                    "metadata": json.dumps(metadata or {}, ensure_ascii=False),
                },
            )
        return vector_id

    def delete_by_content_id(self, content_id: str) -> int:
        if not content_id:
            return 0
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(f"DELETE FROM {self.table} WHERE content_id=:content_id RETURNING id"),
                {"content_id": str(content_id)},
            ).fetchall()
        return len(rows)

    def delete_by_region_ids(self, region_ids: List[str]) -> int:
        if not region_ids:
            return 0
        stmt = text(f"DELETE FROM {self.table} WHERE region_id IN :region_ids RETURNING id").bindparams(
            bindparam("region_ids", expanding=True)
        )
        with self.engine.begin() as conn:
            rows = conn.execute(stmt, {"region_ids": [str(region_id) for region_id in region_ids]}).fetchall()
        return len(rows)

    def search(
        self,
        *,
        query_vector: np.ndarray,
        top_k: int = 5,
        collection_ids: Optional[List[str]] = None,
        filter_condition: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        vector = self._normalize_vector(query_vector)
        if vector.shape[0] != self.dimension:
            raise ValueError(f"视觉查询向量维度不匹配：期望 {self.dimension}，实际 {vector.shape[0]}")

        where_clauses: List[str] = []
        params: Dict[str, Any] = {
            "qvec": "[" + ",".join(map(str, vector.tolist())) + "]",
            "topk": max(1, int(top_k or 5)),
        }

        if collection_ids is not None:
            normalized_collections: List[str] = []
            seen: set[str] = set()
            for collection_id in collection_ids:
                if not collection_id:
                    continue
                candidate = str(collection_id).strip()
                if not candidate:
                    continue
                variants = (candidate, candidate.replace("_", "-"), candidate.replace("-", "_"))
                for variant in variants:
                    if variant and variant not in seen:
                        seen.add(variant)
                        normalized_collections.append(variant)
            if not normalized_collections:
                return []
            where_clauses.append("vector_collection IN :collection_ids")
            params["collection_ids"] = normalized_collections

        if filter_condition:
            where_clauses.append("metadata @> (:filter_condition)::jsonb")
            params["filter_condition"] = json.dumps(filter_condition, ensure_ascii=False)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        stmt = text(
            f"""
            SELECT id, region_id, asset_id, content_id, metadata, (1 - (vector <=> (:qvec)::vector)) AS score
            FROM {self.table}
            {where_sql}
            ORDER BY vector <=> (:qvec)::vector
            LIMIT :topk
            """
        )
        if "collection_ids" in params:
            stmt = stmt.bindparams(bindparam("collection_ids", expanding=True))

        with self.engine.begin() as conn:
            rows = conn.execute(stmt, params).fetchall()

        return [
            {
                "id": str(row[0]),
                "region_id": str(row[1]),
                "asset_id": str(row[2]),
                "content_id": str(row[3]),
                "metadata": row[4] or {},
                "score": float(row[5]),
            }
            for row in rows
        ]
