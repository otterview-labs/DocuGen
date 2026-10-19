#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
数据库基础类模块
提供所有模型的基类
"""

from sqlalchemy.orm import declarative_base

# 创建基础模型类
Base = declarative_base()
