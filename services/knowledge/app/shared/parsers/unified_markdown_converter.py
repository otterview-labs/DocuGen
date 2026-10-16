#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一Markdown转换器
支持文档、图片、视频多模态内容转换为Markdown格式
集成音视频预处理、关键帧提取、VLM分析和语音识别
"""

import os
import json
import uuid
from datetime import datetime
import asyncio
import functools
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import tempfile
import shutil
import re

from app.shared.utils.logger_util import get_logger
from app.shared.audio_processor.media_processor import is_video_processable

# 创建VLM适配器，兼容旧接口
class SimpleVLMAgent:
    """兼容旧接口的VLM适配器"""

    def __init__(self, system_instruction=None, max_images_per_batch=48, **kwargs):
        from app.shared.vlm import VisionAnalyzer, VLMConfig

        # 创建VLM配置，忽略其他不支持的参数
        config = VLMConfig(
            system_prompt=system_instruction or "你是一个视觉分析助手，请准确描述图像内容。",
            output_format="json",
            max_images_per_batch=max_images_per_batch
        )
        self.analyzer = VisionAnalyzer(config)
        # 保存其他参数以兼容旧接口
        self.max_images_per_batch = max_images_per_batch

    def run_with_metadata(self, metadata, user_query, **kwargs):
        """兼容旧的metadata接口"""
        # 分析视频帧
        result = self.analyzer.analyze_video_frames(
            frames_metadata=metadata,
            prompt=user_query
        )

        if result.success and result.data:
            # 检查是否已经是期望的格式
            if "events" in result.data:
                # 如果返回的是events格式，直接返回
                return result.data

            # 如果是images格式，转换为frames
            if "images" in result.data:
                frames = []
                images = result.data.get("images", [])

                # 如果只有一个描述性的image，则分配给每一帧
                if len(images) == 1 and len(metadata) > 1:
                    # 单个描述应用到所有帧
                    desc = images[0].get("description", "")
                    for i, meta in enumerate(metadata):
                        frames.append({
                            "frame_idx": meta.get("frame_idx", i),
                            "time_sec": meta.get("time_sec", 0),
                            "description": desc,
                            "objects": [],
                            "scene": "",
                            "events": []
                        })
                else:
                    # 逐帧转换
                    for i, meta in enumerate(metadata):
                        img_data = images[i] if i < len(images) else {}
                        frames.append({
                            "frame_idx": meta.get("frame_idx", i),
                            "time_sec": meta.get("time_sec", 0),
                            "description": img_data.get("description", ""),
                            "objects": img_data.get("objects", []),
                            "scene": img_data.get("scene", ""),
                            "events": img_data.get("events", [])
                        })
                return {"frames": frames}

            # 如果是纯描述，转换为frames
            if "description" in result.data and isinstance(result.data.get("description"), str):
                frames = []
                desc = result.data.get("description", "")
                for i, meta in enumerate(metadata):
                    frames.append({
                        "frame_idx": meta.get("frame_idx", i),
                        "time_sec": meta.get("time_sec", 0),
                        "description": desc if i == 0 else "",  # 只在第一帧显示描述
                        "objects": [],
                        "scene": "",
                        "events": []
                    })
                return {"frames": frames}

        # 返回默认结果
        return {"frames": []}

    def run_batch_check(self, images_or_dir, user_query, **kwargs):
        """兼容旧的批量检查接口"""
        # 处理输入
        if isinstance(images_or_dir, str):
            images = [images_or_dir]
        elif isinstance(images_or_dir, list):
            images = images_or_dir
        else:
            images = []

        # 分析图片
        result = self.analyzer.analyze_images(
            images=images,
            prompt=user_query
        )

        if result.success and result.data:
            # 首先检查根级别是否有events（新格式）
            if "events" in result.data:
                return result.data

            # 否则从images数组中提取（旧格式）
            all_events = []
            all_descriptions = []

            for img_data in result.data.get("images", []):
                events = img_data.get("events", [])
                if events:
                    all_events.extend(events)
                desc = img_data.get("description", "")
                if desc:
                    all_descriptions.append(desc)

            return {
                "events": all_events,
                "description": " ".join(all_descriptions) if all_descriptions else "图像内容"
            }

        return {"events": [], "description": "分析失败"}
# from app.services.processing_progress_manager import ProcessingStage
# 直接定义ProcessingStage
class ProcessingStage:
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    STORING = "storing"
    ANALYZING = "analyzing"

logger = get_logger("UnifiedMarkdownConverter")


def _build_optional_dependency_error(feature: str, requirements_file: str, package_hint: str = "") -> RuntimeError:
    hint = f"（缺少或未启用: {package_hint}）" if package_hint else ""
    return RuntimeError(
        f"{feature} 所需可选依赖当前不可用{hint}。"
        f"默认安装为 minimal；如需启用该能力，请执行: pip install -r {requirements_file}"
    )


def _detect_bad_pdf_text_layer(text: str, min_chars: int = 100) -> Optional[str]:
    """Detect garbled PDF text layers before accepting pdfplumber output."""
    stripped = (text or "").strip()
    if len(stripped) < min_chars:
        return f"text_too_short:{len(stripped)}"

    compact = re.sub(r"\s+", "", stripped)
    if not compact:
        return "text_empty_after_compact"

    meaningful_count = len(re.findall(r"[A-Za-z0-9\u4e00-\u9fff]", compact))
    bullet_count = len(re.findall(r"[•●○▪■◆◦]", compact))
    replacement_count = compact.count("\ufffd")
    meaningful_ratio = meaningful_count / max(len(compact), 1)
    bullet_ratio = bullet_count / max(len(compact), 1)
    replacement_ratio = replacement_count / max(len(compact), 1)

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    symbol_only_lines = [
        line for line in lines
        if re.fullmatch(r"[•●○▪■◆◦·.\-_\s]+", line)
    ]
    symbol_only_ratio = len(symbol_only_lines) / max(len(lines), 1)
    bullet_runs = len(re.findall(r"(?:[•●○▪■◆◦]\s*){6,}", stripped))

    if meaningful_ratio < 0.25:
        return f"low_meaningful_ratio:{meaningful_ratio:.2f}"
    if replacement_ratio > 0.02:
        return f"replacement_char_ratio:{replacement_ratio:.2f}"
    if bullet_runs >= 2:
        return f"bullet_replacement_runs:{bullet_runs}"
    if len(symbol_only_lines) >= 2 and symbol_only_ratio > 0.15:
        return f"symbol_only_line_ratio:{symbol_only_ratio:.2f}"
    if bullet_count >= 20 and bullet_ratio > 0.12:
        return f"bullet_char_ratio:{bullet_ratio:.2f}"

    return None


class UnifiedMarkdownConverter:
    """统一Markdown转换器"""

    def __init__(self, progress_manager=None):
        self.progress_manager = progress_manager
        self._media_processor = None
        self._image_optimizer = None
        # 延迟初始化音频处理器，只在需要时创建
        self._paraformer_transcriber = None
        self._vlm_agent = None

        # 处理配置
        self.config = {
            'video': {
                'max_duration': 7200,        # 最大2小时
                'keyframe_interval': 1.0,    # 1秒间隔
                'diff_threshold': 0.65,      # 帧差阈值
                'enable_audio': True,        # 启用音频处理
                'batch_size': 48            # VLM批处理大小
            },
            'audio': {
                'sample_rate': 16000,
                'channels': 1,
                'format': 'wav'
            },
            'image': {
                'optimize': True,
                'max_size': (1280, 1280),
                'quality': 85
            }
        }

    @property
    def media_processor(self):
        """延迟初始化媒体处理器，避免音视频依赖影响顶层导入。"""
        if self._media_processor is None:
            from app.shared.audio_processor.media_processor import MediaProcessor

            self._media_processor = MediaProcessor()
        return self._media_processor

    @property
    def image_optimizer(self):
        if self._image_optimizer is None:
            from app.shared.audio_processor.image_optimizer import ImageOptimizer

            self._image_optimizer = ImageOptimizer()
        return self._image_optimizer

    @property
    def vlm_agent(self):
        """延迟初始化 VLM 适配器，避免可选视觉链路影响启动。"""
        if self._vlm_agent is None:
            self._vlm_agent = SimpleVLMAgent(
                system_instruction=(
                    "你是一个严格遵循指令的视觉分析助手。"
                    "所有回答必须是单个 JSON 对象，且不包含任何额外文字、解释、Markdown 围栏或注释。"
                    "如无法识别，输出 {\"events\": []}。"
                ),
                max_images_per_batch=48
            )
        return self._vlm_agent

    @property
    def paraformer_transcriber(self):
        """延迟初始化音频处理器"""
        if self._paraformer_transcriber is None:
            from app.shared.audio_processor.paraformer_transcriber import ParaformerTranscriber
            self._paraformer_transcriber = ParaformerTranscriber()
        return self._paraformer_transcriber

    async def convert_video_to_markdown(self, video_path: str, output_dir: str,
                                 title: Optional[str] = None,
                                 enable_audio: bool = True,
                                 content_id: Optional[str] = None) -> Dict[str, Any]:
        """
        视频转Markdown的完整流程

        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            title: 视频标题
            enable_audio: 是否启用音频处理

        Returns:
            包含Markdown内容和元数据的字典
        """
        try:
            logger.info(f"开始处理视频: {video_path}")

            try:
                from app.shared.frame_extractor.key_frame_extractor import ExtractByIntervalTimeTool
                from app.shared.audio_processor.image_optimizer import batch_optimize_keyframes
            except Exception as exc:
                raise _build_optional_dependency_error(
                    "视频解析",
                    "requirements-full.txt",
                    "opencv-python / imageio-ffmpeg / 相关音视频依赖",
                ) from exc

            # 1. 视频验证
            processable, message = is_video_processable(video_path, self.config['video']['max_duration'])
            if not processable:
                raise ValueError(f"视频无法处理: {message}")

            # 创建工作目录
            work_dir = Path(output_dir) / f"video_processing_{uuid.uuid4().hex[:8]}"
            work_dir.mkdir(parents=True, exist_ok=True)

            # 2. 媒体预处理
            logger.info("开始媒体预处理...")
            # 将重CPU/IO操作放入线程池，避免阻塞事件循环
            media_results = await asyncio.to_thread(
                self.media_processor.batch_process_video,
                video_path, str(work_dir / "processed_media")
            )

            if not media_results['success']:
                raise RuntimeError(f"媒体预处理失败: {media_results.get('error')}")

            # 3. 关键帧提取
            logger.info("开始关键帧提取...")
            # 生成视频文件的标签名称（用于关键帧文件夹命名）
            video_name = Path(video_path).stem
            keyframe_extractor = ExtractByIntervalTimeTool(
                video_path=media_results['standardized_video'],
                tag=video_name,  # 添加必需的tag参数
                seconds=self.config['video']['keyframe_interval'],
                diff_threshold=self.config['video']['diff_threshold']
            )

            # extract_by_time_interval返回(List[Dict], str)，第一个是元数据列表，第二个是目录
            keyframes_metadata, keyframes_dir = await asyncio.to_thread(
                keyframe_extractor.extract_by_time_interval
            )
            logger.info(f"提取到 {len(keyframes_metadata)} 个关键帧")

            if not keyframes_metadata:
                raise RuntimeError("未提取到任何关键帧")

            # keyframes_metadata已经是字典列表，包含path、time_sec、frame_idx等字段
            # 提取路径列表用于后续处理
            keyframe_paths = [item['path'] for item in keyframes_metadata]

            # 为了保持一致性，给每个元数据添加timestamp字段（如果没有）
            for item in keyframes_metadata:
                if 'timestamp' not in item:
                    frame_time = item['time_sec']
                    item['timestamp'] = f"{int(frame_time//60):02d}:{int(frame_time%60):02d}"

            # 4. 图像优化
            logger.info("开始图像优化...")
            optimized_dir = str(work_dir / "optimized_frames")
            optimized_paths = await asyncio.to_thread(
                batch_optimize_keyframes, keyframe_paths, optimized_dir
            )

            # 更新关键帧元数据中的优化路径
            for i, item in enumerate(keyframes_metadata):
                if i < len(optimized_paths):
                    item['optimized_path'] = optimized_paths[i]

            # 5. VLM视觉分析
            logger.info("开始VLM视觉分析...")
            # 为VLM分析准备元数据，使用优化后的路径
            vlm_metadata = []
            for item in keyframes_metadata:
                vlm_item = item.copy()
                # 如果有优化路径，使用优化路径；否则使用原始路径
                vlm_item['path'] = item.get('optimized_path', item['path'])
                vlm_metadata.append(vlm_item)
            vlm_analysis = self._analyze_keyframes_with_vlm(vlm_metadata, content_id)

            # 6. 音频处理（可选）
            audio_transcript: Optional[Dict[str, Any]] = None

            if enable_audio and self.config['video']['enable_audio'] and media_results.get("audio_available"):
                logger.info("开始音频处理...")
                audio_transcript = await self._process_audio(media_results['asr_audio'], keyframes_metadata)
                if audio_transcript is None:
                    # 真异常：函数内部崩溃或抛错被吞，这里记录并兜底
                    logger.warning("音频处理返回 None（异常）")
                    audio_transcript = {"ok": False, "reason": "文件不存在或转录器抛错", "full_transcript": "", "segments": [], "aligned_timeline": []}
            else:
                # 记录更详细的跳过原因
                skip_reasons = []
                if not enable_audio:
                    skip_reasons.append("enable_audio=False")
                if not self.config['video']['enable_audio']:
                    skip_reasons.append("config.enable_audio=False")
                if not media_results.get("audio_available"):
                    skip_reasons.append(f"audio_available={media_results.get('audio_available')}")
                    if media_results.get('audio_warning'):
                        skip_reasons.append(f"原因: {media_results.get('audio_warning')}")

                logger.warning(f"音频处理被跳过: {', '.join(skip_reasons)}")
                audio_transcript = None  # 明确设置为None，表示音频未处理

            # 7. 生成Markdown
            logger.info("开始生成Markdown...")
            markdown_content = self._generate_video_markdown(
                video_path=video_path,
                title=title,
                keyframes_metadata=keyframes_metadata,
                vlm_analysis=vlm_analysis,
                audio_transcript=audio_transcript,
                work_dir=str(work_dir)
            )


            # 8. 保存结果
            markdown_file = work_dir / "video_content.md"
            await asyncio.to_thread(
                self._write_text_file,
                str(markdown_file),
                markdown_content
            )

            # 构建返回结果
            result = {
                'success': True,
                'markdown_content': markdown_content,
                'markdown_file': str(markdown_file),
                'metadata': {
                    'video_path': str(video_path),  # 转为字符串避免JSON序列化错误
                    'title': title or Path(video_path).stem,
                    'keyframes_count': len(keyframes_metadata),
                    'has_audio': audio_transcript is not None,
                    'processing_time': datetime.now().isoformat(),
                    'work_dir': str(work_dir)
                },
                'assets': {
                    'keyframes_dir': str(keyframes_dir),
                    'optimized_frames_dir': str(optimized_dir),
                    'processed_video': str(media_results['standardized_video']) if media_results['standardized_video'] else None,
                    'audio_file': str(media_results['asr_audio']) if enable_audio and media_results['asr_audio'] else None
                }
            }

            logger.info(f"视频转换完成: {result['metadata']}")
            return result

        except Exception as e:
            logger.error(f"视频转Markdown失败: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'markdown_content': None
            }

    def _write_text_file(self, path: str, content: str):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _analyze_keyframes_with_vlm(self, keyframes_metadata: List[Dict], content_id: Optional[str] = None) -> str:
        """使用VLM分析关键帧序列"""
        try:
            # 构建用户查询
            # 使用严格 JSON 输出的用户指令
            user_query = """
