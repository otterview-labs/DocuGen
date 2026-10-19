import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../', import.meta.url));
const env = readFileSync(new URL('../../.env', import.meta.url), 'utf8');
const key = process.env.QUILL_TEST_KEY || env.match(/^QUILL_API_KEY=(.*)$/m)?.[1] || '';

test.beforeEach(async ({ page }) => {
  await page.addInitScript((key) => sessionStorage.setItem('quill-key', key), key);
});

test('upload a Word template, fill variables, and download the result', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const fixture = execFileSync(root + '.venv/bin/python', ['-c',
    'from docx import Document; import io,sys; d=Document(); d.add_paragraph("项目：【项目名称】；负责人：{{负责人}}"); b=io.BytesIO(); d.save(b); sys.stdout.buffer.write(b.getvalue())']);
  await page.goto('/create');
  await page.locator('input[type=file]').setInputFiles({name:'浏览器验收.docx',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',buffer:fixture});
  await page.getByPlaceholder('模板名称（可选，默认用文件名）').fill('浏览器验收-' + Date.now());
  const uploaded = page.waitForResponse(r => r.url().endsWith('/api/upload-template') && r.request().method()==='POST');
  await page.getByRole('button',{name:'上传并入库'}).click();
  expect((await uploaded).status()).toBe(200);
  await page.getByLabel('项目名称',{exact:true}).fill('Quill 集成测试');
  await page.getByLabel('负责人',{exact:true}).fill('验收人员');
  const rendered = page.waitForResponse(r=>r.url().endsWith('/api/generate-from-template'));
  await page.getByRole('button',{name:'生成文档',exact:true}).click();
  expect((await rendered).status()).toBe(200);
  const download = page.waitForEvent('download');
  await page.getByRole('button',{name:'下载 Word'}).click();
  expect((await download).suggestedFilename()).toMatch(/\.docx$/);
  expect(errors).toEqual([]);
});

for (const viewport of [{width:1440,height:1000},{width:390,height:844}]) {
  test(`navigation and layout ${viewport.width}`, async ({page})=>{
    await page.setViewportSize(viewport);
    await page.goto('/knowledge');
    await expect(page.getByRole('heading',{name:'知识库',exact:true})).toBeVisible();
    await expect(page.getByRole('button',{name:'导入资料',exact:true})).toBeVisible();
    await page.getByRole('link',{name:'文档写作',exact:true}).click();
    for (const label of ['知识库','文档写作','文档模板','上传模板']) {
      await expect(page.getByRole('link',{name:label,exact:true})).toBeInViewport();
    }
    await expect(page.getByRole('heading',{name:'文档写作',exact:true})).toBeVisible();
    await expect(page.getByRole('button',{name:'开始生成文档'})).toBeDisabled();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.screenshot({path:`../artifacts/quill-${viewport.width}.png`,fullPage:true});
  });
}
