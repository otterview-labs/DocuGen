#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JetLinksAI 主应用程序
基于FastAPI的智能文档处理和分析系统
"""

import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

# 加载环境变量配置
from dotenv import load_dotenv
from app.runtime_paths import get_runtime_root

PROJECT_ROOT = get_runtime_root()
load_dotenv(PROJECT_ROOT / ".env")  # 优先加载当前服务目录下的 .env

# 解决OpenMP重复加载问题 - 必须在导入numpy/torch等库之前设置
os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')
os.environ.setdefault('OMP_NUM_THREADS', '1')

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# 导入API路由
from app.api.v1.router import router as api_router
from app.config import settings
from app.services.health_service import build_health_report
from app.services.startup_service import initialize_runtime_services

# 设置日志 - 使用自定义的logger工具，同时输出到控制台和文件
from app.shared.utils.logger_util import get_logger

# 配置根日志器，同时输出到控制台（彩色）和文件
# 统一使用 storage/logs/ 目录
logger = get_logger(
    name=__name__,
    level=logging.INFO,
    file_name="app.log",  # 日志文件名，会保存到 storage/logs/YYYY-MM-DD/app.log
    color_console=True,   # 控制台使用彩色输出
    rotate="size",        # 按文件大小轮转
    max_bytes=10 * 1024 * 1024,  # 10MB
    backup_count=5,       # 保留5个备份文件
    log_root=settings.storage.LOGS_DIR  # 使用storage配置的日志目录
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用程序生命周期管理
    """
    # 启动时执行
    logger.info("启动 JetLinksAI 应用程序...")
    logger.info(f"当前环境模式: {settings.ENVIRONMENT}")

    if settings.is_development:
        logger.info("🔧 开发模式：已启用，无需登录验证")
    elif settings.is_production:
        logger.info("🚀 生产模式：已启用，需要完整认证")
    elif settings.is_test:
        logger.info("🧪 测试模式：已启用，适合自动化测试")

    try:
        # 初始化服务
        await initialize_services()
        logger.info("服务初始化完成")
        logger.info("JetLinksAI 应用程序启动成功！")

    except Exception as e:
        logger.error(f"应用程序启动失败: {e}")
        raise

    yield

    # 关闭时执行
    logger.info("正在关闭 JetLinksAI 应用程序...")

    try:
        # 清理资源
        await cleanup_services()
        logger.info("资源清理完成")

    except Exception as e:
        logger.error(f"应用程序关闭时出错: {e}")


async def initialize_services():
    """
    初始化应用程序服务
    """
    startup_summary = await initialize_runtime_services()

    logger.info("=" * 60)
    logger.info("🚀 JetLinksAI 服务已就绪！")
    logger.info("📍 访问地址:")
    logger.info("   - API文档: http://localhost:%s/docs", settings.PORT)
    logger.info("   - 备用文档: http://localhost:%s/redoc", settings.PORT)
    logger.info("   - 健康检查: http://localhost:%s/health", settings.PORT)
    logger.info(
        "   - 启动检查: db_checked=%s, db_ok=%s, db_initialized=%s",
        startup_summary.get("database_connection_checked"),
        startup_summary.get("database_connection_ok"),
        startup_summary.get("database_initialized"),
    )
    logger.info("=" * 60)


async def cleanup_services():
    """
    清理应用程序资源
    """
    # 这里可以添加资源清理逻辑
    # 例如：关闭数据库连接、释放模型资源等


def create_app() -> FastAPI:
    """
    创建FastAPI应用程序实例
    """
    # 创建FastAPI应用
    app = FastAPI(
        title="Quill Knowledge Engine",
        description="基于FastAPI的智能文档处理和分析系统",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        # 禁用文档缓存
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "defaultModelExpandDepth": 1,
            "displayRequestDuration": True,
            "docExpansion": "none",
            "showExtensions": True,
            "showCommonExtensions": True,
        }
    )

    # 注册中间件
    register_middleware(app)

    # 注册异常处理器
    register_exception_handlers(app)

    # 注册路由
    register_routes(app)

    return app


