<template>
  <section class="document-workspace writing-page">
    <UiPageHeader
      title="文档写作"
      description="选择资料，确认章节，生成可下载的 Word 文档。生成内容仍需人工核对。"
      ><template #actions
        ><UiButton to="/knowledge"
          ><Library :size="16" />整理参考资料</UiButton
        ></template
      ></UiPageHeader
    >
    <UiNotice v-if="message" :message="message" />
    <div class="document-editor writing-editor">
      <form class="editor-main" @submit.prevent="generate">
        <section class="editor-section">
          <div class="editor-section-heading">
            <div>
              <h2>文档要求</h2>
              <p>明确主题与参考范围，再组织章节。</p>
            </div>
            <PenLine :size="19" />
          </div>
          <div class="writing-fields">
            <label class="field-label"
              >文档主题<input
                v-model="topic"
                class="field-input"
                required
                maxlength="500"
                placeholder="例如：园区设备运维方案" /></label
            ><label class="field-label"
              >参考知识库<select v-model="selected" class="field-input">
                <option value="">仅使用手动参考资料</option>
                <option
                  v-for="collection in collections"
                  :key="collection.id"
                  :value="collection.id"
                >
                  {{ collection.name }}
                </option>
              </select></label
            ><label class="field-label"
              >手动参考资料<textarea
                v-model="reference"
                class="field-input"
                rows="4"
                maxlength="12000"
                placeholder="项目事实、约束与需要引用的资料"
              /></label
            ><label class="field-label"
              >写作要求<textarea
                v-model="instructions"
                class="field-input"
                rows="2"
                maxlength="10000"
                placeholder="面向谁阅读、篇幅与语气等要求"
              />
            </label>
          </div>
        </section>
        <section class="editor-section">
          <div class="editor-section-heading">
            <div>
              <h2>章节大纲</h2>
              <p>每行一章，可手动填写或生成后调整。</p>
            </div>
            <UiButton
              type="button"
              :disabled="busy || !topic.trim()"
              @click="outline"
              size="compact"
              ><Sparkles :size="15" />生成大纲
            </UiButton>
          </div>
          <label class="sr-only" for="writing-sections"
            >章节（每行一章，可编辑）</label
          ><textarea
            id="writing-sections"
            v-model="sections"
            class="field-input outline-editor"
            rows="7"
            placeholder="项目背景&#10;实施方案&#10;交付与验收"
          />
        </section>
        <footer class="editor-submit">
          <span><Info :size="15" />使用生成模型，内容需人工核对。</span
          ><UiButton
            type="submit"
            :disabled="busy || !topic.trim()"
            variant="primary"
            ><LoaderCircle v-if="busy" :size="16" class="spin" /><FileOutput
              v-else
              :size="16"
            />开始生成文档
          </UiButton>
        </footer>
      </form>
      <aside class="editor-aside generation-history" aria-label="生成记录">
        <div class="editor-aside-title">
          <History :size="20" />
          <h2>生成记录</h2>
          <span v-if="jobs.length" class="document-count">{{
            jobs.length
          }}</span>
        </div>
        <UiEmptyState
          v-if="!jobs.length"
          :icon="Files"
          title="还没有生成记录"
          description="任务和已生成内容会保存在当前工作区。"
          compact
        ></UiEmptyState>
        <ul v-else class="generation-list">
          <li v-for="job in jobs" :key="job.id">
            <button
              class="job-title"
              :aria-pressed="selectedJob?.id === job.id"
              @click="selectedJob = job"
            >
              {{ job.request.topic }}<ChevronRight :size="14" />
            </button>
            <div class="job-meta">
              <span class="job-status" :class="job.status">{{
                labels[job.status] || job.status
              }}</span
              ><span>{{ job.progress }}%</span>
            </div>
            <progress
              v-if="job.status === 'running'"
              :value="job.progress"
              max="100"
              :aria-label="job.request.topic + '生成进度'"
            ></progress
            ><UiButton
              v-if="job.filename"
              @click="downloadFile('/download/' + job.filename)"
              variant="text"
              ><Download :size="14" />下载 Word
            </UiButton>
            <UiNotice v-if="job.error" :message="job.error" />
            <UiButton
              v-if="['failed', 'interrupted'].includes(job.status)"
              @click="retry(job)"
              variant="text"
              ><RefreshCw :size="14" />重新生成
            </UiButton>
          </li>
        </ul>
        <div class="editor-guidance">
          <h3>先确认，再使用</h3>
          <p>
            取材记录保留资料来源。请核对生成内容与引用依据，下载后检查 Word
            排版。
          </p>
        </div>
      </aside>
    </div>
    <article v-if="selectedJob" class="generated-preview">
      <header>
        <FileText :size="20" />
        <h2>{{ selectedJob.request.topic }}</h2>
      </header>
      <div class="generated-prose">
        {{ selectedJob.content || "内容将在章节完成后出现在这里。" }}
      </div>
      <section v-if="selectedJob.sources.length" class="generated-sources">
        <h3>取材记录</h3>
        <ul>
          <li v-for="(source, index) in selectedJob.sources" :key="index">
            [{{ index + 1 }}] {{ source.title }} · {{ source.section }}
          </li>
        </ul>
      </section>
    </article>
  </section>
