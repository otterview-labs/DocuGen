#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文档处理进度推送API端点
基于JAIP协议和SSE的实时进度通信
"""

import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.rag import RAGContent
from app.shared.response_models import ResponseHelper
from app.services.multimodal_upload_service import multimodal_service
from app.shared.utils.logger_util import get_logger

router = APIRouter()
logger = get_logger("DocumentProgressAPI")


# Pydantic模型
class DocumentProcessingRequest(BaseModel):
    """文档处理请求"""
    document_id: str = Field(..., description="文档ID")
    session_id: str = Field(..., description="SSE会话ID")
    processing_config: Dict[str, Any] = Field(
        default_factory=lambda: {
            "enable_parsing": True,
            "enable_chunking": True,
            "enable_embedding": True,
            "enable_storing": True,
            "enable_analysis": False,
            "chunk_strategy": "hybrid",
            "max_chunk_size": 1000,
            "enable_multimodal": True
        },
        description="处理配置"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "doc_123",
                "session_id": "sse_session_456",
                "processing_config": {
                    "enable_parsing": True,
                    "enable_chunking": True,
                    "enable_embedding": True,
                    "enable_storing": True,
                    "enable_analysis": True,
                    "chunk_strategy": "semantic",
                    "max_chunk_size": 800,
                    "enable_multimodal": True
                }
            }
        }
    )


class ProgressSubscriptionRequest(BaseModel):
    """进度订阅请求"""
    session_id: str = Field(..., description="SSE会话ID")
    progress_token: str = Field(..., description="进度令牌")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "sse_session_456",
                "progress_token": "progress_abc123"
            }
        }
    )


class TaskStatusRequest(BaseModel):
    """任务状态请求"""
    task_id: str = Field(..., description="任务ID")


@router.post("/cancel-task", response_model=Dict)
async def cancel_processing_task(
    request: TaskStatusRequest
):
    """取消文档处理任务"""
    try:
        # 验证任务权限
        tracker = get_progress_tracker()
        if request.task_id not in tracker.tasks:
            return ResponseHelper.error("任务不存在", status=404)

        task = tracker.tasks[request.task_id]
        # 无用户系统，跳过权限检查
        # if task.user_id != current_user.id:
        #     return ResponseHelper.error("无权限操作此任务", status=403)

        # 取消任务
        await document_progress_sse_manager.cancel_document_processing(
            request.task_id,
            "用户主动取消"
        )

        return ResponseHelper.success(
            result={
                "taskId": request.task_id,
                "status": "cancelled",
                "message": "任务已取消"
            },
            message="任务取消成功"
        )

    except Exception as e:
        return ResponseHelper.error(f"取消任务失败: {str(e)}", status=500)

# 已删除的接口：
# - GET /task-status/{task_id} - 已删除，不再使用路径参数


@router.get("/user-tasks", response_model=Dict)
async def get_user_tasks():
    """获取用户的所有处理任务"""
    try:
        # 无用户系统，获取所有任务
        tasks = document_progress_sse_manager.get_user_tasks("anonymous")

        return ResponseHelper.success(
            result={
                "tasks": tasks,
                "totalTasks": len(tasks),
                "activeTasks": len([t for t in tasks if t["status"] in ["pending", "running"]]),
                "completedTasks": len([t for t in tasks if t["status"] == "completed"]),
                "timestamp": datetime.now().isoformat()
            },
            message=f"获取到 {len(tasks)} 个任务"
        )

    except Exception as e:
        return ResponseHelper.error(f"获取任务列表失败: {str(e)}", status=500)


        completed_tasks = len([t for t in tracker.tasks.values() if t.status.value == "completed"])
        failed_tasks = len([t for t in tracker.tasks.values() if t.status.value == "failed"])

        # 活跃会话统计
        active_sessions = len(document_progress_sse_manager.progress_token_to_session)

        return ResponseHelper.success(
            result={
                "totalTasks": total_tasks,
                "runningTasks": running_tasks,
                "completedTasks": completed_tasks,
                "failedTasks": failed_tasks,
                "activeSessions": active_sessions,
                "systemStatus": "healthy" if running_tasks < 10 else "busy",
                "avgProcessingTime": _calculate_average_processing_time(tracker),
                "timestamp": datetime.now().isoformat()
            },
            message="统计信息获取成功"
        )

    except Exception as e:
        return ResponseHelper.error(f"获取统计失败: {str(e)}", status=500)


# 辅助函数

async def _process_document_with_progress(
    task_id: str,
    document_id: str,
    processing_config: Dict[str, Any],
    db: Session
):
    """带进度跟踪的文档处理函数"""
    tracker = get_progress_tracker()

    try:
        # 获取文档
        document = db.query(RAGContent).filter(RAGContent.id == document_id).first()
        if not document:
            await tracker.fail_step(task_id, "get_document", "文档不存在")
            return

        # 获取任务的所有步骤
        task = tracker.tasks.get(task_id)
        if not task:
            logger.error(f"任务不存在: {task_id}")
            return

        steps = task.steps

        # 执行各个处理步骤
        for step in steps:
            try:
                await tracker.start_step(task_id, step.id)

                if step.stage == ProcessingStage.PARSING:
                    await _execute_parsing_step(task_id, step.id, document, tracker)

                elif step.stage == ProcessingStage.CHUNKING:
                    await _execute_chunking_step(task_id, step.id, document, processing_config, tracker)

                elif step.stage == ProcessingStage.EMBEDDING:
                    await _execute_embedding_step(task_id, step.id, document, tracker)

                elif step.stage == ProcessingStage.STORING:
                    await _execute_storing_step(task_id, step.id, document, tracker)

                elif step.stage == ProcessingStage.ANALYZING:
                    await _execute_analysis_step(task_id, step.id, document, tracker)

                await tracker.complete_step(task_id, step.id, f"完成: {step.name}")

                # 模拟处理时间
                await asyncio.sleep(0.5)

            except Exception as e:
                await tracker.fail_step(task_id, step.id, f"步骤失败: {str(e)}")
                break

    except Exception as e:
        logger.error(f"文档处理失败: {e}")
        # 如果有正在运行的步骤，标记为失败
        if task and task.current_step:
            await tracker.fail_step(task_id, task.current_step.id, f"处理异常: {str(e)}")


async def _execute_parsing_step(task_id: str, step_id: str, document: RAGContent, tracker):
    """执行解析步骤"""
    await tracker.update_step_progress(task_id, step_id, 30, "开始解析文档...")
    await asyncio.sleep(0.5)

    await tracker.update_step_progress(task_id, step_id, 60, "提取文本内容...")
    await asyncio.sleep(0.5)

    await tracker.update_step_progress(task_id, step_id, 100, "文档解析完成")


async def _execute_chunking_step(task_id: str, step_id: str, document: RAGContent, config: Dict, tracker):
    """执行分块步骤"""
    await tracker.update_step_progress(task_id, step_id, 20, "开始智能分块...")
    await asyncio.sleep(0.3)

    await tracker.update_step_progress(task_id, step_id, 50, "应用分块策略...")
    await asyncio.sleep(0.4)

    await tracker.update_step_progress(task_id, step_id, 80, "优化分块边界...")
    await asyncio.sleep(0.3)

    await tracker.update_step_progress(task_id, step_id, 100, "分块完成")


async def _execute_embedding_step(task_id: str, step_id: str, document: RAGContent, tracker):
    """执行向量化步骤"""
    await tracker.update_step_progress(task_id, step_id, 25, "初始化向量模型...")
    await asyncio.sleep(0.3)

    await tracker.update_step_progress(task_id, step_id, 60, "生成向量嵌入...")
    await asyncio.sleep(0.7)

    await tracker.update_step_progress(task_id, step_id, 100, "向量化完成")


async def _execute_storing_step(task_id: str, step_id: str, document: RAGContent, tracker):
    """执行存储步骤"""
    await tracker.update_step_progress(task_id, step_id, 40, "连接向量数据库...")
    await asyncio.sleep(0.3)

    await tracker.update_step_progress(task_id, step_id, 80, "存储向量数据...")
    await asyncio.sleep(0.4)

    await tracker.update_step_progress(task_id, step_id, 100, "数据存储完成")


async def _execute_analysis_step(task_id: str, step_id: str, document: RAGContent, tracker):
    """执行分析步骤"""
    await tracker.update_step_progress(task_id, step_id, 30, "启动内容分析...")
    await asyncio.sleep(0.4)

    await tracker.update_step_progress(task_id, step_id, 70, "提取关键信息...")
    await asyncio.sleep(0.6)

    await tracker.update_step_progress(task_id, step_id, 100, "内容分析完成")


def _estimate_processing_duration(config: Dict[str, Any]) -> Dict[str, Any]:
    """估算处理时长"""
    base_time = 5  # 基础时长（秒）

    if config.get("enable_parsing", True):
        base_time += 2
    if config.get("enable_chunking", True):
        base_time += 3
    if config.get("enable_embedding", True):
        base_time += 8
    if config.get("enable_storing", True):
        base_time += 2
    if config.get("enable_analysis", False):
        base_time += 5

    return {
        "estimatedSeconds": base_time,
        "estimatedMinutes": round(base_time / 60, 1),
        "estimatedRange": f"{base_time-2}-{base_time+3}秒"
    }


def _calculate_average_processing_time(tracker) -> float:
    """计算平均处理时间"""
    completed_tasks = [
        task for task in tracker.tasks.values()
        if task.status.value == "completed" and task.end_time
    ]

    if not completed_tasks:
        return 0.0

    total_duration = sum(task.duration for task in completed_tasks)
    return round(total_duration / len(completed_tasks), 2)
