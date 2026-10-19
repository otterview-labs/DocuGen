#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
帧差计算工具
用于视频关键帧提取时判断帧间差异

Author: 13594053100@163.com
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
import cv2
import numpy as np


@dataclass
class MotionDiffConfig:
    """帧差计算配置"""
    method: Literal["rgb", "gray", "hsv"] = "rgb"
    resize_w: int = 0  # 0表示不缩放
    norm: bool = True  # 是否归一化


class MotionDiff:
    """帧差计算工具类"""

    def __init__(self, config: MotionDiffConfig):
        """
        Args:
            config: 帧差计算配置
        """
        self.config = config

    def compute(self, frame1: np.ndarray, frame2: np.ndarray) -> float:
        """
        计算两帧之间的差异分数

        Args:
            frame1: 第一帧
            frame2: 第二帧

        Returns:
            差异分数，范围[0, 1]，值越大差异越大
        """
        if frame1 is None or frame2 is None:
            return 1.0

        # 缩放处理
        if self.config.resize_w > 0:
            h1, w1 = frame1.shape[:2]
            h2, w2 = frame2.shape[:2]
            resize_h1 = max(1, int(h1 * (self.config.resize_w / max(1, w1))))
            resize_h2 = max(1, int(h2 * (self.config.resize_w / max(1, w2))))
            frame1 = cv2.resize(frame1, (self.config.resize_w, resize_h1), interpolation=cv2.INTER_AREA)
            frame2 = cv2.resize(frame2, (self.config.resize_w, resize_h2), interpolation=cv2.INTER_AREA)

        # 确保两帧尺寸相同
        if frame1.shape != frame2.shape:
            return 1.0

        # 根据方法计算差异
        if self.config.method == "gray":
            gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY) if len(frame1.shape) == 3 else frame1
            gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY) if len(frame2.shape) == 3 else frame2
            diff = cv2.absdiff(gray1, gray2)
        elif self.config.method == "hsv":
            hsv1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2HSV)
            hsv2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2HSV)
            diff = cv2.absdiff(hsv1, hsv2)
        else:  # rgb
            diff = cv2.absdiff(frame1, frame2)

        # 计算非零像素比例
        threshold = 30  # 差异阈值
        _, binary = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)
        if len(binary.shape) == 3:
            binary = cv2.cvtColor(binary, cv2.COLOR_BGR2GRAY)

        non_zero = np.count_nonzero(binary)
        total = binary.size
        score = non_zero / max(1, total)

        if self.config.norm:
            # 归一化到[0, 1]
            return float(min(1.0, score))

        return float(score)
