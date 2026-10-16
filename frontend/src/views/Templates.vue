<template>
  <div class="templates-page">
    <!-- Hero Section -->
    <section class="hero-section">
      <div class="hero-content">

        <h1 class="hero-title">文档模板</h1>
        <p class="hero-subtitle">选择或上传 Word 模板，填写变量并生成文档。</p>

        <!-- Search Bar -->
        <div class="search-container">
          <div class="search-box">
            <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="11" cy="11" r="8"/>
              <path d="m21 21-4.35-4.35"/>
            </svg>
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索模板..."
              class="search-input"
              @input="handleSearch"
            />
          </div>
        </div>

        <!-- Category Filter -->
        <div class="category-filter">
          <button
            v-for="cat in categories"
            :key="cat.id"
            :class="['category-btn', { active: selectedCategory === cat.id }]"
            @click="selectCategory(cat.id)"
          >
            <span class="category-icon">{{ cat.icon }}</span>
            <span>{{ cat.name }}</span>
          </button>
        </div>
      </div>
    </section>

    <!-- Templates Grid -->
    <section class="templates-section">
      <div class="section-header">
        <h2>全部模板 <span class="count">({{ filteredTemplates.length }})</span></h2>
        <div class="view-toggle">
          <button :class="['toggle-btn', { active: viewMode === 'grid' }]" aria-label="网格视图" @click="viewMode = 'grid'">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <rect x="3" y="3" width="7" height="7" rx="1"/>
              <rect x="14" y="3" width="7" height="7" rx="1"/>
              <rect x="3" y="14" width="7" height="7" rx="1"/>
              <rect x="14" y="14" width="7" height="7" rx="1"/>
            </svg>
          </button>
          <button :class="['toggle-btn', { active: viewMode === 'list' }]" aria-label="列表视图" @click="viewMode = 'list'">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <rect x="3" y="5" width="18" height="4" rx="1"/>
              <rect x="3" y="13" width="18" height="4" rx="1"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="loading-state">
        <div class="spinner"></div>
        <p>加载模板中...</p>
      </div>

      <p v-if="loadError" role="alert">{{ loadError }}</p>
      <!-- Empty State -->
      <div v-else-if="filteredTemplates.length === 0" class="empty-state">
        <div class="empty-icon">📭</div>
        <h3>暂无模板</h3>
        <p>{{ searchQuery ? '未找到匹配的模板，试试其他关键词' : '还没有可用的模板' }}</p>
        <button class="create-btn" @click="$router.push('/create')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          创建第一个模板
        </button>
      </div>

      <!-- Grid View -->
      <div v-else-if="viewMode === 'grid'" class="templates-grid">
        <div
          v-for="template in paginatedTemplates"
          :key="template.name"
          class="template-card"
          @click="useTemplate(template)"
        >
          <div class="card-header">
            <div class="card-icon">{{ getTemplateIcon(template) }}</div>
            <span class="card-badge">{{ template.category || '通用' }}</span>
          </div>
          <div class="card-body">
            <h3 class="card-title">{{ template.name }}</h3>
            <p class="card-description">{{ template.description || '暂无描述' }}</p>
            <div class="card-footer">
              <div class="template-stats">
                <span class="stat">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                  </svg>
                  {{ template.format || 'DOCX' }}
                </span>
                <span class="stat">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M12 2v20M2 12h20"/>
                  </svg>
                  {{ template.variables?.length || 0 }} 变量
                </span>
              </div>
              <button class="use-btn" @click.stop="useTemplate(template)">
                使用模板
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- List View -->
      <div v-else class="templates-list">
        <div
          v-for="template in paginatedTemplates"
          :key="template.name"
          class="template-list-item"
          @click="useTemplate(template)"
        >
          <div class="list-icon">
            {{ getTemplateIcon(template) }}
          </div>
          <div class="list-content">
            <div class="list-header">
              <h3 class="list-title">{{ template.name }}</h3>
              <span class="category-label">{{ template.category || '通用' }}</span>
            </div>
            <p class="list-description">{{ template.description || '暂无描述' }}</p>
            <div class="template-stats">
              <span class="stat">{{ template.format || 'DOCX' }}</span>
              <span class="divider">•</span>
              <span class="stat">{{ template.variables?.length || 0 }} 个变量</span>
            </div>
          </div>
          <button class="use-btn" @click.stop="useTemplate(template)">
            使用模板
          </button>
        </div>
      </div>

      <!-- Pagination -->
      <div class="pagination" v-if="totalPages > 1">
        <button
          class="page-btn"
          :disabled="currentPage === 1"
          @click="changePage(currentPage - 1)"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </button>

        <button
          v-for="page in displayPages"
          :key="page"
          :class="['page-number', { active: currentPage === page }]"
          @click="changePage(page)"
        >
          {{ page }}
        </button>

        <button
          class="page-btn"
          :disabled="currentPage === totalPages"
          @click="changePage(currentPage + 1)"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </button>
      </div>
    </section>

    <!-- CTA Section -->
    <section class="cta-section">
      <div class="cta-content">
        <h2>需要自定义模板？</h2>
        <p>上传你自己的文档模板，让 AI 帮助你快速生成</p>
        <button class="cta-btn" @click="$router.push('/create')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          上传模板
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { fetchTemplates } from '../api/templates';

