import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const key =
  readFileSync(new URL("../../.env", import.meta.url), "utf8").match(
    /^QUILL_API_KEY=(.*)$/m,
  )?.[1] || "";
const headers = { Authorization: `Bearer ${key}` };
const root = "/api/v1/knowledge";
const groups = {
  import: "导入与解析",
  analysis: "分块与分析",
  graph: "知识图谱",
  settings: "知识库设置",
  search: "高级检索",
};
let formCollection;
test.beforeAll(async ({ request }) => {
  // These forms belong to a collection. Seed this spec's own fixture so the
  // suite also works on an empty workspace, regardless of test-file ordering.
  const created = await request.post(root + "/collections", {
    headers,
    data: { name: "示例 · 表单回归 " + Date.now() },
  });
  expect(created.ok()).toBeTruthy();
  formCollection = (await created.json()).result;
});
test.afterAll(async ({ request }) => {
  if (formCollection)
    await request.post(root + "/operations/collection-delete", {
      headers,
      data: { collection_id: formCollection.id, confirmed: true },
    });
});
test.beforeEach(async ({ page }) =>
  page.addInitScript((key) => sessionStorage.setItem("quill-key", key), key),
);
for (const width of [1440, 390])
  test(`all 28 task forms remain reachable at ${width}px`, async ({
    page,
    request,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const catalog = (
      await (await request.get(root + "/capabilities", { headers })).json()
    ).operations;
    await page.goto("/knowledge");
    await page.getByRole("button", { name: new RegExp(formCollection.name) }).click();
    for (const [group, title] of Object.entries(groups)) {
      await page.getByRole("tab", { name: title, exact: true }).click();
      const nav = page.getByRole("navigation", { name: title + "操作" });
      await expect(nav).toBeVisible();
      for (const operation of catalog.filter((o) => o.group === group)) {
        if (width === 390)
          await nav
            .getByRole("button", { name: "选择" + title + "操作", exact: true })
            .click();
        await nav
          .getByRole("button", { name: operation.title, exact: true })
          .click();
        const heading = page.getByRole("heading", {
          name: operation.title,
          exact: true,
        });
        await expect(heading).toBeVisible();
        if (width === 390) {
          await expect(heading).toBeFocused();
          await expect(
            nav.getByRole("button", {
              name: "选择" + title + "操作",
              exact: true,
            }),
          ).toHaveAttribute("aria-expanded", "false");
        }
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        ).toBe(true);
      }
    }
    expect(errors).toEqual([]);
  });
test("shared file picker accepts a dropped QA file and preserves native required submission", async ({
  page,
  request,
}) => {
  const name = "示例 · 上传控件验收 " + Date.now();
  const created = await request.post(root + "/collections", {
    headers,
    data: { name },
  });
  const cid = (await created.json()).result.id;
  try {
    await page.goto("/knowledge");
    await page.getByRole("button", { name: new RegExp(name) }).click();
    await page.getByRole("tab", { name: "导入与解析", exact: true }).click();
    await page
      .getByRole("navigation", { name: "导入与解析操作" })
      .getByRole("button", { name: "批量导入问答对", exact: true })
      .click();
    const input = page.getByLabel("选择文件", { exact: true });
    await expect(input).toHaveAttribute("required", "");
    await input.focus();
    await expect(input).toBeFocused();
    const transfer = await page.evaluateHandle(() => {
      const dt = new DataTransfer();
      dt.items.add(
        new File(
          [
            JSON.stringify([
              { question: "示例：支持什么协议？", answer: "MQTT" },
            ]),
          ],
          "drop-example.json",
          { type: "application/json" },
        ),
      );
      return dt;
    });
    await input.dispatchEvent("drop", { dataTransfer: transfer });
    await expect(page.locator(".ui-file-picker-copy strong")).toHaveText(
      "drop-example.json",
    );
    await page
      .getByRole("button", { name: "批量导入问答对", exact: true })
      .last()
      .click();
    await expect(page.getByRole("region", { name: "操作结果" })).toContainText(
      "已导入 1 条，失败 0 条",
    );
  } finally {
    await request.post(root + "/operations/collection-delete", {
      headers,
      data: { collection_id: cid, confirmed: true },
    });
  }
});
