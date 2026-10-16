#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识图谱管理器

- postgres: 默认使用 PostgreSQL 表存储（kg_nodes/kg_edges）
- neo4j: 可选兼容后端
"""

import logging
import asyncio
import os
import socket
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
import json
import uuid
from urllib.parse import urlparse

from app.core.kg.base import (
    BaseGraphStorage, KnowledgeGraph, KnowledgeGraphNode, KnowledgeGraphEdge,
    GraphQueryResult, GraphNodeType, GraphEdgeType
)
from app.config import settings
from app.shared.helpers.extract_json import extract_json_from_content

logger = logging.getLogger(__name__)


class KnowledgeGraphManager:
    """知识图谱管理器（可切换存储后端）"""

    def __init__(self, namespace: str = "default"):
        self.namespace = namespace
        self._initialized = False

        # 检查图存储是否已配置
        if not settings.graph_db.is_configured:
            logger.warning("知识图谱未启用或配置无效，知识图谱功能将被禁用")
            self.storage = None
            self.enabled = False
        else:
            graph_type = (getattr(settings.graph_db, "GRAPH_DB_TYPE", "postgres") or "postgres").lower()
            try:
                if graph_type == "postgres":
                    from app.core.kg.postgres_impl import PostgresGraphStorage

                    self.storage = PostgresGraphStorage(
                        namespace,
                        schema=getattr(settings.graph_db, "GRAPH_PG_SCHEMA", "public") or "public",
                    )
                else:
                    from app.core.kg.neo4j_impl import Neo4JGraphStorage

                    self.storage = Neo4JGraphStorage(namespace)
                self.enabled = True
            except Exception as exc:
                logger.warning("知识图谱后端初始化失败，已禁用图谱功能: %s", exc)
                self.storage = None
                self.enabled = False

        self.llm_parser = None

        # 初始化知识图谱管理器（仅在事件循环已就绪时自动初始化；否则延迟到首次调用时初始化）
        if self.enabled:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.initialize())
            except RuntimeError:
                pass

    async def _ensure_initialized(self) -> bool:
        """确保存储后端已初始化（幂等）。"""
        if not self.is_enabled():
            return False
        if not self._initialized:
            await self.initialize()
        return self._initialized

    def _get_llm_parser(self):
        """按需初始化 LLM 解析器，避免查询场景引入不必要依赖。"""
        if self.llm_parser is not None:
            return self.llm_parser

        from app.shared.parsers import LLMEnhancedParser

        provider = (getattr(settings.llm, "LLM_PROVIDER", "") or "openai").strip().lower()
        if provider == "local":
            self.llm_parser = LLMEnhancedParser(
                model_name=(getattr(settings.llm, "LOCAL_LLM_MODEL_NAME", "") or "").strip() or getattr(settings.llm, "OPENAI_MODEL_NAME", "gpt-3.5-turbo"),
                api_key=(getattr(settings.llm, "LOCAL_LLM_API_KEY", "") or "").strip(),
                api_base=(getattr(settings.llm, "LOCAL_LLM_ENDPOINT", "") or "").strip() or None,
                auth_mode=(getattr(settings.llm, "LOCAL_LLM_AUTH_MODE", "") or "none").strip(),
                username=(getattr(settings.llm, "LOCAL_LLM_USERNAME", "") or "").strip(),
                password=(getattr(settings.llm, "LOCAL_LLM_PASSWORD", "") or "").strip(),
            )
            logger.info("知识图谱构建使用本地 OpenAI-compatible LLM")
            return self.llm_parser

        self.llm_parser = LLMEnhancedParser(
            model_name=(getattr(settings.llm, "OPENAI_MODEL_NAME", "") or "gpt-3.5-turbo").strip(),
            api_key=(getattr(settings.llm, "OPENAI_API_KEY", "") or "").strip(),
            api_base=(getattr(settings.llm, "OPENAI_API_BASE", "") or "").strip() or None,
            auth_mode=(getattr(settings.llm, "OPENAI_API_AUTH_MODE", "") or "bearer").strip(),
            username=(getattr(settings.llm, "OPENAI_API_USERNAME", "") or "").strip(),
            password=(getattr(settings.llm, "OPENAI_API_PASSWORD", "") or "").strip(),
        )
        logger.info("知识图谱构建使用 OpenAI-compatible LLM")
        return self.llm_parser

    async def initialize(self):
        """初始化知识图谱管理器"""
        if not self.enabled or not self.storage:
            logger.warning("知识图谱功能已禁用/未配置")
            return
        if self._initialized:
            return

        try:
            await self.storage.initialize()
            self._initialized = True
            logger.info(f"知识图谱管理器初始化完成: {self.namespace}")
        except Exception as e:
            logger.error(f"知识图谱管理器初始化失败: {e}")
            self.enabled = False

    async def finalize(self):
        """清理资源"""
        if self.enabled and self.storage:
            await self.storage.finalize()
            self._initialized = False
            logger.info(f"知识图谱管理器清理完成: {self.namespace}")

    def is_enabled(self) -> bool:
        """检查知识图谱功能是否启用"""
        return self.enabled and self.storage is not None

    @staticmethod
    def _normalize_labels(raw_labels: Any) -> List[str]:
        if raw_labels is None:
            return []
        if isinstance(raw_labels, list):
            return [str(item) for item in raw_labels if item is not None]
        if isinstance(raw_labels, tuple):
            return [str(item) for item in raw_labels if item is not None]
        if isinstance(raw_labels, str):
            return [raw_labels]
        return [str(raw_labels)]

    def _normalize_node_record(self, node: Dict[str, Any]) -> Dict[str, Any]:
        properties = dict(node.get("properties") or {})
        labels = self._normalize_labels(node.get("labels") or properties.get("labels"))
        node_id = (
            node.get("id")
            or properties.get("entity_id")
            or properties.get("id")
            or properties.get("name")
            or str(uuid.uuid4())
        )
        name = node.get("name") or properties.get("name") or str(node_id)
        description = node.get("description") or properties.get("description") or ""
        node_type = (
            node.get("node_type")
            or properties.get("node_type")
            or (labels[0] if labels else GraphNodeType.ENTITY.value)
        )
        source_doc = node.get("source_doc") or properties.get("source_doc")

        return {
            "id": str(node_id),
            "name": name,
            "description": description,
            "labels": labels,
            "node_type": node_type,
            "properties": properties,
            "created_at": node.get("created_at") or properties.get("created_at"),
            "updated_at": node.get("updated_at") or properties.get("updated_at"),
            "source_doc": source_doc,
        }

    def _normalize_edge_record(self, edge: Dict[str, Any]) -> Dict[str, Any]:
        properties = dict(edge.get("properties") or {})
        source = edge.get("source") or properties.get("source")
        target = edge.get("target") or properties.get("target")
        edge_type = edge.get("type") or properties.get("type") or "relates_to"
        description = edge.get("description") or properties.get("description") or ""

        return {
            "source": str(source) if source is not None else "",
            "target": str(target) if target is not None else "",
            "type": str(edge_type),
            "description": description,
            "properties": properties,
            "created_at": edge.get("created_at") or properties.get("created_at"),
            "updated_at": edge.get("updated_at") or properties.get("updated_at"),
            "source_doc": edge.get("source_doc") or properties.get("source_doc"),
        }

    async def extract_entities_and_relations(self, text: str) -> Dict[str, Any]:
        """从文本中提取实体和关系：分块LLM优先，失败后走本地关键词兜底。"""
        if not self.is_enabled():
            logger.warning("知识图谱功能未启用，跳过实体关系提取")
            return {"entities": [], "relations": []}

        text = (text or "").strip()
        if not text:
            return {"entities": [], "relations": []}

        try:
            chunks = self._split_text_for_kg(text)
            llm_parser = self._get_llm_parser()
            if not self._is_llm_endpoint_reachable(llm_parser):
                logger.warning("知识图谱LLM服务端口不可达，直接使用关键词兜底")
                fallback = self._simple_extraction(text)
                fallback["method"] = "keyword_quality_fallback"
                return fallback

            chunk_results: List[Dict[str, Any]] = []
            max_consecutive_failures = self._kg_int_setting("KG_LLM_MAX_CONSECUTIVE_FAILURES", 1, 1, 10)
            consecutive_failures = 0

            for index, chunk in enumerate(chunks, start=1):
                chunk_result = await self._extract_kg_chunk_with_llm(
                    llm_parser,
                    chunk,
                    chunk_index=index,
                    total_chunks=len(chunks),
                )
                if chunk_result and chunk_result.get("entities"):
                    chunk_results.append(chunk_result)
                    consecutive_failures = 0
                    continue

                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    logger.warning(
                        "知识图谱分块LLM连续失败，提前降级到关键词兜底 failures=%s chunks_done=%s/%s",
                        consecutive_failures,
                        index,
                        len(chunks),
                    )
                    break

            if chunk_results:
                merged_result = self._merge_chunk_extraction_results(chunk_results)
                min_entities = self._kg_int_setting("KG_LLM_MIN_VALID_ENTITIES", 2, 1, 20)
                if len(merged_result.get("entities", [])) >= min_entities:
                    logger.info(
                        "分块LLM知识图谱抽取完成 chunks=%s/%s entities=%s relations=%s",
                        len(chunk_results),
                        len(chunks),
                        len(merged_result.get("entities", [])),
                        len(merged_result.get("relations", [])),
                    )
                    return merged_result

                logger.warning(
                    "分块LLM抽取有效实体不足 entities=%s min=%s，改用关键词兜底",
                    len(merged_result.get("entities", [])),
                    min_entities,
                )

            logger.warning("分块LLM抽取无有效结果，使用关键词兜底")
            fallback = self._simple_extraction(text)
            fallback["method"] = "keyword_quality_fallback"
            return fallback

        except Exception as e:
            logger.error(f"提取实体关系失败: {e}")
            fallback = self._simple_extraction(text)
            fallback["method"] = "keyword_quality_fallback"
            return fallback

    def _is_llm_endpoint_reachable(self, llm_parser: Any) -> bool:
        """快速检查LLM端口是否可连，避免模型服务离线时每个分块都等待长超时。"""
        enabled = str(os.getenv("KG_LLM_PREFLIGHT_ENABLED", "1")).strip().lower()
        if enabled in {"0", "false", "no", "off"}:
            return True

        endpoint = (
            getattr(llm_parser, "api_base", None)
            or getattr(llm_parser, "_openai_chat_endpoint", None)
            or ""
        )
        parsed = urlparse(str(endpoint))
        if not parsed.hostname:
            return True

        port = parsed.port
        if port is None:
            port = 443 if parsed.scheme == "https" else 80

        timeout = self._kg_float_setting("KG_LLM_PREFLIGHT_TIMEOUT", 5.0, 0.5, 30.0)
        try:
            with socket.create_connection((parsed.hostname, port), timeout=timeout):
                return True
        except OSError as exc:
            logger.warning(
                "知识图谱LLM端口预检查失败 endpoint=%s host=%s port=%s error=%s",
                endpoint,
                parsed.hostname,
                port,
                exc,
            )
            return False

    @staticmethod
    def _kg_int_setting(name: str, default: int, min_value: int, max_value: int) -> int:
        try:
            value = int(os.getenv(name, str(default)))
        except (TypeError, ValueError):
            value = default
        return max(min_value, min(max_value, value))

    @staticmethod
    def _kg_float_setting(name: str, default: float, min_value: float, max_value: float) -> float:
        try:
            value = float(os.getenv(name, str(default)))
        except (TypeError, ValueError):
            value = default
        return max(min_value, min(max_value, value))

    @staticmethod
    def _confidence_value(value: Any, default: float = 0.72) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = default
        return max(0.0, min(1.0, confidence))

    def _split_text_for_kg(self, text: str) -> List[str]:
        """按字符窗口切分文本，并对超长文档做均匀采样，避免一次LLM调用处理整篇文档。"""
        import re

        chunk_size = self._kg_int_setting("KG_LLM_CHUNK_SIZE", 2600, 800, 6000)
        overlap = self._kg_int_setting("KG_LLM_CHUNK_OVERLAP", 180, 0, 1000)
        max_chunks = self._kg_int_setting("KG_LLM_MAX_CHUNKS", 12, 1, 80)

        normalized = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
        if not normalized:
            return []
        if len(normalized) <= chunk_size:
            return [normalized]

        chunks: List[str] = []
        start = 0
        total_length = len(normalized)
        min_split = max(200, int(chunk_size * 0.55))

        while start < total_length:
            target_end = min(total_length, start + chunk_size)
            end = target_end
            if target_end < total_length:
                split_candidates = [
                    normalized.rfind("\n\n", start + min_split, target_end),
                    normalized.rfind("。", start + min_split, target_end),
                    normalized.rfind("；", start + min_split, target_end),
                    normalized.rfind(";", start + min_split, target_end),
                ]
                split_at = max(split_candidates)
                if split_at > start:
                    end = split_at + 1

            chunk = normalized[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= total_length:
                break

            next_start = end - overlap if overlap > 0 else end
            if next_start <= start:
                next_start = end
            start = next_start

        if len(chunks) <= max_chunks:
            return chunks

        if max_chunks == 1:
            return [chunks[0]]

        indexes = sorted(
            {
                round(i * (len(chunks) - 1) / (max_chunks - 1))
                for i in range(max_chunks)
            }
        )
        sampled = [chunks[index] for index in indexes]
        logger.info("知识图谱分块采样: total_chunks=%s sampled=%s", len(chunks), len(sampled))
        return sampled

    async def _extract_kg_chunk_with_llm(
        self,
        llm_parser: Any,
        chunk_text: str,
        *,
        chunk_index: int,
        total_chunks: int,
    ) -> Optional[Dict[str, Any]]:
        entity_limit = self._kg_int_setting("KG_LLM_ENTITIES_PER_CHUNK", 8, 2, 20)
        relation_limit = self._kg_int_setting("KG_LLM_RELATIONS_PER_CHUNK", 8, 0, 20)
        max_tokens = self._kg_int_setting("KG_LLM_MAX_TOKENS", 1600, 600, 4096)

        prompt = f"""
