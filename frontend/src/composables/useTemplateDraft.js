import { ref, watch } from "vue";
export function useTemplateDraft(identity, variables, values, context) {
  const key = "quill-template-draft:v1:" + encodeURIComponent(identity);
  const message = ref("填写后自动暂存到当前标签页"),
    warning = ref(false);
  let ready = false;
  const snapshot = () => ({
    version: 1,
    values: { ...values },
    reference: context.reference.value,
    enableRag: context.enableRag.value,
    knowledgeBase: context.knowledgeBase.value,
    sources: context.sources.value,
  });
  function restore() {
    try {
      const draft = JSON.parse(sessionStorage.getItem(key) || "null");
      if (
        draft?.version === 1 &&
        draft.values &&
        typeof draft.values === "object" &&
        !Array.isArray(draft.values)
      ) {
        for (const variable of variables.value) {
          const value = draft.values[variable.name];
          if (typeof value === "string" || typeof value === "number")
            values[variable.name] = String(value);
        }
        context.reference.value =
          typeof draft.reference === "string" ? draft.reference : "";
        context.enableRag.value = draft.enableRag === true;
        context.knowledgeBase.value =
          typeof draft.knowledgeBase === "string" ? draft.knowledgeBase : "";
        context.sources.value = Array.isArray(draft.sources)
          ? draft.sources
          : [];
        message.value = "已恢复当前标签页的草稿";
      }
    } catch {
      message.value = "无法恢复草稿，可继续填写和导出";
      warning.value = true;
    }
    ready = true;
  }
  watch(
    snapshot,
    () => {
      if (!ready) return;
      try {
        sessionStorage.setItem(key, JSON.stringify(snapshot()));
        message.value = "草稿已保存在当前标签页";
        warning.value = false;
      } catch {
        message.value = "无法暂存草稿，请及时生成并下载文档";
        warning.value = true;
      }
    },
    { deep: true, flush: "sync" },
  );
  return { restore, message, warning };
}
