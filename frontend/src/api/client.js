import axios from "axios";

const apiBase = import.meta.env.VITE_API_BASE || "";

export const api = axios.create({
  baseURL: apiBase,
  timeout: 20000
});

api.interceptors.request.use((config) => {
  const key = sessionStorage.getItem('quill-key');
  if (key) config.headers.Authorization = `Bearer ${key}`;
  return config;
});

export async function downloadFile(url, filename) {
  try {
    const response = await api.get(url, { responseType: 'blob' });
    const blobUrl = URL.createObjectURL(response.data);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = filename || url.split('/').pop();
    link.click();
    setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
  } catch (error) {
    window.alert(`下载失败：${handleError(error)}`);
  }
}

export function handleError(error) {
  if (error.response?.data?.detail) {
    const detail = error.response.data.detail;
    return typeof detail === 'string' ? detail : '请求内容不完整，请检查填写项。';
  }
  if (error.response?.data?.error) return error.response.data.error;
  if (error.message) return error.message;
  return "请求失败";
}
