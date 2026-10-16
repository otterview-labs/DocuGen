import { createRouter, createWebHistory } from 'vue-router';
import Knowledge from './views/Knowledge.vue';
import Writing from './views/Writing.vue';
import Templates from './views/Templates.vue';
import CreateTemplate from './views/CreateTemplate.vue';
import TemplateGenerate from './views/TemplateGenerate.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/knowledge', component: Knowledge },
    { path: '/writing', component: Writing },
    { path: '/', name: 'templates', component: Templates },
    { path: '/create', name: 'create', component: CreateTemplate },
    { path: '/generate/:templateId?', name: 'generate', component: TemplateGenerate }
  ]
});

export default router;
