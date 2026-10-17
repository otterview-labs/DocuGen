# Knowledge capability coverage — 2026-10-17

The inventory is based on the running knowledge engine's OpenAPI document, checked against source registration. Distinct HTTP aliases and legacy transport helpers share one product task; they are not duplicated as separate buttons. All gateway operations require the workspace access key and use a closed allowlist.

The knowledge page retains document management and basic retrieval/answers, and adds 28 named operations under import/parse, chunking/analysis, graph, settings and advanced retrieval. A prerequisite is marked configured only from deployment configuration; this does not establish provider health or output quality. No paid model was called during acceptance.

| Method | Engine path below `/api/v1/rag/` | Page entry / adaptation |
| --- | --- | --- |
| POST | `collections` | 新建知识库 |
| POST | `collections/search` | 知识库列表 |
| POST | `collections/find` | 知识库列表 |
| POST | `collections/list` | 知识库列表 |
| POST | `collections/documents` | 资料管理列表 |
| POST | `collections/delete` | 知识库设置／删除知识库 |
| DELETE, GET | `collections/{collection_id}` | 知识库设置／知识库设置或删除知识库 |
| POST | `collections/update` | 知识库设置／修改知识库设置 |
| POST | `multimodal/upload` | 导入与解析／上传待解析文件 |
| GET | `multimodal/supported-formats` | 导入与解析／解析格式与限制 |
| POST | `simple-upload/process` | 导入与解析／上传并解析 |
| POST | `simple-upload/process-url` | 导入与解析／解析已上传文件 |
| POST | `documents` | 资料管理列表 |
| POST | `documents/reindex` | 分块与分析／批量重建向量索引 |
| POST | `documents/update` | 知识库设置／编辑资料详细信息 |
| POST | `documents/delete` | 资料预览／删除资料 |
| GET | `documents/raw/{document_id}` | 资料预览／原文 |
| GET, POST | `documents/download` | 资料预览／下载原文件或导出文本 |
| POST | `documents/get` | 资料预览 |
| POST | `documents/batch-toggle-status` | 知识库设置／启用或停用资料 |
| POST | `documents/batch-delete` | 资料管理／批量移除（逐份清理原文件） |
| POST | `documents/chunks` | 分块与分析／实际存储分块（适配数据库，替代 Milvus 专用查询） |
| POST | `resource-parse/batch-parse` | 导入与解析／批量解析文件 |
| POST | `resource-parse/batch-status` | 导入与解析／解析任务进度 |
| POST | `resource-parse/markdown` | 导入与解析／查看解析正文 |
| GET | `chunking/strategies` | 分块与分析／分块策略 |
| POST | `search/unified` | 高级检索／高级检索 |
| POST | `kg/query` | 知识图谱／查询实体与关系 |
| POST | `kg/analysis/association` | 知识图谱／实体关联分析 |
| GET | `kg/statistics/knowledge-graph` | 知识图谱／图谱统计 |
| POST | `kg/extract` | 知识图谱／抽取实体与关系 |
| POST | `kg/build-graph` | 知识图谱／构建资料图谱 |
| POST | `kg/get-entities` | 知识图谱／查看资料实体 |
| POST | `kg/visualization/graph-data` | 知识图谱／知识图谱浏览 |
| POST | `content-analysis/analyze` | 分块与分析／生成摘要与标签 |
| POST | `content-analysis/batch-analyze` | 分块与分析／生成摘要与标签（使用 analyze 的 resource_id 列表） |
| POST | `content-analysis/get-result` | 分块与分析／查看已有分析 |
| GET | `search/methods` | 高级检索／检索方法说明 |
| GET | `search/methods/{mode}` | 高级检索／检索方法说明（methods 已包含各方法） |
| POST | `qa/single` | 导入与解析／添加问答对 |
| POST | `qa/batch` | 导入与解析／批量导入问答对 |
| GET | `qa/template` | 导入与解析／JSON、CSV 导入模板 |
| POST | `quill/text` | 导入资料／粘贴文本 |
| POST | `quill/overview` | 知识库列表与资料统计 |
| POST | `quill/resources/list` | 资料管理列表、功能表单资料选择器 |
| POST | `quill/resources/get` | 资料预览 |
| POST | `quill/resources/update` | 资料预览／编辑标题和标签 |
| POST | `quill/resources/delete` | 资料预览／删除或批量移除 |
| POST | `quill/resources/reindex` | 资料预览／重建索引 |
| GET | `quill/capabilities` | 各功能可用状态 |
| POST | `quill/resources/chunks` | 分块与分析／实际存储分块 |

## Runtime boundaries

