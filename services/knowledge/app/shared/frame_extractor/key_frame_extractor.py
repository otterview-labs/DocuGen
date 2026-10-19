#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
关键帧提取工具
按固定时间间隔提取关键帧（带帧差过滤），输出关键帧及其元数据。

Author: 13594053100@163.com
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple, Optional, Dict
import numpy as np
import time

from app.shared.utils.logger_util import get_logger
from app.shared.utils.file_utils import FileUtils
from app.shared.frame_extractor.motion_diff import MotionDiff, MotionDiffConfig

try:
    import cv2

    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False

logger = get_logger("ExtractByIntervalTimeTool")
illegal = '<>:"/\\|?*'

# ===================== 路径&目录工具 =====================
PARENTS_LEVEL = 3
PROJECT_ROOT = Path(__file__).resolve().parents[PARENTS_LEVEL]
DEFAULT_KEY_FRAME_PARENT = PROJECT_ROOT / "storage" / "static" / "images" / "key_frame"


def _verify_project_root() -> None:
    """校验 PROJECT_ROOT 是否合理（至少要有 storage/static 目录）。"""
    expected_static = PROJECT_ROOT / "storage" / "static"
    if not expected_static.exists() or not expected_static.is_dir():
        raise RuntimeError(
            f"PROJECT_ROOT 推断错误：{PROJECT_ROOT}\n未找到目录：{expected_static}\n"
            f"请调整 PARENTS_LEVEL（当前：{PARENTS_LEVEL}）。"
        )


def _build_key_frame_folder(tag: str,
                            parent: Path = DEFAULT_KEY_FRAME_PARENT) -> Tuple[str, str]:
    """在指定父目录下创建关键帧保存文件夹。"""
    _verify_project_root()

    cleaned = FileUtils.sanitize_tag(tag=tag, illegal=illegal)
    if not cleaned:
        raise ValueError("tag 不能为空。")

    parent = Path(parent).resolve()
    parent.mkdir(parents=True, exist_ok=True)

    folder_name = f"{cleaned}_key_frame"
    folder_path = parent / folder_name
    try:
        folder_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"关键帧目录已创建/存在：{folder_path}")
    except OSError as e:
        raise OSError(f"创建文件夹失败: {folder_path}，错误信息: {e}") from e

    return folder_name, str(folder_path.resolve())


def _save_jpg(path: Path, img, quality: int = 90) -> None:
    """使用 imencode 写文件，解决 OpenCV 在中文路径下写盘失败的问题。"""
    params = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
    ok, buf = cv2.imencode(".jpg", img, params)
    if not ok:
        raise RuntimeError("cv2.imencode('.jpg', ...) failed")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(buf.tobytes())
    logger.debug(f"帧已保存：{path}")


