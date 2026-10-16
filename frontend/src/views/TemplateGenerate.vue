<template>
  <div class="generate-page">
    <header class="page-header">
      <div class="header-left">
        <button class="back-btn" @click="goBack">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
          返回
        </button>
        <div class="template-meta">
          <div class="template-icon">{{ templateIcon }}</div>
          <div>
            <h1 class="template-name">{{ template?.name || '生成文档' }}</h1>
            <p class="template-desc">
              <span class="badge">{{ template?.category || '通用' }}</span>
              <span class="desc-text">{{ template?.description || '填写占位符，生成 DOCX 文档' }}</span>
            </p>
          </div>
        </div>
      </div>
      <div class="header-right">
        <button class="secondary-btn" @click="loadVariables" :disabled="loadingVars">
          <span v-if="loadingVars" class="spinner"></span>
          重新提取变量
        </button>
        <button class="primary-btn" @click="generateDoc" :disabled="generating || variables.length === 0">
          <span v-if="generating" class="spinner"></span>
          生成文档
        </button>
      </div>
    </header>

    <main class="layout">
      <section class="panel form-panel">
        <div class="panel-header">
          <h2>变量填写</h2>
          <div class="panel-actions">
            <div class="rag-switch">
              <label class="switch">
                <input type="checkbox" v-model="enableRag" />
                <span class="slider"></span>
              </label>
              <span class="switch-text">RAG 辅助</span>
            </div>
            <select v-model="selectedKnowledgeBase" class="kb-select" :disabled="knowledgeBases.length === 0">
              <option value="">选择知识库（可选）</option>
              <option v-for="kb in knowledgeBases" :key="kb.id" :value="kb.id">
                {{ kb.name }}
              </option>
            </select>
            <button class="ghost-btn" @click="aiFill" :disabled="aiFilling || variables.length === 0">
              <span v-if="aiFilling" class="spinner"></span>
              AI 填充
            </button>
            <button class="ghost-btn" @click="clearValues" :disabled="variables.length === 0">清空</button>
          </div>
        </div>

        <div class="manual-ref">
          <div class="manual-ref-header">
            <h3>参考内容（可选）</h3>
            <p class="muted">没有知识库时可手动粘贴参考内容，AI 填充会优先参考。</p>
          </div>
          <textarea
            v-model="customRagContent"
            rows="4"
            placeholder="可粘贴：项目背景、产品资料、客户需求、标书要求等"
          ></textarea>
        </div>

        <div v-if="loadingVars" class="panel-empty">
          <div class="spinner large"></div>
          <p>正在获取变量...</p>
        </div>

        <div v-else-if="variables.length === 0" class="panel-empty">
          <p>未提取到占位符，先尝试“重新提取变量”。</p>
        </div>

        <div v-else class="variables-grid">
          <div v-for="(variable, idx) in variables" :key="variable.name" class="field">
            <label :for="`var-${idx}`">{{ variable.name }}</label>
            <textarea
              :id="`var-${idx}`"
              v-model="values[variable.name]"
              :placeholder="variable.description || '请输入内容'"
              rows="2"
            ></textarea>
          </div>
        </div>
      </section>

      <section class="panel info-panel">
        <div class="panel-header">
          <h2>生成结果</h2>
        </div>

        <div class="result-block">
          <p class="muted">生成完成后会提供下载链接</p>
          <div v-if="downloadUrl" class="download-box">
            <div>
              <div class="download-label">生成文件</div>
              <div class="download-name">{{ downloadUrl }}</div>
            </div>
            <button @click="downloadFile(downloadUrl)" class="primary-btn small">下载 Word</button>
          </div>
          <ul v-if="lastSources.length"><li v-for="(source,i) in lastSources" :key="i">取材：{{ source.title }}</li></ul>
          <div v-if="lastMessage" class="status-box">
            <div class="status-label">状态</div>
            <div class="status-text">{{ lastMessage }}</div>
          </div>
        </div>

        <div class="panel-footer">
          <h3>提示</h3>
          <ul>
            <li>占位符格式需为【变量】或 &#123;&#123;变量&#125;&#125;，与模板保持一致。</li>
            <li>AI 填充会基于模板内容生成 JSON，请确认后再生成。</li>
            <li>下载生成的 Word 文档后，请核对内容和格式。</li>
          </ul>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { downloadFile } from '../api/client';
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { fetchTemplates, fetchTemplateVariables, aiFillVariables, generateFromTemplate, fetchKnowledgeBases } from '../api/templates';

const route = useRoute();
const router = useRouter();

const template = ref(null);
const variables = ref([]);
const lastSources = ref([]);
const values = reactive({});
const loadingVars = ref(false);
const aiFilling = ref(false);
const generating = ref(false);
const lastMessage = ref('');
const downloadUrl = ref('');
const enableRag = ref(false);
const selectedKnowledgeBase = ref('');
const knowledgeBases = ref([]);
const customRagContent = ref('');

const templateId = computed(() => String(route.params.templateId || ''));

const templateIcon = computed(() => {
  const iconMap = {
    '报告': '📊',
    '合同': '📜',
    '简历': '👤',
    '招投标': '📑',
    '方案': '💡',
    '函件': '✉️'
  };
  return iconMap[template.value?.category] || '📄';
});

onMounted(async () => {
  await loadTemplateMeta();
  await loadVariables();
  await loadKnowledgeBases();
});

function goBack() {
  router.push('/templates');
}

