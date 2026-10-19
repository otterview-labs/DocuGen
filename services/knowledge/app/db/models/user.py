#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户数据库模型
"""

from sqlalchemy import Column, String, Boolean, Text
from sqlalchemy.orm import relationship
from app.config import settings

from app.db.models.base import BaseModel


class User(BaseModel):
    """用户模型"""
    __tablename__ = "users"

    # 根据数据库类型设置schema
    if settings.database.DB_DATABASE_TYPE.lower() == "postgresql":
        __table_args__ = {"schema": "public"}
    else:
        # MySQL 不使用 schema
        __table_args__ = {}

    # 用户基本信息
    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    email = Column(String(100), unique=True, index=True, nullable=False, comment="邮箱")
    hashed_password = Column(String(255), nullable=False, comment="加密密码")
    full_name = Column(String(100), comment="全名")

    # 用户状态
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_superuser = Column(Boolean, default=False, comment="是否超级用户")

    # 额外信息
    avatar = Column(String(255), nullable=True)
    bio = Column(Text, nullable=True)

    # 关系 - 注释掉已删除的模型关系
    # agents = relationship("Agent", back_populates="user")  # Agent模型已删除
    # created_tools = relationship("Tool", back_populates="creator")  # Tool模型已删除
    # created_prompts = relationship("Prompt", back_populates="creator")  # Prompt模型已删除
    # created_templates = relationship("PromptTemplate", back_populates="creator")  # PromptTemplate模型已删除
    # tool_logs = relationship("ToolLog", back_populates="user")  # ToolLog模型已删除
    # prompt_ratings = relationship("PromptRating", back_populates="user")  # PromptRating模型已删除

    # 新增关系 - 也已删除
    # created_applications = relationship("Application", back_populates="creator")  # Application模型已删除
    # owned_teams = relationship("Team", back_populates="owner")  # Team模型已删除
    # team_memberships = relationship("TeamMember", back_populates="user")  # TeamMember模型已删除
    # application_reviews = relationship("ApplicationReview", back_populates="user")  # ApplicationReview模型已删除
    # deployments = relationship("ApplicationDeployment", back_populates="deployer")  # ApplicationDeployment模型已删除
    # created_resources = relationship("Resource", back_populates="creator")  # Resource模型已删除
    # resource_reviews = relationship("ResourceReview", back_populates="user")  # ResourceReview模型已删除
    # resource_downloads = relationship("ResourceDownload", back_populates="user")  # ResourceDownload模型已删除

    # 分析功能相关关系
    # behavior_logs = relationship("UserBehaviorLog", back_populates="user")  # UserBehaviorLog模型已删除
    # analytics_queries = relationship("AnalyticsQuery", back_populates="user")  # AnalyticsQuery模型已删除
    # dashboards = relationship("DashboardConfig", back_populates="user")  # DashboardConfig模型已删除
    # analytics_reports = relationship("AnalyticsReport", back_populates="user")  # AnalyticsReport模型已删除

    # 新版智能体相关关系 - 也已删除
    # created_agent_templates = relationship("AgentTemplate", back_populates="creator")  # AgentTemplate模型已删除
    # created_agent_instances = relationship("AgentInstance", back_populates="creator")  # AgentInstance模型已删除
    # agent_conversations_v2 = relationship("AgentConversation", back_populates="user")  # AgentConversation模型已删除

    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}')>"

    @property
    def is_authenticated(self):
        """用户是否已认证"""
        return True

    @property
    def is_anonymous(self):
        """是否为匿名用户"""
        return False

    def get_id(self):
        """获取用户ID"""
        return str(self.id)