仅输出 JSON，对输入的关键帧序列进行结构化检测结果汇总，JSON 结构如下：
{
  "events": [
    {
      "type": "scene|object|text|issue",
      "description": "字符串，简明客观描述",
      "ranges": {"start_sec": 0.0, "end_sec": 0.0},
      "evidence": [
        {"img": "对应帧的路径或URL", "time_sec": 0.0, "frame_idx": 0}
      ],
      "attributes": {"可选键": "可选值"}
    }
  ]
}
要求：
- 只输出一个 JSON 对象，不要任何额外文字或 Markdown 围栏；
- 若无法确定时间段，可省略 ranges 字段；
- 每个事件给出至少一条 evidence；
- 若没有可识别事件，返回 {"events": []}。
"""

            # 创建简单的进度追踪器（如果需要）
            progress_tracker = None
            if self.progress_manager and content_id:
                # 创建一个简单的进度追踪器包装器
                class SimpleProgressTracker:
                    def __init__(self, progress_manager, content_id):
                        self.progress_manager = progress_manager
                        self.content_id = content_id
                        self.total_batches = 0
                        self.total_images = 0

                    def start_processing(self, batch_count, total_images):
                        self.total_batches = batch_count
                        self.total_images = total_images
                        logger.info(f"VLM开始处理: {total_images}张图片，分{batch_count}批")

                    def start_batch(self, batch_index, batch_size):
                        logger.info(f"VLM处理批次 {batch_index}/{self.total_batches}: {batch_size}张图片")

                    def update_tokens(self, usage_data):
                        if usage_data:
                            logger.debug(f"Token使用: {usage_data}")

                    def end_batch(self, success, result_text):
                        if success:
                            logger.debug(f"批次处理成功")
                        else:
                            logger.warning(f"批次处理失败: {result_text[:200] if result_text else 'No result'}")

                    def end_processing(self, success):
                        if success:
                            logger.info(f"VLM处理完成")
                        else:
                            logger.error(f"VLM处理失败")

                progress_tracker = SimpleProgressTracker(self.progress_manager, content_id)

            # 使用VLM分析（自动处理批次）- 直接同步调用
            analysis_result = self.vlm_agent.run_with_metadata(
                metadata=keyframes_metadata,
                user_query=user_query,
                sort_by_time=True,
                progress_tracker=progress_tracker
            )

            # 保存原始分析结果供后续使用
            self._last_vlm_analysis = analysis_result

            # 添加调试日志
            logger.info(f"VLM分析完成，结果类型: {type(analysis_result)}")
            if isinstance(analysis_result, dict):
                logger.info(f"VLM结果键: {list(analysis_result.keys())}")
                if 'frames' in analysis_result:
                    frames_count = len(analysis_result.get('frames', []))
                    logger.info(f"VLM返回了 {frames_count} 个帧的分析结果")
                    # 打印前两个帧的分析结果作为样本
                    for i, frame in enumerate(analysis_result.get('frames', [])[:2]):
                        logger.info(f"帧 {i} 分析结果: {frame}")

            # 如果返回的是字典，尝试提取分析文本
            if isinstance(analysis_result, dict):
                # 尝试从常见字段提取文本内容
                if 'analysis' in analysis_result:
                    return analysis_result['analysis']
                elif 'result' in analysis_result:
                    return str(analysis_result['result'])
                elif 'events' in analysis_result:
                    # 如果是事件格式，转换为描述文本
                    events = analysis_result.get('events', [])
                    descriptions = []
                    for event in events:
                        if isinstance(event, dict):
                            desc = event.get('description', '')
                            if desc:
                                descriptions.append(desc)
                    if descriptions:
                        return "\n\n".join(descriptions)
                elif 'frames' in analysis_result:
                    # 如果是frames格式，提取每帧的描述
                    frames = analysis_result.get('frames', [])
                    if frames:
                        logger.info(f"处理 {len(frames)} 个帧的VLM分析结果")
                        # 保存到元数据中供后续使用
                        for i, frame in enumerate(frames):
                            if i < len(keyframes_metadata):
                                desc = frame.get('description', '')
                                objs = frame.get('objects', [])
                                scene = frame.get('scene', '')

                                keyframes_metadata[i]['vlm_description'] = desc
                                keyframes_metadata[i]['vlm_objects'] = objs
                                keyframes_metadata[i]['vlm_scene'] = scene

                                # 记录已保存的内容
                                if desc or objs or scene:
                                    logger.info(f"帧 {i} VLM数据已保存 - 描述: {desc[:50]}..., 对象: {objs}, 场景: {scene}")
                                else:
                                    logger.warning(f"帧 {i} VLM数据为空")
                    else:
                        logger.warning("VLM返回了frames键但内容为空")
                    # 不返回文本，让后续在时间轴中显示
                    return ""
                # 如果无法提取，返回JSON字符串
                import json
                return json.dumps(analysis_result, ensure_ascii=False, indent=2)
            else:
                return str(analysis_result)

        except Exception as e:
            logger.error(f"VLM分析失败: {str(e)}", exc_info=True)
            # 尝试标记所有帧为分析失败
            for i in range(len(keyframes_metadata)):
                keyframes_metadata[i]['vlm_description'] = f"VLM分析失败: {str(e)}"
            return f"VLM分析失败: {str(e)}"

    async def _process_audio(self, audio_path: str, keyframes_metadata: List[Dict]) -> Optional[Dict[str, Any]]:
        """
        处理音频转录并与关键帧对齐

        Args:
            audio_path: 音频文件路径
            keyframes_metadata: 关键帧元数据列表（包含时间戳等信息）

        Returns:
            - None: 文件不存在或读取/转录发生异常
            - dict: 结构化转录结果
                * full_transcript: str  可能为空
                * segments: list       可能为空
                * aligned_timeline: list 可能为空
                * metadata: dict       可包含转录元数据或空字典

        逻辑说明：
            1. 文件不存在或转录器抛错 -> None（真正失败）
            2. 文件存在但为空或静音 -> 返回空字典，不算失败
            3. 正常音频 -> 返回完整转录结果
        """
        try:
            import os
            import numpy as np
            import soundfile as sf

            logger.info("开始Paraformer音频处理...")

            # ---------- 1. 文件存在性校验 ----------
            if not os.path.exists(audio_path):
                logger.warning(f"音频文件不存在: {audio_path}")
                return None

            if os.path.getsize(audio_path) < 1024:  # 小于1KB基本可视为空
                logger.warning(f"音频文件过小(<1KB)，视为空文件: {audio_path}")
                return {
                    "full_transcript": "",
                    "segments": [],
                    "aligned_timeline": [],
                    "metadata": {}
                }

            # ---------- 2. 静音检测 ----------
            try:
                y, sr = sf.read(audio_path, dtype='float32', always_2d=False)
                if y is None or y.size == 0:
                    logger.warning(f"音频文件为空: {audio_path}")
                    return {
                        "full_transcript": "",
                        "segments": [],
                        "aligned_timeline": [],
                        "metadata": {}
                    }
                if y.ndim > 1:  # 转单声道
                    y = y.mean(axis=-1)
                rms = float(np.sqrt(np.mean(np.square(y)))) if y.size else 0.0
                voiced_ratio = float(np.count_nonzero(np.abs(y) > 0.01)) / float(sr if sr else 16000)
                if rms < 0.005 or voiced_ratio < 0.1:
                    logger.warning(f"音频检测为静音: {audio_path}")
                    return {
                        "full_transcript": "",
                        "segments": [],
                        "aligned_timeline": [],
                        "metadata": {}
                    }
            except Exception as e:
                # 静音检测失败时不阻塞主流程，只记录日志
                logger.warning(f"静音检测失败，继续尝试转录: {e}")

            # ---------- 3. 正常音频转录 ----------
            # 获取完整转录结果（异步调用）
            transcription_result = await self.paraformer_transcriber.transcribe_audio_file(audio_path)

            # 使用Paraformer进行音频转录和时间轴对齐
            aligned_timeline = await self.paraformer_transcriber.align_with_keyframes(
                audio_path, keyframes_metadata
            )

            if transcription_result.get("success"):
                return {
                    "full_transcript": transcription_result.get("full_transcript", ""),
                    "segments": transcription_result.get("segments", []),
                    "aligned_timeline": aligned_timeline or [],
                    "metadata": transcription_result.get("metadata", {})
                }
            else:
                logger.error(f"音频转录失败: {transcription_result.get('error')}")
                return None

        except Exception as e:
            logger.error(f"音频处理失败: {str(e)}")
            return None


    def _generate_video_markdown(self, video_path: str, title: Optional[str],
                                keyframes_metadata: List[Dict], vlm_analysis: str,
                                audio_transcript: Optional[Dict[str, Any]], work_dir: str) -> str:
        """生成视频的Markdown内容"""
        # 获取服务器的基础URL（可选）
        # - 未设置时，生成相对路径（/optimized_frames/...），更适配端口映射/反向代理场景
        # - 设置时，生成绝对路径（<base>/optimized_frames/...），便于离线导出/外链引用
        base_url = (os.getenv("SERVICE_BASE_URL") or "").strip().rstrip("/")
        base_prefix = base_url if base_url else ""

        # 视频基本信息
        video_info = self.media_processor.get_media_info(video_path)
        video_title = title or Path(video_path).stem
        duration_str = self._format_duration(video_info.get('duration', 0))

        # 构建Markdown内容
        markdown_parts = []

        # 标题和基本信息
        markdown_parts.append(f"# {video_title}")
        markdown_parts.append("")
        markdown_parts.append("## 视频信息")
        # markdown_parts.append(f"- **文件名**: {Path(video_path).name}")
        markdown_parts.append(f"- **时长**: {duration_str}")
        markdown_parts.append(f"- **分辨率**: {video_info['video']['width']}x{video_info['video']['height']}")
        markdown_parts.append(f"- **关键帧数量**: {len(keyframes_metadata)}")

        # 音频状态显示
        if audio_transcript and audio_transcript.get('full_transcript'):
            markdown_parts.append(f"- **音频转录**: 成功（{len(audio_transcript.get('full_transcript', ''))} 字符）")
        elif audio_transcript and not audio_transcript.get('full_transcript'):
            markdown_parts.append(f"- **音频转录**: 无语音内容")
        else:
            markdown_parts.append(f"- **音频转录**: 未处理（视频无音频或提取失败）")

        markdown_parts.append(f"- **处理时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        markdown_parts.append("")

        # 完整转录稿（如果有音频）
        if audio_transcript and audio_transcript.get('full_transcript'):
            markdown_parts.append("## 完整转录稿")
            markdown_parts.append("")
            markdown_parts.append(f'"{audio_transcript["full_transcript"]}"')
            markdown_parts.append("")

            # 转录质量信息
            if 'metadata' in audio_transcript:
                metadata = audio_transcript['metadata']
                avg_confidence = metadata.get('average_confidence', 0)
                segments_count = metadata.get('segments_count', 0)
                markdown_parts.append(f"**转录质量**: 平均置信度 {avg_confidence:.2f}, {segments_count}个音频片段")
                markdown_parts.append("")

        # VLM分析结果
        if vlm_analysis:
            markdown_parts.append(vlm_analysis)
            markdown_parts.append("")

        # 多模态时间轴（如果有音频对齐）
        # if audio_transcript and audio_transcript.get('aligned_timeline'):
        if False:  # 暂时禁用多模态时间轴展示，改为仅视觉关键帧索引
            markdown_parts.append("## 多模态时间轴")
            markdown_parts.append("")

            aligned_timeline = audio_transcript['aligned_timeline']
            for i, item in enumerate(aligned_timeline):
                time_str = self._format_duration(item['time_sec'])
                frame_path = item.get('optimized_path', item['path'])
                # 使用可外部访问的URL路径
                rel_path = f"{base_url}/optimized_frames/{os.path.basename(frame_path)}"

                transcript = item.get('transcript', '')
                confidence = item.get('transcript_confidence', 0)

                markdown_parts.append(f"### 时间点 {i+1}: {time_str}")
                markdown_parts.append(f"![关键帧{i+1}]({rel_path})")

                # 获取VLM分析的描述（如果有的话）
                frame_metadata = keyframes_metadata[i] if i < len(keyframes_metadata) else {}
                vlm_desc = frame_metadata.get('vlm_description', '')
                vlm_scene = frame_metadata.get('vlm_scene', '')
                vlm_objects = frame_metadata.get('vlm_objects', [])

                # 构建画面内容描述
                if vlm_desc:
                    markdown_parts.append(f"**画面内容**: {vlm_desc}")
                elif vlm_scene:
                    markdown_parts.append(f"**画面内容**: {vlm_scene}")
                elif vlm_objects:
                    objects_str = ", ".join(vlm_objects) if isinstance(vlm_objects, list) else str(vlm_objects)
                    markdown_parts.append(f"**画面内容**: 检测到{objects_str}")
                else:
                    markdown_parts.append(f"**画面内容**: （视觉分析进行中）")

                if transcript.strip():
                    markdown_parts.append(f"**语音内容**: \"{transcript.strip()}\"")
                    if confidence > 0:
                        markdown_parts.append(f"**转录置信度**: {confidence:.2f}")

                markdown_parts.append("")
        else:
            # 仅视觉的关键帧索引
            markdown_parts.append("## 关键帧索引")
            markdown_parts.append("")

            for i, frame_info in enumerate(keyframes_metadata):
                time_str = self._format_duration(frame_info['time_sec'])
                frame_path = frame_info.get('optimized_path', frame_info['path'])

                # 使用可外部访问的URL路径
                # 统一使用 /optimized_frames/ 路由，因为关键帧都经过了优化处理
                if 'optimized_path' in frame_info:
                    # 优化后的图片路径
                    rel_path = f"{base_prefix}/optimized_frames/{os.path.basename(frame_path)}"
                else:
                    # 原始关键帧路径（也尝试通过optimized_frames路由访问）
                    rel_path = f"{base_prefix}/optimized_frames/{os.path.basename(frame_path)}"

                markdown_parts.append(f"### 关键帧 {i+1} - {time_str}")
                markdown_parts.append(f"![关键帧{i+1}]({rel_path})")
                markdown_parts.append(f"时间位置: {time_str}  ")
                markdown_parts.append(f"帧索引: {frame_info['frame_idx']}  ")

                # 添加VLM分析的画面描述
                vlm_desc = frame_info.get('vlm_description', '')
                vlm_scene = frame_info.get('vlm_scene', '')
                vlm_objects = frame_info.get('vlm_objects', [])

                # 调试日志
                if i < 2:  # 只记录前两帧
                    logger.info(f"生成Markdown时，帧 {i} 的VLM数据: desc={vlm_desc}, scene={vlm_scene}, objects={vlm_objects}")

                if vlm_desc:
                    markdown_parts.append(f"**画面内容**: {vlm_desc}")
                elif vlm_scene:
                    markdown_parts.append(f"**画面内容**: {vlm_scene}")
                elif vlm_objects:
                    objects_str = ", ".join(vlm_objects) if isinstance(vlm_objects, list) else str(vlm_objects)
                    markdown_parts.append(f"**画面内容**: 检测到{objects_str}")
                # else:
                #     markdown_parts.append(f"**画面内容**: （视觉分析进行中）")

                markdown_parts.append("")

        # 音频转录片段详情（可选，用于调试）
        if audio_transcript and audio_transcript.get('segments') and len(audio_transcript['segments']) <= 20:
            markdown_parts.append("## 音频片段详情")
            markdown_parts.append("")

            for segment in audio_transcript['segments'][:10]:  # 只显示前10个片段
                start_time = self._format_duration(segment.get('start_time', 0))
                end_time = self._format_duration(segment.get('end_time', 0))
                text = segment.get('text', '').strip()
                confidence = segment.get('confidence', 0)

                if text:
                    markdown_parts.append(f"**{start_time}-{end_time}**: \"{text}\" (置信度: {confidence:.2f})")
                    markdown_parts.append("")

        # 技术信息
        markdown_parts.append("## 技术信息")
        markdown_parts.append(f"- **关键帧提取间隔**: {self.config['video']['keyframe_interval']}秒")
        markdown_parts.append(f"- **帧差阈值**: {self.config['video']['diff_threshold']}")
        markdown_parts.append(f"- **VLM批处理大小**: {self.config['video']['batch_size']}")
        markdown_parts.append(f"- **图像优化**: {'启用' if self.config['image']['optimize'] else '禁用'}")

        if audio_transcript:
            markdown_parts.append(f"- **音频采样率**: {self.config['audio']['sample_rate']}Hz")
            markdown_parts.append(f"- **音频格式**: {self.config['audio']['format']}")
            markdown_parts.append(f"- **语音识别模型**: Paraformer-realtime-v2")

        markdown_parts.append("")

        return "\n".join(markdown_parts)

    def _format_duration(self, seconds: float) -> str:
        """格式化时长为 HH:MM:SS 格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def convert_document_to_markdown(self, doc_path: str, **kwargs) -> Dict[str, Any]:
        """文档转Markdown（支持md、txt、pdf等）"""
        try:
            file_ext = Path(doc_path).suffix.lower()
            title = kwargs.get('title') or Path(doc_path).stem

            if file_ext == ".md":
                # Markdown文件直接读取
                with open(doc_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                return {
                    "success": True,
                    "markdown_content": content,
                    "metadata": {
                        "file_type": "markdown",
                        "processing_method": "direct_read",
                        "char_count": len(content),
                        "processing_time": datetime.now().isoformat()
                    }
                }

            elif file_ext == ".txt":
                # 文本文件转换为Markdown
                with open(doc_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 简单的文本到Markdown转换
                markdown_content = f"# {title}\n\n{content}"

                return {
                    "success": True,
                    "markdown_content": markdown_content,
                    "metadata": {
                        "file_type": "text",
                        "processing_method": "text_to_markdown",
                        "char_count": len(content),
                        "processing_time": datetime.now().isoformat()
                    }
                }

            elif file_ext == ".pdf":
                # PDF文件解析：优先使用轻量级方案（pdfplumber + Tesseract OCR）
                # 跳过MinerU（需要下载大模型，服务器网络受限）
                logger.info(f"开始解析PDF: {title}")

                # 先使用 pdfplumber；仅在扫描版场景再加载 OCR 依赖
                try:
                    import pdfplumber

                    logger.info("[PDF解析] 优先使用 pdfplumber 提取文本")

                    with pdfplumber.open(doc_path) as pdf:
                        text_content = ""
                        for page in pdf.pages:
                            page_text = page.extract_text() or ""
                            text_content += page_text + "\n\n"

                    logger.info(f"[PDF解析] pdfplumber提取文本长度: {len(text_content)}")

                    bad_text_reason = _detect_bad_pdf_text_layer(text_content, min_chars=100)
                    if bad_text_reason is None:
                        markdown_content = f"# {title}\n\n{text_content.strip()}"
                        logger.info("[PDF解析] 文字版PDF，直接提取成功")

                        return {
                            "success": True,
                            "markdown_content": markdown_content,
                            "metadata": {
                                "file_type": "pdf",
                                "processing_method": "pdfplumber",
                                "char_count": len(text_content),
                                "processing_time": datetime.now().isoformat()
                            }
                        }

                    logger.warning(
                        f"[PDF解析] pdfplumber文本层质量不合格({bad_text_reason})，尝试OCR"
                    )

                    try:
                        from pdf2image import convert_from_path
                        import pytesseract
                    except Exception as ocr_import_error:
                        logger.warning(f"[PDF解析] OCR依赖不可用，跳过Tesseract OCR: {ocr_import_error}")
                        raise

                    logger.info("[PDF解析] 启动Tesseract OCR识别...")

                    images = convert_from_path(doc_path, dpi=200)
                    logger.info(f"[PDF解析] 转换了{len(images)}页图片")

                    ocr_text = f"# {title}\n\n"
                    for i, img in enumerate(images):
                        logger.info(f"[PDF解析] OCR识别第{i+1}/{len(images)}页...")
                        page_text = pytesseract.image_to_string(img, lang='chi_sim')
                        ocr_text += f"## 第{i+1}页\n\n{page_text}\n\n"

                    logger.info(f"[PDF解析] OCR识别完成，总文本长度: {len(ocr_text)}")

                    return {
                        "success": True,
                        "markdown_content": ocr_text,
                        "metadata": {
                            "file_type": "pdf",
                            "processing_method": "tesseract_ocr",
                            "char_count": len(ocr_text),
                            "pages": len(images),
                            "processing_time": datetime.now().isoformat()
                        }
                    }

                except Exception as e:
                    logger.error(f"[PDF解析] pdfplumber / OCR 方案失败: {str(e)}")
                    # 降级到MinerU（如果可用）
                    logger.info(f"[PDF解析] 尝试降级到MinerU...")

                # 降级方案：尝试MinerU（如果上述方案都失败）
                try:
                    from app.shared.parsers.file_parse import MineruParser

                    parser = MineruParser()

                    if not parser.check_installation():
                        logger.warning("MinerU未正确安装")
                        raise Exception("MinerU不可用")

                    # 创建临时输出目录
                    with tempfile.TemporaryDirectory() as temp_output_dir:
                        # 解析PDF文件
                        logger.info(f"[PDF解析] 开始解析: {doc_path}, 输出目录: {temp_output_dir}")
                        # 使用auto模式，MinerU会自动检测是否需要OCR
                        # 对于中文文档，指定lang='ch'可以提高OCR准确率
                        content_list = parser.parse_pdf(
                            pdf_path=doc_path,
                            output_dir=temp_output_dir,
                            method="auto",
                            lang="ch"  # 指定中文，提高OCR准确率（MinerU使用'ch'而非'zh'）
                        )

                        logger.info(f"[PDF解析] content_list长度: {len(content_list)}")
                        if content_list:
                            logger.info(f"[PDF解析] 前3个块类型: {[item.get('type') for item in content_list[:3]]}")

                        # 读取生成的Markdown文件
                        pdf_stem = Path(doc_path).stem
                        md_file = Path(temp_output_dir) / pdf_stem / "auto" / f"{pdf_stem}.md"

                        logger.info(f"[PDF解析] 查找Markdown文件: {md_file}, 存在: {md_file.exists()}")

                        if md_file.exists():
                            with open(md_file, 'r', encoding='utf-8') as f:
                                markdown_content = f.read()
                            logger.info(f"[PDF解析] 从md文件读取内容，长度: {len(markdown_content)}")
                        else:
                            # 从content_list生成Markdown
                            logger.warning(f"[PDF解析] Markdown文件不存在，从content_list生成")
                            markdown_content = self._generate_markdown_from_content_list(title, content_list)
                            logger.info(f"[PDF解析] 生成Markdown内容，长度: {len(markdown_content)}")

                        # 收集处理统计信息
                        stats = {
                            "total_blocks": len(content_list),
                            "text_blocks": sum(1 for item in content_list if item.get("type") == "text"),
                            "image_blocks": sum(1 for item in content_list if item.get("type") == "image"),
                            "table_blocks": sum(1 for item in content_list if item.get("type") == "table"),
                            "equation_blocks": sum(1 for item in content_list if item.get("type") == "equation")
                        }

                        return {
                            "success": True,
                            "markdown_content": markdown_content,
                            "metadata": {
                                "file_type": "pdf",
                                "processing_method": "mineru_parser",
                                "char_count": len(markdown_content),
                                "processing_time": datetime.now().isoformat(),
                                "content_stats": stats
                            }
                        }

                except Exception as e:
                    logger.error(f"MinerU PDF解析失败: {str(e)}")
                    # 降级策略1: pdfplumber提取文本（仅适用于文字版PDF）
                    try:
                        import pdfplumber

                        logger.info("[PDF降级] 尝试使用pdfplumber提取文本")
                        with pdfplumber.open(doc_path) as pdf:
                            text_content = ""
                            for page in pdf.pages:
                                page_text = page.extract_text() or ""
                                text_content += page_text
                                text_content += "\n\n"

                        bad_text_reason = _detect_bad_pdf_text_layer(text_content, min_chars=50)
                        if bad_text_reason is None:
                            markdown_content = f"# {title}\n\n{text_content.strip()}"
                            logger.info(f"[PDF降级] pdfplumber成功提取文本，长度: {len(text_content)}")

                            return {
                                "success": True,
                                "markdown_content": markdown_content,
                                "metadata": {
                                    "file_type": "pdf",
                                    "processing_method": "pdfplumber_fallback",
                                    "char_count": len(text_content),
                                    "processing_time": datetime.now().isoformat(),
                                    "note": f"MinerU解析失败，使用pdfplumber降级: {str(e)}"
                                }
                            }
                        logger.warning(
                            f"[PDF降级] pdfplumber文本层质量不合格({bad_text_reason})，可能是扫描版或字体映射异常PDF"
                        )
                        # 继续下一个降级策略
                        raise Exception(f"PDF文本层质量不合格: {bad_text_reason}")

                    except Exception as fallback_error:
                        logger.warning(f"[PDF降级] pdfplumber失败: {str(fallback_error)}")

                        # 降级策略2: 使用MinerU OCR模式（强制OCR）
                        try:
                            logger.info("[PDF降级] 尝试使用MinerU OCR模式")
                            from app.shared.parsers.file_parse import MineruParser

                            parser = MineruParser()
                            with tempfile.TemporaryDirectory() as temp_output_dir:
                                # 强制使用OCR模式，适合扫描版PDF
                                content_list = parser.parse_pdf(
                                    pdf_path=doc_path,
                                    output_dir=temp_output_dir,
                                    method="ocr",  # 强制OCR
                                    lang="ch"  # 指定中文语言（MinerU使用'ch'）
                                )

                                logger.info(f"[PDF降级] OCR模式content_list长度: {len(content_list)}")

                                pdf_stem = Path(doc_path).stem
                                md_file = Path(temp_output_dir) / pdf_stem / "ocr" / f"{pdf_stem}.md"

                                if md_file.exists():
                                    with open(md_file, 'r', encoding='utf-8') as f:
                                        markdown_content = f.read()
                                    logger.info(f"[PDF降级] OCR成功，内容长度: {len(markdown_content)}")
                                else:
                                    markdown_content = self._generate_markdown_from_content_list(title, content_list)
                                    logger.info(f"[PDF降级] 从OCR content_list生成，长度: {len(markdown_content)}")

                                # 检查OCR结果
                                if len(markdown_content.strip()) > 50:
                                    return {
                                        "success": True,
                                        "markdown_content": markdown_content,
                                        "metadata": {
                                            "file_type": "pdf",
                                            "processing_method": "mineru_ocr_fallback",
                                            "char_count": len(markdown_content),
                                            "processing_time": datetime.now().isoformat(),
                                            "note": "使用MinerU OCR模式解析（扫描版PDF）"
                                        }
                                    }
                                else:
                                    raise Exception("OCR提取内容仍然太少")

                        except Exception as ocr_error:
                            logger.error(f"[PDF降级] OCR模式也失败: {str(ocr_error)}")

                            # 最终降级：返回错误信息
                            markdown_content = f"""# {title}

## PDF解析失败

此PDF文档无法成功解析，可能的原因：

1. **扫描版PDF**：文档是扫描图片，需要OCR功能
2. **加密或受保护**：PDF文件有访问限制
3. **格式损坏**：PDF文件结构不完整
4. **OCR未安装**：服务器缺少OCR依赖

### 解决建议：

- 如果是扫描版，请转换为文字版PDF后重新上传
- 检查PDF是否有密码保护
- 尝试使用其他工具（如Adobe Acrobat）重新保存PDF
- 联系管理员检查MinerU和Tesseract OCR安装状态

### 技术详情：

- MinerU错误: {str(e)}
- pdfplumber错误: {str(fallback_error)}
- OCR错误: {str(ocr_error)}
"""

                            return {
                                "success": True,
                                "markdown_content": markdown_content,
                                "metadata": {
                                    "file_type": "pdf",
                                    "processing_method": "error_placeholder",
                                    "processing_time": datetime.now().isoformat(),
                                    "errors": {
                                        "mineru": str(e),
                                        "pdfplumber": str(fallback_error),
                                        "ocr": str(ocr_error)
                                    }
                                }
                            }

            elif file_ext in (".docx", ".doc"):
                # 优先使用 Docling（若安装），否则回退到快速解析器
                logger.info(f"开始解析Office文档: {title} ({file_ext})")
                try:
                    from app.shared.parsers.file_parse import DoclingParser
                    parser = DoclingParser()

                    if parser.check_installation():
                        # 使用 Docling 直接解析 Office 文档
                        with tempfile.TemporaryDirectory() as temp_output_dir:
                            content_list = parser.parse_office_doc(
                                doc_path=doc_path,
                                output_dir=temp_output_dir,
                            )

                            # 读取 Docling 生成的 Markdown 文件
                            stem = Path(doc_path).stem
                            md_file = Path(temp_output_dir) / stem / "docling" / f"{stem}.md"

                            if md_file.exists():
                                with open(md_file, 'r', encoding='utf-8') as f:
                                    markdown_content = f.read()
                            else:
                                # 若未生成md文件，则从内容块生成
                                markdown_content = self._generate_markdown_from_content_list(title, content_list)

                            stats = {
                                "total_blocks": len(content_list),
                                "text_blocks": sum(1 for item in content_list if isinstance(item, dict) and item.get("type") == "text"),
                                "image_blocks": sum(1 for item in content_list if isinstance(item, dict) and item.get("type") == "image"),
                                "table_blocks": sum(1 for item in content_list if isinstance(item, dict) and item.get("type") == "table"),
                            }

                            return {
                                "success": True,
                                "markdown_content": markdown_content,
                                "metadata": {
                                    "file_type": file_ext[1:],
                                    "processing_method": "docling_parser",
                                    "char_count": len(markdown_content),
                                    "processing_time": datetime.now().isoformat(),
                                    "content_stats": stats,
                                },
                            }
                    else:
                        logger.warning("Docling 未安装，回退到快速解析器 FileToMarkdown")
                except Exception as e:
                    logger.warning(f"Docling 解析失败或不可用，将回退到快速解析器: {e}")

                # 回退方案：使用快速解析器（基于 python-docx 等）
                try:
                    from app.shared.parsers.file_quckly_parse import FileToMarkdown
                    quick = FileToMarkdown()
                    # 使用正确的方法名 process_file
                    result = quick.process_file(doc_path)
                    markdown_content = result.get("content", "")
                    if not markdown_content:
                        raise ValueError("快速解析器未返回内容")

                    return {
                        "success": True,
                        "markdown_content": f"# {title}\n\n{markdown_content}",
                        "metadata": {
                            "file_type": file_ext[1:],
                            "processing_method": "quick_docx_parser",
                            "char_count": len(markdown_content),
                            "processing_time": datetime.now().isoformat(),
                        },
                    }
                except Exception as e:
                    logger.error(f"快速解析器处理{file_ext}失败: {e}")
                    # 最终回退：占位提示，避免中断流程
                    markdown_content = f"# {title}\n\n无法完整解析{file_ext}文档（{str(e)}）。"
                    return {
                        "success": True,
                        "markdown_content": markdown_content,
                        "metadata": {
                            "file_type": file_ext[1:],
                            "processing_method": "error_placeholder",
                            "processing_time": datetime.now().isoformat(),
                            "error": str(e),
                        },
                    }

            else:
                # 其他格式降级处理
                logger.warning(f"文档格式{file_ext}暂未完全支持，使用占位符")
                markdown_content = f"# {title}\n\n文档格式{file_ext}的完整解析功能正在开发中。"

                return {
                    "success": True,
                    "markdown_content": markdown_content,
                    "metadata": {
                        "file_type": file_ext[1:],
                        "processing_method": "placeholder",
                        "processing_time": datetime.now().isoformat(),
                    },
                }

        except Exception as e:
            logger.error(f"文档转换失败: {str(e)}")
            return {"success": False, "error": f"文档转换失败: {str(e)}"}

    def _generate_markdown_from_content_list(self, title: str, content_list: List[Dict]) -> str:
        """从MinerU的content_list生成Markdown内容"""
        try:
            logger.info(f"[生成Markdown] 开始处理content_list, 共{len(content_list)}个块")
            markdown_lines = [f"# {title}\n"]

            text_count = 0
            image_count = 0
            table_count = 0

            for idx, item in enumerate(content_list):
                item_type = item.get("type", "")

                if item_type == "text":
                    # 文本内容
                    text = item.get("text", "").strip()
                    if text:
                        text_count += 1
                        logger.debug(f"[生成Markdown] 块{idx}: 文本, 长度={len(text)}")
                        markdown_lines.append(text)
                        markdown_lines.append("")
                    else:
                        logger.debug(f"[生成Markdown] 块{idx}: 文本块为空，跳过")

                elif item_type == "image":
                    # 图片内容
                    image_count += 1
                    img_path = item.get("img_path", "")
                    caption = item.get("image_caption", "")
                    logger.debug(f"[生成Markdown] 块{idx}: 图片, path={img_path[:50] if img_path else 'None'}")
                    if img_path:
                        markdown_lines.append(f"![{caption}]({img_path})")
                        if caption:
                            markdown_lines.append(f"*{caption}*")
                        markdown_lines.append("")

                elif item_type == "table":
                    table_count += 1
                    logger.debug(f"[生成Markdown] 块{idx}: 表格")
                    # 表格内容
                    table_caption = item.get("table_caption", "")
                    table_body = item.get("table_body", [])

                    if table_caption:
                        markdown_lines.append(f"## {table_caption}")
                        markdown_lines.append("")

                    if table_body and isinstance(table_body, list) and len(table_body) > 0:
                        # 生成Markdown表格
                        if len(table_body) > 0:
                            # 表头
                            headers = table_body[0] if isinstance(table_body[0], list) else [str(table_body[0])]
                            markdown_lines.append("|" + "|".join(str(cell) for cell in headers) + "|")
                            markdown_lines.append("|" + "|".join("---" for _ in headers) + "|")

                            # 表格行
                            for row in table_body[1:]:
                                if isinstance(row, list):
                                    markdown_lines.append("|" + "|".join(str(cell) for cell in row) + "|")
                                else:
                                    markdown_lines.append(f"|{str(row)}|")

                        markdown_lines.append("")

                elif item_type == "equation":
                    # 公式内容
                    equation_text = item.get("text", "")
                    logger.debug(f"[生成Markdown] 块{idx}: 公式, 长度={len(equation_text) if equation_text else 0}")
                    if equation_text:
                        markdown_lines.append(f"$$\n{equation_text}\n$$")
                        markdown_lines.append("")
                else:
                    logger.warning(f"[生成Markdown] 块{idx}: 未知类型={item_type}")

            result = "\n".join(markdown_lines)
            logger.info(f"[生成Markdown] 完成: 文本块={text_count}, 图片={image_count}, 表格={table_count}, 总长度={len(result)}")
            return result

        except Exception as e:
            logger.error(f"从content_list生成Markdown失败: {str(e)}")
            return f"# {title}\n\nMarkdown生成失败: {str(e)}"


    def convert_audio_to_markdown(self, audio_path: str, **kwargs) -> Dict[str, Any]:
        """
        音频文件转Markdown
        使用语音识别将音频转录为文本

        Args:
            audio_path: 音频文件路径
            **kwargs: 额外参数（如title）

        Returns:
            转换结果字典
        """
        try:
            logger.info(f"开始处理音频文件: {audio_path}")

            # 基本信息
            audio_file = Path(audio_path)
            title = kwargs.get('title') or audio_file.stem
            file_size_mb = audio_file.stat().st_size / (1024 * 1024)

            # 获取音频格式和时长
            audio_info = self.media_processor.get_audio_info(str(audio_file))
            duration = audio_info.get('duration', 0) if audio_info else 0
            format_name = audio_info.get('format_name', 'unknown') if audio_info else 'unknown'

            # 使用Paraformer进行语音识别（同步运行异步方法）
            logger.info("开始语音识别...")
            try:
                transcriber = self.paraformer_transcriber
            except Exception as exc:
                raise _build_optional_dependency_error(
                    "音频转写",
                    "requirements-full.txt",
                    "librosa / 语音识别依赖",
                ) from exc

            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                transcription_result = loop.run_until_complete(
                    transcriber.transcribe_audio_file(str(audio_file))
                )
            finally:
                loop.close()

            # 构建Markdown内容
            markdown_lines = [
                f"# {title}",
                "",
                "## 音频信息",
                f"- **文件格式**: {audio_file.suffix[1:].upper()}",
                f"- **文件大小**: {file_size_mb:.2f} MB",
                f"- **音频时长**: {self._format_duration(duration)}",
                f"- **音频格式**: {format_name}",
                ""
            ]

            # 添加转录内容
            if transcription_result and transcription_result.get('success'):
                text = transcription_result.get('full_transcript', '')
                if text:
                    markdown_lines.extend([
                        "## 语音识别内容",
                        "",
                        text,
                        ""
                    ])

                    # 如果有时间戳信息，添加时间轴
                    segments = transcription_result.get('segments', [])
                    if segments:
                        markdown_lines.extend([
                            "## 时间轴",
                            ""
                        ])
                        for segment in segments:
                            start_time = segment.get('start_time', 0)
                            end_time = segment.get('end_time', 0)
                            text = segment.get('text', '')
                            markdown_lines.append(
                                f"- **[{self._format_duration(start_time)} - {self._format_duration(end_time)}]**: {text}"
                            )
                        markdown_lines.append("")
                else:
                    markdown_lines.extend([
                        "## 语音识别结果",
                        "",
                        "*未检测到可识别的语音内容*",
                        ""
                    ])
            else:
                # 语音识别失败或不可用
                error_msg = transcription_result.get('error', '语音识别服务暂时不可用') if transcription_result else '语音识别服务暂时不可用'
                markdown_lines.extend([
                    "## 语音识别结果",
                    "",
                    f"*{error_msg}*",
                    ""
                ])

            # 添加元数据
            markdown_lines.extend([
                "## 元数据",
                "",
                "```json",
                json.dumps({
                    "type": "audio",
                    "file_name": audio_file.name,
                    "file_size_bytes": audio_file.stat().st_size,
                    "duration_seconds": duration,
                    "format": format_name,
                    "transcription_available": bool(transcription_result and transcription_result.get('success')),
                    "processing_time": datetime.now().isoformat()
                }, ensure_ascii=False, indent=2),
                "```"
            ])

            markdown_content = "\n".join(markdown_lines)

            return {
                "success": True,
                "markdown_content": markdown_content,
                "metadata": {
                    "type": "audio",
                    "title": title,
                    "duration": duration,
                    "has_transcription": bool(transcription_result and transcription_result.get('success')),
                    "file_size": audio_file.stat().st_size
                }
            }

        except Exception as e:
            logger.error(f"音频转换失败: {e}")

            # 返回基础信息
            audio_file = Path(audio_path)
            title = kwargs.get('title') or audio_file.stem

            markdown_content = f"""# {title}

## 音频文件

- **文件名**: {audio_file.name}
- **文件格式**: {audio_file.suffix[1:].upper()}
- **文件大小**: {audio_file.stat().st_size / (1024 * 1024):.2f} MB

## 处理状态

*音频处理遇到错误: {str(e)}*

请确保音频文件格式正确并且未损坏。
"""

            return {
                "success": False,
                "markdown_content": markdown_content,
                "error": str(e),
                "metadata": {
                    "type": "audio",
                    "title": title,
                    "error": True
                }
            }

    def convert_image_to_markdown(self, image_path: str, **kwargs) -> Dict[str, Any]:
        """图片转Markdown - 使用VLM真实分析
        注意：本方法为同步方法，供线程池调用。
        """
        try:
            # from app.core.agents.template_agent.vlm_detect.simple_vlm_agent import SimpleVLMAgent
            # 使用上面定义的占位符类

            logger.info(f"开始处理图片: {image_path}")

            # 初始化VLM智能体（强制 JSON 输出）
            vlm_agent = SimpleVLMAgent(
                system_instruction=(
                    "你是一个严格遵循指令的图像分析助手。"
                    "所有回答必须是单个 JSON 对象，且不包含任何额外文字、解释、Markdown 围栏或注释。"
                    "如无法识别，输出 {\"events\": []}。"
                ),
                max_images_per_batch=1
            )

            # 使用兼容接口进行单图分析（返回JSON字典）
            vlm_error: Optional[str] = None
            try:
                # 严格 JSON 输出的用户提示 - 改进版，确保始终有描述
                user_query = (
                    "分析图片并输出JSON格式的结果。"
                    "输出格式：{\"events\": [{\"type\": \"scene|object|text|content\", \"description\": \"描述内容\"}]}"
                    "要求："
                    "1. 必须输出纯JSON，不要任何额外文本"
                    "2. 始终描述你看到的内容，即使是简单图片也要说明"
                    "3. 如果没有特殊事件，使用type='content'描述整体内容"
                    "4. 确保events数组至少有一个描述"
                )
                analysis = vlm_agent.run_batch_check(
                    images_or_dir=image_path,
                    user_query=user_query
                )
                try:
                    # 打印部分分析结果，便于排查模型输出
                    if isinstance(analysis, dict):
                        evs = analysis.get('events', [])
                        logger.info(f"[UMC] 单图VLM结果: events_count={len(evs)}, keys={list(analysis.keys())}")
                    else:
                        logger.info(f"[UMC] 单图VLM结果(非字典): type={type(analysis)}, head={str(analysis)[:120]}")
                except Exception:
                    pass
            except Exception as vlm_error:
                logger.warning(f"[UMC] VLM分析失败，使用备用描述: {str(vlm_error)}")
                vlm_error = str(vlm_error)
                # 如果VLM分析失败，提供基本的图片信息
                analysis = {
                    "error": str(vlm_error),
                    "fallback_description": f"图片文件: {Path(image_path).name}"
                }

            # 提取文本描述
            if isinstance(analysis, dict):
                # 检查是否有错误信息
                if 'error' in analysis:
                    if 'fallback_description' in analysis:
                        image_description = analysis['fallback_description']
                    else:
                        image_description = f"图片分析失败: {analysis.get('error', '未知错误')}"
                elif 'analysis' in analysis and isinstance(analysis['analysis'], str):
                    image_description = analysis['analysis']
                elif 'result' in analysis:
                    image_description = str(analysis['result'])
                elif 'events' in analysis and isinstance(analysis.get('events'), list):
                    descriptions = []
                    for e in analysis['events']:
                        if isinstance(e, dict):
                            desc = e.get('description') or e.get('summary')
                            if isinstance(desc, str) and desc.strip():
                                descriptions.append(desc.strip())
                    # 如果没有提取到有效描述，提供基本信息
                    if descriptions:
                        image_description = "\n\n".join(descriptions)
                    else:
                        image_description = f"图片: {Path(image_path).name}\n(VLM未返回详细描述)"
                else:
                    # 如果字典中没有可识别的字段，尝试将其转为字符串
                    image_description = json.dumps(analysis, ensure_ascii=False, indent=2)
            else:
                image_description = str(analysis) if analysis else f"图片: {Path(image_path).name}"

            # 获取服务器的基础URL
            base_url = (os.getenv("SERVICE_BASE_URL") or "").strip().rstrip("/")
            base_prefix = base_url if base_url else ""

            # 生成图片的外网访问URL
            # 根据图片路径判断使用哪个路由
            image_filename = Path(image_path).name
            if "uploads" in str(image_path):
                image_url = f"{base_prefix}/uploads/{image_filename}"
            else:
                # 默认使用uploads路由
                image_url = f"{base_prefix}/uploads/{image_filename}"

            # 生成Markdown内容
#             markdown_content = f"""# 图片内容分析

# ## 图片预览
# ![{Path(image_path).stem}]({image_url})

# ## 图片信息
# - **文件名**: {Path(image_path).name}
# - **路径**: {image_path}
# - **大小**: {Path(image_path).stat().st_size} 字节
# - **访问链接**: {image_url}

# ## 内容描述
# {image_description}

# ## 元数据
# - **类型**: 图片文件
# - **格式**: {Path(image_path).suffix.upper()}
# - **处理时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# """
            markdown_content = f"""{image_description}
                        """
            logger.info(f"图片转换完成: {image_path}")

            # 补充元数据中的VLM诊断信息（如有）
            meta: Dict[str, Any] = {
                'type': 'image',
                'file_path': str(image_path),  # 转为字符串避免JSON序列化错误
                'description': image_description,
                'processed_at': datetime.now().isoformat()
            }
            # 如果analysis中自带错误，或前面捕获到异常，则写入vlm_error
            if isinstance(analysis, dict) and analysis.get('error'):
                meta['vlm_error'] = str(analysis.get('error'))
            if vlm_error:
                meta['vlm_error'] = vlm_error
            # 如果包含事件数量，便于前端展示
            try:
                if isinstance(analysis, dict) and isinstance(analysis.get('events'), list):
                    meta['vlm_events_count'] = len(analysis['events'])
                    # 若VLM返回空事件，视为降级（无有效识别结果）
                    if meta['vlm_events_count'] == 0 and 'vlm_error' not in meta:
                        meta['vlm_fallback'] = True
                        meta['vlm_error'] = 'VLM返回空结果'
            except Exception:
                pass

            return {
                'success': True,
                'markdown_content': markdown_content,
                'metadata': meta
            }

        except Exception as e:
            # 不要让图片转换失败阻断整个上传流程；回退到最小可用的Markdown
            logger.error(f"图片转换失败，降级为占位描述: {str(e)}")
            try:
                fname = Path(image_path).name if image_path else "unknown"
            except Exception:
                fname = "unknown"
            fallback_md = f"""# 图片内容分析（降级）

无法使用VLM生成详细描述，已降级为基本信息。

- 文件名: {fname}
- 处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

提示: {str(e)}
"""
            return {
                "success": True,
                "markdown_content": fallback_md,
                "metadata": {
                    "type": "image",
                    "file_path": str(image_path),
                    "fallback": True,
                    "error": str(e)
                }
            }

    async def convert_to_markdown(self, file_path: str, file_type: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """统一入口：根据文件类型分发到对应的转换方法。
        - video: 走异步视频处理
        - image: 在线程池中执行同步的图片转换
        - 其他文档: 在线程池中执行同步的文档转换
        """
        try:
            p = Path(file_path)
            ft = (file_type or p.suffix.lstrip('.')).lower()
            title = kwargs.get('title') or p.stem
            # 输出目录（对视频需要）
            output_dir = kwargs.get('output_dir') or str((p.parent / f"converted_{uuid.uuid4().hex[:8]}").resolve())
            logger.info(f"[UMC] convert_to_markdown: path={p}, type={ft}, title={title}")

            if ft in {"mp4", "avi", "mov", "mkv", "webm"}:
                logger.info(f"[UMC] 分支=video, output_dir={output_dir}")
                return await self.convert_video_to_markdown(str(p), output_dir, title=title, enable_audio=True)
            elif ft in {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff"}:
                # 在线程池中运行同步图片处理，避免阻塞
                logger.info("[UMC] 分支=image (thread)")
                return await asyncio.to_thread(self.convert_image_to_markdown, str(p), title=title)
            else:
                # 文档类
                loop = asyncio.get_event_loop()
                logger.info("[UMC] 分支=document (executor)")
                return await loop.run_in_executor(None, functools.partial(self.convert_document_to_markdown, title=title), str(p))
        except Exception as e:
            logger.error(f"统一转换入口失败: {str(e)}")
            return {"success": False, "error": f"转换失败: {str(e)}"}

# 工具函数
def convert_video_to_markdown(video_path: str, output_dir: str, **kwargs) -> Dict[str, Any]:
    """便捷函数：视频转Markdown"""
    converter = UnifiedMarkdownConverter()
    return converter.convert_video_to_markdown(video_path, output_dir, **kwargs)

if __name__ == "__main__":
    # 测试示例
    converter = UnifiedMarkdownConverter()

    test_video = "test_video.mp4"
    if os.path.exists(test_video):
        result = converter.convert_video_to_markdown(
            video_path=test_video,
            output_dir="./test_output",
            title="测试视频",
            enable_audio=False  # 暂时禁用音频处理
        )

        if result['success']:
            logger.info(f"转换成功！Markdown文件: {result['markdown_file']}")
            logger.info(f"元数据: {result['metadata']}")
        else:
            logger.info(f"转换失败: {result['error']}")
    else:
        logger.debug("使用简单处理方法")
        logger.debug("跳过转换")
