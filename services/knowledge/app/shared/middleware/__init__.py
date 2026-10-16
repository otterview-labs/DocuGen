#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中间件模块
"""

from app.shared.middleware.api_logging_middleware import APILoggingMiddleware

__all__ = ["APILoggingMiddleware"]
