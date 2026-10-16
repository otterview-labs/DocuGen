import { createRouter, createWebHistory } from 'vue-router';
import Knowledge from './views/Knowledge.vue';
import Writing from './views/Writing.vue';
import Templates from './views/Templates.vue';
import CreateTemplate from './views/CreateTemplate.vue';
import TemplateGenerate from './views/TemplateGenerate.vue';
export default createRouter({history:createWebHistory(),routes:[
 {path:'/',redirect:'/knowledge'},
 {path:'/knowledge',component:Knowledge,meta:{title:'知识库'}},
 {path:'/writing',component:Writing,meta:{title:'文档写作'}},
 {path:'/templates',name:'templates',component:Templates,meta:{title:'文档模板'}},
 {path:'/create',name:'create',component:CreateTemplate,meta:{title:'上传模板'}},
 {path:'/generate/:templateId?',name:'generate',component:TemplateGenerate,meta:{title:'模板生成'}},
]});
