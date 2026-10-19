#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Video slicing utility for consuming LLM result dict

Author: 13594053100@163.com
Date: 2025-08-28 15:59:34
LastEditTime: 2025-08-29 13:20:00
"""

from __future__ import annotations

from typing import Dict, Any, List, Tuple
from app.shared.utils.logger_util import get_logger
from app.shared.utils.file_utils import FileUtils

import time
import cv2
import os
import subprocess
from pathlib import Path

# 可选依赖：imageio-ffmpeg（用于定位本地 ffmpeg 可执行文件）
try:
    import imageio_ffmpeg
except Exception:
    imageio_ffmpeg = None  # 若没有也可用系统 PATH 中的 ffmpeg

logger = get_logger("VideoUtils")


# -------------------- 基础工具 --------------------
def _sanitize_tag(tag: str) -> str:
    return FileUtils.sanitize_tag(tag=tag, illegal='<>:"/\\|?*')


def _derive_tag_from_video(video_path: str, n: int = 5) -> str:
    """取视频文件名前 n 位（不足 n 就取全部），并做一次轻量清洗。"""
    stem = Path(video_path).stem
    raw = stem[:max(1, n)] if stem else "video"
    return _sanitize_tag(raw)


def _read_video_meta(src: Path) -> Tuple[float, int, int, int, float]:
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        logger.error(f'OpenCV 无法打开视频：{src}')
        raise FileNotFoundError(f"OpenCV cannot open video: {src}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps > 0 else 0.0
    cap.release()
    return fps, width, height, frame_count, duration


def _safe_time_bounds(start_sec: float, end_sec: float, duration: float) -> Tuple[float, float]:
    """边界保护：落在[0, duration]内，且保证 > 0 的最小时长（0.5s）。"""
    try:
        s = float(start_sec)
        e = float(end_sec)
    except Exception:
        s, e = 0.0, 0.5
    s = max(0.0, s)
    if duration > 0 and s > duration:
        s = max(0.0, duration - 0.5)
    e = max(s, e)
    if duration > 0:
        e = min(duration, e)
    if e - s < 0.5:
        e = min(duration, s + 0.5) if duration > 0 else s + 0.5
    return s, e


def _extract_events_flex(llm_answer_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    兼容两种入参格式：
      A) 直接传 data：{"version": "...", "events": [...]}
      B) 传包装字典：{"ok": true, "data": {...}, "raw": "..."}
    """
    if not isinstance(llm_answer_dict, dict):
        return []
    # 直接是 data
    if "events" in llm_answer_dict and isinstance(llm_answer_dict["events"], list):
        return llm_answer_dict["events"]
    # 外层包装
    data_obj = llm_answer_dict.get("data")
    if isinstance(data_obj, dict) and isinstance(data_obj.get("events"), list):
        return data_obj["events"]
    return []


# -------------------- FFmpeg 工具 --------------------
def _get_ffmpeg_bin() -> str | None:
    """
    优先使用 imageio-ffmpeg 自带的 ffmpeg，其次回退系统 PATH 中的 ffmpeg。
    """
    if imageio_ffmpeg is not None: # 如果没有建议安装imageio_ffmpeg，其会自带FFmpeg二进制文件。
                                    # 安装命令：pip install --upgrade imageio-ffmpeg
        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
    # 回退：系统 PATH
    return "ffmpeg"


def _ffmpeg_available() -> bool:
    ffmpeg_bin = _get_ffmpeg_bin()
    try:
        # 测试是否可用
        subprocess.run([ffmpeg_bin, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False


def _ffmpeg_slice_h264_aac(input_path: Path, start_sec: float, end_sec: float, output_path: Path) -> None:
    """
    用 FFmpeg 精确截取并转码为 H.264 + AAC，首选策略（更稳更兼容）。
    """
    ffmpeg_bin = _get_ffmpeg_bin()
    # 使用输入侧 -ss + -to，转码输出；更精确，避免 B 帧/时间戳问题
    cmd = [
        ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start_sec:.3f}", "-to", f"{end_sec:.3f}",
        "-i", str(input_path),
        "-c:v", "libx264", "-crf", "23", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)


def _opencv_slice(input_path: Path, start_frame: int, end_frame: int, fps: float, width: int, height: int, output_path: Path) -> None:
    """
    OpenCV 回退方案：逐帧写出（更通用，速度可能慢）。
    """
    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"OpenCV cannot open video for reading: {input_path}")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"VideoWriter open failed: {output_path}")

    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        cur = start_frame
        while cur <= end_frame:
            ret, frame = cap.read()
            if not ret:
                break
            writer.write(frame)
            cur += 1
    finally:
        writer.release()
        cap.release()