def register_routes(app: FastAPI):
    """
    注册应用程序路由
    """
    from app.config import settings

    # 挂载静态文件 - 使用统一存储路径
    app.mount("/static", StaticFiles(directory=settings.storage.STATIC_DIR), name="static")

    # 挂载临时上传文件目录
    import os
    # 统一使用 storage/static/uploads 目录，让 multimodal_upload 和 resource-parse 共享文件
    temp_uploads_dir = os.path.join(settings.storage.STATIC_DIR, "uploads")
    if not os.path.exists(temp_uploads_dir):
        os.makedirs(temp_uploads_dir, exist_ok=True)
    app.mount("/temp/uploads", StaticFiles(directory=temp_uploads_dir), name="temp_uploads")

    def _resolve_media_file(file_path: str):
        import glob
        from pathlib import Path

        roots: list[Path] = []
        for candidate_root in (
            Path(settings.storage.STATIC_DIR) / "uploads",
            Path(settings.storage.UPLOADS_DIR),
            Path(settings.storage.TEMP_DIR) / "resource_downloads",
            Path(settings.storage.TEMP_DIR),
        ):
            try:
                resolved_root = candidate_root.resolve()
                if resolved_root not in roots:
                    roots.append(resolved_root)
            except Exception:
                continue

        for root in roots:
            try:
                candidate = (root / file_path).resolve()
                # 防止路径穿越：candidate 必须仍在 root 下
                if not candidate.is_relative_to(root):
                    continue
                if candidate.exists() and candidate.is_file():
                    return candidate
            except Exception:
                continue

        # 兼容旧平台只传文件名的 /api/file/{filename} 请求。
        filename = Path(file_path).name
        if filename:
            for root in roots:
                try:
                    candidate = (root / filename).resolve()
                    if candidate.exists() and candidate.is_file():
                        return candidate
                except Exception:
                    continue

        # 如果常规目录找不到，尝试在视频处理目录中搜索优化帧
        base_dir = (Path(settings.storage.STATIC_DIR).resolve() / "uploads" / "processed")
        if base_dir.exists() and filename:
            pattern = str(base_dir / "*" / "*" / "optimized_frames" / filename)
            files = glob.glob(pattern)
            if files and Path(files[0]).exists():
                return Path(files[0])

        return None

    # 创建统一的媒体文件访问路由
    # - 支持子路径：/uploads/temp/xxx.txt
    # - 支持 HEAD：旧前端/探测会用 HEAD 检查文件是否存在
    @app.api_route("/uploads/{file_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_media_file(file_path: str):
        """
        统一的媒体文件访问路由
        支持访问所有类型的文件：普通上传文件、视频优化帧等
        按优先级搜索多个目录位置
        """
        import mimetypes
        from fastapi import HTTPException
        from fastapi.responses import FileResponse

        candidate = _resolve_media_file(file_path)
        if candidate:
            media_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
            return FileResponse(str(candidate), media_type=media_type)

        raise HTTPException(status_code=404, detail=f"文件未找到: {file_path}")

    @app.api_route("/api/file/{file_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_legacy_api_file(file_path: str):
        """兼容旧平台文件访问路径 /api/file/{filename}。"""
        return await serve_media_file(file_path)

    # 优化帧路由 - 重定向到统一的uploads路径
    @app.get("/optimized_frames/{filename}", include_in_schema=False)
    async def serve_optimized_frame_redirect(filename: str):
        """
        兼容旧的优化帧访问路径
        重定向到统一的 /uploads/{filename} 路径
        """
        from fastapi.responses import RedirectResponse

        # 使用301永久重定向，告诉客户端更新链接
        return RedirectResponse(url=f"/uploads/{filename}", status_code=301)

    # 包含API路由
    app.include_router(api_router, prefix="/api/v1")
    from app.api.quill_ingest import router as quill_router
    app.include_router(quill_router, prefix="/api/v1/rag/quill")

    # 知识库旧接口兼容层：/knowledge/resource/* （前端 jetlinks-knowledge-ui /
    # jetlinks-ai-agent-ui 等老模块直连，不带 /api/v1 前缀；内部转换并转发到
    # /api/v1/rag/*）。本期覆盖 _search 与 defaultAi/cmd/queryKnowledgeGraph。
    from app.api.compat.knowledge_compat import router as knowledge_compat_router

    app.include_router(knowledge_compat_router)
    app.include_router(knowledge_compat_router, prefix="/api")

    # 非知识库相关页面已移除

    # 根路径 - 返回首页
    @app.get("/", include_in_schema=False)
    async def root():
        from fastapi.responses import FileResponse
        import os
        return FileResponse(os.path.join(settings.storage.STATIC_DIR, "index.html"))

    # 知识库测试页面
    @app.get("/knowledge-base-test", include_in_schema=False)
    async def knowledge_base_test():
        from fastapi.responses import FileResponse
        import os
        # 历史文件名可能变化，这里做兼容兜底，确保调试页面可用
        candidates = [
            "knowledge-base-test.html",
            "rag-comprehensive-test.html",
            "search-test.html",
            "knowledge-base-enhanced.html",
            "knowledge-base.html",
            "index.html",
        ]
        for name in candidates:
            fp = os.path.join(settings.storage.STATIC_DIR, name)
            if os.path.exists(fp):
                return FileResponse(fp)
        raise HTTPException(status_code=404, detail="知识库测试页面不存在")

    # 知识图谱可视化页面（便于直接访问，不需要 /static 前缀）
    @app.get("/knowledge-graph-visualization", include_in_schema=False)
    @app.get("/knowledge-graph-visualization.html", include_in_schema=False)
    @app.get("/knowledge-graph", include_in_schema=False)
    async def knowledge_graph_visualization():
        from fastapi.responses import FileResponse
        import os

        fp = os.path.join(settings.storage.STATIC_DIR, "knowledge-graph-visualization.html")
        if os.path.exists(fp):
            return FileResponse(fp)
        raise HTTPException(status_code=404, detail="知识图谱可视化页面不存在")

    # 健康检查
    @app.get("/health", include_in_schema=False)
    async def health_check():
        report, status_code = build_health_report()
        return JSONResponse(status_code=status_code, content=report)

    # 这里可以添加更多路由
    # 例如：用户管理、认证、智能体、RAG等


def register_exception_handlers(app: FastAPI):
    """
    注册异常处理器
    """

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": exc.detail,
                "status_code": exc.status_code
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"未处理的异常: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": "服务器内部错误",
                "status_code": 500
            }
        )


