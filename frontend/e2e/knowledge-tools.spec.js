import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const key =
  readFileSync(new URL("../../.env", import.meta.url), "utf8").match(
    /^QUILL_API_KEY=(.*)$/m,
  )?.[1] || "";
const headers = { Authorization: `Bearer ${key}` };
const root = "/api/v1/knowledge";
test.beforeEach(async ({ page }) => {
  await page.addInitScript(
    (key) => sessionStorage.setItem("quill-key", key),
    key,
  );
});
async function tool(page, tab, name) {
  await page.getByRole("tab", { name: tab, exact: true }).click();
  await page
    .getByRole("navigation", { name: tab + "操作" })
    .getByRole("button", { name, exact: true })
    .click();
}

test("real QA imports, actual chunks, analysis results, status and collection settings", async ({
  page,
  request,
}) => {
  const created = await request.post(root + "/collections", {
    headers,
    data: {
      name: "示例 · 功能验收 " + Date.now(),
      description: "合成验收数据",
    },
  });
  expect(created.ok()).toBeTruthy();
  const collection = (await created.json()).result;
  const cid = collection.id;
  try {
    await page.goto("/knowledge");
    await page
      .getByRole("button", { name: new RegExp(collection.name) })
      .click();
    await tool(page, "导入与解析", "添加问答对");
    await page
      .getByLabel("问题（必填）", { exact: true })
      .fill("验收周期是多久？");
    await page
      .getByLabel("答案（必填）", { exact: true })
      .fill("交付后 30 天。");
    await page
      .getByRole("button", { name: "添加问答对", exact: true })
      .last()
      .click();
    await expect(page.getByRole("region", { name: "操作结果" })).toContainText(
      "问答对已保存",
    );
    await tool(page, "导入与解析", "批量导入问答对");
    const template = page.waitForEvent("download");
    await page.getByRole("button", { name: "CSV 导入模板" }).click();
    expect((await template).suggestedFilename()).toBe("qa-template.csv");
    await page.getByLabel("选择文件", { exact: true }).setInputFiles({
      name: "qa.json",
      mimeType: "application/json",
      buffer: Buffer.from(
        JSON.stringify([
          { question: "MQTT 用于什么？", answer: "设备消息接入。" },
          { question: "", answer: "无效示例" },
        ]),
      ),
    });
    await page
      .getByRole("button", { name: "批量导入问答对", exact: true })
      .last()
      .click();
    await expect(page.getByRole("region", { name: "操作结果" })).toContainText(
      "已导入 1 条，失败 1 条",
    );
    await tool(page, "分块与分析", "实际存储分块");
    await page
      .getByLabel("资料（必填）", { exact: true })
      .selectOption({ label: "验收周期是多久？" });
    await page
      .getByRole("button", { name: "实际存储分块", exact: true })
      .last()
      .click();
    await expect(page.getByRole("region", { name: "操作结果" })).toContainText(
      "尚无存储分块",
    );
    await tool(page, "分块与分析", "查看已有分析");
    await page
      .getByLabel("资料（必填）", { exact: true })
      .selectOption({ label: "验收周期是多久？" });
    await page
      .getByRole("button", { name: "查看已有分析", exact: true })
      .last()
      .click();
    await expect(page.getByRole("region", { name: "操作结果" })).toContainText(
      "交付后 30 天。",
    );
    await tool(page, "知识库设置", "启用或停用资料");
    await page
      .getByLabel("资料（必填）", { exact: true })
      .selectOption({ label: "验收周期是多久？" });
    await page
      .getByRole("button", { name: "启用或停用资料", exact: true })
      .last()
      .click();
    await expect(page.getByRole("region", { name: "操作结果" })).toContainText(
      "成功 1 个",
    );
    const docs = (
      await (
        await request.get(root + "/resources", {
          headers,
          params: { collection_id: cid },
        })
      ).json()
    ).items;
    expect(docs.find((d) => d.title === "验收周期是多久？").enabled).toBe(
      false,
    );
    await tool(page, "知识库设置", "修改知识库设置");
    await page
      .getByLabel("集合类型", { exact: true })
      .selectOption("multimodal");
    await page
      .getByRole("button", { name: "修改知识库设置", exact: true })
      .last()
      .click();
    await expect(page.getByRole("region", { name: "操作结果" })).toContainText(
      "集合更新成功",
    );
    const detail = await request.post(root + "/operations/collection-detail", {
      headers,
      data: { collection_id: cid },
    });
    expect((await detail.json()).result.collection_type).toBe("multimodal");
    await tool(page, "知识库设置", "删除知识库");
    const remove = page
      .getByRole("button", { name: "删除知识库", exact: true })
      .last();
    await expect(remove).toBeDisabled();
    await page.getByLabel(/输入.*确认删除/).fill(collection.name);
    await expect(remove).toBeEnabled();
    await remove.click();
    await expect(
      page.getByRole("button", { name: new RegExp(collection.name) }),
    ).toHaveCount(0);
  } finally {
    await request
      .post(root + "/operations/collection-delete", {
        headers,
        data: { collection_id: cid, confirmed: true },
      })
      .catch(() => {});
  }
});

