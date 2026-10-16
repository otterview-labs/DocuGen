<template>
  <div class="quill-shell">
    <aside class="app-sidebar" aria-label="主导航">
      <RouterLink to="/knowledge" class="quill-brand" aria-label="Quill 首页">
        <span class="quill-symbol"
          ><Feather :size="24" :stroke-width="1.5"
        /></span>
        <span class="brand-copy"
          ><strong>Quill<span class="brand-period">.</span></strong
          ><small>知识与文档工作台</small></span
        >
      </RouterLink>
      <nav class="workspace-nav" aria-label="工作台导航">
        <RouterLink
          v-for="item in navigation"
          :key="item.path"
          :to="item.path"
          :aria-label="item.label"
        >
          <component :is="item.icon" :size="19" :stroke-width="1.7" /><span>{{
            item.label
          }}</span>
          <ChevronRight class="nav-indicator" :size="14" />
        </RouterLink>
      </nav>
      <div class="sidebar-note">
        <BookOpen :size="18" />
        <p>从资料出发，<br />写出有依据的内容。</p>
      </div>
      <div class="sidebar-bottom">
        <div class="workspace-identity">
          <span class="workspace-avatar">O</span
          ><span
            ><strong>Otterview Labs</strong><small>本地共享工作区</small></span
          >
        </div>
        <details class="connection-settings">
          <summary>
            <Settings :size="17" /><span>连接设置</span
            ><ChevronDown :size="14" />
          </summary>
          <form @submit.prevent="saveKey" class="connection-form">
            <label
              >访问密钥<input
                class="field-input"
                type="password"
                v-model="accessKey"
                autocomplete="off"
                placeholder="输入工作区访问密钥"
            /></label>
            <p>保存在当前标签页中。共享工作区内的资料对持有密钥的成员可见。</p>
            <UiButton type="submit" variant="primary" size="compact"
              >保存并连接</UiButton
            >
          </form>
        </details>
      </div>
    </aside>
    <div class="app-frame">
      <header class="workspace-bar">
        <div class="breadcrumbs">
          <span>工作区</span><ChevronRight :size="13" /><strong>{{
            pageTitle
          }}</strong>
        </div>
        <div class="workspace-bar-actions">
          <span class="model-state" :class="{ ready: modelConfigured }"
            ><span class="status-dot"></span
            >{{
              modelConfigured === null
                ? "未连接工作区"
                : modelConfigured
                  ? "生成模型已配置"
                  : "生成模型未配置"
            }}</span
          ><a href="/docs" target="_blank" rel="noopener" class="docs-link"
            >API 文档 <ArrowUpRight :size="14"
          /></a>
        </div>
      </header>
      <main id="main-content" class="app-content"><RouterView /></main>
    </div>
  </div>
</template>
<script setup>
import UiButton from "./components/ui/UiButton.vue";
import { computed, onMounted, ref } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
import {
  ArrowUpRight,
  BookOpen,
  ChevronDown,
  ChevronRight,
  Feather,
  Library,
  LayoutTemplate,
  PenLine,
  Settings,
  Upload,
} from "@lucide/vue";
import { api } from "./api/client";
import "./styles/workbench.css";
import "./styles/documents.css";
import "./styles/ui.css";
const route = useRoute();
const accessKey = ref(sessionStorage.getItem("quill-key") || "");
const modelConfigured = ref(null);
const navigation = [
  { path: "/knowledge", label: "知识库", icon: Library },
  { path: "/writing", label: "文档写作", icon: PenLine },
  { path: "/templates", label: "文档模板", icon: LayoutTemplate },
  { path: "/create", label: "上传模板", icon: Upload },
];
const pageTitle = computed(() => route.meta.title || "文档模板");
function saveKey() {
  sessionStorage.setItem("quill-key", accessKey.value);
  window.location.reload();
}
onMounted(async () => {
  try {
    modelConfigured.value = (
      await api.get("/api/v1/status")
    ).data.model_configured;
  } catch {
    /* Each workspace screen shows its own actionable connection error. */
  }
});
</script>
