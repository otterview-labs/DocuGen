<template>
  <section class="document-workspace template-studio">
    <UiPageHeader
      :title="template?.name || '生成文档'"
      :description="template?.description || '填写占位符，生成 DOCX 文档'"
      ><template #actions
        ><UiButton @click="goBack"
          ><ArrowLeft :size="15" />返回模板库
        </UiButton></template
      ></UiPageHeader
    >
    <div class="studio-context">
      <span :class="{ 'draft-warning': draft.warning.value }"
        ><Save :size="15" />{{ draft.message.value }}</span
      ><span>手动填写与导出无需模型</span>
    </div>
    <div v-if="!templateId" class="catalog-panel">
      <UiEmptyState
        title="先选择一份模板"
        description="从模板库挑选文档，或导入自己的 Word 模板。"
        ><UiButton to="/templates" variant="primary"
          >浏览模板</UiButton
        ></UiEmptyState
      >
    </div>
    <div v-else class="document-editor studio-layout">
      <section class="editor-main">
        <div class="editor-section">
          <div class="editor-section-heading">
            <div>
              <h2>
                填写文档内容
                <span class="document-count">{{ variables.length }}</span>
              </h2>
              <p>先完善基本信息，再填写正文，最后核对并导出。</p>
            </div>
            <UiButton
              :disabled="loadingVars || aiFilling || generating"
              @click="loadVariables({ refresh: true })"
              size="compact"
              ><RefreshCw
                :size="15"
                :class="{ spin: loadingVars }"
              />重新提取变量
            </UiButton>
          </div>
          <div class="retrieval-assist">
            <label class="assist-toggle"
              ><input v-model="enableRag" type="checkbox" />知识库辅助</label
            ><select
              v-model="selectedKnowledgeBase"
              class="field-input"
              aria-label="辅助知识库"
              :disabled="!knowledgeBases.length"
            >
              <option value="">选择知识库（可选）</option>
              <option
                v-for="knowledgeBase in knowledgeBases"
                :key="knowledgeBase.id"
                :value="knowledgeBase.id"
              >
                {{ knowledgeBase.name }}
              </option></select
            ><UiButton
              size="compact"
              :disabled="
                aiFilling || generating || loadingVars || !variables.length
              "
              @click="aiFill"
              ><LoaderCircle
                v-if="aiFilling"
                :size="15"
                class="spin"
              /><Sparkles v-else :size="15" />AI 填充</UiButton
            ><UiButton
              :disabled="generating || aiFilling || !variables.length"
              @click="clearValues"
              variant="text"
            >
              清空
            </UiButton>
          </div>
          <details class="reference-disclosure">
            <summary>
              <BookOpen :size="16" />参考内容（可选）<ChevronDown :size="15" />
            </summary>
            <label class="field-label" for="template-reference"
              >手动参考资料<textarea
                id="template-reference"
                v-model="customRagContent"
                class="field-input"
                rows="4"
                placeholder="可粘贴：项目背景、产品资料、客户需求、标书要求等"
              />
            </label>
            <p>AI 填充会优先参考这些内容。</p>
          </details>
          <UiEmptyState
            v-if="loadingVars"
            :icon="LoaderCircle"
            description="正在获取变量…"
            state="loading"
            compact
          ></UiEmptyState>
          <UiEmptyState
            v-else-if="!variables.length"
            :icon="TextCursorInput"
            description="未提取到占位符，请尝试重新提取变量。"
            compact
          ></UiEmptyState>
          <TemplateFields
            v-else
            :variables="variables"
            :revision="fieldRevision"
            :model-value="values"
            :disabled="generating || aiFilling"
            @update:model-value="updateValues"
          />
        </div>
      </section>
      <aside class="editor-aside studio-aside" aria-label="生成文档">
        <div class="editor-aside-title">
          <FileCheck2 :size="20" />
          <h2>生成与导出</h2>
        </div>
        <p class="editor-help">核对变量后生成文档，保留模板中的格式。</p>
        <dl class="document-summary">
          <dt>模板分类</dt>
          <dd>{{ template?.category || "通用" }}</dd>
          <dt>填写进度</dt>
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
        <UiButton
          :disabled="
            generating || loadingVars || aiFilling || !variables.length
          "
          ref="exportAction"
          id="studio-export"
          @click="generateDoc"
          class="full-width"
          variant="primary"
          ><LoaderCircle v-if="generating" :size="16" class="spin" /><FileOutput
            v-else
            :size="16"
          />{{ generating ? "生成中…" : "生成文档" }}</UiButton
        >
        <UiNotice
          v-if="lastMessage"
          :message="lastMessage"
          :tone="lastMessage.includes('失败') ? 'error' : 'info'"
        />
        <div v-if="downloadUrl" class="document-download">
          <CheckCircle2 :size="22" /><strong>文档已生成</strong>
          <p>下载后请核对内容与排版。</p>
          <UiButton @click="downloadFile(downloadUrl)"
            ><Download :size="16" />下载 Word
          </UiButton>
        </div>
        <div v-if="lastSources.length" class="editor-guidance">
          <h3>取材记录</h3>
          <ul>
            <li v-for="(source, index) in lastSources" :key="index">
              {{ source.title }}
            </li>
          </ul>
        </div>
        <section
          v-if="variables.length"
          class="content-review"
          aria-label="内容核对预览"
        >
          <header>
            <h3>内容核对</h3>
            <span
              >{{ completedVariables }} / {{ variables.length }} 项已填写</span
            >
          </header>
          <p>随填写更新；这里核对内容，Word 版式以下载文件为准。</p>
          <div class="review-paper">
            <h4>{{ template?.name }}</h4>
            <section v-for="variable in variables" :key="variable.name">
              <h5>{{ variable.name }}</h5>
              <p
                :class="{
                  'review-empty': !String(values[variable.name] || '').trim(),
                }"
              >
                {{ String(values[variable.name] || "").trim() || "待填写" }}
              </p>
            </section>
          </div>
        </section>
        <div class="editor-guidance">
          <h3>使用提示</h3>
          <p>
            支持 <code>【变量】</code> 和 <code v-pre>{{ 变量 }}</code
            >。AI 填充后请确认，再生成文档。
          </p>
          <p>手动填写和导出无需模型。</p>
        </div>
      </aside>
    </div>
    <div v-if="templateId && variables.length" class="studio-mobile-actions">
      <span>{{ completedVariables }} / {{ variables.length }} 项已填写</span
      ><UiButton
        href="#studio-export"
        variant="primary"
        @click.prevent="focusExport"
        >核对与导出<ArrowRight
      /></UiButton>
    </div>
  </section>
