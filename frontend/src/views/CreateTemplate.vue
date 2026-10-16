<template>
  <div class="create-page">
    <header class="hero">
      <div class="hero-body">
        <div class="hero-title">
          <div class="pill">模板生成工作台</div>
          <h1>选择模板 · 填充变量 · 一键导出 DOCX</h1>
          <p>支持占位符自动识别、AI 变量填充与在线下载。可上传自己的 Word 模板（【变量】或 &#123;&#123;变量&#125;&#125;）。</p>
        </div>
        <div class="hero-metrics">
          <div class="metric">
            <div class="metric-icon">📄</div>
            <div>
              <div class="metric-label">模板数量</div>
              <div class="metric-value">{{ templates.length || 0 }}</div>
            </div>
          </div>
          <div class="metric">
            <div class="metric-icon">🧠</div>
            <div>
              <div class="metric-label">AI 填充</div>
              <div class="metric-value">支持</div>
            </div>
          </div>
          <div class="metric">
            <div class="metric-icon">⬇️</div>
            <div>
              <div class="metric-label">导出格式</div>
              <div class="metric-value">DOCX</div>
            </div>
          </div>
        </div>
      </div>
    </header>

    <main class="layout">
      <section class="panel main-panel">
        <div class="panel-header">
          <div>
            <h2>模板与变量</h2>
            <p class="muted">选择一个模板或上传新的模板，系统会自动提取占位符。</p>
          </div>
          <div class="header-actions">
            <button class="ghost-btn" @click="loadTemplates" :disabled="loadingTemplates">
              <span v-if="loadingTemplates" class="spinner"></span> 重新加载
            </button>
            <button class="primary-btn" @click="generateDoc" :disabled="generating || variables.length === 0">
              <span v-if="generating" class="spinner"></span> 生成文档
            </button>
          </div>
        </div>

        <div class="grid-2">
          <div class="block">
            <label class="label">选择模板</label>
            <div class="template-select">
              <select v-model="selectedTemplateName" @change="handleTemplateChange">
                <option disabled value="">请选择模板</option>
                <option v-for="t in templates" :key="t.name" :value="t.name">
                  {{ t.name }}（{{ t.category || '通用' }}）
                </option>
              </select>
              <button class="secondary-btn" @click="loadVariables" :disabled="!selectedTemplateName || loadingVars">
                <span v-if="loadingVars" class="spinner"></span> 提取变量
              </button>
            </div>
            <p class="muted small">占位符格式支持【变量】或 &#123;&#123;变量&#125;&#125;，与 Word 模板中的写法一致。</p>
          </div>

          <div class="block upload-block">
            <label class="label">上传模板</label>
            <div class="upload-row">
              <input type="file" ref="uploadInput" accept=".docx" @change="handleFileSelect" />
              <input v-model="uploadName" type="text" placeholder="模板名称（可选，默认用文件名）" />
              <button class="secondary-btn" @click="handleUpload" :disabled="uploading || !uploadFile">
                <span v-if="uploading" class="spinner"></span> 上传并入库
              </button>
            </div>
            <p class="muted small">上传后自动提取变量并加入列表。</p>
          </div>
        </div>

        <div class="block">
          <div class="block-header">
            <div>
              <h3>变量填写（{{ variables.length }}）</h3>
              <p class="muted small" v-if="selectedTemplateName">当前模板：{{ selectedTemplateName }}</p>
            </div>
            <div class="block-actions">

              <button class="ghost-btn" @click="aiFill" :disabled="aiFilling || variables.length === 0">
                <span v-if="aiFilling" class="spinner"></span> AI 填充
              </button>
              <button class="ghost-btn" @click="clearValues" :disabled="variables.length === 0">清空</button>
            </div>
          </div>

          <div class="manual-ref">
            <div class="manual-ref-title">参考内容（可选）</div>
            <textarea
              v-model="customRagContent"
              rows="4"
              placeholder="没有知识库时可手动粘贴参考内容，AI 填充会优先参考"
            ></textarea>
            <p class="muted small">不依赖知识库；仅在 AI 填充时使用。</p>
          </div>

          <div v-if="loadingVars" class="empty">
            <div class="spinner big"></div>
            <p>正在提取变量...</p>
          </div>
          <div v-else-if="variables.length === 0" class="empty">
            <p>未找到变量，请先选择模板并提取。</p>
          </div>
          <div v-else class="vars-grid">
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
        </div>
      </section>

      <aside class="panel side-panel">
        <div class="panel-header">
          <h2>操作步骤</h2>
        </div>
        <ol class="steps">
          <li>选择或上传 DOCX 模板</li>
          <li>提取并填写占位符变量</li>
          <li>可选：填写参考资料后点“AI 填充”</li>
          <li>点击 “生成文档”，下载 DOCX</li>
        </ol>

        <div class="status-card">
          <div class="status-title">生成结果</div>
          <p class="muted small">生成完成后可下载 Word 文档。</p>
          <div v-if="downloadUrl" class="download-box">
            <div>
              <div class="label">生成文件</div>
              <div class="value">{{ downloadUrl }}</div>
            </div>
            <button class="primary-btn small" @click="downloadFile(downloadUrl)">下载 Word</button>
          </div>
          <div v-if="status" class="status-text">{{ status }}</div>
        </div>

        <div class="info-card">
          <div class="info-title">占位符规范</div>
          <ul>
            <li>推荐格式：<code>【变量】</code>；兼容 <code>&#123;&#123;变量&#125;&#125;</code></li>
            <li>上传模板后会自动入库并在列表可选</li>
            <li>AI 填充依赖模板内容，确保模板文本包含上下文</li>
          </ul>
        </div>
      </aside>
    </main>
  </div>
