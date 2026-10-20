"""Bounded anonymous browser sessions, each running its own workspace.

Run exactly one worker. This is an expiring public sandbox, not an account or
tenant system. Engine, database and workspace ports must stay private.
"""

import asyncio
import hmac
import ipaddress
import json
import logging
import secrets
import shutil
import time
from collections import deque
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from hashlib import sha256
from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from quill.config import Settings
from quill.demo_knowledge import DemoKnowledgeClient
from quill.main import create_app

logger = logging.getLogger(__name__)


@dataclass
class Visitor:
    app: object
    lifespan: object
    created: float
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    writes: int = 0


class DemoGateway:
    max_sessions = 32
    ttl = 7200
    body_limit = 6 * 1024 * 1024
    storage_limit = 40 * 1024 * 1024

    def __init__(self, settings=None):
        self.settings = settings or Settings()
        self.cookie_name = "__Host-docugen-demo" if self.settings.demo_cookie_secure else "docugen-demo"
        self.root = self.settings.data_dir.resolve() / "demo"
        self.root.mkdir(parents=True, exist_ok=True)
        secret_file = self.root / ".session-secret"
        if not secret_file.exists():
            with secret_file.open("x") as f:
                secret_file.chmod(0o600)
                f.write(secrets.token_hex(32))
        self.secret = secret_file.read_bytes()
        self.visitors = {}
        self.registry_lock = asyncio.Lock()
        self.capacity = asyncio.Semaphore(4)
        self.rates = {}
        self.static = {}
        for name in ("assets", "template-previews"):
            directory = self.settings.frontend_dir / name
            if directory.is_dir():
                self.static[name] = StaticFiles(directory=directory)
        self.control = Starlette(lifespan=self.lifespan)

    @asynccontextmanager
    async def lifespan(self, app):
        reaper = asyncio.create_task(self.reap())
        try:
            yield
        finally:
            reaper.cancel()
            with suppress(asyncio.CancelledError):
                await reaper
            for visitor in self.visitors.values():
                await visitor.lifespan.__aexit__(None, None, None)
            self.visitors.clear()

    def sign(self, sid):
        return sid + "." + hmac.new(self.secret, sid.encode(), sha256).hexdigest()

    def session_id(self, token):
        sid, _, signature = token.partition(".")
        if len(sid) != 32 or any(c not in "0123456789abcdef" for c in sid):
            return None
        return sid if hmac.compare_digest(self.sign(sid).partition(".")[2], signature) else None

    def client_ip(self, scope, headers):
        value = scope.get("client", ("unknown", 0))[0]
        # Deployment's Caddy overwrites this header; never trust it from direct clients.
        if value in {"127.0.0.1", "::1"}:
            forwarded = headers.get("x-real-ip", value)
            try:
                return str(ipaddress.ip_address(forwarded))
            except ValueError:
                pass
        return value

    def rate(self, ip, fresh=False):
        now = time.time()
        for key in list(self.rates):
            if now - self.rates[key][0] > 3600:
                self.rates.pop(key)
        if ip not in self.rates:
            if len(self.rates) >= 4096:
                return False
            self.rates[ip] = (now, deque(), deque())
        _, requests, starts = self.rates[ip]
        while requests and requests[0] < now - 60:
            requests.popleft()
        while starts and starts[0] < now - 3600:
            starts.popleft()
        if len(requests) >= 180 or (fresh and len(starts) >= 8):
            return False
        requests.append(now)
        if fresh:
            starts.append(now)
        return True

    async def open_visitor(self, sid):
        if sid in self.visitors:
            return self.visitors[sid]
        directory = self.root / sid
        meta = directory / "session.json"
        if not meta.exists():
            directory.mkdir()
            meta.write_text(json.dumps({"created": time.time()}))
        created = json.loads(meta.read_text())["created"]
        writes = json.loads(meta.read_text()).get("writes", 0)
        config = self.settings.model_copy(update={
            "data_dir": directory, "api_key": "", "demo_mode": True,
            "max_upload_mb": 5, "max_expanded_mb": 20,
            # Anonymous model execution needs a separate metered allowance.
            "llm_model": "", "llm_api_key": "",
        })
        app = create_app(config, knowledge_factory=DemoKnowledgeClient)
        life = app.router.lifespan_context(app)
        await life.__aenter__()
        visitor = Visitor(app, life, created, writes=writes)
        self.visitors[sid] = visitor
        return visitor

    async def reap_once(self):
        async with self.registry_lock:
            for directory in self.root.iterdir():
                if not directory.is_dir() or len(directory.name) != 32:
                    continue
                meta = directory / "session.json"
                if not meta.exists() or time.time() - json.loads(meta.read_text())["created"] < self.ttl:
                    continue
                visitor = self.visitors.get(directory.name)
                if visitor and visitor.lock.locked():
                    continue
                try:
                    visitor = visitor or await self.open_visitor(directory.name)
                    await visitor.app.state.knowledge.cleanup()
                    await visitor.lifespan.__aexit__(None, None, None)
                    self.visitors.pop(directory.name)
                    shutil.rmtree(directory)
                except Exception:
                    # Keep failed cleanup in the registry and capacity accounting.
                    logger.exception("Demo expiry cleanup failed")

    async def reap(self):
        while True:
            await self.reap_once()
            await asyncio.sleep(60)

    async def reject(self, scope, receive, send, code, message):
        await JSONResponse({"detail": message}, status_code=code)(scope, receive, send)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            return await self.control(scope, receive, send)
        if scope["type"] != "http":
            return
        path = scope["path"]
        if path == "/health":
            return await JSONResponse({"status": "ok", "service": "docugen-demo"})(scope, receive, send)
        first = path.split("/")[1]
        if first in self.static:
            static_scope = {**scope, "path": path[len(first) + 1:], "root_path": ""}
            try:
                return await self.static[first](static_scope, receive, send)
            except HTTPException as exc:
                return await self.reject(scope, receive, send, exc.status_code, "文件不存在。")
        request = Request(scope)
        headers = request.headers
        if scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
            origin = headers.get("origin")
            if headers.get("sec-fetch-site") == "cross-site" or (
                origin and urlsplit(origin).netloc != headers.get("host")
            ):
                return await self.reject(scope, receive, send, 403, "请从演示站页面提交操作。")
        token = request.cookies.get(self.cookie_name, "")
        sid = self.session_id(token)
        fresh = not sid or not (self.root / sid / "session.json").is_file()
        if not self.rate(self.client_ip(scope, headers), fresh):
            return await self.reject(scope, receive, send, 429, "请求过于频繁，请稍后再试。")
        if not fresh:
            created = json.loads((self.root / sid / "session.json").read_text())["created"]
            if time.time() - created >= self.ttl:
                return await self.reject(scope, receive, send, 410, "演示会话已到期，请清除本站 Cookie 后重新进入。")
        # Read with a hard bound, including chunked bodies with no Content-Length.
        body = bytearray()
        try:
            async with asyncio.timeout(20):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > self.body_limit:
                        return await self.reject(scope, receive, send, 413, "演示请求过大，单个上传文件最多 5 MB。")
                    if not message.get("more_body"):
                        break
        except TimeoutError:
            return await self.reject(scope, receive, send, 408, "上传超时，请重试。")
        try:
            await asyncio.wait_for(self.capacity.acquire(), timeout=1)
        except TimeoutError:
            return await self.reject(scope, receive, send, 429, "演示站繁忙，请稍后重试。")
        try:
            async with self.registry_lock:
                if fresh:
                    count = sum(1 for d in self.root.iterdir() if d.is_dir())
                    if count >= self.max_sessions:
                        return await self.reject(scope, receive, send, 429, "当前演示名额已满，请稍后再来。")
                    sid = secrets.token_hex(16)
                visitor = await self.open_visitor(sid)
                # Acquire before dropping the registry lock so cleanup cannot race.
                await visitor.lock.acquire()
            try:
                if scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
                    used = sum(p.stat().st_size for p in (self.root / sid).rglob("*") if p.is_file())
                    if used + len(body) > self.storage_limit or visitor.writes >= 100:
                        return await self.reject(scope, receive, send, 429, "本次演示的存储或操作额度已用完。")
                    visitor.writes += 1
                    (self.root / sid / "session.json").write_text(json.dumps({
                        "created": visitor.created, "writes": visitor.writes,
                    }))
                delivered = False

                async def replay():
                    nonlocal delivered
                    if not delivered:
                        delivered = True
                        return {"type": "http.request", "body": bytes(body), "more_body": False}
                    return await receive()

                async def wrapped_send(message):
                    if message["type"] == "http.response.start":
                        response_headers = list(message.get("headers", []))
                        response_headers += [(b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff")]
                        if fresh:
                            cookie = f"{self.cookie_name}={self.sign(sid)}; Path=/; Max-Age={self.ttl}; HttpOnly; SameSite=Strict"
                            if self.settings.demo_cookie_secure:
                                cookie += "; Secure"
                            response_headers.append((b"set-cookie", cookie.encode()))
                        message = {**message, "headers": response_headers}
                    await send(message)

                await visitor.app(scope, replay, wrapped_send)
            finally:
                visitor.lock.release()
        finally:
            self.capacity.release()


def create_demo():
    return DemoGateway()