</template>
<script setup>
import "../styles/template-studio.css";
import TemplateFields from "../components/templates/TemplateFields.vue";
import { useTemplateDraft } from "../composables/useTemplateDraft";
import UiNotice from "../components/ui/UiNotice.vue";
import UiEmptyState from "../components/ui/UiEmptyState.vue";
import UiPageHeader from "../components/ui/UiPageHeader.vue";
import UiButton from "../components/ui/UiButton.vue";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  Download,
  FileCheck2,
  FileOutput,
  LoaderCircle,
  RefreshCw,
  Sparkles,
  Save,
  TextCursorInput,
} from "@lucide/vue";

import { downloadFile } from "../api/client";
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  fetchTemplates,
  fetchTemplateVariables,
  aiFillVariables,
  generateFromTemplate,
  fetchKnowledgeBases,
} from "../api/templates";

const route = useRoute();
const router = useRouter();

const template = ref(null);
const variables = ref([]);
const fieldRevision = ref(0);
const lastSources = ref([]);
const values = reactive({});
const loadingVars = ref(true);
const aiFilling = ref(false);
const generating = ref(false);
const lastMessage = ref("");
const downloadUrl = ref("");
const exportAction = ref(null);
function focusExport() {
  exportAction.value?.focus();
}
const enableRag = ref(false);
const selectedKnowledgeBase = ref("");
const knowledgeBases = ref([]);
const customRagContent = ref("");

