#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@Time   : 2025/1/27
@Author : 13594053100@163.com
@File   : streaming_keyframe_extractor.py
"""

import cv2
import os
import numpy as np
import asyncio
import logging
from typing import List, Tuple, Optional, AsyncGenerator, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import json

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("StreamingKeyframeExtractor")

@dataclass
class ExtractionProgress:
    """提取进度信息"""
    current_frame: int
    total_frames: int
    saved_frames: int
    current_time: float
    total_duration: float
    progress_percentage: float
    status: str  # "processing", "completed", "error"
    message: str
    timestamp: str

@dataclass
class KeyframeInfo:
    """关键帧信息"""
    frame_path: str
    frame_index: int
    timestamp: float
    confidence_score: float
    frame_size: Tuple[int, int]
    extraction_time: str

class StreamingKeyframeExtractor:
    """
    流式关键帧提取器，支持实时进度反馈和流式输出
    """

    def __init__(self, video_path: str, base_output_dir: str = "storage/static/videos"):
        """
        初始化流式关键帧提取器

        Args:
            video_path: 输入视频文件路径
            base_output_dir: 关键帧输出基础目录
        """
        self.video_path = video_path
        self.base_output_dir = base_output_dir
        self.output_dir = self._generate_new_keyframe_dir()
        self.video_info = self._get_video_info()

    def _generate_new_keyframe_dir(self) -> str:
        """生成唯一的输出目录"""
        index = 1
        while True:
            folder_name = f"keyframe_stream_{index:03d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            full_path = os.path.join(self.base_output_dir, folder_name)
            if not os.path.exists(full_path):
                os.makedirs(full_path, exist_ok=True)
                logger.info(f"创建流式关键帧输出目录: {full_path}")
                return full_path
            index += 1

    def _get_video_info(self) -> Dict[str, Any]:
        """获取视频基本信息"""
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频: {self.video_path}")

        info = {
            'fps': cap.get(cv2.CAP_PROP_FPS),
            'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'duration': cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS) if cap.get(cv2.CAP_PROP_FPS) > 0 else 0
        }
        cap.release()
        return info

    async def extract_by_interval_streaming(
        self,
        interval: int = 30,
        tag: str = '',
        diff_threshold: float = 0.65,
        mode: str = 'rgb',
        resize: Optional[Tuple[int, int]] = None,
        enable_progress: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式提取关键帧（按帧间隔）

        Args:
            interval: 每隔多少帧采样一次
            tag: 文件命名前缀
            diff_threshold: 帧差阈值
            mode: 比较模式 ('gray' 或 'rgb')
            resize: 图像缩放尺寸
            enable_progress: 是否启用进度反馈

        Yields:
            包含进度信息和关键帧数据的字典
        """
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            yield {
                'type': 'error',
                'message': f"无法打开视频: {self.video_path}",
                'timestamp': datetime.now().isoformat()
            }
            return

        try:
            frame_index = 0
            saved_index = 0
            last_frame = None
            start_time = datetime.now()

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_index % interval == 0:
                    # 处理帧
                    processed_frame = self._process_frame(frame, resize)

                    # 计算帧差
                    if last_frame is not None:
                        diff_ratio = self._calculate_diff(processed_frame, last_frame, mode)
                        should_save = diff_ratio >= diff_threshold
                    else:
                        should_save = True

                    if should_save:
                        # 保存关键帧
                        frame_name = f"{tag}_frame_{saved_index:04d}.jpg"
                        frame_path = os.path.join(self.output_dir, frame_name)

                        success = cv2.imwrite(frame_path, processed_frame)
                        if success:
                            # 计算置信度分数
                            confidence = self._calculate_confidence_score(processed_frame, last_frame, mode)

                            # 创建关键帧信息
                            keyframe_info = KeyframeInfo(
                                frame_path=frame_path,
                                frame_index=frame_index,
                                timestamp=frame_index / self.video_info['fps'],
                                confidence_score=confidence,
                                frame_size=(processed_frame.shape[1], processed_frame.shape[0]),
                                extraction_time=datetime.now().isoformat()
                            )

                            # 发送关键帧数据
                            yield {
                                'type': 'keyframe',
                                'data': keyframe_info.__dict__,
                                'timestamp': datetime.now().isoformat()
                            }

                            saved_index += 1
                            last_frame = processed_frame.copy()

                            # 发送进度信息
                            if enable_progress:
                                progress = self._create_progress_info(
                                    frame_index, saved_index, start_time
                                )
                                yield {
                                    'type': 'progress',
                                    'data': progress.__dict__,
                                    'timestamp': datetime.now().isoformat()
                                }

                frame_index += 1

                # 添加小延迟避免阻塞
                await asyncio.sleep(0.001)

        finally:
            cap.release()

        # 发送完成信息
        yield {
            'type': 'completed',
            'data': {
                'total_frames_processed': frame_index,
                'total_keyframes_saved': saved_index,
                'output_directory': self.output_dir,
                'processing_time': (datetime.now() - start_time).total_seconds()
            },
            'timestamp': datetime.now().isoformat()
        }

    async def extract_by_time_interval_streaming(
        self,
        seconds: float = 1.0,
        tag: str = '',
        diff_threshold: float = 0.65,
        mode: str = 'rgb',
        resize: Optional[Tuple[int, int]] = None,
        enable_progress: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式提取关键帧（按时间间隔）

        Args:
            seconds: 采样时间间隔（秒）
            tag: 文件命名前缀
            diff_threshold: 帧差阈值
            mode: 比较模式
            resize: 图像缩放尺寸
            enable_progress: 是否启用进度反馈

        Yields:
            包含进度信息和关键帧数据的字典
        """
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            yield {
                'type': 'error',
                'message': f"无法打开视频: {self.video_path}",
                'timestamp': datetime.now().isoformat()
            }
            return

        try:
            frame_interval = int(self.video_info['fps'] * seconds)
            frame_index = 0
            saved_index = 0
            last_frame = None
            start_time = datetime.now()

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_index % frame_interval == 0:
                    # 处理帧
                    processed_frame = self._process_frame(frame, resize)

                    # 计算帧差
                    if last_frame is not None:
                        diff_ratio = self._calculate_diff(processed_frame, last_frame, mode)
                        should_save = diff_ratio >= diff_threshold
                    else:
                        should_save = True

                    if should_save:
                        # 保存关键帧
                        frame_name = f"{tag}_frame_{saved_index:04d}.jpg"
                        frame_path = os.path.join(self.output_dir, frame_name)

                        success = cv2.imwrite(frame_path, processed_frame)
                        if success:
                            # 计算置信度分数
                            confidence = self._calculate_confidence_score(processed_frame, last_frame, mode)

                            # 创建关键帧信息
                            keyframe_info = KeyframeInfo(
                                frame_path=frame_path,
                                frame_index=frame_index,
                                timestamp=frame_index / self.video_info['fps'],
                                confidence_score=confidence,
                                frame_size=(processed_frame.shape[1], processed_frame.shape[0]),
                                extraction_time=datetime.now().isoformat()
                            )

                            # 发送关键帧数据
                            yield {
                                'type': 'keyframe',
                                'data': keyframe_info.__dict__,
                                'timestamp': datetime.now().isoformat()
                            }

                            saved_index += 1
                            last_frame = processed_frame.copy()

                            # 发送进度信息
                            if enable_progress:
                                progress = self._create_progress_info(
                                    frame_index, saved_index, start_time
                                )
                                yield {
                                    'type': 'progress',
                                    'data': progress.__dict__,
                                    'timestamp': datetime.now().isoformat()
                                }

                frame_index += 1
                await asyncio.sleep(0.001)

        finally:
            cap.release()

        # 发送完成信息
        yield {
            'type': 'completed',
            'data': {
                'total_frames_processed': frame_index,
                'total_keyframes_saved': saved_index,
                'output_directory': self.output_dir,
                'processing_time': (datetime.now() - start_time).total_seconds()
            },
            'timestamp': datetime.now().isoformat()
        }

    def _process_frame(self, frame: np.ndarray, resize: Optional[Tuple[int, int]]) -> np.ndarray:
        """处理帧图像"""
        if resize:
            frame = cv2.resize(frame, resize)
        return frame

    def _calculate_diff(self, frame1: np.ndarray, frame2: np.ndarray, mode: str) -> float:
        """计算帧差异"""
        if mode == 'gray':
            frame1_gray = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            frame2_gray = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(frame1_gray, frame2_gray)
            return np.count_nonzero(diff) / diff.size
        elif mode == 'rgb':
            diff = cv2.absdiff(frame1, frame2)
            diff_mean = np.mean(diff, axis=2)
            threshold_value = 30
            return np.count_nonzero(diff_mean > threshold_value) / diff_mean.size
        else:
            raise ValueError(f"不支持的比较模式: {mode}")

    def _calculate_confidence_score(self, current_frame: np.ndarray, last_frame: Optional[np.ndarray], mode: str) -> float:
        """计算置信度分数"""
        if last_frame is None:
            return 1.0

        diff_ratio = self._calculate_diff(current_frame, last_frame, mode)
        # 将差异比例转换为置信度分数（0-1）
        confidence = min(diff_ratio * 2, 1.0)
        return confidence

    def _create_progress_info(self, current_frame: int, saved_frames: int, start_time: datetime) -> ExtractionProgress:
        """创建进度信息"""
        total_frames = self.video_info['total_frames']
        current_time = current_frame / self.video_info['fps']
        total_duration = self.video_info['duration']
        progress_percentage = (current_frame / total_frames) * 100 if total_frames > 0 else 0

        return ExtractionProgress(
            current_frame=current_frame,
            total_frames=total_frames,
            saved_frames=saved_frames,
            current_time=current_time,
            total_duration=total_duration,
            progress_percentage=progress_percentage,
            status="processing",
            message=f"已处理 {current_frame}/{total_frames} 帧，保存 {saved_frames} 个关键帧",
            timestamp=datetime.now().isoformat()
        )

    def get_video_info(self) -> Dict[str, Any]:
        """获取视频信息"""
        return self.video_info.copy()

    def get_output_directory(self) -> str:
        """获取输出目录"""
        return self.output_dir
