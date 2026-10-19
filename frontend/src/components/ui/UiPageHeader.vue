<template>
  <header class="page-heading">
    <div class="page-heading-copy">
      <h1>{{ title }}</h1>
      <p v-if="description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="heading-actions">
      <slot name="actions" />
    </div>
  </header>
</template>
<script setup>
defineProps({ title: { type: String, required: true }, description: String });
</script>
