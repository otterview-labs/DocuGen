<template>
  <section class="document-workspace create-page">
    <UiPageHeader
      title="上传模板"
      description="从常用模板开始，或导入自己的 Word，保留版式生成新文档。"
    >
      <template #actions
        ><UiButton href="#create-upload-heading" @click.prevent="focusUpload"
          ><Upload />导入 Word</UiButton
        ><UiButton to="/templates"><ArrowLeft />返回模板库</UiButton></template
      >
    </UiPageHeader>

    <div class="create-intake">
      <section
        class="create-template-options"
        aria-labelledby="create-existing-heading"
      >
        <div class="create-gallery-heading">
          <div>
            <h2 id="create-existing-heading">使用已有模板</h2>
            <p>选择适合的文档，查看版式，再填入你的内容。</p>
          </div>
          <UiButton
            :to="{ path: '/templates', query: { source: 'builtin' } }"
            variant="text"
            >浏览内置模板<span v-if="library.length"
              >（{{ library.length }}）</span
            ><ArrowRight
          /></UiButton>
        </div>
        <UiNotice v-if="libraryError" tone="error"
          >{{ libraryError }}
          <UiButton variant="text" @click="loadLibrary"
            >重新加载</UiButton
          ></UiNotice
        >
        <UiNotice
          v-if="libraryActionError"
          tone="error"
          :message="libraryActionError"
        />
        <ul
          v-if="!libraryError"
          class="create-starter-list"
          :aria-busy="loadingLibrary"
        >
          <li v-for="template in suggestedTemplates" :key="template.id">
            <RouterLink
              class="create-starter-preview"
              :aria-label="'预览' + template.name"
              :to="{
                path: '/templates',
                query: { source: 'builtin', q: template.name },
              }"
              ><TemplateCover :template="template" decorative /><strong>{{
                template.name
              }}</strong></RouterLink
            >
            <div class="create-starter-meta">
              <span
                >{{ template.category }} ·
                {{ template.variables.length }} 个变量</span
              ><UiButton
                variant="text"
                size="compact"
                :aria-label="'使用' + template.name"
                :disabled="!!usingStarter"
                @click="prepareStarter(template)"
                >{{ usingStarter === template.id ? "准备中…" : "使用模板"
                }}<ArrowRight
              /></UiButton>
            </div>
          </li>
          <li v-if="loadingLibrary" class="create-starter-loading">
            正在读取模板…
          </li>
          <li
            v-else-if="!suggestedTemplates.length"
            class="create-starter-loading"
          >
            当前没有内置模板，可导入 Word 文件继续。
          </li>
        </ul>
        <div class="create-workspace-templates">
          <label class="field-label" for="selected-template">选择模板</label>
          <div class="template-select-row">
            <select
              id="selected-template"
              v-model="selectedTemplateName"
              class="field-input"
              @change="handleTemplateChange"
            >
              <option disabled value="">继续使用工作区中的模板…</option>
              <option
                v-for="template in templates"
                :key="template.name"
                :value="template.name"
              >
                {{ template.name }}
              </option></select
            ><UiButton
              aria-label="重新加载模板"
              :disabled="loadingTemplates"
              @click="loadTemplates"
              variant="ghost"
              icon-only
              ><RefreshCw :class="{ spin: loadingTemplates }" /></UiButton
            ><UiButton
              :disabled="!selectedTemplateName || loadingVars"
              @click="loadVariables({ refresh: true })"
              aria-label="提取变量"
              icon-only
              ><ScanText
            /></UiButton>
          </div>
          <span>已有模板可直接继续填写</span>
        </div>
      </section>
      <section
        class="create-upload-panel"
        aria-labelledby="create-upload-heading"
      >
        <div class="create-section-title">
          <div>
            <h2 id="create-upload-heading">导入你的 Word 模板</h2>
            <p>已有固定格式？上传后自动识别可填写的内容。</p>
          </div>
          <span class="document-tag">DOCX</span>
        </div>
        <label
          class="template-upload-drop ui-upload"
          :class="{ dragging, 'has-file': uploadFile }"
          for="template-upload"
          @dragover.prevent="dragging = true"
          @dragleave="dragging = false"
          @drop.prevent="dropTemplate"
        >
          <input
            id="template-upload"
            ref="uploadInput"
            class="sr-only"
            type="file"
            accept=".docx"
            :disabled="uploading"
            @change="handleFileSelect"
          />
          <FileText v-if="uploadFile" aria-hidden="true" /><Upload
            v-else
            aria-hidden="true"
          />
          <strong>{{
            uploadFile ? uploadFile.name : "点击选择，或将 Word 文件拖到这里"
          }}</strong>
          <span>{{
            uploadFile
              ? formatBytes(uploadFile.size) + " · 点击可更换文件"
              : "支持 .docx · 保留标题、表格、页眉与页脚"
          }}</span>
        </label>
        <div class="create-template-details">
          <label class="field-label" for="upload-name"
            >模板名称<input
              id="upload-name"
              v-model="uploadName"
              class="field-input"
              maxlength="100"
              placeholder="模板名称（可选，默认用文件名）"
          /></label>
          <div>
            <label class="field-label" for="upload-category">模板分类</label>
            <select
              id="upload-category"
              v-model="uploadCategory"
              class="field-input"
            >
              <option v-for="category in uploadCategories" :key="category">
                {{ category }}
              </option>
            </select>
          </div>
          <label class="field-label create-template-description"
            >模板说明<input
              v-model="uploadDescription"
              class="field-input"
              maxlength="500"
              placeholder="用途、适用场景或填写提示（可选）"
          /></label>
        </div>
        <div class="create-upload-footer">
          <span
            ><ScanText />自动提取 <code>【变量】</code> 和
            <code v-pre>{{ 变量 }}</code></span
          ><UiButton
            :disabled="uploading || !uploadFile"
            variant="primary"
            @click="handleUpload"
            ><LoaderCircle v-if="uploading" class="spin" /><Upload v-else />{{
              uploading ? "上传中…" : "上传并入库"
            }}</UiButton
          >
        </div>
      </section>
    </div>

    <UiNotice v-if="status" :message="status" class="create-status" />
    <div
      v-if="selectedTemplateName || loadingVars"
      class="create-variable-layout"
    >
      <section
        class="editor-section create-variable-panel"
        aria-labelledby="create-variables-heading"
      >
        <div class="editor-section-heading">
          <div>
            <h2 id="create-variables-heading">
              填写文档内容
              <span class="document-count">{{ variables.length }} 个变量</span>
            </h2>
            <p>
              {{
                selectedTemplateName
                  ? "当前模板：" + selectedTemplateName
                  : "准备好模板后，在这里填写内容。"
              }}
            </p>
          </div>
          <div class="inline-actions">
            <UiButton
              :disabled="aiFilling || !variables.length"
              @click="aiFill"
              size="compact"
              ><LoaderCircle v-if="aiFilling" class="spin" /><Sparkles
                v-else
              />AI 填充</UiButton
            ><UiButton
              :disabled="!variables.length"
              @click="clearValues"
              variant="text"
              >清空</UiButton
            >
          </div>
        </div>
        <details class="reference-disclosure">
          <summary>
            <BookOpen :size="16" />参考内容（可选）<ChevronDown :size="16" />
          </summary>
          <label class="field-label" for="upload-reference"
            >手动参考资料<textarea
              id="upload-reference"
              v-model="customRagContent"
              class="field-input"
              rows="4"
              placeholder="没有知识库时可手动粘贴参考内容，AI 填充会优先参考"
            />
          </label>
          <p>仅在 AI 填充时使用，生成结果仍需核对。</p>
        </details>
        <UiEmptyState
          v-if="loadingVars"
          :icon="LoaderCircle"
          description="正在提取变量…"
          state="loading"
          compact
        />
        <UiEmptyState
          v-else-if="!variables.length"
          :icon="TextCursorInput"
          title="先准备一份模板"
          description="上传 Word 或选择已有模板后，可填写的变量会显示在这里。"
          compact
        />
        <div v-else class="variables-grid">
          <label
            v-for="(variable, index) in variables"
            :key="variable.name"
            class="field-label"
            :for="`var-${index}`"
            >{{ variable.name
            }}<textarea
              :id="`var-${index}`"
              v-model="values[variable.name]"
              class="field-input"
              :placeholder="variable.description || '请输入内容'"
              rows="3"
            />
          </label>
        </div>
      </section>
      <aside class="create-export-panel" aria-label="生成文档">
        <div class="editor-aside-title">
          <FileCheck2 />
          <h2>准备导出</h2>
        </div>
        <p class="editor-help">核对填写内容，生成沿用模板版式的 Word 文档。</p>
        <dl class="document-summary">
          <dt>当前模板</dt>
          <dd>{{ selectedTemplateName || "尚未选择" }}</dd>
          <dt>内容已填</dt>
          <dd>{{ completedVariables }} / {{ variables.length }}</dd>
          <dt>导出格式</dt>
          <dd>Word · DOCX</dd>
        </dl>
        <UiButton
          :disabled="generating || !variables.length"
          @click="generateDoc"
          class="full-width"
          variant="primary"
          ><LoaderCircle v-if="generating" class="spin" /><FileOutput
            v-else
          />{{ generating ? "生成中…" : "生成文档" }}</UiButton
        >
        <div v-if="downloadUrl" class="document-download">
          <CheckCircle2 /><strong>文档已生成</strong>
          <p>下载后请核对内容与排版。</p>
          <UiButton @click="downloadFile(downloadUrl)"
            ><Download />下载 Word</UiButton
          >
        </div>
        <p class="create-export-note">
          <ShieldCheck />手动填写与导出无需模型。AI 填充使用已配置的生成模型。
        </p>
      </aside>
    </div>
    <p v-else class="create-start-hint">
      <Info :size="16" />准备好模板后，可继续填写内容并导出 Word 文档。
    </p>
  </section>