def register_middleware(app: FastAPI):
    """
    注册中间件
    """

    # 添加 CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 允许所有来源，生产环境应该限制具体域名
        allow_credentials=True,
        allow_methods=["*"],  # 允许所有 HTTP 方法
        allow_headers=["*"],  # 允许所有请求头
    )

    # 添加 API 日志记录中间件
    from app.shared.middleware import APILoggingMiddleware
    app.add_middleware(APILoggingMiddleware)

    # 行为追踪中间件已移除

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """记录请求日志"""
        logger.info(f"请求: {request.method} {request.url}")
        response = await call_next(request)
        logger.info(f"响应: {response.status_code}")
        return response

    @app.middleware("http")
    async def disable_cache(request: Request, call_next):
        """禁用缓存中间件"""
        response = await call_next(request)

        # 为API文档页面禁用缓存
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response

    @app.middleware("http")
    async def strip_trailing_slash(request: Request, call_next):
        """透明去掉 API/兼容层路径的尾斜杠，避免前端多带 `/` 时触发 307 重定向。

        只处理 /api/ 和 /knowledge/ 前缀（不动 /static、/uploads 等 mount）；
        根路径 / 保留。配合各路由统一无尾斜杠定义使用（前端带不带斜杠都能命中）。
        """
        path = request.scope.get("path", "")
        if (
            len(path) > 1
            and path.endswith("/")
            and (path.startswith("/api/") or path.startswith("/knowledge/"))
        ):
            request.scope["path"] = path.rstrip("/")
        return await call_next(request)


# 创建应用程序实例
app = create_app()

if __name__ == "__main__":
    import uvicorn

    port = settings.PORT

    logger.info(f"正在启动服务器，端口: {port}")

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=port,
        reload=False if settings.is_production else True,
        log_level="info"
    )
