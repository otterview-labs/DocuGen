#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Schema 通用配置辅助。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import ConfigDict


def schema_config(
    *,
    populate_by_name: bool = False,
    example: Optional[Dict[str, Any]] = None,
    examples: Optional[List[Dict[str, Any]]] = None,
    extra: Optional[str] = None,
) -> ConfigDict:
    """统一构造 Pydantic schema 配置。"""
    json_schema_extra: Dict[str, Any] = {}
    if example is not None:
        json_schema_extra["example"] = example
    if examples is not None:
        json_schema_extra["examples"] = examples

    config: Dict[str, Any] = dict(
        populate_by_name=populate_by_name,
        json_schema_extra=json_schema_extra or None,
    )
    if extra is not None:
        config["extra"] = extra
    return ConfigDict(**config)
