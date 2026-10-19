<template>
  <section class="knowledge-tools" :aria-label="groupTitle">
    <div v-if="loading" role="status" class="tools-loading">
      正在检查知识引擎功能…
    </div>
    <UiNotice v-if="error" :message="error" tone="error" />
    <UiButton v-if="!catalog && !loading" @click="loadCatalog"
      >重新检查功能</UiButton
    >
    <template v-if="catalog">
      <p class="tools-context">
        {{ groupDescription
        }}<span v-if="group === 'analysis'">
          当前向量库：{{ catalog.vector_backend }}。</span
        >
      </p>
      <div class="tools-layout">
        <nav
          class="tools-menu"
          :class="{ 'tools-menu--expanded': menuExpanded }"
          :aria-label="groupTitle + '操作'"
        >
          <UiButton
            class="tools-menu-trigger"
            :aria-label="'选择' + groupTitle + '操作'"
            :aria-expanded="menuExpanded"
            :aria-controls="'tasks-' + group"
            @click="menuExpanded = !menuExpanded"
            ><component :is="operationIcon(operationId)" :size="16" /><span>{{
              operation?.title || "选择操作"
            }}</span
            ><ChevronDown :size="16"
          /></UiButton>
          <div class="tools-menu-options" :id="'tasks-' + group">
            <button
              v-for="item in operations"
              :key="item.id"
              :aria-label="item.title"
              :aria-current="operationId === item.id ? 'true' : undefined"
              @click="selectOperation(item.id)"
            >
              <component
                :is="operationIcon(item.id)"
                :size="16"
                aria-hidden="true"
              /><span class="tools-menu-copy"
                ><span>{{ item.title }}</span
                ><small v-if="!item.available">需配置</small></span
              ><ChevronRight
                v-if="operationId === item.id"
                :size="14"
                class="tools-menu-current"
                aria-hidden="true"
              />
            </button>
          </div>
        </nav>
        <div v-if="operation" class="tools-detail">
          <header class="tools-heading">
            <h3 ref="operationHeading" tabindex="-1">{{ operation.title }}</h3>
            <p>{{ operation.description }}</p>
          </header>
          <UiNotice
            v-if="operation.reason"
            :message="operation.reason + ' 配置完成后，请重新检查配置。'"
            tone="warning"
          />
          <UiNotice v-if="choicesError" :message="choicesError" tone="error" />
          <div
            v-if="['qa-single', 'qa-batch'].includes(operationId)"
            class="inline-actions"
          >
            <UiButton
              size="compact"
              @click="
                downloadFile(
                  '/api/v1/knowledge/exports/qa-template?format=json',
                  'qa-template.json',
                )
              "
              ><Download :size="16" />JSON 导入模板</UiButton
            >
            <UiButton
              size="compact"
              @click="
                downloadFile(
                  '/api/v1/knowledge/exports/qa-template?format=csv',
                  'qa-template.csv',
                )
              "
              >CSV 导入模板</UiButton
            >
          </div>
          <p v-if="settingsLoading" role="status" class="tools-help">
            正在读取现有设置…
          </p>
          <form :key="operationId" @submit.prevent="execute">
            <fieldset :disabled="busy || settingsLoading" class="tools-fields">
              <div
                v-if="operation.encoding === 'file'"
                class="field-label tools-field-wide"
              >
                选择文件<UiFilePicker
                  :key="operationId"
                  v-model="file"
                  label="选择文件"
                  required
                  :accept="
                    operationId === 'qa-batch' ? '.json,.csv' : undefined
                  "
                  :hint="
                    operationId === 'qa-batch'
                      ? '支持 JSON 或 CSV 问答文件。'
                      : '支持格式可在“解析格式与限制”中查看。'
                  "
                />
              </div>
              <template v-for="field in operation.fields" :key="field.key">
                <label
                  v-if="!field.advanced && field.kind !== 'collection'"
                  class="field-label"
                  :class="{
                    'tools-check': field.kind === 'boolean',
                    'tools-field-wide': ![
                      'number',
                      'select',
                      'boolean',
                    ].includes(field.kind),
                  }"
                >
                  <span
                    >{{ field.label
                    }}<small v-if="field.required">（必填）</small></span
                  >
                  <input
                    v-if="field.kind === 'boolean'"
                    type="checkbox"
                    v-model="values[field.key]"
                  />
                  <select
                    v-else-if="field.kind === 'select'"
                    :aria-label="
                      field.label + (field.required ? '（必填）' : '')
                    "
                    class="field-input"
                    v-model="values[field.key]"
                  >
                    <option
                      v-for="choice in field.options"
                      :key="choice[0]"
                      :value="choice[0]"
                    >
                      {{ choice[1] }}
                    </option>
                  </select>
                  <select
                    v-else-if="
                      ['resource', 'content', 'resources'].includes(field.kind)
                    "
                    class="field-input"
                    :aria-label="
                      field.label + (field.required ? '（必填）' : '')
                    "
                    :multiple="field.kind === 'resources'"
                    :size="field.kind === 'resources' ? 5 : undefined"
                    v-model="values[field.key]"
                    :required="field.required"
                  >
                    <option v-if="field.kind !== 'resources'" value="">
                      请选择资料
                    </option>
                    <option
                      v-for="item in choices"
                      :key="item.resource_id"
                      :value="
                        field.kind === 'content'
                          ? item.content_id
                          : item.resource_id
                      "
                    >
                      {{ item.title
                      }}{{ item.enabled === false ? "（已停用）" : "" }}
                    </option>
                  </select>
                  <UiFilePicker
                    v-else-if="field.kind === 'image'"
                    :model-value="imageFiles[field.key]"
                    :label="field.label"
                    accept="image/png,image/jpeg,image/webp,image/gif"
                    hint="PNG、JPEG、WebP 或 GIF，最大 2 MB。"
                    @update:model-value="imageChosen($event, field.key)"
                  />
                  <textarea
                    v-else-if="
                      ['textarea', 'lines', 'json', 'json-string'].includes(
                        field.kind,
                      )
                    "
                    class="field-input"
                    rows="4"
                    v-model="values[field.key]"
                    :required="field.required"
                    :placeholder="field.placeholder"
                  />
                  <input
                    v-else
                    class="field-input"
                    :type="field.kind === 'number' ? 'number' : 'text'"
                    v-model="values[field.key]"
                    :required="field.required"
                    :min="field.min"
                    :max="field.max"
                    :step="
                      field.step || (field.kind === 'number' ? 1 : undefined)
                    "
                    :placeholder="field.placeholder"
                  />
                </label>
              </template>
              <details
                v-if="operation.fields.some((f) => f.advanced)"
                class="tools-advanced tools-field-wide"
              >
                <summary>更多选项</summary>
                <div class="tools-fields">
                  <label
                    v-for="field in operation.fields.filter((f) => f.advanced)"
                    :key="field.key"
                    class="field-label"
                    :class="{
                      'tools-check': field.kind === 'boolean',
                      'tools-field-wide': ![
                        'number',
                        'select',
                        'boolean',
                      ].includes(field.kind),
                    }"
                    ><span>{{ field.label }}</span>
                    <input
                      v-if="field.kind === 'boolean'"
                      type="checkbox"
                      v-model="values[field.key]"
                    />
                    <textarea
                      v-else-if="
                        ['json', 'json-string', 'lines'].includes(field.kind)
                      "
                      class="field-input"
                      rows="3"
                      v-model="values[field.key]"
                    />
                    <input
                      v-else
                      class="field-input"
                      :type="field.kind === 'number' ? 'number' : 'text'"
                      v-model="values[field.key]"
                      :min="field.min"
                      :max="field.max"
                      :step="field.step || 1"
                    />
                  </label>
                </div>
              </details>
              <label
                v-if="operation.destructive"
                class="field-label tools-field-wide"
                >输入“{{ collection.name }}”确认删除<input
                  v-model="confirmation"
                  class="field-input"
                  required
                  autocomplete="off"
              /></label>
              <p
                v-if="
                  operation.fields.some((f) =>
                    ['resource', 'content', 'resources'].includes(f.kind),
                  )
                "
                class="tools-help tools-field-wide"
              >
                资料选择器支持按名称键入定位；多选可使用 ⌘ / Ctrl 或 Shift。{{
                  choices.length
                }}
                份资料可选。
              </p>
              <div class="inline-actions tools-actions tools-field-wide">
                <UiButton
                  type="submit"
                  :variant="operation.destructive ? 'danger' : 'primary'"
                  :disabled="
                    !operation.available ||
                    choicesLoading ||
                    (operation.destructive && confirmation !== collection.name)
                  "
                  ><LoaderCircle v-if="busy" :size="16" class="spin" />{{
                    busy ? "处理中…" : operation.title
                  }}</UiButton
                ><UiButton v-if="!operation.available" @click="loadCatalog"
                  >重新检查配置</UiButton
                >
              </div>
            </fieldset>
          </form>
          <section
            v-if="operationId === 'batch-status' && recentTasks.length"
            class="tools-task-history"
            aria-label="最近的解析任务"
          >
            <h3>最近提交的任务</h3>
            <ul>
              <li
                v-for="task in recentTasks.filter(
                  (t) => t.collection === collection.id,
                )"
                :key="task.id"
              >
                <UiButton
                  size="compact"
                  variant="text"
                  @click="values.batch_id = task.id"
                  >{{ task.id }}</UiButton
                ><time>{{ new Date(task.time).toLocaleString("zh-CN") }}</time>
              </li>
            </ul>
          </section>
          <section
            v-if="result !== null"
            class="tools-result"
            aria-label="操作结果"
            aria-live="polite"
          >
            <header>
              <h3>操作结果</h3>
              <UiButton size="compact" variant="ghost" @click="result = null"
                >清除结果</UiButton
              >
            </header>
            <UiNotice
              v-if="result.message"
              :message="result.message"
              :tone="partialFailure ? 'warning' : 'success'"
            />
            <div v-if="uploadedUrl" class="tools-followup">
              <p>文件已上传，可继续解析。</p>
              <UiButton size="compact" :disabled="busy" @click="useUploaded"
                >解析此文件</UiButton
              >
            </div>
            <div v-if="batchId" class="tools-followup">
              <p>解析任务编号：{{ batchId }}</p>
              <UiButton size="compact" :disabled="busy" @click="useBatch"
                >查看任务进度</UiButton
              >
            </div>
            <div v-if="graph.nodes.length" class="tools-graph">
              <p class="tools-graph-summary">
                {{ graph.nodes.length }} 个实体 ·
                {{ graph.edges.length }} 条关系
              </p>
              <svg viewBox="0 0 360 260" role="img" aria-label="实体关系网络">
                <g v-for="(edge, i) in graph.edges" :key="'e' + i">
                  <line
                    :x1="nodePosition(edge.source).x"
                    :y1="nodePosition(edge.source).y"
                    :x2="nodePosition(edge.target).x"
                    :y2="nodePosition(edge.target).y"
                    stroke="var(--muted)"
                    stroke-width="1.25"
                  />
                  <text
                    v-if="edge.relation || edge.label || edge.type"
                    :x="
                      (nodePosition(edge.source).x +
                        nodePosition(edge.target).x) /
                      2
                    "
                    :y="
                      (nodePosition(edge.source).y +
                        nodePosition(edge.target).y) /
                        2 -
                      7
                    "
                    text-anchor="middle"
                    class="tools-graph-relation"
                  >
                    {{ edge.relation || edge.label || edge.type }}
                  </text>
                </g>
                <g
                  v-for="(node, i) in graph.nodes"
                  :key="'n' + i"
                  :transform="`translate(${nodePosition(node.id || node.name).x},${nodePosition(node.id || node.name).y})`"
                >
                  <circle r="8" fill="var(--accent)" />
                  <text
                    y="23"
                    text-anchor="middle"
                    fill="var(--ink)"
                    font-size="12"
                  >
                    {{
                      (node.name || node.label || node.id || "").slice(0, 16)
                    }}
                  </text>
                </g>
              </svg>
              <p>
                实体与关系明细见下方；优先使用图谱返回的位置；无坐标时按环形排布。
              </p>
            </div>
            <template v-if="operationId === 'advanced-search'">
              <p v-if="result.answer" class="result-prose">
                {{ result.answer }}
              </p>
              <p class="tools-search-count">
                找到 {{ result.results?.length || 0 }} 条结果
              </p>
              <UiEmptyState
                v-if="!result.results?.length"
                title="没有找到相关资料"
                description="调整关键词、资料范围或相似度阈值后重试。"
                compact
                heading="h4"
              />
              <ol v-else class="tools-search-results">
                <li
                  v-for="(item, index) in result.results"
                  :key="item.resource_id || item.content_id || index"
                >
                  <h4>
                    {{ item.title || item.metadata?.file_name || "未命名资料" }}
                  </h4>
                  <p class="result-prose">
                    {{ item.content || item.snippet || "暂无文字内容" }}
                  </p>
                  <div class="tools-search-source">
                    <span v-if="item.similarity_score != null"
                      >相关性
                      {{ Number(item.similarity_score).toFixed(2) }}</span
                    ><UiButton
                      v-if="item.resource_id"
                      size="compact"
                      variant="text"
                      @click="emit('preview', item.resource_id)"
                      >预览来源</UiButton
                    >
                  </div>
                </li>
              </ol>
              <details v-if="result.citations?.length" class="tools-raw">
                <summary>来源引用</summary>
                <KnowledgeResult :value="result.citations" />
              </details>
            </template>
            <KnowledgeResult
              v-else
              :value="result.result ?? result.data ?? result"
            />
            <details class="tools-raw">
              <summary>原始结果</summary>
              <pre>{{ JSON.stringify(result, null, 2) }}</pre>
            </details>
          </section>
        </div>
      </div>
    </template>
  </section>
