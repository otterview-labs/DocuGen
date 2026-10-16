#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问答对批量导入接口
支持JSON、CSV、Excel格式的问答对批量导入
"""

from typing import List, Dict, Optional, Any
from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlalchemy.orm import Session
from pathlib import Path
import json
import csv
import uuid
from datetime import datetime
try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from app.db.session import get_db
from app.services.enhanced_rag_service import get_enhanced_rag_service
from app.shared.response_models import ResponseHelper
from app.db.models.rag import RAGContent

router = APIRouter()


@router.post("/batch", summary="批量导入问答对")
async def import_qa_batch(
    file: UploadFile = File(...),
    collection_id: Optional[str] = Form(default="default"),
    db: Session = Depends(get_db)
):
    """
    批量导入问答对

    支持的文件格式：
    1. JSON格式：
    ```json
    [
      {
        "question": "什么是JetLinks？",
        "answer": "JetLinks是一个开源的企业级物联网平台..."
      },
      {
        "question": "如何接入设备？",
        "answer": "支持MQTT、HTTP、CoAP等多种协议..."
      }
    ]
    ```

    2. CSV格式（带表头）：
    ```csv
    question,answer
    "什么是JetLinks？","JetLinks是一个开源的企业级物联网平台..."
    "如何接入设备？","支持MQTT、HTTP、CoAP等多种协议..."
    ```

    返回：
    - 成功导入的问答对数量
    - 失败的问答对及原因
    """
    try:
        if not file or not file.filename:
            return ResponseHelper.error("未选择文件", status=400)

        # 读取文件内容
        content = await file.read()
        filename = file.filename.lower()

        # 解析问答对
        qa_pairs = []

        if filename.endswith('.json'):
            # JSON格式
            try:
                data = json.loads(content.decode('utf-8'))
                if not isinstance(data, list):
                    return ResponseHelper.error("JSON格式错误：必须是数组", status=400)
                qa_pairs = data
            except json.JSONDecodeError as e:
                return ResponseHelper.error(f"JSON解析失败: {str(e)}", status=400)

        elif filename.endswith('.csv'):
            # CSV格式
            try:
                decoded_content = content.decode('utf-8-sig')  # 处理BOM
                csv_reader = csv.DictReader(decoded_content.splitlines())
                qa_pairs = list(csv_reader)
            except Exception as e:
                return ResponseHelper.error(f"CSV解析失败: {str(e)}", status=400)
        else:
            return ResponseHelper.error("不支持的文件格式，请使用JSON或CSV", status=400)

        if not qa_pairs:
            return ResponseHelper.error("文件中没有问答对数据", status=400)

        # 验证和处理问答对
        rag_service = get_enhanced_rag_service()
        success_count = 0
        failed_items = []

        for idx, item in enumerate(qa_pairs, 1):
            try:
                question = item.get('question', '').strip()
                answer = item.get('answer', '').strip()

                if not question or not answer:
                    failed_items.append({
                        "index": idx,
                        "item": item,
                        "reason": "问题或答案为空"
                    })
                    continue

                # 构建QA文本内容
                qa_text = f"# Q&A {idx}\n\n**问题**: {question}\n\n**答案**: {answer}\n"

                # 添加额外元数据
                metadata = item.get('metadata', {})
                if metadata:
                    qa_text += f"\n**元数据**: {json.dumps(metadata, ensure_ascii=False)}\n"

                # 创建RAGContent记录
                content_id = str(uuid.uuid4())
                rag_content = RAGContent(
                    id=content_id,
                    user_id="default_user",
                    content_type="qa",  # 特殊类型：问答对
                    content_text=qa_text,
                    title=f"Q: {question[:50]}{'...' if len(question) > 50 else ''}",
                    description=answer[:200] + ('...' if len(answer) > 200 else ''),
                    content_summary=answer,
                    processing_status="pending",
                    create_time=datetime.now(),
                    update_time=datetime.now()
                )
                db.add(rag_content)
                db.flush()
                # 确保内容记录已落库（process_document 内部会使用独立 DB 会话写入 rag_chunks）
                db.commit()
                db.refresh(rag_content)

                # 处理文档（分块、向量化）
                try:
                    vector_ids = await rag_service.process_document(
                        content=qa_text,
                        doc_id=content_id,
                        collection_id=collection_id,
                        title=rag_content.title,
                        description=rag_content.description,
                        extra_metadata={
                            "content_type": "qa",
                            "question": question,
                            "answer": answer,
                            **metadata
                        }
                    )

                    if vector_ids:
                        # 更新状态
                        rag_content.processing_status = "completed"
                        rag_content.vector_collection = collection_id
                        # 更新 doc-profile 向量（用于候选文档语义排序）
                        try:
                            await rag_service.upsert_doc_profile_vector(rag_content)
                        except Exception as e:
                            logger.warning(f"更新文档概要向量失败（已忽略）: {e}")
                        success_count += 1
                    else:
                        rag_content.processing_status = "failed"
                        rag_content.processing_message = "向量化失败"
                        failed_items.append({
                            "index": idx,
                            "item": item,
                            "reason": "向量化失败"
                        })

                except Exception as e:
                    logger.error(f"处理问答对 #{idx} 失败: {e}")
                    rag_content.processing_status = "failed"
                    rag_content.processing_message = str(e)
                    failed_items.append({
                        "index": idx,
                        "item": item,
                        "reason": str(e)
                    })

            except Exception as e:
                logger.error(f"导入问答对 #{idx} 失败: {e}")
                failed_items.append({
                    "index": idx,
                    "item": item,
                    "reason": str(e)
                })

        db.commit()

        return ResponseHelper.success(
            result={
                "total": len(qa_pairs),
                "success": success_count,
                "failed": len(failed_items),
                "collection_id": collection_id,
                "failed_items": failed_items[:10]  # 只返回前10个失败项
            },
            message=f"导入完成：成功 {success_count}/{len(qa_pairs)}"
        )

    except Exception as e:
        logger.error(f"批量导入问答对失败: {e}")
        db.rollback()
        return ResponseHelper.error(f"批量导入失败: {str(e)}", status=500)


@router.post("/single", summary="单个问答对导入")
async def import_single_qa(
    question: str = Form(...),
    answer: str = Form(...),
    title: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),
    collection_id: Optional[str] = Form(default="default"),
    db: Session = Depends(get_db)
):
    """
    导入单个问答对

    Args:
        question: 问题
        answer: 答案
        title: 可选标题（默认使用问题作为标题）
        metadata: 可选元数据（JSON字符串）
        collection_id: 集合ID
    """
    try:
        if not question.strip() or not answer.strip():
            return ResponseHelper.error("问题和答案不能为空", status=400)

        # 解析元数据
        extra_meta = {}
        if metadata:
            try:
                extra_meta = json.loads(metadata)
            except:
                pass

        # 构建QA文本
        qa_text = f"# Q&A\n\n**问题**: {question}\n\n**答案**: {answer}\n"
        if extra_meta:
            qa_text += f"\n**元数据**: {json.dumps(extra_meta, ensure_ascii=False)}\n"

        # 创建记录
        content_id = str(uuid.uuid4())
        rag_content = RAGContent(
            id=content_id,
            user_id="default_user",
            content_type="qa",
            content_text=qa_text,
            title=title or f"Q: {question[:50]}{'...' if len(question) > 50 else ''}",
            description=answer[:200] + ('...' if len(answer) > 200 else ''),
            content_summary=answer,
            processing_status="pending",
            create_time=datetime.now(),
            update_time=datetime.now()
        )
        db.add(rag_content)
        db.flush()
        # 确保内容记录已落库（process_document 内部会使用独立 DB 会话写入 rag_chunks）
        db.commit()
        db.refresh(rag_content)

        # 处理文档
        rag_service = get_enhanced_rag_service()
        vector_ids = await rag_service.process_document(
            content=qa_text,
            doc_id=content_id,
            collection_id=collection_id,
            title=rag_content.title,
            description=rag_content.description,
            extra_metadata={
                "content_type": "qa",
                "question": question,
                "answer": answer,
                **extra_meta
            }
        )

        if vector_ids:
            rag_content.processing_status = "completed"
            rag_content.vector_collection = collection_id
            # 更新 doc-profile 向量（用于候选文档语义排序）
            try:
                await rag_service.upsert_doc_profile_vector(rag_content)
            except Exception as e:
                logger.warning(f"更新文档概要向量失败（已忽略）: {e}")
            db.commit()

            return ResponseHelper.success(
                result={
                    "content_id": content_id,
                    "title": rag_content.title,
                    "collection_id": collection_id,
                    "vector_count": len(vector_ids)
                },
                message="问答对导入成功"
            )
        else:
            rag_content.processing_status = "failed"
            rag_content.processing_message = "向量化失败"
            db.commit()
            return ResponseHelper.error("向量化失败", status=500)

    except Exception as e:
        logger.error(f"导入单个问答对失败: {e}")
        db.rollback()
        return ResponseHelper.error(f"导入失败: {str(e)}", status=500)


@router.get("/template", summary="下载问答对导入模板")
async def download_template(format: str = "json"):
    """
    下载问答对导入模板

    Args:
        format: 格式类型（json/csv）
    """
    try:
        if format == "json":
            template = [
                {
                    "question": "什么是JetLinks物联网平台？",
                    "answer": "JetLinks是一个开源的企业级物联网平台，提供设备管理、数据安全通信、消息订阅、规则引擎等核心功能。",
                    "metadata": {
                        "category": "产品介绍",
                        "tags": ["物联网", "开源", "企业级"]
                    }
                },
                {
                    "question": "如何接入设备？",
                    "answer": "JetLinks支持多种协议接入，包括MQTT、HTTP、CoAP、UDP、TCP、WebSocket等。可以通过自定义编解码插件实现设备接入。",
                    "metadata": {
                        "category": "设备接入",
                        "tags": ["设备", "协议", "MQTT"]
                    }
                }
            ]

            return ResponseHelper.success(
                result={
                    "format": "json",
                    "template": template,
                    "example": json.dumps(template, ensure_ascii=False, indent=2)
                },
                message="JSON模板"
            )

        elif format == "csv":
            csv_template = """question,answer,category,tags
"什么是JetLinks物联网平台？","JetLinks是一个开源的企业级物联网平台，提供设备管理、数据安全通信、消息订阅、规则引擎等核心功能。","产品介绍","物联网,开源,企业级"
"如何接入设备？","JetLinks支持多种协议接入，包括MQTT、HTTP、CoAP、UDP、TCP、WebSocket等。可以通过自定义编解码插件实现设备接入。","设备接入","设备,协议,MQTT"
"""

            return ResponseHelper.success(
                result={
                    "format": "csv",
                    "template": csv_template,
                    "note": "CSV文件请使用UTF-8编码保存"
                },
                message="CSV模板"
            )
        else:
            return ResponseHelper.error("不支持的格式，请使用json或csv", status=400)

    except Exception as e:
        logger.error(f"生成模板失败: {e}")
        return ResponseHelper.error(f"生成模板失败: {str(e)}", status=500)
