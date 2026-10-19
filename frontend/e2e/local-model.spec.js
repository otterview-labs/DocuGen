import { test, expect } from "@playwright/test";

// Explicit opt-in: this test calls the configured real model and writes synthetic test data.
test("real local model fills a template and generates a Word document through the UI", async ({
  page,
  request,
}) => {
  test.skip(process.env.QUILL_REAL_LOCAL_MODEL !== "1", "Enable only against the isolated local-model runtime.");
  test.setTimeout(180000);
  const status = await request.get("/api/v1/status");
  expect(status.status()).toBe(200);
  expect((await status.json()).model_configured).toBe(true);
  const templates = (await (await request.get("/api/templates")).json()).templates;
  const template = templates.find((item) => item.name === "示例 · 独立验收模板");
  expect(template).toBeTruthy();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const facts = "项目名称：水獭演示项目。负责人：示例甲。验收周期30天。交付资料包括测试报告。以上为合成验收数据。";
  await page.goto("/generate/" + encodeURIComponent(template.name));
  await page.locator(".reference-disclosure > summary").click();
  await page.getByLabel("手动参考资料", { exact: true }).fill(facts);
  const filled = page.waitForResponse((r) => r.url().endsWith("/api/ai-fill-template-variables"));
  await page.getByRole("button", { name: "AI 填充", exact: true }).click();
  expect((await filled).status()).toBe(200);
  await expect(page.getByLabel("项目名称", { exact: true })).toHaveValue("水獭演示项目");
  await expect(page.getByLabel("负责人", { exact: true })).toHaveValue("示例甲");
  await page.getByRole("button", { name: "生成文档", exact: true }).click();
  let download = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载 Word", exact: true }).click();
  expect((await download).suggestedFilename()).toMatch(/\.docx$/);
  await page.goto("/writing");
  await page.getByLabel("文档主题", { exact: true }).fill("示例 · 本机模型浏览器验收 " + Date.now());
  await page.getByLabel("手动参考资料", { exact: true }).fill(facts);
  await page.getByLabel("写作要求", { exact: true }).fill("仅写80字以内，说明验收周期30天和测试报告，引用资料，不补充其他事实。");
  const outline = page.waitForResponse((r) => r.url().endsWith("/api/v1/documents/outline"));
  await page.getByRole("button", { name: "生成大纲", exact: true }).click();
  expect((await outline).status()).toBe(200);
  const sections = page.getByLabel("章节（每行一章，可编辑）", { exact: true });
  await expect(sections).not.toHaveValue("");
  await sections.fill("验收结论");
  const submitted = page.waitForResponse((r) => r.url().endsWith("/api/v1/documents/jobs") && r.request().method() === "POST");
  await page.getByRole("button", { name: "开始生成文档", exact: true }).click();
  const job = await submitted;
  expect(job.status()).toBe(202);
  const id = (await job.json()).id;
  await expect.poll(async () => (await (await request.get("/api/v1/documents/jobs/" + id)).json()).status, { timeout: 120000 }).toBe("completed");
  await expect(page.locator(".generated-prose")).toContainText("30", { timeout: 10000 });
  await expect(page.locator(".generated-sources")).toContainText("手动参考资料");
  download = page.waitForEvent("download");
  await page.locator(".generation-list > li").first().getByRole("button", { name: "下载 Word", exact: true }).click();
  expect((await download).suggestedFilename()).toMatch(/\.docx$/);
  expect(errors).toEqual([]);
});
