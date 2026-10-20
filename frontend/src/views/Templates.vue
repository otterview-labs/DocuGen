<template>
  <section class="document-workspace templates-page">
    <UiPageHeader
      title="文档模板"
      description="从常用文档开始，先看结构，再填写内容。也可以上传自己的 Word 模板。"
      ><template #actions
        ><UiButton to="/create" variant="primary"
          ><Plus :size="16" />上传模板</UiButton
        ></template
      ></UiPageHeader
    >
    <UiNotice v-if="actionError" tone="error" :message="actionError" />
    <section class="catalog-panel" aria-label="模板库">
      <UiTabs
        v-model="source"
        label="模板来源"
        :items="sourceTabs"
        id-prefix="template-source-"
      />
      <div
        :id="'template-source-' + source + '-panel'"
        role="tabpanel"
        :aria-labelledby="'template-source-' + source + '-tab'"
      >
        <div class="catalog-toolbar">
          <label class="catalog-search ui-search-field"
            ><Search :size="17" /><input
              v-model="searchQuery"
              type="search"
              aria-label="搜索模板"
              placeholder="搜索模板名称或说明…"
              @input="currentPage = 1"
          /></label>
          <span class="catalog-total"
            >{{ filteredTemplates.length }} 个模板</span
          >
          <div class="view-switch" role="group" aria-label="模板显示方式">
            <UiButton
              :aria-pressed="viewMode === 'grid'"
              size="compact"
              aria-label="网格视图"
              @click="viewMode = 'grid'"
              variant="ghost"
              icon-only
              ><LayoutGrid :size="17" /></UiButton
            ><UiButton
              :aria-pressed="viewMode === 'list'"
              size="compact"
              aria-label="列表视图"
              @click="viewMode = 'list'"
              variant="ghost"
              icon-only
              ><List :size="18"
            /></UiButton>
          </div>
        </div>
        <section
          v-if="preview"
          id="template-structure"
          ref="previewPanel"
          class="template-structure"
          tabindex="-1"
          aria-label="模板结构预览"
          @keydown.esc.stop="closePreview"
        >
          <div class="template-paper">
            <p class="template-paper-header">{{ preview.name }} · DOCX</p>
            <h2>{{ preview.name }}</h2>
            <TemplateCover class="catalog-page-preview" :template="preview" />
            <details class="preview-structure-details">
              <summary>查看可填写的变量与章节</summary>
              <dl class="template-paper-fields">
                <template v-for="field in preview.fields" :key="field"
                  ><dt>{{ field }}</dt>
                  <dd>{{ placeholder(field) }}</dd></template
                >
              </dl>
              <section v-for="section in preview.sections" :key="section.field">
                <h3>{{ section.title }}</h3>
                <p>{{ placeholder(section.field) }}</p>
              </section>
            </details>
          </div>
          <aside class="template-structure-info">
            <div class="editor-section-heading">
              <h2>模板结构预览</h2>
              <UiButton
                variant="ghost"
                size="compact"
                icon-only
                aria-label="关闭模板预览"
                @click="closePreview"
                ><X
              /></UiButton>
            </div>
            <span class="document-tag"
              >DocuGen 内置 · {{ preview.category }}</span
            >
            <h3>{{ preview.name }}</h3>
            <p>{{ preview.description }}</p>
            <dl class="document-summary">
              <dt>可填写变量</dt>
              <dd>{{ preview.variables.length }} 个</dd>
              <dt>纸张</dt>
              <dd>A4 · 纵向</dd>
              <dt>包含版式</dt>
              <dd>标题、信息表、章节、页眉和页码</dd>
            </dl>
            <UiButton
              variant="primary"
              class="full-width"
              :disabled="!!using"
              @click="useTemplate(preview)"
              ><ArrowRight />{{
                using === preview.id ? "正在添加…" : "使用此模板"
              }}</UiButton
            >
            <UiButton
              class="full-width template-original"
              :disabled="downloading"
              @click="downloadOriginal(preview)"
              ><Download />下载 Word 模板</UiButton
            >
            <p>
              首屏图片展示模板原始版式，变量与章节可展开查看。实际分页与字体以下载文件为准，可在
              Word 中调整版式后重新上传。
            </p>
          </aside>
        </section>
        <div class="catalog-categories" role="group" aria-label="模板分类">
          <UiButton
            variant="ghost"
            size="compact"
            v-for="category in categories"
            :key="category"
            :aria-pressed="selectedCategory === category"
            @click="
              selectedCategory = category;
              currentPage = 1;
            "
          >
            {{ category }}
          </UiButton>
        </div>
        <UiEmptyState
          v-if="loading"
          :icon="LoaderCircle"
          description="正在读取模板…"
          state="loading"
        ></UiEmptyState>
        <UiEmptyState
          v-else-if="loadError"
          :icon="AlertCircle"
          title="暂时无法读取模板"
          :description="loadError"
          state="error"
          heading="h2"
          ><UiButton @click="loadTemplates"
            ><RefreshCw :size="15" />重新加载
          </UiButton></UiEmptyState
        >
        <UiEmptyState
          v-else-if="!filteredTemplates.length"
          :icon="Files"
          :title="
            searchQuery || selectedCategory !== '全部'
              ? '没有匹配的模板'
              : '把常用文档，变成可复用的模板'
          "
          :description="
            searchQuery || selectedCategory !== '全部'
              ? '换一个关键词或分类，再试一次。'
              : '上传 Word 文件，自动识别变量。每次填写新内容，保留熟悉的文档格式。'
          "
          heading="h2"
          ><UiButton
            v-if="searchQuery || selectedCategory !== '全部'"
            @click="
              searchQuery = '';
              selectedCategory = '全部';
            "
          >
            清除筛选</UiButton
          ><UiButton v-else to="/create" variant="primary"
            ><Plus :size="15" />创建第一个模板</UiButton
          ></UiEmptyState
        >
        <div
          v-else
          class="template-catalog"
          :class="{ 'list-view': viewMode === 'list' }"
        >
          <article
            v-for="template in paginatedTemplates"
            :key="
              template.origin === 'builtin'
                ? 'builtin-' + template.id
                : template.id
            "
            class="template-entry"
          >
            <button
              v-if="template.origin === 'builtin'"
              class="template-cover-trigger"
              :aria-label="'查看' + template.name + '版式预览'"
              :aria-expanded="preview?.id === template.id"
              aria-controls="template-structure"
              @click="openPreview(template, $event)"
            >
              <TemplateCover :template="template" decorative /><span
                >查看版式预览</span
              >
            </button>
            <div v-else class="template-sheet" aria-hidden="true">
              <FileText :size="27" :stroke-width="1.3" /><span>DOCX</span>
            </div>
            <div class="template-entry-body">
              <span class="document-tag"
                >{{ template.category || "通用" }} ·
                {{
                  template.origin === "builtin" ? "内置模板" : "工作区模板"
                }}</span
              >
              <h2>
                <template v-if="template.origin === 'builtin'">{{
                  template.name
                }}</template>
                <RouterLink
                  v-else
                  :to="{
                    name: 'generate',
                    params: { templateId: template.name },
                  }"
                  >{{ template.name }}</RouterLink
                >
              </h2>
              <p>
                {{ template.description || "填写模板变量，生成 Word 文档。" }}
              </p>
              <div class="template-entry-footer">
                <span>{{ template.variables?.length || 0 }} 个变量</span
                ><UiButton
                  v-if="template.origin === 'builtin'"
                  variant="text"
                  size="compact"
                  :aria-label="'预览' + template.name"
                  :aria-expanded="preview?.id === template.id"
                  aria-controls="template-structure"
                  @click="openPreview(template, $event)"
                  >查看结构</UiButton
                >
                <UiButton
                  v-if="template.origin === 'builtin'"
                  variant="primary"
                  size="compact"
                  :disabled="!!using"
                  :aria-label="'使用' + template.name"
                  @click="useTemplate(template)"
                  >{{ using === template.id ? "正在添加…" : "使用模板"
                  }}<ArrowRight
                /></UiButton>
                <UiButton
                  v-else
                  :to="{
                    name: 'generate',
                    params: { templateId: template.name },
                  }"
                  variant="primary"
                  size="compact"
                  >使用模板<ArrowRight :size="15"
                /></UiButton>
              </div>
            </div>
          </article>
        </div>
        <footer class="catalog-footer">
          <span
            >内置模板可直接填写；上传和已使用的模板保存在当前共享工作区。</span
          >
          <div v-if="totalPages > 1" class="pagination-controls">
            <UiButton
              aria-label="上一页模板"
              :disabled="currentPage === 1"
              @click="currentPage--"
              variant="ghost"
              icon-only
              ><ChevronLeft :size="17" /></UiButton
            ><span>{{ currentPage }} / {{ totalPages }}</span
            ><UiButton
              aria-label="下一页模板"
              :disabled="currentPage === totalPages"
              @click="currentPage++"
              variant="ghost"
              icon-only
              ><ChevronRight :size="17"
            /></UiButton>
          </div>
        </footer>
      </div>
    </section>
    <p class="document-footnote">
      <Info :size="15" />占位符支持 <code>【变量】</code> 和
      <code v-pre>{{ 变量 }}</code
      >，生成后请核对内容与格式。
    </p>
  </section>
