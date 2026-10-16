<template>
  <div
    class="ui-notice"
    :class="`ui-notice--${resolvedTone}`"
    :role="resolvedTone === 'error' ? 'alert' : 'status'"
  >
    <component
      :is="
        resolvedTone === 'error'
          ? AlertCircle
          : resolvedTone === 'success'
            ? CheckCircle2
            : Info
      "
      :size="18"
    /><span
      ><slot>{{ message }}</slot></span
    ><UiButton
      v-if="dismissible"
      icon-only
      size="compact"
      variant="ghost"
      aria-label="关闭提示"
      @click="$emit('dismiss')"
      ><X
    /></UiButton>
  </div>
</template>
<script setup>
import { computed } from "vue";
import { AlertCircle, CheckCircle2, Info, X } from "@lucide/vue";
import UiButton from "./UiButton.vue";
const props = defineProps({
  message: String,
  tone: { type: String, default: "auto" },
  dismissible: Boolean,
});
defineEmits(["dismiss"]);
const resolvedTone = computed(() =>
  props.tone !== "auto"
    ? props.tone
    : /失败|错误|无法|未配置|不可用/.test(props.message || "")
      ? "error"
      : /成功|已完成|已生成|已保存/.test(props.message || "")
        ? "success"
        : "info",
);
</script>
