#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用配置文件
所有配置值都来源于环境变量
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.shared.utils.http_auth import normalize_auth_mode
from app.runtime_paths import get_application_root, get_runtime_root


APPLICATION_ROOT = get_application_root()
PROJECT_ROOT = get_runtime_root()
ENV_PATH = Path(os.getenv("JETLINKS_KNOWLEDGE_ENV") or (PROJECT_ROOT / ".env"))
load_dotenv(ENV_PATH)


def _settings_config(**overrides) -> SettingsConfigDict:
    return SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
        **overrides,
    )


def get_storage_path(subdir: str) -> str:
    """获取存储子目录路径"""

    base_path = PROJECT_ROOT / "storage"
    path = base_path / subdir
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


class DatabaseSettings(BaseSettings):
    """数据库配置"""

    model_config = _settings_config()

    DB_DATABASE_TYPE: Literal["mysql", "postgresql", "postgres", "sqlite"] = "postgresql"

    DB_MYSQL_HOST: str = "localhost"
    DB_MYSQL_PORT: int = 5432
    DB_MYSQL_USER: str = "postgres"
    DB_MYSQL_PASSWORD: str = ""
    DB_MYSQL_DATABASE: str = "jetlinks_knowledge"

    SQLITE_DATABASE: str = Field(
        default_factory=lambda: os.path.join(get_storage_path("data"), "jetlinks.db"),
        description="SQLite数据库文件路径",
    )
    SQLALCHEMY_ECHO: bool = Field(default=False, description="是否启用SQLAlchemy SQL日志")
    SQLALCHEMY_POOL_SIZE: int = Field(default=10, description="数据库连接池大小")
    SQLALCHEMY_MAX_OVERFLOW: int = Field(default=20, description="数据库连接池最大溢出连接数")

    @property
    def database_url(self) -> str:
        """获取数据库连接URL"""

        if self.DB_DATABASE_TYPE == "mysql":
            return (
                f"mysql+pymysql://{self.DB_MYSQL_USER}:{self.DB_MYSQL_PASSWORD}"
                f"@{self.DB_MYSQL_HOST}:{self.DB_MYSQL_PORT}/{self.DB_MYSQL_DATABASE}"
            )
        if self.DB_DATABASE_TYPE in {"postgresql", "postgres"}:
            return (
                f"postgresql://{self.DB_MYSQL_USER}:{self.DB_MYSQL_PASSWORD}"
                f"@{self.DB_MYSQL_HOST}:{self.DB_MYSQL_PORT}/{self.DB_MYSQL_DATABASE}"
            )
        if self.DB_DATABASE_TYPE == "sqlite":
            return f"sqlite:///{self.SQLITE_DATABASE}"
        raise ValueError(f"不支持的数据库类型: {self.DB_DATABASE_TYPE}")


class SecuritySettings(BaseSettings):
    """安全配置"""

    model_config = _settings_config(env_prefix="SECURITY_")

    SECRET_KEY: str = Field(default="", description="JWT密钥")
    ALGORITHM: str = Field(default="HS256", description="JWT算法")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="访问令牌过期时间（分钟）")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="刷新令牌过期时间（天）")

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, value: object) -> str:
        if isinstance(value, str) and len(value) >= 32:
            return value
        if not value:
            return "dev-secret-key-for-development-only-change-in-production-32chars"
        if isinstance(value, str) and len(value) < 32:
            raise ValueError(f"SECRET_KEY长度至少32位，当前长度: {len(value)}")
        return str(value)


