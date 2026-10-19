#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音视频预处理器 - FFmpeg封装
支持视频统一格式转换和音频优化处理
"""

import os
import subprocess
import shutil
import json
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
import tempfile

try:
    import ffmpeg
    FFMPEG_PYTHON_AVAILABLE = True
except ImportError:
    FFMPEG_PYTHON_AVAILABLE = False

try:
    import imageio_ffmpeg
    IMAGEIO_FFMPEG_AVAILABLE = True
except ImportError:
    IMAGEIO_FFMPEG_AVAILABLE = False

from app.shared.utils.logger_util import get_logger

logger = get_logger("MediaProcessor")

@dataclass
class VideoConfig:
    """视频配置"""
    container: str = "mp4"
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    video_bitrate: str = "2000k"
    audio_bitrate: str = "128k"
    resolution: str = "1280x720"
    fps: int = 30
    crf: int = 23  # 质量控制，18-28范围，越小质量越好

@dataclass
class AudioConfig:
    """音频配置"""
    format: str = "wav"
    codec: str = "pcm_s16le"
    sample_rate: int = 16000
    channels: int = 1
    bitrate: str = "256k"

class MediaProcessor:
    """媒体文件处理器"""

    @staticmethod
    def _safe_parse_fps(fps_str: str) -> float:
        """
        安全解析FPS字符串

        Args:
            fps_str: FPS字符串，格式如 "30/1" 或 "30"

        Returns:
            解析后的FPS值，解析失败返回0.0
        """
        try:
            if not fps_str or fps_str == '0/0':
                return 0.0

            if '/' in fps_str:
                parts = fps_str.split('/')
                if len(parts) == 2:
                    numerator = float(parts[0])
                    denominator = float(parts[1])
                    if denominator != 0:
                        return numerator / denominator
                return 0.0

            return float(fps_str)
        except (ValueError, ZeroDivisionError, AttributeError):
            logger.warning(f"无法解析FPS值: {fps_str}")
            return 0.0

    def __init__(self, check_ffmpeg: bool = True):
        # 检查FFmpeg可用性（可选）
        if check_ffmpeg and not self._check_ffmpeg():
            logger.warning(
                "ffmpeg not available. Video processing will be disabled.\n"
                "Either install ffmpeg system binary or use ffmpeg-python.\n"
                "macOS: brew install ffmpeg\n"
                "Ubuntu: sudo apt-get install ffmpeg\n"
                "CentOS: sudo yum install ffmpeg\n"
                "Or ensure ffmpeg-python is working properly."
            )
            self._ffmpeg_available = False
        else:
            self._ffmpeg_available = True
            logger.info("FFmpeg检查通过")

    def _check_ffmpeg(self) -> bool:
        """检查FFmpeg是否可用"""

        # 首先检查imageio-ffmpeg（包含FFmpeg二进制文件）
        if IMAGEIO_FFMPEG_AVAILABLE:
            try:
                import imageio_ffmpeg
                ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                # 测试FFmpeg是否工作
                result = subprocess.run([ffmpeg_exe, '-version'],
                                      capture_output=True, text=True, check=True)
                logger.info(f"imageio-ffmpeg可用，版本: {result.stdout.split()[2]}")
                return True
            except Exception as e:
                logger.warning(f"imageio-ffmpeg不可用: {e}")

        # 检查ffmpeg-python库
        if FFMPEG_PYTHON_AVAILABLE:
            try:
                # 测试ffmpeg-python是否工作
                import ffmpeg
                # 尝试简单的版本查询而不是probe一个无效文件
                ffmpeg_version = ffmpeg.version.ffmpeg_version
                logger.info(f"ffmpeg-python库可用，FFmpeg版本: {ffmpeg_version}")
                return True
            except Exception as e:
                logger.warning(f"ffmpeg-python库不可用: {e}")

        # 降级到系统FFmpeg命令
        try:
            result = subprocess.run(['ffmpeg', '-version'],
                                  capture_output=True, text=True, check=True)
            version_info = result.stdout.split('\n')[0] if result.stdout else "未知版本"
            logger.info(f"系统FFmpeg可用: {version_info}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"系统FFmpeg命令不可用: {e}")
            return False

    def get_media_info(self, input_path: str) -> Dict[str, Any]:
        """获取媒体文件信息"""

        # 尝试使用imageio-ffmpeg
        if IMAGEIO_FFMPEG_AVAILABLE:
            try:
                import imageio_ffmpeg
                ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                # 构造ffprobe路径 - imageio-ffmpeg只提供ffmpeg，我们需要用它来获取信息

                result = subprocess.run([
                    ffmpeg_exe, '-i', input_path,
                    '-v', 'quiet',
                    '-print_format', 'json',
                    '-show_format', '-show_streams',
                    '-f', 'null', '-'
                ], capture_output=True, text=True)

                # imageio-ffmpeg的ffmpeg可能不支持-print_format，我们用另一种方式
                if result.returncode != 0:
                    # 使用ffmpeg -i 来获取基本信息
                    result = subprocess.run([
                        ffmpeg_exe, '-i', input_path
                    ], capture_output=True, text=True)

                    # 从stderr解析信息（ffmpeg把信息输出到stderr）
                    stderr_text = result.stderr

                    # 简单解析视频信息
                    duration = 0
                    width = 1280
                    height = 720
                    fps = 30

                    # 解析Duration
                    if 'Duration:' in stderr_text:
                        duration_line = [line for line in stderr_text.split('\n') if 'Duration:' in line][0]
                        duration_str = duration_line.split('Duration:')[1].split(',')[0].strip()
                        # 转换 HH:MM:SS.ms 为秒
                        parts = duration_str.split(':')
                        if len(parts) == 3:
                            duration = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])

                    # 解析分辨率
                    for line in stderr_text.split('\n'):
                        if 'Video:' in line and 'x' in line:
                            # 查找分辨率模式如 "1920x1080"
                            # 注意：ffmpeg 输出常包含 "avc1 / 0x31637661" 这类 codec tag，
                            # 其中 "0x31637661" 会被朴素的 (\d+)x(\d+) 误判为分辨率。
                            import re
                            for w_str, h_str in re.findall(r'(\d{1,5})x(\d{1,5})', line):
                                try:
                                    w = int(w_str)
                                    h = int(h_str)
                                except Exception:
                                    continue
                                # 过滤掉明显不合理的值（比如 0x31637661）
                                if 16 <= w <= 10000 and 16 <= h <= 10000:
                                    width = w
                                    height = h
                                    break

                            # 查找fps
                            fps_match = re.search(r'(\d+(?:\.\d+)?)\s*fps', line)
                            if fps_match:
                                fps = float(fps_match.group(1))

                    file_size = os.path.getsize(input_path)

                    return {
                        'duration': duration,
                        'size': file_size,
                        'video': {
                            'codec': 'h264',  # 假设
                            'width': width,
                            'height': height,
                            'fps': fps,
                            'bitrate': 0
                        },
                        'audio': {
                            'codec': 'aac',  # 假设
                            'sample_rate': 48000,
                            'channels': 2,
                            'bitrate': 0
                        }
                    }
                else:
                    # 如果支持JSON输出，解析JSON
                    info = json.loads(result.stdout)

                    # 提取关键信息
                    video_stream = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
                    audio_stream = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)

                    return {
                        'duration': float(info['format'].get('duration', 0)),
                        'size': int(info['format'].get('size', 0)),
                        'video': {
                            'codec': video_stream.get('codec_name') if video_stream else None,
                            'width': int(video_stream.get('width', 0)) if video_stream else 0,
                            'height': int(video_stream.get('height', 0)) if video_stream else 0,
                            'fps': self._safe_parse_fps(video_stream.get('r_frame_rate', '0/1')) if video_stream else 0,
                            'bitrate': int(video_stream.get('bit_rate', 0)) if video_stream else 0
                        },
                        'audio': {
                            'codec': audio_stream.get('codec_name') if audio_stream else None,
                            'sample_rate': int(audio_stream.get('sample_rate', 0)) if audio_stream else 0,
                            'channels': int(audio_stream.get('channels', 0)) if audio_stream else 0,
                            'bitrate': int(audio_stream.get('bit_rate', 0)) if audio_stream else 0
                        }
                    }

            except Exception as e:
                logger.warning(f"imageio-ffmpeg获取媒体信息失败: {e}，尝试其他方式")

        # 尝试使用ffmpeg-python库
        if FFMPEG_PYTHON_AVAILABLE:
            try:
                import ffmpeg
                probe = ffmpeg.probe(input_path)

                # 提取关键信息
                video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
                audio_stream = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)

                return {
                    'duration': float(probe['format'].get('duration', 0)),
                    'size': int(probe['format'].get('size', 0)),
                    'video': {
                        'codec': video_stream.get('codec_name') if video_stream else None,
                        'width': int(video_stream.get('width', 0)) if video_stream else 0,
                        'height': int(video_stream.get('height', 0)) if video_stream else 0,
                        'fps': eval(video_stream.get('r_frame_rate', '0/1')) if video_stream else 0,
                        'bitrate': int(video_stream.get('bit_rate', 0)) if video_stream else 0
                    },
                    'audio': {
                        'codec': audio_stream.get('codec_name') if audio_stream else None,
                        'sample_rate': int(audio_stream.get('sample_rate', 0)) if audio_stream else 0,
                        'channels': int(audio_stream.get('channels', 0)) if audio_stream else 0,
                        'bitrate': int(audio_stream.get('bit_rate', 0)) if audio_stream else 0
                    }
                }
            except Exception as e:
                logger.warning(f"ffmpeg-python获取媒体信息失败: {e}，尝试ffprobe命令")

        # 降级到命令行ffprobe
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_format', '-show_streams',
            input_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)

            # 提取关键信息
            video_stream = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
            audio_stream = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)

            return {
                'duration': float(info['format'].get('duration', 0)),
                'size': int(info['format'].get('size', 0)),
                'video': {
                    'codec': video_stream.get('codec_name') if video_stream else None,
                    'width': int(video_stream.get('width', 0)) if video_stream else 0,
                    'height': int(video_stream.get('height', 0)) if video_stream else 0,
                    'fps': eval(video_stream.get('r_frame_rate', '0/1')) if video_stream else 0,
                    'bitrate': int(video_stream.get('bit_rate', 0)) if video_stream else 0
                },
                'audio': {
                    'codec': audio_stream.get('codec_name') if audio_stream else None,
                    'sample_rate': int(audio_stream.get('sample_rate', 0)) if audio_stream else 0,
                    'channels': int(audio_stream.get('channels', 0)) if audio_stream else 0,
                    'bitrate': int(audio_stream.get('bit_rate', 0)) if audio_stream else 0
                }
            }
        except FileNotFoundError:
            logger.error("ffprobe not found. Video processing will be disabled.")
            # 返回基于文件大小的默认信息
            file_size = os.path.getsize(input_path)
            return {
                'duration': 60,  # 默认1分钟
                'size': file_size,
                'video': {
                    'codec': 'unknown',
                    'width': 1280,
                    'height': 720,
                    'fps': 30,
                    'bitrate': 0
                },
                'audio': {
                    'codec': 'unknown',
                    'sample_rate': 0,
                    'channels': 0,
                    'bitrate': 0
                }
            }
        except Exception as e:
            logger.error(f"获取媒体信息失败: {e}")
            raise

    def standardize_video(self, input_path: str, output_path: str,
                         config: Optional[VideoConfig] = None) -> bool:
        """
        视频标准化处理
        - 统一格式为MP4 H.264+AAC
        - 标准化分辨率和比特率
        - 优化文件大小和兼容性
        """
        if not self._ffmpeg_available:
            logger.warning("FFmpeg不可用，跳过视频标准化处理")
            # 如果输入输出路径不同，复制文件
            if input_path != output_path:
                import shutil
                shutil.copy2(input_path, output_path)
            return True

        config = config or VideoConfig()

        try:
            # 获取原始信息
            media_info = self.get_media_info(input_path)
            logger.info(f"原始视频信息: {media_info}")

            # 尝试使用imageio-ffmpeg
            if IMAGEIO_FFMPEG_AVAILABLE:
                try:
                    import imageio_ffmpeg
                    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

                    cmd = [
                        ffmpeg_exe, '-i', str(input_path),

                        # 视频编码设置
                        '-c:v', config.video_codec,
                        '-crf', str(config.crf),          # 质量控制
                        '-preset', 'medium',              # 编码速度vs质量平衡
                        '-vf', f'scale={config.resolution}',  # 分辨率调整
                        '-r', str(config.fps),            # 帧率

                        # 音频编码设置
                        '-c:a', config.audio_codec,
                        '-b:a', config.audio_bitrate,
                        '-ar', '48000',                   # 音频采样率
                        '-ac', '2',                       # 立体声

                        # 输出设置
                        '-f', config.container,
                        '-movflags', '+faststart',        # 优化网络播放
                        '-y',                            # 覆盖输出文件
                        str(output_path)
                    ]

                    logger.info(f"使用imageio-ffmpeg进行视频标准化处理")
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

                    # 验证输出文件
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        new_info = self.get_media_info(str(output_path))
                        logger.info(f"处理完成，新文件信息: {new_info}")
                        return True
                    else:
                        logger.error("输出文件创建失败")
                        return False

                except Exception as e:
                    logger.warning(f"imageio-ffmpeg视频处理失败: {e}，尝试其他方式")

            # 降级到系统FFmpeg命令
            cmd = [
                'ffmpeg', '-i', str(input_path),

                # 视频编码设置
                '-c:v', config.video_codec,
                '-crf', str(config.crf),          # 质量控制
                '-preset', 'medium',              # 编码速度vs质量平衡
                '-vf', f'scale={config.resolution}',  # 分辨率调整
                '-r', str(config.fps),            # 帧率

                # 音频编码设置
                '-c:a', config.audio_codec,
                '-b:a', config.audio_bitrate,
                '-ar', '48000',                   # 音频采样率
                '-ac', '2',                       # 立体声

                # 输出设置
                '-f', config.container,
                '-movflags', '+faststart',        # 优化网络播放
                '-y',                            # 覆盖输出文件
                str(output_path)
            ]

            logger.info(f"开始视频标准化处理: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # 验证输出文件
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                new_info = self.get_media_info(output_path)
                logger.info(f"处理完成，新文件信息: {new_info}")
                return True
            else:
                logger.error("输出文件创建失败")
                return False

        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg视频标准化失败: {e.stderr}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return False
        except Exception as e:
            logger.error(f"视频标准化处理异常: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return False

    def extract_audio_for_asr(
    self,
    input_path: str,
    output_path: str,
    config: Optional[AudioConfig] = None
    ) -> bool:
        """
        为 ASR 优化的音频提取
        - 统一导出 16kHz / Mono / WAV / PCM（如 Paraformer 要求）
        - 成功返回 True；无音轨或任意提取失败返回 False
        """
        import os
        import subprocess
        import logging

        logger = logging.getLogger(__name__)

        config = config or AudioConfig()

        # 0) 前置：FFmpeg 可用性（系统级或 imageio-ffmpeg）
        ffmpeg_methods: list[str] = []

        # 检查 ffmpeg-python 的同时，确保系统 ffmpeg 命令可用
        try:
            if 'FFMPEG_PYTHON_AVAILABLE' in globals() and FFMPEG_PYTHON_AVAILABLE:
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
                ffmpeg_methods.append('ffmpeg-python')
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("系统 FFmpeg 不可用，跳过 ffmpeg-python 方法")

        # 检查 imageio-ffmpeg
        if 'IMAGEIO_FFMPEG_AVAILABLE' in globals() and IMAGEIO_FFMPEG_AVAILABLE:
            ffmpeg_methods.append('imageio-ffmpeg')

        if not ffmpeg_methods:
            logger.warning("没有可用的 FFmpeg 提取方法")
            return False

        # 1) 检查是否包含音频流
        try:
            media_info = self.get_media_info(input_path)
            audio_info = (media_info or {}).get('audio', {})
            if not audio_info or audio_info.get('codec') is None:
                logger.info("源视频不含音频流，返回 False")
                return False
        except Exception as e:
            # 如果连检测都失败，这里直接判失败，按照你的新契约不再“尝试”“兜底”
            logger.warning(f"检测音频流失败：{e}，返回 False")
            return False

        # 删除旧输出（避免误判上次残留）
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
        except Exception as e:
            logger.warning(f"清理旧输出失败：{e}")

        # 2) 依次尝试两条链路
        # 2.1 ffmpeg-python
        if 'ffmpeg-python' in ffmpeg_methods:
            try:
                import ffmpeg
                (
                    ffmpeg
                    .input(str(input_path))
                    .audio
                    .output(
                        str(output_path),
                        acodec=config.codec,      # e.g. pcm_s16le
                        ac=config.channels,       # 1
                        ar=config.sample_rate,    # 16000
                        format=config.format      # wav
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info("使用 ffmpeg-python 提取音频成功")
                    return True
                logger.error("ffmpeg-python 生成的音频文件无效（不存在或为空）")
            except Exception as e:
                logger.error(f"ffmpeg-python 提取失败：{e}")

        # 2.2 imageio-ffmpeg
        if 'imageio-ffmpeg' in ffmpeg_methods:
            try:
                import imageio_ffmpeg
                ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

                cmd = [
                    ffmpeg_exe, '-hide_banner', '-y',
                    '-i', str(input_path),
                    '-vn',
                    '-c:a', str(config.codec),
                    '-ar', str(config.sample_rate),
                    '-ac', str(config.channels),
                    '-f', str(config.format),
                    str(output_path)
                ]
                logger.info("使用 imageio-ffmpeg 提取音频...")
                subprocess.run(cmd, capture_output=True, text=True, check=True)

                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info("imageio-ffmpeg 提取音频成功")
                    return True
                logger.error("imageio-ffmpeg 生成的音频文件无效（不存在或为空）")
            except subprocess.CalledProcessError as e:
                logger.error(f"imageio-ffmpeg 提取失败，退出码 {e.returncode}，stderr: {e.stderr}")
            except Exception as e:
                logger.error(f"imageio-ffmpeg 提取异常：{e}")

        # 全部失败
        logger.warning("所有音频提取方法均失败，返回 False")
        return False

    def extract_audio_segment(self, input_path: str, output_path: str,
                            start_time: float, duration: float,
                            config: Optional[AudioConfig] = None) -> bool:
        """
        提取音频片段（用于与关键帧时间轴对齐）
        """
        config = config or AudioConfig()

        try:
            cmd = [
                'ffmpeg', '-i', str(input_path),
                '-ss', str(start_time),          # 开始时间
                '-t', str(duration),             # 持续时间
                '-vn',                           # 禁用视频
                '-c:a', config.codec,
                '-ar', str(config.sample_rate),
                '-ac', str(config.channels),
                '-f', config.format,
                '-y',
                str(output_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0

        except Exception as e:
            logger.error(f"音频片段提取失败: {e}")
            return False

    def batch_process_video(self, input_path: str, output_dir: str) -> Dict[str, str]:
        """
        批量处理视频：同时生成标准化视频和ASR音频

        Returns:
            包含处理结果路径的字典
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        input_stem = Path(input_path).stem

        results = {
            'standardized_video': str(output_dir / f"{input_stem}_standard.mp4"),
            'asr_audio': str(output_dir / f"{input_stem}_asr.wav"),
            'success': False,
            'error': None
        }

        try:
            # 1. 视频标准化
            logger.info("开始视频标准化处理...")
            video_success = self.standardize_video(input_path, results['standardized_video'])
            if not video_success:
                results['error'] = "视频标准化处理失败"
                logger.error(f"视频标准化失败: {input_path} -> {results['standardized_video']}")
                return results

            # 2. ASR音频提取
            logger.info("开始ASR音频提取...")
            audio_success = self.extract_audio_for_asr(input_path, results['asr_audio'])

            # 修改策略：音频失败时仍然允许视频处理继续
            if not audio_success:
                # 视频本身没有音频流或提取失败
                logger.warning(f"视频无音频或提取失败")
                results['success'] = True  # 视频成功就算成功
                results['audio_warning'] = "音频提取失败，跳过语音识别，仅进行视觉分析"
                results['audio_available'] = False
            else:
                logger.info("音频提取成功")
                results['success'] = True
                results['audio_available'] = True

            logger.info(f"批量处理完成: {results}")

        except Exception as e:
            results['error'] = f"批量处理异常: {str(e)}"
            logger.error(f"批量处理异常: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")

        return results

