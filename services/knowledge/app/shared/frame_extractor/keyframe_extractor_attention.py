#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@Time   : 2025/8/1 10:56
@Author : 13594053100@163.com
@File   : keyframe_extractor_attention.py
"""

import cv2
import os
import numpy as np
from typing import List, Tuple, Optional
import logging

# 配置日志输出到控制台
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("KeyframeExtractor")

class KeyframeExtractorAttention:
    def __init__(self, video_path: str, base_output_dir: str = r"D:\easyrag_work\JetLinksAI\static\videos"):
        """
        初始化关键帧提取器，并自动创建唯一的 keyframeXXX 输出目录。

        Args:
            video_path (str): 输入视频路径。
            base_output_dir (str): 输出关键帧保存的主目录路径，默认保存在 storage/static/videos 下。
        """
        self.video_path = video_path
        self.base_output_dir = base_output_dir
        self.output_dir = self._generate_new_keyframe_dir()

    def _generate_new_keyframe_dir(self) -> str:
        """
        在输出主目录中创建不重复的 keyframeXXX 文件夹。

        Returns:
            str: 新创建的 keyframe 文件夹的完整路径。
        """
        index = 1
        while True:
            folder_name = f"keyframe{index:03d}"
            full_path = os.path.join(self.base_output_dir, folder_name)
            if not os.path.exists(full_path):
                os.makedirs(full_path)
                logger.info(f"创建关键帧输出目录: {full_path}")
                return full_path
            index += 1

    def _attention_hook(self, frame: np.ndarray) -> np.ndarray:
        """
        预留的视觉注意力增强处理函数，默认为无操作。

        Args:
            frame (np.ndarray): 当前帧图像。

        Returns:
            np.ndarray: 处理后的帧图像（默认返回原图）。
        """
        return frame

    def _resize_if_needed(self, frame: np.ndarray, resize: Optional[Tuple[int, int]]) -> np.ndarray:
        """
        根据需要调整图像尺寸。

        Args:
            frame (np.ndarray): 原始帧图像。
            resize (Optional[Tuple[int, int]]): 指定的新尺寸 (宽, 高)，若为 None 则保持原尺寸。

        Returns:
            np.ndarray: 调整后或原始尺寸的帧图像。
        """
        if resize:
            return cv2.resize(frame, resize)
        return frame

    def _calculate_diff(self, frame1: np.ndarray, frame2: np.ndarray, mode: str) -> float:
        """
        计算帧之间的差异比值（支持灰度或 RGB 模式）。

        Args:
            frame1 (np.ndarray): 当前帧图像。
            frame2 (np.ndarray): 上一个关键帧图像。
            mode (str): 比较模式，可选 'gray' 或 'rgb'。

        Returns:
            float: 差异比值，范围为 0~1，值越大表示帧间差异越大。
        """
        if mode == 'gray':
            frame1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            frame2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(frame1, frame2)
            return np.count_nonzero(diff) / diff.size
        elif mode == 'rgb':
            diff = cv2.absdiff(frame1, frame2)
            diff_mean = np.mean(diff, axis=2)
            threshold_value = 30
            return np.count_nonzero(diff_mean > threshold_value) / diff_mean.size
        else:
            logger.error(f"不支持的 mode: {mode}")
            raise ValueError(f"Unsupported mode: {mode}")

    def extract_by_interval(self, interval: int = 30, tag: str = '', diff_threshold: float = 0.65,
                            mode: str = 'rgb', resize: Optional[Tuple[int, int]] = None) -> List[str]:
        """
        每隔固定帧数从视频中采样，可选帧差过滤、图像增强与缩放处理。

        Args:
            interval (int): 每隔多少帧进行一次采样。
            tag (str): 可选标签，添加到保存图像文件名中。
            diff_threshold (float): 帧差阈值，超过该值则保存为关键帧。
            mode (str): 比较模式，可选 'gray' 或 'rgb'。
            resize (Optional[Tuple[int, int]]): 图像缩放尺寸 (宽, 高)，默认为原始尺寸。

        Returns:
            List[str]: 提取并保存的关键帧图像路径列表。
        """
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            logger.error(f"无法打开视频: {self.video_path}")
            raise ValueError(f"无法打开视频: {self.video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        logger.info(f"视频总帧数: {total_frames}")

        frame_index = 0
        saved_index = 0
        saved_paths = []
        last_frame = None

        while True:
            ret, frame = cap.read()
            if not ret or frame is None or frame.shape[0] == 0 or frame.shape[1] == 0:
                logger.warning(f"第 {frame_index} 帧无效或读取失败，终止。")
                break

            if frame_index % interval == 0:
                frame = self._attention_hook(frame)
                diff_ratio = 1.0 if last_frame is None else self._calculate_diff(frame, last_frame, mode)

                if last_frame is None or diff_ratio >= diff_threshold:
                    frame = self._resize_if_needed(frame, resize)
                    frame_name = f"{tag}_frame_{saved_index:04d}.jpg"
                    frame_path = os.path.join(self.output_dir, frame_name)
                    cv2.imwrite(frame_path, frame)
                    saved_paths.append(frame_path)
                    last_frame = frame.copy()
                    saved_index += 1

            frame_index += 1

        cap.release()
        logger.info(f"总采样帧数: {frame_index}, 成功保存关键帧: {saved_index}")
        return saved_paths

    def extract_by_time_interval(self, seconds: float = 1.0, tag: str = '', diff_threshold: float = 0.65,
                                 mode: str = 'rgb', resize: Optional[Tuple[int, int]] = None) -> List[str]:
        """
        根据设定的时间间隔从视频中采样，支持图像差异过滤、图像处理模式及尺寸调整。

        Args:
            seconds (float): 采样时间间隔（单位：秒），即每隔多少秒提取一帧。
            tag (str): 可选的标签信息，将附加到保存图像的文件名中，便于分类或索引。
            diff_threshold (float): 图像差异阈值，用于判断帧之间是否存在显著变化，超过该值的帧将被保留。
            mode (str): 图像处理模式，可选值：
                        - 'gray'：将帧转换为灰度图后进行比较；
                        - 'rgb'：使用 RGB 颜色空间进行比较。
            resize (Optional[Tuple[int, int]]): 图像尺寸调整参数，格式为 (宽, 高)。
                                                若为 None，则保持原始帧尺寸。

        Returns:
            List[str]: 返回提取并保存的关键帧图像路径列表。
        """
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            logger.error(f"无法打开视频: {self.video_path}")
            raise ValueError(f"无法打开视频: {self.video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = int(fps * seconds)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        logger.info(f"视频帧率: {fps}，总帧数: {total_frames}")

        frame_index = 0
        saved_index = 0
        saved_paths = []
        last_frame = None

        while True:
            ret, frame = cap.read()
            if not ret or frame is None or frame.shape[0] == 0 or frame.shape[1] == 0:
                logger.warning(f"第 {frame_index} 帧无效或读取失败，终止。")
                break

            if frame_index % frame_interval == 0:
                frame = self._attention_hook(frame)
                diff_ratio = 1.0 if last_frame is None else self._calculate_diff(frame, last_frame, mode)

                if last_frame is None or diff_ratio >= diff_threshold:
                    frame = self._resize_if_needed(frame, resize)
                    frame_name = f"{tag}_frame_{saved_index:04d}.jpg"
                    frame_path = os.path.join(self.output_dir, frame_name)
                    cv2.imwrite(frame_path, frame)
                    saved_paths.append(frame_path)
                    last_frame = frame.copy()
                    saved_index += 1

            frame_index += 1

        cap.release()
        logger.info(f"总采样帧数: {frame_index}, 成功保存关键帧: {saved_index}")
        return saved_paths
