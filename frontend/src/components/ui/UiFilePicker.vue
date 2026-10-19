<template>
  <div
    class="ui-file-picker"
    :class="{
      'ui-file-picker--dragging': dragging,
      'ui-file-picker--selected': modelValue,
    }"
  >
    <input
      ref="input"
      type="file"
      :aria-label="label"
      :accept="accept"
      :required="required"
      :disabled="disabled"
      @change="select($event.target.files[0])"
      @dragover.prevent="dragging = true"
      @dragleave="dragging = false"
      @drop.prevent="drop"
    />
    <component
      :is="modelValue ? FileText : Upload"
      :size="24"
      aria-hidden="true"
    />
    <div class="ui-file-picker-copy">
      <strong>{{
        modelValue ? modelValue.name : "选择文件，或拖放到这里"
      }}</strong>
      <span>{{
        modelValue ? formatBytes(modelValue.size) + " · 点击可更换文件" : hint
      }}</span>
    </div>
    <Check v-if="modelValue" :size="18" aria-hidden="true" />
  </div>
</template>
<script setup>
import { ref, watch } from "vue";
import { Check, FileText, Upload } from "@lucide/vue";
const props = defineProps({
  modelValue: { default: null },
  label: { type: String, default: "选择文件" },
  accept: String,
  required: Boolean,
  disabled: Boolean,
  hint: { type: String, default: "保留原文件，按所选方式处理。" },
});
const emit = defineEmits(["update:modelValue"]);
const input = ref(null),
  dragging = ref(false);
watch(
  () => props.modelValue,
  (value) => {
    if (!value && input.value) input.value.value = "";
  },
);
function formatBytes(size) {
  return size < 1024
    ? size + " B"
    : size < 1048576
      ? (size / 1024).toFixed(1) + " KB"
      : (size / 1048576).toFixed(1) + " MB";
}
function select(file) {
  dragging.value = false;
  emit("update:modelValue", file || null);
}
function drop(event) {
  dragging.value = false;
  if (input.value.matches(":disabled")) return;
  const file = event.dataTransfer.files[0];
  if (!file) return;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  input.value.files = transfer.files;
  select(file);
}
</script>
