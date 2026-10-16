# -*- coding: utf-8 -*-
"""
统一日志配置
所有模块使用统一的日志格式和级别
"""

import os
import logging
from pathlib import Path
from app.shared.utils.logger_util import get_logger

# 日志级别配置
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# 日志目录配置
LOG_DIR = Path('logs')
LOG_DIR.mkdir(exist_ok=True)

# 日志格式配置
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# 全局日志配置
def configure_logging():
    """配置全局日志"""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT
    )

    # 设置第三方库日志级别
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('pymilvus').setLevel(logging.WARNING)
    logging.getLogger('neo4j').setLevel(logging.WARNING)
    logging.getLogger('redis').setLevel(logging.WARNING)

# 初始化配置
configure_logging()
