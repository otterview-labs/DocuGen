#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业知识图谱双模构建系统
支持向量化存储与知识图谱双模式知识构建，实现结构化与非结构化知识的融合
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import logging
import asyncio
import json
from datetime import datetime
import uuid
import re
from pathlib import Path
from app.config import settings

logger = logging.getLogger(__name__)


class KnowledgeType(Enum):
    """知识类型"""
    FACTUAL = "factual"           # 事实性知识
    PROCEDURAL = "procedural"     # 程序性知识
    CONCEPTUAL = "conceptual"     # 概念性知识
    RELATIONAL = "relational"     # 关系性知识


class ExtractionMode(Enum):
    """知识抽取模式"""
    RULE_BASED = "rule_based"     # 基于规则
    ML_BASED = "ml_based"         # 基于机器学习
    LLM_BASED = "llm_based"       # 基于大语言模型
    HYBRID = "hybrid"             # 混合模式


@dataclass
class Entity:
    """实体"""
    id: str
    name: str
    type: str
    properties: Dict[str, Any]
    source_id: str
    confidence: float = 1.0
    aliases: List[str] = None

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []


@dataclass
class Relation:
    """关系"""
    id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    properties: Dict[str, Any]
    confidence: float = 1.0
    evidence: List[str] = None

    def __post_init__(self):
        if self.evidence is None:
            self.evidence = []


@dataclass
class KnowledgeTriplet:
    """知识三元组"""
    subject: Entity
    predicate: str
    object: Entity
    confidence: float
    source: str
    context: str = ""


@dataclass
class VectorizedKnowledge:
    """向量化知识"""
    id: str
    content: str
    vector: List[float]
    metadata: Dict[str, Any]
    chunk_index: int = 0
    parent_document_id: str = ""


@dataclass
class DualModeKnowledge:
    """双模式知识"""
    id: str
    structured_knowledge: List[KnowledgeTriplet]
    vectorized_knowledge: VectorizedKnowledge
    source_data: CollectedData
    knowledge_type: KnowledgeType
    extraction_method: ExtractionMode
    created_at: datetime
    confidence_score: float = 0.0