</template>
<script setup>
import "../styles/create.css";
import TemplateCover from "../components/TemplateCover.vue";
import UiNotice from "../components/ui/UiNotice.vue";
import UiEmptyState from "../components/ui/UiEmptyState.vue";
import UiPageHeader from "../components/ui/UiPageHeader.vue";
import UiButton from "../components/ui/UiButton.vue";
import { RouterLink, useRouter } from "vue-router";
import {
  ArrowRight,
  ShieldCheck,
  FileText,
  Info,
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  Download,
  FileCheck2,
  FileOutput,
  LoaderCircle,
  RefreshCw,
  ScanText,
  Sparkles,
  TextCursorInput,
  Upload,
} from "@lucide/vue";

import { downloadFile } from "../api/client";
import { computed, onMounted, reactive, ref } from "vue";
import {
  fetchTemplates,
  fetchTemplateLibrary,
  useLibraryTemplate,
  fetchTemplateVariables,
  aiFillVariables,
  generateFromTemplate,
  uploadTemplate,
} from "../api/templates";

const router = useRouter();
function focusUpload() {
  document
    .getElementById("create-upload-heading")
    ?.scrollIntoView({ block: "center", behavior: "instant" });
  uploadInput.value?.focus({ preventScroll: true });
}
const usingStarter = ref(""),
  libraryActionError = ref("");
