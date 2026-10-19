<template>
  <component
    :is="to ? RouterLink : href ? 'a' : 'button'"
    ref="element"
    v-bind="to ? { to } : href ? { href } : { type }"
    class="ui-button"
    :class="[
      `ui-button--${variant}`,
      `ui-button--${size}`,
      { 'ui-button--icon': iconOnly },
    ]"
  >
    <slot />
  </component>
</template>
<script setup>
import { ref } from "vue";
import { RouterLink } from "vue-router";
defineProps({
  to: [String, Object],
  href: String,
  type: { type: String, default: "button" },
  variant: { type: String, default: "secondary" },
  size: { type: String, default: "default" },
  iconOnly: Boolean,
});
const element = ref(null);
defineExpose({
  focus: () => {
    const target = element.value?.$el || element.value;
    target?.focus();
  },
});
</script>