class BaseKnowledgeExtractor(ABC):
    """知识抽取器基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def extract_entities(self, text: str, context: Dict[str, Any] = None) -> List[Entity]:
        """抽取实体"""
        pass

    @abstractmethod
    async def extract_relations(self, text: str, entities: List[Entity], context: Dict[str, Any] = None) -> List[Relation]:
        """抽取关系"""
        pass

    @abstractmethod
    async def extract_triplets(self, text: str, context: Dict[str, Any] = None) -> List[KnowledgeTriplet]:
        """抽取知识三元组"""
        pass


class RuleBasedExtractor(BaseKnowledgeExtractor):
    """基于规则的知识抽取器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.entity_patterns = self._load_entity_patterns()
        self.relation_patterns = self._load_relation_patterns()

    def _load_entity_patterns(self) -> Dict[str, List[str]]:
        """加载实体识别规则"""
        return {
            "PERSON": [
                r"(?:先生|女士|博士|教授|工程师|经理|总监|CEO|CTO)\s*([\\u4e00-\\u9fa5]{2,4})",
                r"([\\u4e00-\\u9fa5]{2,4})(?:先生|女士|博士|教授|工程师|经理|总监)",
            ],
            "ORGANIZATION": [
                r"([\\u4e00-\\u9fa5]+(?:公司|集团|企业|机构|部门|中心|研究所))",
                r"(\\b[A-Z][a-zA-Z\\s]+(?:Inc|Corp|Ltd|Company)\\b)",
            ],
            "LOCATION": [
                r"([\\u4e00-\\u9fa5]+(?:市|省|区|县|镇|村|路|街|号))",
                r"([\\u4e00-\\u9fa5]+(?:大厦|大楼|商场|医院|学校|银行))",
            ],
            "TECHNOLOGY": [
                r"\\b(Python|Java|JavaScript|React|Vue|Angular|Docker|Kubernetes)\\b",
                r"([\\u4e00-\\u9fa5]+(?:技术|算法|框架|平台|系统|工具))",
            ],
            "PRODUCT": [
                r"([\\u4e00-\\u9fa5]+(?:产品|服务|解决方案|平台))",
                r"\\b([A-Z][a-zA-Z]+\\s*(?:2\\.0|3\\.0|Pro|Plus|Max))\\b",
            ]
        }

    def _load_relation_patterns(self) -> List[Dict[str, str]]:
        """加载关系识别规则"""
        return [
            {
                "pattern": r"([\\u4e00-\\u9fa5]{2,10})(?:是|为)([\\u4e00-\\u9fa5]{2,10})(?:的)?([\\u4e00-\\u9fa5]{2,10})",
                "relation": "IS_A"
            },
            {
                "pattern": r"([\\u4e00-\\u9fa5]{2,10})(?:拥有|具有|包含)([\\u4e00-\\u9fa5]{2,10})",
                "relation": "HAS"
            },
            {
                "pattern": r"([\\u4e00-\\u9fa5]{2,10})(?:负责|管理|领导)([\\u4e00-\\u9fa5]{2,10})",
                "relation": "MANAGES"
            },
            {
                "pattern": r"([\\u4e00-\\u9fa5]{2,10})(?:属于|隶属于)([\\u4e00-\\u9fa5]{2,10})",
                "relation": "BELONGS_TO"
            },
            {
                "pattern": r"([\\u4e00-\\u9fa5]{2,10})(?:使用|采用|基于)([\\u4e00-\\u9fa5]{2,10})",
                "relation": "USES"
            }
        ]

    async def extract_entities(self, text: str, context: Dict[str, Any] = None) -> List[Entity]:
        """基于规则抽取实体"""
        entities = []

        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0] if match[0] else match[1]

                    entity = Entity(
                        id=str(uuid.uuid4()),
                        name=match.strip(),
                        type=entity_type,
                        properties={
                            "extraction_method": "rule_based",
                            "pattern": pattern,
                            "source_text": text[:100] + "..." if len(text) > 100 else text
                        },
                        source_id=context.get("source_id", "") if context else "",
                        confidence=0.8
                    )
                    entities.append(entity)

        # 去重
        unique_entities = {}
        for entity in entities:
            key = f"{entity.type}_{entity.name.lower()}"
            if key not in unique_entities or entity.confidence > unique_entities[key].confidence:
                unique_entities[key] = entity

        return list(unique_entities.values())

    async def extract_relations(self, text: str, entities: List[Entity], context: Dict[str, Any] = None) -> List[Relation]:
        """基于规则抽取关系"""
        relations = []

        for pattern_info in self.relation_patterns:
            pattern = pattern_info["pattern"]
            relation_type = pattern_info["relation"]

            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) >= 2:
                    source_name = match[0].strip()
                    target_name = match[1].strip()

                    # 查找匹配的实体
                    source_entity = None
                    target_entity = None

                    for entity in entities:
                        if entity.name.lower() == source_name.lower():
                            source_entity = entity
                        if entity.name.lower() == target_name.lower():
                            target_entity = entity

                    if source_entity and target_entity:
                        relation = Relation(
                            id=str(uuid.uuid4()),
                            source_entity_id=source_entity.id,
                            target_entity_id=target_entity.id,
                            relation_type=relation_type,
                            properties={
                                "extraction_method": "rule_based",
                                "pattern": pattern,
                                "evidence": [f"在文本中发现: {match}"]
                            },
                            confidence=0.7,
                            evidence=[text[:200] + "..." if len(text) > 200 else text]
                        )
                        relations.append(relation)

        return relations

    async def extract_triplets(self, text: str, context: Dict[str, Any] = None) -> List[KnowledgeTriplet]:
        """抽取知识三元组"""
        entities = await self.extract_entities(text, context)
        relations = await self.extract_relations(text, entities, context)

        triplets = []
        entity_map = {e.id: e for e in entities}

        for relation in relations:
            if relation.source_entity_id in entity_map and relation.target_entity_id in entity_map:
                triplet = KnowledgeTriplet(
                    subject=entity_map[relation.source_entity_id],
                    predicate=relation.relation_type,
                    object=entity_map[relation.target_entity_id],
                    confidence=relation.confidence,
                    source=context.get("source_id", "") if context else "",
                    context=text[:300] + "..." if len(text) > 300 else text
                )
                triplets.append(triplet)

        return triplets


class LLMBasedExtractor(BaseKnowledgeExtractor):
    """基于大语言模型的知识抽取器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.llm_config = config.get("llm", {})
        # 初始化统一LLM服务
        from app.core.llm.unified_service import UnifiedLLMService
        self.llm_service = UnifiedLLMService()

    async def extract_entities(self, text: str, context: Dict[str, Any] = None) -> List[Entity]:
        """基于LLM抽取实体"""
        try:
            from app.core.llm.unified_service import LLMRequest, TaskType

            prompt = f"""请从以下文本中提取实体，返回JSON格式：