const templateId = String(route.params.templateId || "");
const completedVariables = computed(
  () =>
    variables.value.filter((v) => String(values[v.name] || "").trim()).length,
);
const draft = useTemplateDraft(templateId, variables, values, {
  reference: customRagContent,
  enableRag,
  knowledgeBase: selectedKnowledgeBase,
  sources: lastSources,
});
function updateValues(next) {
  Object.assign(values, next);
}
watch(
  [() => ({ ...values }), lastSources],
  () => {
    if (downloadUrl.value) {
      downloadUrl.value = "";
      lastMessage.value = "内容已更改，请重新生成文档。";
    }
  },
  { deep: true, flush: "sync" },
);

onMounted(async () => {
  await loadTemplateMeta();
  await loadVariables();
  draft.restore();
  fieldRevision.value++;
  await loadKnowledgeBases();
});

function goBack() {
  router.push("/templates");
}

async function loadTemplateMeta() {
  const { data, error } = await fetchTemplates();
  if (error) {
    lastMessage.value = `获取模板列表失败：${error}`;
    return;
  }
  const found = (data || []).find((t) => t.name === templateId);
  template.value = found || {
    name: templateId,
    category: "通用",
    description: "",
  };
}

function resetValues(varList, preserve = false) {
  const previous = preserve ? { ...values } : {};
  Object.keys(values).forEach((k) => delete values[k]);
  (varList || []).forEach((v) => {
    values[v.name] = Object.hasOwn(previous, v.name)
      ? previous[v.name]
      : v.default_value || "";
  });
  fieldRevision.value++;
}

async function loadVariables({ refresh = false } = {}) {
  if (!templateId) return;
  loadingVars.value = true;
  lastMessage.value = "";
  try {
    // 优先使用元数据中的变量
    if (
      !refresh &&
      template.value?.variables &&
      template.value.variables.length > 0
    ) {
      variables.value = template.value.variables;
      resetValues(variables.value);
    } else {
      const { data, error } = await fetchTemplateVariables(templateId, {
        refresh,
      });
      if (error) {
        lastMessage.value = `提取变量失败：${error}`;
        if (!refresh) variables.value = [];
      } else {
        variables.value = data || [];
        resetValues(variables.value, refresh);
        if (template.value) template.value.variables = variables.value;
      }
    }
  } finally {
    loadingVars.value = false;
  }
}

async function loadKnowledgeBases() {
  try {
    const { data, error } = await fetchKnowledgeBases();
    if (!error && data) {
      knowledgeBases.value = data;
    }
  } catch (err) {
    console.error("加载知识库列表失败:", err);
  }
}

async function aiFill() {
  if (!templateId) return;
  aiFilling.value = true;
  lastMessage.value = "AI 填充中...";
  try {
    const payload = {
      template_name: templateId,
      enable_rag: enableRag.value,
      custom_rag_content: customRagContent.value,
    };
    if (selectedKnowledgeBase.value) {
      payload.kb_name = selectedKnowledgeBase.value;
    }
    const { data, error } = await aiFillVariables(payload);
    if (error || !data?.variables) {
      lastMessage.value = `AI 填充失败：${error || "无返回"}`;
      return;
    }
    lastSources.value = data.sources || [];
    Object.entries(data.variables).forEach(([k, v]) => {
      if (variables.value.some((variable) => variable.name === k))
        values[k] = String(v ?? "");
    });
    fieldRevision.value++;
    lastMessage.value = "AI 填充完成，请确认后生成。";
  } finally {
    aiFilling.value = false;
  }
}

function clearValues() {
  lastSources.value = [];
  Object.keys(values).forEach((k) => {
    values[k] = "";
  });
  fieldRevision.value++;
  lastMessage.value = "已清空";
}

async function generateDoc() {
  if (!templateId) return;
  generating.value = true;
  lastMessage.value = "生成中...";
  downloadUrl.value = "";
  try {
    const { data, error } = await generateFromTemplate(
      templateId,
      values,
      lastSources.value,
    );
    if (error || !data?.filename) {
      lastMessage.value = `生成失败：${error || "无返回"}`;
      return;
    }
    downloadUrl.value = `/download/${data.filename}`;
    lastMessage.value = "生成成功，可点击下载。";
  } finally {
    generating.value = false;
  }
}
</script>