const router = useRouter();
const searchQuery = ref('');
const selectedCategory = ref('all');
const viewMode = ref('grid');
const currentPage = ref(1);
const itemsPerPage = 9;
const templates = ref([]);
const loading = ref(true);
const loadError = ref('');

const categories = [
  { id: 'all', name: '全部', icon: '📋' },
  { id: 'report', name: '报告', icon: '📊' },
  { id: 'contract', name: '合同', icon: '📜' },
   { id: 'resume', name: '简历', icon: '👤' },
   { id: 'bidding', name: '招投标', icon: '📑' },
  { id: 'proposal', name: '方案', icon: '💡' },
  { id: 'letter', name: '函件', icon: '✉️' },
  { id: 'other', name: '其他', icon: '📄' }
];

onMounted(async () => {
  await loadTemplates();
});

async function loadTemplates() {
  loading.value = true;
  const { data, error } = await fetchTemplates();
  loading.value = false;

  if (error) {
    loadError.value = `加载模板失败：${error}`;
    templates.value = [];
    return;
  }

  templates.value = data || [];
}

const filteredTemplates = computed(() => {
  let result = templates.value;

  // Category filter
  if (selectedCategory.value !== 'all') {
    result = result.filter(t =>
      (t.category || '').toLowerCase() === getCategoryName(selectedCategory.value).toLowerCase()
    );
  }

  // Search filter
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    result = result.filter(t =>
      t.name.toLowerCase().includes(query) ||
      (t.description && t.description.toLowerCase().includes(query))
    );
  }

  return result;
});

const totalPages = computed(() => Math.ceil(filteredTemplates.value.length / itemsPerPage));

const paginatedTemplates = computed(() => {
  const start = (currentPage.value - 1) * itemsPerPage;
  const end = start + itemsPerPage;
  return filteredTemplates.value.slice(start, end);
});

const displayPages = computed(() => {
  const pages = [];
  const maxDisplay = 5;
  let start = Math.max(1, currentPage.value - Math.floor(maxDisplay / 2));
  let end = Math.min(totalPages.value, start + maxDisplay - 1);

  if (end - start < maxDisplay - 1) {
    start = Math.max(1, end - maxDisplay + 1);
  }

  for (let i = start; i <= end; i++) {
    pages.push(i);
  }

  return pages;
});

function getCategoryName(categoryId) {
  const category = categories.find(c => c.id === categoryId);
  return category ? category.name : '';
}

function getTemplateIcon(template) {
  const categoryIcons = {
    '报告': '📊',
    '合同': '📜',
    '简历': '👤',
    '招投标': '📑',
    '方案': '💡',
    '函件': '✉️'
  };
  return categoryIcons[template.category] || '📄';
}

function selectCategory(categoryId) {
  selectedCategory.value = categoryId;
  currentPage.value = 1;
}

function handleSearch() {
  currentPage.value = 1;
}

function changePage(page) {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

function useTemplate(template) {
  router.push({ name: 'generate', params: { templateId: template.name } });
}
</script>

<style scoped>
.templates-page {
  min-height: 100vh;
  padding-bottom: 60px;
  background: #fff;
  color: #111827;
}

.templates-page :deep(*) {
  color: inherit;
}

.hero-section {
  padding: 60px 20px;
  text-align: center;
  background: #fff;
  border-bottom: 1px solid #f1f5f9;
}

.hero-content {
  max-width: 900px;
  margin: 0 auto;
}

.badge-tag {
  display: inline-flex;
  padding: 8px 20px;
  border-radius: 20px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #1d4ed8;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 24px;
  animation: fadeInUp 0.6s ease;
}

.hero-title {
  font-size: clamp(32px, 5vw, 48px);
  font-weight: 800;
  margin: 0 0 16px;
  color: #111827;
  animation: fadeInUp 0.6s ease 0.1s backwards;
}

.hero-subtitle {
  font-size: 18px;
  color: #4b5563;
  margin: 0 0 40px;
  animation: fadeInUp 0.6s ease 0.2s backwards;
}

.search-container {
  margin: 40px auto 30px;
  max-width: 600px;
  animation: fadeInUp 0.6s ease 0.3s backwards;
}

.search-box {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 20px;
  width: 20px;
  height: 20px;
  color: #64748b;
  stroke-width: 2;
}

.search-input {
  width: 100%;
  padding: 14px 20px 14px 52px;
  background: #fff;
  border: 2px solid #e5e7eb;
  border-radius: 12px;
  color: #111827;
  font-size: 16px;
  transition: all 0.3s ease;
}

.search-input:focus {
  outline: none;
  border-color: #3b82f6;
  background: #fff;
}

.search-input::placeholder {
  color: #94a3b8;
}

.category-filter {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
  animation: fadeInUp 0.6s ease 0.4s backwards;
}

.category-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  color: #111827;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.category-btn:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #111827;
  transform: translateY(-2px);
}