# -------------------- 主工具类 --------------------
class VideoUtils:
    @staticmethod
    def violation_video_intercept_base_llm_answer_dict(
        original_video_path: str, llm_answer_dict: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        original_video_path：待截取的视频路径
        llm_answer_dict：   LLM 对 original_video 关键帧做出的回答字典
                           （可传 data 或 包装字典 {"ok","data","raw"}）

        return：截取的视频路径列表，每项：
            {
              "type": 事件类型,
              "start_sec": "起始秒(字符串保留两位)",
              "end_sec": "结束秒(字符串保留两位)",
              "output_path": "输出mp4绝对路径"
            }

        规则：
        - 输出文件名：{tag}_{type}.mp4；同类型多段自动加序号：{tag}_{type}_2.mp4 ...
        - tag 为原视频文件名前 5 位（不足取全部）；
        - 跳过 type in {"not_found", "uncertain"} 的事件；
        - 兼容字段名 "ranges"/"range"；
        - 最小切片时长 0.5s，自动边界保护；
        - 输出目录：与原视频同级目录下的 {tag}_clips_base_event/ 。
        """
        src = Path(original_video_path)
        if not src.exists():
            logger.error(f'视频地址无效：{original_video_path}')
            raise FileNotFoundError(f"Video not found: {original_video_path}")

        tag = _derive_tag_from_video(original_video_path, 5)
        fps, width, height, frame_count, duration = _read_video_meta(src)
        logger.info(
            f"打开视频成功 -> {original_video_path} "
            f"fps={fps:.2f}, size={width}x{height}, frames={frame_count}, dur={duration:.2f}s"
        )

        out_dir = src.with_suffix("").parent / f"{tag}_clips_base_event"
        out_dir.mkdir(parents=True, exist_ok=True)

        events = _extract_events_flex(llm_answer_dict)
        if len(events) == 0:
            logger.info("视觉LLM没有检测到任何违规事件（events 为空或未找到）")
            return []

        # 同类型计数器，避免文件名重名
        counters: Dict[str, int] = {}
        results: List[Dict[str, str]] = []

        use_ffmpeg = _ffmpeg_available()
        if use_ffmpeg:
            logger.info("FFmpeg 可用，将优先使用 FFmpeg 进行精准切片（H.264 + AAC）。")
        else:
            logger.info("FFmpeg 不可用，回退使用 OpenCV 逐帧切片。")

        for ev in events:
            ev_type = str(ev.get("type", "")).strip()
            if ev_type in {"", "not_found", "uncertain"}:
                logger.debug(f"跳过事件类型：{ev_type}")
                continue

            ranges = ev.get("ranges") or ev.get("range")
            if not isinstance(ranges, dict):
                logger.debug("跳过无范围事件")
                continue

            start_sec = ranges.get("start_sec", 0.0)
            end_sec = ranges.get("end_sec", 0.0)
            s, e = _safe_time_bounds(start_sec, end_sec, duration)
            start_frame = int(round(s * fps))
            end_frame = int(round(e * fps))

            # 文件命名：{tag}_{type}.mp4；同类型递增
            counters.setdefault(ev_type, 0)
            counters[ev_type] += 1
            base_name = (
                f"{tag}_{ev_type}.mp4"
                if counters[ev_type] == 1
                else f"{tag}_{ev_type}_{counters[ev_type]}.mp4"
            )
            out_path = out_dir / base_name

            logger.info(f"Slice [{ev_type}] {s:.2f}s ~ {e:.2f}s -> {out_path.name}")

            # --- 先 FFmpeg，失败再 OpenCV ---
            sliced_ok = False
            if use_ffmpeg:
                try:
                    _ffmpeg_slice_h264_aac(src, s, e, out_path)
                    # 简单校验：文件存在且>0
                    if out_path.exists() and os.path.getsize(out_path) > 0:
                        sliced_ok = True
                except subprocess.CalledProcessError as ce:
                    logger.warning(f"FFmpeg 切片失败，回退 OpenCV。detail: {ce}")
                except Exception as e_ff:
                    logger.warning(f"FFmpeg 异常，回退 OpenCV。detail: {e_ff}")

            if not sliced_ok:
                # OpenCV 回退
                _opencv_slice(src, start_frame, end_frame, fps, width, height, out_path)

            results.append(
                {
                    "type": ev_type,
                    "start_sec": f"{s:.2f}",
                    "end_sec": f"{e:.2f}",
                    "output_path": str(out_path),
                }
            )

        logger.info(f"事件证据视频片段截取并保存完成. 片段总数: {len(results)}")
        return results


# -------------------- 自测入口 --------------------
if __name__ == "__main__":
    from app.core.agents.template_agent.Intelligent_inspection import IntelligentInspection
    t0 = time.time()

    video_path = r"D:\easyrag_work\JetLinksAI\static\video\光厂_7567837_戴上安全帽的男子慢动作升格镜头工地现场施.mp4"
    results = None
    try:
        insp = IntelligentInspection(
            video_path=video_path,
            seconds=1,
            diff_threshold=0.65
        )
        results = insp.analyze_video(user_query="请检查视频中是否存在违规行为")
    except Exception as e:
        logger.info(f"{e}")

    if results and results.get("ok"):
        logger.info(f'LLM原始回答：{results["raw"]}')
        print('*' * 60)
        logger.info(f'JSON解析后的LLM回答：{results["data"]}')
        try:
            # 推荐直接传 data；函数也兼容传包装字典
            violation_results = VideoUtils.violation_video_intercept_base_llm_answer_dict(
                original_video_path=video_path,
                llm_answer_dict=results["data"]
            )
            for r in violation_results:
                logger.info(f'{r["type"]} -> {r["output_path"]}')
        except Exception as e:
            logger.info(f"{e}")
        logger.info(f'算法运行时间：{time.time() - t0:.2f}')
    else:
        logger.info(f'LLM原始回复为：{results["raw"] if results else ""}')