</template>
<script setup>
import TemplateCover from "../components/TemplateCover.vue";
import UiEmptyState from "../components/ui/UiEmptyState.vue";
import UiPageHeader from "../components/ui/UiPageHeader.vue";
import UiButton from "../components/ui/UiButton.vue";
import UiNotice from "../components/ui/UiNotice.vue";
import UiTabs from "../components/ui/UiTabs.vue";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import {
  AlertCircle,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Files,
  FileText,
  Info,
  LayoutGrid,
  List,
  LoaderCircle,
  Plus,
  RefreshCw,
  Search,
  X,
  Download,
} from "@lucide/vue";
import {
  fetchTemplates,
  fetchTemplateLibrary,
  useLibraryTemplate,
} from "../api/templates";
import { downloadFile } from "../api/client";
const router = useRouter(),
  route = useRoute();
const source = ref(route.query.source === "builtin" ? "builtin" : "all");
const library = ref([]),
  preview = ref(null),
  previewPanel = ref(null),
  using = ref(""),
  downloading = ref(false),
  actionError = ref("");
let previewTrigger;
const sourceTabs = computed(() => [
  {
    value: "all",
    label: "全部模板",
    count: templates.value.length + library.value.length,
  },
  { value: "builtin", label: "内置模板", count: library.value.length },
  { value: "workspace", label: "工作区模板", count: templates.value.length },
]);
const placeholder = (field) => "{{ " + field + " }}";
async function openPreview(template, event) {
  previewTrigger = event.currentTarget;
  preview.value = template;
  await nextTick();
  previewPanel.value?.focus();
  previewPanel.value?.scrollIntoView({ block: "start", behavior: "instant" });
}
function closePreview() {
  preview.value = null;
  nextTick(() => previewTrigger?.focus());
}
async function useTemplate(template) {
  using.value = template.id;
  actionError.value = "";
  const { data, error } = await useLibraryTemplate(template.id);
  using.value = "";
  if (error) {
    actionError.value = error;
    return;
  }
  router.push({ name: "generate", params: { templateId: data.name } });
}
async function downloadOriginal(template) {
  downloading.value = true;
  actionError.value = "";
  try {
    await downloadFile(
      `/api/template-library/${encodeURIComponent(template.id)}/download`,
      template.name + ".docx",
    );
  } catch (error) {
    actionError.value = error.message || "模板下载失败，请重试。";
  } finally {
    downloading.value = false;
  }
}
const searchQuery = ref(typeof route.query.q === "string" ? route.query.q : ""),
  selectedCategory = ref("全部"),
  viewMode = ref("grid"),
  currentPage = ref(1),
  templates = ref([]),
  loading = ref(true),
  loadError = ref("");
