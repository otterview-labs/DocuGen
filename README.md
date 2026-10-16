# Otterview Quill

**知识与文档工作台。让资料成为有据可查的文档。**

Quill 将 JetLinks 知识引擎与 DocuGen 的 Word 模板处理能力整理在一个独立仓库中。你可以建立知识集合、保存和检索文本资料，使用 Word 模板填充业务内容，也可以按章节检索资料、调用模型生成文档并下载 DOCX。

当前为 **0.1.0 本地整合版**。采用一个共享工作区和一个访问密钥，适合个人或可信团队自部署。没有多租户、独立用户权限或协同编辑。来源记录表示模型取材依据，不等同于逐句事实核验。

[English](README.en.md) · [架构与边界](docs/ARCHITECTURE.md) · [源码来源与发布条件](docs/PROVENANCE.md)

## 已接入的流程

- **知识库**：集合列表和创建、文本资料入库、关键词/语义/智能检索及基于资料的问答。知识引擎在仓库内，通过内部 HTTP 协议连接。
- **模板文档**：上传 DOCX，提取 `【变量】` 和 `{{变量}}`，人工填写或使用 AI 辅助，导出 Word。复用 DocuGen 跨 run 占位符替换及表格处理。
- **文档写作**：生成并编辑大纲、按章节取材和写作、查看进度及中间内容、下载 Word。
- **持久化**：模板元数据、生成任务和产物来源写入 SQLite；知识资料与向量由知识引擎管理。重启后未完成任务标为“已中断”，保留内容，可重新生成。
- **失败可见**：知识引擎、模型不可用或所选知识库无命中时返回明确错误，不返回示例生成内容。

## 本地启动工作台

需要 Python 3.11+、Node.js 22.12+。在仓库根目录运行：

```bash
uv venv --python 3.11
uv pip install --python .venv/bin/python -e '.[dev]'
cp .env.example .env
# 编辑 .env：设置 QUILL_LLM_BASE_URL、QUILL_LLM_MODEL 和所需的 API Key。
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/uvicorn quill.main:app --host 127.0.0.1 --port 8080 --workers 1
```

打开 [工作台](http://127.0.0.1:8080) 或 [API 文档](http://127.0.0.1:8080/docs)。设置了 `QUILL_API_KEY` 后，在工作台右上角填入访问密钥。密钥仅保存在当前浏览器标签页的 sessionStorage 中；所有用户共用该密钥和工作区。不要将它当作独立用户登录系统。

没有模型时仍可上传模板、手动填写并导出 Word。没有知识引擎时可用手动参考资料调用模型写作；知识库页面会说明连接问题。模型接口使用 OpenAI-compatible `/chat/completions` 协议，`QUILL_LLM_BASE_URL` 填基础 URL（通常以 `/v1` 结尾）。

开发前端可运行 `npm --prefix frontend run dev`，Vite 会代理 `/api` 和 `/download` 到本机 8080。

需要无需 Docker 的本地文本知识库时，先安装文本引擎依赖，再启动两个本地进程：

```bash
uv pip install --python .venv/bin/python -r services/knowledge/requirements.quill.txt
.venv/bin/python scripts/dev.py
```

此模式使用本地 SQLite，默认支持文本入库和关键词检索；不承诺语义索引能力。知识库数据库位于 `data/knowledge.db`。macOS 如缺少 libmagic，可执行 `brew install libmagic`。不要同时运行另一套占用 8080 或 8006 的服务。

## 启动完整知识引擎

```bash
# 编辑 .env：设置 QUILL_API_KEY 和 POSTGRES_PASSWORD，推荐分别使用随机值。
docker compose -p quill up -d --build
```

Compose 启动工作台、知识引擎、PostgreSQL + pgvector。只有工作台 8080 映射到 **127.0.0.1**；知识引擎和数据库不发布宿主机端口。三个服务的数据均存放在命名卷中。备份时分别保存三个卷；`docker compose down` 保留卷，`down -v` 会删除数据。

知识引擎默认按内部可信服务运行，跳过其旧用户认证，由 Quill 网关控制入口。**不要直接对公网发布知识引擎端口。** 网络共享需要自行配置 TLS 反向代理，并保留访问密钥。当前使用单个 Quill 进程和内置任务执行器，不支持多 worker 或横向扩容。

语义检索需要配置可调用的 Embedding 模型；维度由 `QUILL_EMBEDDING_DIMENSION` 指定，必须与模型输出一致。未配置时可以保存文本并使用关键词检索，界面会区分“已保存”和“已建立向量索引”。写作和 Embedding 默认复用同一模型网关地址与凭据。

原知识引擎保留文件、多模态和知识图谱相关代码，但第一版工作台只接入文本资料。OCR、视频、图谱等旧功能不属于已验证的默认部署能力；上游的 `requirements*.txt` 作为迁移参考保留，默认引擎使用 `requirements.quill.txt`。

## 验证

```bash
.venv/bin/python -m pytest tests
.venv/bin/python -m ruff check quill tests
# 安装知识引擎文本配置后，在独立 Python 进程中运行继承测试。
uv pip install --python .venv/bin/python -r services/knowledge/requirements.quill.txt
(cd services/knowledge && ../../.venv/bin/python -m pytest tests)
npm --prefix frontend run build
```

根目录测试覆盖模板上传、跨 run 替换、表格填充、下载认证、来源存储、知识库协议与分页、生成任务和重启恢复。模型契约使用受控响应，默认测试不消耗模型额度。真实模型质量及复杂 Word 排版需用自己的资料单独验收。

浏览器回归使用正在运行的本地服务（默认端口 18080，可通过 `QUILL_TEST_URL` 修改），会创建明确命名的验收模板：

```bash
(cd frontend && QUILL_TEST_URL=http://127.0.0.1:8080 npx playwright test)
```

测试从本地 `.env` 读取工作区访问密钥，也可设置 `QUILL_TEST_KEY`。运行前需要 Playwright Chromium 浏览器和根目录 `.venv`。

## 目录

```text
quill/                     统一 API、持久化、模型与知识库适配、生成任务
quill/legacy/              从 DocuGen 提取的模板处理和 Word 导出方法
frontend/                  基于 DocuGen Vue 工作台的统一入口
services/knowledge/        JetLinks 知识引擎源码与独立运行依赖
tests/                     Quill 集成与契约测试
docs/                      架构、来源清单与发布状态
compose.yaml               完整本地部署入口
```

项目归属 Otterview Labs。本地整合不改变上游代码的著作权或授权；公开发布前必须完成 [来源与授权核对](docs/PROVENANCE.md)。