async function loadTemplateMeta() {
  const { data, error } = await fetchTemplates();
  if (error) {
    lastMessage.value = `获取模板列表失败：${error}`;
    return;
  }
  const found = (data || []).find((t) => t.name === templateId.value);
  template.value = found || { name: templateId.value, category: '通用', description: '' };
}

function resetValues(varList) {
  Object.keys(values).forEach((k) => delete values[k]);
  (varList || []).forEach((v) => {
    values[v.name] = v.default_value || '';
  });
}

async function loadVariables() {
  if (!templateId.value) return;
  loadingVars.value = true;
  lastMessage.value = '';
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
    console.error('加载知识库列表失败:', err);
  }
}

async function aiFill() {
  if (!templateId.value) return;
  aiFilling.value = true;
  lastMessage.value = 'AI 填充中...';
  try {
    const payload = {
      template_name: templateId.value,
      enable_rag: enableRag.value,
      custom_rag_content: customRagContent.value
    };
    if (selectedKnowledgeBase.value) {
      payload.kb_name = selectedKnowledgeBase.value;
    }
    const { data, error } = await aiFillVariables(payload);
    if (error || !data?.variables) {
      lastMessage.value = `AI 填充失败：${error || '无返回'}`;
      return;
    }
    lastSources.value = data.sources || [];
    Object.entries(data.variables).forEach(([k, v]) => {
      values[k] = v;
    });
    lastMessage.value = 'AI 填充完成，请确认后生成。';
  } finally {
    aiFilling.value = false;
  }
}

function clearValues() {
  Object.keys(values).forEach((k) => {
    values[k] = '';
  });
  lastMessage.value = '已清空';
}

async function generateDoc() {
  if (!templateId.value) return;
  generating.value = true;
  lastMessage.value = '生成中...';
  downloadUrl.value = '';
  try {
    const { data, error } = await generateFromTemplate(templateId.value, values, lastSources.value);
    if (error || !data?.filename) {
      lastMessage.value = `生成失败：${error || '无返回'}`;
      return;
    }
    downloadUrl.value = `/download/${data.filename}`;
    lastMessage.value = '生成成功，可点击下载。';
  } finally {
    generating.value = false;
  }
}
</script>

<style scoped>
.generate-page {
  min-height: 100vh;
  background: #fff;
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
}
.back-btn svg {
  width: 18px;
  height: 18px;
}
.template-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}
.template-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: #eef2ff;
  display: grid;
  place-items: center;
  font-size: 22px;
}
.template-name {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #111827;
}
.template-desc {
  margin: 6px 0 0;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6b7280;
  font-size: 14px;
}
.badge {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 6px;
  background: #eef2ff;
  color: #4f46e5;
  font-weight: 600;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.primary-btn,
.secondary-btn,
.ghost-btn,
.primary-btn.small {
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.primary-btn {
  background: #4f46e5;
  color: #fff;
  padding: 10px 16px;
}
.primary-btn.small {
  padding: 8px 12px;
}
.secondary-btn {
  background: #111827;
  color: #fff;
  padding: 10px 16px;
}
.ghost-btn {
  background: #f3f4f6;
  color: #111827;
  padding: 8px 12px;
}
.layout {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
  padding: 16px;
}
.panel {
  background: #fff;
  border-radius: 14px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.03);
  display: flex;
  flex-direction: column;
  min-height: 400px;
}
.panel-header {
  padding: 16px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.panel-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

/* RAG Toggle Switch */
.rag-switch {
  display: flex;
  align-items: center;
  gap: 8px;
}

.switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}

.switch input[type="checkbox"] {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #e5e7eb;
  border-radius: 24px;
  transition: all 0.3s ease;
}

.slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  border-radius: 50%;
  transition: all 0.3s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.switch input:checked + .slider {
  background-color: #4f46e5;
}

.switch input:checked + .slider:before {
  transform: translateX(20px);
}

.switch input:focus + .slider {
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.2);
}

.switch-text {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
  user-select: none;
}

.kb-select {
  padding: 8px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  font-size: 14px;
  color: #111827;
  cursor: pointer;
  min-width: 180px;
}

.kb-select:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  background-color: #f9fafb;
}
.manual-ref {
  padding: 0 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.manual-ref-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}
.manual-ref-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #111827;
}
.manual-ref textarea {
  width: 100%;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px;
  font-size: 14px;
  resize: vertical;
  min-height: 100px;
}
.variables-grid {
  padding: 16px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field label {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}
.field textarea {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
  font-size: 14px;
  resize: vertical;
  min-height: 60px;
}
.panel-empty {
  flex: 1;
  display: grid;
  place-items: center;
  color: #6b7280;
  gap: 8px;
}
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #e5e7eb;
  border-top-color: #4f46e5;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
.spinner.large {
  width: 24px;
  height: 24px;
}
.info-panel {
  padding: 0;
}
.result-block {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.muted {
  color: #6b7280;
  margin: 0;
}
.download-box,
.status-box {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.download-label,
.status-label {
  color: #6b7280;
  font-size: 13px;
}
.download-name,
.status-text {
  font-weight: 600;
  color: #111827;
}
.panel-footer {
  margin-top: auto;
  padding: 16px;
  border-top: 1px solid #e5e7eb;
}
.panel-footer ul {
  padding-left: 18px;
  color: #4b5563;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 1024px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .variables-grid {
    grid-template-columns: 1fr;
  }
}
</style>