# ===================== 主类 =====================
class ExtractByIntervalTimeTool:
    """按固定时间间隔提取关键帧（带帧差过滤），输出关键帧及其元数据。"""

    def __init__(
        self,
        *,
        video_path: str,
        tag: Optional[str] = None,
        seconds: float = 1.0,
        diff_threshold: float = 0.65,
        resize_w: int = 320,
        jpg_quality: int = 90,
        diff_config: Optional[MotionDiffConfig] = None,
    ) -> None:
        """
        Args:
            video_path: 本地视频路径或流地址（rtsp/http/https）
            tag: 输出文件夹与文件名前缀；为空则取视频名前 5 位
            seconds: 抽帧间隔（秒）
            diff_threshold: 帧差非零比例阈值，[0,1]
            resize_w: 帧差计算时的小图宽度（保持比例）
            jpg_quality: 保存 JPG 的质量 [0,100]
            diff_config: 帧差计算配置
        """
        if seconds <= 0:
            raise ValueError("seconds 必须 > 0")
        if not (0.0 <= diff_threshold <= 1.0):
            raise ValueError("diff_threshold 必须在 [0,1] 之间")
        if not CV2_AVAILABLE:
            raise RuntimeError(
                "OpenCV未安装，当前默认 minimal 安装不包含关键帧提取依赖。"
                "如需启用视频解析，请执行: pip install -r requirements-full.txt"
            )

        self.video_path = str(video_path)
        if tag and tag.strip():
            self.tag = FileUtils.sanitize_tag(tag=tag, illegal=illegal)
        else:
            stem = Path(video_path).stem
            self.tag = stem[:5] if len(stem) >= 5 else stem

        self.seconds = float(seconds)
        self.diff_threshold = float(diff_threshold)
        self.resize_w = int(resize_w)
        self.jpg_quality = int(jpg_quality)

        # ================= 核心变更：避免双重缩放 =================
        # 外部（本类中）已将帧缩放到 self.resize_w，再交给 MotionDiff
        # 因此这里将 MotionDiff 的 resize_w 设为 0，禁止其内部再缩放
        cfg = diff_config or MotionDiffConfig(method="rgb", resize_w=0, norm=True)
        self.diff = MotionDiff(cfg)

    def extract_by_time_interval(self) -> Tuple[List[Dict], str]:
        """
        提取关键帧并保存。

        Returns:
            metadata: List[Dict]
                    [{"path": str, "time_sec": float, "frame_idx": int}]
            folder_abs: str 关键帧保存目录
        """
        if not CV2_AVAILABLE:
            raise RuntimeError(
                "OpenCV未安装，无法执行关键帧提取。"
                "如需启用，请执行: pip install -r requirements-full.txt"
            )

        # 本地文件存在性检查
        lower = self.video_path.lower()
        is_stream = lower.startswith(("rtsp://", "http://", "https://"))
        if (not is_stream) and (not Path(self.video_path).is_file()):
            raise FileNotFoundError(f"video not found: {self.video_path}")

        t0 = time.time()
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise RuntimeError(f"failed to open video: {self.video_path}")

        # 创建关键帧目录
        _, folder_abs = _build_key_frame_folder(self.tag)
        save_folder = Path(folder_abs)

        # 计算步长
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        step = max(1, int(round(fps * self.seconds)))
        logger.info(f"视频 FPS={fps:.2f}，抽帧间隔={self.seconds:.2f}s，步长={step}帧")

        metadata: List[Dict] = []
        saved_index = 0
        frame_counter = 0
        last_small = None

        try:
            while True:
                # 跳过中间帧
                for _ in range(step - 1):
                    if not cap.grab():
                        return metadata, str(save_folder.resolve())
                    frame_counter += 1

                ret, frame = cap.read()
                if not ret:
                    break
                frame_counter += 1

                if frame is None or not isinstance(frame, np.ndarray):
                    continue

                # 小图缩放（保留你的原始逻辑）
                h, w = frame.shape[:2]
                small_h = max(1, int(h * (self.resize_w / max(1, w))))
                small = cv2.resize(frame, (self.resize_w, small_h), interpolation=cv2.INTER_AREA)

                # 帧差计算
                save = last_small is None
                motion_score = 1.0
                if last_small is not None:
                    motion_score = self.diff.compute(last_small, small)
                    save = motion_score >= self.diff_threshold

                if save:
                    name = f"{self.tag}_frame_{saved_index:04d}.jpg"
                    out_path = save_folder / name
                    _save_jpg(out_path, frame, quality=self.jpg_quality)

                    # 时间戳
                    t_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                    t_sec = t_msec / 1000.0 if t_msec > 0 else frame_counter / fps

                    entry = {"path": str(out_path.resolve()), "time_sec": float(t_sec)}
                    entry.update({
                        "frame_idx": frame_counter,
                    })
                    metadata.append(entry)

                    saved_index += 1
                    last_small = small
        finally:
            cap.release()
            logger.info(
                "关键帧提取完成：%d 帧，目录：%s，耗时 %.2f 秒",
                len(metadata), save_folder, time.time() - t0
            )

        return metadata, str(save_folder.resolve())


# ===================== 示例运行 =====================
if __name__ == "__main__":
    tool = ExtractByIntervalTimeTool(
        video_path=r"D:\easyrag_work\OtterFlowAI\static\video\GwW8KUm1c7kR59Pa9C4_348905827390_mp4_264_ld_aliyun.mp4"
    )
    metadata, folder = tool.extract_by_time_interval()
    for md in metadata:
        logger.info(f"{md}")
