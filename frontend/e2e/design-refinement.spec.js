import { test, expect } from "@playwright/test";
import { readFileSync, mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../../", import.meta.url));
const env = readFileSync(new URL("../../.env", import.meta.url), "utf8");
const key =
  process.env.QUILL_TEST_KEY || env.match(/^QUILL_API_KEY=(.*)$/m)?.[1] || "";
const title = "示例 · 项目验收记录";
test.beforeEach(async ({ page }) => {
  await page.addInitScript(
    (key) => sessionStorage.setItem("quill-key", key),
    key,
  );
});
test.beforeAll(async ({ request }) => {
  const headers = { Authorization: `Bearer ${key}` };
  const listed = await request.get("/api/templates", { headers });
  expect(listed.ok()).toBeTruthy();
  const names = new Set(
    (await listed.json()).templates.map((template) => template.name),
  );
  const buffer = execFileSync(root + ".venv/bin/python", [
    "-c",
    'from docx import Document; import io,sys; d=Document();d.add_paragraph("项目：【项目名称】；负责人：{{负责人}}");b=io.BytesIO();d.save(b);sys.stdout.buffer.write(b.getvalue())',
  ]);
  for (const name of [
    title,
    "示例 · 设备巡检报告",
    "示例 · 园区设备运维项目交付与验收说明（包含多部门联合确认记录）",
  ]) {
    if (names.has(name)) continue;
    const response = await request.post("/api/upload-template", {
      headers,
      multipart: {
        template_name: name,
        description: "虚构模板，仅用于界面和工作流程验收。",
        file: {
          name: "example.docx",
          mimeType:
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          buffer,
        },
      },
    });
    expect(response.ok()).toBeTruthy();
  }
});
test("catalog filtering, view switch, keyboard entry, and template download", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/templates");
  await page.getByRole("searchbox", { name: "搜索模板" }).fill(title);
  await expect(page.locator(".template-entry")).toHaveCount(1);
  await page.getByRole("button", { name: "列表视图", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "列表视图", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  const source = page.getByRole("link", { name: title, exact: true });
  await source.focus();
  await source.press("Enter");
  await expect(
    page.getByRole("heading", { level: 1, name: title, exact: true }),
  ).toBeVisible();
  await page.getByLabel("项目名称", { exact: true }).fill("Quill 界面验收");
  await page.getByLabel("负责人", { exact: true }).fill("虚构验收人员");
  await page.getByRole("button", { name: "生成文档", exact: true }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载 Word", exact: true }).click();
  expect((await download).suggestedFilename()).toMatch(/\.docx$/);
  expect(errors).toEqual([]);
});
for (const width of [1440, 1024, 390]) {
  test(`consistent document surfaces at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    mkdirSync("../artifacts/design-reference", { recursive: true });
    for (const route of [
      "templates",
      "create",
      "writing",
      "generate/" + encodeURIComponent(title),
    ]) {
      await page.goto("/" + route);
      if (route === "templates")
        await page.getByLabel("搜索模板", { exact: true }).fill(title);
      if (route === "templates")
        await expect(
          page.getByRole("link", { name: title, exact: true }),
        ).toBeVisible();
      else if (route.startsWith("generate/"))
        await expect(
          page.getByLabel("项目名称", { exact: true }),
        ).toBeVisible();
      else if (route === "create")
        await expect(
          page.getByRole("button", { name: "上传并入库" }),
        ).toBeDisabled();
      else
        await expect(
          page.getByRole("button", { name: "开始生成文档" }),
        ).toBeDisabled();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      await page.screenshot({
        path: `../artifacts/design-reference/${route.split("/")[0]}-${width}.png`,
        fullPage: true,
      });
    }
    expect(errors).toEqual([]);
  });
}