任务: 从文档分块抽取知识图谱。只输出完整合法JSON，不要Markdown，不要解释。
分块: {chunk_index}/{total_chunks}
限制:
- entities最多{entity_limit}个，relations最多{relation_limit}条。
- 实体必须是稳定名词/术语/对象/场景/指标，不要抽取句子片段、页码、乱码、报错信息。
- description不超过18个汉字。
- evidence必须是原文片段且不超过30个汉字。
- confidence必须是0到1之间的小数。
- 关系source和target必须等于实体name，关系必须有原文证据。
- 优先使用具体关系，禁止使用“相关/关联/relates_to”。
实体类型只能用: 场景,对象,人员,组织,系统,技术,指标,行为,风险,文本,概念。
关系类型只能用: 包含,位于,执行,使用,支持,产生,显示,连接,依赖,属于,影响,存在风险,证明。
返回格式:
{{"entities":[{{"name":"实体","type":"类型","description":"描述","properties":{{"evidence":"证据"}},"confidence":0.9}}],"relations":[{{"source":"源实体","target":"目标实体","type":"关系","description":"描述","properties":{{"evidence":"证据"}},"confidence":0.9}}]}}
文本片段:
{chunk_text}
"""

        try:
            llm_result = await asyncio.to_thread(
                llm_parser.call_llm_api,
                prompt,
                max_tokens,
                0.0,
                {"type": "json_object"},
                "你是知识图谱JSON抽取器。必须只返回可被json.loads解析的JSON对象。",
            )
        except Exception as exc:
            logger.warning("知识图谱分块LLM调用异常 chunk=%s/%s error=%s", chunk_index, total_chunks, exc)
            return None

        if not llm_result.get("success") or not llm_result.get("content"):
            logger.warning(
                "知识图谱分块LLM调用失败 chunk=%s/%s error=%s",
                chunk_index,
                total_chunks,
                llm_result.get("error", "未知错误"),
            )
            return None

        result = self._parse_llm_graph_json(llm_result.get("content"))
        if not result:
            logger.warning(
                "知识图谱分块LLM返回非JSON chunk=%s/%s preview=%s",
                chunk_index,
                total_chunks,
                str(llm_result.get("content", ""))[:300],
            )
            return None

        result = self._validate_and_enhance_result(result)
        for entity in result.get("entities", []):
            properties = dict(entity.get("properties") or {})
            properties["source"] = "chunked_llm"
            properties["chunk_index"] = chunk_index
            properties.setdefault("chunk_total", total_chunks)
            entity["properties"] = properties
        for relation in result.get("relations", []):
            properties = dict(relation.get("properties") or {})
            properties["source"] = "chunked_llm"
            properties["chunk_index"] = chunk_index
            properties.setdefault("chunk_total", total_chunks)
            relation["properties"] = properties

        return result

    def _parse_llm_graph_json(self, content: Any) -> Optional[Dict[str, Any]]:
        if not content:
            return None
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            result = extract_json_from_content(str(content))

        if not isinstance(result, dict):
            return None

        for key in ("result", "data", "knowledge_graph", "graph"):
            nested = result.get(key)
            if isinstance(nested, dict) and ("entities" in nested or "relations" in nested):
                result = nested
                break

        entities = result.get("entities") or result.get("nodes") or []
        relations = result.get("relations") or result.get("edges") or []
        if not isinstance(entities, list):
            entities = []
        if not isinstance(relations, list):
            relations = []
        return {"entities": entities, "relations": relations}

    def _merge_chunk_extraction_results(self, chunk_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        min_entity_conf = self._kg_float_setting("KG_LLM_MIN_ENTITY_CONFIDENCE", 0.58, 0.0, 1.0)
        min_relation_conf = self._kg_float_setting("KG_LLM_MIN_RELATION_CONFIDENCE", 0.60, 0.0, 1.0)
        max_entities = self._kg_int_setting("KG_LLM_MAX_ENTITIES", 40, 1, 200)
        max_relations = self._kg_int_setting("KG_LLM_MAX_RELATIONS", 80, 0, 300)

        entity_map: Dict[str, Dict[str, Any]] = {}
        alias_map: Dict[str, str] = {}

        for chunk_result in chunk_results:
            for entity in chunk_result.get("entities", []) or []:
                if not isinstance(entity, dict):
                    continue
                original_name = str(entity.get("name") or "").strip()
                entity_name = self._clean_entity_name(original_name)
                if not entity_name:
                    continue

                confidence = self._confidence_value(entity.get("confidence"), 0.72)
                if confidence < min_entity_conf:
                    continue

                key = entity_name.lower()
                properties = dict(entity.get("properties") or {})
                evidence = str(properties.get("evidence") or "").strip()
                chunk_index = properties.get("chunk_index")

                current = entity_map.get(key)
                if current is None:
                    current = {
                        "name": entity_name,
                        "type": entity.get("type") or self._guess_entity_type(entity_name),
                        "description": entity.get("description") or f"从文本中提取的{self._guess_entity_type(entity_name)}: {entity_name}",
                        "properties": {
                            "source": "chunked_llm",
                            "evidence": evidence,
                            "evidence_list": [evidence] if evidence else [],
                            "chunk_indexes": [chunk_index] if chunk_index is not None else [],
                        },
                        "confidence": confidence,
                        "_score": confidence,
                        "_mentions": 1,
                    }
                    entity_map[key] = current
                else:
                    current["_mentions"] += 1
                    current["_score"] += confidence
                    current["confidence"] = max(current.get("confidence", 0.0), confidence)
                    if len(entity_name) > len(current["name"]):
                        current["name"] = entity_name
                    if evidence and evidence not in current["properties"].get("evidence_list", []):
                        current["properties"].setdefault("evidence_list", []).append(evidence)
                        if not current["properties"].get("evidence"):
                            current["properties"]["evidence"] = evidence
                    if chunk_index is not None and chunk_index not in current["properties"].get("chunk_indexes", []):
                        current["properties"].setdefault("chunk_indexes", []).append(chunk_index)

                if original_name:
                    alias_map[original_name] = entity_map[key]["name"]
                alias_map[entity_name] = entity_map[key]["name"]

        ranked_entities = sorted(
            entity_map.values(),
            key=lambda item: (
                -(item.get("_score", 0.0) + item.get("_mentions", 0) * 0.15),
                -len(item.get("name", "")),
                item.get("name", ""),
            ),
        )[:max_entities]

        selected_names = {entity["name"] for entity in ranked_entities}
        output_entities: List[Dict[str, Any]] = []
        for entity in ranked_entities:
            properties = dict(entity.get("properties") or {})
            properties["chunk_indexes"] = sorted(idx for idx in properties.get("chunk_indexes", []) if idx is not None)
            evidence_list = properties.get("evidence_list") or []
            if evidence_list:
                properties["evidence"] = properties.get("evidence") or evidence_list[0]
                properties["evidence_list"] = evidence_list[:5]
            output_entities.append({
                "name": entity["name"],
                "type": entity.get("type") or self._guess_entity_type(entity["name"]),
                "description": entity.get("description") or "",
                "properties": properties,
                "confidence": round(float(entity.get("confidence", 0.0)), 4),
            })

        relation_map: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for chunk_result in chunk_results:
            for relation in chunk_result.get("relations", []) or []:
                if not isinstance(relation, dict):
                    continue

                raw_source = relation.get("source")
                raw_target = relation.get("target")
                source_name = alias_map.get(str(raw_source or "").strip()) or self._clean_entity_name(raw_source)
                target_name = alias_map.get(str(raw_target or "").strip()) or self._clean_entity_name(raw_target)
                relation_type = str(relation.get("type") or "").strip()
                if not source_name or not target_name or not relation_type or source_name == target_name:
                    continue
                if source_name not in selected_names or target_name not in selected_names:
                    continue

                confidence = self._confidence_value(relation.get("confidence"), 0.72)
                if confidence < min_relation_conf:
                    continue

                properties = dict(relation.get("properties") or {})
                evidence = str(properties.get("evidence") or "").strip()
                relation_key = (source_name, target_name, relation_type)
                current = relation_map.get(relation_key)
                if current is None:
                    relation_map[relation_key] = {
                        "source": source_name,
                        "target": target_name,
                        "type": relation_type,
                        "description": relation.get("description") or "",
                        "properties": {
                            "source": "chunked_llm",
                            "evidence": evidence,
                            "evidence_list": [evidence] if evidence else [],
                            "chunk_indexes": [properties.get("chunk_index")] if properties.get("chunk_index") is not None else [],
                        },
                        "confidence": confidence,
                        "_score": confidence,
                        "_mentions": 1,
                    }
                else:
                    current["_mentions"] += 1
                    current["_score"] += confidence
                    current["confidence"] = max(current.get("confidence", 0.0), confidence)
                    if evidence and evidence not in current["properties"].get("evidence_list", []):
                        current["properties"].setdefault("evidence_list", []).append(evidence)
                        if not current["properties"].get("evidence"):
                            current["properties"]["evidence"] = evidence
                    chunk_index = properties.get("chunk_index")
                    if chunk_index is not None and chunk_index not in current["properties"].get("chunk_indexes", []):
                        current["properties"].setdefault("chunk_indexes", []).append(chunk_index)

        output_relations: List[Dict[str, Any]] = []
        for relation in sorted(
            relation_map.values(),
            key=lambda item: (-(item.get("_score", 0.0) + item.get("_mentions", 0) * 0.1), item.get("type", "")),
        )[:max_relations]:
            properties = dict(relation.get("properties") or {})
            properties["chunk_indexes"] = sorted(idx for idx in properties.get("chunk_indexes", []) if idx is not None)
            evidence_list = properties.get("evidence_list") or []
            if evidence_list:
                properties["evidence"] = properties.get("evidence") or evidence_list[0]
                properties["evidence_list"] = evidence_list[:5]
            output_relations.append({
                "source": relation["source"],
                "target": relation["target"],
                "type": relation["type"],
                "description": relation.get("description") or "",
                "properties": properties,
                "confidence": round(float(relation.get("confidence", 0.0)), 4),
            })

        output_relations = self._filter_relation_quality(output_relations)
        return {
            "entities": output_entities,
            "relations": output_relations,
            "method": "chunked_llm",
            "chunks_total": len(chunk_results),
        }

    def _simple_extraction(self, text: str) -> Dict[str, Any]:
        """本地关键词兜底抽取，避免把连续中文硬截成句子碎片。"""
        import re

        entities: List[Dict[str, Any]] = []
        if not text:
            return {"entities": entities, "relations": []}

        normalized_text = re.sub(r"\s+", " ", text)
        score_map: Dict[str, float] = {}
        evidence_map: Dict[str, str] = {}

        domain_terms = [
            "城市桥梁检测与评定技术规范",
            "城市桥梁检测与评定",
            "城市桥梁",
            "桥梁检测",
            "桥梁评定",
            "桥梁结构",
            "桥梁荷载试验",
            "荷载试验",
            "静载试验",
            "动载试验",
            "技术状况评定",
            "技术状况",
            "承载能力",
            "承载能力评定",
            "结构变位",
            "结构状态",
            "结构检算",
            "校验系数",
            "容许应力法",
            "极限状态法",
            "抗裂性",
            "挠度",
            "应变",
            "裂缝",
            "索力",
            "频率",
            "振型",
            "阻尼",
            "桥面系",
            "上部结构",
            "下部结构",
            "检测报告",
            "评定报告",
            "技术规范",
            "行业标准",
            "检测项目",
            "评定指标",
        ]

        priority_terms = {
            "桥梁荷载试验",
            "荷载试验",
            "静载试验",
            "动载试验",
            "结构变位",
            "承载能力评定",
            "技术状况评定",
            "校验系数",
            "容许应力法",
            "极限状态法",
            "裂缝",
            "挠度",
            "应变",
            "索力",
        }
        generic_terms = {"技术规范", "技术状况", "承载能力", "城市桥梁", "上部结构", "下部结构"}

        for term in domain_terms:
            if term in normalized_text:
                base_score = 16.0 if term in priority_terms else 8.5 if term in generic_terms else 12.0
                self._add_entity_candidate(score_map, evidence_map, term, base_score, normalized_text)

        try:
            import jieba
            import jieba.analyse

            for term in domain_terms:
                jieba.add_word(term, freq=200000)

            for keyword, weight in jieba.analyse.extract_tags(
                normalized_text,
                topK=50,
                withWeight=True,
                allowPOS=("n", "nz", "vn", "v", "eng"),
            ):
                self._add_entity_candidate(score_map, evidence_map, keyword, float(weight) * 4, normalized_text)
        except Exception as exc:
            logger.debug("jieba关键词兜底抽取失败，继续使用规则抽取: %s", exc)

        suffixes = (
            "技术规范|检测与评定|荷载试验|状态评定|状况评定|承载能力评定|"
            "承载能力|校验系数|容许应力法|极限状态法|结构变位|静载试验|"
            "动载试验|桥梁检测|桥梁结构|技术状况|检测报告|评定报告|"
            "行业标准|技术标准|评定指标|检测项目|检测方法|评定方法|"
            "规范|标准|规程|方法|系统|平台|模型|算法|指标|风险|设备|车辆|隧道|桥梁"
        )
        for match in re.finditer(r"[\u4e00-\u9fa5A-Za-z0-9/·（）()《》-]{2,24}(?:" + suffixes + r")", normalized_text):
            self._add_entity_candidate(score_map, evidence_map, match.group(0), 7.0, normalized_text)

        for match in re.finditer(r"\b[A-Z][A-Z0-9./-]{3,}\b", normalized_text):
            self._add_entity_candidate(score_map, evidence_map, match.group(0), 3.0, normalized_text)

        for name in list(score_map):
            score_map[name] += min(normalized_text.count(name), 5) * 0.8
            score_map[name] += min(len(name), 12) * 0.08

        ranked_names = sorted(score_map, key=lambda item: (-score_map[item], -len(item), item))[:14]
        for entity_name in ranked_names:
            entity_type = self._guess_entity_type(entity_name)
            evidence = evidence_map.get(entity_name) or entity_name
            entities.append({
                "name": entity_name,
                "type": entity_type,
                "description": f"从文本中提取的{entity_type}: {entity_name}",
                "properties": {"source": "simple_extraction", "evidence": evidence},
                "confidence": 0.72,
            })

        return {"entities": entities, "relations": []}

    def _add_entity_candidate(
        self,
        score_map: Dict[str, float],
        evidence_map: Dict[str, str],
        candidate: Any,
        score: float,
        text: str,
    ) -> None:
        entity_name = self._clean_entity_name(candidate)
        if not entity_name:
            return

        score_map[entity_name] = max(score_map.get(entity_name, 0.0), score)
        evidence_map.setdefault(entity_name, self._entity_context(text, entity_name))

    def _entity_context(self, text: str, entity_name: str, window: int = 18) -> str:
        index = text.find(entity_name)
        if index < 0:
            return entity_name
        start = max(0, index - window)
        end = min(len(text), index + len(entity_name) + window)
        return text[start:end].strip()

    def _clean_entity_name(self, name: Any) -> Optional[str]:
        """清洗并过滤低质量实体名。"""
        import re

        if name is None:
            return None

        cleaned = str(name).strip()
        if not cleaned:
            return None

        cleaned = re.sub(r"[#*_`]+", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.strip(" \t\r\n。；;，,、:：()（）[]【】{}<>《》'\\\"“”‘’|\\/")

        cleaned = re.sub(
            r"^(?:第[一二三四五六七八九十0-9]+[章节条款页]?|是|为|将|可|应|按|以|于|在|由|对|和|与|及|或|但|若|当|只有|依据|根据|采用|进行|该|其|本|结果)+",
            "",
            cleaned,
        )
        cleaned = re.sub(r"(?:的|和|及|与|或|等|时|后|前|中|内|下|上|者|进行|采用|符合|可|应|为|按)$", "", cleaned)
        cleaned = cleaned.strip(" \t\r\n。；;，,、:：()（）[]【】{}<>《》'\\\"“”‘’|\\/")

        if not cleaned:
            return None

        bad_markers = {
            "分析失败",
            "解析失败",
            "请求错误",
            "未知错误",
            "mineru错误",
            "ocr错误",
            "pdfplumber错误",
        }
        lower_name = cleaned.lower()
        if any(marker in lower_name for marker in bad_markers):
            return None

        if re.fullmatch(r"[A-Za-z]{1,3}", cleaned):
            return None

        if re.fullmatch(r"\d+(?:\.\d+)?", cleaned):
            return None

        if re.fullmatch(r"[0-9[:punct:] A-Za-z_./-]+", cleaned):
            if not re.search(r"[A-Z]{2,}|[0-9].*[A-Za-z]|[A-Za-z].*[0-9]", cleaned):
                return None

        chinese_chars = re.findall(r"[\u4e00-\u9fa5]", cleaned)
        if chinese_chars:
            if len(chinese_chars) < 2:
                return None
            if len(cleaned) > 18:
                return None

            fragment_markers = (
                "应符合",
                "客观条件",
                "实际检测的结果",
                "获知按",
                "样做",
                "这样做",
                "现行行",
                "进行检测",
                "进行评定",
            )
            if any(marker in cleaned for marker in fragment_markers):
                return None

            quality_terms = (
                "规范",
                "标准",
                "规程",
                "方法",
                "技术",
                "系统",
                "平台",
                "模型",
                "算法",
                "指标",
                "风险",
                "设备",
                "车辆",
                "隧道",
                "桥梁",
                "检测",
                "评定",
                "试验",
                "结构",
                "状态",
                "承载",
                "荷载",
                "系数",
                "应力",
                "裂缝",
                "挠度",
                "应变",
                "索力",
                "频率",
                "振型",
                "阻尼",
                "人员",
                "对象",
                "场景",
            )
            if len(chinese_chars) >= 7 and not any(term in cleaned for term in quality_terms):
                return None

        return cleaned

    def _guess_entity_type(self, entity_name: str) -> str:
        """猜测实体类型"""
        if any(kw in entity_name for kw in ['公司', '集团', '组织', '部门']):
            return '组织'
        elif any(kw in entity_name for kw in ['系统', '平台', '软件', '工具']):
            return '产品'
        elif any(kw in entity_name for kw in ['技术', '协议', '算法', '方法']):
            return '技术'
        elif entity_name.isupper() and len(entity_name) <= 5:
            return '技术'  # 缩写通常是技术术语
        else:
            return '概念'

    def _validate_and_enhance_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """验证和增强提取结果"""
        raw_entities = result.get("entities", [])
        relations = result.get("relations", [])
        min_entity_conf = self._kg_float_setting("KG_LLM_MIN_ENTITY_CONFIDENCE", 0.58, 0.0, 1.0)

        entities = []
        entity_aliases: Dict[str, str] = {}
        seen_entities = set()
        for entity in raw_entities:
            if not isinstance(entity, dict):
                continue
            original_name = str(entity.get("name") or "").strip()
            cleaned_name = self._clean_entity_name(original_name)
            if not cleaned_name or cleaned_name in seen_entities:
                continue

            confidence = self._confidence_value(entity.get("confidence"), 0.72)
            if confidence < min_entity_conf:
                continue

            normalized_entity = dict(entity)
            normalized_entity["name"] = cleaned_name
            normalized_entity["type"] = normalized_entity.get("type") or self._guess_entity_type(cleaned_name)
            normalized_entity["confidence"] = confidence
            properties = dict(normalized_entity.get("properties") or {})
            if properties.get("evidence"):
                properties["evidence"] = str(properties["evidence"])[:80]
            normalized_entity["properties"] = properties
            entities.append(normalized_entity)
            seen_entities.add(cleaned_name)
            if original_name:
                entity_aliases[original_name] = cleaned_name

        entity_names = {entity["name"] for entity in entities}

        valid_relations = []
        for relation in relations or []:
            if not isinstance(relation, dict):
                continue
            source = entity_aliases.get(relation.get("source"), self._clean_entity_name(relation.get("source")) or relation.get("source"))
            target = entity_aliases.get(relation.get("target"), self._clean_entity_name(relation.get("target")) or relation.get("target"))
            relation["source"] = source
            relation["target"] = target
            relation["confidence"] = self._confidence_value(relation.get("confidence"), 0.72)

            properties = dict(relation.get("properties") or {})
            if properties.get("evidence"):
                properties["evidence"] = str(properties["evidence"])[:80]
            relation["properties"] = properties

            if source in entity_names and target in entity_names:
                valid_relations.append(relation)
            else:
                source_matched = self._fuzzy_match_entity(source, entity_names) if source else None
                target_matched = self._fuzzy_match_entity(target, entity_names) if target else None

                if source_matched and target_matched:
                    relation["source"] = source_matched
                    relation["target"] = target_matched
                    valid_relations.append(relation)
                    logger.info(f"修复关系: {source}->{source_matched}, {target}->{target_matched}")

        valid_relations = self._filter_relation_quality(valid_relations)

        return {
            "entities": entities,
            "relations": valid_relations,
        }

    def _filter_relation_quality(self, relations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤低质量关系，避免为了凑边生成大量泛化“相关”。"""
        filtered: List[Dict[str, Any]] = []
        generic_types = {"相关", "关联", "relates_to", "related", "RELATED"}
        min_relation_conf = self._kg_float_setting("KG_LLM_MIN_RELATION_CONFIDENCE", 0.60, 0.0, 1.0)

        for relation in relations or []:
            source = (relation.get("source") or "").strip()
            target = (relation.get("target") or "").strip()
            relation_type = str(relation.get("type") or "").strip()
            properties = relation.get("properties") or {}
            confidence_value = self._confidence_value(relation.get("confidence"), 0.72)

            if not source or not target or source == target:
                continue

            if confidence_value < min_relation_conf:
                continue

            if properties.get("inferred") is True:
                continue

            if relation_type in generic_types:
                continue

            evidence = str(properties.get("evidence") or properties.get("source_text") or "").strip()
            if len(evidence) > 120:
                properties = dict(properties)
                properties["evidence"] = evidence[:120]
                relation["properties"] = properties

            relation["confidence"] = confidence_value
            filtered.append(relation)

        return filtered

    def _fuzzy_match_entity(self, name: str, entity_names: set) -> Optional[str]:
        """模糊匹配实体名称"""
        if not name:
            return None

        # 完全匹配
        if name in entity_names:
            return name

        # 包含匹配
        for entity_name in entity_names:
            if name in entity_name or entity_name in name:
                return entity_name

        # 相似度匹配（简单实现）
        name_lower = name.lower()
        for entity_name in entity_names:
            if name_lower in entity_name.lower() or entity_name.lower() in name_lower:
                return entity_name

        return None

    def _infer_relations(self, entities: List[Dict]) -> List[Dict]:
        """基于实体类型推断可能的关系"""
        inferred = []

        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                entity1 = entities[i]
                entity2 = entities[j]

                # 基于类型推断关系
                type1, type2 = entity1.get('type', ''), entity2.get('type', '')

                if type1 == '产品' and type2 == '技术':
                    inferred.append({
                        'source': entity1['name'],
                        'target': entity2['name'],
                        'type': '使用',
                        'description': f'{entity1["name"]}可能使用{entity2["name"]}',
                        'confidence': 0.6,
                        'properties': {'inferred': True}
                    })
                elif type1 == '组织' and type2 == '产品':
                    inferred.append({
                        'source': entity1['name'],
                        'target': entity2['name'],
                        'type': '开发',
                        'description': f'{entity1["name"]}可能开发{entity2["name"]}',
                        'confidence': 0.5,
                        'properties': {'inferred': True}
                    })
                elif type1 == '概念' and type2 == '概念':
                    inferred.append({
                        'source': entity1['name'],
                        'target': entity2['name'],
                        'type': '相关',
                        'description': f'{entity1["name"]}与{entity2["name"]}相关',
                        'confidence': 0.4,
                        'properties': {'inferred': True}
                    })

        return inferred[:3]  # 最多返回3个推断的关系

    async def build_knowledge_graph(self, text: str, doc_id: str = None) -> Dict[str, Any]:
        """构建知识图谱"""
        if not await self._ensure_initialized():
            logger.warning("知识图谱功能未启用，跳过构建")
            return {"error": "知识图谱功能未启用"}

        try:
            # 提取实体和关系
            extraction_result = await self.extract_entities_and_relations(text)

            # 创建节点
            node_ids = []
            for entity in extraction_result.get("entities", []):
                node_id = await self._create_entity_node(entity, doc_id)
                if node_id:
                    node_ids.append(node_id)

            # 创建边
            edge_ids = []
            for relation in extraction_result.get("relations", []):
                edge_id = await self._create_relation_edge(relation, doc_id)
                if edge_id:
                    edge_ids.append(edge_id)

            return {
                "doc_id": doc_id,
                "node_count": len(node_ids),
                "edge_count": len(edge_ids),
                "node_ids": node_ids,
                "edge_ids": edge_ids,
                "method": extraction_result.get("method"),
                "chunks_total": extraction_result.get("chunks_total"),
            }

        except Exception as e:
            logger.error(f"构建知识图谱失败: {e}")
            return {"error": str(e)}

    async def store_extracted_graph(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
        *,
        doc_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """将已经抽取好的实体和关系写入图存储。"""
        if not await self._ensure_initialized():
            logger.warning("知识图谱功能未启用，跳过图写入")
            return {"error": "知识图谱功能未启用"}

        try:
            node_ids: List[str] = []
            edge_ids: List[str] = []

            for entity in entities or []:
                node_id = await self._create_entity_node(entity, doc_id)
                if node_id:
                    node_ids.append(node_id)

            known_entities = {self._clean_entity_name(entity.get("name")) for entity in entities or [] if entity.get("name")}
            known_entities = {name for name in known_entities if name}
            for relation in relations or []:
                source_name = self._clean_entity_name(relation.get("source"))
                target_name = self._clean_entity_name(relation.get("target"))
                if source_name not in known_entities or target_name not in known_entities:
                    continue
                relation = dict(relation)
                relation["source"] = source_name
                relation["target"] = target_name
                edge_id = await self._create_relation_edge(relation, doc_id)
                if edge_id:
                    edge_ids.append(edge_id)

            return {
                "doc_id": doc_id,
                "node_count": len(node_ids),
                "edge_count": len(edge_ids),
                "node_ids": node_ids,
                "edge_ids": edge_ids,
            }
        except Exception as e:
            logger.error(f"写入抽取图谱失败: {e}")
            return {"error": str(e)}

    async def _create_entity_node(self, entity: Dict[str, Any], doc_id: str = None) -> Optional[str]:
        """创建实体节点"""
        if not await self._ensure_initialized():
            return None

        try:
            entity_name = self._clean_entity_name(entity.get("name"))
            if not entity_name:
                return None

            node_id = entity_name
            labels = [entity.get("type", self._guess_entity_type(entity_name)), "concept"]

            properties = {
                "name": entity_name,
                "description": entity.get("description", ""),
                "node_type": GraphNodeType.ENTITY.value,
                "source_doc": doc_id,
                "created_at": datetime.now().isoformat(),
                **entity.get("properties", {})
            }
            properties["name"] = entity_name
            if entity.get("confidence") is not None:
                properties["confidence"] = self._confidence_value(entity.get("confidence"))

            success = await self.storage.upsert_node(node_id, labels, properties)
            if success:
                logger.debug(f"创建实体节点: {node_id}")
                return node_id
            return None

        except Exception as e:
            logger.error(f"创建实体节点失败: {e}")
            return None

    async def _create_relation_edge(self, relation: Dict[str, Any], doc_id: str = None) -> Optional[str]:
        """创建关系边"""
        if not await self._ensure_initialized():
            return None

        try:
            source = self._clean_entity_name(relation.get("source"))
            target = self._clean_entity_name(relation.get("target"))

            if not source or not target:
                return None

            edge_type = relation.get("type", "relates_to")

            properties = {
                "description": relation.get("description", ""),
                "edge_type": GraphEdgeType.RELATES_TO.value,
                "source_doc": doc_id,
                "created_at": datetime.now().isoformat(),
                **relation.get("properties", {})
            }
            if relation.get("confidence") is not None:
                properties["confidence"] = self._confidence_value(relation.get("confidence"))

            success = await self.storage.upsert_edge(source, target, edge_type, properties)
            if success:
                logger.debug(f"创建关系边: {source} -> {target}")
                return f"{source}_{target}"
            return None

        except Exception as e:
            logger.error(f"创建关系边失败: {e}")
            return None

    async def search_knowledge_graph(self, query: str, search_type: str = "mixed",
                                   limit: int = 10) -> GraphQueryResult:
        """搜索知识图谱"""
        if not await self._ensure_initialized():
            logger.warning("知识图谱功能未启用，返回空结果")
            return GraphQueryResult()

        try:
            result = GraphQueryResult()

            if search_type in ["nodes", "mixed"]:
                nodes = await self.storage.search_nodes(query, limit)
                result.nodes = nodes

            if search_type in ["edges", "mixed"]:
                edges = await self.storage.search_edges(query, limit)
                result.edges = edges

            return result

        except Exception as e:
            logger.error(f"搜索知识图谱失败: {e}")
            return GraphQueryResult()

    async def get_knowledge_graph(self, node_label: str, max_depth: int = 3,
                                max_nodes: int = 100) -> KnowledgeGraph:
        """获取知识图谱子图"""
        if not await self._ensure_initialized():
            logger.warning("知识图谱功能未启用，返回空图")
            return KnowledgeGraph()

        try:
            return await self.storage.get_knowledge_graph(node_label, max_depth, max_nodes)
        except Exception as e:
            logger.error(f"获取知识图谱失败: {e}")
            return KnowledgeGraph()

    async def query_nodes(
        self,
        *,
        query: Optional[str] = None,
        node_type: Optional[str] = None,
        document_id: Optional[str] = None,
        node_ids: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """按条件查询节点，并输出统一结构。"""
        if not await self._ensure_initialized():
            return []

        finder = getattr(self.storage, "query_nodes", None)
        if callable(finder):
            try:
                rows = await finder(
                    query=query,
                    node_type=node_type,
                    document_id=document_id,
                    node_ids=node_ids,
                    limit=limit,
                )
                return [self._normalize_node_record(row) for row in rows]
            except Exception as e:
                logger.error(f"查询节点失败: {e}")
                return []

        try:
            search_term = query or node_type or document_id or ""
            rows = await self.storage.search_nodes(search_term, limit)
            normalized = [self._normalize_node_record(row) for row in rows]
            if node_type:
                normalized = [
                    row for row in normalized
                    if row["node_type"] == node_type or node_type in row["labels"]
                ]
            if document_id:
                normalized = [row for row in normalized if row.get("source_doc") == document_id]
            if node_ids:
                wanted = {str(node_id) for node_id in node_ids}
                normalized = [row for row in normalized if row["id"] in wanted]
            return normalized[:limit]
        except Exception as e:
            logger.error(f"查询节点失败: {e}")
            return []

    async def query_edges(
        self,
        *,
        query: Optional[str] = None,
        document_id: Optional[str] = None,
        node_ids: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """按条件查询边，并输出统一结构。"""
        if not await self._ensure_initialized():
            return []

        finder = getattr(self.storage, "query_edges", None)
        if callable(finder):
            try:
                rows = await finder(
                    query=query,
                    document_id=document_id,
                    node_ids=node_ids,
                    limit=limit,
                )
                return [self._normalize_edge_record(row) for row in rows]
            except Exception as e:
                logger.error(f"查询边失败: {e}")
                return []

        try:
            search_term = query or document_id or ""
            rows = await self.storage.search_edges(search_term, limit)
            normalized = [self._normalize_edge_record(row) for row in rows]
            if document_id:
                normalized = [row for row in normalized if row.get("source_doc") == document_id]
            if node_ids:
                wanted = {str(node_id) for node_id in node_ids}
                normalized = [
                    row for row in normalized
                    if row["source"] in wanted or row["target"] in wanted
                ]
            return normalized[:limit]
        except Exception as e:
            logger.error(f"查询边失败: {e}")
            return []

    async def list_document_entities(
        self,
        document_id: str,
        *,
        content_name: str = "",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """查询与指定文档相关的实体节点。"""
        if not await self._ensure_initialized():
            return []

        finder = getattr(self.storage, "list_document_entities", None)
        if callable(finder):
            try:
                rows = await finder(document_id=document_id, content_name=content_name, limit=limit)
                return [self._normalize_node_record(row) for row in rows]
            except Exception as e:
                logger.error(f"查询文档实体失败: {e}")
                return []

        rows = await self.query_nodes(query=content_name or None, document_id=document_id, limit=limit)
        return rows[:limit]

    async def add_document_to_graph(self, doc_id: str, content: str,
                                  metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """将文档添加到知识图谱"""
        if not await self._ensure_initialized():
            logger.warning("知识图谱功能未启用，跳过文档添加")
            return {"error": "知识图谱功能未启用"}

        try:
            # 创建文档节点
            doc_node_id = f"doc_{doc_id}"
            doc_labels = ["document", "content"]
            doc_properties = {
                "name": f"文档 {doc_id}",
                "description": content[:200] + "..." if len(content) > 200 else content,
                "node_type": GraphNodeType.DOCUMENT.value,
                "content_length": len(content),
                "created_at": datetime.now().isoformat(),
                **(metadata or {})
            }

            await self.storage.upsert_node(doc_node_id, doc_labels, doc_properties)

            # 构建知识图谱
            graph_result = await self.build_knowledge_graph(content, doc_id)

            # 创建文档与实体的关系
            for entity_name in graph_result.get("node_ids", []):
                await self.storage.upsert_edge(
                    doc_node_id, entity_name, "contains",
                    {"description": "文档包含此实体", "created_at": datetime.now().isoformat()}
                )

            return {
                "doc_id": doc_id,
                "doc_node_id": doc_node_id,
                "graph_result": graph_result
            }

        except Exception as e:
            logger.error(f"添加文档到知识图谱失败: {e}")
            return {"error": str(e)}

    async def get_graph_statistics(self) -> Dict[str, Any]:
        """获取图统计信息"""
        if not await self._ensure_initialized():
            return {
                "enabled": False,
                "message": "知识图谱功能未启用"
            }

        try:
            getter = getattr(self.storage, "get_statistics", None)
            if callable(getter):
                stats = await getter()
            else:
                stats = {}

            total_nodes = int(stats.get("total_nodes", 0) or 0)
            total_edges = int(stats.get("total_edges", 0) or 0)
            node_types = stats.get("node_types", {}) or {}
            edge_types = stats.get("edge_types", {}) or {}

            return {
                "enabled": True,
                "total_nodes": total_nodes,
                "total_edges": total_edges,
                "node_types": node_types,
                "edge_types": edge_types,
                "total_knowledge": total_nodes,
                "total_relationships": total_edges,
                "relationship_types": edge_types,
            }
        except Exception as e:
            logger.error(f"获取图统计信息失败: {e}")
            return {}

    async def analyze_entity_associations(
        self,
        entity_name: str,
        *,
        max_depth: int = 2,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """基于统一图存储做实体关联分析。"""
        if not await self._ensure_initialized():
            return []

        seed_nodes = await self.query_nodes(query=entity_name, limit=max(limit, 10))
        if not seed_nodes:
            return []

        normalized_name = entity_name.strip().lower()
        preferred_seed_nodes = [
            node for node in seed_nodes
            if (node.get("name") or "").strip().lower() == normalized_name
        ] or seed_nodes[:1]

        visited = {node["id"] for node in preferred_seed_nodes}
        frontier_ids = list(visited)
        path_map: Dict[str, List[str]] = {node_id: [] for node_id in frontier_ids}
        distance_map: Dict[str, int] = {node_id: 0 for node_id in frontier_ids}
        node_cache = {node["id"]: node for node in preferred_seed_nodes}

        for depth in range(1, max(1, max_depth) + 1):
            if not frontier_ids or len(node_cache) >= limit + len(preferred_seed_nodes):
                break

            edges = await self.query_edges(node_ids=frontier_ids, limit=max(limit * 10, 100))
            next_ids: List[str] = []
            frontier_set = set(frontier_ids)

            for edge in edges:
                source_id = edge.get("source")
                target_id = edge.get("target")
                if source_id in frontier_set and target_id not in visited:
                    visited.add(target_id)
                    next_ids.append(target_id)
                    path_map[target_id] = path_map.get(source_id, []) + [edge.get("type", "related")]
                    distance_map[target_id] = depth
                elif target_id in frontier_set and source_id not in visited:
                    visited.add(source_id)
                    next_ids.append(source_id)
                    path_map[source_id] = path_map.get(target_id, []) + [edge.get("type", "related")]
                    distance_map[source_id] = depth

            if not next_ids:
                break

            discovered_nodes = await self.query_nodes(node_ids=next_ids, limit=len(next_ids))
            for node in discovered_nodes:
                node_cache[node["id"]] = node

            frontier_ids = [node["id"] for node in discovered_nodes]

        seed_ids = {node["id"] for node in preferred_seed_nodes}
        associations: List[Dict[str, Any]] = []
        for node_id, node in node_cache.items():
            if node_id in seed_ids:
                continue
            distance = distance_map.get(node_id, 0)
            if distance <= 0:
                continue
            associations.append(
                {
                    "id": node_id,
                    "name": node.get("name") or node_id,
                    "types": node.get("labels") or [node.get("node_type") or "entity"],
                    "distance": distance,
                    "relationship_path": path_map.get(node_id, []),
                    "relevance": 1.0 / (distance + 1),
                }
            )

        associations.sort(key=lambda item: (item["distance"], -item["relevance"], item["name"]))
        return associations[:limit]

    async def clear_graph(self) -> bool:
        """清空知识图谱"""
        if not await self._ensure_initialized():
            logger.warning("知识图谱功能未启用，跳过清空操作")
            return False

        try:
            return await self.storage.clear()
        except Exception as e:
            logger.error(f"清空知识图谱失败: {e}")
            return False

    async def export_graph(self, format: str = "json") -> Dict[str, Any]:
        """导出知识图谱"""
        if not await self._ensure_initialized():
            return {"error": "知识图谱功能未启用"}

        try:
            if format == "json":
                # 这里需要实现导出逻辑
                return {
                    "format": "json",
                    "nodes": [],
                    "edges": [],
                    "exported_at": datetime.now().isoformat(),
                    "message": "导出功能待实现"
                }
            else:
                raise ValueError(f"不支持的导出格式: {format}")

        except Exception as e:
            logger.error(f"导出知识图谱失败: {e}")
            return {"error": str(e)}

    async def import_graph(self, data: Dict[str, Any]) -> bool:
        """导入知识图谱"""
        if not await self._ensure_initialized():
            logger.warning("知识图谱功能未启用，跳过导入操作")
            return False

        try:
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])

            # 导入节点
            for node in nodes:
                node_id = node["id"]
                labels = node.get("labels", [])
                properties = node.get("properties", {})
                await self.storage.upsert_node(node_id, labels, properties)

            # 导入边
            for edge in edges:
                source = edge["source"]
                target = edge["target"]
                edge_type = edge.get("type", "relates_to")
                properties = edge.get("properties", {})
                await self.storage.upsert_edge(source, target, edge_type, properties)

            logger.info(f"成功导入知识图谱: {len(nodes)} 个节点, {len(edges)} 条边")
            return True

        except Exception as e:
            logger.error(f"导入知识图谱失败: {e}")
            return False

    async def find_related_documents(
        self,
        doc_id: str,
        *,
        max_hops: int = 2,
        limit: int = 10,
        vector_collection: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """返回与指定文档相关的其它文档（依赖具体图存储实现）。"""
        if not await self._ensure_initialized():
            return []
        finder = getattr(self.storage, "find_related_documents", None)
        if not callable(finder):
            return []
        return await finder(
            doc_id,
            max_hops=max_hops,
            limit=limit,
            vector_collection=vector_collection,
        )
