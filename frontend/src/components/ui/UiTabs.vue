<template>
  <div class="ui-tabs" role="tablist" :aria-label="label">
    <button
      v-for="(item, index) in items"
      :key="item.value"
      :ref="(element) => (buttons[index] = element)"
      :id="idPrefix + item.value + '-tab'"
      role="tab"
      :aria-controls="idPrefix + item.value + '-panel'"
      :aria-selected="modelValue === item.value"
      :tabindex="modelValue === item.value ? 0 : -1"
      @click="$emit('update:modelValue', item.value)"
      @keydown="navigate($event, index)"
    >
      <component v-if="item.icon" :is="item.icon" :size="16" /><span>{{
        item.label
      }}</span
      ><small v-if="item.count !== undefined">{{ item.count }}</small>
    </button>
  </div>
</template>
<script setup>
import { nextTick, ref } from "vue";
const props = defineProps({
  modelValue: String,
  items: { type: Array, required: true },
  label: { type: String, required: true },
  idPrefix: { type: String, default: "" },
});
const emit = defineEmits(["update:modelValue"]);
const buttons = ref([]);
function navigate(event, index) {
  let next = index;
  if (event.key === "ArrowRight") next = (index + 1) % props.items.length;
  else if (event.key === "ArrowLeft")
    next = (index + props.items.length - 1) % props.items.length;
  else if (event.key === "Home") next = 0;
  else if (event.key === "End") next = props.items.length - 1;
  else return;
  event.preventDefault();
  emit("update:modelValue", props.items[next].value);
  nextTick(() => buttons.value[next]?.focus());
}
</script>
