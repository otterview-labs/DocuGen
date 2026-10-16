#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一检索相关 schema。
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, model_validator

from .common import schema_config


class SearchRequest(BaseModel):
    """统一检索请求模型"""

    query: Optional[str] = Field(
        None,
        description="检索查询内容（文本查询或图片查询至少提供一个）",
        json_schema_extra={"example": "系统架构设计"},
    )
    image: Optional[str] = Field(None, description="图片输入：支持base64编码、URL或本地路径")
    image_prompt: str = Field(
        "请详细描述这张图片的内容，包括主要物体、场景、文字、关键信息等",
        description="图片分析提示词，用于控制VLM分析的侧重点",
    )
    search_mode: str = Field(
        "intelligent",
        description="检索模式：intelligent(智能, 默认), semantic(语义), keyword(关键词), kg(知识图谱), file(文件级), image(图转文搜索), image_to_image(图搜图/视觉相似)",
        json_schema_extra={"example": "intelligent"},
    )

    collection_id: Optional[List[str]] = Field(None, description="集合ID列表，支持多集合搜索")
    resource_id: Optional[Union[str, List[str]]] = Field(
        None,
        description="资源ID过滤，支持单个资源ID或资源ID列表；KG检索会优先据此约束到对应文档图谱",
        json_schema_extra={"example": ["res_001", "res_002"]},
    )
    resource_types: Optional[List[str]] = Field(None, description="资源类型列表：file/text/url")
    bindings: Optional[List[str]] = Field(None, description="权限绑定key，自动从用户获取")

    top_k: int = Field(10, description="返回结果数量", ge=1, le=100)
    similarity_threshold: float = Field(0.15, description="相似度阈值", ge=0.0, le=1.0)
    max_files: int = Field(1, description="文件级检索时返回的文件数量", ge=1, le=10)
    answer_with_file: bool = Field(False, description="在文件级模式下，是否基于选中文件生成回答")
    max_content_chars: int = Field(6000, description="生成回答时用于上下文的最大字符数", ge=1000, le=20000)
    selected_file_ids: Optional[List[str]] = Field(None, description="显式指定用于文件级检索/回答的文件ID列表（绕过检索）")
    return_citations: bool = Field(True, description="answer_with_file 为 true 时，是否返回结构化引用信息")
    use_chunk_retrieval: bool = Field(True, description="回答时是否使用片段/段落级向量检索提升引用精度")
    per_file_citations: int = Field(2, description="每个文件返回的引用片段数量", ge=1, le=10)
    highlight_keywords: bool = Field(True, description="是否在引用片段中返回关键词高亮位置")
    field_semantic_select: bool = Field(False, description="是否基于标题/摘要/标签的语义相似度来选择文件")
    field_weights: Optional[Dict[str, float]] = Field(None, description="字段权重，如 {title:0.4, summary:0.5, tags:0.1}")
    insert_citation_markers: bool = Field(True, description="是否在回答中加入 [1][2] 小标")
    append_references: bool = Field(True, description="是否在回答末尾附带参考资料列表")

    kg_config: Optional[Dict[str, Any]] = Field(
        None,
        description="知识图谱配置",
        json_schema_extra={"example": {"search_type": "entity", "max_depth": 3, "include_relations": True}},
    )
    max_graph_hops: int = Field(2, description="跨文档扩展的最大跳数", ge=1, le=5)
    enable_graph_expansion: bool = Field(False, description="是否启用跨文档扩展（基于知识图谱，将相关文档加入候选集）")

    include_content: bool = Field(True, description="是否包含完整内容")
    include_snippet: bool = Field(True, description="是否包含内容片段")
    include_metadata: bool = Field(True, description="是否包含元数据")

    model_config = schema_config(
        examples=[
            {
                "query": "设备和网关之间的关系",
                "search_mode": "kg",
                "resource_id": "res_001",
                "kg_config": {"search_type": "relation", "max_depth": 2},
                "top_k": 10,
            },
            {
                "image": "data:image/png;base64,AAAA",
                "search_mode": "image_to_image",
                "top_k": 5,
            },
        ]
    )

    @model_validator(mode="after")
    def check_query_or_image(self):
        """验证至少提供 query 或 image 之一。"""
        if self.search_mode in {"image", "image_to_image", "visual_similarity"} and self.image:
            return self
        if not self.query and not self.image:
            raise ValueError("query和image至少提供一个")
        return self


class SearchResultDebugInternal(BaseModel):
    """检索结果内部调试信息。"""

    content_id: Optional[str] = Field(None, description="关联的 rag_contents.id")
    vector_id: Optional[str] = Field(None, description="底层向量ID或原始候选ID")

    model_config = schema_config(extra="allow")


class SearchResultDebug(BaseModel):
    """检索结果调试信息。"""

    internal: Optional[SearchResultDebugInternal] = Field(None, description="内部调试字段")

    model_config = schema_config(extra="allow")


class SearchHighlightRange(BaseModel):
    """命中高亮区间。"""

    term: Optional[str] = Field(None, description="命中的关键词")
    start: int = Field(..., description="起始偏移")
    end: int = Field(..., description="结束偏移")

    model_config = schema_config(extra="allow")


