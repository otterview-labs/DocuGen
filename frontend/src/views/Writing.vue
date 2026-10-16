<template>
  <section class="workspace">
    <h1>文档写作</h1>
    <p>选择资料，确认章节，生成可下载的 Word 文档。生成内容仍需人工核对。</p>
    <p v-if="message" class="work-status" role="status">{{ message }}</p>
    <form class="work-form" @submit.prevent="generate">
      <label>文档主题<input v-model="topic" required maxlength="500" placeholder="例如：园区设备运维方案" /></label>
      <label>参考知识库<select v-model="selected"><option value="">仅使用手动参考资料</option><option v-for="c in collections" :key="c.id" :value="c.id">{{ c.name }}</option></select></label>
      <label>手动参考资料<textarea v-model="reference" rows="4" maxlength="12000" placeholder="项目事实、约束与需要引用的资料" /></label>
      <label>写作要求<textarea v-model="instructions" rows="2" maxlength="10000" /></label>
      <div class="work-actions"><button type="button" @click="outline" :disabled="busy || !topic.trim()">生成大纲</button></div>
      <label>章节（每行一章，可编辑）<textarea v-model="sections" rows="6" placeholder="项目背景&#10;实施方案&#10;交付与验收" /></label>
      <div class="work-actions"><button :disabled="busy || !topic.trim()">开始生成文档</button></div>
    </form>
    <h2>生成记录</h2>
    <p v-if="!jobs.length">还没有生成记录。任务和已生成内容会保存在当前工作区。</p>
    <ul class="work-list"><li v-for="job in jobs" :key="job.id">
      <button class="job-title" @click="selectedJob=job">{{ job.request.topic }}</button>
      <span> · {{ labels[job.status] || job.status }} · {{ job.progress }}%</span>
      <button v-if="job.filename" class="work-button" @click="downloadFile('/download/'+job.filename)">下载 Word</button>
      <p v-if="job.error" class="work-status">{{ job.error }}</p>
      <button v-if="['failed','interrupted'].includes(job.status)" @click="retry(job)">重新生成</button>
    </li></ul>
    <article v-if="selectedJob" class="work-result"><h2>{{ selectedJob.request.topic }}</h2><div>{{ selectedJob.content }}</div>
      <h3 v-if="selectedJob.sources.length">取材记录</h3><ul><li v-for="(source,i) in selectedJob.sources" :key="i">[{{i+1}}] {{source.title}} · {{source.section}}</li></ul>
    </article>
  </section>
</template>
<script setup>
import { onMounted, onUnmounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { api, handleError, downloadFile } from '../api/client';
const route = useRoute();
const collections=ref([]),selected=ref(String(route.query.collection || '')),topic=ref(''),reference=ref(''),instructions=ref(''),sections=ref(''),busy=ref(false),message=ref(''),jobs=ref([]),selectedJob=ref(null);
const labels={queued:'排队中',running:'生成中',completed:'已完成',failed:'失败',interrupted:'已中断'};
let timer;
async function refresh(){try{jobs.value=(await api.get('/api/v1/documents/jobs')).data.jobs;if(selectedJob.value)selectedJob.value=jobs.value.find(j=>j.id===selectedJob.value.id)||selectedJob.value;}catch(e){message.value=handleError(e);}}
function payload(){return {topic:topic.value,sections:sections.value.split('\n').map(s=>s.trim()).filter(Boolean),collection_ids:selected.value?[selected.value]:[],instructions:instructions.value,reference:reference.value};}
async function outline(){busy.value=true;message.value='正在整理大纲…';try{const r=await api.post('/api/v1/documents/outline',payload(),{timeout:180000});sections.value=r.data.sections.join('\n')||r.data.outline;message.value='请核对并编辑章节后再生成。';}catch(e){message.value=handleError(e);}finally{busy.value=false;}}
async function generate(){busy.value=true;try{selectedJob.value=(await api.post('/api/v1/documents/jobs',payload())).data;message.value='任务已提交，可在生成记录查看进度。';await refresh();}catch(e){message.value=handleError(e);}finally{busy.value=false;}}
async function retry(job){try{selectedJob.value=(await api.post('/api/v1/documents/jobs',job.request)).data;await refresh();}catch(e){message.value=handleError(e);}}
onMounted(async()=>{await refresh();try{collections.value=(await api.get('/api/v1/knowledge/collections')).data.data;}catch(e){message.value='知识引擎暂不可用，可先使用手动参考资料。';}timer=setInterval(refresh,3000);});
onUnmounted(()=>clearInterval(timer));
</script>
<style scoped>.job-title{background:none;border:0;text-decoration:underline;color:#245d75;cursor:pointer;font:inherit;text-align:left}.work-list .work-button{margin:8px}.work-result div{white-space:pre-wrap}</style>
