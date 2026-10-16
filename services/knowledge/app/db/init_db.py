#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库初始化脚本
"""

import asyncio
from sqlalchemy import text
import os
import sys
from app.shared.utils.logger_util import get_logger

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = get_logger(__name__)

from app.db.session import engine, SessionLocal
from app.db.models.user import User
from app.db.operations import DatabaseOperations
from passlib.context import CryptContext

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def init_database():
    """初始化数据库"""
    logger.info("🚀 开始初始化数据库...")

    try:
        # 创建所有表
        from app.db.base_class import Base
        Base.metadata.create_all(bind=engine)
        logger.info("✅ 数据库表创建成功")

        # 创建初始数据
        create_initial_data()

        logger.info("🎉 数据库初始化完成！")

    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise

def create_initial_data():
    """创建初始数据"""
    logger.info("📝 创建初始数据...")

    # 创建管理员用户
    create_admin_user()

    logger.info("✅ 初始数据创建完成")

def create_admin_user():
    """创建管理员用户"""
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
                "email": "admin@otterflow.ai",
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
        logger.error(f"创建管理员用户失败: {e}")
    finally:
        db.close()

def test_admin_login():
    """测试管理员登录"""
    db = SessionLocal()
    try:
        # 查找admin用户
        admin_user = DatabaseOperations.get_by_field(db, User, "username", "admin")
        if admin_user:
            logger.info(f"✅ 管理员用户存在: {admin_user.username}")
            return True
        else:
            logger.info("❌ 管理员用户不存在")
            return False
    except Exception as e:
        logger.error(f"测试管理员登录失败: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    # 初始化数据库
    init_database()

    # 测试管理员登录
    test_admin_login()