test("advanced keyword search and explicit unavailable model/graph states", async ({
  page,
  request,
}) => {
  const name = "示例 · 检索验收 " + Date.now();
  const created = await request.post(root + "/collections", {
    headers,
    data: { name },
  });
  const cid = (await created.json()).result.id;
  await request.post(root + "/text", {
    headers,
    data: {
      collection_id: cid,
      title: "示例验收资料",
      content: "项目验收周期为 30 天。",
    },
  });
  try {
    await page.goto("/knowledge");
    await page.getByRole("button", { name: new RegExp(name) }).click();
    await tool(page, "高级检索", "高级检索");
    await page.getByLabel("查询内容", { exact: true }).fill("验收");
    await page
      .getByRole("button", { name: "高级检索", exact: true })
      .last()
      .click();
    await expect(page.getByRole("region", { name: "操作结果" })).toContainText(
      "验收",
    );
    await page
      .getByRole("button", { name: "预览来源", exact: true })
      .first()
      .click();
    await expect(
      page.getByRole("tabpanel", { name: /资料管理/ }),
    ).toBeVisible();
    await expect(
      page.getByRole("complementary", { name: "资料预览" }),
    ).toBeVisible();
    // At tablet widths the preview is a drawer covering the task tabs.
    await page.getByRole("button", { name: "关闭资料预览", exact: true }).click();
    await expect(
      page.getByRole("complementary", { name: "资料预览" }),
    ).toHaveCount(0);
    await tool(page, "知识图谱", "查询实体与关系");
    await expect(page.getByText(/尚未启用图数据库。/)).toBeVisible();
    await expect(
      page.getByRole("button", { name: "查询实体与关系", exact: true }).last(),
    ).toBeDisabled();
    await tool(page, "分块与分析", "生成摘要与标签");
    await expect(page.getByText(/尚未配置知识引擎生成模型。/)).toBeVisible();
    await expect(
      page.getByRole("button", { name: "生成摘要与标签", exact: true }).last(),
    ).toBeDisabled();
  } finally {
    await request
      .post(root + "/operations/collection-delete", {
        headers,
        data: { collection_id: cid, confirmed: true },
      })
      .catch(() => {});
  }
});

