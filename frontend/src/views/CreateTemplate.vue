<template>
  <section class="document-workspace">
    <header class="page-heading">
      <div>
        <h1>上传模板</h1>
        <p>选择模板，填写变量，生成可下载的 Word 文档。</p>
      </div>
      <RouterLink class="button" to="/templates"
        ><ArrowLeft :size="15" />返回模板库</RouterLink
      >
    </header>
    <div class="document-editor">
      <div class="editor-main">
        <section class="editor-section">
          <div class="editor-section-heading">
            <div>
              <h2>模板与变量</h2>
              <p>选择已有模板，或上传新的 Word 文件。</p>
            </div>
            <button
              class="icon-button"
              aria-label="重新加载模板"
              :disabled="loadingTemplates"
              @click="loadTemplates"
            >
              <RefreshCw :size="17" :class="{ spin: loadingTemplates }" />
            </button>
          </div>
          <label class="field-label" for="selected-template">选择模板</label>
          <div class="template-select-row">
            <select
              id="selected-template"
              v-model="selectedTemplateName"
              class="field-input"
              @change="handleTemplateChange"
            >
              <option disabled value="">请选择模板</option>
              <option
                v-for="template in templates"
                :key="template.name"
                :value="template.name"
              >
                {{ template.name }}（{{ template.category || "通用" }}）
              </option></select
            ><button
              class="button"
              :disabled="!selectedTemplateName || loadingVars"
              @click="loadVariables"
            >
              <ScanText :size="15" />提取变量
            </button>
          </div>
          <div class="upload-divider"><span>或上传新模板</span></div>
          <label
            class="template-upload-drop"
            for="template-upload"
            @dragover.prevent
            @drop.prevent="
              handleFileSelect({ target: { files: $event.dataTransfer.files } })
            "
            ><input
              id="template-upload"
              ref="uploadInput"
              class="sr-only"
              type="file"
              accept=".docx"
              @change="handleFileSelect"
            /><Upload :size="25" :stroke-width="1.5" /><strong>{{
              uploadFile ? uploadFile.name : "点击选择或拖入 Word 模板"
            }}</strong
            ><span>仅支持 DOCX · 自动提取占位符</span></label
          >
          <div class="template-upload-row">
            <input
              v-model="uploadName"
              class="field-input"
              aria-label="模板名称"
              placeholder="模板名称（可选，默认用文件名）"
            /><button
              class="button"
              :disabled="uploading || !uploadFile"
              @click="handleUpload"
            >
              <LoaderCircle v-if="uploading" :size="15" class="spin" /><Upload
                v-else
                :size="15"
              />{{ uploading ? "上传中…" : "上传并入库" }}
            </button>
          </div>
        </section>
        <section class="editor-section">
          <div class="editor-section-heading">
            <div>
              <h2>
                变量填写
                <span class="document-count">{{ variables.length }}</span>
              </h2>
              <p v-if="selectedTemplateName">
                当前模板：{{ selectedTemplateName }}
              </p>
            </div>
            <div class="inline-actions">
              <button
                class="button small"
                :disabled="aiFilling || !variables.length"
                @click="aiFill"
              >
                <LoaderCircle
                  v-if="aiFilling"
                  :size="14"
                  class="spin"
                /><Sparkles v-else :size="14" />AI 填充</button
              ><button
                class="text-button"
                :disabled="!variables.length"
                @click="clearValues"
              >
                清空
              </button>
            </div>
          </div>
          <details class="reference-disclosure">
            <summary>
              <BookOpen :size="16" />参考内容（可选）<ChevronDown :size="15" />
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
          <div v-if="loadingVars" class="editor-empty" role="status">
            <LoaderCircle :size="23" class="spin" />
            <p>正在提取变量…</p>
          </div>
          <div v-else-if="!variables.length" class="editor-empty">
            <TextCursorInput :size="27" :stroke-width="1.4" />
            <p>选择或上传模板后，在这里填写变量。</p>
          </div>
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
      </div>
      <aside class="editor-aside" aria-label="生成文档">
        <div class="editor-aside-title">
          <FileCheck2 :size="20" />
          <h2>生成结果</h2>
        </div>
        <p class="editor-help">
          填写并核对变量后，沿用模板格式导出 Word 文档。
        </p>
        <dl class="document-summary">
          <dt>当前模板</dt>
          <dd>{{ selectedTemplateName || "尚未选择" }}</dd>
          <dt>变量填写</dt>
          <dd>
            {{
              variables.filter((variable) =>
                String(values[variable.name] || "").trim(),
              ).length
            }}
            / {{ variables.length }}
          </dd>
          <dt>导出格式</dt>
          <dd>Word · DOCX</dd>
        </dl>
        <button
          class="button primary full-width"
          :disabled="generating || !variables.length"
          @click="generateDoc"
        >
          <LoaderCircle v-if="generating" :size="16" class="spin" /><FileOutput
            v-else
            :size="16"
          />{{ generating ? "生成中…" : "生成文档" }}
        </button>
        <p v-if="status" class="editor-status" role="status">{{ status }}</p>
        <div v-if="downloadUrl" class="document-download">
          <CheckCircle2 :size="22" /><strong>文档已生成</strong>
          <p>下载后请核对内容与排版。</p>
          <button class="button" @click="downloadFile(downloadUrl)">
            <Download :size="16" />下载 Word
          </button>
        </div>
        <div class="editor-guidance">
          <h3>占位符规范</h3>
          <p>
            在 Word 模板中使用 <code>【变量】</code> 或
            <code v-pre>{{ 变量 }}</code
            >。上传后会自动提取，也可以重新提取变量。
          </p>
          <p>AI 填充需要配置生成模型，手动填写和导出无需模型。</p>
        </div>
      </aside>
    </div>
  </section>
</template>
<script setup>
import { RouterLink } from "vue-router";
import {
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
  fetchTemplateVariables,
  aiFillVariables,
  generateFromTemplate,
  uploadTemplate,
} from "../api/templates";

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
const uploading = ref(false);

const currentTemplate = computed(
  () =>
    templates.value.find((t) => t.name === selectedTemplateName.value) || null,
);

onMounted(async () => {
  await loadTemplates();
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
    if (!selectedTemplateName.value && templates.value.length > 0) {
      selectedTemplateName.value = templates.value[0].name;
      await loadVariables();
    }
  } finally {
    loadingTemplates.value = false;
  }
}

function handleTemplateChange() {
  loadVariables();
}

function resetValues(varList) {
  Object.keys(values).forEach((k) => delete values[k]);
  (varList || []).forEach((v) => {
    values[v.name] = v.default_value || "";
  });
}

async function loadVariables() {
  if (!selectedTemplateName.value) return;
  loadingVars.value = true;
  status.value = "";
  variables.value = [];
  try {
    // 优先使用元数据附带变量
    if (currentTemplate.value?.variables?.length) {
      variables.value = currentTemplate.value.variables;
      resetValues(variables.value);
    } else {
      const { data, error } = await fetchTemplateVariables(
        selectedTemplateName.value,
      );
      if (error) {
        status.value = `提取变量失败：${error}`;
        variables.value = [];
      } else {
        variables.value = data || [];
        resetValues(variables.value);
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
    formData.append("description", "上传自创建页面");
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