class VectorDBSettings(BaseSettings):
    """向量数据库配置"""

    model_config = _settings_config(env_prefix="VECTOR_")

    DB_TYPE: Literal["faiss", "milvus", "qdrant", "pgvector"] = Field(
        default="pgvector",
        description="向量数据库类型",
    )
    DB_DIMENSION: int = Field(default=1536, description="向量维度")

    FAISS_INDEX_PATH: str = Field(default=get_storage_path("indices"), description="FAISS索引文件路径")
    FAISS_INDEX_TYPE: str = Field(default="IVFFlat", description="FAISS索引类型")

    MILVUS_HOST: str = Field(default="localhost", description="Milvus主机地址")
    MILVUS_PORT: int = Field(default=19530, description="Milvus端口")
    MILVUS_URI: str = Field(
        default="",
        description="Milvus连接URI，支持HTTP/HTTPS，例如 http://127.0.0.1:19531",
    )
    MILVUS_USE_HTTP: bool = Field(default=False, description="是否通过HTTP(19531)方式连接Milvus")
    MILVUS_USER: str = Field(default="", description="Milvus用户名")
    MILVUS_PASSWORD: str = Field(default="", description="Milvus密码")
    MILVUS_DB: str = Field(default="default", description="Milvus数据库名")
    MILVUS_NPROBE: int = Field(
        default=15,
        description="Milvus搜索的nprobe参数，提升召回可适当调大（代价是耗时）",
    )

    QDRANT_HOST: str = Field(default="localhost", description="Qdrant主机地址")
    QDRANT_PORT: int = Field(default=6333, description="Qdrant端口")
    QDRANT_API_KEY: str = Field(default="", description="Qdrant API密钥")

    @property
    def VECTOR_DB_TYPE(self) -> str:
        return self.DB_TYPE

    @property
    def VECTOR_DB_DIMENSION(self) -> int:
        return self.DB_DIMENSION

    @field_validator("DB_TYPE", mode="before")
    @classmethod
    def normalize_vector_db_type(cls, value: object) -> object:
        current_env = (os.getenv("VECTOR_DB_TYPE") or "").strip()
        if not current_env:
            legacy = (os.getenv("VECTOR_VECTOR_DB_TYPE") or "").strip()
            if legacy:
                value = legacy
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("DB_DIMENSION", mode="before")
    @classmethod
    def normalize_vector_db_dimension(cls, value: object) -> object:
        current_env = (os.getenv("VECTOR_DB_DIMENSION") or "").strip()
        if not current_env:
            legacy = (os.getenv("VECTOR_VECTOR_DB_DIMENSION") or "").strip()
            if legacy:
                value = legacy
        return value


class GraphDBSettings(BaseSettings):
    """图数据库配置"""

    model_config = _settings_config()

    GRAPH_DB_ENABLED: bool = False
    GRAPH_DB_TYPE: Literal["neo4j", "postgres"] = Field(
        default="postgres",
        description="知识图谱存储类型：postgres（默认，使用主库 PostgreSQL 表存储）或 neo4j（兼容模式）",
    )
    GRAPH_PG_SCHEMA: str = Field(default="public", description="当 GRAPH_DB_TYPE=postgres 时使用的schema")
    GRAPH_NAMESPACE: str = Field(
        default="default",
        description="图数据命名空间（Postgres 后端用于隔离；Neo4j 兼容模式不区分）",
    )
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    NEO4J_DATABASE: str = "neo4j"
    NEO4J_MAX_CONNECTION_POOL_SIZE: int = 100
    NEO4J_CONNECTION_TIMEOUT: float = 30.0

    @property
    def is_configured(self) -> bool:
        """检查知识图谱后端是否已配置。"""

        if not self.GRAPH_DB_ENABLED:
            return False
        if (self.GRAPH_DB_TYPE or "").lower() == "postgres":
            db_type = (os.getenv("DB_DATABASE_TYPE", "") or "").lower()
            return db_type in {"postgresql", "postgres"}
        return bool(self.NEO4J_URI and self.NEO4J_USERNAME and self.NEO4J_PASSWORD is not None)

    @property
    def neo4j_config(self) -> dict:
        """获取Neo4j配置字典"""

        return {
            "uri": self.NEO4J_URI,
            "username": self.NEO4J_USERNAME,
            "password": self.NEO4J_PASSWORD,
            "database": self.NEO4J_DATABASE,
            "max_connection_pool_size": self.NEO4J_MAX_CONNECTION_POOL_SIZE,
            "connection_timeout": self.NEO4J_CONNECTION_TIMEOUT,
        }


