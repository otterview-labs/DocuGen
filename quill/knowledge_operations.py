"""Explicit knowledge-engine operations exposed by the shared workspace.

Aliases and transport-only helpers are documented in KNOWLEDGE_CAPABILITIES.md.
There is deliberately no arbitrary engine path supplied by the caller.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Operation:
    title: str
    group: str
    path: str
    description: str
    fields: list[dict[str, Any]] = field(default_factory=list)
    method: str = "POST"
    encoding: str = "json"
    dependency: str = ""
    destructive: bool = False


def f(key, label, kind="text", default=None, **options):
    return {"key": key, "label": label, "kind": kind, "default": default, **options}


collection = f("collection_id", "知识库", "collection", required=True)
resources = f("resource_ids", "资料", "resources", required=True)
content = f("content_id", "资料", "content", required=True)
OPERATIONS = {
    "upload": Operation(
        "上传待解析文件",
        "import",
        "multimodal/upload",
        "保存到知识引擎，随后可在“解析已上传文件”中处理。",
        encoding="file",
    ),
    "process": Operation(
        "上传并解析",
        "import",
        "simple-upload/process",
        "调用引擎解析器；图片、音视频和扫描件需要对应解析器与模型。",
        [
            collection,
            f("title", "资料标题"),
            f("enable_audio", "启用音频转写", "boolean", False),
            f("parse_options_json", "解析选项", "json-string", {}, advanced=True),
        ],
        encoding="file",
    ),
    "process-upload": Operation(
        "解析已上传文件",
        "import",
        "simple-upload/process-url",
        "使用前一步返回的已上传文件地址。",
        [
            collection,
            f("url", "已上传文件地址", required=True, placeholder="/uploads/…"),
            f("title", "资料标题"),
            f("parse_options_json", "解析选项", "json-string", {}, advanced=True),
        ],
        encoding="form",
    ),
    "batch-parse": Operation(
        "批量解析文件",
        "import",
        "resource-parse/batch-parse",
        "每行一个已上传文件地址。任务提交后可按任务编号查看进度。",
        [collection, f("urls", "已上传文件地址（每行一个）", "lines", required=True)],
    ),
    "batch-status": Operation(
        "解析任务进度",
        "import",
        "resource-parse/batch-status",
        "输入批量解析返回的任务编号；状态保存在引擎进程中，重启后不保留。",
        [f("batch_id", "任务编号", required=True)],
    ),
    "markdown": Operation(
        "查看解析正文",
        "import",
        "resource-parse/markdown",
        "读取已解析的 Markdown 内容。",
        [f("resource_id", "资料", "resource", required=True)],
    ),
    "qa-single": Operation(
        "添加问答对",
        "import",
        "qa/single",
        "保存问题和答案，未配置向量模型时仍可使用关键词检索。",
        [
            collection,
            f("question", "问题", "textarea", required=True),
            f("answer", "答案", "textarea", required=True),
            f("title", "资料标题"),
            f("metadata", "补充元数据", "json-string", {}, advanced=True),
        ],
        encoding="form",
    ),
    "qa-batch": Operation(
        "批量导入问答对",
        "import",
        "qa/batch",
        "上传 UTF-8 JSON 数组或带 question、answer 表头的 CSV，逐条显示导入结果。",
        [collection],
        encoding="file",
    ),
    "formats": Operation(
        "解析格式与限制",
        "import",
        "multimodal/supported-formats",
        "查看引擎声明的文件格式；是否能解析还取决于已安装的解析器。",
        method="GET",
    ),
    "strategies": Operation(
        "分块策略", "analysis", "chunking/strategies", "查看每种分块策略的适用场景和默认参数。", method="GET"
    ),
    "chunks": Operation(
        "实际存储分块",
        "analysis",
        "quill/resources/chunks",
        "读取数据库中的实际分块与索引状态；与预览中的阅读分段区分。",
        [f("resource_id", "资料", "resource", required=True)],
    ),
    "analyze": Operation(
        "生成摘要与标签",
        "analysis",
        "content-analysis/analyze",
        "分析所选资料，可批量执行；需要生成模型。",
        [
            resources,
            f(
                "analysis_type",
                "分析内容",
                "select",
                "both",
                options=[["both", "摘要与标签"], ["summary", "仅摘要"], ["tags", "仅标签"]],
            ),
        ],
        dependency="llm",
    ),
    "analysis-result": Operation(
        "查看已有分析",
        "analysis",
        "content-analysis/get-result",
        "读取已保存的摘要和标签，不调用模型。",
        [content],
    ),
    "reindex": Operation(
        "批量重建向量索引",
        "analysis",
        "documents/reindex",
        "按当前知识库处理启用资料；需要 Embedding 模型。",
        [
            collection,
            f("limit", "最多处理份数", "number", 200, min=1, max=5000),
            f("overwrite", "重建已有索引", "boolean", False),
        ],
        dependency="embedding",
    ),
    "status": Operation(
        "启用或停用资料",
        "settings",
        "documents/batch-toggle-status",
        "停用资料会退出检索，原文仍保留。",
        [
            resources,
            f("action", "操作", "select", "disable", options=[["enable", "启用"], ["disable", "停用"]]),
            f("reason", "操作说明"),
        ],
    ),
    "metadata": Operation(
        "编辑资料详细信息",
        "settings",
        "documents/update",
        "修改标题、说明、标签以及关联信息。当前仍是单一共享工作区。",
        [
            f("id", "资料", "content", required=True),
            f("name", "资料标题"),
            f("description", "资料说明", "textarea"),
            f("tags", "标签（每行一个）", "lines"),
            f("bindings", "绑定标记（每行一个）", "lines", advanced=True),
            f("relation", "关联对象", "json", [], advanced=True),
        ],
    ),
    "collection-detail": Operation(
        "知识库设置",
        "settings",
        "collections/{collection_id}",
        "查看知识库类型、模型设置和描述。",
        [collection],
        method="GET",
    ),
    "collection-update": Operation(
        "修改知识库设置",
        "settings",
        "collections/update",
        "修改名称、说明、集合类型与默认模型记录。实际模型服务仍使用部署配置。",
        [
            collection,
            f("name", "知识库名称", required=True),
            f("description", "说明", "textarea"),
            f(
                "collection_type",
                "集合类型",
                "select",
                "text",
                options=[["text", "文本"], ["multimodal", "多模态"]],
            ),
            f("embedding_model", "Embedding 模型名称"),
            f("rerank_model", "重排序模型名称"),
        ],
    ),
    "collection-delete": Operation(
        "删除知识库",
        "settings",
        "collections/delete",
        "永久删除当前知识库及其资料。请先确认需要保留的原文已下载。",
        [collection],
        destructive=True,
    ),
    "advanced-search": Operation(
        "高级检索",
        "search",
        "search/unified",
        "支持七种检索模式、资料范围和结构化引用。图像与图谱模式需要相应配置。",
        [
            collection,
            f("query", "查询内容", "textarea"),
            f(
                "search_mode",
                "检索模式",
                "select",
                "keyword",
                options=[
                    ["keyword", "关键词"],
                    ["intelligent", "智能"],
                    ["semantic", "语义"],
                    ["file", "文件级"],
                    ["kg", "知识图谱"],
                    ["image", "以图搜文"],
                    ["image_to_image", "以图搜图"],
                ],
            ),
            f("image", "查询图片", "image"),
            f("top_k", "结果数量", "number", 10, min=1, max=100),
            f("similarity_threshold", "相似度阈值", "number", 0.15, min=0, max=1, step=0.05),
            f("resource_id", "限定资料", "resources"),
            f("max_files", "最多文件数", "number", 3, min=1, max=10, advanced=True),
            f("answer_with_file", "基于文件生成回答", "boolean", False, advanced=True),
            f("return_citations", "返回结构化引用", "boolean", True, advanced=True),
            f("use_chunk_retrieval", "使用分块检索", "boolean", True, advanced=True),
            f("per_file_citations", "每份资料引用数", "number", 2, min=1, max=10, advanced=True),
            f("field_semantic_select", "按标题、摘要和标签语义排序", "boolean", False, advanced=True),
            f("enable_graph_expansion", "跨文档图谱扩展", "boolean", False, advanced=True),
            f("max_graph_hops", "图谱扩展跳数", "number", 2, min=1, max=5, advanced=True),
            f("kg_config", "图谱检索设置", "json", {"search_type": "entity", "max_depth": 1}, advanced=True),
            f(
                "field_weights",
                "字段权重",
                "json",
                {"title": 0.4, "summary": 0.5, "tags": 0.1},
                advanced=True,
            ),
        ],
    ),
    "search-methods": Operation(
        "检索方法说明", "search", "search/methods", "查看引擎返回的检索方法与示例。", method="GET"
    ),
    "graph-query": Operation(
        "查询实体与关系",
        "graph",
        "kg/query",
        "按关键词、实体类型或资料范围查找子图。",
        [
            f("query", "实体关键词"),
            f("node_type", "实体类型"),
            f("document_id", "限定资料", "content"),
            f("limit", "最多节点数", "number", 30, min=1, max=100),
            f("include_relations", "包含关系", "boolean", True),
            f("expand_neighbors", "扩展相邻节点", "boolean", True),
            f("max_depth", "扩展深度", "number", 1, min=1, max=3),
            f("max_edges", "最多关系数", "number", 200, min=1, max=1000),
        ],
        dependency="graph",
    ),
    "graph-view": Operation(
        "知识图谱浏览",
        "graph",
        "kg/visualization/graph-data",
        "查看当前知识库的实体关系网络。",
        [
            collection,
            f("query", "实体关键词"),
            f("entity_type", "实体类型"),
            f("max_nodes", "最多节点数", "number", 100, min=1, max=500),
            f("layout", "布局", "select", "force", options=[["force", "关系网络"], ["circular", "环形"]]),
        ],
        dependency="graph",
    ),
    "graph-extract": Operation(
        "抽取实体与关系",
        "graph",
        "kg/extract",
        "从资料或直接输入的文字中抽取实体关系，不写入图数据库。",
        [
            f("content_id", "资料", "content"),
            f("text_content", "直接输入文字", "textarea"),
            f(
                "extraction_type",
                "抽取内容",
                "select",
                "both",
                options=[["both", "实体与关系"], ["entities", "实体"], ["relations", "关系"]],
            ),
            f("max_entities", "最多实体数", "number", 50, min=1, max=200),
            f("max_relations", "最多关系数", "number", 100, min=1, max=500),
        ],
        dependency="llm",
    ),
    "graph-build": Operation(
        "构建资料图谱",
        "graph",
        "kg/build-graph",
        "抽取所选资料的实体关系并写入图数据库。",
        [
            content,
            f(
                "extraction_type",
                "抽取内容",
                "select",
                "both",
                options=[["both", "实体与关系"], ["entities", "实体"], ["relations", "关系"]],
            ),
            f("max_entities", "最多实体数", "number", 50, min=1, max=200),
            f("max_relations", "最多关系数", "number", 100, min=1, max=500),
        ],
        dependency="graph_llm",
    ),
    "graph-entities": Operation(
        "查看资料实体",
        "graph",
        "kg/get-entities",
        "读取所选资料的已保存实体。",
        [content],
        dependency="graph",
    ),
    "graph-association": Operation(
        "实体关联分析",
        "graph",
        "kg/analysis/association",
        "围绕一个实体查询关联网络。",
        [
            f("entity", "实体名称", required=True),
            f("depth", "关联深度", "number", 2, min=1, max=5),
            f("threshold", "相关性阈值", "number", 0.5, min=0, max=1, step=0.05),
            f("limit", "最多结果数", "number", 50, min=1, max=200),
        ],
        dependency="graph",
    ),
    "graph-statistics": Operation(
        "图谱统计",
        "graph",
        "kg/statistics/knowledge-graph",
        "读取图数据库的实体与关系统计。",
        method="GET",
        dependency="graph",
    ),
}
