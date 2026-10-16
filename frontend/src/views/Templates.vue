<template>
  <section class="document-workspace templates-page">
    <header class="page-heading">
      <div>
        <h1>文档模板</h1>
        <p>选择或上传 Word 模板，填写变量并生成文档。</p>
      </div>
      <RouterLink to="/create" class="button primary"
        ><Plus :size="16" />上传模板</RouterLink
      >
    </header>
    <section class="catalog-panel" aria-label="模板库">
      <div class="catalog-toolbar">
        <label class="catalog-search"
          ><Search :size="17" /><input
            v-model="searchQuery"
            type="search"
            aria-label="搜索模板"
            placeholder="搜索模板名称或说明…"
            @input="currentPage = 1"
        /></label>
        <span class="catalog-total">{{ filteredTemplates.length }} 个模板</span>
        <div class="view-switch" role="group" aria-label="模板显示方式">
          <button
            class="icon-button"
            :aria-pressed="viewMode === 'grid'"
            aria-label="网格视图"
            @click="viewMode = 'grid'"
          >
            <LayoutGrid :size="17" /></button
          ><button
            class="icon-button"
            :aria-pressed="viewMode === 'list'"
            aria-label="列表视图"
            @click="viewMode = 'list'"
          >
            <List :size="18" />
          </button>
        </div>
      </div>
      <div class="catalog-categories" role="group" aria-label="模板分类">
        <button
          v-for="category in categories"
          :key="category"
          :aria-pressed="selectedCategory === category"
          @click="
            selectedCategory = category;
            currentPage = 1;
          "
        >
          {{ category }}
        </button>
      </div>
      <div v-if="loading" class="document-empty" role="status">
        <LoaderCircle :size="24" class="spin" />
        <p>正在读取模板…</p>
      </div>
      <div v-else-if="loadError" class="document-empty" role="alert">
        <AlertCircle :size="28" />
        <h2>暂时无法读取模板</h2>
        <p>{{ loadError }}</p>
        <button class="button" @click="loadTemplates">
          <RefreshCw :size="15" />重新加载
        </button>
      </div>
      <div v-else-if="!filteredTemplates.length" class="document-empty">
        <Files :size="36" :stroke-width="1.3" />
        <h2>
          {{
            searchQuery || selectedCategory !== "全部"
              ? "没有匹配的模板"
              : "把常用文档，变成可复用的模板"
          }}
        </h2>
        <p>
          {{
            searchQuery || selectedCategory !== "全部"
              ? "换一个关键词或分类，再试一次。"
              : "上传 Word 文件，自动识别变量。每次填写新内容，保留熟悉的文档格式。"
          }}
        </p>
        <button
          v-if="searchQuery || selectedCategory !== '全部'"
          class="button"
          @click="
            searchQuery = '';
            selectedCategory = '全部';
          "
        >
          清除筛选</button
        ><RouterLink v-else to="/create" class="button primary"
          ><Plus :size="15" />创建第一个模板</RouterLink
        >
      </div>
      <div
        v-else
        class="template-catalog"
        :class="{ 'list-view': viewMode === 'list' }"
      >
        <article
          v-for="template in paginatedTemplates"
          :key="template.name"
          class="template-entry"
        >
          <div class="template-sheet" aria-hidden="true">
            <FileText :size="27" :stroke-width="1.3" /><span>DOCX</span>
          </div>
          <div class="template-entry-body">
            <span class="document-tag">{{ template.category || "通用" }}</span>
            <h2>
              <RouterLink
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
              ><RouterLink
                class="text-button"
                :to="{
                  name: 'generate',
                  params: { templateId: template.name },
                }"
                >使用模板<ArrowRight :size="15"
              /></RouterLink>
            </div>
          </div>
        </article>
      </div>
      <footer class="catalog-footer">
        <span>上传的模板保存在当前共享工作区。</span>
        <div v-if="totalPages > 1" class="pagination-controls">
          <button
            class="icon-button"
            aria-label="上一页模板"
            :disabled="currentPage === 1"
            @click="currentPage--"
          >
            <ChevronLeft :size="17" /></button
          ><span>{{ currentPage }} / {{ totalPages }}</span
          ><button
            class="icon-button"
            aria-label="下一页模板"
            :disabled="currentPage === totalPages"
            @click="currentPage++"
          >
            <ChevronRight :size="17" />
          </button>
        </div>
      </footer>
    </section>
    <p class="document-footnote">
      <Info :size="15" />占位符支持 <code>【变量】</code> 和
      <code v-pre>{{ 变量 }}</code
      >，生成后请核对内容与格式。
    </p>
  </section>
</template>
<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
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
} from "@lucide/vue";
import { fetchTemplates } from "../api/templates";
const searchQuery = ref(""),
  selectedCategory = ref("全部"),
  viewMode = ref("grid"),
  currentPage = ref(1),
  templates = ref([]),
  loading = ref(true),
  loadError = ref("");
const categories = [
  "全部",
  "报告",
  "合同",
  "简历",
  "招投标",
  "方案",
  "函件",
  "其他",
];
const filteredTemplates = computed(() =>
  templates.value.filter((template) => {
    const category = template.category || "通用";
    const matchesCategory =
      selectedCategory.value === "全部" ||
      (selectedCategory.value === "其他"
        ? !categories.slice(1, -1).includes(category)
        : category === selectedCategory.value);
    const query = searchQuery.value.trim().toLowerCase();
    return (
      matchesCategory &&
      (!query ||
        [template.name, template.description].some((value) =>
          (value || "").toLowerCase().includes(query),
        ))
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
  const { data, error } = await fetchTemplates();
  if (error) {
    loadError.value = error;
    templates.value = [];
  } else templates.value = data || [];
  loading.value = false;
}
onMounted(loadTemplates);
</script>