class LLMSettings(BaseSettings):
    """LLM配置"""

    model_config = _settings_config()

    LLM_PROVIDER: Literal["openai", "local"] = Field(default="openai", description="LLM提供商")
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API密钥")
    OPENAI_API_BASE: str = Field(default="https://api.openai.com/v1", description="OpenAI API基础URL")
    OPENAI_MODEL_NAME: str = Field(default="gpt-3.5-turbo", description="OpenAI模型名称")
    OPENAI_API_AUTH_MODE: Literal["none", "bearer", "basic"] = Field(default="bearer", description="OpenAI/OpenAI-compatible 认证方式")
    OPENAI_API_USERNAME: str = Field(default="", description="OpenAI-compatible Basic Auth 用户名")
    OPENAI_API_PASSWORD: str = Field(default="", description="OpenAI-compatible Basic Auth 密码")
    LOCAL_LLM_ENDPOINT: str = Field(default="", description="本地LLM端点")
    LOCAL_LLM_MODEL_NAME: str = Field(default="", description="本地LLM模型名称")
    LOCAL_LLM_AUTH_MODE: Literal["none", "bearer", "basic"] = Field(default="none", description="本地 LLM 认证方式")
    LOCAL_LLM_API_KEY: str = Field(default="", description="本地 LLM Bearer Token")
    LOCAL_LLM_USERNAME: str = Field(default="", description="本地 LLM Basic Auth 用户名")
    LOCAL_LLM_PASSWORD: str = Field(default="", description="本地 LLM Basic Auth 密码")

    @field_validator("OPENAI_API_KEY", mode="before")
    @classmethod
    def normalize_openai_api_key(cls, value: object) -> str:
        current_env = (os.getenv("OPENAI_API_KEY") or "").strip()
        if not current_env:
            legacy = os.getenv("LLM_API_KEY")
            if legacy and legacy.strip():
                value = legacy
        if value is None:
            return ""
        if isinstance(value, str) and value.strip().lower() in {"disabled", "none", "null"}:
            return ""
        return str(value)

    @field_validator("OPENAI_API_BASE", mode="before")
    @classmethod
    def normalize_openai_api_base(cls, value: object) -> object:
        current_env = (os.getenv("OPENAI_API_BASE") or "").strip()
        if not current_env:
            legacy = os.getenv("LLM_API_BASE") or os.getenv("LLM_BASE_URL")
            if legacy and legacy.strip():
                return legacy.strip()
        return value

    @field_validator("OPENAI_MODEL_NAME", mode="before")
    @classmethod
    def normalize_openai_model_name(cls, value: object) -> object:
        current_env = (os.getenv("OPENAI_MODEL_NAME") or "").strip()
        if not current_env:
            legacy = os.getenv("LLM_MODEL_NAME") or os.getenv("LLM_MODEL")
            if legacy and legacy.strip():
                return legacy.strip()
        return value

    @field_validator("OPENAI_API_AUTH_MODE", "LOCAL_LLM_AUTH_MODE", mode="before")
    @classmethod
    def normalize_llm_auth_mode(cls, value: object) -> str:
        return normalize_auth_mode(str(value) if value is not None else None)


