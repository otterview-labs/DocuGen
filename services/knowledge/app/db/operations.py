#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库操作工具类
"""

from typing import Any, Dict, List, Optional, Type, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from app.db.base_class import Base

class DatabaseOperations:
    """数据库操作工具类"""

    @staticmethod
    def get_by_id(db: Session, model: Type[Base], id: Any) -> Optional[Base]:
        """根据ID获取对象"""
        return db.query(model).filter(model.id == id).first()

    @staticmethod
    def get_multi(
        db: Session,
        model: Type[Base],
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Base]:
        """获取多个对象"""
        query = db.query(model)

        # 应用过滤条件
        if filters:
            for field, value in filters.items():
                if hasattr(model, field):
                    if isinstance(value, (list, tuple)):
                        query = query.filter(getattr(model, field).in_(value))
                    else:
                        query = query.filter(getattr(model, field) == value)

        return query.offset(skip).limit(limit).all()

    @staticmethod
    def create(db: Session, model: Type[Base], obj_in: Union[BaseModel, Dict[str, Any]]) -> Base:
        """创建对象"""
        if isinstance(obj_in, BaseModel):
            obj_in_data = jsonable_encoder(obj_in)
        else:
            obj_in_data = obj_in

        db_obj = model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def update(
        db: Session,
        model: Type[Base],
        db_obj: Base,
        obj_in: Union[BaseModel, Dict[str, Any]]
    ) -> Base:
        """更新对象"""
        obj_data = jsonable_encoder(db_obj)

        if isinstance(obj_in, BaseModel):
            update_data = obj_in.dict(exclude_unset=True)
        else:
            update_data = obj_in

        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def remove(db: Session, model: Type[Base], id: int) -> Base:
        """删除对象"""
        obj = db.query(model).get(id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj

    @staticmethod
    def count(db: Session, model: Type[Base], filters: Optional[Dict[str, Any]] = None) -> int:
        """统计对象数量"""
        query = db.query(model)

        if filters:
            for field, value in filters.items():
                if hasattr(model, field):
                    query = query.filter(getattr(model, field) == value)

        return query.count()

    @staticmethod
    def get_by_field(db: Session, model: Type[Base], field: str, value: Any) -> Optional[Base]:
        """根据字段获取对象"""
        if hasattr(model, field):
            return db.query(model).filter(getattr(model, field) == value).first()
        return None

    @staticmethod
    def get_by_fields(db: Session, model: Type[Base], filters: Dict[str, Any]) -> List[Base]:
        """根据多个字段获取对象"""
        query = db.query(model)

        for field, value in filters.items():
            if hasattr(model, field):
                query = query.filter(getattr(model, field) == value)

        return query.all()

    @staticmethod
    def search(
        db: Session,
        model: Type[Base],
        search_term: str,
        search_fields: List[str],
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Base]:
        """搜索对象"""
        query = db.query(model)

        # 构建搜索条件
        search_conditions = []
        for field in search_fields:
            if hasattr(model, field):
                search_conditions.append(
                    getattr(model, field).contains(search_term)
                )

        if search_conditions:
            query = query.filter(or_(*search_conditions))

        return query.offset(skip).limit(limit).all()