文本：{text}

要求：
1. 识别人名、组织、地点、技术、产品等实体
2. 返回JSON数组格式：[{{"name": "实体名", "type": "实体类型", "confidence": 0.95}}]
3. confidence范围0-1，表示置信度
4. type可选：PERSON, ORGANIZATION, LOCATION, TECHNOLOGY, PRODUCT, OTHER

JSON:"""

            request = LLMRequest(
                messages=[{"role": "user", "content": prompt}],
                task_type=TaskType.ENTITY_EXTRACTION,
                temperature=0.1,
                max_tokens=1000
            )

            response = await self.llm_service.chat(request)

            # 解析LLM返回的JSON
            import json
            try:
                entities_data = json.loads(response.content)
                entities = []

                for entity_dict in entities_data:
                    entity = Entity(
                        id=str(uuid.uuid4()),
                        name=entity_dict.get("name", ""),
                        type=entity_dict.get("type", "OTHER"),
                        properties={
                            "extraction_method": "llm_based",
                            "llm_response": response.content,
                            "model_name": response.model_name
                        },
                        source_id=context.get("source_id", "") if context else "",
                        confidence=float(entity_dict.get("confidence", 0.8))
                    )
                    entities.append(entity)

                self.logger.info(f"LLM成功提取 {len(entities)} 个实体")
                return entities

            except json.JSONDecodeError as e:
                self.logger.error(f"LLM返回的JSON格式错误: {e}, 响应内容: {response.content}")
                # 降级到规则提取
                return await self._fallback_rule_extraction(text, context)

        except Exception as e:
            self.logger.error(f"LLM实体抽取失败: {e}")
            # 降级到规则提取
            return await self._fallback_rule_extraction(text, context)

    async def _fallback_rule_extraction(self, text: str, context: Dict[str, Any] = None) -> List[Entity]:
        """降级到规则抽取"""
        rule_extractor = RuleBasedExtractor({})
        return await rule_extractor.extract_entities(text, context)

    async def extract_relations(self, text: str, entities: List[Entity], context: Dict[str, Any] = None) -> List[Relation]:
        """基于LLM抽取关系"""
        try:
            if len(entities) < 2:
                return []

            from app.core.llm.unified_service import LLMRequest, TaskType

            # 构建实体列表用于prompt
            entity_list = "\n".join([f"- {e.name} ({e.type})" for e in entities])

            prompt = f"""请分析以下文本中实体间的关系，返回JSON格式：

                文本：{text}

                已识别实体：
                {entity_list}

                要求：
                1. 分析实体间的语义关系
                2. 返回JSON数组：[{{"source": "实体1", "target": "实体2", "relation": "关系类型", "confidence": 0.9}}]
                3. relation可选：IS_A, HAS, USES, MANAGES, BELONGS_TO, LOCATED_IN, PART_OF, OTHER
                4. 只返回文本中明确体现的关系

                JSON:"""

            request = LLMRequest(
                messages=[{"role": "user", "content": prompt}],
                task_type=TaskType.RELATION_EXTRACTION,
                temperature=0.1,
                max_tokens=1000
            )

            response = await self.llm_service.chat(request)

            # 解析关系
            import json
            try:
                relations_data = json.loads(response.content)
                relations = []

                # 创建实体名称到ID的映射
                entity_name_map = {e.name: e.id for e in entities}

                for rel_dict in relations_data:
                    source_name = rel_dict.get("source", "")
                    target_name = rel_dict.get("target", "")

                    # 查找对应实体ID
                    source_id = entity_name_map.get(source_name)
                    target_id = entity_name_map.get(target_name)

                    if source_id and target_id:
                        relation = Relation(
                            id=str(uuid.uuid4()),
                            source_entity_id=source_id,
                            target_entity_id=target_id,
                            relation_type=rel_dict.get("relation", "OTHER"),
                            properties={
                                "extraction_method": "llm_based",
                                "llm_response": response.content,
                                "model_name": response.model_name
                            },
                            confidence=float(rel_dict.get("confidence", 0.8)),
                            evidence=[text]
                        )
                        relations.append(relation)

                self.logger.info(f"LLM成功提取 {len(relations)} 个关系")
                return relations

            except json.JSONDecodeError as e:
                self.logger.error(f"LLM关系抽取JSON解析失败: {e}")
                return []

        except Exception as e:
            self.logger.error(f"LLM关系抽取失败: {e}")
            return []

    async def extract_triplets(self, text: str, context: Dict[str, Any] = None) -> List[KnowledgeTriplet]:
        """基于LLM抽取知识三元组"""
        entities = await self.extract_entities(text, context)
        relations = await self.extract_relations(text, entities, context)

        triplets = []
        entity_map = {e.id: e for e in entities}

        for relation in relations:
            if relation.source_entity_id in entity_map and relation.target_entity_id in entity_map:
                triplet = KnowledgeTriplet(
                    subject=entity_map[relation.source_entity_id],
                    predicate=relation.relation_type,
                    object=entity_map[relation.target_entity_id],
                    confidence=relation.confidence,
                    source=context.get("source_id", "") if context else "",
                    context=text
                )
                triplets.append(triplet)

        return triplets


class VectorKnowledgeProcessor:
    """向量知识处理器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.vector_db = None
        self.embedding_model = config.get("embedding_model", "text-embedding-ada-002")
        self.chunk_size = config.get("chunk_size", 512)
        self.chunk_overlap = config.get("chunk_overlap", 50)
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        """初始化向量数据库"""
        try:
            # 简化实现：不依赖具体的向量数据库
            self.vector_db = None  # 将在实际部署时初始化
            self.logger.info("向量数据库初始化完成（简化模式）")
        except Exception as e:
            self.logger.error(f"向量数据库初始化失败: {e}")
            raise

    def chunk_text(self, text: str) -> List[str]:
        """文本分块"""
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            # 尝试在合适的位置断句
            if end < len(text):
                # 寻找最近的句号、问号或感叹号
                for i in range(end, max(start + self.chunk_size // 2, start + 1), -1):
                    if text[i] in '。！？.!?':
                        end = i + 1
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - self.chunk_overlap
            if start >= len(text):
                break

        return chunks

    async def process_to_vectors(self, data: CollectedData) -> List[VectorizedKnowledge]:
        """处理数据为向量化知识"""
        try:
            chunks = self.chunk_text(data.content)
            vectorized_knowledge = []

            # 初始化嵌入模型
            from app.core.llm.embedding_model import create_embedding_model
            import os
            try:
                dim = int((os.getenv("VECTOR_DB_DIMENSION") or "1536").strip())
            except Exception:
                dim = 1536
            embedding_model = create_embedding_model()
            self.logger.info(
                "使用 %s embedding 模型处理知识图谱向量",
                (getattr(settings.embedding, "PROVIDER", "") or "openai").strip().lower(),
            )

            for i, chunk in enumerate(chunks):
                try:
                    # 生成真实向量
                    vectors, _ = embedding_model.encode([chunk])
                    vector = vectors[0].tolist()

                except Exception as e:
                    self.logger.error(f"向量化失败，使用模拟向量: {e}")
                    # 仅在嵌入失败时使用模拟向量
                    vector = [0.1] * dim

                vk = VectorizedKnowledge(
                    id=f"{data.source_id}_chunk_{i}",
                    content=chunk,
                    vector=vector,
                    metadata={
                        "source_id": data.source_id,
                        "source_type": data.source_type.value,
                        "title": data.title,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "created_time": data.created_time.isoformat(),
                        "tags": data.tags or [],
                        "embedding_model": embedding_model.__class__.__name__ if 'embedding_model' in locals() else "mock"
                    },
                    chunk_index=i,
                    parent_document_id=data.source_id
                )
                vectorized_knowledge.append(vk)

            self.logger.info(f"文档 {data.source_id} 成功分块为 {len(vectorized_knowledge)} 个向量知识单元")
            return vectorized_knowledge

        except Exception as e:
            self.logger.error(f"向量化处理失败: {e}")
            return []

    async def store_vectors(self, vectorized_knowledge: List[VectorizedKnowledge]) -> bool:
        """存储向量到向量数据库"""
        try:
            if not vectorized_knowledge:
                self.logger.warning("没有向量知识单元需要存储")
                return True

            # 导入向量数据库服务
            from app.core.rag.vector_db.faiss_db import FaissVectorDB
            import numpy as np

            vector_db = FaissVectorDB()

            # 准备向量和元数据
            vectors = []
            metadata_list = []
            ids = []

            for vk in vectorized_knowledge:
                vectors.append(vk.vector)
                metadata_list.append({
                    **vk.metadata,
                    "content": vk.content,
                    "chunk_index": vk.chunk_index,
                    "parent_document_id": vk.parent_document_id,
                    "knowledge_id": vk.id,
                    "created_at": datetime.now().isoformat()
                })
                ids.append(vk.id)

            # 转换为numpy数组
            vectors_array = np.array(vectors, dtype=np.float32)

            # 确定集合名称（根据配置或使用默认）
            collection_name = self.config.get("collection_name", "knowledge_graph")

            # 如果集合不存在，先创建
            if not vector_db.collection_exists(collection_name):
                vector_db.create_collection(collection_name, dimension=len(vectors[0]))
                self.logger.info(f"创建向量集合: {collection_name}")

            # 添加向量
            stored_ids = vector_db.add_vectors(
                collection_name=collection_name,
                vectors=vectors_array,
                metadata=metadata_list,
                ids=ids
            )

            self.logger.info(f"成功存储 {len(stored_ids)} 个向量知识单元到集合 {collection_name}")
            return len(stored_ids) == len(vectorized_knowledge)

        except Exception as e:
            self.logger.error(f"向量存储失败: {e}")
            return False


class KnowledgeGraphBuilder:
    """知识图谱构建器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.extractors = {}
        self.vector_processor = VectorKnowledgeProcessor(config.get("vector", {}))
        self.logger = logging.getLogger(__name__)

        # 初始化抽取器
        self._init_extractors()

    def _init_extractors(self):
        """初始化知识抽取器"""
        extractor_configs = self.config.get("extractors", {})

        if extractor_configs.get("rule_based", {}).get("enabled", True):
            self.extractors[ExtractionMode.RULE_BASED] = RuleBasedExtractor(
                extractor_configs.get("rule_based", {})
            )

        if extractor_configs.get("llm_based", {}).get("enabled", False):
            self.extractors[ExtractionMode.LLM_BASED] = LLMBasedExtractor(
                extractor_configs.get("llm_based", {})
            )

        self.logger.info(f"初始化了 {len(self.extractors)} 个知识抽取器")

    async def build_dual_mode_knowledge(self, data: CollectedData, extraction_mode: ExtractionMode = ExtractionMode.RULE_BASED) -> DualModeKnowledge:
        """构建双模式知识"""
        try:
            self.logger.info(f"开始构建双模式知识: {data.title}")

            # 1. 结构化知识抽取
            structured_knowledge = []
            if extraction_mode in self.extractors:
                extractor = self.extractors[extraction_mode]
                context = {
                    "source_id": data.source_id,
                    "source_type": data.source_type.value,
                    "title": data.title
                }

                triplets = await extractor.extract_triplets(data.content, context)
                structured_knowledge = triplets
                self.logger.info(f"抽取到 {len(triplets)} 个知识三元组")

            # 2. 向量化知识处理
            vectorized_knowledge_list = await self.vector_processor.process_to_vectors(data)

            # 选择主要的向量化知识（第一个chunk）
            main_vectorized_knowledge = vectorized_knowledge_list[0] if vectorized_knowledge_list else VectorizedKnowledge(
                id=data.source_id,
                content=data.content,
                vector=[0.0] * 1536,
                metadata={"source_id": data.source_id}
            )

            # 3. 知识类型判断
            knowledge_type = self._determine_knowledge_type(data, structured_knowledge)

            # 4. 计算置信度分数
            confidence_score = self._calculate_confidence_score(structured_knowledge, vectorized_knowledge_list)

            # 5. 构建双模式知识
            dual_knowledge = DualModeKnowledge(
                id=f"dual_{data.source_id}",
                structured_knowledge=structured_knowledge,
                vectorized_knowledge=main_vectorized_knowledge,
                source_data=data,
                knowledge_type=knowledge_type,
                extraction_method=extraction_mode,
                created_at=datetime.now(),
                confidence_score=confidence_score
            )

            self.logger.info(f"双模式知识构建完成，置信度: {confidence_score:.2f}")
            return dual_knowledge

        except Exception as e:
            self.logger.error(f"双模式知识构建失败: {e}")
            raise

    def _determine_knowledge_type(self, data: CollectedData, structured_knowledge: List[KnowledgeTriplet]) -> KnowledgeType:
        """判断知识类型"""
        content = data.content.lower()

        # 基于关键词判断知识类型
        if any(keyword in content for keyword in ["步骤", "流程", "如何", "方法", "操作", "procedure", "how to", "step"]):
            return KnowledgeType.PROCEDURAL
        elif any(keyword in content for keyword in ["概念", "定义", "什么是", "含义", "concept", "definition", "meaning"]):
            return KnowledgeType.CONCEPTUAL
        elif len(structured_knowledge) > 2:  # 有较多关系的认为是关系性知识
            return KnowledgeType.RELATIONAL
        else:
            return KnowledgeType.FACTUAL

    def _calculate_confidence_score(self, structured_knowledge: List[KnowledgeTriplet], vectorized_knowledge: List[VectorizedKnowledge]) -> float:
        """计算置信度分数"""
        if not structured_knowledge and not vectorized_knowledge:
            return 0.0

        # 结构化知识置信度权重 40%
        structured_score = 0.0
        if structured_knowledge:
            structured_score = sum(triplet.confidence for triplet in structured_knowledge) / len(structured_knowledge)

        # 向量化知识置信度权重 30%（基于内容长度和完整性）
        vector_score = 0.0
        if vectorized_knowledge:
            total_content_length = sum(len(vk.content) for vk in vectorized_knowledge)
            vector_score = min(1.0, total_content_length / 1000)  # 1000字符为满分

        # 数据源可靠性权重 30%
        source_score = 0.8  # 默认数据源可靠性

        final_score = structured_score * 0.4 + vector_score * 0.3 + source_score * 0.3
        return round(final_score, 3)


class DualModeKnowledgeManager:
    """双模式知识管理器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.kg_builder = KnowledgeGraphBuilder(config.get("knowledge_graph", {}))
        self.data_manager = MultiSourceDataManager()
        self.knowledge_storage = {}  # 简化的存储，实际应该用数据库
        self.logger = logging.getLogger(__name__)

    async def build_enterprise_knowledge_base(self, data_sources: List[CollectedData]) -> Dict[str, Any]:
        """构建企业知识库"""
        results = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "knowledge_types": {},
            "extraction_stats": {},
            "knowledge_ids": []
        }

        self.logger.info(f"开始构建企业知识库，数据源数量: {len(data_sources)}")

        for data in data_sources:
            try:
                results["total_processed"] += 1

                # 构建双模式知识
                dual_knowledge = await self.kg_builder.build_dual_mode_knowledge(data)

                # 存储知识
                self.knowledge_storage[dual_knowledge.id] = dual_knowledge

                # 统计信息
                results["successful"] += 1
                results["knowledge_ids"].append(dual_knowledge.id)

                # 知识类型统计
                knowledge_type = dual_knowledge.knowledge_type.value
                results["knowledge_types"][knowledge_type] = results["knowledge_types"].get(knowledge_type, 0) + 1

                # 抽取方法统计
                extraction_method = dual_knowledge.extraction_method.value
                results["extraction_stats"][extraction_method] = results["extraction_stats"].get(extraction_method, 0) + 1

                self.logger.info(f"成功处理数据源: {data.title}")

            except Exception as e:
                results["failed"] += 1
                self.logger.error(f"处理数据源失败 {data.title}: {e}")

        self.logger.info(f"企业知识库构建完成，成功: {results['successful']}, 失败: {results['failed']}")
        return results

    async def query_knowledge(self, query: str, mode: str = "hybrid") -> Dict[str, Any]:
        """查询知识"""
        results = {
            "query": query,
            "mode": mode,
            "structured_results": [],
            "vector_results": [],
            "hybrid_results": []
        }

        if mode in ["structured", "hybrid"]:
            # 结构化查询
            structured_results = self._query_structured_knowledge(query)
            results["structured_results"] = structured_results

        if mode in ["vector", "hybrid"]:
            # 向量查询
            vector_results = await self._query_vector_knowledge(query)
            results["vector_results"] = vector_results

        if mode == "hybrid":
            # 混合结果
            results["hybrid_results"] = self._merge_query_results(
                results["structured_results"],
                results["vector_results"]
            )

        return results

    def _query_structured_knowledge(self, query: str) -> List[Dict[str, Any]]:
        """查询结构化知识"""
        results = []
        query_lower = query.lower()

        for knowledge_id, dual_knowledge in self.knowledge_storage.items():
            for triplet in dual_knowledge.structured_knowledge:
                # 简单的关键词匹配
                if (query_lower in triplet.subject.name.lower() or
                    query_lower in triplet.object.name.lower() or
                    query_lower in triplet.predicate.lower()):

                    results.append({
                        "knowledge_id": knowledge_id,
                        "triplet": {
                            "subject": triplet.subject.name,
                            "predicate": triplet.predicate,
                            "object": triplet.object.name,
                            "confidence": triplet.confidence
                        },
                        "source": triplet.source,
                        "context": triplet.context[:200]
                    })

        return sorted(results, key=lambda x: x["triplet"]["confidence"], reverse=True)

    async def _query_vector_knowledge(self, query: str) -> List[Dict[str, Any]]:
        """查询向量知识"""
        try:
            from app.core.llm.embedding_model import create_embedding_model
            import numpy as np

            # 初始化嵌入模型
            embedding_model = create_embedding_model()

            # 生成查询向量
            query_vectors, _ = embedding_model.encode([query])
            query_vector = query_vectors[0]

            results = []

            for knowledge_id, dual_knowledge in self.knowledge_storage.items():
                vk = dual_knowledge.vectorized_knowledge

                try:
                    # 计算余弦相似度
                    doc_vector = np.array(vk.vector)
                    similarity = np.dot(query_vector, doc_vector) / (
                        np.linalg.norm(query_vector) * np.linalg.norm(doc_vector)
                    )

                    # 设置相似度阈值
                    if similarity > 0.3:
                        results.append({
                            "knowledge_id": knowledge_id,
                            "content": vk.content,
                            "similarity_score": float(similarity),
                            "metadata": vk.metadata,
                            "search_method": "vector_similarity"
                        })

                except Exception as e:
                    self.logger.error(f"计算相似度失败: {e}")
                    # 降级到关键词匹配
                    if query.lower() in vk.content.lower():
                        results.append({
                            "knowledge_id": knowledge_id,
                            "content": vk.content,
                            "similarity_score": 0.5,  # 关键词匹配默认分数
                            "metadata": vk.metadata,
                            "search_method": "keyword_fallback"
                        })

            return sorted(results, key=lambda x: x["similarity_score"], reverse=True)

        except Exception as e:
            self.logger.error(f"向量查询失败: {e}")
            # 最终降级到关键词搜索
            return self._fallback_keyword_search(query)

    def _fallback_keyword_search(self, query: str) -> List[Dict[str, Any]]:
        """降级关键词搜索"""
        results = []
        query_lower = query.lower()

        for knowledge_id, dual_knowledge in self.knowledge_storage.items():
            vk = dual_knowledge.vectorized_knowledge
            if query_lower in vk.content.lower():
                results.append({
                    "knowledge_id": knowledge_id,
                    "content": vk.content,
                    "similarity_score": 0.6,  # 关键词匹配固定分数
                    "metadata": vk.metadata,
                    "search_method": "keyword"
                })

        return sorted(results, key=lambda x: x["similarity_score"], reverse=True)

    def _merge_query_results(self, structured_results: List[Dict], vector_results: List[Dict]) -> List[Dict]:
        """合并查询结果"""
        merged = []

        # 按知识ID分组
        knowledge_groups = {}

        for result in structured_results:
            kid = result["knowledge_id"]
            if kid not in knowledge_groups:
                knowledge_groups[kid] = {"structured": [], "vector": []}
            knowledge_groups[kid]["structured"].append(result)

        for result in vector_results:
            kid = result["knowledge_id"]
            if kid not in knowledge_groups:
                knowledge_groups[kid] = {"structured": [], "vector": []}
            knowledge_groups[kid]["vector"].append(result)

        # 构建混合结果
        for knowledge_id, group in knowledge_groups.items():
            dual_knowledge = self.knowledge_storage.get(knowledge_id)
            if dual_knowledge:
                merged.append({
                    "knowledge_id": knowledge_id,
                    "title": dual_knowledge.source_data.title,
                    "knowledge_type": dual_knowledge.knowledge_type.value,
                    "confidence_score": dual_knowledge.confidence_score,
                    "structured_matches": len(group["structured"]),
                    "vector_matches": len(group["vector"]),
                    "structured_details": group["structured"],
                    "vector_details": group["vector"]
                })

        return sorted(merged, key=lambda x: x["confidence_score"], reverse=True)

    def get_knowledge_statistics(self) -> Dict[str, Any]:
        """获取知识统计信息"""
        stats = {
            "total_knowledge": len(self.knowledge_storage),
            "knowledge_types": {},
            "extraction_methods": {},
            "data_sources": {},
            "confidence_distribution": {"high": 0, "medium": 0, "low": 0},
            "structured_triplets": 0,
            "vector_chunks": 0
        }

        for dual_knowledge in self.knowledge_storage.values():
            # 知识类型统计
            kt = dual_knowledge.knowledge_type.value
            stats["knowledge_types"][kt] = stats["knowledge_types"].get(kt, 0) + 1

            # 抽取方法统计
            em = dual_knowledge.extraction_method.value
            stats["extraction_methods"][em] = stats["extraction_methods"].get(em, 0) + 1

            # 数据源统计
            ds = dual_knowledge.source_data.source_type.value
            stats["data_sources"][ds] = stats["data_sources"].get(ds, 0) + 1

            # 置信度分布
            if dual_knowledge.confidence_score >= 0.8:
                stats["confidence_distribution"]["high"] += 1
            elif dual_knowledge.confidence_score >= 0.5:
                stats["confidence_distribution"]["medium"] += 1
            else:
                stats["confidence_distribution"]["low"] += 1

            # 三元组和向量统计
            stats["structured_triplets"] += len(dual_knowledge.structured_knowledge)
            stats["vector_chunks"] += 1  # 每个知识单元对应一个主要向量块

        return stats


# 使用示例
async def demo_dual_mode_knowledge_construction():
    """双模式知识构建演示"""
    # 配置
    config = {
        "knowledge_graph": {
            "extractors": {
                "rule_based": {
                    "enabled": True,
                    "confidence_threshold": 0.7
                },
                "llm_based": {
                    "enabled": False,
                    "llm": {
                        "model": "qwen-max",
                        "api_key": "your_api_key"
                    }
                }
            },
            "vector": {
                "embedding_model": "text-embedding-ada-002",
                "chunk_size": 512,
                "chunk_overlap": 50
            }
        }
    }

    # 创建管理器
    manager = DualModeKnowledgeManager(config)

    # 模拟数据源
    sample_data = [
        CollectedData(
            source_id="tech_doc_001",
            source_type=DataSourceType.WEB_PAGE,
            title="人工智能技术概述",
            content="人工智能是计算机科学的一个分支，它使用机器学习和深度学习技术来模拟人类智能。深度学习基于神经网络，是机器学习的子集。人工智能在图像识别、自然语言处理等领域有广泛应用。",
            metadata={"category": "technology", "language": "zh"},
            created_time=datetime.now(),
            tags=["人工智能", "机器学习", "技术"]
        ),
        CollectedData(
            source_id="process_doc_001",
            source_type=DataSourceType.OA_SYSTEM,
            title="软件开发流程",
            content="软件开发流程包括以下步骤：1. 需求分析阶段，项目经理负责收集用户需求；2. 设计阶段，架构师设计系统架构；3. 编码阶段，开发人员使用Python和JavaScript进行开发；4. 测试阶段，测试工程师执行功能测试。",
            metadata={"category": "process", "department": "技术部"},
            created_time=datetime.now(),
            tags=["软件开发", "流程", "项目管理"]
        )
    ]

    logger.info("=== 开始构建企业双模式知识库 ===")

    # 构建知识库
    build_results = await manager.build_enterprise_knowledge_base(sample_data)
    logger.info(f"构建结果: {json.dumps(build_results, ensure_ascii=False, indent=2)}")

    logger.info("\n=== 知识库统计信息 ===")
    stats = manager.get_knowledge_statistics()
    logger.info(f"统计信息: {json.dumps(stats, ensure_ascii=False, indent=2)}")

    logger.info("\n=== 结构化知识查询 ===")
    structured_query = await manager.query_knowledge("人工智能", mode="structured")
    logger.info(f"结构化查询结果: {json.dumps(structured_query['structured_results'], ensure_ascii=False, indent=2)}")

    logger.info("\n=== 向量知识查询 ===")
    vector_query = await manager.query_knowledge("软件开发", mode="vector")
    logger.info(f"向量查询结果: {json.dumps(vector_query['vector_results'], ensure_ascii=False, indent=2)}")

    logger.info("\n=== 混合模式查询 ===")
    hybrid_query = await manager.query_knowledge("技术", mode="hybrid")
    logger.info(f"混合查询结果: {json.dumps(hybrid_query['hybrid_results'], ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    asyncio.run(demo_dual_mode_knowledge_construction())