</template>
<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import {
  BarChart3,
  BookOpen,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  Download,
  FileText,
  FileUp,
  FolderOpen,
  GitBranch,
  Layers3,
  LoaderCircle,
  MessageSquare,
  Network,
  Pencil,
  RefreshCw,
  ScanText,
  Search,
  Settings2,
  Sparkles,
  ToggleLeft,
  Trash2,
} from "@lucide/vue";
import UiButton from "../ui/UiButton.vue";
import UiFilePicker from "../ui/UiFilePicker.vue";
import UiNotice from "../ui/UiNotice.vue";
import UiEmptyState from "../ui/UiEmptyState.vue";
import KnowledgeResult from "./KnowledgeResult.vue";
import { api, downloadFile, handleError } from "../../api/client";
import "../../styles/knowledge-tools.css";
const props = defineProps({
  group: String,
  collection: Object,
  selectedResources: { type: Array, default: () => [] },
});
const emit = defineEmits(["changed", "preview"]);
const menuExpanded = ref(false),
  operationHeading = ref(null),
  imageFiles = ref({});
const taskIcons = {
  upload: FileUp,
  process: FileText,
  "process-upload": BookOpen,
  "batch-parse": FolderOpen,
  "batch-status": ClipboardList,
  markdown: FileText,
  "qa-single": MessageSquare,
  "qa-batch": MessageSquare,
  formats: CircleHelp,
  strategies: Layers3,
  chunks: Layers3,
  analyze: Sparkles,
  "analysis-result": ClipboardList,
  reindex: RefreshCw,
  status: ToggleLeft,
  metadata: Pencil,
  "collection-detail": Settings2,
  "collection-update": Settings2,
  "collection-delete": Trash2,
  "advanced-search": Search,
  "search-methods": CircleHelp,
  "graph-query": Search,
  "graph-view": Network,
  "graph-extract": ScanText,
  "graph-build": Network,
  "graph-entities": Layers3,
  "graph-association": GitBranch,
  "graph-statistics": BarChart3,
};
function operationIcon(id) {
  return taskIcons[id] || FileText;
}
function selectOperation(id) {
  operationId.value = id;
  menuExpanded.value = false;
  if (window.innerWidth <= 600) nextTick(() => operationHeading.value?.focus());
}

