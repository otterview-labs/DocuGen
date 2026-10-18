import { test, expect } from "@playwright/test";

test("fresh tabs can use the local workspace without a key or authorization header", async ({
  page,
  context,
  request,
}) => {
  const status = await request.get("/api/v1/status");
  expect(status.status()).toBe(200);
  expect((await status.json()).authentication).toBe(false);
  const errors = [];
  const unauthorized = [];
  function observe(tab) {
    tab.on("pageerror", (error) => errors.push(error.message));
    tab.on("response", (response) => {
      if (response.status() === 401) unauthorized.push(response.url());
    });
  }
  observe(page);
  context.on("page", observe);
  for (const route of ["/templates", "/knowledge", "/writing", "/create"]) {
    const response = page.waitForResponse((r) =>
      r.url().endsWith("/api/v1/status"),
    );
    await page.goto(route);
    const connected = await response;
    expect(connected.status()).toBe(200);
    expect(connected.request().headers().authorization).toBeUndefined();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.locator(".connection-settings")).toHaveCount(0);
    expect(await page.evaluate(() => sessionStorage.getItem("quill-key"))).toBeNull();
  }
  const fresh = await context.newPage();
  await fresh.goto("/templates");
  await expect(fresh.locator(".template-entry").first()).toBeVisible();
  await fresh.reload();
  await expect(fresh.locator(".template-entry").first()).toBeVisible();
  await expect(fresh.locator(".connection-settings")).toHaveCount(0);
  expect(errors).toEqual([]);
  expect(unauthorized).toEqual([]);
});

test("a protected deployment still exposes connection settings after a 401", async ({
  page,
}) => {
  await page.route("**/api/v1/status", (route) =>
    route.fulfill({
      status: 401,
      json: { detail: "请在工作台设置访问密钥。" },
    }),
  );
  await page.goto("/templates");
  const connection = page.locator(".connection-settings");
  await expect(connection).toBeVisible();
  await connection.locator("summary").click();
  await expect(page.getByLabel("访问密钥", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "保存并连接" })).toBeVisible();
});
