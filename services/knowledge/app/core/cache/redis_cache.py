#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Redis 缓存服务
用于知识图谱系统的多级缓存
"""

import redis
import json
import hashlib
import pickle
import logging
from typing import Any, Optional, Dict, List
from functools import wraps
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class RedisCache:
    """Redis 缓存管理器"""

    def __init__(self):
        """初始化 Redis 连接"""
        self.host = os.getenv('REDIS_HOST', 'localhost')
        self.port = int(os.getenv('REDIS_PORT', 6379))
        self.password = os.getenv('REDIS_PASSWORD')
        self.db = int(os.getenv('REDIS_DB', 0))

        self.client = None
        self._connect()

    def _connect(self):
        """建立 Redis 连接"""
        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                db=self.db,
                decode_responses=False,  # 使用二进制存储以支持pickle
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # 测试连接
            self.client.ping()
            logger.info(f"Redis 连接成功: {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Redis 连接失败: {e}")
            self.client = None

    def is_connected(self) -> bool:
        """检查连接状态"""
        if not self.client:
            return False
        try:
            self.client.ping()
            return True
        except:
            return False

    # ============ 基础操作 ============

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if not self.client:
            return None

        try:
            value = self.client.get(key)
            if value:
                # 尝试反序列化
                try:
                    return pickle.loads(value)
                except:
                    # 如果pickle失败，尝试JSON
                    try:
                        return json.loads(value)
                    except:
                        # 返回原始字符串
                        return value.decode('utf-8') if isinstance(value, bytes) else value
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        if not self.client:
            return False

        try:
            # 序列化值
            try:
                serialized = pickle.dumps(value)
            except:
                # pickle失败，尝试JSON
                serialized = json.dumps(value).encode('utf-8')

            if ttl:
                return self.client.setex(key, ttl, serialized)
            else:
                return self.client.set(key, serialized)
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False

    def delete(self, *keys) -> int:
        """删除缓存"""
        if not self.client:
            return 0

        try:
            return self.client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return 0

    def delete_pattern(self, pattern: str) -> int:
        """按模式删除缓存键"""
        if not self.client:
            return 0

        try:
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Redis delete_pattern error: {e}")
            return 0

    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if not self.client:
            return False

        try:
            return self.client.exists(key) > 0
        except:
            return False

    # ============ 知识图谱专用缓存 ============

    def cache_query_result(self, query: str, results: Any, ttl: int = 3600) -> bool:
        """缓存查询结果"""
        key = f"kg:query:{self._hash_key(query)}"
        return self.set(key, results, ttl)

    def get_query_result(self, query: str) -> Optional[Any]:
        """获取查询结果缓存"""
        key = f"kg:query:{self._hash_key(query)}"
        return self.get(key)

    def cache_vector(self, doc_id: str, chunk_id: str, vector: List[float], ttl: int = 86400) -> bool:
        """缓存向量"""
        key = f"kg:vec:{doc_id}:{chunk_id}"
        return self.set(key, vector, ttl)

    def get_vector(self, doc_id: str, chunk_id: str) -> Optional[List[float]]:
        """获取向量缓存"""
        key = f"kg:vec:{doc_id}:{chunk_id}"
        return self.get(key)

    def cache_graph_path(self, start_node: str, end_node: str, path: Any, ttl: int = 7200) -> bool:
        """缓存图路径"""
        key = f"kg:path:{start_node}:{end_node}"
        return self.set(key, path, ttl)

    def get_graph_path(self, start_node: str, end_node: str) -> Optional[Any]:
        """获取图路径缓存"""
        key = f"kg:path:{start_node}:{end_node}"
        return self.get(key)

    def add_hot_query(self, query: str, score: float = 1.0) -> bool:
        """添加热门查询"""
        if not self.client:
            return False

        try:
            self.client.zincrby("kg:hot:queries", score, query)
            return True
        except Exception as e:
            logger.error(f"Redis add hot query error: {e}")
            return False

    def get_hot_queries(self, top_n: int = 10) -> List[tuple]:
        """获取热门查询"""
        if not self.client:
            return []

        try:
            results = self.client.zrevrange("kg:hot:queries", 0, top_n - 1, withscores=True)
            return [(q.decode('utf-8') if isinstance(q, bytes) else q, score)
                    for q, score in results]
        except Exception as e:
            logger.error(f"Redis get hot queries error: {e}")
            return []

    def cache_session_context(self, session_id: str, context: Dict, ttl: int = 1800) -> bool:
        """缓存会话上下文"""
        key = f"kg:session:{session_id}"
        return self.set(key, context, ttl)

    def get_session_context(self, session_id: str) -> Optional[Dict]:
        """获取会话上下文"""
        key = f"kg:session:{session_id}"
        return self.get(key)

    # ============ 工具方法 ============

    def _hash_key(self, value: str) -> str:
        """生成哈希键"""
        return hashlib.md5(value.encode()).hexdigest()

    def clear_pattern(self, pattern: str) -> int:
        """清除匹配模式的所有键"""
        if not self.client:
            return 0

        try:
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Redis clear pattern error: {e}")
            return 0

    def get_info(self) -> Dict:
        """获取 Redis 信息"""
        if not self.client:
            return {}

        try:
            info = self.client.info()
            return {
                'version': info.get('redis_version'),
                'used_memory': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'db_size': self.client.dbsize()
            }
        except:
            return {}


# ============ 装饰器 ============

def cached(ttl: int = 3600, prefix: str = "cache"):
    """缓存装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{prefix}:{func.__name__}:{hashlib.md5(str(args).encode()).hexdigest()}"

            # 获取缓存实例
            cache = RedisCache()
            if not cache.is_connected():
                # Redis 不可用，直接执行函数
                return func(*args, **kwargs)

            # 尝试从缓存获取
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_result

            # 执行函数
            result = func(*args, **kwargs)

            # 存入缓存
            cache.set(cache_key, result, ttl)
            logger.debug(f"Cache set: {cache_key}")

            return result
        return wrapper
    return decorator


# ============ 单例模式 ============

_redis_cache_instance = None

def get_redis_cache() -> RedisCache:
    """获取 Redis 缓存单例"""
    global _redis_cache_instance
    if _redis_cache_instance is None:
        _redis_cache_instance = RedisCache()
    return _redis_cache_instance


# 全局实例
cache = get_redis_cache()

# ============ 使用示例 ============

if __name__ == "__main__":
    # 测试缓存
    test_cache = get_redis_cache()

    if test_cache.is_connected():
        logger.info("✅ Redis 已连接")

        # 测试基本操作
        test_cache.set("test_key", {"data": "test"}, ttl=60)
        logger.info(f"获取测试数据: {test_cache.get('test_key')}")

        # 测试知识图谱缓存
        test_cache.cache_query_result("深度学习", {"results": ["doc1", "doc2"]})
        logger.info(f"查询缓存: {test_cache.get_query_result('深度学习')}")

        # 测试热门查询
        test_cache.add_hot_query("深度学习", 10)
        test_cache.add_hot_query("Transformer", 8)
        logger.info(f"热门查询: {test_cache.get_hot_queries(5)}")

        # 显示信息
        logger.info(f"Redis 信息: {test_cache.get_info()}")
    else:
        logger.info("❌ Redis 未连接")