.category-btn.active {
  background: #e5edff;
  border-color: #1d4ed8;
  color: #1d4ed8;
}

.category-icon {
  font-size: 18px;
}

.templates-section {
  padding: 60px 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  flex-wrap: wrap;
  gap: 20px;
}

.section-header h2 {
  font-size: 24px;
  font-weight: 700;
  margin: 0;
  color: #111827;
}

.count {
  color: #6b7280;
  font-size: 18px;
  font-weight: 400;
}

.view-toggle {
  display: flex;
  gap: 6px;
  background: #f3f4f6;
  padding: 6px;
  border-radius: 10px;
}

.toggle-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 8px;
  color: #111827;
  cursor: pointer;
  transition: all 0.3s ease;
}

.toggle-btn svg {
  width: 18px;
  height: 18px;
}

.toggle-btn:hover {
  background: #e5e7eb;
  color: #111827;
}

.toggle-btn.active {
  background: #1d4ed8;
  color: #fff;
}

.loading-state,
.empty-state {
  text-align: center;
  padding: 80px 20px;
}

.spinner {
  width: 48px;
  height: 48px;
  margin: 0 auto 20px;
  border: 4px solid rgba(59, 130, 246, 0.2);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 20px;
}

.empty-state h3 {
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 12px;
  color: #111827;
}

.empty-state p {
  font-size: 16px;
  color: #4b5563;
  margin: 0 0 30px;
}

.create-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  border: none;
  border-radius: 10px;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.create-btn svg {
  width: 18px;
  height: 18px;
  stroke-width: 2.5;
}

.create-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.4);
}

.templates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 24px;
  margin-bottom: 40px;
}

.template-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.3s ease;
  animation: fadeInUp 0.4s ease backwards;
}

.template-card:hover {
  transform: translateY(-4px);
  border-color: #1d4ed8;
  box-shadow: 0 12px 40px rgba(59, 130, 246, 0.15);
}

.card-header {
  padding: 24px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  border-bottom: 1px solid #e5e7eb;
}

.card-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  background: #eef2ff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
}

.card-badge {
  padding: 4px 12px;
  background: #e5edff;
  color: #1d4ed8;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.card-body {
  padding: 24px;
}

.card-title {
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 12px;
  color: #111827;
}

.card-description {
  font-size: 14px;
  color: #4b5563;
  line-height: 1.6;
  margin: 0 0 20px;
  min-height: 42px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
}

.template-stats {
  display: flex;
  gap: 16px;
}

.stat {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #6b7280;
  font-size: 13px;
}

.stat svg {
  width: 14px;
  height: 14px;
  stroke-width: 2;
}

.divider {
  color: #9ca3af;
}

.use-btn {
  padding: 8px 16px;
  background: #111827;
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.use-btn:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
}

/* List View */
.templates-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 40px;
}

.template-list-item {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 20px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.template-list-item:hover {
  border-color: #1d4ed8;
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.12);
  transform: translateX(4px);
}

.list-icon {
  width: 64px;
  height: 64px;
  border-radius: 12px;
  background: #eef2ff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  flex-shrink: 0;
}

.list-content {
  flex: 1;
  min-width: 0;
}

.list-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.list-title {
  font-size: 18px;
  font-weight: 700;
  margin: 0;
  color: #111827;
}

.category-label {
  padding: 4px 10px;
  background: #e5edff;
  color: #1d4ed8;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.list-description {
  font-size: 14px;
  color: #4b5563;
  line-height: 1.6;
  margin: 0 0 12px;
}

/* Pagination */
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  margin-top: 60px;
}

.page-btn,
.page-number {
  min-width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  color: #111827;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.page-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.page-btn:not(:disabled):hover,
.page-number:hover {
  background: #f8fafc;
  border-color: #1d4ed8;
  transform: translateY(-2px);
}

.page-number.active {
  background: #1d4ed8;
  border-color: #1d4ed8;
  color: #fff;
}

.page-btn svg {
  width: 20px;
  height: 20px;
  stroke-width: 2;
}

/* CTA Section */
.cta-section {
  margin-top: 80px;
  padding: 50px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  text-align: center;
  max-width: 1000px;
  margin-left: auto;
  margin-right: auto;
}

.cta-content h2 {
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 12px;
  color: #111827;
}

.cta-content p {
  font-size: 16px;
  color: #4b5563;
  margin: 0 0 28px;
}

.cta-btn {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 14px 28px;
  background: #111827;
  border: none;
  border-radius: 10px;
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.3);
}

.cta-btn:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 32px rgba(59, 130, 246, 0.4);
}

.cta-btn svg {
  width: 20px;
  height: 20px;
  stroke-width: 2.5;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 768px) {
  .hero-section {
    padding: 40px 16px;
  }

  .templates-grid {
    grid-template-columns: 1fr;
  }

  .template-list-item {
    flex-direction: column;
    text-align: center;
  }

  .section-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .cta-section {
    padding: 30px 20px;
  }

  .category-filter {
    gap: 8px;
  }

  .category-btn {
    font-size: 13px;
    padding: 8px 14px;
  }
}
</style>