</template>
<script setup>
import UiNotice from "../components/ui/UiNotice.vue";
import UiEmptyState from "../components/ui/UiEmptyState.vue";
import UiPageHeader from "../components/ui/UiPageHeader.vue";
import UiButton from "../components/ui/UiButton.vue";
import { RouterLink } from "vue-router";
import {
  ChevronRight,
  Download,
  Files,
  FileOutput,
  FileText,
  History,
  Info,
  Library,
  LoaderCircle,
  PenLine,
  RefreshCw,
  Sparkles,
} from "@lucide/vue";

import { onMounted, onUnmounted, ref } from "vue";
import { useRoute } from "vue-router";
import { api, handleError, downloadFile } from "../api/client";
const route = useRoute();
const collections = ref([]),
  selected = ref(String(route.query.collection || "")),
  topic = ref(""),
  reference = ref(""),
  instructions = ref(""),
  sections = ref(""),
  busy = ref(false),
  message = ref(""),
  jobs = ref([]),
  selectedJob = ref(null);
const labels = {
  queued: "排队中",
  running: "生成中",
  completed: "已完成",
  failed: "失败",
  interrupted: "已中断",
};
let timer;
async function refresh() {
  try {
    jobs.value = (await api.get("/api/v1/documents/jobs")).data.jobs;
    if (selectedJob.value)
      selectedJob.value =
        jobs.value.find((j) => j.id === selectedJob.value.id) ||
        selectedJob.value;
  } catch (e) {
    message.value = handleError(e);
  }
}
function payload() {
  return {
    topic: topic.value,
    sections: sections.value
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean),
    collection_ids: selected.value ? [selected.value] : [],
    instructions: instructions.value,
    reference: reference.value,
  };
}
async function outline() {
  busy.value = true;
  message.value = "正在整理大纲…";
  try {
    const r = await api.post("/api/v1/documents/outline", payload(), {
      timeout: 180000,
    });
    sections.value = r.data.sections.join("\n") || r.data.outline;
    message.value = "请核对并编辑章节后再生成。";
  } catch (e) {
    message.value = handleError(e);
  } finally {
    busy.value = false;
  }
}
async function generate() {
  busy.value = true;
  try {
    selectedJob.value = (
      await api.post("/api/v1/documents/jobs", payload())
    ).data;
    message.value = "任务已提交，可在生成记录查看进度。";
    await refresh();
  } catch (e) {
    message.value = handleError(e);
  } finally {
    busy.value = false;
  }
}
async function retry(job) {
  try {
    selectedJob.value = (
      await api.post("/api/v1/documents/jobs", job.request)
    ).data;
    await refresh();
  } catch (e) {
    message.value = handleError(e);
  }
}
onMounted(async () => {
  await refresh();
  try {
    collections.value = (
      await api.get("/api/v1/knowledge/collections")
    ).data.data;
  } catch (e) {
    message.value = "知识引擎暂不可用，可先使用手动参考资料。";
  }
  timer = setInterval(refresh, 3000);
});
onUnmounted(() => clearInterval(timer));
</script>
