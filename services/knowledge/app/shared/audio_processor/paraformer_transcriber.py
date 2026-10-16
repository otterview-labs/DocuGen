#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paraformer语音识别器

主路径统一为 OpenAI-compatible transcription；
本地 Paraformer/Whisper 作为可选回退链。
"""

from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
import numpy as np
from typing import List, Dict, Optional, Any, Tuple
import requests

from app.shared.utils.http_auth import (
    HTTPAuthConfig,
    apply_auth_headers,
    build_requests_auth,
    normalize_auth_mode,
)
from app.shared.utils.logger_util import get_logger

logger = get_logger("ParaformerTranscriber")

try:
    import librosa

    LIBROSA_AVAILABLE = True
except ImportError:
    librosa = None
    LIBROSA_AVAILABLE = False


def _resolve_audio_provider_from_env() -> str:
    raw = (os.getenv("AUDIO_TRANSCRIBE_PROVIDER") or "").strip().lower()
    if not raw:
        return "disabled"
    mapping = {
        "openai": "openai",
        "remote": "openai",
        "local": "local",
        "disabled": "disabled",
        "disable": "disabled",
        "none": "disabled",
        "off": "disabled",
        "false": "disabled",
        "0": "disabled",
    }
    return mapping.get(raw, "disabled")


def _normalize_openai_base_url(api_base: Optional[str]) -> str:
    if not api_base:
        return ""
    value = str(api_base).strip().rstrip("/")
    for suffix in ("/audio/transcriptions", "/v1/audio/transcriptions"):
        if value.endswith(suffix):
            value = value[: -len(suffix)].rstrip("/")
            break
    if not value.endswith("/v1"):
        value = f"{value}/v1"
    return value


@dataclass(frozen=True)
class AudioTranscriptionConfig:
    provider: str
    model_name: str
    api_base: Optional[str]
    auth_mode: str
    api_key: Optional[str]
    username: Optional[str]
    password: Optional[str]
    language: str = "zh"
    prompt: str = "请准确转录这段音频的内容"
    max_retries: int = 2
    timeout: int = 120

    @classmethod
    def from_env(cls) -> "AudioTranscriptionConfig":
        provider = _resolve_audio_provider_from_env()
        if provider == "local":
            fallback_base = os.getenv("LOCAL_LLM_ENDPOINT") or ""
            fallback_model = os.getenv("LOCAL_LLM_MODEL_NAME") or ""
            default_auth_mode = os.getenv("LOCAL_LLM_AUTH_MODE") or "none"
            fallback_api_key = os.getenv("LOCAL_LLM_API_KEY") or ""
            fallback_username = os.getenv("LOCAL_LLM_USERNAME") or ""
            fallback_password = os.getenv("LOCAL_LLM_PASSWORD") or ""
        else:
            fallback_base = os.getenv("OPENAI_API_BASE") or ""
            fallback_model = os.getenv("OPENAI_MODEL_NAME") or ""
            default_auth_mode = os.getenv("OPENAI_API_AUTH_MODE") or "bearer"
            fallback_api_key = os.getenv("OPENAI_API_KEY") or ""
            fallback_username = os.getenv("OPENAI_API_USERNAME") or ""
            fallback_password = os.getenv("OPENAI_API_PASSWORD") or ""

        return cls(
            provider=provider,
            model_name=(os.getenv("AUDIO_TRANSCRIBE_MODEL_NAME") or fallback_model or "whisper-1").strip(),
            api_base=(os.getenv("AUDIO_TRANSCRIBE_API_BASE") or fallback_base or "").strip() or None,
            auth_mode=normalize_auth_mode(
                os.getenv("AUDIO_TRANSCRIBE_AUTH_MODE") or default_auth_mode,
                default="none" if provider == "local" else "bearer",
            ),
            api_key=(os.getenv("AUDIO_TRANSCRIBE_API_KEY") or fallback_api_key or "").strip() or None,
            username=(os.getenv("AUDIO_TRANSCRIBE_USERNAME") or fallback_username or "").strip() or None,
            password=(os.getenv("AUDIO_TRANSCRIBE_PASSWORD") or fallback_password or "").strip() or None,
            language=(os.getenv("AUDIO_TRANSCRIBE_LANGUAGE") or "zh").strip() or "zh",
            prompt=(os.getenv("AUDIO_TRANSCRIBE_PROMPT") or "请准确转录这段音频的内容").strip(),
            max_retries=max(0, int((os.getenv("AUDIO_TRANSCRIBE_MAX_RETRIES") or "2").strip() or "2")),
            timeout=max(30, int((os.getenv("AUDIO_TRANSCRIBE_TIMEOUT") or "120").strip() or "120")),
        )

class ParaformerTranscriber:
    """Paraformer语音识别器"""

    def __init__(
        self,
        model_path: Optional[str] = None,
        lazy_load: bool = True,
        transcription_config: Optional[AudioTranscriptionConfig] = None,
    ):
        """
        初始化Paraformer转录器

        Args:
            model_path: 模型路径，默认使用ModelScope自动下载
            lazy_load: 是否延迟加载模型（首次使用时再加载）
        """
        # 确保环境变量已加载
        from dotenv import load_dotenv
        load_dotenv()

        self.model_path = model_path or "damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
        self.model = None
        self.pipeline = None
        self.lazy_load = lazy_load
        self._model_loaded = False
        self.transcription_config = transcription_config or AudioTranscriptionConfig.from_env()
        self._remote_auth_config = HTTPAuthConfig.build(
            mode=self.transcription_config.auth_mode,
            api_key=self.transcription_config.api_key,
            username=self.transcription_config.username,
            password=self.transcription_config.password,
            default_mode="none" if self.transcription_config.provider == "local" else "bearer",
        )

        if not LIBROSA_AVAILABLE:
            logger.info(
                "librosa未安装，音频转写链路保持可选关闭状态。"
                "如需启用，请安装: pip install -r requirements-full.txt"
            )

        # Paraformer配置
        self.config = {
            'sample_rate': 16000,
            'chunk_length': 10,      # 分段长度（秒）
            'overlap': 1,            # 重叠长度（秒）
            'min_segment_length': 0.5,  # 最小片段长度
            'confidence_threshold': 0.3  # 置信度阈值
        }

        # 检查ModelScope可用性
        try:
            from modelscope.models import Model
            from modelscope.pipelines import pipeline
            from modelscope.utils.constant import Tasks
            self._modelscope_available = True
            logger.info("ModelScope可用")
        except ImportError:
            self._modelscope_available = False
            # 改为INFO级别，这只是一个可选功能的提示
            logger.info(
                "ModelScope未安装，Paraformer语音识别功能已禁用。"
                "如需使用语音识别，请安装: pip install modelscope"
            )

        if not lazy_load:
            self._load_model()

    def _create_placeholder_result(self, audio_path: str, reason: str = "fallback") -> Dict[str, Any]:
        """
        创建占位符转录结果

        Args:
            audio_path: 音频文件路径
            reason: 创建占位符的原因

        Returns:
            占位符转录结果
        """
        return {
            'success': True,
            'full_transcript': '[音频转录暂时不可用，请稍后重试]',
            'segments': [{
                'text': '[音频转录暂时不可用，请稍后重试]',
                'confidence': 0.0,
                'start_time': 0,
                'end_time': 0,
                'duration': 0
            }],
            'metadata': {
                'audio_path': audio_path,
                'total_duration': 0,
                'segments_count': 1,
                'average_confidence': 0.0,
                'model': f'placeholder-{reason}',
                'note': '音频转录服务暂时不可用'
            }
        }

    def _load_model(self):
        """加载Paraformer模型"""
        if self._model_loaded:
            return True

        if not self._modelscope_available:
            raise RuntimeError(
                "ModelScope未安装，无法加载Paraformer模型。"
                "请安装: pip install modelscope"
            )

        try:
            logger.info(f"正在加载Paraformer模型: {self.model_path}")

            from modelscope.models import Model
            from modelscope.pipelines import pipeline
            from modelscope.utils.constant import Tasks

            # 加载模型
            self.model = Model.from_pretrained(self.model_path)

            # 创建ASR pipeline
            self.pipeline = pipeline(
                task=Tasks.auto_speech_recognition,
                model=self.model,
                # 可以添加更多配置参数
                param_dict={
                    'sample_rate': self.config['sample_rate'],
                    'language': 'zh-cn',
                    'use_timestamp': True,
                    'hotword': None  # 可以设置热词
                }
            )

            self._model_loaded = True
            logger.info("Paraformer模型加载成功")
            return True

        except Exception as e:
            logger.error(f"Paraformer模型加载失败: {str(e)}")
            logger.info("将使用备用方案（占位符转录）")
            self.model = None
            self.pipeline = None
            self._model_loaded = False
            return False

    def _load_audio(self, audio_path: str) -> Tuple[np.ndarray, int]:
        """
        加载音频文件

        Returns:
            (音频数据, 采样率)
        """
        try:
            if not LIBROSA_AVAILABLE:
                raise RuntimeError(
                    "librosa未安装，当前默认 minimal 安装不包含音频转写依赖。"
                    "如需启用，请执行: pip install -r requirements-full.txt"
                )

            # 使用librosa加载音频，自动转换为16kHz单声道
            audio_data, sr = librosa.load(
                audio_path,
                sr=self.config['sample_rate'],
                mono=True,
                dtype=np.float32
            )

            logger.debug(f"音频加载成功: {audio_path}, 长度: {len(audio_data)/sr:.2f}秒")
            return audio_data, sr

        except Exception as e:
            logger.error(f"音频加载失败: {str(e)}")
            raise

    def _segment_audio(self, audio_data: np.ndarray, sample_rate: int) -> List[Dict[str, Any]]:
        """
        将音频分段处理

        Returns:
            分段信息列表
        """
        segments = []
        audio_duration = len(audio_data) / sample_rate

        chunk_samples = int(self.config['chunk_length'] * sample_rate)
        overlap_samples = int(self.config['overlap'] * sample_rate)
        step_samples = chunk_samples - overlap_samples

        start_sample = 0
        segment_id = 0

        while start_sample < len(audio_data):
            end_sample = min(start_sample + chunk_samples, len(audio_data))

            # 提取音频片段
            segment_audio = audio_data[start_sample:end_sample]

            # 计算时间戳
            start_time = start_sample / sample_rate
            end_time = end_sample / sample_rate

            # 检查最小片段长度
            if (end_time - start_time) >= self.config['min_segment_length']:
                segments.append({
                    'id': segment_id,
                    'audio_data': segment_audio,
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': end_time - start_time
                })
                segment_id += 1

            start_sample += step_samples

            # 避免无限循环
            if start_sample >= len(audio_data):
                break

        logger.info(f"音频分段完成: {len(segments)}个片段，总时长: {audio_duration:.2f}秒")
        return segments

    def _transcribe_segment(self, audio_segment: np.ndarray) -> Dict[str, Any]:
        """
        转录单个音频片段

        Returns:
            转录结果
        """
        if self.pipeline is None:
            # 使用备用方案：基于Whisper的降级转录
            # 注意：这里需要在调用处确保是async环境
            try:
                return self._fallback_whisper_transcribe_sync(audio_segment)
            except Exception as e:
                logger.error(f"同步Whisper转录失败: {e}")
                return {
                    'text': '',
                    'confidence': 0.0,
                    'timestamps': [],
                    'status': 'error',
                    'error': str(e)
                }

        try:
            # 使用Paraformer进行转录
            result = self.pipeline(audio_segment)

            # 解析结果
            if isinstance(result, dict):
                text = result.get('text', '')
                confidence = result.get('confidence', 0.0)
                timestamps = result.get('timestamps', [])
            elif isinstance(result, str):
                text = result
                confidence = 1.0  # 假设置信度
                timestamps = []
            else:
                text = str(result)
                confidence = 0.5
                timestamps = []

            return {
                'text': text.strip(),
                'confidence': float(confidence),
                'timestamps': timestamps,
                'status': 'success'
            }

        except Exception as e:
            logger.error(f"音频片段转录失败: {str(e)}")
            return {
                'text': '',
                'confidence': 0.0,
                'timestamps': [],
                'status': 'error',
                'error': str(e)
            }

    async def transcribe_audio_file(self, audio_path: str) -> Dict[str, Any]:
        """
        转录完整音频文件

        Args:
            audio_path: 音频文件路径

        Returns:
            转录结果
        """
        try:
            logger.info(f"开始转录音频文件: {audio_path}")

            remote_result = await self._remote_audio_transcribe(audio_path)
            if remote_result.get("success"):
                return remote_result

            if remote_result.get("error"):
                logger.warning(f"远端音频转写不可用，回退本地链路: {remote_result['error']}")

            local_result = await self._local_paraformer_transcribe(audio_path)
            if local_result.get("success"):
                return local_result

            if local_result.get("error"):
                logger.warning(f"本地Paraformer转写不可用，回退Whisper: {local_result['error']}")

            return await self._fallback_whisper_transcribe(audio_path)

        except Exception as e:
            logger.error(f"音频文件转录失败: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'full_transcript': '',
                'segments': []
            }

    def _remote_transcription_enabled(self) -> bool:
        provider = (self.transcription_config.provider or "").strip().lower()
        if provider not in {"openai", "local"}:
            return False
        if not self.transcription_config.api_base:
            return False
        if self._remote_auth_config.mode == "bearer" and not self._remote_auth_config.api_key:
            return False
        return True

    def _is_retryable_remote_error(self, error_text: str) -> bool:
        normalized = (error_text or "").strip().lower()
        return any(
            keyword in normalized
            for keyword in ("quota exceeded", "rate limit", "too many requests", "throttled", "timeout", "temporarily unavailable")
        )

    def _build_transcription_result(
        self,
        *,
        audio_path: str,
        full_transcript: str,
        model_name: str,
        confidence: float,
        segments: Optional[List[Dict[str, Any]]] = None,
        retry_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        normalized_segments = list(segments or [])
        if not normalized_segments:
            normalized_segments = [{
                'text': full_transcript,
                'confidence': confidence,
                'start_time': 0,
                'end_time': 0,
                'duration': 0,
            }]

        average_confidence = (
            sum(float(seg.get('confidence', 0.0)) for seg in normalized_segments) / len(normalized_segments)
            if normalized_segments else confidence
        )
        metadata = {
            'audio_path': audio_path,
            'total_duration': max(float(seg.get('end_time', 0) or 0) for seg in normalized_segments) if normalized_segments else 0,
            'segments_count': len(normalized_segments),
            'average_confidence': average_confidence,
            'model': model_name,
        }
        if retry_count is not None:
            metadata['retry_count'] = retry_count

        return {
            'success': True,
            'full_transcript': full_transcript,
            'segments': normalized_segments,
            'metadata': metadata,
        }

    async def _remote_audio_transcribe(self, audio_path: str) -> Dict[str, Any]:
        import asyncio

        if not self._remote_transcription_enabled():
            return {
                'success': False,
                'error': '远端音频转写未启用或配置不完整',
            }

        last_error: Optional[Exception] = None
        max_retries = max(0, int(self.transcription_config.max_retries))
        for attempt in range(max_retries + 1):
            try:
                result = await asyncio.to_thread(self._remote_audio_transcribe_sync, audio_path, attempt)
                if result.get('success'):
                    return result
                last_error = RuntimeError(result.get('error', '远端音频转写失败'))
            except Exception as exc:
                last_error = exc

            if attempt < max_retries and self._is_retryable_remote_error(str(last_error)):
                delay = attempt + 1
                logger.warning(f"远端音频转写失败，{delay} 秒后重试: {last_error}")
                await asyncio.sleep(delay)

        return {
            'success': False,
            'error': str(last_error or '远端音频转写失败'),
        }

    def _remote_audio_transcribe_sync(self, audio_path: str, attempt: int = 0) -> Dict[str, Any]:
        base_url = _normalize_openai_base_url(self.transcription_config.api_base)
        if not base_url:
            raise ValueError("AUDIO_TRANSCRIBE_API_BASE 未配置")

        endpoint = f"{base_url}/audio/transcriptions"
        headers = apply_auth_headers({}, self._remote_auth_config)
        data = {
            'model': self.transcription_config.model_name,
            'language': self.transcription_config.language,
        }
        if self.transcription_config.prompt:
            data['prompt'] = self.transcription_config.prompt

        mime_type, _ = mimetypes.guess_type(audio_path)
        mime_type = mime_type or 'application/octet-stream'

        with open(audio_path, 'rb') as audio_file:
            response = requests.post(
                endpoint,
                headers=headers,
                data=data,
                files={'file': (os.path.basename(audio_path), audio_file, mime_type)},
                timeout=self.transcription_config.timeout,
                proxies={"http": None, "https": None},
                auth=build_requests_auth(self._remote_auth_config),
            )

        if response.status_code != 200:
            raise RuntimeError(f"API调用失败: HTTP {response.status_code} - {response.text}")

        try:
            payload = response.json()
        except Exception:
            payload = {'text': response.text}

        text = (payload.get('text') or payload.get('transcript') or response.text or '').strip()
        if not text:
            raise RuntimeError("远端音频转写响应为空")

        raw_segments = payload.get('segments') or []
        segments = []
        for item in raw_segments:
            if not isinstance(item, dict):
                continue
            start_time = float(item.get('start', item.get('start_time', 0)) or 0)
            end_time = float(item.get('end', item.get('end_time', start_time)) or start_time)
            segments.append({
                'text': str(item.get('text', '')).strip(),
                'confidence': float(item.get('confidence', 0.9) or 0.9),
                'start_time': start_time,
                'end_time': end_time,
                'duration': max(0.0, end_time - start_time),
            })

        return self._build_transcription_result(
            audio_path=audio_path,
            full_transcript=text,
            model_name=self.transcription_config.model_name,
            confidence=0.9,
            segments=segments,
            retry_count=attempt,
        )

    async def _local_paraformer_transcribe(self, audio_path: str) -> Dict[str, Any]:
        import asyncio

        return await asyncio.to_thread(self._local_paraformer_transcribe_sync, audio_path)

    def _local_paraformer_transcribe_sync(self, audio_path: str) -> Dict[str, Any]:
        if not self._load_model():
            return {
                'success': False,
                'error': '本地Paraformer模型不可用',
            }

        try:
            audio_data, sample_rate = self._load_audio(audio_path)
            audio_segments = self._segment_audio(audio_data, sample_rate)
            transcription_segments: List[Dict[str, Any]] = []

            for audio_segment in audio_segments:
                result = self._transcribe_segment(audio_segment['audio_data'])
                if result.get('status') != 'success':
                    continue
                text = str(result.get('text', '')).strip()
                if not text:
                    continue
                transcription_segments.append({
                    'text': text,
                    'confidence': float(result.get('confidence', 0.0) or 0.0),
                    'start_time': audio_segment['start_time'],
                    'end_time': audio_segment['end_time'],
                    'duration': audio_segment['duration'],
                })

            full_transcript = self._merge_transcription_results(transcription_segments)
            if not full_transcript:
                return {
                    'success': False,
                    'error': '本地Paraformer未产出有效转写结果',
                }

            return self._build_transcription_result(
                audio_path=audio_path,
                full_transcript=full_transcript,
                model_name=self.model_path,
                confidence=0.85,
                segments=transcription_segments,
            )
        except Exception as exc:
            logger.error(f"本地Paraformer转写失败: {exc}")
            return {
                'success': False,
                'error': str(exc),
            }

    async def _fallback_whisper_transcribe(self, audio_path: str) -> Dict[str, Any]:
        """
        Whisper降级转录

        Args:
            audio_path: 音频文件路径

        Returns:
            转录结果
        """
        try:
            import whisper

            model = whisper.load_model("base")
            result = model.transcribe(audio_path, language='zh')
            return self._build_transcription_result(
                audio_path=audio_path,
                full_transcript=result['text'],
                model_name='whisper-base',
                confidence=0.8,
            )

        except Exception as e:
            logger.error(f"Whisper降级转录失败: {str(e)}")
            # 返回占位符结果，避免处理流程中断
            return self._create_placeholder_result(audio_path, reason="whisper-unavailable")

    def _merge_transcription_results(self, segments: List[Dict[str, Any]]) -> str:
        """合并分段转录结果为完整文本"""
        valid_segments = [s for s in segments if s['confidence'] > self.config['confidence_threshold']]

        if not valid_segments:
            return ""

        # 简单拼接（可以添加更智能的合并逻辑）
        texts = [s['text'] for s in valid_segments if s['text'].strip()]
        return ' '.join(texts)

    def _fallback_whisper_transcribe_sync(self, audio_segment) -> Dict[str, Any]:
        """
        同步版本的Whisper降级转录

        Args:
            audio_segment: 音频段数据

        Returns:
            转录结果
        """
        try:
            import whisper

            model = whisper.load_model("base")

            # 如果是文件路径
            if isinstance(audio_segment, str):
                result = model.transcribe(audio_segment, language='zh')
            else:
                # 如果是音频数据，需要先保存为临时文件
                import tempfile
                import os

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                    # 假设audio_segment是音频数据
                    if hasattr(audio_segment, 'write'):
                        tmp_file.write(audio_segment)
                    else:
                        tmp_file.write(bytes(audio_segment))
                    tmp_path = tmp_file.name

                try:
                    result = model.transcribe(tmp_path, language='zh')
                finally:
                    os.unlink(tmp_path)

            return {
                'text': result['text'].strip(),
                'confidence': 0.8,
                'timestamps': [],
                'status': 'success',
                'model': 'whisper-base'
            }

        except Exception as e:
            logger.error(f"同步Whisper转录失败: {str(e)}")
            return {
                'text': '',
                'confidence': 0.0,
                'timestamps': [],
                'status': 'error',
                'error': str(e)
            }

    async def align_with_keyframes(self, audio_path: str, keyframes_metadata: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将音频转录与关键帧时间轴对齐

        Args:
            audio_path: 音频文件路径
            keyframes_metadata: 关键帧元数据列表

        Returns:
            对齐后的时间轴数据
        """
        try:
            logger.info("开始音频与关键帧对齐...")

            # 1. 转录完整音频
            transcription_result = await self.transcribe_audio_file(audio_path)

            if not transcription_result['success']:
                logger.error(f"音频转录失败: {transcription_result.get('error')}")
                return keyframes_metadata  # 返回原始数据

            # 2. 与关键帧对齐
            aligned_timeline = []
            transcription_segments = transcription_result['segments']

            for i, keyframe in enumerate(keyframes_metadata):
                keyframe_time = keyframe['time_sec']

                # 查找对应的音频片段
                matching_transcript = self._find_matching_transcript(
                    keyframe_time, transcription_segments
                )

                # 构建对齐数据
                aligned_item = keyframe.copy()
                aligned_item.update({
                    'transcript': matching_transcript.get('text', ''),
                    'transcript_confidence': matching_transcript.get('confidence', 0.0),
                    'transcript_start_time': matching_transcript.get('start_time'),
                    'transcript_end_time': matching_transcript.get('end_time')
                })

                aligned_timeline.append(aligned_item)

            logger.info(f"音频对齐完成: {len(aligned_timeline)}个时间点")
            return aligned_timeline

        except Exception as e:
            logger.error(f"音频对齐失败: {str(e)}")
            return keyframes_metadata

    def _find_matching_transcript(self, target_time: float, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """查找与目标时间最匹配的转录片段"""
        if not segments:
            return {}

        # 寻找包含目标时间的片段
        for segment in segments:
            if segment['start_time'] <= target_time <= segment['end_time']:
                return segment

        # 如果没有包含的，找最近的
        distances = [abs(segment['start_time'] + segment['duration']/2 - target_time) for segment in segments]
        closest_idx = distances.index(min(distances))
        return segments[closest_idx]

# 工具函数
async def transcribe_audio(audio_path: str) -> str:
    """简化接口：转录音频文件返回文本"""
    transcriber = ParaformerTranscriber()
    result = await transcriber.transcribe_audio_file(audio_path)
    return result.get('full_transcript', '') if result['success'] else ''

async def create_multimodal_timeline(keyframes_metadata: List[Dict], audio_path: str) -> List[Dict]:
    """创建多模态时间轴"""
    transcriber = ParaformerTranscriber()
    return await transcriber.align_with_keyframes(audio_path, keyframes_metadata)

if __name__ == "__main__":
    # 测试示例
    import asyncio

    async def test():
        transcriber = ParaformerTranscriber()

        test_audio = "test_audio.wav"
        if os.path.exists(test_audio):
            # 测试转录
            result = await transcriber.transcribe_audio_file(test_audio)

            if result['success']:
                logger.info(f"转录结果: {result['full_transcript']}")
                logger.info(f"片段数量: {len(result['segments'])}")
                logger.info(f"平均置信度: {result['metadata']['average_confidence']:.2f}")
            else:
                logger.info(f"转录失败: {result['error']}")
        else:
            logger.debug("调试信息")

    asyncio.run(test())
