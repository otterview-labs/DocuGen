#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用视觉分析器
提供简化的视觉理解接口
"""

from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import base64
import json
import mimetypes
import re
import time
import random
import os
from dataclasses import dataclass

import requests

from app.shared.utils.http_auth import (
    HTTPAuthConfig,
    apply_auth_headers,
    build_requests_auth,
)
from app.shared.utils.logger_util import get_logger
from .config import VLMConfig, default_vlm_config

logger = get_logger("VisionAnalyzer")


@dataclass
class ImageMetadata:
    """图像元数据"""
    path: str
    time_sec: Optional[float] = None
    frame_idx: Optional[int] = None
    additional_info: Optional[Dict[str, Any]] = None


@dataclass
class AnalysisResult:
    """分析结果"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    raw_response: Optional[str] = None


class VisionAnalyzer:
    """
    通用视觉分析器

    功能：
    1. 分析单张或多张图片
    2. 提取视频关键帧并分析
    3. 生成结构化描述
    4. 支持多种VLM后端
    """

    def __init__(self, config: Optional[VLMConfig] = None):
        """
        初始化视觉分析器

        Args:
            config: VLM配置，为None时使用默认配置
        """
        self.config = config or default_vlm_config
        self._auth_config = HTTPAuthConfig.build(
            mode=self.config.auth_mode,
            api_key=self.config.api_key,
            username=self.config.username,
            password=self.config.password,
            default_mode="none" if self.config.provider == "local" else "bearer",
        )
        # 仅用于标记是否具备真实VLM调用能力
        self._llm_client = None
        self._init_llm_client()

    def _init_llm_client(self):
        """初始化LLM客户端"""
        try:
            provider = (self.config.provider or "").strip().lower()
            if provider == "disabled":
                logger.info("VLM provider 已禁用，使用模拟模式")
                self._llm_client = None
                return

            if provider not in {"openai", "local"}:
                logger.warning(f"不支持的VLM provider: {self.config.provider}，使用模拟模式")
                self._llm_client = None
                return

            base_url = self._normalize_openai_base_url(self.config.api_base)
            if not base_url:
                logger.warning("未配置 VLM_API_BASE，使用模拟模式")
                self._llm_client = None
                return

            if self._auth_config.mode == "bearer" and not self._auth_config.api_key:
                logger.warning("VLM provider 需要 bearer token，但未配置 VLM_API_KEY，使用模拟模式")
                self._llm_client = None
                return

            self._openai_base_url = base_url
            self._llm_client = True
            logger.info("VLM 初始化完成(provider=%s, model=%s)", provider, self.config.model_name)
            return

        except Exception as e:
            logger.error(f"初始化LLM客户端失败: {e}，使用模拟模式")
            self._llm_client = None

    @staticmethod
    def _normalize_openai_base_url(api_base: Optional[str]) -> str:
        """规范化为 OpenAI-compatible base_url（一般应以 /v1 结尾）。"""
        if not api_base:
            return ""
        u = str(api_base).strip().rstrip("/")

        # 若用户填的是完整 endpoints，这里回退到 API 根
        for suffix in ("/chat/completions", "/completions", "/v1/chat/completions", "/v1/completions"):
            if u.endswith(suffix):
                u = u[: -len(suffix)].rstrip("/")
                break

        if not u.endswith("/v1"):
            u = f"{u}/v1"
        return u

    @staticmethod
    def _to_openai_image_url(image_path: str) -> Optional[str]:
        """将本地路径/URL 转为 OpenAI-compatible 的 image_url.url。"""
        if not image_path:
            return None

        raw = str(image_path).strip()
        if raw.startswith(("http://", "https://", "data:image")):
            return raw

        # file:// -> 本地路径
        if raw.lower().startswith("file://"):
            raw = raw[len("file://") :]

        local_path = os.path.abspath(raw)
        if not os.path.exists(local_path):
            logger.warning(f"图片文件不存在: {local_path}")
            return None

        mime, _ = mimetypes.guess_type(local_path)
        mime = mime or "image/jpeg"
        with open(local_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    def analyze_image(
        self,
        image_path: Union[str, Path],
        prompt: str = "请描述这张图片的内容",
        **kwargs
    ) -> AnalysisResult:
        """
        分析单张图片

        Args:
            image_path: 图片路径
            prompt: 分析提示词
            **kwargs: 额外参数

        Returns:
            AnalysisResult: 分析结果
        """
        try:
            result = self.analyze_images(
                images=[str(image_path)],
                prompt=prompt,
                **kwargs
            )

            if result.success and result.data:
                # 提取第一张图片的结果
                images_data = result.data.get("images", [])
                if images_data:
                    return AnalysisResult(
                        success=True,
                        data=images_data[0]
                    )

            return result

        except Exception as e:
            logger.error(f"分析图片失败: {e}")
            return AnalysisResult(
                success=False,
                error=str(e)
            )

    def analyze_images(
        self,
        images: List[Union[str, Path, ImageMetadata]],
        prompt: str = "请描述这些图片的内容",
        batch_process: bool = True,
        **kwargs
    ) -> AnalysisResult:
        """
        分析多张图片

        Args:
            images: 图片列表（路径或元数据）
            prompt: 分析提示词
            batch_process: 是否批处理
            **kwargs: 额外参数

        Returns:
            AnalysisResult: 分析结果
        """
        try:
            # 预处理图片列表
            image_list = self._prepare_images(images)

            if not image_list:
                return AnalysisResult(
                    success=False,
                    error="没有有效的图片"
                )

            # 如果没有真实的LLM客户端，返回模拟结果
            if not self._llm_client:
                return self._generate_mock_result(image_list, prompt)

            # 批处理
            if batch_process and len(image_list) > self.config.max_images_per_batch:
                return self._batch_analyze(image_list, prompt, **kwargs)

            # 直接分析
            return self._do_analyze(image_list, prompt, **kwargs)

        except Exception as e:
            logger.error(f"分析图片失败: {e}")
            return AnalysisResult(
                success=False,
                error=str(e)
            )

    def analyze_video_frames(
        self,
        frames_metadata: List[Dict[str, Any]],
        prompt: str = "请分析这些视频帧的内容",
        **kwargs
    ) -> AnalysisResult:
        """
        分析视频帧

        Args:
            frames_metadata: 帧元数据列表，每项包含 path, time_sec, frame_idx
            prompt: 分析提示词
            **kwargs: 额外参数

        Returns:
            AnalysisResult: 分析结果
        """
        try:
            # 转换为ImageMetadata
            images = []
            for frame in frames_metadata:
                images.append(ImageMetadata(
                    path=frame.get("path", ""),
                    time_sec=frame.get("time_sec"),
                    frame_idx=frame.get("frame_idx"),
                    additional_info=frame
                ))

            # 分析
            result = self.analyze_images(
                images=images,
                prompt=prompt,
                batch_process=True,
                **kwargs
            )

            # 添加时间轴信息
            if result.success and result.data:
                result.data["is_video"] = True
                result.data["frame_count"] = len(frames_metadata)

            return result

        except Exception as e:
            logger.error(f"分析视频帧失败: {e}")
            return AnalysisResult(
                success=False,
                error=str(e)
            )

    def _prepare_images(self, images: List[Union[str, Path, ImageMetadata]]) -> List[ImageMetadata]:
        """预处理图片列表"""
        result = []
        for img in images:
            if isinstance(img, ImageMetadata):
                result.append(img)
            elif isinstance(img, (str, Path)):
                result.append(ImageMetadata(path=str(img)))
            elif isinstance(img, dict):
                # 兼容字典格式
                result.append(ImageMetadata(
                    path=img.get("path", ""),
                    time_sec=img.get("time_sec"),
                    frame_idx=img.get("frame_idx"),
                    additional_info=img
                ))
        return result

    def _batch_analyze(
        self,
        image_list: List[ImageMetadata],
        prompt: str,
        **kwargs
    ) -> AnalysisResult:
        """批量分析"""
        all_results = []
        batch_size = self.config.max_images_per_batch

        for i in range(0, len(image_list), batch_size):
            batch = image_list[i:i + batch_size]
            batch_result = self._do_analyze(batch, prompt, **kwargs)

            if batch_result.success and batch_result.data:
                batch_images = batch_result.data.get("images", [])
                all_results.extend(batch_images)

        return AnalysisResult(
            success=True,
            data={"images": all_results}
        )

    def _do_analyze(
        self,
        image_list: List[ImageMetadata],
        prompt: str,
        **kwargs
    ) -> AnalysisResult:
        """执行实际分析"""
        try:
            user_content: List[Dict[str, Any]] = []
            user_content.append({"type": "text", "text": prompt})

            for idx, img_meta in enumerate(image_list):
                if img_meta.time_sec is not None or img_meta.frame_idx is not None:
                    meta_text = f"[图片 {idx+1}]"
                    if img_meta.time_sec is not None:
                        meta_text += f" 时间: {img_meta.time_sec:.2f}秒"
                    if img_meta.frame_idx is not None:
                        meta_text += f" 帧号: {img_meta.frame_idx}"
                    user_content.append({"type": "text", "text": meta_text})

                image_url = self._to_openai_image_url(img_meta.path)
                if not image_url:
                    continue
                user_content.append({"type": "image_url", "image_url": {"url": image_url}})

            messages = [{"role": "user", "content": user_content}]
            logger.debug(f"发送消息(OpenAI-compatible): {messages}")
            response = self._call_llm_with_retry(messages)

            # 解析结果
            parsed = self._parse_response(response)

            return AnalysisResult(
                success=True,
                data=parsed,
                raw_response=response
            )

        except Exception as e:
            logger.error(f"执行分析失败: {e}")
            return AnalysisResult(
                success=False,
                error=str(e)
            )

    def _call_llm_with_retry(self, messages: List[Dict]) -> str:
        """带重试的LLM调用"""
        last_error = None

        for attempt in range(self.config.max_retries):
            try:
                base_url = getattr(self, "_openai_base_url", "") or self._normalize_openai_base_url(self.config.api_base)
                if not base_url:
                    raise ValueError("VLM_API_BASE未配置")
                headers = apply_auth_headers({"Content-Type": "application/json"}, self._auth_config)

                # 补齐 system_prompt
                full_messages = []
                if self.config.system_prompt and not any(m.get("role") == "system" for m in messages):
                    full_messages.append({"role": "system", "content": self.config.system_prompt})
                full_messages.extend(messages)

                url = f"{base_url.rstrip('/')}/chat/completions"
                payload = {
                    "model": self.config.model_name,
                    "messages": full_messages,
                    "stream": False,
                }

                resp = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=max(30, int(getattr(self.config, "batch_timeout", 60))),
                    proxies={"http": None, "https": None},
                    auth=build_requests_auth(self._auth_config),
                )
                if resp.status_code != 200:
                    raise Exception(f"API调用失败: HTTP {resp.status_code} - {resp.text}")

                data = resp.json()
                choices = data.get("choices") or []
                if not choices:
                    raise Exception("OpenAI-compatible 响应 choices 为空")
                msg = choices[0].get("message") or {}
                content = msg.get("content")
                if content is None:
                    raise Exception("OpenAI-compatible 响应 message.content 为空")
                if isinstance(content, list):
                    texts = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            texts.append(str(item.get("text", "")))
                        elif isinstance(item, dict) and "text" in item:
                            texts.append(str(item.get("text", "")))
                        else:
                            texts.append(str(item))
                    return " ".join(text for text in texts if text)
                return str(content)

            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"LLM调用失败，{delay:.1f}秒后重试: {e}")
                    time.sleep(delay)

        raise last_error or Exception("LLM调用失败")

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            # 尝试提取JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

            # 如果不是JSON，返回文本描述
            return {
                "description": response.strip(),
                "images": [{"description": response.strip()}]
            }

        except Exception as e:
            logger.warning(f"解析响应失败: {e}")
            return {
                "description": response[:500] if response else "解析失败",
                "images": []
            }

    def _generate_mock_result(
        self,
        image_list: List[ImageMetadata],
        prompt: str
    ) -> AnalysisResult:
        """生成模拟结果（用于测试或无LLM时）"""
        mock_results = []

        for idx, img_meta in enumerate(image_list):
            result = {
                "index": idx,
                "path": img_meta.path,
                "description": f"这是第{idx+1}张图片的内容描述",
                "objects": ["物体1", "物体2"],
                "scene": "场景描述"
            }

            if img_meta.time_sec is not None:
                result["time_sec"] = img_meta.time_sec
            if img_meta.frame_idx is not None:
                result["frame_idx"] = img_meta.frame_idx

            mock_results.append(result)

        return AnalysisResult(
            success=True,
            data={
                "prompt": prompt,
                "images": mock_results,
                "total_count": len(image_list)
            }
        )
