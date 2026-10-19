import { test, expect } from "@playwright/test";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
const key =
  process.env.QUILL_TEST_KEY ||
  readFileSync(new URL("../../.env", import.meta.url), "utf8").match(
    /^QUILL_API_KEY=(.*)$/m,
  )?.[1] ||
  "";
test.beforeEach(async ({ page }) => {
  await page.addInitScript(
    (key) => sessionStorage.setItem("quill-key", key),
    key,
  );
});
for (const width of [1440, 1024, 390]) {
  test(`shared control contracts at ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 1000 });
    const response = await request.get("/api/templates", {
      headers: { Authorization: `Bearer ${key}` },
    });
    expect(response.ok()).toBeTruthy();
    const template = (await response.json()).templates.find(item =>
      ["项目名称", "负责人"].every(name => item.variables.some(variable => variable.name === name)));
    expect(template).toBeTruthy();
    const report = {};
    for (const route of [
      "/knowledge",
      "/templates",
      "/create",
      "/writing",
      "/generate/" + encodeURIComponent(template.name),
    ]) {
      await page.goto(route);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      if (route === "/create") await page.getByLabel("选择模板", { exact: true }).selectOption(template.name);
      if (route === "/knowledge")
        await expect(page.locator(".library-title h2")).toBeVisible();
      if (route === "/create" || route.startsWith("/generate/"))
        await expect(
          page.getByLabel("项目名称", { exact: true }),
        ).toBeVisible();
      await page.mouse.move(0, 0);
      const details = await page.locator(".app-content").evaluate((root) => {
        const visible = (e) =>
          e.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true });
        const buttons = [...root.querySelectorAll(".ui-button")]
          .filter(visible)
          .map((e) => {
            let s = getComputedStyle(e),
              classes = e.classList;
            return {
              label: (e.getAttribute("aria-label") || e.textContent).trim(),
              variant: [...classes].find((c) =>
                /^ui-button--(primary|secondary|ghost|text|danger)$/.test(c),
              ),
              compact:
                classes.contains("ui-button--compact") ||
                classes.contains("ui-button--text"),
              pressed: e.getAttribute("aria-pressed") === "true",
              height: e.getBoundingClientRect().height,
              family: s.fontFamily,
              font: s.fontSize,
              weight: s.fontWeight,
              radius: s.borderRadius,
              color: s.color,
              background: s.backgroundColor,
              icons: [...e.querySelectorAll("svg")].map((icon) => ({
                width: getComputedStyle(icon).width,
                height: getComputedStyle(icon).height,
                stroke: getComputedStyle(icon).strokeWidth,
              })),
            };
          });
        const fields = [
          ...root.querySelectorAll(".field-input,.ui-search-field>input"),
        ]
          .filter(visible)
          .map((e) => {
            let s = getComputedStyle(e);
            return {
              label: e.getAttribute("aria-label") || e.id,
              family: s.fontFamily,
              font: s.fontSize,
              weight: s.fontWeight,
              color: s.color,
            };
          });
        const contentButtons = [
          ...root.querySelectorAll(
            ".collection-item,.resource-title,.job-title,.search-result header>button",
          ),
        ]
          .filter(visible)
          .map((e) => ({
            label: e.textContent.trim().slice(0, 30),
            family: getComputedStyle(e).fontFamily,
          }));
        const h = root.querySelector(".page-heading h1"),
          hs = getComputedStyle(h);
        return {
          family: getComputedStyle(root).fontFamily,
          buttons,
          fields,
          contentButtons,
          heading: {
            font: hs.fontSize,
            weight: hs.fontWeight,
            color: hs.color,
          },
        };
      });
      report[route] = details;
      expect(details.heading).toEqual({
        font: width <= 640 ? "24px" : "28px",
        weight: "600",
        color: "rgb(32, 51, 46)",
      });
      const colors = {
        "ui-button--primary": "rgb(255, 253, 243)",
        "ui-button--secondary": "rgb(32, 51, 46)",
        "ui-button--ghost": "rgb(102, 115, 107)",
        "ui-button--text": "rgb(40, 100, 78)",
        "ui-button--danger": "rgb(157, 58, 51)",
      };
      for (const control of details.buttons) {
        expect(control.family, route + " " + control.label).toBe(
          details.family,
        );
        expect(control.font, route + " " + control.label).toBe("13px");
        expect(control.weight, control.label).toBe("500");
        expect(control.radius, control.label).toBe("6px");
        expect(control.height, route + " " + control.label).toBe(
          width <= 640
            ? control.compact
              ? 40
              : 44
            : control.compact
              ? 32
              : 40,
        );
        expect(control.color, route + " " + control.label).toBe(
          control.pressed ? "rgb(40, 100, 78)" : colors[control.variant],
        );
        for (const icon of control.icons)
          expect(icon, control.label).toEqual({
            width: "16px",
            height: "16px",
            stroke: "1.75px",
          });
      }
      for (const contentButton of details.contentButtons)
        expect(contentButton.family, route + " " + contentButton.label).toBe(
          details.family,
        );
      for (const field of details.fields) {
        expect(field.family, route + " " + field.label).toBe(details.family);
        expect(field.font, route + " " + field.label).toBe(
          width <= 640 ? "16px" : "14px",
        );
        expect(field.weight, field.label).toBe("400");
        expect(field.color, field.label).toBe("rgb(32, 51, 46)");
      }
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        route,
      ).toBe(true);
    }
    mkdirSync("../artifacts/ui-consistency", { recursive: true });
    writeFileSync(
      `../artifacts/ui-consistency/computed-${width}.json`,
      JSON.stringify(report, null, 2),
    );
  });
}
test("shared tab keyboard behavior and focus are preserved", async ({
  page,
}) => {
  await page.goto("/knowledge");
  await expect(page.locator(".library-title h2")).toBeVisible();
  const documents = page.getByRole("tab", { name: /资料管理/ });
  await documents.focus();
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("tab", { name: "检索与问答", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Home");
  await expect(documents).toBeFocused();
});

test("identical AI fill actions share the compact toolbar size", async ({
  page,
  request,
}) => {
  const templates = await request.get("/api/templates", {
    headers: { Authorization: `Bearer ${key}` },
  });
  const name = (await templates.json()).templates[0].name;
  const styles = [];
  for (const route of ["/create", "/generate/" + encodeURIComponent(name)]) {
    await page.goto(route);
    const button = page.getByRole("button", { name: "AI 填充", exact: true });
    await expect(button).toBeVisible();
    styles.push(
      await button.evaluate((e) => {
        const s = getComputedStyle(e);
        return {
          height: e.getBoundingClientRect().height,
          font: s.fontSize,
          weight: s.fontWeight,
          color: s.color,
          radius: s.borderRadius,
          family: s.fontFamily,
        };
      }),
    );
  }
  expect(styles[0]).toEqual(styles[1]);
});
test("shared form buttons preserve outline and explicit submit behavior", async ({
  page,
}) => {
  let submissions = 0;
  await page.route("**/api/v1/documents/outline", (route) =>
    route.fulfill({ json: { sections: ["虚构验收章节"] } }),
  );
  await page.route("**/api/v1/documents/jobs", (route) => {
    if (route.request().method() === "POST") {
      submissions++;
      return route.fulfill({
        status: 503,
        json: { detail: "尚未配置生成模型（受控验收响应）" },
      });
    }
    return route.continue();
  });
  await page.goto("/writing");
  await page.getByLabel("文档主题", { exact: true }).fill("虚构界面验收主题");
  await page.getByRole("button", { name: "生成大纲", exact: true }).click();
  await expect(
    page.getByLabel("章节（每行一章，可编辑）", { exact: true }),
  ).toHaveValue("虚构验收章节");
  expect(submissions).toBe(0);
  await page.getByRole("button", { name: "开始生成文档", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("尚未配置生成模型");
  expect(submissions).toBe(1);
});

test('canonical link buttons retain href, keyboard role and navigation',async({page})=>{
 await page.goto('/templates');const upload=page.locator('.heading-actions').getByRole('link',{name:'上传模板',exact:true});await expect(upload).toHaveAttribute('href','/create');await upload.focus();await upload.press('Enter');await expect(page.getByRole('heading',{level:1,name:'上传模板',exact:true})).toBeVisible();const back=page.locator('.heading-actions').getByRole('link',{name:'返回模板库',exact:true});await expect(back).toHaveAttribute('href','/templates');await back.focus();await back.press('Enter');await expect(page.getByRole('heading',{level:1,name:'文档模板',exact:true})).toBeVisible();await page.getByLabel('搜索模板',{exact:true}).fill('示例 · 项目验收记录');const use=page.locator('.template-entry').getByRole('link',{name:'使用模板',exact:true});await expect(use).toHaveAttribute('href',/\/generate\//);await use.focus();await use.press('Enter');await expect(page.getByRole('heading',{level:1})).toBeVisible();await expect(page.getByLabel('项目名称',{exact:true})).toBeVisible();
});