class SearchCitationOffset(BaseModel):
    """引用片段在文档中的偏移区间。"""

    start: int = Field(..., description="起始偏移")
    end: int = Field(..., description="结束偏移")

    model_config = schema_config(extra="allow")


class SearchCitation(BaseModel):
    """文件级问答引用信息。"""

    doc_id: Optional[str] = Field(None, description="文档ID")
    title: Optional[str] = Field(None, description="文档标题")
    snippet: Optional[str] = Field(None, description="引用片段")
    score: Optional[float] = Field(None, description="引用相关度分数")
    offset: Optional[SearchCitationOffset] = Field(None, description="引用片段偏移区间")
    highlights: Optional[List[SearchHighlightRange]] = Field(None, description="命中高亮区间")
    collection: Optional[str] = Field(None, description="所属集合ID（兼容字段）")
    collection_id: Optional[str] = Field(None, description="所属集合ID")
    resource_id: Optional[str] = Field(None, description="资源ID")
    file_name: Optional[str] = Field(None, description="文件名")

    model_config = schema_config(extra="allow")


class SearchExecutionQueryAnalysis(BaseModel):
    """查询分析信息。"""

    original_mode: Optional[str] = Field(None, description="请求的原始模式")
    selected_mode: Optional[str] = Field(None, description="实际执行模式")
    query_length: Optional[int] = Field(None, description="查询长度")
    has_filters: Optional[bool] = Field(None, description="是否带集合/资源过滤条件")

    model_config = schema_config(extra="allow")


class SearchExecutionPerformance(BaseModel):
    """检索性能与能力信息。"""

    vector_search_available: Optional[bool] = Field(None, description="语义向量检索是否可用")
    kg_search_available: Optional[bool] = Field(None, description="知识图谱检索是否可用")
    total_collections_searched: Optional[int] = Field(None, description="本次实际检索的集合数量")

    model_config = schema_config(extra="allow")


class SearchExecutionInfo(BaseModel):
    """统一检索执行信息。"""

    execution_time_ms: Optional[int] = Field(None, description="执行耗时（毫秒）")
    search_mode_used: Optional[str] = Field(None, description="实际执行的检索模式")
    result_count: Optional[int] = Field(None, description="返回结果数")
    query_analysis: Optional[SearchExecutionQueryAnalysis] = Field(None, description="查询分析")
    performance: Optional[SearchExecutionPerformance] = Field(None, description="执行性能信息")

    model_config = schema_config(extra="allow")


class SearchResultItem(BaseModel):
    """统一检索单条结果。"""

    id: Optional[str] = Field(None, description="内部/兼容结果ID")
    doc_id: Optional[str] = Field(None, description="兼容字段：文档ID")
    content_id: Optional[str] = Field(None, description="关联的 rag_contents.id")
    source_doc: Optional[str] = Field(None, description="KG 兼容字段：原始来源文档标识")
    title: Optional[str] = Field(None, description="结果标题")
    description: Optional[str] = Field(None, description="结果描述")
    content: Optional[str] = Field(None, description="完整内容")
    content_type: Optional[str] = Field(None, description="内容类型")
    snippet: Optional[str] = Field(None, description="结果摘要片段")
    similarity_score: Optional[float] = Field(None, description="相似度分数")
    score: Optional[float] = Field(None, description="兼容字段：评分")
    search_mode: Optional[str] = Field(None, description="对外返回的检索模式")
    original_search_mode: Optional[str] = Field(None, description="内部原始命中模式")
    resource_id: Optional[str] = Field(None, description="资源ID")
    collection_id: Optional[str] = Field(None, description="所属集合ID")
    version: Optional[int] = Field(None, description="文档版本号")
    metadata: Optional[Dict[str, Any]] = Field(None, description="扩展元数据")
    debug: Optional[SearchResultDebug] = Field(None, description="调试信息")

    model_config = schema_config(
        extra="allow",
        example={
            "title": "网关",
            "content_type": "knowledge_graph",
            "resource_id": "res-001",
            "collection_id": "collection-a",
            "version": 3,
            "similarity_score": 0.91,
            "debug": {"internal": {"content_id": "content-001", "vector_id": "entity-001"}},
        },
    )


class SearchResponse(BaseModel):
    """统一检索响应模型"""

    query: str
    search_mode: str
    total: int
    results: List[SearchResultItem]
    execution_info: SearchExecutionInfo
    suggestions: Optional[List[str]] = None
    answer: Optional[str] = None
    citations: Optional[List[SearchCitation]] = None

    model_config = schema_config(
        example={
            "query": "设备和网关之间的关系",
            "search_mode": "kg",
            "total": 1,
            "results": [
                {
                    "title": "网关",
                    "content_type": "knowledge_graph",
                    "resource_id": "res-001",
                    "collection_id": "collection-a",
                    "version": 3,
                    "search_mode": "kg",
                    "debug": {"internal": {"content_id": "content-001"}},
                }
            ],
            "execution_info": {
                "execution_time_ms": 12,
                "search_mode_used": "kg",
                "result_count": 1,
            },
        }
    )
