import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));

test("all twelve authentic cover assets correspond to the current template definitions", async ({ request, page }) => {
  const library = (await (await request.get("/api/template-library")).json()).templates;
  const provenance = await (await request.get("/template-previews/provenance.json")).json();
  expect(provenance).toHaveLength(12);
  for (const item of library) {
    expect(provenance.find(record => record.id === item.id).definition).toEqual(item);
    const image = await request.get(`/template-previews/${item.id}.png`);
    expect(image.status()).toBe(200);
    expect(image.headers()["content-type"]).toContain("image/png");
    expect((await image.body()).subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");
  }
  await page.goto("/create");
  await expect(page.locator(".create-starter-list img")).toHaveCount(4);
  await expect.poll(() => page.locator(".create-starter-list img").evaluateAll(images => images.every(image => image.complete && image.naturalWidth > 0))).toBe(true);
  await page.getByRole("link", { name: "导入 Word", exact: true }).click();
  await expect(page.locator('input[type="file"]')).toBeFocused();
});

test("missing preview keeps content and the template action available", async ({ page }) => {
  await page.route("**/template-previews/project-plan.png", route => route.fulfill({ status: 404, body: "missing" }));
  await page.goto("/create");
  await expect(page.getByText("图片暂不可用 · 仍可查看结构和使用模板")).toBeVisible();
  await page.getByRole("button", { name: "使用项目实施方案", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/项目实施方案/);
});

test("gallery manual export remains available when the UI reports no configured model", async ({ page }) => {
  const modelCalls = [];
  await page.route("**/api/v1/status", route => route.fulfill({ json: { authentication: false, model_configured: false, model: "" } }));
  page.on("request", request => { if (request.url().includes("ai-fill")) modelCalls.push(request.url()); });
  await page.goto("/create");
  await expect(page.locator(".model-state")).toHaveText("生成模型未配置");
  await page.getByRole("button", { name: "使用工作周报", exact: true }).click();
  await page.getByLabel("团队或项目", { exact: true }).fill("无模型导出演示");
  await page.getByRole("button", { name: "生成文档", exact: true }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载 Word", exact: true }).click();
  const file = await download;
  const text = execFileSync(root + ".venv/bin/python", ["-c", "from docx import Document;import sys;d=Document(sys.argv[1]);print('\\n'.join(c.text for t in d.tables for r in t.rows for c in r.cells))", await file.path()], { encoding: "utf8" });
  expect(text).toContain("无模型导出演示");
  expect(modelCalls).toEqual([]);
});