class EmbeddingSettings(BaseSettings):
    """Embedding模型配置"""

    model_config = _settings_config(env_prefix="EMBEDDING_")

    PROVIDER: Literal["openai", "local"] = Field(default="openai", description="Embedding提供商")
    OPENAI_EMBEDDING_MODEL: str = Field(
        default="text-embedding-ada-002",
        description="OpenAI Embedding模型名称",
    )
    LOCAL_EMBEDDING_URL: str = Field(default="", description="本地Embedding服务URL")
    LOCAL_EMBEDDING_MODEL: str = Field(default="", description="本地Embedding模型名称")
    LOCAL_EMBEDDING_AUTH_MODE: Literal["none", "bearer", "basic"] = Field(default="none", description="本地 Embedding 认证方式")
    LOCAL_EMBEDDING_API_KEY: str = Field(default="", description="本地 Embedding Bearer Token")
    LOCAL_EMBEDDING_USERNAME: str = Field(default="", description="本地 Embedding Basic Auth 用户名")
    LOCAL_EMBEDDING_PASSWORD: str = Field(default="", description="本地 Embedding Basic Auth 密码")

    @property
    def EMBEDDING_PROVIDER(self) -> str:
        return self.PROVIDER

    @field_validator("PROVIDER", mode="before")
    @classmethod
    def normalize_embedding_provider(cls, value: object) -> object:
        current_env = (os.getenv("EMBEDDING_PROVIDER") or "").strip()
        if not current_env:
            legacy = os.getenv("EMBEDDING_MODEL_TYPE")
            if legacy and legacy.strip():
                value = legacy
            else:
                return value
        if isinstance(value, str):
            raw_value = value.strip()
            normalized = raw_value.lower()
            mapping = {
                "openai": "openai",
                "local": "local",
                "qwen": "openai",
                "openaiembedding": "openai",
                "localembedding": "local",
            }
            if raw_value in {"OpenAI", "Local"}:
                return normalized
            return mapping.get(normalized, normalized)
        return value

    @field_validator("OPENAI_EMBEDDING_MODEL", mode="before")
    @classmethod
    def normalize_openai_embedding_model(cls, value: object) -> object:
        current_env = (
            (os.getenv("EMBEDDING_OPENAI_EMBEDDING_MODEL") or "").strip()
            or (os.getenv("OPENAI_EMBEDDING_MODEL") or "").strip()
        )
        if not current_env:
            return (
                (os.getenv("EMBEDDING_MODEL_NAME") or "").strip()
                or value
            )
        return value

    @field_validator("LOCAL_EMBEDDING_AUTH_MODE", mode="before")
    @classmethod
    def normalize_local_embedding_auth_mode(cls, value: object) -> str:
        return normalize_auth_mode(str(value) if value is not None else None, default="none")


class RerankSettings(BaseSettings):
    """Rerank模型配置"""

    model_config = _settings_config(env_prefix="RERANK_")

    PROVIDER: Literal["openai", "local", "disabled"] = Field(
        default="openai",
        description="Rerank提供商",
    )
    OPENAI_RERANK_MODEL: str = Field(default="text-embedding-ada-002", description="OpenAI Rerank模型名称")
    LOCAL_RERANK_URL: str = Field(default="", description="本地Rerank服务URL")
    LOCAL_RERANK_MODEL: str = Field(default="", description="本地Rerank模型名称")
    LOCAL_RERANK_AUTH_MODE: Literal["none", "bearer", "basic"] = Field(default="none", description="本地 Rerank 认证方式")
    LOCAL_RERANK_API_KEY: str = Field(default="", description="本地 Rerank Bearer Token")
    LOCAL_RERANK_USERNAME: str = Field(default="", description="本地 Rerank Basic Auth 用户名")
    LOCAL_RERANK_PASSWORD: str = Field(default="", description="本地 Rerank Basic Auth 密码")

    @property
    def RERANK_PROVIDER(self) -> str:
        return self.PROVIDER

    @field_validator("PROVIDER", mode="before")
    @classmethod
    def normalize_rerank_provider(cls, value: object) -> object:
        current_env = (os.getenv("RERANK_PROVIDER") or "").strip()
        if not current_env:
            legacy = os.getenv("RERANK_MODEL_TYPE")
            if legacy and legacy.strip():
                value = legacy
            else:
                return value
        if isinstance(value, str):
            raw_value = value.strip()
            normalized = raw_value.lower()
            if normalized in {"disabled", "disable", "none", "null", "false", "0"}:
                return "disabled"
            if raw_value in {"OpenAI", "Local"}:
                return normalized
            return normalized
        return value

    @field_validator("OPENAI_RERANK_MODEL", mode="before")
    @classmethod
    def normalize_openai_rerank_model(cls, value: object) -> object:
        current_env = (
            (os.getenv("RERANK_OPENAI_RERANK_MODEL") or "").strip()
            or (os.getenv("OPENAI_RERANK_MODEL") or "").strip()
        )
        if not current_env:
            return (
                (os.getenv("RERANK_MODEL_NAME") or "").strip()
                or value
            )
        return value

    @field_validator("LOCAL_RERANK_AUTH_MODE", mode="before")
    @classmethod
    def normalize_local_rerank_auth_mode(cls, value: object) -> str:
        return normalize_auth_mode(str(value) if value is not None else None, default="none")


