#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础数据库模型
提供所有模型的基类
"""

from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.sql import func
from datetime import datetime

from app.db.base_class import Base

class BaseModel(Base):
    """
    基础模型类
    提供所有模型共用的字段
    """
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def to_dict(self):
        """转换为字典"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"