- `resource-parse` was previously skipped because aiohttp was absent. The lightweight engine requirements now include it. Batch parsing accepts staged `/uploads/` references through Quill; it does not expose arbitrary server-side URL fetching or local paths.
- QA imports now persist the collection, resource ID, content ID, question/answer and summary before optional indexing. Missing embedding does not discard a valid pair. Partial failures are shown individually.
- Stored chunks come from RAGChunk for the deployed backend. Preview reading segments are explicitly separate. Empty storage does not invent indexed chunks.
- Resource-ID/content-ID compatibility is preserved for status/get/download operations. Collection removal clears dependent chunk records before the collection, and reports cleanup errors. Original files saved in either service can be downloaded through authenticated Quill routes.
- The seven advanced search modes are exposed. Semantic retrieval, graph expansion, graph retrieval and file answering report missing prerequisites explicitly. Image input is an uploaded data URL, never an arbitrary engine filesystem path. Actual VLM/visual-vector availability remains an engine execution check.
- Graph building requires both an enabled graph store and a configured engine LLM. Graph rendering has a relational diagram plus complete structured records. Controlled fixtures are labeled synthetic and only verify UI contracts; real graph/model quality remains unaccepted.
- Default collection model names are persisted metadata. Changing them does not reconfigure the global model provider or install parsers. Parser format declarations describe support, not proof that every optional parser is installed.
- Batch parsing task IDs are kept in the current browser session (last 20). Actual statuses live in the engine process and are lost on engine restart. There is no invented persistent task queue or cancellation capability.
- `document_progress.py` and `resource_chunks.py` are source modules that are not mounted in the current RAG router. Their standalone task cancellation/SSE and Milvus diagnostics are not usable backend APIs and are not advertised as working page actions. Batch task progress and stored chunks cover the mounted product capabilities. LLM administration/chat and health internals are outside the knowledge-content API scope.
- The workspace is still shared by one access key; metadata bindings are stored labels, not a new multi-user permission guarantee.

## UI integration and acceptance

This is an extension of the Reading Workbench documented in [DESIGN.md](../DESIGN.md) and its [sidecar](../.impeccable/design.json), following the [knowledge surface contract](../.impeccable/surfaces/frontend-src-views-knowledge-vue.md). `Knowledge.vue` keeps the collection, document and preview workflow. All seven knowledge tabs and 28 named task entries use Lucide line icons. Actions, notices, empty states and top-level tabs reuse the shared UI components and `ui.css`; the task stylesheet arranges those controls with existing semantic colors and type roles. The accepted direction seed (04518e4f), palette, type ramp and shared control geometry remain intact. No new visual identity or shipped raster asset was added.

`UiFilePicker.vue` adds a canonical native single-file control in `frontend/src/components/ui/`, with styles owned by `frontend/src/styles/ui.css`. Upload tasks and image queries share Chinese selection/replacement copy, selected filename and size, drag feedback and a visible focus ring. The native input retains its accessible name, accept restrictions, required validation and keyboard selection. Disabled fields reject drops; resetting the model clears the file input. Image format filters and the size limit remain caller configuration and validation. Its reusable contract is recorded in DESIGN.md, and the sidecar now contains 11 component specimens, including this file picker.

`KnowledgeTools.vue` pairs a 200px desktop task menu with a form capped at 820px. Compact number, selection and boolean fields share two columns; long text, files and resource lists span the form. At 1100px and below, task choices move above the form and wrap. At 600px and below, a native-button disclosure shows the current task and exposes a two-column task list; choosing a task closes the disclosure and focuses its h3. Form fields and submit actions stack at that width. These measurements describe the knowledge surface, not a new global layout rule.

Results prioritize readable prose, status and source context. Advanced retrieval presents source titles, excerpts, relevance and a preview action before optional response details. `KnowledgeResult.vue` translates known field/status labels and keeps opaque identifiers, hashes and debug metadata in a native “编号与补充信息” disclosure; vector arrays are omitted from the readable tree, while the separate raw-response disclosure retains the returned payload. The graph shows actual node/edge counts, labels each returned relationship and uses semantic ink/muted colors against the subtle surface. A surface-colored text stroke keeps relation names readable over edges; full structured records remain below the diagram. Returned coordinates take priority, with circular layout used when coordinates are unavailable. No graph data or model output is fabricated.

The first capability review returned **ship** for seven states at both 1440px and 390px. Its [14-capture report](../.impeccable/review/knowledge-features/capture-report.json) remains the earlier acceptance record. The full task polish review subsequently inspected all 16 originals across eight states at both widths: documents, empty upload, QA import, stored chunks, unavailable graph, metadata, advanced results and a synthetic graph. The [polish capture report](../.impeccable/review/knowledge-polish/capture-report.json) records no page errors or horizontal overflow. The reviewer’s selected-collection metadata contrast finding was corrected with the existing accent token (5.87:1), and the final correction verdict was **ship**. These images are local acceptance evidence, not product assets. Synthetic graph fixtures establish the display contract only; provider health, real model output and real graph quality remain unaccepted, and no paid model call was made.