</template>

<script setup>
import { downloadFile } from '../api/client';
import { computed, onMounted, reactive, ref } from 'vue';
import {
  fetchTemplates,
  fetchTemplateVariables,
  aiFillVariables,
  generateFromTemplate,
  uploadTemplate
} from '../api/templates';

const templates = ref([]);
const loadingTemplates = ref(false);
const selectedTemplateName = ref('');
const variables = ref([]);
const lastSources = ref([]);
const values = reactive({});
const loadingVars = ref(false);
const aiFilling = ref(false);
const generating = ref(false);
const status = ref('');
const downloadUrl = ref('');
const customRagContent = ref('');

const uploadInput = ref(null);
const uploadFile = ref(null);
const uploadName = ref('');
const uploading = ref(false);

const currentTemplate = computed(() =>
  templates.value.find((t) => t.name === selectedTemplateName.value) || null
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
    values[v.name] = v.default_value || '';
  });
}

async function loadVariables() {
  if (!selectedTemplateName.value) return;
  loadingVars.value = true;
  status.value = '';
  variables.value = [];
  try {
    // 优先使用元数据附带变量
    if (currentTemplate.value?.variables?.length) {
      variables.value = currentTemplate.value.variables;
      resetValues(variables.value);
    } else {
      const { data, error } = await fetchTemplateVariables(selectedTemplateName.value);
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
  status.value = 'AI 填充中...';
  try {
    const payload = {
      template_name: selectedTemplateName.value,
      enable_rag: false,
      custom_rag_content: customRagContent.value
    };
    const { data, error } = await aiFillVariables(payload);
    if (error || !data?.variables) {
      status.value = `AI 填充失败：${error || '无返回'}`;
      return;
    }
    lastSources.value = data.sources || [];
    Object.entries(data.variables).forEach(([k, v]) => {
      values[k] = v;
    });
    status.value = 'AI 填充完成，请检查后生成。';
  } finally {
    aiFilling.value = false;
  }
}

function clearValues() {
  Object.keys(values).forEach((k) => {
    values[k] = '';
  });
  status.value = '已清空';
}

async function generateDoc() {
  if (!selectedTemplateName.value || variables.value.length === 0) return;
  generating.value = true;
  downloadUrl.value = '';
  status.value = '生成中...';
  try {
    const { data, error } = await generateFromTemplate(selectedTemplateName.value, values, lastSources.value);
    if (error || !data?.filename) {
      status.value = `生成失败：${error || '无返回'}`;
      return;
    }
    downloadUrl.value = `/download/${data.filename}`;
    status.value = '生成成功，点击下载。';
  } finally {
    generating.value = false;
  }
}

function handleFileSelect(event) {
  const [file] = event.target.files || [];
  uploadFile.value = file || null;
  if (file && !uploadName.value) {
    uploadName.value = file.name.replace(/\.(docx?|DOCX?)$/, '');
  }
}

async function handleUpload() {
  if (!uploadFile.value) return;
  uploading.value = true;
  status.value = '上传中...';
  try {
    const formData = new FormData();
    formData.append('template_name', uploadName.value || uploadFile.value.name);
    formData.append('file', uploadFile.value);
    formData.append('description', '上传自创建页面');
    const { data, error } = await uploadTemplate(formData);
    if (error || !data?.success) {
      status.value = `上传失败：${error || data?.error || '未知错误'}`;
      return;
    }
    status.value = '上传成功，已自动入库。';
    uploadFile.value = null;
    uploadName.value = '';
    if (uploadInput.value) uploadInput.value.value = '';
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

<style scoped>
.create-page {
  min-height: 100vh;
  background: #fff;
  color: #111827;
}

.create-page :deep(*) {
  color: inherit;
}

.hero {
  border-bottom: 1px solid #e5e7eb;
  padding: 32px 24px 16px;
  background: #fff;
}

.hero-body {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: center;
}

.hero-title h1 {
  margin: 10px 0;
  font-size: 32px;
  font-weight: 800;
}

.hero-title p {
  margin: 0;
  color: #4b5563;
}

.pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #1d4ed8;
  font-weight: 700;
  font-size: 13px;
}

.hero-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  min-width: 360px;
}

.metric {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  background: #fff;
}

.metric-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: #eef2ff;
  display: grid;
  place-items: center;
  font-size: 20px;
}

.metric-label {
  color: #6b7280;
  font-size: 12px;
}

.metric-value {
  font-weight: 800;
  font-size: 18px;
}

.layout {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 16px;
  padding: 16px 24px 32px;
}

.panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.04);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.panel-header h2 {
  margin: 0;
  font-size: 20px;
}

