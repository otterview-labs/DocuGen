<template>
  <section class="workspace">
    <h1>知识库</h1>
    <p>整理资料，检索片段，为文档生成提供依据。</p>
    <p class="work-status" role="status">{{ message }}</p>
    <form class="work-form" @submit.prevent="createCollection">
      <label>新建知识库<input v-model="newName" required maxlength="100" placeholder="例如：产品与技术资料" /></label>
      <div class="work-actions"><button :disabled="busy">新建知识库</button><button type="button" @click="load" :disabled="busy">刷新列表</button></div>
    </form>
    <form class="work-form" @submit.prevent="saveText">
      <label>当前知识库<select v-model="selected" required><option value="">请选择</option><option v-for="c in collections" :key="c.id" :value="c.id">{{ c.name }}</option></select></label>
      <label>资料标题<input v-model="title" required maxlength="255" /></label>
      <label>资料内容<textarea v-model="content" required rows="7" maxlength="200000" placeholder="粘贴产品说明、项目背景或其他文本资料" /></label>
      <div class="work-actions"><button :disabled="busy || !selected">保存资料</button></div>
    </form>
    <form class="work-form" @submit.prevent="search">
      <label>检索资料<input v-model="query" required placeholder="输入关键词或问题" /></label>
      <label>检索方式<select v-model="mode"><option value="keyword">关键词（无需向量模型）</option><option value="intelligent">智能检索</option><option value="semantic">语义检索</option></select></label>
      <div class="work-actions"><button :disabled="busy || !selected">检索</button><button type="button" :disabled="busy || !selected || !query.trim()" @click="answerQuestion">基于资料回答</button></div>
    </form>
    <article v-if="answer" class="work-result"><h2>回答</h2><p>{{ answer }}</p></article>
    <p v-if="searched && !results.length">没有检索到相关资料，请调整关键词。</p>
    <article v-for="(result, i) in results" :key="i" class="work-result"><h2>{{ result.title }}</h2><p>{{ result.content }}</p></article>
  </section>
</template>
<script setup>
import { onMounted, ref } from 'vue';
import { api, handleError } from '../api/client';
const collections=ref([]),selected=ref(''),newName=ref(''),title=ref(''),content=ref(''),query=ref(''),mode=ref('keyword');
const busy=ref(false),message=ref(''),results=ref([]),searched=ref(false);
const answer=ref('');
async function action(fn) { busy.value=true; message.value=''; try { await fn(); } catch(e) {message.value=handleError(e);} finally {busy.value=false;} }
async function load() { await action(async()=>{ collections.value=(await api.get('/api/v1/knowledge/collections')).data.data; }); }
async function createCollection() { await action(async()=>{ await api.post('/api/v1/knowledge/collections',{name:newName.value});collections.value=(await api.get('/api/v1/knowledge/collections')).data.data; newName.value='';message.value='知识库已创建。'; }); }
async function saveText() { await action(async()=>{ const r=await api.post('/api/v1/knowledge/text',{collection_id:selected.value,title:title.value,content:content.value}); message.value=r.data.result.message;title.value='';content.value=''; }); }
async function search() { await action(async()=>{results.value=(await api.post('/api/v1/knowledge/search',{query:query.value,collection_ids:[selected.value],mode:mode.value})).data.sources; searched.value=true;}); }
async function answerQuestion() { await action(async()=>{answer.value='';const r=await api.post('/api/v1/knowledge/answer',{query:query.value,collection_ids:[selected.value],mode:mode.value},{timeout:180000});answer.value=r.data.answer;results.value=r.data.sources;searched.value=true;}); }
onMounted(load);
</script>
