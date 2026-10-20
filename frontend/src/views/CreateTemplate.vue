<template>
  <section class="document-workspace create-page">
    <UiPageHeader
      title="上传模板"
      description="导入 Word、确认模板信息，保存后进入文档填写。"
    >
      <template #actions
        ><UiButton href="#create-upload-heading" @click.prevent="focusUpload"
          ><Upload />导入 Word</UiButton
        ><UiButton to="/templates"><ArrowLeft />返回模板库</UiButton></template
      >
    </UiPageHeader>

    <div class="create-intake upload-intake">
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
              :disabled="uploading"
              class="field-input"
              maxlength="100"
              placeholder="模板名称（可选，默认用文件名）"
          /></label>
          <div>
            <label class="field-label" for="upload-category">模板分类</label>
            <select
              id="upload-category"
              v-model="uploadCategory"
              :disabled="uploading"
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
              :disabled="uploading"
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
      <aside
        class="create-template-options"
        aria-labelledby="create-existing-heading"
      >
        <div class="create-gallery-heading">
          <div>
            <h2 id="create-existing-heading">使用已有模板</h2>
            <p>已有模板无需重新上传，选择后直接填写。</p>
          </div>
        </div>
        <UiButton
          :to="{ path: '/templates', query: { source: 'builtin' } }"
          variant="primary"
          class="full-width"
          >浏览模板库</UiButton
        >
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
              ><RefreshCw :class="{ spin: loadingTemplates }"
            /></UiButton>
          </div>
          <span>已有模板可直接继续填写</span>
        </div>
      </aside>
    </div>

    <UiNotice
      v-if="status"
      :message="status"
      :tone="status.includes('失败') ? 'error' : 'info'"
      class="create-status"
    />
  </section>
</template>
<script setup>
import "../styles/create.css";
import UiNotice from "../components/ui/UiNotice.vue";
import UiPageHeader from "../components/ui/UiPageHeader.vue";
import UiButton from "../components/ui/UiButton.vue";
import { useRouter } from "vue-router";
import {
  ArrowLeft,
  FileText,
  RefreshCw,
  ScanText,
  Upload,
  LoaderCircle,
} from "@lucide/vue";
import { onMounted, ref } from "vue";
import { fetchTemplates, uploadTemplate } from "../api/templates";
const router = useRouter();
const uploadInput = ref(null),
  uploadFile = ref(null),
  uploadName = ref(""),
  uploadCategory = ref("通用"),
  uploadDescription = ref(""),
  uploading = ref(false),
  dragging = ref(false),
  status = ref("");
const templates = ref([]),
  loadingTemplates = ref(false),
  selectedTemplateName = ref("");
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
function focusUpload() {
  uploadInput.value?.focus();
}
function formatBytes(size) {
  return size < 1048576
    ? (size / 1024).toFixed(1) + " KB"
    : (size / 1048576).toFixed(1) + " MB";
}
function handleFileSelect(event) {
  const [file] = event.target.files || [];
  if (file && !/\.docx$/i.test(file.name)) {
    uploadFile.value = null;
    status.value = "上传失败：请选择 .docx 格式的 Word 模板。";
    return;
  }
  uploadFile.value = file || null;
  if (file && !uploadName.value)
    uploadName.value = file.name.replace(/\.docx$/i, "");
}
function dropTemplate(event) {
  dragging.value = false;
  if (!uploading.value)
    handleFileSelect({ target: { files: event.dataTransfer.files } });
}
async function loadTemplates() {
  loadingTemplates.value = true;
  const { data, error } = await fetchTemplates();
  templates.value = data || [];
  if (error) status.value = "加载模板失败：" + error;
  loadingTemplates.value = false;
}
function handleTemplateChange() {
  if (selectedTemplateName.value)
    router.push({
      name: "generate",
      params: { templateId: selectedTemplateName.value },
    });
}
async function handleUpload() {
  if (!uploadFile.value || uploading.value) return;
  uploading.value = true;
  status.value = "";
  try {
    const form = new FormData();
    form.append("template_name", uploadName.value || uploadFile.value.name);
    form.append("file", uploadFile.value);
    form.append("description", uploadDescription.value);
    form.append("category", uploadCategory.value);
    const { data, error } = await uploadTemplate(form);
    if (error || !data?.success) {
      status.value = "上传失败：" + (error || data?.error || "请重试");
      return;
    }
    await router.push({
      name: "generate",
      params: { templateId: data.template_name },
    });
  } finally {
    uploading.value = false;
  }
}
onMounted(loadTemplates);
</script>
