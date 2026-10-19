#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图像优化处理器
基于qvq-max模型限制优化图像大小和格式
"""

import os
import base64
from PIL import Image, ImageOps
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import io

from app.shared.utils.logger_util import get_logger

logger = get_logger("ImageOptimizer")

class ImageOptimizer:
    """图像优化器 - 针对qvq-max模型限制"""

    # qvq-max限制配置
    MAX_FILE_SIZE_MB = 10
    MAX_BASE64_SIZE_MB = 10
    MIN_PIXELS = 10
    MAX_ASPECT_RATIO = 200
    RECOMMENDED_PIXELS = 1003520  # qvq-max推荐上限

    # 优化配置
    RECOMMENDED_SIZE = (1280, 1280)
    JPEG_QUALITY = 85
    PNG_COMPRESS_LEVEL = 6
    WEBP_QUALITY = 80

    def __init__(self):
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp', '.gif'}

    def validate_image(self, image_path: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        验证图像是否符合qvq-max要求

        Returns:
            (是否有效, 验证信息, 图像信息)
        """
        try:
            if not os.path.exists(image_path):
                return False, "图像文件不存在", {}

            # 检查文件大小
            file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
            if file_size_mb > self.MAX_FILE_SIZE_MB:
                return False, f"文件大小{file_size_mb:.1f}MB超过{self.MAX_FILE_SIZE_MB}MB限制", {}

            # 打开图像获取信息
            with Image.open(image_path) as img:
                width, height = img.size
                pixels = width * height
                aspect_ratio = max(width, height) / min(width, height)

                # 检查最小尺寸
                if width < self.MIN_PIXELS or height < self.MIN_PIXELS:
                    return False, f"图像尺寸{width}x{height}小于最小要求{self.MIN_PIXELS}px", {}

                # 检查宽高比
                if aspect_ratio > self.MAX_ASPECT_RATIO:
                    return False, f"宽高比{aspect_ratio:.1f}超过{self.MAX_ASPECT_RATIO}:1限制", {}

                # 图像信息
                info = {
                    'width': width,
                    'height': height,
                    'pixels': pixels,
                    'aspect_ratio': aspect_ratio,
                    'format': img.format,
                    'mode': img.mode,
                    'file_size_mb': file_size_mb,
                    'needs_optimization': pixels > self.RECOMMENDED_PIXELS or file_size_mb > 5
                }

                # 建议信息
                if pixels > self.RECOMMENDED_PIXELS:
                    message = f"图像{width}x{height}({pixels}像素)建议优化，推荐不超过{self.RECOMMENDED_PIXELS}像素"
                elif file_size_mb > 5:
                    message = f"文件大小{file_size_mb:.1f}MB建议压缩"
                else:
                    message = f"图像{width}x{height}符合要求"

                return True, message, info

        except Exception as e:
            return False, f"图像验证失败: {str(e)}", {}

    def calculate_optimal_size(self, original_size: Tuple[int, int]) -> Tuple[int, int]:
        """
        计算最优图像尺寸
        - 保持宽高比
        - 控制在推荐像素范围内
        - 优先保证较长边不超过1280px
        """
        width, height = original_size
        pixels = width * height

        # 如果已经在推荐范围内，不调整
        if pixels <= self.RECOMMENDED_PIXELS and max(width, height) <= 1280:
            return original_size

        # 计算缩放比例
        if max(width, height) > 1280:
            # 基于最大边长限制
            scale_factor = 1280 / max(width, height)
        else:
            # 基于像素总数限制
            scale_factor = (self.RECOMMENDED_PIXELS / pixels) ** 0.5

        # 应用缩放
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)

        # 确保最小尺寸
        new_width = max(new_width, self.MIN_PIXELS)
        new_height = max(new_height, self.MIN_PIXELS)

        return new_width, new_height

    def optimize_image(self, input_path: str, output_path: str,
                      target_size: Optional[Tuple[int, int]] = None,
                      quality: int = None) -> bool:
        """
        优化图像文件
        - 调整尺寸到最优配置
        - 压缩文件大小
        - 保持图像质量平衡
        """
        try:
            with Image.open(input_path) as img:
                # 转换为RGB模式（确保兼容性）
                if img.mode in ('RGBA', 'LA', 'P'):
                    # 保留透明度信息的处理
                    if img.mode == 'P' and 'transparency' in img.info:
                        img = img.convert('RGBA')
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        background.paste(img, mask=img.split()[-1])
                    else:
                        background.paste(img)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                # 计算目标尺寸
                if target_size is None:
                    target_size = self.calculate_optimal_size(img.size)

                # 调整尺寸（高质量重采样）
                if img.size != target_size:
                    img = img.resize(target_size, Image.Resampling.LANCZOS)
                    logger.info(f"图像尺寸调整: {input_path} {img.size} -> {target_size}")

                # 自动旋转（基于EXIF信息）
                img = ImageOps.exif_transpose(img)

                # 保存优化后的图像
                save_kwargs = {}
                output_format = Path(output_path).suffix.lower()

                if output_format in ['.jpg', '.jpeg']:
                    save_kwargs.update({
                        'format': 'JPEG',
                        'quality': quality or self.JPEG_QUALITY,
                        'optimize': True,
                        'progressive': True
                    })
                elif output_format == '.png':
                    save_kwargs.update({
                        'format': 'PNG',
                        'optimize': True,
                        'compress_level': self.PNG_COMPRESS_LEVEL
                    })
                elif output_format == '.webp':
                    save_kwargs.update({
                        'format': 'WEBP',
                        'quality': quality or self.WEBP_QUALITY,
                        'optimize': True
                    })
                else:
                    # 默认保存为JPEG
                    output_path = str(Path(output_path).with_suffix('.jpg'))
                    save_kwargs.update({
                        'format': 'JPEG',
                        'quality': quality or self.JPEG_QUALITY,
                        'optimize': True
                    })

                img.save(output_path, **save_kwargs)

                # 验证输出文件
                if os.path.exists(output_path):
                    optimized_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                    logger.info(f"图像优化完成: {output_path}, 大小: {optimized_size_mb:.2f}MB")
                    return True
                else:
                    logger.error("优化后的图像文件创建失败")
                    return False

        except Exception as e:
            logger.error(f"图像优化失败: {str(e)}")
            return False

    def check_base64_size(self, image_path: str) -> Tuple[bool, float]:
        """
        检查Base64编码后的大小是否符合要求

        Returns:
            (是否符合要求, Base64大小MB)
        """
        try:
            with open(image_path, 'rb') as img_file:
                img_data = img_file.read()
                base64_data = base64.b64encode(img_data)
                base64_size_mb = len(base64_data) / (1024 * 1024)

                return base64_size_mb <= self.MAX_BASE64_SIZE_MB, base64_size_mb

        except Exception as e:
            logger.error(f"Base64大小检查失败: {str(e)}")
            return False, 0

    def batch_optimize_images(self, image_paths: list, output_dir: str) -> Dict[str, Any]:
        """
        批量优化图像文件

        Returns:
            处理结果统计
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {
            'total': len(image_paths),
            'success': 0,
            'failed': 0,
            'optimized_paths': [],
            'errors': []
        }

        for i, img_path in enumerate(image_paths):
            try:
                # 验证图像
                valid, message, info = self.validate_image(img_path)
                if not valid:
                    results['errors'].append(f"{img_path}: {message}")
                    results['failed'] += 1
                    continue

                # 生成输出路径
                img_stem = Path(img_path).stem
                output_path = output_dir / f"{img_stem}_optimized.jpg"

                # 优化图像
                if self.optimize_image(img_path, str(output_path)):
                    results['optimized_paths'].append(str(output_path))
                    results['success'] += 1

                    # 检查Base64大小
                    base64_ok, base64_size = self.check_base64_size(str(output_path))
                    if not base64_ok:
                        logger.warning(f"Base64大小{base64_size:.1f}MB可能超限制")
                else:
                    results['errors'].append(f"{img_path}: 优化失败")
                    results['failed'] += 1

            except Exception as e:
                results['errors'].append(f"{img_path}: {str(e)}")
                results['failed'] += 1

        logger.info(f"批量优化完成: 成功{results['success']}/{results['total']}")
        return results

    def get_image_token_estimate(self, width: int, height: int) -> int:
        """
        估算图像的Token使用量（基于qvq-max规则）
        """
        pixels = width * height

        # 基于像素数的简化估算
        if pixels <= 980 * 980:  # 默认Token限制范围
            return int(pixels / 800)  # 大致估算
        elif pixels <= 1288 * 1288:  # 高分辨率Token限制
            return int(pixels / 400)  # 高分辨率需要更多Token
        else:
            return int(pixels / 300)  # 超大图像

# 工具函数
def optimize_image_for_vlm(image_path: str, output_path: str) -> bool:
    """优化单张图像用于VLM处理"""
    optimizer = ImageOptimizer()
    return optimizer.optimize_image(image_path, output_path)

def batch_optimize_keyframes(keyframe_paths: list, output_dir: str) -> list:
    """批量优化关键帧图像"""
    optimizer = ImageOptimizer()
    results = optimizer.batch_optimize_images(keyframe_paths, output_dir)
    return results['optimized_paths']

if __name__ == "__main__":
    # 测试示例
    optimizer = ImageOptimizer()

    test_image = "test_image.jpg"
    if os.path.exists(test_image):
        # 验证图像
        valid, message, info = optimizer.validate_image(test_image)
        logger.info(f"图像验证: {message}")
        logger.info(f"图像信息: {info}")

        if valid:
            # 优化图像
            output_path = "optimized_image.jpg"
            success = optimizer.optimize_image(test_image, output_path)
            logger.info(f"优化结果: {'成功' if success else '失败'}")

            if success:
                # 检查Base64大小
                base64_ok, base64_size = optimizer.check_base64_size(output_path)
                logger.info(f"Base64大小: {base64_size:.2f}MB, 符合要求: {base64_ok}")
    else:
        logger.debug("调试信息")
