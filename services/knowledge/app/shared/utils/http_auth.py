#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP 认证辅助。

统一支持：
- none: 不附带认证头
- bearer: Authorization: Bearer <token>
- basic: HTTP Basic Auth
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, MutableMapping, Optional

import httpx
from requests.auth import HTTPBasicAuth


VALID_AUTH_MODES = {"none", "bearer", "basic"}


def normalize_auth_mode(value: Optional[str], default: str = "bearer") -> str:
    normalized_default = (default or "bearer").strip().lower()
    if normalized_default not in VALID_AUTH_MODES:
        normalized_default = "bearer"

    if value is None:
        return normalized_default

    normalized = str(value).strip().lower()
    if not normalized:
        return normalized_default
    if normalized in {"disable", "disabled", "off", "false", "0"}:
        return "none"
    if normalized in VALID_AUTH_MODES:
        return normalized
    return normalized_default


def _clean_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(frozen=True)
class HTTPAuthConfig:
    mode: str
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None

    @classmethod
    def build(
        cls,
        *,
        mode: Optional[str],
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        default_mode: str = "bearer",
    ) -> "HTTPAuthConfig":
        return cls(
            mode=normalize_auth_mode(mode, default=default_mode),
            api_key=_clean_str(api_key),
            username=_clean_str(username),
            password=_clean_str(password),
        )

    @property
    def sdk_api_key(self) -> str:
        """OpenAI SDK 使用的 api_key。

        - bearer 模式走真实 token
        - none/basic 模式传空字符串，避免 SDK 从环境变量偷读并自动注入 Bearer 头
        """
        if self.mode == "bearer":
            return self.api_key or ""
        return ""


def apply_auth_headers(
    headers: Optional[Mapping[str, str]],
    auth_config: HTTPAuthConfig,
) -> dict[str, str]:
    merged: dict[str, str] = dict(headers or {})
    if auth_config.mode == "bearer" and auth_config.api_key:
        merged["Authorization"] = f"Bearer {auth_config.api_key}"
    return merged


def build_requests_auth(auth_config: HTTPAuthConfig) -> HTTPBasicAuth | None:
    if auth_config.mode != "basic":
        return None
    return HTTPBasicAuth(auth_config.username or "", auth_config.password or "")


def build_httpx_auth(auth_config: HTTPAuthConfig) -> httpx.BasicAuth | None:
    if auth_config.mode != "basic":
        return None
    return httpx.BasicAuth(auth_config.username or "", auth_config.password or "")


def update_mutable_headers(
    headers: MutableMapping[str, str],
    auth_config: HTTPAuthConfig,
) -> MutableMapping[str, str]:
    headers.update(apply_auth_headers(headers, auth_config))
    return headers
