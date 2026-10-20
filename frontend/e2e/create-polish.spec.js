import { test, expect } from "@playwright/test";

test("template preparation starts clearly and starter links lead to the selected document", async ({
  page,
}) => {
  await page.goto("/create");
  await expect(
    page.getByRole("heading", { name: "导入你的 Word 模板" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "使用已有模板" }),
  ).toBeVisible();
  await expect(page.getByLabel("选择模板", { exact: true })).toHaveValue("");
  await expect(page.getByRole("button", { name: "上传并入库" })).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "生成文档", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("link", { name: "浏览模板库", exact: true }).click();
  await page.getByRole("searchbox", { name: "搜索模板" }).fill("项目验收报告");
  await expect(page.locator(".template-entry")).toHaveCount(1);
  await page
    .getByRole("button", { name: "使用项目验收报告", exact: true })
    .click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    /项目验收报告/,
  );
});

test("library failure explains the problem and can be retried without blocking file import", async ({
  page,
}) => {
  let attempts = 0;
  await page.route("**/api/template-library", async (route) => {
    attempts++;
    if (attempts === 1)
      await route.fulfill({
        status: 503,
        json: { detail: "内置模板暂时不可用，请重试" },
      });
    else await route.continue();
  });
  await page.goto("/templates?source=builtin");
  await expect(page.getByRole("alert")).toContainText(
    "内置模板暂时不可用，请重试",
  );
  await expect(
    page.getByRole("link", { name: "上传模板", exact: true }).last(),
  ).toBeEnabled();
  await page.getByRole("button", { name: "重新加载", exact: true }).click();
  await expect(page.locator(".template-entry")).toHaveCount(9);
  await expect(page.getByRole("alert")).toHaveCount(0);
});
