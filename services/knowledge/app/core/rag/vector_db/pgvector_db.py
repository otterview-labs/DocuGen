#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PgVector 向量库实现（使用 Postgres + pgvector 扩展）
"""
import logging
import json
import os
import uuid
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from app.core.rag.vector_db.base import VectorDBBase
from app.config import settings
from app.db.session import engine as default_engine

logger = logging.getLogger(__name__)


class PgVectorVectorDB(VectorDBBase):
    """基于 pgvector 的向量库实现"""

    def __init__(self, engine: Engine = None):
        self.engine = engine or default_engine
        self.collections_table = "rag_vector_collections"
        self.vectors_table = "rag_vectors"
        self.dimension = settings.vector_db.VECTOR_DB_DIMENSION
        self._ensure_schema()

    # --- schema helpers ---
    def _ensure_schema(self):
        """确保 pgvector 扩展及基础表存在"""
        ddl = f"""
        CREATE EXTENSION IF NOT EXISTS vector;

        CREATE TABLE IF NOT EXISTS {self.collections_table} (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            dimension INT NOT NULL,
            distance TEXT DEFAULT 'cosine',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS {self.vectors_table} (
            id UUID PRIMARY KEY,
            collection_id INT NOT NULL REFERENCES {self.collections_table}(id) ON DELETE CASCADE,
            vector vector({self.dimension}) NOT NULL,
            metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """
        with self.engine.begin() as conn:
            conn.execute(text(ddl))

        try:
            self._ensure_indexes()
        except Exception as e:
            logger.warning("⚠️ pgvector 索引创建失败（可忽略）: %s", e)

    def _ensure_indexes(self) -> None:
        auto_index = (os.getenv("PGVECTOR_AUTO_INDEX") or "1").strip().lower()
        if auto_index in {"0", "false", "no", "off"}:
            return

        hnsw_m = int((os.getenv("PGVECTOR_HNSW_M") or "16").strip())
        hnsw_ef_construction = int((os.getenv("PGVECTOR_HNSW_EF_CONSTRUCTION") or "64").strip())
        ivfflat_lists = int(
            (
                os.getenv("PGVECTOR_IVFFLAT_LISTS_KNOWLEDGE")
                or os.getenv("PGVECTOR_IVFFLAT_LISTS")
                or "200"
            ).strip()
        )

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS idx_{self.vectors_table}_collection_id "
                    f"ON {self.vectors_table} (collection_id)"
                )
            )

            rows = conn.execute(
                text(
                    "SELECT amname FROM pg_am WHERE amname IN ('hnsw','ivfflat') ORDER BY amname"
                )
            ).fetchall()
            ams = {r[0] for r in rows}

            if "hnsw" in ams:
                conn.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.vectors_table}_vector_hnsw "
                        f"ON {self.vectors_table} USING hnsw (vector vector_cosine_ops) "
                        f"WITH (m={hnsw_m}, ef_construction={hnsw_ef_construction})"
                    )
                )
                conn.execute(text(f"ANALYZE {self.vectors_table}"))
                logger.info("✅ pgvector 向量索引已就绪（HNSW）")
                return

            if "ivfflat" in ams:
                conn.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.vectors_table}_vector_ivfflat "
                        f"ON {self.vectors_table} USING ivfflat (vector vector_cosine_ops) "
                        f"WITH (lists={ivfflat_lists})"
                    )
                )
                conn.execute(text(f"ANALYZE {self.vectors_table}"))
                logger.info("✅ pgvector 向量索引已就绪（IVFFLAT）")
                return

        logger.info("ℹ️ pgvector 未检测到 hnsw/ivfflat，跳过向量索引创建")

    def _get_collection_id(self, collection_name: str, create_if_missing: bool = True) -> Optional[int]:
        with self.engine.begin() as conn:
            res = conn.execute(
                text(f"SELECT id, dimension FROM {self.collections_table} WHERE name=:name"),
                {"name": collection_name},
            ).first()
            if res:
                cid, dim = res
                if dim != self.dimension:
                    logger.warning(f"集合 {collection_name} 维度不匹配，期望 {self.dimension}，实际 {dim}")
                return cid
            if not create_if_missing:
                return None
            res = conn.execute(
                text(
                    f"INSERT INTO {self.collections_table} (name, dimension) VALUES (:name, :dim) RETURNING id"
                ),
                {"name": collection_name, "dim": self.dimension},
            ).first()
            return res[0] if res else None

    # --- interface impl ---
    def create_collection(self, collection_name: str, dimension: int = 1536, **kwargs) -> bool:
        # dimension参数暂未动态支持，使用当前配置的 self.dimension
        self._get_collection_id(collection_name, create_if_missing=True)
        return True

    def collection_exists(self, collection_name: str) -> bool:
        return self._get_collection_id(collection_name, create_if_missing=False) is not None

    def list_collections(self) -> List[str]:
        with self.engine.begin() as conn:
            rows = conn.execute(text(f"SELECT name FROM {self.collections_table} ORDER BY id")).fetchall()
            return [r[0] for r in rows]

    def delete_collection(self, collection_name: str) -> bool:
        with self.engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {self.collections_table} WHERE name=:name"), {"name": collection_name})
        return True

    def add_vectors(
        self,
        collection_name: str,
        vectors: np.ndarray,
        metadata: List[Dict[str, Any]],
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        if vectors is None or len(vectors) == 0:
            return []
        cid = self._get_collection_id(collection_name, create_if_missing=True)
        if cid is None:
            raise ValueError(f"无法创建/获取集合 {collection_name}")
        vectors = np.asarray(vectors, dtype=np.float32)
        ids = ids or [str(uuid.uuid4()) for _ in range(len(vectors))]
        rows = []
        for vid, vec, meta in zip(ids, vectors, metadata):
            vec_str = "[" + ",".join(map(str, vec.tolist())) + "]"
            rows.append(
                {
                    "id": vid,
                    "collection_id": cid,
                    "vector": vec_str,
                    "metadata": json.dumps(meta or {}, ensure_ascii=False),
                }
            )
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {self.vectors_table} (id, collection_id, vector, metadata)
                    VALUES (:id, :collection_id, (:vector)::vector, (:metadata)::jsonb)
                    """
                ),
                rows,
            )
        return ids

    def search(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        top_k: int = 5,
        filter_condition: Optional[Dict] = None,
    ) -> Tuple[List[str], List[float], List[Dict]]:
        cid = self._get_collection_id(collection_name, create_if_missing=False)
        if cid is None:
            return [], [], []
        qvec = "[" + ",".join(map(str, np.asarray(query_vector, dtype=np.float32).tolist())) + "]"

        where_clauses = ["collection_id = :cid"]
        params: Dict[str, Any] = {"cid": cid, "topk": top_k, "qvec": qvec}
        if filter_condition:
            # 简单过滤支持：metadata @> jsonb
            where_clauses.append("metadata @> (:filt)::jsonb")
            params["filt"] = json.dumps(filter_condition, ensure_ascii=False)

        where_sql = " AND ".join(where_clauses)
        # 统一向量库接口：返回“相似度分数”（越大越相似），与 Milvus/FAISS 保持一致。
        # pgvector 的 `<=>` 为 cosine distance（越小越相似），这里转换为 cosine similarity：
        # score = 1 - distance
        sql = f"""
        SELECT id, metadata, (1 - (vector <=> (:qvec)::vector)) AS score
        FROM {self.vectors_table}
        WHERE {where_sql}
        ORDER BY vector <=> (:qvec)::vector
        LIMIT :topk
        """
        with self.engine.begin() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        ids = [r[0] for r in rows]
        scores = [float(r[2]) for r in rows]
        metas = [r[1] or {} for r in rows]
        return ids, scores, metas

    def search_by_ids(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        ids: List[str],
        top_k: int = 5,
    ) -> Tuple[List[str], List[float], List[Dict]]:
        """在指定集合内，仅在给定 id 列表中进行向量相似度排序。

        场景：selected_file_ids 已知候选集合（几百个），直接对候选向量做排序，避免全量检索。
        """
        if not ids:
            return [], [], []

        cid = self._get_collection_id(collection_name, create_if_missing=False)
        if cid is None:
            return [], [], []

        qvec = "[" + ",".join(map(str, np.asarray(query_vector, dtype=np.float32).tolist())) + "]"
        top_k = max(1, min(int(top_k or 5), len(ids)))

        stmt = (
            text(
                f"""
                SELECT id, metadata, (1 - (vector <=> (:qvec)::vector)) AS score
                FROM {self.vectors_table}
                WHERE collection_id = :cid AND id IN :ids
                ORDER BY vector <=> (:qvec)::vector
                LIMIT :topk
                """
            )
            .bindparams(bindparam("ids", expanding=True))
        )

        with self.engine.begin() as conn:
            rows = conn.execute(stmt, {"cid": cid, "qvec": qvec, "topk": top_k, "ids": ids}).fetchall()

        out_ids = [str(r[0]) for r in rows]
        scores = [float(r[2]) for r in rows]
        metas = [r[1] or {} for r in rows]
        return out_ids, scores, metas

    def delete_vectors(self, collection_name: str, ids: List[str]) -> bool:
        cid = self._get_collection_id(collection_name, create_if_missing=False)
        if cid is None or not ids:
            return False
        with self.engine.begin() as conn:
            stmt = (
                text(f"DELETE FROM {self.vectors_table} WHERE collection_id=:cid AND id IN :ids")
                .bindparams(bindparam("ids", expanding=True))
            )
            conn.execute(stmt, {"cid": cid, "ids": ids})
        return True

    def delete_by_metadata(self, collection_name: str, metadata_filter: Dict[str, Any]) -> int:
        cid = self._get_collection_id(collection_name, create_if_missing=False)
        if cid is None:
            return 0

        filt = metadata_filter or {}
        if not filt:
            return 0

        filt_json = json.dumps(filt, ensure_ascii=False)
        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    f"""
                    DELETE FROM {self.vectors_table}
                    WHERE collection_id=:cid AND metadata @> (:filt)::jsonb
                    RETURNING id
                    """
                ),
                {"cid": cid, "filt": filt_json},
            ).fetchall()
        return len(rows)

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        cid = self._get_collection_id(collection_name, create_if_missing=False)
        if cid is None:
            return {}
        with self.engine.begin() as conn:
            meta = conn.execute(
                text(
                    f"SELECT id, name, dimension, distance, created_at FROM {self.collections_table} WHERE id=:cid"
                ),
                {"cid": cid},
            ).first()
            count = conn.execute(
                text(f"SELECT COUNT(*) FROM {self.vectors_table} WHERE collection_id=:cid"),
                {"cid": cid},
            ).scalar_one()
        return {
            "id": meta.id,
            "name": meta.name,
            "dimension": meta.dimension,
            "distance": meta.distance,
            "created_at": meta.created_at.isoformat() if meta.created_at else None,
            "vector_count": count,
        }

    def update_metadata(self, collection_name: str, id: str, metadata: Dict[str, Any]) -> bool:
        cid = self._get_collection_id(collection_name, create_if_missing=False)
        if cid is None:
            return False
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    f"UPDATE {self.vectors_table} SET metadata=(:meta)::jsonb WHERE collection_id=:cid AND id=:id"
                ),
                {"cid": cid, "id": id, "meta": json.dumps(metadata or {}, ensure_ascii=False)},
            )
        return True
