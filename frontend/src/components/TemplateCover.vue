<template>
  <div class="template-cover">
    <img
      v-if="!failed"
      :src="`/template-previews/${template.id}.png`"
      :alt="decorative ? '' : template.name + ' Word 版式预览'"
      width="420"
      height="594"
      loading="lazy"
      decoding="async"
      @error="failed = true"
    />
    <div v-else class="template-cover-fallback">
      <strong>{{ template.name }}</strong>
      <span
        v-for="section in template.sections.slice(0, 3)"
        :key="section.title"
        >{{ section.title }}</span
      >
      <small>图片暂不可用 · 仍可查看结构和使用模板</small>
    </div>
  </div>
</template>
<script setup>
import { ref, watch } from "vue";
const props = defineProps({
  template: { type: Object, required: true },
  decorative: Boolean,
});
const failed = ref(false);
watch(
  () => props.template.id,
  () => {
    failed.value = false;
  },
);
</script>
<style scoped>
.template-cover {
  width: 100%;
  height: var(--template-cover-height, 220px);
  overflow: hidden;
  padding: 18px 26px 0;
  background: var(--ground);
  border: 1px solid var(--line);
  border-radius: var(--radius-control);
}
.template-cover img {
  display: block;
  width: 100%;
  height: auto;
  background: white;
  border: 1px solid var(--line);
}
.template-cover-fallback {
  display: grid;
  gap: 14px;
  padding: 18px;
  background: var(--paper);
  font-size: var(--font-meta);
  color: var(--muted);
}
.template-cover-fallback strong {
  color: var(--ink);
}
@media (max-width: 640px) {
  .template-cover {
    padding: 12px 16px 0;
  }
}
</style>
