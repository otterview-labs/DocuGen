<template>
  <section
    v-for="group in groups"
    :key="group.title"
    class="template-field-group"
  >
    <h3>
      {{ group.title }}<span>{{ group.fields.length }} 项</span>
    </h3>
    <div class="variables-grid">
      <label
        v-for="variable in group.fields"
        :key="variable.name"
        class="field-label"
        :class="{ 'long-template-field': kind(variable) === 'long' }"
        :for="'template-field-' + variables.indexOf(variable)"
      >
        {{ variable.name }}
        <textarea
          v-if="kind(variable) === 'long'"
          :id="'template-field-' + variables.indexOf(variable)"
          class="field-input"
          :value="modelValue[variable.name]"
          :disabled="disabled"
          :placeholder="variable.description || '填写' + variable.name"
          rows="4"
          @input="update(variable.name, $event.target.value)"
        />
        <input
          v-else
          :id="'template-field-' + variables.indexOf(variable)"
          class="field-input"
          :type="kind(variable) === 'date' ? 'date' : 'text'"
          :value="modelValue[variable.name]"
          :disabled="disabled"
          :placeholder="variable.description || '填写' + variable.name"
          @input="update(variable.name, $event.target.value)"
        />
      </label>
    </div>
  </section>
</template>
<script setup>
import { computed, ref, watch } from "vue";
import { templateFieldKind } from "../../composables/templateFields";
const props = defineProps({
  variables: { type: Array, default: () => [] },
  modelValue: { type: Object, required: true },
  disabled: Boolean,
  revision: { type: Number, default: 0 },
});
const emit = defineEmits(["update:modelValue"]);
// Choose a safe representation for loaded/restored/external values, then keep
// the DOM node and its group stable while the user is typing.
const modes = ref({});
watch(
  [() => props.variables, () => props.revision],
  () => {
    modes.value = Object.fromEntries(
      props.variables.map((variable) => [
        variable.name,
        templateFieldKind(variable, props.modelValue[variable.name]),
      ]),
    );
  },
  { immediate: true, flush: "sync" },
);
const kind = (variable) => modes.value[variable.name] || "long";
const groups = computed(() =>
  [
    {
      title: "基本信息",
      fields: props.variables.filter((v) => kind(v) !== "long"),
    },
    {
      title: "正文内容",
      fields: props.variables.filter((v) => kind(v) === "long"),
    },
  ].filter((g) => g.fields.length),
);
function update(name, value) {
  emit("update:modelValue", { ...props.modelValue, [name]: value });
}
</script>
