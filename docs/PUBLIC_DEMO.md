# 公开演示部署

普通 `compose.yaml` 是单个共享工作区，不提供用户或租户隔离，不应直接无密钥公开。匿名演示使用独立入口 `quill.demo:create_demo --factory`，不改变自部署版的共享工作区行为。

## 演示范围

- 每个浏览器获得随机、服务器签名的 HttpOnly / Secure / SameSite=Strict Cookie，模板、下载、任务及原文件存入独立目录。
- 知识库由服务器端持久化归属清单管理；请求中的集合与资料 ID 必须属于当前会话。检索结果再次校验集合范围。引擎高级工具不向匿名访客开放。
- 开放 12 个内置模板、DOCX 上传、手动填写与 Word 导出，以及文本资料导入、资料预览、原文件下载、修改、删除和关键词检索。
- 演示不调用付费模型，也不开放未计量的匿名 AI 调用；AI、向量、多模态、图谱等功能由自部署版提供。界面保留功能入口并说明不可用原因。
- 每个会话有效期为创建后 2 小时；过期数据在后台每 60 秒尝试清理，包括引擎内的集合与资料。清理失败保留占位和重试，不能让过期数据继续被读取。
- 每次演示最多 3 个知识库、20 份资料、50 万字符、100 次写操作和 40 MiB 本地存储；单文件最多 5 MiB、DOCX 解压最多 20 MiB。单份资料最多 5 万字符。
- 最多同时保留 32 个会话；每个 IP 每分钟 180 个动态请求、每小时 8 个新会话。静态资源不分配会话。服务器最多同时处理 4 个动态请求，工作进程必须为 1。
- Cookie 是当前匿名会话的访问凭据；拥有同一 Cookie 的浏览器可访问同一会话。这不是实名账户系统。到期前应下载需要保留的成果，勿上传敏感信息。
- 自动过期清理针对服务器数据；当前标签页的草稿仍由浏览器 sessionStorage 管理，关闭标签页后结束其生命周期。

## 启动

使用独立目录、Compose 项目和数据卷，不复制开发环境 `.env` 或业务数据。先在部署目录配置 `.env`：

```dotenv
POSTGRES_PASSWORD=replace-with-a-new-random-server-side-password
DOCUGEN_DEMO_PORT=18080
QUILL_LLM_MODEL=
QUILL_LLM_API_KEY=
```

需要 Docker Compose 2.24.4 或更新版本，以支持 `!override` 端口替换。

```bash
docker compose -f compose.yaml -f deploy/compose.demo.yaml -p docugen-demo up -d --build
```

应用仅监听 `127.0.0.1:18080`。知识引擎 8006 与 PostgreSQL 5432 不映射宿主端口。将 `deploy/Caddyfile.demo` 作为独立站点加入现有 Caddy 配置，校验通过后 reload。Caddy 必须覆盖 `X-Real-IP`，ASGI 保持 `--no-proxy-headers`。使用 HTTPS，匿名 Cookie 默认只通过 HTTPS 发送；本地测试可单独设置 `QUILL_DEMO_COOKIE_SECURE=false`，公网不得这样配置。

生产机器已有业务时，先检查端口、资源、站点配置和磁盘余量。新实例上线后要使用两个不同 Cookie 的客户端验证模板、资料、检索与下载的隔离，再验证超额请求与过期清理；只看到页面或健康检查 200 不代表完成验收。

## 回退

移除新增的 DocuGen Caddy 站点并校验 reload，再执行同样 Compose 参数下的 `stop`。保留数据卷供排查；不要运行全机 Docker prune 或更改其他项目的网络、数据库、端口。用户资料随演示过期清理，不作为长期资料库保存。
