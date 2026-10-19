#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缓存模块
"""

from app.core.cache.redis_cache import (
    RedisCache,
    get_redis_cache,
    cache
)

__all__ = [
    'RedisCache',
    'get_redis_cache',
    'cache'
]
