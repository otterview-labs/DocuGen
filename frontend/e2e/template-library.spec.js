import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));

test("starter library previews, downloads and generates a real Word document without a model", async ({
  page,
  request,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const response = await request.get("/api/template-library");
  expect(response.status()).toBe(200);
  expect((await response.json()).templates).toHaveLength(12);
  await page.goto("/create");
  await page.getByRole("link", { name: "浏览模板库", exact: true }).click();
  await expect(page.getByRole("tab", { name: /内置模板/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page
    .getByRole("group", { name: "模板分类" })
    .getByRole("button", { name: "报告", exact: true })
    .click();
  await expect(page.locator(".template-entry")).toHaveCount(4);
  await page.getByRole("button", { name: "预览工作周报", exact: true }).click();
  const preview = page.getByRole("region", { name: "模板结构预览" });
  await expect(preview).toBeFocused();
  await preview.locator(".preview-structure-details > summary").click();
  await expect(
    preview.getByRole("heading", { name: "本周完成" }),
  ).toBeVisible();
  const originalDownload = page.waitForEvent("download");
  await preview.getByRole("button", { name: "下载 Word 模板" }).click();
  const original = await originalDownload;
  expect(original.suggestedFilename()).toBe("工作周报.docx");
  await page.getByRole("button", { name: "关闭模板预览" }).click();
  await expect(
    page.getByRole("button", { name: "预览工作周报", exact: true }),
  ).toBeFocused();
  await page.getByRole("button", { name: "列表视图" }).click();
  await expect(page.locator(".template-catalog")).toHaveClass(/list-view/);
  await page.getByRole("button", { name: "使用工作周报", exact: true }).click();
  await expect(page).toHaveURL(/\/generate\//);
  await expect(page.locator("h1")).toHaveText(/工作周报/);
  const templateName = await page.locator("h1").innerText();
  await page.getByLabel("团队或项目", { exact: true }).fill("北岸项目");
  await page.getByLabel("汇报人", { exact: true }).fill("示例人员");
  await page
    .getByLabel("本周完成", { exact: true })
    .fill("完成模板验收\n确认导出排版");
  await page.getByRole("button", { name: "生成文档", exact: true }).click();
  const renderedDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载 Word", exact: true }).click();
  const rendered = await renderedDownload;
  const text = execFileSync(
    root + ".venv/bin/python",
    [
      "-c",
      "from docx import Document;import sys;d=Document(sys.argv[1]);print('\\n'.join([p.text for p in d.paragraphs]+[c.text for t in d.tables for r in t.rows for c in r.cells]));assert d.paragraphs[0].style.name=='Title';assert d.tables[0].style.name=='Table Grid'",
      await rendered.path(),
    ],
    { encoding: "utf8" },
  );
  expect(text).toContain("北岸项目");
  expect(text).toContain("完成模板验收\n确认导出排版");
  expect(text).not.toContain("{{");
  await page.goto("/templates");
  await page.getByRole("tab", { name: /工作区模板/ }).click();
  await expect(
    page.getByRole("link", { name: templateName, exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("upload preserves category and description for catalog filtering", async ({
  page,
  request,
}) => {
  const source = await request.get(
    "/api/template-library/meeting-minutes/download",
  );
  const name = "示例 · 自定义纪要 " + Date.now();
  await page.goto("/create");
  await page.locator('input[type="file"]').setInputFiles({
    name: "minutes.docx",
    mimeType:
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: await source.body(),
  });
  await page.getByLabel("模板名称", { exact: true }).fill(name);
  await page.getByLabel("模板分类", { exact: true }).selectOption("报告");
  await page.getByLabel("模板说明", { exact: true }).fill("保留会议纪要版式");
  const uploadResponse = page.waitForResponse((r) =>
    r.url().endsWith("/api/upload-template"),
  );
  await page.getByRole("button", { name: "上传并入库" }).click();
  expect((await uploadResponse).status()).toBe(200);
  await page.goto("/templates");
  await page.getByRole("tab", { name: /工作区模板/ }).click();
  await page.getByLabel("搜索模板", { exact: true }).fill(name);
  await expect(page.locator(".template-entry")).toHaveCount(1);
  await expect(page.locator(".template-entry")).toContainText(
    "报告 · 工作区模板",
  );
  await expect(page.locator(".template-entry")).toContainText(
    "保留会议纪要版式",
  );
});

for (const width of [1440, 1024, 390]) {
  test(`template library layout and preview at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/templates?source=builtin");
    await expect(page.locator(".template-entry")).toHaveCount(9);
    await page.screenshot({
      path: root + `artifacts/template-library/catalog-${width}.png`,
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "预览项目实施方案", exact: true })
      .click();
    await expect(
      page.getByRole("region", { name: "模板结构预览" }),
    ).toBeVisible();
    await page.screenshot({
      path: root + `artifacts/template-library/preview-${width}.png`,
      fullPage: true,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.getByRole("button", { name: "关闭模板预览" }).click();
    await page.getByRole("button", { name: "下一页模板" }).click();
    await expect(page.locator(".template-entry")).toHaveCount(3);
    await page.goto("/create");
    await page.screenshot({
      path: root + `artifacts/template-library/upload-${width}.png`,
      fullPage: true,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });
}
