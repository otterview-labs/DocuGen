<template>
  <section class="document-workspace">
    <UiPageHeader
      :title="template?.name || '生成文档'"
      :description="template?.description || '填写占位符，生成 DOCX 文档'"
      ><template #actions
        ><UiButton @click="goBack"
          ><ArrowLeft :size="15" />返回模板库
        </UiButton></template
      ></UiPageHeader
    >
    <div class="document-editor">
      <section class="editor-main">
        <div class="editor-section">
          <div class="editor-section-heading">
            <div>
              <h2>
                变量填写
                <span class="document-count">{{ variables.length }}</span>
              </h2>
              <p>填写内容将替换模板中对应的占位符。</p>
            </div>
            <UiButton
              :disabled="loadingVars"
              @click="loadVariables"
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
              :disabled="aiFilling || !variables.length"
              @click="aiFill"
              ><LoaderCircle
                v-if="aiFilling"
                :size="15"
                class="spin"
              /><Sparkles v-else :size="15" />AI 填充</UiButton
            ><UiButton
              :disabled="!variables.length"
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
        </div>
      </section>
      <aside class="editor-aside" aria-label="生成文档">
        <div class="editor-aside-title">
          <FileCheck2 :size="20" />
          <h2>生成结果</h2>
        </div>
        <p class="editor-help">核对变量后生成文档，保留模板中的格式。</p>
        <dl class="document-summary">
          <dt>模板分类</dt>
          <dd>{{ template?.category || "通用" }}</dd>
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
        <UiButton
          :disabled="generating || !variables.length"
          @click="generateDoc"
          class="full-width"
          variant="primary"
          ><LoaderCircle v-if="generating" :size="16" class="spin" /><FileOutput
            v-else
            :size="16"
          />{{ generating ? "生成中…" : "生成文档" }}</UiButton
        >
        <UiNotice v-if="lastMessage" :message="lastMessage" />
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
  </section>
</template>
<script setup>
import UiNotice from "../components/ui/UiNotice.vue";
import UiEmptyState from "../components/ui/UiEmptyState.vue";
import UiPageHeader from "../components/ui/UiPageHeader.vue";
import UiButton from "../components/ui/UiButton.vue";
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
  Sparkles,
  TextCursorInput,
} from "@lucide/vue";

import { downloadFile } from "../api/client";
import { computed, onMounted, reactive, ref } from "vue";
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
const lastSources = ref([]);
const values = reactive({});
const loadingVars = ref(false);
const aiFilling = ref(false);
const generating = ref(false);
const lastMessage = ref("");
const downloadUrl = ref("");
const enableRag = ref(false);
const selectedKnowledgeBase = ref("");
const knowledgeBases = ref([]);
const customRagContent = ref("");

const templateId = computed(() => String(route.params.templateId || ""));

onMounted(async () => {
  await loadTemplateMeta();
  await loadVariables();
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
  const found = (data || []).find((t) => t.name === templateId.value);
  template.value = found || {
    name: templateId.value,
    category: "通用",
    description: "",
  };
}

function resetValues(varList) {
  Object.keys(values).forEach((k) => delete values[k]);
  (varList || []).forEach((v) => {
    values[v.name] = v.default_value || "";
  });
}

async function loadVariables() {
  if (!templateId.value) return;
  loadingVars.value = true;
  lastMessage.value = "";
  try {
    // 优先使用元数据中的变量
    if (template.value?.variables && template.value.variables.length > 0) {
      variables.value = template.value.variables;
      resetValues(variables.value);
    } else {
      const { data, error } = await fetchTemplateVariables(templateId.value);
      if (error) {
        lastMessage.value = `提取变量失败：${error}`;
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
  if (!templateId.value) return;
  aiFilling.value = true;
  lastMessage.value = "AI 填充中...";
  try {
    const payload = {
      template_name: templateId.value,
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
      values[k] = v;
    });
    lastMessage.value = "AI 填充完成，请确认后生成。";
  } finally {
    aiFilling.value = false;
  }
}

function clearValues() {
  Object.keys(values).forEach((k) => {
    values[k] = "";
  });
  lastMessage.value = "已清空";
}

async function generateDoc() {
  if (!templateId.value) return;
  generating.value = true;
  lastMessage.value = "生成中...";
  downloadUrl.value = "";
  try {
    const { data, error } = await generateFromTemplate(
      templateId.value,
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
