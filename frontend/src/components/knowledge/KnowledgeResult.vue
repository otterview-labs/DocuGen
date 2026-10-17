<template>
  <div class="knowledge-result-tree">
    <template v-if="value === null || value === undefined"
      ><span class="muted">暂无</span></template
    >
    <template v-else-if="typeof value === 'boolean'">{{
      value ? "是" : "否"
    }}</template>
    <template v-else-if="typeof value !== 'object'"
      ><span class="result-prose">{{ displayValue }}</span></template
    >
    <template v-else-if="Array.isArray(value)">
      <p v-if="!value.length" class="muted">暂无记录</p>
      <ol v-else class="result-records">
        <li v-for="(item, index) in value" :key="index">
          <KnowledgeResult :value="item" />
        </li>
      </ol>
    </template>
    <template v-else>
      <dl class="result-properties">
        <div
          v-for="[key, item] in visibleEntries"
          :key="key"
          class="result-property"
        >
          <dt>{{ labels[key] || key }}</dt>
          <dd><KnowledgeResult :value="item" :field-key="key" /></dd>
        </div>
      </dl>
      <details v-if="technicalEntries.length" class="result-technical">
        <summary>编号与补充信息</summary>
        <dl class="result-properties">
          <div
            v-for="[key, item] in technicalEntries"
            :key="key"
            class="result-property"
          >
            <dt>{{ labels[key] || key }}</dt>
            <dd><KnowledgeResult :value="item" :field-key="key" /></dd>
          </div>
        </dl>
      </details>
    </template>
  </div>
</template>
<script setup>
import { computed } from "vue";
const props = defineProps({ value: null, fieldKey: String });
const technicalKeys = new Set([
  "resource_id",
  "content_id",
  "collection_id",
  "file_sha256",
  "md5",
  "sha256",
  "bindings",
  "metadata",
  "debug",
  "timestamp",
]);
const entries = computed(() =>
  Object.entries(props.value || {}).filter(
    ([key]) => !["embedding", "vector"].includes(key),
  ),
);
function technical(key, value) {
  return (
    technicalKeys.has(key) ||
    (key === "id" &&
      typeof value === "string" &&
      /^[a-f0-9-]{24,}$/.test(value))
  );
}
const visibleEntries = computed(() =>
  entries.value.filter(([key, value]) => !technical(key, value)),
);
const technicalEntries = computed(() =>
  entries.value.filter(([key, value]) => technical(key, value)),
);
const displayValue = computed(() => {
  if (!["status", "action", "new_status"].includes(props.fieldKey))
    return props.value;
  return (
    {
      started: "已提交",
      processing: "处理中",
      pending: "等待处理",
      completed: "已完成",
      failed: "失败",
      success: "成功",
      enable: "启用",
      disable: "停用",
      0: "停用",
      1: "启用",
    }[props.value] ?? props.value
  );
});
const labels = {
  title: "标题",
  name: "名称",
  content: "正文",
  text: "文字",
  summary: "摘要",
  tags: "标签",
  description: "说明",
  message: "说明",
  total: "总数",
  count: "数量",
  success: "成功",
  failed: "失败",
  success_count: "成功数",
  failed_count: "失败数",
  failed_items: "失败记录",
  items: "记录",
  results: "检索结果",
  result: "结果",
  data: "内容",
  details: "逐项结果",
  index: "序号",
  reason: "原因",
  status: "状态",
  indexed: "向量索引",
  chunks: "存储分块",
  characters: "字符数",
  start: "起始位置",
  end: "结束位置",
  strategy: "分块策略",
  embedding_model: "向量模型",
  rerank_model: "重排序模型",
  collection_type: "知识库类型",
  collection_id: "知识库编号",
  content_id: "内容编号",
  resource_id: "资料编号",
  id: "编号",
  vector_indexed: "向量索引已建立",
  duplicate: "重复资料",
  content_type: "内容类型",
  version: "版本",
  file_name: "文件名",
  size: "大小（字节）",
  url: "文件地址",
  batch_id: "解析任务编号",
  progress: "进度",
  entities: "实体",
  relations: "关系",
  nodes: "实体节点",
  edges: "关系边",
  links: "关系",
  source: "起点",
  target: "终点",
  type: "类型",
  label: "名称",
  relation: "关系",
  confidence: "置信度",
  properties: "属性",
  metadata: "元数据",
  statistics: "统计",
  entity_count: "实体数",
  relation_count: "关系数",
  node_count: "节点数",
  edge_count: "关系数",
  answer: "回答",
  citations: "来源引用",
  snippet: "引用片段",
  score: "相关性",
  similarity_score: "相关性",
  search_mode: "检索模式",
  query: "查询",
  methods: "检索方法",
  mode: "模式",
  features: "特性",
  examples: "示例",
  use_case: "适用场景",
  recommendation: "使用建议",
  recommended: "推荐",
  expected_result: "预期结果",
  strategies: "策略",
  default_config: "默认参数",
  config: "配置",
  supported_formats: "支持格式",
  formats: "格式",
  deleted_collection_id: "已删除知识库",
  deleted_documents_count: "已删除资料数",
  failed_documents_count: "删除失败数",
  filename: "文件名",
  vector_count: "向量数",
  total_targets: "目标数",
  action: "操作",
  new_status: "新状态",
  created_at: "创建时间",
  updated_at: "更新时间",
  create_time: "创建时间",
  update_time: "更新时间",
  parsed: "已解析",
  completed: "已完成",
  pending: "等待处理",
  errors: "错误",
  tasks: "任务",
  cleanup_pending: "存在待清理项",
};
</script>