async function prepareStarter(template) {
  usingStarter.value = template.id;
  libraryActionError.value = "";
  const { data, error } = await useLibraryTemplate(template.id);
  usingStarter.value = "";
  if (error) {
    libraryActionError.value = error;
    return;
  }
  await router.push({ name: "generate", params: { templateId: data.name } });
}
const library = ref([]),
  loadingLibrary = ref(true),
  libraryError = ref("");
const suggestedTemplates = computed(() =>
  ["project-plan", "acceptance-report", "weekly-report", "meeting-minutes"]
    .map((id) => library.value.find((template) => template.id === id))
    .filter(Boolean),
);
async function loadLibrary() {
  loadingLibrary.value = true;
  const { data, error } = await fetchTemplateLibrary();
  library.value = data || [];
  libraryError.value = error || "";
  loadingLibrary.value = false;
}
const dragging = ref(false);
const completedVariables = computed(
  () =>
    variables.value.filter((variable) =>
      String(values[variable.name] || "").trim(),
    ).length,
);
function formatBytes(size) {
  return size < 1048576
    ? (size / 1024).toFixed(1) + " KB"
    : (size / 1048576).toFixed(1) + " MB";
}
function dropTemplate(event) {
  dragging.value = false;
  if (uploading.value) return;
  handleFileSelect({ target: { files: event.dataTransfer.files } });
}
const templates = ref([]);
const loadingTemplates = ref(false);
const selectedTemplateName = ref("");
const variables = ref([]);
const lastSources = ref([]);
const values = reactive({});
const loadingVars = ref(false);
const aiFilling = ref(false);
const generating = ref(false);
const status = ref("");
const downloadUrl = ref("");
const customRagContent = ref("");

const uploadInput = ref(null);
const uploadFile = ref(null);
const uploadName = ref("");
const uploadCategory = ref("通用");
const uploadDescription = ref("");
const uploadCategories = [
  "通用",
  "报告",
  "合同",
  "简历",
  "招投标",
  "方案",
  "函件",
  "其他",
];
const uploading = ref(false);