# 工具函数
def get_video_duration(video_path: str) -> float:
    """获取视频时长（秒）"""
    processor = MediaProcessor()
    info = processor.get_media_info(video_path)
    return info.get('duration', 0)

def is_video_processable(video_path: str, max_duration: int = 7200) -> Tuple[bool, str]:
    """
    检查视频是否可处理

    Args:
        video_path: 视频路径
        max_duration: 最大时长（秒），默认2小时

    Returns:
        (是否可处理, 检查结果信息)
    """
    try:
        if not os.path.exists(video_path):
            return False, "视频文件不存在"

        # 检查文件大小（基础验证）
        file_size = os.path.getsize(video_path)
        if file_size == 0:
            return False, "视频文件为空"

        # 尝试获取视频信息
        try:
            processor = MediaProcessor()
            info = processor.get_media_info(video_path)

            duration = info.get('duration', 0)
            if duration > max_duration:
                return False, f"视频时长{duration:.1f}秒超过限制{max_duration}秒"

            if duration < 1:
                logger.warning("无法获取视频时长，使用默认检查")
                # 当无法获取时长时，基于文件大小进行粗略判断
                # 假设平均比特率1Mbps，计算估算时长
                estimated_duration = file_size * 8 / (1024 * 1024)  # 秒
                if estimated_duration > max_duration:
                    return False, f"估算视频时长过长"

            # 检查是否有视频流（如果可以获取的话）
            video_info = info.get('video', {})
            width = video_info.get('width', 0)

            # 对于.mov文件，即使width为0也可能是有效的视频（imageio-ffmpeg解析限制）
            file_ext = Path(video_path).suffix.lower()
            if width == 0 and duration > 1:
                if file_ext in {'.mov', '.mp4', '.avi', '.mkv', '.webm'}:
                    logger.warning(f"无法获取{file_ext}文件的详细视频信息，但文件格式支持，允许处理")
                else:
                    return False, "无效的视频流"

            return True, f"视频可处理，时长{duration:.1f}秒"

        except Exception as e:
            # FFmpeg/ffprobe 不可用时的降级处理
            logger.warning(f"无法获取视频详细信息: {e}，进行基础验证")

            # 基于文件大小的简单验证
            max_size = 200 * 1024 * 1024  # 200MB
            if file_size > max_size:
                return False, f"视频文件过大: {file_size / 1024 / 1024:.1f}MB > {max_size / 1024 / 1024}MB"

            # 基于文件扩展名验证
            video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'}
            file_ext = Path(video_path).suffix.lower()
            if file_ext not in video_extensions:
                return False, f"不支持的视频格式: {file_ext}"

            return True, f"基础验证通过，文件大小{file_size / 1024 / 1024:.1f}MB (注意：视频处理功能受限)"

    except Exception as e:
        logger.error(f"视频检查异常: {e}")
        return False, f"视频检查失败: {str(e)}"

if __name__ == "__main__":
    # 测试示例
    processor = MediaProcessor()

    # 示例：处理视频
    test_video = "test_video.mp4"
    if os.path.exists(test_video):
        # 检查可处理性
        processable, message = is_video_processable(test_video)
        logger.info(f"视频检查结果: {message}")

        if processable:
            # 批量处理
            results = processor.batch_process_video(test_video, "./processed_media")
            logger.info(f"处理结果: {results}")
    else:
        logger.debug("调试信息")
