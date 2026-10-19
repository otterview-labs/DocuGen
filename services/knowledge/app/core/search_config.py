#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜索服务配置
统一管理所有搜索相关的超时和性能参数
"""

import os
from typing import Dict, Any


class SearchTimeoutConfig:
    """搜索超时配置"""

    # 基础超时时间（秒）
    SEMANTIC_SEARCH_TIMEOUT = float(os.getenv('SEMANTIC_SEARCH_TIMEOUT', '30.0'))
    KEYWORD_SEARCH_TIMEOUT = float(os.getenv('KEYWORD_SEARCH_TIMEOUT', '10.0'))
    KG_SEARCH_TIMEOUT = float(os.getenv('KG_SEARCH_TIMEOUT', '30.0'))
    THREE_LAYER_SEARCH_TIMEOUT = float(os.getenv('THREE_LAYER_SEARCH_TIMEOUT', '30.0'))
    HYBRID_SEARCH_TIMEOUT = float(os.getenv('HYBRID_SEARCH_TIMEOUT', '60.0'))

    # 向量数据库连接超时
    MILVUS_CONNECTION_TIMEOUT = float(os.getenv('MILVUS_CONNECTION_TIMEOUT', '10.0'))
    MILVUS_SEARCH_TIMEOUT = float(os.getenv('MILVUS_SEARCH_TIMEOUT', '20.0'))

    # 嵌入模型API超时
    EMBEDDING_API_TIMEOUT = float(os.getenv('EMBEDDING_API_TIMEOUT', '10.0'))

    # 数据库查询超时
    DB_QUERY_TIMEOUT = float(os.getenv('DB_QUERY_TIMEOUT', '5.0'))

    # Redis缓存超时
    REDIS_CONNECTION_TIMEOUT = float(os.getenv('REDIS_CONNECTION_TIMEOUT', '5.0'))
    REDIS_SOCKET_TIMEOUT = float(os.getenv('REDIS_SOCKET_TIMEOUT', '5.0'))

    # Neo4j图数据库超时
    NEO4J_CONNECTION_TIMEOUT = float(os.getenv('NEO4J_CONNECTION_TIMEOUT', '10.0'))
    NEO4J_QUERY_TIMEOUT = float(os.getenv('NEO4J_QUERY_TIMEOUT', '20.0'))


class SearchPerformanceConfig:
    """搜索性能配置"""

    # 最大并发搜索数
    MAX_CONCURRENT_SEARCHES = int(os.getenv('MAX_CONCURRENT_SEARCHES', '4'))

    # 最大搜索集合数（未指定集合时）
    MAX_SEARCH_COLLECTIONS = int(os.getenv('MAX_SEARCH_COLLECTIONS', '10'))

    # 批量查询大小
    BATCH_QUERY_SIZE = int(os.getenv('BATCH_QUERY_SIZE', '50'))

    # 连接池配置
    MILVUS_CONNECTION_POOL_SIZE = int(os.getenv('MILVUS_CONNECTION_POOL_SIZE', '10'))
    DB_CONNECTION_POOL_SIZE = int(os.getenv('DB_CONNECTION_POOL_SIZE', '20'))

    # 缓存配置
    SEARCH_CACHE_TTL = int(os.getenv('SEARCH_CACHE_TTL', '1800'))  # 30分钟
    CACHE_MAX_SIZE = int(os.getenv('CACHE_MAX_SIZE', '10000'))

    # 重试配置
    MAX_RETRY_ATTEMPTS = int(os.getenv('MAX_RETRY_ATTEMPTS', '3'))
    RETRY_DELAY_SECONDS = float(os.getenv('RETRY_DELAY_SECONDS', '1.0'))


# 导出配置实例
search_timeout_config = SearchTimeoutConfig()
search_performance_config = SearchPerformanceConfig()


def get_search_timeout_settings() -> Dict[str, float]:
    """获取所有搜索超时设置"""
    return {
        'semantic': search_timeout_config.SEMANTIC_SEARCH_TIMEOUT,
        'keyword': search_timeout_config.KEYWORD_SEARCH_TIMEOUT,
        'kg': search_timeout_config.KG_SEARCH_TIMEOUT,
        'three_layer': search_timeout_config.THREE_LAYER_SEARCH_TIMEOUT,
        'hybrid': search_timeout_config.HYBRID_SEARCH_TIMEOUT,
        'milvus_connection': search_timeout_config.MILVUS_CONNECTION_TIMEOUT,
        'milvus_search': search_timeout_config.MILVUS_SEARCH_TIMEOUT,
        'embedding_api': search_timeout_config.EMBEDDING_API_TIMEOUT,
        'db_query': search_timeout_config.DB_QUERY_TIMEOUT,
        'redis_connection': search_timeout_config.REDIS_CONNECTION_TIMEOUT,
        'neo4j_connection': search_timeout_config.NEO4J_CONNECTION_TIMEOUT,
        'neo4j_query': search_timeout_config.NEO4J_QUERY_TIMEOUT,
    }


def get_search_performance_settings() -> Dict[str, Any]:
    """获取所有搜索性能设置"""
    return {
        'max_concurrent_searches': search_performance_config.MAX_CONCURRENT_SEARCHES,
        'max_search_collections': search_performance_config.MAX_SEARCH_COLLECTIONS,
        'batch_query_size': search_performance_config.BATCH_QUERY_SIZE,
        'milvus_pool_size': search_performance_config.MILVUS_CONNECTION_POOL_SIZE,
        'db_pool_size': search_performance_config.DB_CONNECTION_POOL_SIZE,
        'cache_ttl': search_performance_config.SEARCH_CACHE_TTL,
        'cache_max_size': search_performance_config.CACHE_MAX_SIZE,
        'max_retry': search_performance_config.MAX_RETRY_ATTEMPTS,
        'retry_delay': search_performance_config.RETRY_DELAY_SECONDS,
    }
