<template>
  <div
    class="ui-empty"
    :class="{ 'ui-empty--compact': compact }"
    :role="
      state === 'error' ? 'alert' : state === 'loading' ? 'status' : undefined
    "
  >
    <component
      v-if="icon"
      :is="icon"
      class="ui-empty-icon"
      :class="{ spin: state === 'loading' }"
      :size="32"
      :stroke-width="1.6"
    /><component v-if="title" :is="heading">{{ title }}</component>
    <p v-if="description">{{ description }}</p>
    <div v-if="$slots.default" class="ui-empty-actions"><slot /></div>
  </div>
</template>
<script setup>
defineProps({
  title: String,
  description: String,
  icon: [Object, Function],
  heading: { type: String, default: "h3" },
  state: { type: String, default: "empty" },
  compact: Boolean,
});
</script>
