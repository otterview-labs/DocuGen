#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
数据库会话管理
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# 创建数据库引擎
engine = create_engine(
    settings.database.database_url,
    pool_pre_ping=True,
    pool_size=10,                    # 连接池大小
    max_overflow=20,                 # 最大溢出连接数
    pool_timeout=30,                 # 获取连接超时时间（秒）
    pool_recycle=3600,               # 连接回收时间（秒），1小时
    pool_reset_on_return='commit',   # 连接返回时重置方式
    echo=settings.database.SQLALCHEMY_ECHO
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_initial_data():
    """创建初始数据"""
    from app.db.models.user import User
    from app.db.operations import DatabaseOperations
    from passlib.context import CryptContext

    # 密码加密上下文
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

    db = SessionLocal()
    try:
        # 检查是否已存在admin用户
        admin_user = DatabaseOperations.get_by_field(db, User, "username", "admin")
        if not admin_user:
            # 创建admin用户
            try:
                hashed_password = pwd_context.hash("123456")
            except Exception as e:
                import hashlib
                hashed_password = hashlib.sha256("123456".encode()).hexdigest()

            admin_data = {
                "username": "admin",
                "email": "admin@jetlinks.ai",
                "hashed_password": hashed_password,
                "full_name": "系统管理员",
                "is_active": True,
                "is_superuser": True
            }

            DatabaseOperations.create(db, User, admin_data)
            logger.info("✅ 管理员用户创建成功")
        else:
            logger.info("ℹ️ 管理员用户已存在")

    except Exception as e:
        logger.error(f"创建初始数据失败: {e}")
    finally:
        db.close()

def test_db_connection():
    """测试数据库连接"""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        logger.debug("数据库连接测试成功")
        return True
    except Exception as e:
        logger.error(f"数据库连接测试失败: {e}")
        return False
