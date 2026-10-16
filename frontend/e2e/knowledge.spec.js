import { test, expect } from '@playwright/test';
import { readFileSync, mkdirSync } from 'node:fs';
const env = readFileSync(new URL('../../.env', import.meta.url), 'utf8');
const key = process.env.QUILL_TEST_KEY || env.match(/^QUILL_API_KEY=(.*)$/m)?.[1] || '';
test.beforeEach(async({page})=>{await page.addInitScript(key=>sessionStorage.setItem('quill-key',key),key);});
test.beforeAll(async({request})=>{
  const headers={Authorization:`Bearer ${key}`};
  const overview=await request.get('/api/v1/knowledge/overview',{headers});
  expect(overview.ok()).toBeTruthy();
  let collection=(await overview.json()).collections.find(c=>c.name==='示例 · 设备运维资料');
  if(!collection){
    const created=await request.post('/api/v1/knowledge/collections',{headers,data:{name:'示例 · 设备运维资料',description:'用于界面验收的虚构资料，演示设备运维、项目交付与规范管理。'}});
    expect(created.ok()).toBeTruthy();collection=(await created.json()).result;
  }
  const listed=await request.get('/api/v1/knowledge/resources',{headers,params:{collection_id:collection.id}});
  expect(listed.ok()).toBeTruthy();
  const titles=new Set((await listed.json()).items.map(item=>item.title));
  const fixtures=[
    ['示例 · 园区项目验收规范','这是一份用于功能验收的虚构资料。\n\n项目验收范围包括设备接入、告警处理与数据检索。验收资料需包含测试记录、操作说明和交付清单。\n\n所有示例描述均为虚构，仅用于界面和工作流程测试。'],
    ['示例 · 网关日常巡检记录','这是虚构的巡检示例。每天检查设备连接、数据上报和告警记录，保存异常处理依据。'],
    ['示例 · 告警处理操作说明','这是虚构的告警处理示例。记录触发时间、排查步骤和恢复结果，再由操作人员核对。'],
  ];
  for(const [title,content] of fixtures){
    if(titles.has(title))continue;
    const saved=await request.post('/api/v1/knowledge/text',{headers,data:{collection_id:collection.id,title,content}});
    expect(saved.ok()).toBeTruthy();
  }
});

test('manage knowledge, import duplicate files, preview sources, and delete selected data',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/knowledge');
  await page.locator('.heading-actions').getByRole('button',{name:'新建知识库'}).click();
  const name='E2E 示例知识库 '+Date.now();
  await page.getByLabel('知识库名称',{exact:true}).fill(name);
  await page.getByLabel('说明',{exact:true}).fill('浏览器回归创建的虚构资料，仅供测试。');
  await page.getByRole('button',{name:'创建',exact:true}).click();
  await expect(page.locator('.library-title h2')).toHaveText(name);
  await page.getByRole('button',{name:'导入资料',exact:true}).click();
  const file={name:'E2E验收资料.txt',mimeType:'text/plain',buffer:Buffer.from('这是虚构的验收资料。验收范围包括设备接入、数据查询与原文预览。')};
  const importResponse=page.waitForResponse(r=>r.url().endsWith('/api/v1/knowledge/import')&&r.request().method()==='POST');
  await page.getByLabel('选择知识库文件',{exact:true}).setInputFiles(file);
  expect((await importResponse).status()).toBe(200);
  await expect(page.locator('.resource-table tbody tr')).toHaveCount(1);
  const duplicate=page.waitForResponse(r=>r.url().endsWith('/api/v1/knowledge/import')&&r.request().method()==='POST');
  await page.getByLabel('选择知识库文件',{exact:true}).setInputFiles(file);
  expect((await duplicate).status()).toBe(200);
  await expect(page.getByText('已存在，跳过重复导入',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:/E2E验收资料.*文本/}).click();
  const preview=page.getByRole('complementary',{name:'资料预览'});
  await expect(preview.locator('.preview-prose')).toContainText('设备接入');
  await expect(preview.getByRole('button',{name:'关闭资料预览'})).toBeFocused();
  const download=page.waitForEvent('download');await preview.getByRole('button',{name:'下载原文件',exact:true}).click();
  expect((await download).suggestedFilename()).toBe('E2E验收资料.txt');
  await preview.getByRole('button',{name:'内容分段',exact:false}).click();
  await expect(preview.locator('.preview-segments article')).toHaveCount(1);
  await preview.getByRole('button',{name:'资料信息',exact:true}).click();
  await preview.getByLabel('资料名称',{exact:true}).fill('E2E修改后的验收资料');
  await preview.getByLabel('标签',{exact:true}).fill('验收，测试');
  await preview.getByRole('button',{name:'保存信息',exact:true}).click();
  await expect(preview.getByRole('heading',{name:'E2E修改后的验收资料'})).toBeVisible();
  await preview.getByRole('button',{name:'重建向量索引',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('向量模型尚未就绪');
  await preview.getByRole('button',{name:'关闭资料预览'}).click();
  await expect(page.getByRole('button',{name:/E2E修改后的验收资料.*文本/})).toBeFocused();
  await page.getByRole('tab',{name:'检索与问答',exact:true}).click();
  await page.getByLabel('检索问题',{exact:true}).fill('验收');
  await page.getByRole('button',{name:'检索资料',exact:true}).click();
  await expect(page.getByRole('heading',{name:'命中 1 条资料'})).toBeVisible();
  await expect(page.locator('.search-result mark').first()).toBeVisible();
  await page.getByRole('button',{name:'查看来源',exact:true}).click();
  await expect(preview.locator('.preview-prose')).toContainText('设备接入');
  await preview.getByRole('button',{name:'资料信息',exact:true}).click();
  await preview.getByRole('button',{name:'移除资料',exact:true}).click();
  await preview.getByRole('button',{name:'确认移除资料',exact:true}).click();
  await expect(preview).toHaveCount(0);
  await page.getByRole('tab',{name:'资料管理',exact:false}).click();
  await expect(page.getByRole('heading',{name:'你的资料，将从这里开始'})).toBeVisible();
  expect(errors).toEqual([]);
});

for(const width of [1440,390]){
 test(`knowledge library and preview at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:1000});await page.goto('/knowledge');
  await page.getByRole('button',{name:/示例 · 设备运维资料/}).click();
  await expect(page.locator('.resource-table tbody tr')).toHaveCount(3);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  mkdirSync('../artifacts/knowledge-redesign',{recursive:true});
  await page.screenshot({path:`../artifacts/knowledge-redesign/library-${width}.png`,fullPage:true});
  await page.getByRole('button',{name:/示例 · 园区项目验收规范.*文本/}).click();
  await expect(page.locator('.preview-prose')).toContainText('验收资料需包含');
  await expect(page.getByRole('button',{name:'关闭资料预览'})).toBeFocused();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:`../artifacts/knowledge-redesign/preview-${width}.png`,fullPage:true});
  await page.getByRole('button',{name:'关闭资料预览'}).click();
  await page.getByRole('tab',{name:'检索与问答',exact:true}).click();await page.getByLabel('检索问题',{exact:true}).fill('验收');await page.getByRole('button',{name:'检索资料',exact:true}).click();
  await expect(page.locator('.search-result').first()).toBeVisible();
  await page.screenshot({path:`../artifacts/knowledge-redesign/search-${width}.png`,fullPage:true});
 });
}
