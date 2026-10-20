import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

test("re-extraction preserves confirmed fields and spaced placeholders render on both template screens", async ({
  page,
  request,
}) => {
  const root = fileURLToPath(new URL("../../", import.meta.url));
  const name = "示例 · 变量重提取回归 " + Date.now();
  const fixture = execFileSync(root + ".venv/bin/python", [
    "-c",
    "from docx import Document;import io,sys;d=Document();d.add_paragraph('项目：{{ 项目名称 }}；负责人：【 负责人 】');d.sections[0].header.paragraphs[0].text='项目：{{ 项目名称 }}';b=io.BytesIO();d.save(b);sys.stdout.buffer.write(b.getvalue())",
  ]);
  const upload = await request.post("/api/upload-template", {
    multipart: {
      template_name: name,
      file: {
        name: "spaces.docx",
        mimeType:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        buffer: fixture,
      },
    },
  });
  expect(upload.status()).toBe(200);
  for (const route of ["/create", "/generate/" + encodeURIComponent(name)]) {
    await page.goto(route);
    if (route === "/create")
      await page.getByLabel("选择模板", { exact: true }).selectOption(name);
    await page.getByLabel("项目名称", { exact: true }).fill("人工确认项目");
    await page.getByLabel("负责人", { exact: true }).fill("示例乙（已确认）");
    const refreshed = page.waitForResponse((r) =>
      r.url().endsWith("/api/refresh-template-variables"),
    );
    await page
      .getByRole("button", { name: "重新提取变量", exact: true })
      .click();
    expect((await refreshed).status()).toBe(200);
    await expect(page.getByLabel("项目名称", { exact: true })).toHaveValue(
      "人工确认项目",
    );
    await expect(page.getByLabel("负责人", { exact: true })).toHaveValue(
      "示例乙（已确认）",
    );
    await page.getByRole("button", { name: "生成文档", exact: true }).click();
    const downloading = page.waitForEvent("download");
    await page.getByRole("button", { name: "下载 Word", exact: true }).click();
    const download = await downloading;
    const text = execFileSync(
      root + ".venv/bin/python",
      [
        "-c",
        "from docx import Document;import sys;d=Document(sys.argv[1]);print('\\n'.join([p.text for p in d.paragraphs]+[p.text for s in d.sections for p in s.header.paragraphs]))",
        await download.path(),
      ],
      { encoding: "utf8" },
    );
    expect(text).toContain("项目：人工确认项目；负责人：示例乙（已确认）");
    expect(text).not.toContain("{{");
    expect(text).not.toContain("【");
  }
});