test("staged upload, parse task history and actual task response", async ({
  page,
  request,
}) => {
  await page.goto("/knowledge");
  await tool(page, "导入与解析", "上传待解析文件");
  await page.getByLabel("选择文件", { exact: true }).setInputFiles({
    name: "示例解析.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("示例资料：项目验收周期为交付后 30 天。"),
  });
  await page
    .getByRole("button", { name: "上传待解析文件", exact: true })
    .last()
    .click();
  await expect(page.getByRole("region", { name: "操作结果" })).toContainText(
    "/uploads/",
  );
  const raw = await page.locator(".tools-raw pre").textContent();
  const url = JSON.parse(raw).result.url;
  await tool(page, "导入与解析", "批量解析文件");
  await page
    .getByLabel("已上传文件地址（每行一个）（必填）", { exact: true })
    .fill(url);
  await page
    .getByRole("button", { name: "批量解析文件", exact: true })
    .last()
    .click();
  await expect(page.getByRole("region", { name: "操作结果" })).toContainText(
    "批量解析任务已启动",
  );
  await page.getByRole("button", { name: "查看任务进度", exact: true }).click();
  await expect(
    page.getByLabel("任务编号（必填）", { exact: true }),
  ).not.toHaveValue("");
  await page
    .getByRole("button", { name: "解析任务进度", exact: true })
    .last()
    .click();
  await expect(page.getByRole("region", { name: "操作结果" })).toContainText(
    "解析任务编号",
  );
  await expect(
    page.getByRole("region", { name: "最近的解析任务" }),
  ).toBeVisible();
  const batch = await page.getByLabel("任务编号（必填）").inputValue();
  let task;
  await expect
    .poll(async () => {
      task = (
        await (
          await request.post(root + "/operations/batch-status", {
            headers,
            data: { batch_id: batch },
          })
        ).json()
      ).result;
      return task.completed + task.failed;
    })
    .toBe(1);
  expect(task.completed).toBe(1);
  const rid = task.resources[0].id;
  const resource = await (
    await request.get(root + "/resources/" + rid, { headers })
  ).json();
  expect(resource.has_original).toBe(true);
  const download = await request.get(root + "/resources/" + rid + "/download", {
    headers,
  });
  expect(download.ok()).toBeTruthy();
  expect((await download.body()).toString()).toBe(
    "示例资料：项目验收周期为交付后 30 天。",
  );
  await request.delete(root + "/resources/" + rid, { headers });
});

test("metadata loads existing values and controlled graph renders entities and links", async ({
  page,
  request,
}) => {
  const name = "示例 · 元数据验收 " + Date.now();
  const created = await request.post(root + "/collections", {
    headers,
    data: { name },
  });
  const cid = (await created.json()).result.id;
  await request.post(root + "/text", {
    headers,
    data: {
      collection_id: cid,
      title: "示例 · 接入资料",
      content: "设备支持 MQTT。",
    },
  });
  try {
    const docs = (
      await (
        await request.get(root + "/resources", {
          headers,
          params: { collection_id: cid },
        })
      ).json()
    ).items;
    await page.goto("/knowledge");
    await page.getByRole("button", { name: new RegExp(name) }).click();
    await tool(page, "知识库设置", "编辑资料详细信息");
    await page
      .getByRole("combobox", { name: "资料（必填）" })
      .selectOption(docs[0].content_id);
    await expect(page.getByLabel("资料标题", { exact: true })).toHaveValue(
      docs[0].title,
    );
    const updated = page.waitForResponse((r) =>
      r.url().endsWith("/operations/metadata"),
    );
    await page
      .getByLabel("资料说明", { exact: true })
      .fill("示例说明：设备接入资料。");
    await page
      .getByRole("button", { name: "编辑资料详细信息", exact: true })
      .last()
      .click();
    expect((await updated).status()).toBe(200);
    const stored = await (
      await request.get(root + "/resources/" + docs[0].resource_id, { headers })
    ).json();
    expect(stored.description).toContain("示例说明");
    await page.route("**/api/v1/knowledge/capabilities", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.operations = body.operations.map((o) => ({
        ...o,
        available: true,
        reason: "",
      }));
      await route.fulfill({ response, json: body });
    });
    await page.route("**/api/v1/knowledge/operations/graph-view", (route) =>
      route.fulfill({
        json: {
          success: true,
          message: "合成图谱示例，仅用于界面验收。",
          result: {
            nodes: [
              { id: "device", name: "示例设备" },
              { id: "gateway", name: "示例网关" },
            ],
            edges: [{ source: "device", target: "gateway", relation: "接入" }],
          },
        },
      }),
    );
    await page.reload();
    await tool(page, "知识图谱", "知识图谱浏览");
    await page
      .getByRole("button", { name: "知识图谱浏览", exact: true })
      .last()
      .click();
    await expect(page.getByRole("img", { name: "实体关系网络" })).toBeVisible();
    await expect(page.locator(".tools-graph line")).toHaveCount(1);
    await expect(page.getByRole("region", { name: "操作结果" })).toContainText(
      "示例设备",
    );
  } finally {
    await request
      .post(root + "/operations/collection-delete", {
        headers,
        data: { collection_id: cid, confirmed: true },
      })
      .catch(() => {});
  }
});
