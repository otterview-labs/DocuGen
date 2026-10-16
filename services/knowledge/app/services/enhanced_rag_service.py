#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强的RAG服务 - 核心文档处理和检索服务

**核心功能**：
- 文档向量化：智能分块、向量生成和存储
- 语义检索：基于Embedding的相似度搜索
- 知识图谱：实体抽取和关系构建
- 重排序：使用Rerank模型优化结果排序

**主要方法**：
- add_content(): 添加文档并向量化
- update_content(): 更新文档内容
- delete_content(): 删除文档和向量
- search(): 执行语义搜索
- search_with_rerank(): 搜索+重排序

**向量数据库支持**：
- Milvus: 生产环境（分布式）
- FAISS: 开发环境（本地）

**被使用位置**：
- app/services/unified_search_service.py: 搜索服务依赖
- app/services/multimodal_upload_service.py: 文档上传处理
- app/api/v1/rag/endpoints/document_operations.py: 文档操作API
- app/core/rag/three_layer_search.py: 三层搜索引擎
"""

import os
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime
import numpy as np
import uuid

from app.config import settings
from app.core.llm.embedding_model import create_embedding_model
from app.core.rag.vector_db import get_vector_db
from app.db.models.rag import (
    RAGCollection,
    RAGCollectionContent,
    RAGChunk,
    RAGContent,
    RAGMediaAsset,
    RAGQuery,
    RAGVisualRegion,
)
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.shared.parsers.smart_chunker import SmartChunker
from app.core.rag.utils.collection_mapper import collection_mapper
from app.shared.utils.visual_regions import (
    build_full_region_definition,
    crop_image_by_normalized_bbox,
    load_image_size,
    normalize_external_visual_regions,
    resolve_upload_file_path,
)

# 新增导入：知识图谱和增强功能
from app.core.kg.manager import KnowledgeGraphManager
from app.core.llm import create_rerank_model
from app.shared.parsers import LLMEnhancedParser

# 使用自定义logger工具，同时输出到控制台和文件
from app.shared.utils.logger_util import get_logger
logger = get_logger(
    name=__name__,
    file_name="rag_service.log",  # RAG服务单独的日志文件
    color_console=True
)

# 文档“概要/摘要”向量（用于 selected_file_ids 场景下快速在候选文档中做语义排序）
# 使用单独的向量集合避免与 chunk 向量混用。
DOC_PROFILE_COLLECTION = (os.getenv("DOC_PROFILE_COLLECTION") or "__doc_profiles").strip() or "__doc_profiles"
DOC_PROFILE_VECTOR_PREFIX = "doc_profile:"
VISUAL_ASSET_PREFIX = "visual_asset:"
VISUAL_REGION_PREFIX = "visual_region:"


def _resolve_embedding_runtime_config() -> Dict[str, str]:
    """解析主检索链实际使用的 embedding 配置。

    优先走 pydantic settings；旧环境变量只作为兼容回退。
    """
    openai_api_key = (getattr(settings.llm, "OPENAI_API_KEY", "") or "").strip()
    openai_api_base = (getattr(settings.llm, "OPENAI_API_BASE", "") or "").strip() or "https://api.openai.com/v1"
    openai_auth_mode = (getattr(settings.llm, "OPENAI_API_AUTH_MODE", "") or "bearer").strip().lower()
    openai_username = (getattr(settings.llm, "OPENAI_API_USERNAME", "") or "").strip()
    openai_password = (getattr(settings.llm, "OPENAI_API_PASSWORD", "") or "").strip()
    preferred_provider = (getattr(settings.embedding, "PROVIDER", "") or "").strip().lower()

    openai_model = (
        (getattr(settings.embedding, "OPENAI_EMBEDDING_MODEL", "") or "").strip()
        or (os.getenv("OPENAI_EMBED_MODEL") or "").strip()
        or (os.getenv("EMBEDDING_MODEL_NAME") or "").strip()
        or "text-embedding-ada-002"
    )
    local_url = (
        (getattr(settings.embedding, "LOCAL_EMBEDDING_URL", "") or "").strip()
        or (os.getenv("LOCAL_EMBEDDING_URL") or "").strip()
        or "http://localhost:8001"
    )
    local_model = (
        (getattr(settings.embedding, "LOCAL_EMBEDDING_MODEL", "") or "").strip()
        or (os.getenv("LOCAL_EMBEDDING_MODEL") or "").strip()
        or ""
    )
    local_auth_mode = (getattr(settings.embedding, "LOCAL_EMBEDDING_AUTH_MODE", "") or "none").strip().lower()
    local_api_key = (getattr(settings.embedding, "LOCAL_EMBEDDING_API_KEY", "") or "").strip()
    local_username = (getattr(settings.embedding, "LOCAL_EMBEDDING_USERNAME", "") or "").strip()
    local_password = (getattr(settings.embedding, "LOCAL_EMBEDDING_PASSWORD", "") or "").strip()

    if not preferred_provider:
        if openai_api_key or (openai_auth_mode in {"none", "basic"} and openai_api_base):
            preferred_provider = "openai"
        else:
            preferred_provider = "local"

    return {
        "provider": preferred_provider,
        "openai_api_key": openai_api_key,
        "openai_api_base": openai_api_base,
        "openai_auth_mode": openai_auth_mode,
        "openai_username": openai_username,
        "openai_password": openai_password,
        "openai_model": openai_model,
        "local_url": local_url,
        "local_model": local_model,
        "local_auth_mode": local_auth_mode,
        "local_api_key": local_api_key,
        "local_username": local_username,
        "local_password": local_password,
    }


def visual_asset_id_for_content(content_id: str, asset_key: str = "primary") -> str:
    """为内容生成稳定的视觉资产 ID。"""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{VISUAL_ASSET_PREFIX}{content_id}:{asset_key}"))


def visual_region_id_for_asset(asset_id: str, external_key: str) -> str:
    """为资产下 region 生成稳定 ID。"""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{VISUAL_REGION_PREFIX}{asset_id}:{external_key}"))


class EnhancedRAGService:
    """增强的RAG服务 - 集成向量搜索、语义检索和知识图谱功能"""

    def __init__(self, user_id: str = None):
        """初始化RAG服务

        Args:
            user_id: 用户ID，用于知识图谱命名空间
        """
        self.user_id = user_id
        self.embedding_model = None
        self.vector_db = None
        self.rerank_model = None
        self.llm_parser = None
        self.kg_manager = None
        # 向量维度：默认 1536（OpenAI-compatible 常见维度），可通过 VECTOR_DB_DIMENSION 覆盖
        try:
            self.dimension = int((os.getenv("VECTOR_DB_DIMENSION") or "1536").strip())
        except Exception:
            self.dimension = 1536

        # 初始化各个组件
        self._init_embedding_model()
        self._init_vector_db()
        self._init_rerank_model()
        self._init_llm_parser()
        self._init_kg_manager()

    def _init_embedding_model(self):
        """初始化嵌入模型"""
        try:
            runtime_config = _resolve_embedding_runtime_config()
            preferred_provider = runtime_config["provider"]

            def _try_init_openai() -> bool:
                if runtime_config["openai_auth_mode"] == "bearer" and not runtime_config["openai_api_key"]:
                    return False
                self.embedding_model = create_embedding_model(
                    model_type="OpenAI",
                    key=runtime_config["openai_api_key"],
                    model_name=runtime_config["openai_model"],
                    base_url=runtime_config["openai_api_base"],
                    auth_mode=runtime_config["openai_auth_mode"],
                    username=runtime_config["openai_username"],
                    password=runtime_config["openai_password"],
                )
                logger.info("OpenAI-compatible 嵌入模型初始化成功")
                return True

            def _try_init_local() -> bool:
                if not runtime_config["local_url"]:
                    return False
                kwargs: Dict[str, Any] = {
                    "model_type": "Local",
                    "base_url": runtime_config["local_url"],
                    "key": runtime_config["local_api_key"],
                    "auth_mode": runtime_config["local_auth_mode"],
                    "username": runtime_config["local_username"],
                    "password": runtime_config["local_password"],
                }
                if runtime_config["local_model"]:
                    kwargs["model_name"] = runtime_config["local_model"]
                self.embedding_model = create_embedding_model(**kwargs)
                logger.info("本地嵌入模型初始化成功")
                return True

            candidates = {
                "openai": ("OpenAI-compatible", _try_init_openai),
                "local": ("Local", _try_init_local),
            }

            preferred = candidates.get(preferred_provider)
            if preferred is not None:
                preferred_name, preferred_initializer = preferred
                try:
                    if preferred_initializer():
                        return
                    logger.warning(
                        f"EMBEDDING_PROVIDER={preferred_provider} 但 {preferred_name} embedding 配置不完整，按兼容顺序降级"
                    )
                except Exception as e:
                    logger.warning(f"{preferred_name} 嵌入模型初始化失败: {e}")

            for provider_key in ("openai", "local"):
                if provider_key == preferred_provider:
                    continue
                provider_name, initializer = candidates[provider_key]
                try:
                    if initializer():
                        return
                except Exception as e:
                    logger.warning(f"{provider_name} 嵌入模型初始化失败: {e}")

            self.embedding_model = None
            logger.warning("嵌入模型不可用，将使用关键词搜索")
        except Exception as e:
            logger.error(f"嵌入模型初始化失败: {e}")
            self.embedding_model = None

    def _init_vector_db(self):
        """初始化向量数据库"""
        try:
            # 按配置创建向量数据库（FAISS/Milvus 等）
            self.vector_db = get_vector_db()
            logger.info("向量数据库初始化成功")
        except Exception as e:
            logger.error(f"向量数据库初始化失败: {e}")
            self.vector_db = None

    def _init_rerank_model(self):
        """初始化重排序模型"""
        try:
            # 尝试初始化重排序模型
            self.rerank_model = create_rerank_model()
            logger.info("重排序模型初始化成功")
        except Exception as e:
            logger.warning(f"重排序模型初始化失败，将使用基础排序: {e}")
            self.rerank_model = None

    def _init_llm_parser(self):
        """初始化LLM解析器"""
        try:
            self.llm_parser = LLMEnhancedParser()
            logger.info("LLM解析器初始化成功")
        except Exception as e:
            logger.warning(f"LLM解析器初始化失败: {e}")
            self.llm_parser = None

    def _init_kg_manager(self):
        """初始化知识图谱管理器"""
        try:
            self.kg_manager = KnowledgeGraphManager(namespace=self.user_id or "default")
            logger.info("知识图谱管理器初始化成功")
        except Exception as e:
            logger.warning(f"知识图谱管理器初始化失败: {e}")
            self.kg_manager = None

    def _l2_normalize(self, embeddings: np.ndarray) -> np.ndarray:
        """对向量进行L2归一化（便于使用内积近似余弦相似度）"""
        if embeddings is None:
            return embeddings
        if isinstance(embeddings, list):
            embeddings = np.array(embeddings)
        if embeddings.ndim == 1:
            norm = np.linalg.norm(embeddings) + 1e-12
            return embeddings / norm
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-12
        return embeddings / norms

    async def process_document(
        self,
        content: str,
        title: Optional[str],
        collection_id: Optional[str],
        doc_id: str,
        *,
        description: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
        chunking_config: Optional[Dict[str, Any]] = None,
        save_chunks_to_db: bool = True,  # 新增参数，控制是否保存分块到数据库
    ) -> List[str]:
        """对给定内容执行分块、向量化，并写入向量库，返回生成的vector_ids。

        注意：该方法不负责回写关系数据库，调用方应自行更新 rag_contents 记录。
        如果 save_chunks_to_db=True，会将分块信息保存到 rag_chunks 表。
        """
        if not content:
            logger.warning("process_document: content为空，跳过")
            return []
        if not self.embedding_model or not self.vector_db:
            logger.error("process_document: 嵌入模型或向量数据库不可用")
            return []

        # 1) 分块（使用 SmartChunker，无 content_type 参数）
        try:
            chunker = SmartChunker()
            chunks = chunker.chunk_content(content, chunking_config or {})
        except Exception as e:
            logger.warning(f"SmartChunker 分块失败，回退到简单切分: {e}")
            chunks = []

        # 回退：若分块为空，则使用整段内容
        if not chunks:
            chunks = [{"content": content, "metadata": {"chunk_index": 0}}]

        # 提取文本与估算偏移
        # ✅ 修复：保持chunk索引映射，避免因跳过空chunk导致索引错位
        texts: List[str] = []
        offsets: List[Tuple[int, int]] = []
        chunk_mapping: List[int] = []  # 记录texts[i]对应原始chunks[j]
        cursor = 0
        for chunk_idx, ch in enumerate(chunks):
            txt = (ch.get("content") or "").strip()
            if not txt:
                logger.debug(f"跳过空chunk: chunk_index={chunk_idx}")
                continue
            idx = content.find(txt, cursor)
            if idx == -1:
                idx = max(0, cursor)
            start = idx
            end = start + len(txt)
            texts.append(txt)
            offsets.append((start, end))
            chunk_mapping.append(chunk_idx)  # ✅ 记录原始索引
            cursor = max(cursor, end)

        if not texts:
            texts = [content]
            offsets = [(0, len(content))]
            chunk_mapping = [0]

        # 2) 生成嵌入并归一化
        logger.info(f"准备向量化 {len(texts)} 个分块（原始chunks: {len(chunks)}）")
        embeddings, _ = self.embedding_model.encode(texts)
        embeddings = self._l2_normalize(embeddings)
        if isinstance(embeddings, np.ndarray):
            vectors = embeddings.astype(np.float32)
        else:
            vectors = np.array(embeddings, dtype=np.float32)

        # ✅ 验证向量化是否完整
        if len(vectors) != len(texts):
            logger.error(f"❌ 向量化不完整！texts数量: {len(texts)}, vectors数量: {len(vectors)}")
            raise ValueError(f"向量化失败：期望{len(texts)}个向量，实际得到{len(vectors)}个")

        logger.info(f"✅ 向量化成功：{len(vectors)} 个向量")

        # 3) 确保集合存在
        collection_name = collection_id or "default"
        if not self.vector_db.collection_exists(collection_name):
            self.vector_db.create_collection(collection_name, self.dimension)
            logger.info(f"创建新集合: {collection_name}")

        # 4) 先生成chunk_ids（在写入向量库之前）
        chunk_ids = [str(uuid.uuid4()) for _ in range(len(vectors))]

        # ✅ 最终验证：确保所有数组长度一致
        if not (len(texts) == len(vectors) == len(chunk_ids) == len(offsets) == len(chunk_mapping)):
            logger.error(
                f"❌ 数组长度不一致！"
                f"texts:{len(texts)}, vectors:{len(vectors)}, "
                f"chunk_ids:{len(chunk_ids)}, offsets:{len(offsets)}, "
                f"chunk_mapping:{len(chunk_mapping)}"
            )
            raise ValueError("内部错误：数组长度不一致")

        logger.info(f"✅ 数据验证通过：{len(texts)} 个有效分块准备写入")

        # 5) 写入向量库
        base_meta = {
            "doc_id": doc_id,  # ✅ 改名：id -> doc_id（避免混淆）
            "title": title or "",
            "description": description or "",
            "created_at": datetime.now().isoformat(),
        }
        if extra_metadata and isinstance(extra_metadata, dict):
            base_meta.update(extra_metadata)

        metas: List[Dict[str, Any]] = []
        for idx, (text, (start, end)) in enumerate(zip(texts, offsets)):
            # ✅ 修复：使用实际的chunk文本作为snippet，而不是从原始content中提取
            # 避免因content.find()定位不准导致snippet与实际向量内容不匹配
            snippet = text[:200]
            m = {
                **base_meta,
                "chunk_index": idx,
                "start_offset": start,
                "end_offset": end,
                "snippet": snippet,
            }

            # ✅ 修复：使用chunk_mapping获取正确的原始chunk索引
            if chunks and idx < len(chunk_mapping):
                original_chunk_idx = chunk_mapping[idx]  # ✅ 获取原始索引
                chunk_metadata = chunks[original_chunk_idx].get("metadata", {})
                if chunk_metadata:
                    # 保留 markdown 层级信息
                    if "heading_path" in chunk_metadata:
                        m["heading_path"] = chunk_metadata["heading_path"]
                    if "parent_heading" in chunk_metadata:
                        m["parent_heading"] = chunk_metadata["parent_heading"]
                    if "prev_sibling" in chunk_metadata:
                        m["prev_sibling"] = chunk_metadata["prev_sibling"]
                    if "next_sibling" in chunk_metadata:
                        m["next_sibling"] = chunk_metadata["next_sibling"]
                    if "is_complete_section" in chunk_metadata:
                        m["is_complete_section"] = chunk_metadata["is_complete_section"]

            metas.append(m)

        # ✅ 使用chunk_ids作为向量ID（而不是让Milvus自动生成）
        vector_ids = self.vector_db.add_vectors(
            collection_name=collection_name,
            vectors=vectors,
            metadata=metas,
            ids=chunk_ids  # ✅ 传递chunk_ids
        )

        # 5) 保存分块信息到数据库（如果启用）
        if save_chunks_to_db and vector_ids:
            try:
                db_gen = get_db()
                db = next(db_gen)

                # 获取分块策略信息（兼容多种字段名）
                strategy = chunking_config.get("strategy", "semantic") if chunking_config else "semantic"
                overlap = chunking_config.get("overlap_size") or chunking_config.get("overlap", 75) if chunking_config else 75

                embedding_model_name = (
                    getattr(self.embedding_model, "model_name", None)
                    or os.getenv("EMBEDDING_MODEL_NAME")
                    or "unknown"
                )

                # ✅ 保存每个分块（使用预生成的chunk_ids）
                for idx, (text, vector_id, (start, end)) in enumerate(zip(texts, vector_ids, offsets)):
                    # ✅ 提取分块元数据（包含层级信息）
                    chunk_metadata_dict = {
                        "chunk_number": idx + 1,
                        "total_chunks": len(texts),
                        "title": title or "",
                        "collection": collection_name
                    }

                    # ✅ 修复：使用chunk_mapping获取正确的原始chunk索引
                    if chunks and idx < len(chunk_mapping):
                        original_chunk_idx = chunk_mapping[idx]  # ✅ 获取原始索引
                        chunk_meta = chunks[original_chunk_idx].get("metadata", {})
                        if chunk_meta:
                            # 保留关键的层级信息
                            for key in ["heading_path", "parent_heading", "parent_level",
                                       "prev_sibling", "next_sibling", "section_index",
                                       "is_complete_section", "is_subsection",
                                       "parent_heading_path", "subsection_index"]:
                                if key in chunk_meta:
                                    chunk_metadata_dict[key] = chunk_meta[key]

                    chunk = RAGChunk(
                        id=vector_id,  # ✅ 使用vector_id作为主键（保持一致）
                        content_id=doc_id,  # 关联到RAGContent的ID
                        chunk_index=idx,
                        chunk_text=text,
                        chunk_size=len(text),
                        start_position=start,
                        end_position=end,
                        vector_id=vector_id,  # ✅ vector_id和id现在相同
                        embedding_model=embedding_model_name,  # 使用的嵌入模型
                        chunking_strategy=strategy,
                        overlap_size=overlap,
                        chunk_metadata=json.dumps(chunk_metadata_dict, ensure_ascii=False)
                    )
                    db.add(chunk)

                db.commit()
                logger.info(f"成功保存 {len(texts)} 个分块到数据库，content_id: {doc_id}")

            except Exception as e:
                logger.error(f"保存分块到数据库失败: {e}")
                if 'db' in locals():
                    db.rollback()
            finally:
                if 'db' in locals():
                    db.close()

        return vector_ids or []

    async def add_document_to_vector_db(self, document: RAGContent, db: Session = None) -> bool:
        """将文档实际写入向量数据库，并回写 vector_id 等信息。

        要求：document.content_text 已存在；vector_collection 为集合名；document.id 为内容ID。
        """
        try:
            if not self.embedding_model or not self.vector_db:
                logger.error("add_document_to_vector_db: 嵌入模型或向量数据库不可用")
                return False

            if not document or not (document.id and (document.content_text or "").strip()):
                logger.warning("add_document_to_vector_db: 文档为空或内容缺失，跳过")
                return False

            # 确保 DB 会话
            if not db:
                db_gen = get_db()
                db = next(db_gen)
                should_close = True
            else:
                should_close = False

            try:
                # 先保存到主数据库（确保数据存在）
                db.add(document)
                db.flush()  # 确保获取到ID，但不提交事务

                try:
                    # ✅ 从 content_metadata 中读取分块配置
                    chunking_config = {}
                    if document.content_metadata:
                        try:
                            metadata = json.loads(document.content_metadata) if isinstance(document.content_metadata, str) else document.content_metadata
                            if metadata and "chunking" in metadata:
                                raw_config = metadata["chunking"]
                                # 字段名映射：将前端字段名转换为SmartChunker期望的字段名
                                chunking_config = {
                                    "max_chunk_size": int(raw_config.get("size") or raw_config.get("max_chunk_size", 500)),
                                    "overlap_size": int(raw_config.get("overlap") or raw_config.get("overlap_size", 75)),
                                    "min_chunk_size": int(raw_config.get("min_size") or raw_config.get("min_chunk_size", 120)),
                                    "strategy": str(raw_config.get("strategy", "semantic")).strip(),
                                }
                                # markdown策略专用参数
                                if chunking_config["strategy"] == "markdown":
                                    if "split_level" in raw_config:
                                        chunking_config["split_level"] = int(raw_config["split_level"])
                                    if "fallback_strategy" in raw_config:
                                        chunking_config["fallback_strategy"] = str(raw_config["fallback_strategy"]).strip()

                                logger.info(f"从metadata读取分块配置: {chunking_config}")
                        except Exception as e:
                            logger.warning(f"解析chunking配置失败，使用默认配置: {e}")
                            chunking_config = {}

                    # 执行分块、嵌入与入库
                    vector_ids = await self.process_document(
                        content=document.content_text or "",
                        title=document.title or "",
                        collection_id=document.vector_collection or "default",
                        doc_id=document.id,
                        description=document.description or "",
                        extra_metadata={
                            "content_type": document.content_type,
                            "file_name": getattr(document, "file_name", None),
                            "file_size": getattr(document, "file_size", None),
                        },
                        chunking_config=chunking_config,  # ✅ 传递配置
                        # 保存分块到 rag_chunks
                        save_chunks_to_db=True,
                    )

                    # 回写一个代表向量ID（取第一个，兼容旧字段）
                    if vector_ids:
                        try:
                            document.vector_id = vector_ids[0]
                        except Exception:
                            pass

                    # 提交主数据库事务
                    db.commit()
                    logger.info(f"文档 {document.id} 成功写入数据库与向量库")

                    # 写入/更新文档概要向量（用于“候选文档集”语义排序）
                    try:
                        await self.upsert_doc_profile_vector(document)
                    except Exception as e:
                        logger.warning(f"更新文档概要向量失败（已忽略）: {e}")

                    # 写入/更新视觉索引（仅图片内容）
                    try:
                        await self.upsert_visual_similarity_index(document, db)
                    except Exception as e:
                        logger.warning(f"更新视觉索引失败（已忽略）: {e}")
                    return True

                except Exception as e:
                    # 如果向量数据库写入失败，回滚主数据库事务
                    db.rollback()
                    logger.error(f"向量数据库写入失败，已回滚主数据库事务: {e}")
                    raise

            finally:
                if should_close:
                    db.close()

        except Exception as e:
            logger.error(f"添加文档到向量数据库失败: {e}")
            return False

    async def remove_document_from_vector_db(self, document_id: str, collection_id: Optional[str] = None,
                                           db: Optional[Session] = None) -> bool:
        """从向量数据库移除文档，同时保证主数据库数据一致性

        Args:
            document_id: 文档ID
            collection_id: 集合ID（可选）
            db: 数据库会话（可选）

        Returns:
            是否成功删除
        """
        try:
            # 处理数据库会话
            if db is None:
                db_gen = get_db()
                db = next(db_gen)
                should_close = True
            else:
                should_close = False

            try:
                # 1. 先查询文档信息，确认存在
                document = db.query(RAGContent).filter(RAGContent.id == document_id).first()
                if not document:
                    logger.warning(f"文档 {document_id} 在数据库中不存在")
                    return False

                # 获取集合信息
                if not collection_id:
                    collection_id = document.vector_collection or "default"

                # 2. 先从向量数据库删除（如果失败，主数据库数据保持不变）
                if self.vector_db:
                    try:
                        # 使用新的按元数据删除方法
                        deleted_count = self.vector_db.delete_by_metadata(
                            collection_name=collection_id,
                            metadata_filter={"id": document_id}
                        )
                        logger.info(f"从向量数据库删除了 {deleted_count} 个向量")

                        # 也尝试删除相关的分块
                        # 注意：这里假设分块的元数据中也有doc_id字段
                        chunk_deleted = self.vector_db.delete_by_metadata(
                            collection_name=collection_id,
                            metadata_filter={"doc_id": document_id}
                        )
                        if chunk_deleted > 0:
                            logger.info(f"从向量数据库删除了 {chunk_deleted} 个相关分块")

                        # 删除文档概要向量（如果已启用）
                        try:
                            if self.vector_db.collection_exists(DOC_PROFILE_COLLECTION):
                                vid = self.doc_profile_vector_id_for_doc_id(document_id)
                                self.vector_db.delete_vectors(DOC_PROFILE_COLLECTION, [vid])
                        except Exception as e:
                            logger.warning(f"删除文档概要向量失败（已忽略）: {e}")

                        # 删除视觉向量
                        try:
                            from app.core.rag.vector_db.pgvector_visual_db import PgVectorVisualStore

                            deleted_visual = PgVectorVisualStore().delete_by_content_id(document_id)
                            if deleted_visual > 0:
                                logger.info(f"删除了 {deleted_visual} 个视觉向量")
                        except Exception as e:
                            logger.warning(f"删除视觉向量失败（已忽略）: {e}")

                    except Exception as e:
                        logger.error(f"从向量数据库删除失败: {e}")
                        # 如果向量数据库删除失败，不删除主数据库记录
                        return False

                # 3. 删除相关的分块记录（如果有）
                try:
                    chunk_count = db.query(RAGChunk).filter(RAGChunk.content_id == document_id).count()
                    if chunk_count > 0:
                        db.query(RAGChunk).filter(RAGChunk.content_id == document_id).delete()
                        logger.info(f"删除了 {chunk_count} 个相关分块记录")
                except Exception as e:
                    logger.warning(f"删除分块记录时出错: {e}")

                try:
                    region_count = db.query(RAGVisualRegion).join(
                        RAGMediaAsset, RAGVisualRegion.asset_id == RAGMediaAsset.id
                    ).filter(RAGMediaAsset.content_id == document_id).count()
                    if region_count > 0:
                        db.query(RAGVisualRegion).filter(
                            RAGVisualRegion.asset_id.in_(
                                db.query(RAGMediaAsset.id).filter(RAGMediaAsset.content_id == document_id)
                            )
                        ).delete(synchronize_session=False)
                        logger.info(f"删除了 {region_count} 条视觉区域记录")
                except Exception as e:
                    logger.warning(f"删除视觉区域记录时出错: {e}")

                try:
                    asset_count = db.query(RAGMediaAsset).filter(RAGMediaAsset.content_id == document_id).count()
                    if asset_count > 0:
                        db.query(RAGMediaAsset).filter(RAGMediaAsset.content_id == document_id).delete(synchronize_session=False)
                        logger.info(f"删除了 {asset_count} 条媒体资产记录")
                except Exception as e:
                    logger.warning(f"删除媒体资产记录时出错: {e}")

                # 4. 最后删除主数据库中的文档记录
                db.delete(document)
                db.commit()

                logger.info(f"文档 {document_id} 及其相关数据已完全删除")
                return True

            except Exception as e:
                db.rollback()
                logger.error(f"删除文档失败，已回滚事务: {e}")
                return False

            finally:
                if should_close:
                    db.close()

        except Exception as e:
            logger.error(f"从向量数据库移除文档失败: {e}")
            return False

    def _prepare_content_for_embedding(self, document: RAGContent) -> str:
        """准备用于嵌入的内容"""
        content_parts = []

        # 添加标题
        if document.title:
            content_parts.append(f"标题: {document.title}")

        # 添加描述
        if document.description:
            content_parts.append(f"描述: {document.description}")

        # 添加摘要
        if document.content_summary:
            content_parts.append(f"摘要: {document.content_summary}")

        # 添加标签
        if document.content_tags:
            try:
                tags = json.loads(document.content_tags) if isinstance(document.content_tags, str) else document.content_tags
                if tags:
                    content_parts.append(f"标签: {', '.join(tags)}")
            except:
                pass

        # 添加文本内容（截断）
        if document.content_text:
            content_text = document.content_text[:2000]  # 限制长度
            content_parts.append(f"内容: {content_text}")

        return "\n".join(content_parts)

    @staticmethod
    def doc_profile_vector_id_for_doc_id(doc_id: str) -> str:
        """为 doc_id 生成稳定的 UUID（用于 doc-profile 向量主键）。"""
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{DOC_PROFILE_VECTOR_PREFIX}{doc_id}"))

    def _build_doc_profile_text(self, document: RAGContent) -> str:
        """构建文档概要向量的文本（尽量短、稳定、可更新）。"""
        parts: List[str] = []

        title = (document.title or "").strip()
        if title:
            parts.append(title)

        summary = (document.content_summary or "").strip()
        if summary:
            parts.append(summary)

        desc = (document.description or "").strip()
        if desc:
            parts.append(desc)

        tags = None
        try:
            raw = document.content_tags
            if isinstance(raw, str):
                tags = json.loads(raw) if raw else []
            else:
                tags = raw
        except Exception:
            tags = []

        if isinstance(tags, list):
            tag_list = [str(t).strip() for t in tags if str(t).strip()]
            if tag_list:
                parts.append("标签: " + ", ".join(tag_list[:30]))

        text = "\n".join(parts).strip()
        # 限制长度，避免 embedding 成本过高
        return text[:4000]

    async def upsert_doc_profile_vector(self, document: RAGContent) -> bool:
        """写入/更新文档概要向量（doc-level），用于“候选文档集”快速语义排序。"""
        if not document or not getattr(document, "id", None):
            return False
        if not self.embedding_model or not self.vector_db:
            return False

        profile_text = self._build_doc_profile_text(document)
        if not profile_text:
            return False

        # 1) 生成向量并归一化
        emb, _ = self.embedding_model.encode([profile_text])
        emb = self._l2_normalize(emb)
        vec = np.asarray(emb[0], dtype=np.float32).reshape(1, -1)

        # 2) 确保集合存在
        if not self.vector_db.collection_exists(DOC_PROFILE_COLLECTION):
            self.vector_db.create_collection(DOC_PROFILE_COLLECTION, self.dimension)

        # 3) 使用稳定 UUID 作为主键，避免重复与便于按 doc_id 定位
        vid = self.doc_profile_vector_id_for_doc_id(str(document.id))
        meta = {
            "doc_id": str(document.id),
            "vector_collection": (document.vector_collection or "").strip() or "default",
            "content_type": (document.content_type or "").strip(),
            "file_name": getattr(document, "file_name", None),
            "updated_at": datetime.now().isoformat(),
        }

        # 删除旧记录后写入（pgvector 表主键为 uuid，直接 insert 会冲突）
        try:
            self.vector_db.delete_vectors(DOC_PROFILE_COLLECTION, [vid])
        except Exception:
            pass

        self.vector_db.add_vectors(DOC_PROFILE_COLLECTION, vec, [meta], ids=[vid])
        return True

    async def rank_doc_ids_by_doc_profile(
        self,
        *,
        query: str,
        doc_ids: List[str],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """在给定 doc_ids 范围内，使用 doc-profile 向量对文档做语义排序。"""
        if not query or not (doc_ids or []):
            return []
        if not self.embedding_model or not self.vector_db:
            return []
        if not self.vector_db.collection_exists(DOC_PROFILE_COLLECTION):
            return []

        # 1) 查询向量
        qvec, _ = self.embedding_model.encode_queries(query)
        qvec = self._l2_normalize(qvec).astype(np.float32)

        # 2) 候选向量 ID（稳定 UUID）
        uniq_doc_ids: List[str] = []
        seen = set()
        for d in doc_ids:
            if not d:
                continue
            ds = str(d)
            if ds in seen:
                continue
            seen.add(ds)
            uniq_doc_ids.append(ds)

        vid_to_doc: Dict[str, str] = {}
        candidate_vids: List[str] = []
        for ds in uniq_doc_ids:
            vid = self.doc_profile_vector_id_for_doc_id(ds)
            vid_to_doc[vid] = ds
            candidate_vids.append(vid)

        top_k = max(1, min(int(top_k or 10), len(candidate_vids)))

        # 3) 仅在候选向量集合中排序（pgvector 走 SQL；其他向量库可按需实现同名方法）
        if not hasattr(self.vector_db, "search_by_ids"):
            return []

        ids, scores, metas = self.vector_db.search_by_ids(
            DOC_PROFILE_COLLECTION, qvec, candidate_vids, top_k=top_k
        )

        ranked: List[Dict[str, Any]] = []
        for vid, score, meta in zip(ids, scores, metas):
            doc_id = vid_to_doc.get(str(vid))
            if not doc_id:
                continue
            ranked.append(
                {
                    "doc_id": doc_id,
                    "score": float(score),
                    "metadata": meta or {},
                }
            )
        return ranked

    def _extract_visual_config(self, document: RAGContent) -> Dict[str, Any]:
        try:
            metadata = document.content_metadata
            if isinstance(metadata, str):
                metadata = json.loads(metadata) if metadata else {}
            if not isinstance(metadata, dict):
                return {}
            visual = metadata.get("visual")
            return visual if isinstance(visual, dict) else {}
        except Exception:
            return {}

    def _resolve_visual_source_path(self, document: RAGContent) -> Optional[str]:
        try:
            if getattr(document, "file_path", None):
                candidate = os.path.abspath(str(document.file_path))
                if os.path.exists(candidate):
                    return candidate
        except Exception:
            pass

        try:
            upload_path = resolve_upload_file_path(getattr(document, "content_url", None))
            if upload_path:
                return upload_path
        except Exception:
            pass

        return None

    def _upsert_visual_asset_record(
        self,
        *,
        document: RAGContent,
        image_path: str,
        width: int,
        height: int,
        db: Session,
    ) -> RAGMediaAsset:
        asset_key = "primary"
        asset_id = visual_asset_id_for_content(str(document.id), asset_key)
        asset = db.query(RAGMediaAsset).filter(RAGMediaAsset.id == asset_id).first()
        if asset is None:
            asset = RAGMediaAsset(
                id=asset_id,
                content_id=str(document.id),
                asset_key=asset_key,
                asset_type="image",
            )
            db.add(asset)

        asset.file_path = image_path
        asset.file_url = getattr(document, "content_url", None)
        asset.width = int(width)
        asset.height = int(height)
        asset.asset_metadata = {
            "content_type": getattr(document, "content_type", None),
            "resource_id": getattr(document, "resource_id", None),
            "updated_at": datetime.now().isoformat(),
        }
        asset.status = "1"
        return asset

    def _sync_visual_regions(
        self,
        *,
        asset: RAGMediaAsset,
        external_regions: List[Dict[str, Any]],
        db: Session,
    ) -> tuple[List[RAGVisualRegion], List[str]]:
        region_defs = [build_full_region_definition()] + list(external_regions or [])
        desired_keys = {str(region_def["external_key"]) for region_def in region_defs}

        existing_regions = db.query(RAGVisualRegion).filter(RAGVisualRegion.asset_id == asset.id).all()
        existing_by_key = {str(region.external_key): region for region in existing_regions}

        stale_region_ids: List[str] = []
        for region in existing_regions:
            region_key = str(region.external_key)
            if region_key == "__full__":
                continue
            if region.source == "external" and region_key not in desired_keys:
                stale_region_ids.append(str(region.id))
                db.delete(region)

        synced_regions: List[RAGVisualRegion] = []
        for region_def in region_defs:
            external_key = str(region_def["external_key"])
            region = existing_by_key.get(external_key)
            if region is None:
                region = RAGVisualRegion(
                    id=visual_region_id_for_asset(asset.id, external_key),
                    asset_id=asset.id,
                    external_key=external_key,
                )
                db.add(region)

            region.external_region_id = region_def.get("external_region_id")
            region.region_type = str(region_def.get("region_type") or "bbox")
            region.coord_space = str(region_def.get("coord_space") or "normalized")
            region.bbox_raw = region_def.get("bbox_raw")
            region.bbox_normalized = region_def.get("bbox_normalized")
            region.label = region_def.get("label")
            region.confidence = region_def.get("confidence")
            region.region_text = region_def.get("region_text")
            region.source = str(region_def.get("source") or "external")
            region.source_system = region_def.get("source_system")
            region.sort_order = int(region_def.get("sort_order", 0) or 0)
            region.region_metadata = region_def.get("metadata") or {}
            region.status = "1"
            synced_regions.append(region)

        return synced_regions, stale_region_ids

    async def upsert_visual_similarity_index(self, document: RAGContent, db: Session) -> bool:
        """写入/更新视觉索引（整图 + 外部传入 bbox region）。"""
        if not document or not getattr(document, "id", None):
            return False
        if (document.content_type or "").strip().lower() != "image":
            return False

        image_path = self._resolve_visual_source_path(document)
        if not image_path:
            logger.warning(f"视觉索引跳过: 未找到图片路径 content_id={getattr(document, 'id', None)}")
            return False

        try:
            width, height = load_image_size(image_path)
        except Exception as exc:
            logger.warning(f"视觉索引跳过: 无法读取图片尺寸 content_id={document.id}, error={exc}")
            return False

        visual_config = self._extract_visual_config(document)
        external_regions = normalize_external_visual_regions(
            visual_config.get("regions"),
            width=width,
            height=height,
            default_source_system=visual_config.get("source_system"),
        )

        try:
            from app.core.rag.vector_db.pgvector_visual_db import PgVectorVisualStore
            from app.shared.vlm.visual_embedding import get_visual_image_embedder

            embedder = get_visual_image_embedder()
            store = PgVectorVisualStore()

            asset = self._upsert_visual_asset_record(
                document=document,
                image_path=image_path,
                width=width,
                height=height,
                db=db,
            )
            db.flush()

            regions, stale_region_ids = self._sync_visual_regions(
                asset=asset,
                external_regions=external_regions,
                db=db,
            )
            db.flush()

            if stale_region_ids:
                try:
                    store.delete_by_region_ids(stale_region_ids)
                except Exception as exc:
                    logger.warning(f"删除过期视觉向量失败（已忽略）: {exc}")

            for region in regions:
                bbox_normalized = region.bbox_normalized or [0.0, 0.0, 1.0, 1.0]
                if region.region_type == "full":
                    vector = await asyncio.to_thread(embedder.embed_image_file, image_path)
                else:
                    cropped = crop_image_by_normalized_bbox(image_path, bbox_normalized)
                    vector = await asyncio.to_thread(embedder.embed_pil_image, cropped)

                store.upsert_vector(
                    region_id=str(region.id),
                    asset_id=str(asset.id),
                    content_id=str(document.id),
                    vector_collection=(document.vector_collection or "").strip() or "default",
                    vector=vector,
                    provider=getattr(embedder, "provider", "clip"),
                    model_name=getattr(embedder, "model_name", "visual-embedding"),
                    metadata={
                        "content_id": str(document.id),
                        "asset_id": str(asset.id),
                        "region_id": str(region.id),
                        "region_type": region.region_type,
                        "bbox": bbox_normalized,
                        "label": region.label,
                        "source": region.source,
                        "source_system": region.source_system,
                        "content_type": "image",
                    },
                )

            db.commit()
            logger.info(
                f"视觉索引更新成功: content_id={document.id}, asset_id={asset.id}, regions={len(regions)}"
            )
            return True
        except Exception as exc:
            db.rollback()
            try:
                from app.core.rag.vector_db.pgvector_visual_db import PgVectorVisualStore

                PgVectorVisualStore().delete_by_content_id(str(document.id))
            except Exception:
                pass
            logger.warning(f"upsert_visual_similarity_index 失败: {exc}")
            return False

    def _calculate_keyword_similarity(self, query: str, document: Any) -> float:
        """计算关键词相似度分数"""
        try:
            # 提取查询关键词
            query_keywords = set(query.lower().split())

            # 构建文档文本
            doc_text = ""
            if hasattr(document, 'title') and document.title:
                doc_text += document.title + " "
            if hasattr(document, 'description') and document.description:
                doc_text += document.description + " "
            if hasattr(document, 'content_text') and document.content_text:
                doc_text += document.content_text[:1000] + " "  # 限制长度
            if hasattr(document, 'content_summary') and document.content_summary:
                doc_text += document.content_summary + " "

            doc_words = set(doc_text.lower().split())

            # 计算交集
            intersection = query_keywords.intersection(doc_words)

            if not query_keywords:
                return 0.0

            # 基础匹配分数
            base_score = len(intersection) / len(query_keywords)

            # 考虑标题和描述的权重
            title_bonus = 0.0
            if hasattr(document, 'title') and document.title:
                title_words = set(document.title.lower().split())
                title_matches = query_keywords.intersection(title_words)
                title_bonus = 0.3 * len(title_matches) / len(query_keywords)

            # 考虑完全匹配的奖励
            exact_match_bonus = 0.0
            if query.lower() in doc_text.lower():
                exact_match_bonus = 0.4

            # 综合分数
            final_score = min(1.0, base_score + title_bonus + exact_match_bonus)
            return round(final_score, 3)

        except Exception as e:
            logger.error(f"计算关键词相似度失败: {e}")
            return 0.3  # 默认低分数

    async def semantic_search(self, query: str, collection_id: Optional[Union[str, List[str]]] = None,
                            top_k: int = 5, similarity_threshold: float = 0.15) -> List[Dict[str, Any]]:
        """语义搜索

        Args:
            query: 搜索查询
            collection_id: 集合ID（单个字符串）或集合ID列表（支持多集合搜索）
            top_k: 返回结果数量
            similarity_threshold: 相似度阈值
        """
        try:
            if not self.embedding_model or not self.vector_db:
                logger.warning("嵌入模型或向量数据库不可用，降级到关键词搜索")
                return await self._fallback_keyword_search(query, collection_id, top_k)

            # 对短查询动态降低阈值，避免短问句被过滤
            effective_threshold = similarity_threshold
            if query and len(query) <= 6:
                effective_threshold = min(similarity_threshold, 0.05)
            if effective_threshold is None:
                effective_threshold = 0.0

            # 生成查询向量并L2归一化
            query_embedding, _ = self.embedding_model.encode_queries(query)
            if isinstance(query_embedding, list):
                query_embedding = np.array(query_embedding)
            # 归一化（cosine == 内积）
            qn = np.linalg.norm(query_embedding) + 1e-12
            query_embedding = (query_embedding / qn).astype(np.float32)

            # 兼容处理：将单个collection_id转换为列表
            if collection_id is not None:
                if isinstance(collection_id, str):
                    collection_id = [collection_id]

                # 兼容不同向量库的集合命名规则：优先使用原始ID，不存在则尝试常见的归一化形式
                collections = []
                for coll_id in collection_id:
                    candidates = [
                        coll_id,
                        coll_id.replace("-", "_"),
                        coll_id.replace("_", "-"),
                        collection_mapper.to_milvus_name(coll_id),
                    ]
                    found = None
                    for cand in candidates:
                        if not cand:
                            continue
                        try:
                            if self.vector_db.collection_exists(cand):
                                found = cand
                                break
                        except Exception:
                            continue

                    if found:
                        collections.append(found)
                    else:
                        logger.info(f"集合 {coll_id} 不存在，跳过")

                # 如果没有任何有效集合，返回空结果
                if not collections:
                    logger.warning(f"指定的集合均不存在: {collection_id}")
                    return []
            else:
                # 未指定集合：搜索全部集合（智能筛选有数据的集合）
                all_collections = self.vector_db.list_collections()

                # ✅ 优化策略：优先搜索有数据的集合
                collections_with_data = []
                for coll_name in all_collections:
                    try:
                        info = self.vector_db.get_collection_info(coll_name) or {}
                        vector_count = info.get("vector_count", 0)
                        try:
                            vector_count = int(vector_count)
                        except Exception:
                            vector_count = 0

                        if vector_count > 0:
                            collections_with_data.append(coll_name)
                        # 限制最多50个集合
                        if len(collections_with_data) >= 50:
                            break
                    except:
                        # 出错的集合跳过
                        continue

                collections = collections_with_data if collections_with_data else all_collections[:10]

                if len(collections_with_data) > 0:
                    logger.info(f"智能筛选后将搜索 {len(collections)} 个有数据的集合（共{len(all_collections)}个集合）")
                else:
                    logger.warning(f"集合数量过多（{len(all_collections)}个），仅搜索前10个集合")

            # 执行集合范围内的搜索
            results = []
            for coll_name in collections:
                try:
                    coll_results = await self._search_collection(coll_name, query_embedding, top_k, effective_threshold)
                    results.extend(coll_results)
                except Exception as e:
                    logger.warning(f"搜索集合 {coll_name} 失败: {e}")

            # 按相似度排序并限制数量
            results.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
            if results:
                return results[:top_k]

            # 若被阈值过滤完，尝试放宽阈值再搜一轮
            if effective_threshold > 0:
                relaxed_top_k = max(top_k * 2, 10)
                relaxed_results = []
                for coll_name in collections:
                    try:
                        relaxed_results.extend(
                            await self._search_collection(coll_name, query_embedding, relaxed_top_k, 0.0)
                        )
                    except Exception as e:
                        logger.warning(f"放宽阈值搜索集合 {coll_name} 失败: {e}")
                relaxed_results.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
                return relaxed_results[:top_k]

            return []

        except Exception as e:
            logger.error(f"语义搜索失败: {e}")
            # 降级到关键词搜索
            return await self._fallback_keyword_search(query, collection_id, top_k)

    async def _search_collection(self, collection_name: str, query_embedding: np.ndarray,
                               top_k: int, similarity_threshold: float) -> List[Dict[str, Any]]:
        """搜索单个集合"""
        try:
            verbose_debug = os.getenv("SEARCH_VERBOSE_LOG", "false").lower() == "true"

            # 执行向量搜索
            vector_ids, scores, metadata_list = self.vector_db.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                top_k=top_k
            )

            results = []
            filtered_by_threshold = 0
            filtered_by_db_missing = 0
            filtered_by_empty_content = 0

            # 使用数据库会话获取完整内容
            db_gen = get_db()
            db = next(db_gen)

            try:
                # 1) 先做阈值过滤，并收集 doc_id（批量查库，避免 N+1）
                candidates: List[Dict[str, Any]] = []
                for vector_id, score, metadata in zip(vector_ids, scores, metadata_list):
                    if score < similarity_threshold:
                        filtered_by_threshold += 1
                        continue

                    meta = metadata if isinstance(metadata, dict) else (metadata or {})
                    # ✅ 兼容旧数据(id)和新数据(doc_id)
                    content_id = str(meta.get("doc_id") or meta.get("id") or vector_id)
                    candidates.append(
                        {"vector_id": str(vector_id), "score": float(score), "metadata": meta, "content_id": content_id}
                    )

                if not candidates:
                    if verbose_debug:
                        logger.info(
                            f"🔍 [DEBUG] 过滤统计 - 集合: {collection_name}, Milvus返回: {len(vector_ids)} 个, 相似度过滤: {filtered_by_threshold} 个, 最终返回: 0 个"
                        )
                    return []

                # 2) 批量拉取文档记录
                content_ids = list({c["content_id"] for c in candidates})
                content_records = db.query(RAGContent).filter(RAGContent.id.in_(content_ids)).all()
                content_map = {str(r.id): r for r in content_records}

                # 3) 构建结果
                for c in candidates:
                    full_content = content_map.get(c["content_id"])
                    if not full_content:
                        filtered_by_db_missing += 1
                        continue

                    if not full_content.content_text and not full_content.description and not full_content.title:
                        filtered_by_empty_content += 1
                        continue

                    # 构建搜索结果
                    # ✅ 修复：使用分块ID作为主ID，避免同文档多分块被去重
                    # ✅ 修复：返回分块内容而不是完整文档

                    # 获取分块内容（如果有分块信息）
                    chunk_content = None
                    meta = c["metadata"]
                    start_offset = meta.get("start_offset")
                    end_offset = meta.get("end_offset")

                    if start_offset is not None and end_offset is not None and full_content.content_text:
                        # 有分块位置信息，截取对应的分块内容
                        try:
                            chunk_content = full_content.content_text[start_offset:end_offset]
                        except Exception as e:
                            if verbose_debug:
                                logger.warning(f"提取分块内容失败: {e}, 使用摘要/截断内容")
                            chunk_content = None

                    # 如果没有分块内容，使用摘要或截取前1000字符
                    if not chunk_content:
                        if full_content.content_summary:
                            chunk_content = full_content.content_summary
                        elif full_content.content_text:
                            # 截取前1000字符作为预览
                            chunk_content = full_content.content_text[:1000] + ("..." if len(full_content.content_text) > 1000 else "")
                        else:
                            chunk_content = full_content.description or ""

                    result = {
                        "id": c["vector_id"],  # ✅ 使用分块ID（vector_id）
                        "doc_id": c["content_id"],  # ✅ 添加文档ID字段
                        "title": full_content.title or meta.get("title", ""),
                        "description": full_content.description or meta.get("description", ""),
                        "content": chunk_content,  # ✅ 返回分块内容，而不是完整文档
                        "content_type": full_content.content_type or meta.get("content_type", ""),
                        "similarity_score": float(c["score"]),
                        # 优先返回分片命中片段
                        "snippet": meta.get("snippet") or self._generate_snippet(
                            chunk_content or "",
                            full_content.content_summary or meta.get("content_summary", "")
                        ),
                        "metadata": {
                            "file_name": full_content.file_name or meta.get("file_name"),
                            "file_size": full_content.file_size or meta.get("file_size"),
                            "upload_time": full_content.create_time.isoformat() if full_content.create_time else meta.get("created_at"),
                            "collection_id": collection_name,
                            "content_summary": full_content.content_summary or meta.get("content_summary"),
                            "content_tags": full_content.content_tags or meta.get("content_tags"),
                            "chunk_index": meta.get("chunk_index"),
                            "start_offset": meta.get("start_offset"),
                            "end_offset": meta.get("end_offset"),
                            "is_chunk": start_offset is not None and end_offset is not None  # 标记是否为分块
                        }
                    }
                    results.append(result)

                if verbose_debug:
                    logger.info(f"🔍 [DEBUG] 过滤统计 - 集合: {collection_name}")
                    logger.info(f"🔍 [DEBUG]   向量库返回: {len(vector_ids)} 个")
                    logger.info(f"🔍 [DEBUG]   相似度过滤: {filtered_by_threshold} 个")
                    logger.info(f"🔍 [DEBUG]   数据库未找到: {filtered_by_db_missing} 个")
                    logger.info(f"🔍 [DEBUG]   内容为空: {filtered_by_empty_content} 个")
                    logger.info(f"🔍 [DEBUG]   最终返回: {len(results)} 个")

                # 可选轻量重排序（基于关键词匹配作轻微加权）
                if os.getenv("RERANK_ENABLED", "false").lower() == "true":
                    q_terms = set((query or "").lower().split())
                    for r in results:
                        text = " ".join([
                            str(r.get("title", "")),
                            str(r.get("description", "")),
                            str(r.get("snippet", ""))
                        ]).lower()
                        doc_terms = set(text.split())
                        overlap = len(q_terms & doc_terms) / max(1, len(q_terms))
                        r["_rerank_score"] = r.get("similarity_score", 0) + 0.05 * overlap
                    results.sort(key=lambda x: x.get("_rerank_score", x.get("similarity_score", 0)), reverse=True)
                return results

            finally:
                db.close()

        except Exception as e:
            logger.error(f"搜索集合 {collection_name} 失败: {e}")
            return []

    def _generate_snippet(self, content: str, summary: str) -> str:
        """生成搜索结果片段"""
        # 优先使用摘要
        if summary and summary.strip():
            return summary[:200] + "..." if len(summary) > 200 else summary
        # 其次使用内容
        elif content and content.strip():
            # 清理换行符和多余空格
            clean_content = " ".join(content.strip().split())
            return clean_content[:200] + "..." if len(clean_content) > 200 else clean_content
        else:
            return "暂无内容预览"

    async def _fallback_keyword_search(self, query: str, collection_id: Optional[Union[str, List[str]]] = None,
                                     top_k: int = 5) -> List[Dict[str, Any]]:
        """降级关键词搜索

        Args:
            query: 搜索查询
            collection_id: 集合ID（单个字符串）或集合ID列表（支持多集合搜索）
            top_k: 返回结果数量
        """
        try:
            # 使用数据库会话
            db_gen = get_db()
            db = next(db_gen)

            try:
                # 构建基础查询
                base_query = db.query(RAGContent).filter(RAGContent.status == "1")

                # 按集合筛选（支持多集合）
                if collection_id:
                    # 兼容处理：将单个collection_id转换为列表
                    if isinstance(collection_id, str):
                        collection_id = [collection_id]
                    # 兼容横线/下划线以及映射后的集合名
                    normalized_ids = set()
                    for cid in collection_id:
                        normalized_ids.add(cid)
                        normalized_ids.add(cid.replace("_", "-"))
                        normalized_ids.add(cid.replace("-", "_"))
                        normalized_ids.add(collection_mapper.to_milvus_name(cid))
                    base_query = base_query.filter(RAGContent.vector_collection.in_(list(normalized_ids)))

                # 关键词匹配
                if query:
                    base_query = base_query.filter(
                        (RAGContent.title.like(f"%{query}%")) |
                        (RAGContent.description.like(f"%{query}%")) |
                        (RAGContent.content_text.like(f"%{query}%")) |
                        (RAGContent.content_summary.like(f"%{query}%"))
                    )

                # 限制结果数量
                documents = base_query.limit(top_k).all()

                # 构建搜索结果
                results = []
                for doc in documents:
                    # 跳过完全为空的文档
                    if not doc.content_text and not doc.description and not doc.title:
                        logger.warning(f"文档 {doc.id} 内容完全为空，跳过")
                        continue

                    # 计算真实的关键词匹配分数
                    similarity_score = self._calculate_keyword_similarity(query, doc)

                    # ✅ 关键词搜索返回摘要或前1000字符，而不是完整文档
                    # 这与语义搜索保持一致，避免返回超大内容
                    if doc.content_summary:
                        content = doc.content_summary
                        logger.info(f"🔍 [KEYWORD] 使用摘要: doc_id={doc.id}, length={len(content)}")
                    elif doc.content_text:
                        content = doc.content_text[:1000] + ("..." if len(doc.content_text) > 1000 else "")
                        logger.info(f"🔍 [KEYWORD] 截取前1000字符: doc_id={doc.id}, total_length={len(doc.content_text)}, returned={len(content)}")
                    else:
                        content = doc.description or ""
                        logger.info(f"🔍 [KEYWORD] 使用描述: doc_id={doc.id}")

                    result = {
                        "id": doc.id,
                        "title": doc.title or "未命名文档",
                        "description": doc.description or "",
                        "content": content,  # ✅ 返回摘要或截取内容，而不是完整文档
                        "content_type": doc.content_type,
                        "similarity_score": similarity_score,  # 真实计算的相似度
                        "snippet": self._generate_snippet(content, doc.content_summary or ""),
                        "search_type": "keyword",  # 添加搜索类型
                        "metadata": {
                            "file_name": doc.file_name,
                            "file_size": doc.file_size,
                            "upload_time": doc.create_time.isoformat() if doc.create_time else None,
                            "collection_id": doc.vector_collection,
                            "content_summary": doc.content_summary,
                            "content_tags": doc.content_tags,
                            "is_chunk": False,  # 关键词搜索返回的是文档级摘要，不是分块
                            "is_summary": bool(doc.content_summary)  # 标记是否使用了摘要
                        }
                    }
                    results.append(result)

                # 按相似度排序
                results.sort(key=lambda x: x["similarity_score"], reverse=True)
                return results

            finally:
                db.close()

        except Exception as e:
            logger.error(f"关键词搜索失败: {e}")
            return []

    async def cleanup_orphaned_vectors(self, collection_name: str = None) -> Dict[str, Any]:
        """清理孤儿向量（向量数据库中存在但关系数据库中不存在的记录）"""
        if not self.vector_db:
            return {"error": "向量数据库不可用"}

        db_gen = get_db()
        db = next(db_gen)

        try:
            collections = [collection_name] if collection_name else self.vector_db.list_collections()
            cleanup_stats = {"total_checked": 0, "orphaned_found": 0, "cleaned": 0}

            for coll_name in collections:
                if not self.vector_db.collection_exists(coll_name):
                    continue

                logger.info(f"清理集合 {coll_name} 中的孤儿向量...")

                # 这里需要实现获取所有向量ID的方法
                # 由于FAISS的限制，我们暂时跳过自动清理
                logger.warning(f"集合 {coll_name} 的自动清理需要FAISS增强支持")

            return cleanup_stats

        except Exception as e:
            logger.error(f"清理孤儿向量失败: {e}")
            return {"error": str(e)}
        finally:
            db.close()

    async def hybrid_search(self, query: str, collection_id: Optional[Union[str, List[str]]] = None,
                          top_k: int = 10) -> List[Dict[str, Any]]:
        """混合搜索：结合语义搜索和关键词搜索

        Args:
            query: 搜索查询
            collection_id: 集合ID（单个字符串）或集合ID列表（支持多集合搜索）
            top_k: 返回结果数量
        """
        try:
            # 兼容处理：将单个collection_id转换为列表
            if collection_id is not None and isinstance(collection_id, str):
                collection_id = [collection_id]

            # 执行语义搜索
            semantic_results = await self.semantic_search(query, collection_id, top_k//2 + 2)

            # 执行关键词搜索
            keyword_results = await self._fallback_keyword_search(query, collection_id, top_k//2 + 2)

            # 合并结果并去重
            seen_ids = set()
            combined_results = []

            # 优先添加语义搜索结果
            for result in semantic_results:
                if result["id"] not in seen_ids:
                    result["search_type"] = "semantic"
                    combined_results.append(result)
                    seen_ids.add(result["id"])

            # 添加关键词搜索结果
            for result in keyword_results:
                if result["id"] not in seen_ids:
                    result["search_type"] = "keyword"
                    combined_results.append(result)
                    seen_ids.add(result["id"])

            # 按相似度排序并限制数量
            combined_results.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
            return combined_results[:top_k]

        except Exception as e:
            logger.error(f"混合搜索失败: {e}")
            # 降级到关键词搜索
            return await self._fallback_keyword_search(query, collection_id, top_k)


    def get_vector_db_stats(self) -> Dict[str, Any]:
        """获取向量数据库统计信息"""
        try:
            if not self.vector_db:
                return {"error": "向量数据库不可用"}

            collections = self.vector_db.list_collections()
            stats = {
                "total_collections": len(collections),
                "collections": {}
            }

            for collection_name in collections:
                info = self.vector_db.get_collection_info(collection_name)
                stats["collections"][collection_name] = info

            return stats

        except Exception as e:
            logger.error(f"获取向量数据库统计信息失败: {e}")
            return {"error": str(e)}

    # ==================== 知识图谱功能（从unified_rag_service_v2迁移） ====================

    async def get_knowledge_graph(self, user_id: str, node_label: str = None,
                                max_depth: int = 3, max_nodes: int = 100) -> Dict[str, Any]:
        """获取知识图谱"""
        try:
            if not self.kg_manager:
                return {"error": "知识图谱管理器不可用"}

            if node_label:
                kg = await self.kg_manager.get_knowledge_graph(node_label, max_depth, max_nodes)
                return kg.to_dict()
            else:
                stats = await self.kg_manager.get_graph_statistics()
                return {
                    "statistics": stats,
                    "message": "请指定节点标签以获取子图"
                }
        except Exception as e:
            logger.error(f"获取知识图谱失败: {e}")
            return {"error": str(e)}

    async def search_knowledge_graph(self, user_id: str, query: str,
                                   search_type: str = "mixed", limit: int = 10) -> Dict[str, Any]:
        """搜索知识图谱"""
        try:
            if not self.kg_manager:
                return {"error": "知识图谱管理器不可用"}

            results = await self.kg_manager.search_knowledge_graph(query, search_type, limit)
            return results.to_dict()
        except Exception as e:
            logger.error(f"搜索知识图谱失败: {e}")
            return {"error": str(e)}

    async def export_knowledge_graph(self, user_id: str, format: str = "json") -> Dict[str, Any]:
        """导出知识图谱"""
        try:
            if not self.kg_manager:
                return {"error": "知识图谱管理器不可用"}

            return await self.kg_manager.export_graph(format)
        except Exception as e:
            logger.error(f"导出知识图谱失败: {e}")
            return {"error": str(e)}

    async def import_knowledge_graph(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """导入知识图谱"""
        try:
            if not self.kg_manager:
                return {"error": "知识图谱管理器不可用"}

            success = await self.kg_manager.import_graph(data)
            return {
                "success": success,
                "message": "知识图谱导入成功" if success else "知识图谱导入失败"
            }
        except Exception as e:
            logger.error(f"导入知识图谱失败: {e}")
            return {"error": str(e)}

    async def clear_knowledge_graph(self, user_id: str) -> Dict[str, Any]:
        """清空知识图谱"""
        try:
            if not self.kg_manager:
                return {"error": "知识图谱管理器不可用"}

            success = await self.kg_manager.clear_graph()
            return {
                "success": success,
                "message": "知识图谱已清空" if success else "清空知识图谱失败"
            }
        except Exception as e:
            logger.error(f"清空知识图谱失败: {e}")
            return {"error": str(e)}

    # ==================== 内容处理功能（从unified_rag_service_v2迁移） ====================

    async def process_text_content(self, db: Session, user_id: str, content: str,
                                 metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """处理文本内容并添加到RAG系统"""
        try:
            # 创建内容记录
            content_id = str(uuid.uuid4())
            # 检查是否已存在（upsert逻辑）
            existing_content = db.query(RAGContent).filter(
                RAGContent.resource_id == resource_id
            ).first()

            if existing_content:
                # 更新现有记录
                for key, value in content_data.items():
                    if key != 'id':  # 不更新主键
                        setattr(existing_content, key, value)
                rag_content = existing_content
            else:
                # 创建新记录
                rag_content = RAGContent(
                id=content_id,
                user_id=user_id,
                content_type="text",
                content_text=content,
                title=metadata.get("title", "未命名文档") if metadata else "未命名文档",
                description=metadata.get("description", "") if metadata else "",
                status="1"
            )

            db.add(rag_content)
            db.commit()

            # 向量化和存储
            if self.embedding_model and self.vector_db:
                await self.add_document_to_vector_db(rag_content, db)

            # 构建知识图谱
            if self.kg_manager and self.llm_parser:
                await self.kg_manager.build_knowledge_graph_from_text(content, content_id)

            return {
                "content_id": content_id,
                "status": "success",
                "message": "文本内容处理成功"
            }

        except Exception as e:
            logger.error(f"处理文本内容失败: {e}")
            db.rollback()
            return {"error": str(e)}

    async def get_content_summary_and_tags(self, db: Session, content_id: str) -> Dict[str, Any]:
        """获取内容摘要和标签"""
        try:
            content = db.query(RAGContent).filter(RAGContent.id == content_id).first()
            if not content:
                return {"error": "内容不存在"}

            result = {
                "summary": content.content_summary or "",
                "tags": []
            }

            # 解析标签
            if content.content_tags:
                try:
                    tags = json.loads(content.content_tags) if isinstance(content.content_tags, str) else content.content_tags
                    result["tags"] = tags if isinstance(tags, list) else []
                except:
                    pass

            # 如果没有摘要，生成摘要
            if not result["summary"] and self.llm_parser:
                try:
                    summary_prompt = f"请为以下内容生成简短摘要（不超过200字）：\n\n{content.content_text[:1000]}"
                    result["summary"] = await self.llm_parser.parse_text(summary_prompt)
                except:
                    result["summary"] = content.content_text[:200] + "..." if len(content.content_text) > 200 else content.content_text

            # 获取知识图谱信息
            kg_info = None
            if self.kg_manager:
                try:
                    kg_info = await self.kg_manager.get_knowledge_graph(content_id, max_depth=2, max_nodes=20)
                except:
                    pass

            return {
                "content_id": content_id,
                "summary": result["summary"],
                "tags": result["tags"],
                "knowledge_graph": kg_info,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"获取内容摘要失败: {e}")
            return {"error": str(e)}

    # ==================== 统计功能（从unified_rag_service_v2迁移） ====================

    def _record_query(self, db: Session, user_id: str, query: str, search_type: str, results: Dict):
        """记录查询"""
        try:
            rag_query = RAGQuery(
                id=str(uuid.uuid4()),
                user_id=user_id,
                query=query,
                search_type=search_type,
                results_count=len(results.get("results", [])),
                created_at=datetime.now()
            )

            db.add(rag_query)
            db.commit()

        except Exception as e:
            logger.error(f"记录查询失败: {e}")

    async def get_search_statistics(self, db: Session, user_id: str) -> Dict[str, Any]:
        """获取搜索统计信息"""
        try:
            # 获取查询统计
            total_queries = db.query(RAGQuery).filter(RAGQuery.user_id == user_id).count()

            # 获取内容统计
            total_contents = db.query(RAGContent).filter(RAGContent.user_id == user_id).count()

            # 获取向量数据库统计
            vector_stats = self.get_vector_db_stats() if self.vector_db else None

            # 获取知识图谱统计
            kg_stats = None
            if self.kg_manager:
                kg_stats = await self.kg_manager.get_graph_statistics()

            return {
                "total_queries": total_queries,
                "total_contents": total_contents,
                "vector_db_stats": vector_stats,
                "knowledge_graph_stats": kg_stats,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"获取搜索统计失败: {e}")
            return {"error": str(e)}


# 单例实例
_enhanced_rag_service = None

def get_enhanced_rag_service(user_id: str = None) -> EnhancedRAGService:
    """获取增强RAG服务的单例实例

    Args:
        user_id: 用户ID，用于知识图谱命名空间
    """
    global _enhanced_rag_service

    if _enhanced_rag_service is None:
        _enhanced_rag_service = EnhancedRAGService(user_id=user_id)

    return _enhanced_rag_service
