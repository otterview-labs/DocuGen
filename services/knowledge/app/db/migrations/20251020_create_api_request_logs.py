#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration: Create api_request_logs table

创建API请求日志表，用于记录所有API接口的请求和响应信息
"""

from typing import Optional
from sqlalchemy import text, inspect


def migrate(engine) -> Optional[str]:
    """
    创建api_request_logs表的迁移脚本

    Returns:
        执行状态字符串，如果跳过则返回None
    """
    try:
        insp = inspect(engine)

        # 检查表是否已存在
        if 'api_request_logs' in insp.get_table_names():
            return 'api_request_logs table already exists; skipped'

        dialect = engine.dialect.name.lower()

        with engine.begin() as conn:
            if dialect == 'mysql':
                # MySQL版本的建表语句
                conn.execute(text("""
                    CREATE TABLE api_request_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL,

                        method VARCHAR(10) NOT NULL COMMENT '请求方法: GET/POST/PUT/DELETE',
                        endpoint VARCHAR(500) NOT NULL COMMENT '请求端点路径',
                        client_ip VARCHAR(50) COMMENT '客户端IP地址',
                        user_agent VARCHAR(500) COMMENT '用户代理',

                        query_params TEXT COMMENT 'URL查询参数(JSON格式)',
                        request_body TEXT COMMENT '请求体内容(JSON格式)',

                        status_code INT COMMENT 'HTTP响应状态码',
                        response_body TEXT COMMENT '响应体内容(JSON格式)',
                        response_time FLOAT COMMENT '响应时间(毫秒)',

                        error_message TEXT COMMENT '错误信息(如果有)',

                        user_id VARCHAR(100) COMMENT '用户ID',
                        collection_id VARCHAR(100) COMMENT '集合ID(RAG相关)',
                        search_query TEXT COMMENT '搜索查询内容(RAG相关)',
                        search_mode VARCHAR(50) COMMENT '搜索模式(RAG相关)',
                        result_count INT COMMENT '返回结果数量',

                        INDEX idx_endpoint_created (endpoint(255), created_at),
                        INDEX idx_user_created (user_id, created_at),
                        INDEX idx_collection_created (collection_id, created_at),
                        INDEX idx_status_created (status_code, created_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='API请求日志表'
                """))
                return 'mysql: api_request_logs table created'

            elif dialect in ('postgresql', 'postgres'):
                # PostgreSQL版本的建表语句
                conn.execute(text("""
                    CREATE TABLE api_request_logs (
                        id SERIAL PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

                        method VARCHAR(10) NOT NULL,
                        endpoint VARCHAR(500) NOT NULL,
                        client_ip VARCHAR(50),
                        user_agent VARCHAR(500),

                        query_params TEXT,
                        request_body TEXT,

                        status_code INTEGER,
                        response_body TEXT,
                        response_time FLOAT,

                        error_message TEXT,

                        user_id VARCHAR(100),
                        collection_id VARCHAR(100),
                        search_query TEXT,
                        search_mode VARCHAR(50),
                        result_count INTEGER
                    )
                """))

                # 创建索引
                conn.execute(text("CREATE INDEX idx_endpoint_created ON api_request_logs (endpoint, created_at)"))
                conn.execute(text("CREATE INDEX idx_user_created ON api_request_logs (user_id, created_at)"))
                conn.execute(text("CREATE INDEX idx_collection_created ON api_request_logs (collection_id, created_at)"))
                conn.execute(text("CREATE INDEX idx_status_created ON api_request_logs (status_code, created_at)"))

                return 'postgres: api_request_logs table created'

            elif dialect == 'sqlite':
                # SQLite版本的建表语句
                conn.execute(text("""
                    CREATE TABLE api_request_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,

                        method VARCHAR(10) NOT NULL,
                        endpoint VARCHAR(500) NOT NULL,
                        client_ip VARCHAR(50),
                        user_agent VARCHAR(500),

                        query_params TEXT,
                        request_body TEXT,

                        status_code INTEGER,
                        response_body TEXT,
                        response_time REAL,

                        error_message TEXT,

                        user_id VARCHAR(100),
                        collection_id VARCHAR(100),
                        search_query TEXT,
                        search_mode VARCHAR(50),
                        result_count INTEGER
                    )
                """))

                # 创建索引
                conn.execute(text("CREATE INDEX idx_endpoint_created ON api_request_logs (endpoint, created_at)"))
                conn.execute(text("CREATE INDEX idx_user_created ON api_request_logs (user_id, created_at)"))
                conn.execute(text("CREATE INDEX idx_collection_created ON api_request_logs (collection_id, created_at)"))
                conn.execute(text("CREATE INDEX idx_status_created ON api_request_logs (status_code, created_at)"))

                return 'sqlite: api_request_logs table created'

            else:
                return f'{dialect}: unsupported dialect; skipped'

    except Exception as e:
        return f'error: {e}'
