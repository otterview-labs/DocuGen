import { test, expect } from "@playwright/test";

const target = process.env.DOCUGEN_DEMO_URL;
test.skip(!target, "Opt in against an isolated public demo using DOCUGEN_DEMO_URL.");

test("anonymous demo has a real Word workflow and denies another browser's data", async ({ browser }) => {
  test.setTimeout(120000);
  const a = await browser.newContext({ baseURL: target, acceptDownloads: true });
  const b = await browser.newContext({ baseURL: target });
  try {
    const page = await a.newPage();
    const failures = [];
    page.on("pageerror", (error) => failures.push(error.message));
    page.on("response", (response) => {
      if (response.status() >= 500) failures.push(response.status() + " " + response.url());
    });
    await page.goto("/templates?source=builtin");
    await expect(page.getByText(/访客资料互相隔离/)).toBeVisible();
    await page.getByRole("button", { name: "使用项目实施方案", exact: true }).click();
    await page.getByLabel("项目名称", { exact: true }).fill("Synthetic public demo acceptance");
    const rendered = page.waitForResponse((response) =>
      response.url().endsWith("/api/generate-from-template") && response.request().method() === "POST",
    );
    await page.getByRole("button", { name: "生成文档", exact: true }).click();
    const response = await rendered;
    expect(response.status()).toBe(200);
    const filename = (await response.json()).filename;
    const downloadEvent = page.waitForEvent("download");
    await page.getByRole("button", { name: "下载 Word", exact: true }).click();
    expect(await (await downloadEvent).failure()).toBeNull();
    const other = await b.newPage();
    await other.goto("/templates?source=workspace");
    expect((await (await b.request.get("/api/templates")).json()).templates).toEqual([]);
    expect((await b.request.get("/download/" + filename)).status()).toBe(404);
    const collection = await a.request.post("/api/v1/knowledge/collections", {
      data: { name: "Synthetic browser isolation" },
    });
    expect(collection.status()).toBe(200);
    const id = (await collection.json()).result.id;
    const text = await a.request.post("/api/v1/knowledge/text", {
      data: { collection_id: id, title: "Synthetic browser source", content: "ISOLATED_BROWSER_DEMO_ONLY" },
    });
    expect(text.status()).toBe(200);
    const rid = (await text.json()).result.resource_id;
    expect((await b.request.get("/api/v1/knowledge/resources/" + rid)).status()).toBe(404);
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      for (const path of ["/templates?source=builtin", "/create", "/knowledge", "/writing"]) {
        await page.goto(path);
        await expect(page.locator("main")).toBeVisible();
        await expect(page.getByText(/访客资料互相隔离/)).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      }
    }
    expect(failures).toEqual([]);
  } finally {
    await a.close();
    await b.close();
  }
});