const catalog = ref(null),
  loading = ref(false),
  error = ref(""),
  operationId = ref(""),
  values = ref({}),
  file = ref(null),
  busy = ref(false),
  result = ref(null),
  confirmation = ref(""),
  choices = ref([]),
  choicesLoading = ref(false),
  choicesError = ref(""),
  settingsLoading = ref(false);
const groupTitle = computed(
  () =>
    ({
      import: "导入与解析",
      analysis: "分块与分析",
      graph: "知识图谱",
      settings: "知识库设置",
      search: "高级检索",
    })[props.group],
);
const groupDescription = computed(
  () =>
    ({
      import: "将文件或问答对整理入库，并跟踪解析任务。",
      analysis: "查看实际分块，生成摘要标签，维护向量索引。",
      graph: "抽取、浏览实体关系，并检查图谱统计。",
      settings: "维护资料状态、完整元数据及知识库配置。",
      search: "按资料、图片、实体或引用要求查找内容。",
    })[props.group],
);
const operations = computed(() =>
  (catalog.value?.operations || []).filter((o) => o.group === props.group),
);
const operation = computed(() =>
  operations.value.find((o) => o.id === operationId.value),
);
const partialFailure = computed(() =>
  Boolean(
    result.value?.result?.failed ||
    result.value?.result?.failed_count ||
    result.value?.result?.failed_documents_count,
  ),
);
const uploadedUrl = computed(() =>
  operationId.value === "upload"
    ? result.value?.url || result.value?.result?.url
    : "",
);
const batchId = computed(() =>
  operationId.value === "batch-parse"
    ? result.value?.result?.batch_id || result.value?.batch_id
    : "",
);
const graph = computed(() => {
  const body = result.value?.result || result.value?.data || result.value || {};
  return {
    nodes: body.nodes || body.graph?.nodes || [],
    edges: body.edges || body.links || body.graph?.edges || [],
  };
});
function nodePosition(id) {
  const nodes = graph.value.nodes;
  const index = nodes.findIndex(
    (node) => String(node.id || node.name) === String(id?.id || id),
  );
  const node = nodes[Math.max(index, 0)];
  if (
    node &&
    nodes.every((n) => Number.isFinite(n.x) && Number.isFinite(n.y))
  ) {
    const xs = nodes.map((n) => n.x),
      ys = nodes.map((n) => n.y);
    const minX = Math.min(...xs),
      minY = Math.min(...ys);
    return {
      x: 40 + ((node.x - minX) / (Math.max(...xs) - minX || 1)) * 280,
      y: 35 + ((node.y - minY) / (Math.max(...ys) - minY || 1)) * 170,
    };
  }
  const angle = (Math.max(index, 0) / Math.max(nodes.length, 1)) * Math.PI * 2;
  return { x: 180 + Math.cos(angle) * 120, y: 115 + Math.sin(angle) * 80 };
}
let sequence = 0,
  choiceSequence = 0;
