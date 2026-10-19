import { api, handleError } from "./client";

export async function fetchTemplateLibrary() {
  try {
    const res = await api.get("/api/template-library");
    return { data: res.data.templates || [] };
  } catch (error) {
    return { error: handleError(error) };
  }
}

export async function useLibraryTemplate(id) {
  try {
    const res = await api.post(`/api/template-library/${encodeURIComponent(id)}/use`);
    return { data: res.data.template };
  } catch (error) {
    return { error: handleError(error) };
  }
}

export async function fetchTemplates() {
  try {
    const res = await api.get("/api/templates");
    return { data: res.data.templates || [] };
  } catch (error) {
    return { error: handleError(error) };
  }
}

export async function uploadTemplate(formData) {
  try {
    const res = await api.post("/api/upload-template", formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });
    return { data: res.data };
  } catch (error) {
    return { error: handleError(error) };
  }
}

export async function fetchTemplateVariables(templateName, { refresh = false } = {}) {
  try {
    const res = refresh
      ? await api.post("/api/refresh-template-variables", new URLSearchParams({ template_name: templateName }))
      : await api.get("/api/get-template-variables", { params: { template_name: templateName } });
    return { data: res.data.variables || [] };
  } catch (error) {
    return { error: handleError(error) };
  }
}

export async function aiFillVariables(payload) {
  try {
    const res = await api.post("/api/ai-fill-template-variables", payload, {
      timeout: 180000,
    });

    if (res.data?.success === false && res.data?.error) {
      return { error: res.data.error };
    }

    return { data: res.data };
  } catch (error) {
    return { error: handleError(error) };
  }
}

export async function generateFromTemplate(templateName, values, sources = []) {
  try {
    const res = await api.post(
      "/api/generate-from-template",
      new URLSearchParams({
        template_name: templateName,
        data: JSON.stringify(values || {}),
        sources: JSON.stringify(sources)
      }),
      { headers: { "Content-Type": "application/x-www-form-urlencoded" } }
    );
    return { data: res.data };
  } catch (error) {
    return { error: handleError(error) };
  }
}

export async function fetchKnowledgeBases() {
  try {
    const res = await api.get("/api/kb/list");

    if (res.data?.success === false && res.data?.error) {
      return { error: res.data.error };
    }

    const list = res.data?.data;
    if (!Array.isArray(list)) return { data: [] };

    const normalized = list.map((item) => {
      if (typeof item === "string") return { id: item, name: item };
      if (item && typeof item === "object") {
        const name = item.name ?? item.id ?? String(item);
        const id = item.id ?? item.name ?? name;
        return { id, name };
      }
      const str = String(item);
      return { id: str, name: str };
    });

    return { data: normalized };
  } catch (error) {
    return { error: handleError(error) };
  }
}
