#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG相关数据库模型
"""

from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, Float, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.models.base import BaseModel


class RAGContent(BaseModel):
    """RAG内容表"""
    __tablename__ = "rag_contents"

    id = Column(String(64), primary_key=True)
    resource_id = Column(String(64), nullable=False, unique=True, index=True, comment="资源唯一ID")
    user_id = Column(String(64), nullable=False, index=True)
    content_type = Column(String(32), nullable=False, index=True, comment="内容类型: text,image,video,document")
    title = Column(String(255), nullable=True, comment="内容标题")
    description = Column(Text, nullable=True, comment="内容描述")

    # 资源类型字段
    resource_type = Column(String(20), default="file", comment="资源类型: file/text/url")
    resource_name = Column(String(255), comment="资源名称")
    resource_description = Column(Text, comment="资源描述")

    # 文件信息 (扩展)
    file_path = Column(String(500), nullable=True, comment="文件路径")
    file_name = Column(String(255), nullable=True, comment="文件名")
    file_size = Column(Integer, nullable=True, comment="文件大小(字节)")
    mime_type = Column(String(100), nullable=True, comment="MIME类型")
    content_url = Column(String(500), comment="文件URL")
    file_md5 = Column(String(32), comment="MD5值")
    file_sha256 = Column(String(64), comment="SHA256值")

    # 内容信息
    # 跨数据库兼容：MySQL 使用 LONGTEXT，其它数据库使用 TEXT
    content_text = Column(Text().with_variant(LONGTEXT, "mysql"), nullable=True, comment="文本内容")
    content_summary = Column(Text, nullable=True, comment="内容摘要")
    content_tags = Column(JSON, nullable=True, comment="内容标签(JSON数组)")
    content_metadata = Column(JSON, nullable=True, comment="内容元数据(JSON)")

    # 权限绑定
    bindings = Column(JSON, comment="权限绑定key列表，用于细粒度权限控制")

    # 标签修改标记
    tags_manually_modified = Column(Boolean, default=False, comment="标签是否被用户手动修改过")
    summary_manually_modified = Column(Boolean, default=False, comment="摘要是否被用户手动修改过")

    # 向量库信息
    vector_id = Column(String(64), nullable=True, comment="向量库中的ID")
    vector_collection = Column(String(255), nullable=True, comment="向量集合名称")

    # 状态
    status = Column(String(1), nullable=False, default="1", comment="状态: 0-禁用, 1-启用")
    is_public = Column(Boolean, default=True, comment="是否公开")

    # 文档处理状态
    processing_status = Column(String(20), nullable=False, default="pending", index=True,
                              comment="处理状态: pending-等待处理, processing-处理中, completed-处理完成, failed-处理失败")
    processing_message = Column(String(500), nullable=True,
                               comment="处理状态消息，记录处理失败原因或进度信息")

    # 详细处理进度 (JSON格式存储各阶段状态)
    processing_details = Column(JSON, nullable=True,
                               comment="详细处理进度(JSON): 包含各阶段状态、进度百分比、耗时等信息")

    # JAIP会话相关
    session_id = Column(String(64), index=True, comment="关联的JAIP会话ID")

    # 时间戳
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())


class RAGResourceRelation(BaseModel):
    """RAG资源关系表"""
    __tablename__ = "rag_resource_relations"

    id = Column(String(64), primary_key=True)
    source_resource_id = Column(String(64), nullable=False, index=True, comment="源资源ID")
    target_type = Column(String(20), nullable=False, comment="目标类型: device/resource/user")
    target_id = Column(String(64), nullable=False, index=True, comment="目标ID")
    confidence = Column(Float, default=1.0, comment="置信度 0.0-1.0")
    relation_desc = Column(String(255), comment="关系描述")
    expands = Column(JSON, comment="关系属性扩展信息")

    # 状态
    status = Column(String(1), nullable=False, default="1", comment="状态: 0-禁用, 1-启用")

    # 时间戳
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())


class RAGCollection(BaseModel):
    """RAG集合表"""
    __tablename__ = "rag_collections"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    name = Column(String(255), nullable=False, comment="集合名称")
    description = Column(Text, nullable=True, comment="集合描述")

    # 集合类型
    collection_type = Column(String(32), nullable=False, default="text", comment="集合类型: text,multimodal")

    # 向量库配置
    vector_collection_name = Column(String(255), nullable=True, comment="向量库集合名称")
    embedding_model = Column(String(100), nullable=True, comment="默认Embedding模型")
    rerank_model = Column(String(100), nullable=True, comment="默认Rerank模型")

    # 状态
    status = Column(String(1), nullable=False, default="1", comment="状态: 0-禁用, 1-启用")
    is_public = Column(Boolean, default=True, comment="是否公开")

    # 时间戳
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())


class RAGCollectionContent(BaseModel):
    """RAG集合内容关联表"""
    __tablename__ = "rag_collection_contents"

    id = Column(String(64), primary_key=True)
    collection_id = Column(String(64), ForeignKey("rag_collections.id"), nullable=False, index=True)
    content_id = Column(String(64), ForeignKey("rag_contents.id"), nullable=False, index=True)

    # 排序权重
    weight = Column(Float, default=1.0, comment="内容权重")

    # 时间戳
    create_time = Column(DateTime, server_default=func.now())


class RAGMediaAsset(BaseModel):
    """RAG媒体资产表 - 可被视觉检索的媒体对象"""
    __tablename__ = "rag_media_assets"
    __table_args__ = (
        UniqueConstraint("content_id", "asset_key", name="uq_rag_media_assets_content_asset_key"),
    )

    id = Column(String(64), primary_key=True)
    content_id = Column(String(64), ForeignKey("rag_contents.id"), nullable=False, index=True, comment="关联的内容ID")
    asset_key = Column(String(128), nullable=False, default="primary", comment="同一内容下的稳定资产键")
    asset_type = Column(String(32), nullable=False, default="image", index=True, comment="资产类型: image/pdf_page_image/video_frame")
    file_path = Column(String(500), nullable=True, comment="本地文件路径")
    file_url = Column(String(500), nullable=True, comment="可访问文件URL")
    page_no = Column(Integer, nullable=True, comment="PDF页码")
    frame_ts_ms = Column(Integer, nullable=True, comment="视频帧时间戳(ms)")
    width = Column(Integer, nullable=True, comment="原始宽度")
    height = Column(Integer, nullable=True, comment="原始高度")
    asset_metadata = Column(JSON, nullable=True, comment="资产元数据(JSON)")
    status = Column(String(1), nullable=False, default="1", comment="状态: 0-禁用, 1-启用")
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())


class RAGVisualRegion(BaseModel):
    """RAG视觉区域表 - 支持整图与外部传入 bbox region"""
    __tablename__ = "rag_visual_regions"
    __table_args__ = (
        UniqueConstraint("asset_id", "external_key", name="uq_rag_visual_regions_asset_external_key"),
    )

    id = Column(String(64), primary_key=True)
    asset_id = Column(String(64), ForeignKey("rag_media_assets.id"), nullable=False, index=True, comment="关联媒体资产ID")
    external_key = Column(String(128), nullable=False, comment="幂等键")
    external_region_id = Column(String(128), nullable=True, index=True, comment="上游业务传入的region_id")
    region_type = Column(String(32), nullable=False, default="full", index=True, comment="区域类型: full/bbox/ocr_block")
    coord_space = Column(String(16), nullable=False, default="normalized", comment="坐标系: pixel/normalized")
    bbox_raw = Column(JSON, nullable=True, comment="原始bbox(JSON)")
    bbox_normalized = Column(JSON, nullable=True, comment="归一化bbox(JSON)")
    label = Column(String(255), nullable=True, comment="区域标签")
    confidence = Column(Float, nullable=True, comment="区域置信度")
    region_text = Column(Text, nullable=True, comment="区域关联文本")
    source = Column(String(32), nullable=False, default="system", index=True, comment="来源: system/external")
    source_system = Column(String(128), nullable=True, index=True, comment="来源系统标识")
    sort_order = Column(Integer, nullable=False, default=0, comment="排序")
    region_metadata = Column(JSON, nullable=True, comment="区域元数据(JSON)")
    status = Column(String(1), nullable=False, default="1", comment="状态: 0-禁用, 1-启用")
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())


class RAGQuery(BaseModel):
    """RAG查询记录表"""
    __tablename__ = "rag_queries"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    collection_id = Column(String(64), ForeignKey("rag_collections.id"), nullable=True, index=True)

    # 查询信息
    query_text = Column(Text, nullable=False, comment="查询文本")
    query_type = Column(String(32), nullable=False, default="text", comment="查询类型: text,multimodal")

    # 检索参数
    top_k = Column(Integer, default=10, comment="检索数量")
    similarity_threshold = Column(Float, default=0.2, comment="相似度阈值")

    # 结果信息
    result_content = Column(Text, nullable=True, comment="查询结果(JSON格式)")
    result_count = Column(Integer, default=0, comment="结果数量")

    # 性能信息
    response_time = Column(Float, nullable=True, comment="响应时间(秒)")
    token_usage = Column(Integer, default=0, comment="Token使用量")

    # 时间戳
    create_time = Column(DateTime, server_default=func.now())


# RAGDocument 表已删除，功能已合并到 RAGContent


class RAGChunk(BaseModel):
    """RAG文档分块表 - 记录分块细节"""
    __tablename__ = "rag_chunks"

    id = Column(String(64), primary_key=True)
    content_id = Column(String(64), ForeignKey("rag_contents.id"), nullable=True, index=True, comment="关联的内容ID")

    # 分块信息
    chunk_index = Column(Integer, nullable=False, comment="分块索引")
    chunk_text = Column(Text, nullable=False, comment="分块文本")
    chunk_size = Column(Integer, nullable=False, comment="分块大小")

    # 位置信息
    start_position = Column(Integer, nullable=True, comment="起始位置")
    end_position = Column(Integer, nullable=True, comment="结束位置")

    # 向量化信息
    vector_id = Column(String(64), nullable=True, comment="向量库中的ID")
    embedding = Column(Text, nullable=True, comment="向量嵌入(JSON格式)")
    embedding_model = Column(String(100), nullable=True, comment="使用的嵌入模型")

    # 分块策略信息
    chunking_strategy = Column(String(50), nullable=True, comment="分块策略")
    overlap_size = Column(Integer, nullable=True, comment="重叠大小")

    # 语义信息
    semantic_score = Column(Float, nullable=True, comment="语义完整性评分")
    keywords = Column(JSON, nullable=True, comment="分块关键词")

    # 分块元数据
    chunk_metadata = Column(Text, nullable=True, comment="分块元数据(JSON格式)")

    # 状态
    status = Column(String(1), nullable=False, default="1", comment="状态: 0-禁用, 1-启用")

    # 时间戳
    create_time = Column(DateTime, server_default=func.now())
    update_time = Column(DateTime, server_default=func.now(), onupdate=func.now())