class DataSyncSettings(BaseSettings):
    """数据同步配置"""

    model_config = _settings_config(env_prefix="DATA_SYNC_")

    AUTO_SYNC_ON_STARTUP: bool = Field(
        default=False,
        description="启动时是否自动执行数据一致性检查和修复",
    )
    SYNC_CHECK_TIMEOUT: int = Field(default=300, description="数据同步检查超时时间（秒）")
    AUTO_REPAIR_INCONSISTENCIES: bool = Field(
        default=True,
        description="是否自动修复发现的数据不一致问题",
    )
    SYNC_LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="数据同步操作的日志级别",
    )
    MAX_SYNC_RETRIES: int = Field(default=3, description="同步操作失败时的最大重试次数")


class RedisSettings(BaseSettings):
    """Redis 配置（可选）"""

    model_config = _settings_config()

    REDIS_URL: str = Field(default="", description="Redis 连接 URL（优先）")
    REDIS_HOST: str = Field(default="", description="Redis 主机")
    REDIS_PORT: int = Field(default=6379, description="Redis 端口")
    REDIS_PASSWORD: str = Field(default="", description="Redis 口令")
    REDIS_DB: int = Field(default=0, description="Redis DB")
    REDIS_DECODE_RESPONSES: bool = Field(default=True, description="是否 decode")
    REDIS_SOCKET_TIMEOUT: float = Field(default=5.0, description="socket 超时（秒）")
    REDIS_SOCKET_CONNECT_TIMEOUT: float = Field(default=5.0, description="连接超时（秒）")
    REDIS_RETRY_ON_TIMEOUT: bool = Field(default=True, description="超时是否重试")

    @property
    def is_configured(self) -> bool:
        return bool((self.REDIS_URL or "").strip() or (self.REDIS_HOST or "").strip())


class StorageSettings(BaseSettings):
    """存储路径配置"""

    model_config = _settings_config()

    STORAGE_ROOT: str = Field(
        default_factory=lambda: str(PROJECT_ROOT / "storage"),
        description="存储根目录路径",
    )
    DATA_DIR: str = Field(
        default_factory=lambda: get_storage_path("data"),
        validation_alias="STORAGE_DATA_DIR",
        description="数据文件目录",
    )
    UPLOADS_DIR: str = Field(
        default_factory=lambda: get_storage_path("uploads"),
        validation_alias="STORAGE_UPLOADS_DIR",
        description="上传文件目录",
    )
    STATIC_DIR: str = Field(
        default_factory=lambda: get_storage_path("static"),
        validation_alias="STORAGE_STATIC_DIR",
        description="静态资源目录",
    )
    INDICES_DIR: str = Field(
        default_factory=lambda: get_storage_path("indices"),
        validation_alias="STORAGE_INDICES_DIR",
        description="向量索引目录",
    )
    LOGS_DIR: str = Field(
        default_factory=lambda: get_storage_path("logs"),
        validation_alias="STORAGE_LOGS_DIR",
        description="日志文件目录",
    )
    TEMP_DIR: str = Field(
        default_factory=lambda: get_storage_path("temp"),
        validation_alias="STORAGE_TEMP_DIR",
        description="临时文件目录",
    )
    WORKSPACE_DIR: str = Field(
        default_factory=lambda: get_storage_path("workspace"),
        validation_alias="STORAGE_WORKSPACE_DIR",
        description="工作空间目录",
    )


class ContextCompressionSettings(BaseSettings):
    """上下文压缩配置"""

    model_config = _settings_config()

    COMPRESSION_STRATEGY: Literal["sliding_window", "importance_based", "summary_based", "hybrid"] = Field(
        default="hybrid",
        validation_alias="CONTEXT_COMPRESSION_STRATEGY",
        description="对话压缩策略",
    )
    MAX_CONTEXT_TOKENS: int = Field(
        default=4000,
        validation_alias="CONTEXT_MAX_TOKENS",
        description="压缩后最大token数",
    )
    MAX_CONTEXT_MESSAGES: int = Field(
        default=20,
        validation_alias="CONTEXT_MAX_MESSAGES",
        description="最大保留消息数",
    )
    SUMMARY_RATIO: float = Field(
        default=0.3,
        validation_alias="CONTEXT_SUMMARY_RATIO",
        description="摘要部分占比",
    )
    IMPORTANCE_THRESHOLD: float = Field(
        default=0.5,
        validation_alias="CONTEXT_IMPORTANCE_THRESHOLD",
        description="消息重要性阈值",
    )
    PRESERVE_RECENT_COUNT: int = Field(
        default=5,
        validation_alias="CONTEXT_PRESERVE_RECENT",
        description="必须保留的最近消息数",
    )
    ENABLE_LLM_SUMMARY: bool = Field(
        default=True,
        validation_alias="CONTEXT_ENABLE_LLM_SUMMARY",
        description="是否启用LLM摘要功能",
    )


