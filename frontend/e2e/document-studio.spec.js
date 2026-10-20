import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../../", import.meta.url));
async function starter(request, id) {
  const r = await request.post("/api/template-library/" + id + "/use");
  expect(r.ok()).toBe(true);
  return (await r.json()).template;
}
async function downloadedText(page) {
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载 Word", exact: true }).click();
  return execFileSync(
    root + ".venv/bin/python",
    [
      "-c",
      "from docx import Document;import sys;d=Document(sys.argv[1]);print('\\n'.join([p.text for p in d.paragraphs]+[c.text for t in d.tables for r in t.rows for c in r.cells]))",
      await (await download).path(),
    ],
    { encoding: "utf8" },
  );
}
test("grouped native fields, content review, tab draft recovery and stale download invalidation", async ({
  page,
  request,
}) => {
  const item = await starter(request, "project-plan");
  await page.goto("/generate/" + encodeURIComponent(item.name));
  await expect(page.getByLabel("项目名称", { exact: true })).toHaveAttribute(
    "type",
    "text",
  );
  await expect(page.getByLabel("编制日期", { exact: true })).toHaveAttribute(
    "type",
    "date",
  );
  await expect(
    page.getByLabel("项目背景与目标", { exact: true }),
  ).toHaveJSProperty("tagName", "TEXTAREA");
  await page.getByLabel("项目名称", { exact: true }).fill("合成 · 北岸交付");
  await page.getByLabel("编制日期", { exact: true }).fill("2026-10-20");
  await page
    .getByLabel("项目背景与目标", { exact: true })
    .fill("完成设备联调\n核对交付范围");
  await expect(
    page.getByRole("region", { name: "内容核对预览" }),
  ).toContainText("合成 · 北岸交付");
  await expect(
    page.getByRole("region", { name: "内容核对预览" }),
  ).toContainText("完成设备联调\n核对交付范围");
  await page.locator(".reference-disclosure summary").click();
  await page
    .getByLabel("手动参考资料", { exact: true })
    .fill("合成参考资料，不调用模型。");
  await page.reload();
  await expect(page.getByLabel("项目名称", { exact: true })).toHaveValue(
    "合成 · 北岸交付",
  );
  await expect(
    page.getByText("已恢复当前标签页的草稿", { exact: true }),
  ).toBeVisible();
  await page.locator(".reference-disclosure summary").click();
  await expect(page.getByLabel("手动参考资料", { exact: true })).toHaveValue(
    "合成参考资料，不调用模型。",
  );
  await page.getByRole("button", { name: "生成文档", exact: true }).click();
  const text = await downloadedText(page);
  expect(text).toContain("2026-10-20");
  expect(text).toContain("合成 · 北岸交付");
  expect(text).toContain("完成设备联调\n核对交付范围");
  await page
    .getByLabel("项目名称", { exact: true })
    .fill("合成 · 修订后的交付");
  await expect(
    page.getByRole("button", { name: "下载 Word", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("内容已更改，请重新生成文档。", { exact: true }),
  ).toBeVisible();
});
test("SPA template switching keeps separate drafts", async ({
  page,
  request,
}) => {
  const project = await starter(request, "project-plan");
  await starter(request, "weekly-report");
  await page.goto("/generate/" + encodeURIComponent(project.name));
  await page
    .getByLabel("项目名称", { exact: true })
    .fill("合成 · 项目专属草稿");
  await page.getByRole("button", { name: "返回模板库", exact: true }).click();
  await page.getByLabel("搜索模板", { exact: true }).fill("工作周报");
  await page.getByRole("button", { name: "使用工作周报", exact: true }).click();
  await expect(page.locator("h1")).toHaveText("工作周报");
  await expect(page.getByLabel("项目名称", { exact: true })).toHaveCount(0);
  await page
    .getByLabel("团队或项目", { exact: true })
    .fill("合成 · 周报专属草稿");
  await page.getByRole("button", { name: "返回模板库", exact: true }).click();
  await page.getByLabel("搜索模板", { exact: true }).fill("项目实施方案");
  await page
    .getByRole("button", { name: "使用项目实施方案", exact: true })
    .click();
  await expect(page.getByLabel("项目名称", { exact: true })).toHaveValue(
    "合成 · 项目专属草稿",
  );
  await expect(page.getByLabel("团队或项目", { exact: true })).toHaveCount(0);
});
test("non ISO dates and multiline short fields survive fill, reload and Word export", async ({
  page,
  request,
}) => {
  const item = await starter(request, "project-plan");
  await page.route("**/api/ai-fill-template-variables", (route) =>
    route.fulfill({
      json: {
        variables: {
          编制日期: "2026年10月20日",
          负责人: "合成人员甲\n合成人员乙",
        },
        sources: [],
      },
    }),
  );
  await page.goto("/generate/" + encodeURIComponent(item.name));
  await page.getByRole("button", { name: "AI 填充", exact: true }).click();
  await expect(page.getByLabel("编制日期", { exact: true })).toHaveAttribute(
    "type",
    "text",
  );
  await expect(page.getByLabel("负责人", { exact: true })).toHaveJSProperty(
    "tagName",
    "TEXTAREA",
  );
  await page.reload();
  await expect(page.getByLabel("编制日期", { exact: true })).toHaveValue(
    "2026年10月20日",
  );
  await expect(page.getByLabel("负责人", { exact: true })).toHaveValue(
    "合成人员甲\n合成人员乙",
  );
  await page.getByRole("button", { name: "生成文档", exact: true }).click();
  const text = await downloadedText(page);
  expect(text).toContain("2026年10月20日");
  expect(text).toContain("合成人员甲\n合成人员乙");
});
test("storage and generation failures preserve manual editing and allow retry", async ({
  page,
  request,
}) => {
  const item = await starter(request, "weekly-report");
  await page.addInitScript(() => {
    Storage.prototype.setItem = function () {
      throw new DOMException("Storage quota", "QuotaExceededError");
    };
  });
  let calls = 0;
  await page.route("**/api/generate-from-template", (r) =>
    ++calls === 1
      ? r.fulfill({ status: 503, json: { detail: "合成故障：请重试" } })
      : r.continue(),
  );
  await page.goto("/generate/" + encodeURIComponent(item.name));
  await page
    .getByLabel("团队或项目", { exact: true })
    .fill("合成 · 无存储仍可导出");
  await expect(
    page.getByText("无法暂存草稿，请及时生成并下载文档", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "生成文档", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("合成故障");
  await expect(page.getByLabel("团队或项目", { exact: true })).toHaveValue(
    "合成 · 无存储仍可导出",
  );
  await page.getByRole("button", { name: "生成文档", exact: true }).click();
  expect(await downloadedText(page)).toContain("合成 · 无存储仍可导出");
});
test("cover preview opens real first page by keyboard and restores focus on Escape", async ({
  page,
}) => {
  await page.goto("/templates?source=builtin");
  const trigger = page.getByRole("button", {
    name: "查看项目实施方案版式预览",
    exact: true,
  });
  await trigger.focus();
  await trigger.press("Enter");
  const preview = page.getByRole("region", { name: "模板结构预览" });
  await expect(preview).toBeFocused();
  await expect(preview.locator("img")).toBeVisible();
  await expect
    .poll(() =>
      preview.locator("img").evaluate((e) => e.complete && e.naturalWidth > 0),
    )
    .toBe(true);
  await page.keyboard.press("Escape");
  await expect(preview).toHaveCount(0);
  await expect(trigger).toBeFocused();
});
test("invalid import is rejected before any upload request", async ({
  page,
}) => {
  const calls = [];
  page.on("request", (r) => {
    if (r.url().endsWith("/api/upload-template")) calls.push(r.url());
  });
  await page.goto("/create");
  await page.locator("input[type=file]").setInputFiles({
    name: "selected.docx",
    mimeType:
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: Buffer.from("synthetic extension validation"),
  });
  await expect(
    page.getByRole("button", { name: "上传并入库", exact: true }),
  ).toBeEnabled();
  await page.locator("input[type=file]").setInputFiles({
    name: "unsupported.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("synthetic"),
  });
  await expect(page.getByRole("alert")).toContainText(".docx");
  await expect(
    page.getByRole("button", { name: "上传并入库", exact: true }),
  ).toBeDisabled();
  expect(calls).toEqual([]);
});

test("mobile export shortcut stays available and moves focus to generation", async ({
  page,
  request,
}) => {
  const item = await starter(request, "project-plan");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/generate/" + encodeURIComponent(item.name));
  const shortcut = page.getByRole("link", { name: "核对与导出", exact: true });
  await expect(shortcut).toBeInViewport();
  await shortcut.click();
  await expect(
    page.getByRole("button", { name: "生成文档", exact: true }),
  ).toBeFocused();
  await expect(
    page.getByRole("button", { name: "生成文档", exact: true }),
  ).toBeInViewport();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("manual editing keeps focus across short-field length and restored multiline boundaries", async ({
  page,
  request,
}) => {
  const item = await starter(request, "project-plan");
  await page.goto("/generate/" + encodeURIComponent(item.name));
  const field = page.getByLabel("项目名称", { exact: true }),
    longText = "合成" + "a".repeat(117) + "继续输入超过一百二十个字符";
  await field.fill(longText.slice(0, 119));
  await field.press("End");
  await field.pressSequentially(longText.slice(119));
  await expect(field).toBeFocused();
  await expect(field).toHaveJSProperty("tagName", "INPUT");
  await expect(field).toHaveValue(longText);
  await page.getByRole("button", { name: "生成文档", exact: true }).click();
  expect(await downloadedText(page)).toContain(longText);
  await page.route("**/api/ai-fill-template-variables", (r) =>
    r.fulfill({
      json: { variables: { 项目名称: "合成甲\n合成乙" }, sources: [] },
    }),
  );
  await page.getByRole("button", { name: "AI 填充", exact: true }).click();
  await expect(field).toHaveJSProperty("tagName", "TEXTAREA");
  await page.reload();
  await expect(field).toHaveValue("合成甲\n合成乙");
  await expect(field).toHaveJSProperty("tagName", "TEXTAREA");
  await field.focus();
  await field.press("ControlOrMeta+A");
  await field.press("Backspace");
  await expect(field).toBeFocused();
  await expect(field).toHaveJSProperty("tagName", "TEXTAREA");
  await field.pressSequentially("restored draft edited without losing focus");
  await expect(field).toBeFocused();
  await expect(field).toHaveValue("restored draft edited without losing focus");
  await page.getByRole("button", { name: "生成文档", exact: true }).click();
  expect(await downloadedText(page)).toContain(
    "restored draft edited without losing focus",
  );
});