const currentTemplate = computed(
  () =>
    templates.value.find((t) => t.name === selectedTemplateName.value) || null,
);

onMounted(async () => {
  await Promise.all([loadTemplates(), loadLibrary()]);
});

async function loadTemplates() {
  loadingTemplates.value = true;
  try {
    const { data, error } = await fetchTemplates();
    if (error) {
      status.value = `加载模板失败：${error}`;
      templates.value = [];
      return;
    }
    templates.value = data || [];
  } finally {
    loadingTemplates.value = false;
  }
}

function handleTemplateChange() {
  loadVariables();
}

function resetValues(varList, preserve = false) {
  const previous = preserve ? { ...values } : {};
  Object.keys(values).forEach((k) => delete values[k]);
  (varList || []).forEach((v) => {
    values[v.name] = Object.hasOwn(previous, v.name)
      ? previous[v.name]
      : v.default_value || "";
  });
}

async function loadVariables({ refresh = false } = {}) {
  if (!selectedTemplateName.value) return;
  loadingVars.value = true;
  status.value = "";
  if (!refresh) {
    downloadUrl.value = "";
    lastSources.value = [];
  }
  try {
    // 优先使用元数据附带变量
    if (!refresh && currentTemplate.value?.variables?.length) {
      variables.value = currentTemplate.value.variables;
      resetValues(variables.value);
    } else {
      const { data, error } = await fetchTemplateVariables(
        selectedTemplateName.value,
        { refresh },
      );
      if (error) {
        status.value = `提取变量失败：${error}`;
        if (!refresh) variables.value = [];
      } else {
        variables.value = data || [];
        resetValues(variables.value, refresh);
        if (currentTemplate.value)
          currentTemplate.value.variables = variables.value;
      }
    }
  } finally {
    loadingVars.value = false;
  }
}

async function aiFill() {
  if (!selectedTemplateName.value || variables.value.length === 0) return;
  aiFilling.value = true;
  status.value = "AI 填充中...";
  try {
    const payload = {
      template_name: selectedTemplateName.value,
      enable_rag: false,
      custom_rag_content: customRagContent.value,
    };
    const { data, error } = await aiFillVariables(payload);
    if (error || !data?.variables) {
      status.value = `AI 填充失败：${error || "无返回"}`;
      return;
    }
    lastSources.value = data.sources || [];
    Object.entries(data.variables).forEach(([k, v]) => {
      values[k] = v;
    });
    status.value = "AI 填充完成，请检查后生成。";
  } finally {
    aiFilling.value = false;
  }
}

function clearValues() {
  Object.keys(values).forEach((k) => {
    values[k] = "";
  });
  status.value = "已清空";
}

async function generateDoc() {
  if (!selectedTemplateName.value || variables.value.length === 0) return;
  generating.value = true;
  downloadUrl.value = "";
  status.value = "生成中...";
  try {
    const { data, error } = await generateFromTemplate(
      selectedTemplateName.value,
      values,
      lastSources.value,
    );
    if (error || !data?.filename) {
      status.value = `生成失败：${error || "无返回"}`;
      return;
    }
    downloadUrl.value = `/download/${data.filename}`;
    status.value = "生成成功，点击下载。";
  } finally {
    generating.value = false;
  }
}

function handleFileSelect(event) {
  const [file] = event.target.files || [];
  uploadFile.value = file || null;
  if (file && !uploadName.value) {
    uploadName.value = file.name.replace(/\.(docx?|DOCX?)$/, "");
  }
}

async function handleUpload() {
  if (!uploadFile.value) return;
  uploading.value = true;
  status.value = "上传中...";
  try {
    const formData = new FormData();
    formData.append("template_name", uploadName.value || uploadFile.value.name);
    formData.append("file", uploadFile.value);
    formData.append("description", uploadDescription.value);
    formData.append("category", uploadCategory.value);
    const { data, error } = await uploadTemplate(formData);
    if (error || !data?.success) {
      status.value = `上传失败：${error || data?.error || "未知错误"}`;
      return;
    }
    status.value = "上传成功，已自动入库。";
    uploadFile.value = null;
    uploadName.value = "";
    if (uploadInput.value) uploadInput.value.value = "";
    await loadTemplates();
    if (data.template_name) {
      selectedTemplateName.value = data.template_name;
      await loadVariables();
    }
  } finally {
    uploading.value = false;
  }
}
</script>