class KnowledgeGraphPipelineSettings(BaseSettings):
    """知识图谱构建流水线配置"""

    model_config = _settings_config()

    ENABLED: bool = Field(
        default=True,
        validation_alias="KG_ENABLED",
        description="是否启用知识图谱构建（流水线层面）",
    )
    MIN_TEXT_LENGTH: int = Field(
        default=0,
        validation_alias="KG_MIN_TEXT_LENGTH",
        description="触发知识图谱构建的最小文本长度阈值",
    )


class StartupSettings(BaseSettings):
    """启动期控制开关。"""

    model_config = _settings_config(env_prefix="STARTUP_")

    CHECK_DATABASE_ON_STARTUP: bool = Field(default=True, description="启动时是否执行数据库连通性检查")
    INITIALIZE_DATABASE_ON_STARTUP: bool = Field(default=False, description="启动时是否执行 create_all")
    RUN_DATABASE_MIGRATIONS_ON_STARTUP: bool = Field(default=False, description="启动时是否执行在线迁移脚本")
    SEED_LLM_CONFIG_ON_STARTUP: bool = Field(default=False, description="启动时是否初始化 LLM 配置数据")
    FAIL_FAST_ON_STARTUP_ERROR: bool = Field(default=True, description="启动检查失败时是否直接终止服务启动")


class HealthSettings(BaseSettings):
    """健康检查配置。"""

    model_config = _settings_config(env_prefix="HEALTH_")

    CHECK_REDIS: bool = Field(default=True, description="是否检测 Redis 健康状态")
    CHECK_VECTOR_DB: bool = Field(default=True, description="是否检测向量库健康状态")
    CHECK_GRAPH_DB: bool = Field(default=True, description="是否检测知识图谱健康状态")
    TIMEOUT_SECONDS: float = Field(default=3.0, description="依赖探活超时时间（秒）")


class AppSettings(BaseSettings):
    """应用主配置"""

    model_config = _settings_config(case_sensitive=False)

    ENVIRONMENT: Literal["development", "production", "test"] = Field(default="development", description="运行环境")
    PROJECT_ROOT: str | None = Field(default=None, description="项目根目录")
    LOG_LEVEL: str = Field(default="INFO", description="日志级别")
    LOG_FILE: str | None = Field(default=None, description="日志文件路径")
    HOST: str = Field(default="0.0.0.0", description="服务器主机地址")
    PORT: int = Field(default=8006, description="服务器端口")
    DEBUG: bool = Field(default=False, description="是否启用调试模式")
    DEV_MODE: bool = Field(default=True, description="是否为开发模式（影响认证行为）")
    SKIP_AUTH: bool = Field(default=True, description="是否跳过认证检查（开发阶段使用）")

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    vector_db: VectorDBSettings = Field(default_factory=VectorDBSettings)
    graph_db: GraphDBSettings = Field(default_factory=GraphDBSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    rerank: RerankSettings = Field(default_factory=RerankSettings)
    data_sync: DataSyncSettings = Field(default_factory=DataSyncSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    context_compression: ContextCompressionSettings = Field(default_factory=ContextCompressionSettings)
    kg_pipeline: KnowledgeGraphPipelineSettings = Field(default_factory=KnowledgeGraphPipelineSettings)
    startup: StartupSettings = Field(default_factory=StartupSettings)
    health: HealthSettings = Field(default_factory=HealthSettings)

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT.lower() == "test"


settings = AppSettings()

if not settings.PROJECT_ROOT:
    settings.PROJECT_ROOT = str(PROJECT_ROOT)