const recentTasks = ref(readTasks());
function readTasks() {
  try {
    return JSON.parse(sessionStorage.getItem("quill-parse-tasks") || "[]");
  } catch {
    return [];
  }
}

async function loadCatalog() {
  loading.value = true;
  error.value = "";
  try {
    catalog.value = (await api.get("/api/v1/knowledge/capabilities")).data;
    if (!operation.value) operationId.value = operations.value[0]?.id || "";
  } catch (e) {
    error.value = handleError(e);
  } finally {
    loading.value = false;
  }
}
async function loadChoices() {
  const seq = ++choiceSequence;
  choicesLoading.value = true;
  choicesError.value = "";
  try {
    let items = [];
    for (let page = 0; page < 10; page++) {
      const r = (
        await api.get("/api/v1/knowledge/resources", {
          params: { collection_id: props.collection.id, page, size: 100 },
        })
      ).data;
      items.push(...r.items);
      if (r.items.length < 100) break;
      if (page === 9 && r.total > 1000)
        throw Error("当前资料超过 1000 份，请在资料列表选择目标后执行操作。");
    }
    if (seq === choiceSequence) choices.value = items;
  } catch (e) {
    if (seq === choiceSequence) {
      choices.value = [];
      choicesError.value = handleError(e);
    }
  } finally {
    if (seq === choiceSequence) choicesLoading.value = false;
  }
}
async function loadSettings() {
  if (operationId.value !== "collection-update") return;
  const seq = sequence;
  settingsLoading.value = true;
  try {
    const r = (
      await api.post("/api/v1/knowledge/operations/collection-detail", {
        collection_id: props.collection.id,
      })
    ).data.result;
    if (seq === sequence)
      for (const key of [
        "name",
        "description",
        "collection_type",
        "embedding_model",
        "rerank_model",
      ])
        values.value[key] = r[key] ?? "";
  } catch (e) {
    if (seq === sequence) error.value = handleError(e);
  } finally {
    settingsLoading.value = false;
  }
}
function reset() {
  sequence++;
  result.value = null;
  error.value = "";
  file.value = null;
  imageFiles.value = {};
  menuExpanded.value = false;
  confirmation.value = "";
  const v = {};
  for (const f of operation.value?.fields || []) {
    let x = f.default;
    if (f.kind === "collection") x = props.collection.id;
    else if (f.key === "name" && operationId.value === "collection-update")
      x = props.collection.name;
    else if (
      f.key === "description" &&
      operationId.value === "collection-update"
    )
      x = props.collection.description;
    else if (f.kind === "resources") x = [...props.selectedResources];
    else if (["lines"].includes(f.kind)) x = (x || []).join("\n");
    else if (["json", "json-string"].includes(f.kind))
      x = JSON.stringify(x ?? {}, null, 2);
    v[f.key] = x ?? "";
  }
  values.value = v;
}
async function imageChosen(image, key) {
  values.value[key] = "";
  imageFiles.value[key] = null;
  if (!image) return;
  if (image.size > 2 * 1024 * 1024) {
    error.value = "查询图片不能超过 2 MB。";
    return;
  }
  imageFiles.value[key] = image;
  const seq = sequence,
    reader = new FileReader();
  reader.onload = () => {
    if (sequence === seq && imageFiles.value[key] === image)
      values.value[key] = reader.result;
  };
  reader.readAsDataURL(image);
}
async function execute() {
  const seq = sequence;
  busy.value = true;
  error.value = "";
  result.value = null;
  try {
    const payload = {};
    for (const f of operation.value.fields) {
      let v = values.value[f.key];
      if (f.kind === "number" && v !== "") v = Number(v);
      if (f.kind === "lines")
        v = String(v || "")
          .split("\n")
          .map((v) => v.trim())
          .filter(Boolean);
      if (["json", "json-string"].includes(f.kind)) {
        try {
          const parsed = JSON.parse(v || "{}");
          v = f.kind === "json" ? parsed : JSON.stringify(parsed);
        } catch {
          throw Error(f.label + "不是有效的 JSON。");
        }
      }
      if (
        v !== undefined &&
        v !== null &&
        (v !== "" ||
          operationId.value === "collection-update" ||
          (operationId.value === "metadata" && f.key === "description"))
      )
        payload[f.key] = v;
    }
    if (operation.value.destructive)
      payload.confirmed = confirmation.value === props.collection.name;
    const id = operationId.value;
    let response;
    if (operation.value.encoding === "file") {
      if (!file.value) throw Error("请选择文件。");
      const form = new FormData();
      form.append("file", file.value);
      form.append("fields", JSON.stringify(payload));
      response = await api.post("/api/v1/knowledge/uploads/" + id, form, {
        timeout: 180000,
      });
    } else
      response = await api.post("/api/v1/knowledge/operations/" + id, payload, {
        timeout: 180000,
      });
    if (seq === sequence) result.value = response.data;
    if (id === "batch-parse") {
      const batch = response.data.result?.batch_id;
      if (batch) {
        recentTasks.value = [
          { id: batch, collection: payload.collection_id, time: Date.now() },
          ...recentTasks.value,
        ].slice(0, 20);
        sessionStorage.setItem(
          "quill-parse-tasks",
          JSON.stringify(recentTasks.value),
        );
      }
    }

    if (
      ![
        "formats",
        "strategies",
        "chunks",
        "analysis-result",
        "graph-query",
        "graph-view",
        "graph-entities",
        "graph-association",
        "graph-statistics",
        "search-methods",
        "advanced-search",
        "collection-detail",
        "batch-status",
        "markdown",
        "upload",
      ].includes(id)
    ) {
      emit("changed");
      await loadChoices();
    }
  } catch (e) {
    if (seq === sequence) error.value = handleError(e);
  } finally {
    busy.value = false;
  }
}
function useUploaded() {
  const url = uploadedUrl.value;
  operationId.value = "process-upload";
  values.value.url = url;
}
function useBatch() {
  const id = batchId.value;
  operationId.value = "batch-status";
  values.value.batch_id = id;
}
watch(
  () => values.value.id,
  async (id) => {
    if (operationId.value !== "metadata" || !id) return;
    const item = choices.value.find((item) => item.content_id === id);
    if (!item) return;
    const seq = sequence;
    settingsLoading.value = true;
    try {
      const detail = (
        await api.get("/api/v1/knowledge/resources/" + item.resource_id)
      ).data;
      if (seq !== sequence || values.value.id !== id) return;
      values.value.name = detail.title;
      values.value.description = detail.description || "";
      values.value.tags = (detail.tags || []).join("\n");
      values.value.bindings = (detail.bindings || []).join("\n");
      values.value.relation = JSON.stringify(detail.relation || [], null, 2);
    } catch (e) {
      if (seq === sequence) error.value = handleError(e);
    } finally {
      settingsLoading.value = false;
    }
  },
);
watch(
  operationId,
  () => {
    reset();
    loadSettings();
  },
  { flush: "sync" },
);
watch(
  () => props.group,
  () => {
    operationId.value = operations.value[0]?.id || "";
  },
);
watch(
  () => props.collection.id,
  () => {
    reset();
    loadSettings();
    loadChoices();
  },
);
onMounted(() => {
  loadCatalog();
  loadChoices();
});
</script>