const visibleTemplates = computed(() =>
  source.value === "builtin"
    ? library.value
    : source.value === "workspace"
      ? templates.value
      : [...templates.value, ...library.value],
);
const categories = computed(() => [
  "全部",
  ...new Set(visibleTemplates.value.map((t) => t.category || "通用")),
]);
watch(source, () => {
  currentPage.value = 1;
  selectedCategory.value = "全部";
  preview.value = null;
});
const filteredTemplates = computed(() =>
  visibleTemplates.value.filter((template) => {
    const category = template.category || "通用";
    const matchesCategory =
      selectedCategory.value === "全部" || category === selectedCategory.value;
    const query = searchQuery.value.trim().toLowerCase();
    return (
      matchesCategory &&
      (!query ||
        [
          template.name,
          template.description,
          ...(template.variables || []).map((v) => v.name),
        ].some((value) => (value || "").toLowerCase().includes(query)))
    );
  }),
);
const totalPages = computed(() =>
  Math.ceil(filteredTemplates.value.length / 9),
);
const paginatedTemplates = computed(() =>
  filteredTemplates.value.slice(
    (currentPage.value - 1) * 9,
    currentPage.value * 9,
  ),
);
async function loadTemplates() {
  loading.value = true;
  loadError.value = "";
  const [workspace, builtin] = await Promise.all([
    fetchTemplates(),
    fetchTemplateLibrary(),
  ]);
  templates.value = workspace.data || [];
  library.value = builtin.data || [];
  loadError.value = workspace.error || builtin.error || "";
  loading.value = false;
}
onMounted(loadTemplates);
</script>