.muted {
  color: #6b7280;
}

.muted.small {
  font-size: 13px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.primary-btn,
.secondary-btn,
.ghost-btn {
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
}

.primary-btn {
  background: #111827;
  color: #fff;
}

.primary-btn.small {
  padding: 8px 12px;
}

.secondary-btn {
  background: #1d4ed8;
  color: #fff;
}

.ghost-btn {
  background: #f3f4f6;
  color: #111827;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.block {
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px;
}

.block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.block-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.manual-ref {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px;
  background: #fff;
  margin-bottom: 14px;
}
.manual-ref-title {
  font-weight: 800;
  font-size: 14px;
  margin-bottom: 10px;
}
.manual-ref textarea {
  width: 100%;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
  resize: vertical;
  font-size: 14px;
  min-height: 100px;
}

.label {
  display: block;
  font-weight: 700;
  margin-bottom: 6px;
}

.template-select {
  display: flex;
  align-items: center;
  gap: 10px;
}

.template-select select,
.upload-row input[type="text"] {
  flex: 1;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
  font-size: 14px;
}

.upload-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.upload-row input[type="file"] {
  flex: 1;
  border: 1px dashed #e5e7eb;
  padding: 8px;
  border-radius: 10px;
  background: #fff;
}

.vars-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field textarea {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
  min-height: 60px;
  resize: vertical;
  font-size: 14px;
  background: #fff;
}

.empty {
  text-align: center;
  padding: 30px 10px;
  color: #6b7280;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #e5e7eb;
  border-top-color: #1d4ed8;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.spinner.big {
  width: 24px;
  height: 24px;
}

.side-panel .steps {
  margin: 0 0 16px;
  padding-left: 18px;
  color: #111827;
}

.status-card,
.info-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 12px;
  background: #fff;
}

.status-title,
.info-title {
  font-weight: 700;
  margin-bottom: 6px;
}

.download-box {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
  margin-bottom: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.label {
  font-size: 12px;
  color: #6b7280;
}

.value {
  font-weight: 700;
}

.status-text {
  color: #111827;
}

.info-card ul {
  margin: 0;
  padding-left: 18px;
  color: #4b5563;
}

.switch {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #4b5563;
}

.switch input {
  width: 16px;
  height: 16px;
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
  .hero-body {
    flex-direction: column;
    align-items: flex-start;
  }
  .hero-metrics {
    min-width: 0;
    width: 100%;
  }
}
</style>
