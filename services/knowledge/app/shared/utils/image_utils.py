# ！/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@Time   : 2025/7/28 11:50
@Author : 13594053100@163.com
@File   : image_utils.py
"""

import re
import logging
import traceback
import os

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ImageUtils(object):
    SUPPORTED_IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp']

    @staticmethod
    def _is_url(path: str) -> bool:
        """判断是否为网络URL"""
        # 匹配以 http:// 或 https:// 开头的字符串
        # 示例匹配：'http://example.com/xxx.jpg'、'https://abc.cn/1.png'
        return re.match(r'^https?://', path, re.IGNORECASE) is not None

    @staticmethod
    def _is_file_uri(path: str) -> bool:
        """判断是否为标准file URI格式"""
        # 匹配以 file:// 开头的字符串
        # 示例匹配：'file://D:/path/images.jpg' 或 'file:///home/user/a.jpg'
        return re.match(r'^file://', path, re.IGNORECASE) is not None

    @staticmethod
    def validate_image_path(image_path: str) -> bool:
        """验证图片路径的有效性"""
        try:
            if ImageUtils._is_url(image_path):
                logger.info(f"检测到网络URL: {image_path}")
                if not re.match(r'^https?://[^\s/$.?#].[^\s]*$', image_path):
                    logger.error(f"URL格式不正确: {image_path}")
                    return False
                return True
            elif ImageUtils._is_file_uri(image_path):
                logger.info(f"检测到file URI: {image_path}")
                # 解析file URI为本地路径进行存在性校验
                if os.name == 'nt':
                    # Windows: file://D:/path/file.jpg
                    m = re.match(r'^file://([a-zA-Z]:/.*)$', image_path)
                    if m:
                        local_path = m.group(1)
                    else:
                        logger.error(f"file URI格式不正确: {image_path}")
                        return False
                else:
                    # Linux/Mac: file:///abs/path/file.jpg
                    m = re.match(r'^file://(/.*)$', image_path)
                    if m:
                        local_path = m.group(1)
                    else:
                        logger.error(f"file URI格式不正确: {image_path}")
                        return False
                if not os.path.exists(local_path):
                    logger.error(f"本地文件不存在: {local_path}")
                    return False
                file_size = os.path.getsize(local_path)
                logger.info(f"文件大小: {file_size} bytes")
                if file_size == 0:
                    logger.error(f"文件为空: {local_path}")
                    return False
                ext = os.path.splitext(local_path)[1].lower()
                if ext not in ImageUtils.SUPPORTED_IMAGE_EXTS:
                    logger.warning(f"不支持的图片格式: {ext}")
                    supported = ', '.join(ImageUtils.SUPPORTED_IMAGE_EXTS)
                    logger.warning(f"仅支持以下图片格式: {supported}")
                return True
            else:
                logger.info(f"检测到本地路径: {image_path}")
                if not os.path.exists(image_path):
                    logger.error(f"本地文件不存在: {image_path}")
                    return False
                file_size = os.path.getsize(image_path)
                logger.info(f"文件大小: {file_size} bytes")
                if file_size == 0:
                    logger.error(f"文件为空: {image_path}")
                    return False
                ext = os.path.splitext(image_path)[1].lower()
                if ext not in ImageUtils.SUPPORTED_IMAGE_EXTS:
                    logger.warning(f"不支持的图片格式: {ext}")
                    supported = ', '.join(ImageUtils.SUPPORTED_IMAGE_EXTS)
                    logger.warning(f"仅支持以下图片格式: {supported}")
                    return False
                return True
        except Exception as e:
            logger.error(f"验证图片路径时出错: {e}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            return False

    @staticmethod
    def _to_file_uri(path: str) -> str:
        """
        将本地文件路径转换为标准file URI格式
        Linux/Mac: file:///绝对路径/图片名.扩展名
        Windows: file://盘符:/路径/图片名.扩展名
        """
        try:
            abs_path = os.path.abspath(path)
            logger.debug(f"原始路径: {path}")
            logger.debug(f"绝对路径: {abs_path}")

            # 判断操作系统
            if os.name == 'nt':
                # Windows
                abs_path = abs_path.replace("\\", "/")
                # 盘符处理
                if re.match(r'^[a-zA-Z]:', abs_path):
                    file_uri = f"file://{abs_path}"
                else:
                    # 理论上不会走到这里
                    file_uri = f"file:///{abs_path}"
            else:
                # Linux/Mac
                file_uri = f"file://{abs_path}"
            logger.debug(f"生成的file URI: {file_uri}")
            return file_uri
        except Exception as e:
            logger.error(f"转换file URI时出错: {e}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            raise

    @staticmethod
    def adapt_image_path(image_path: str) -> str:
        """
        自动识别图片路径类型并适配为标准格式
        - 网络URL: 保持不变
        - file URI: 保持不变
        - 本地路径: 转换为标准file URI
        """
        if ImageUtils._is_url(image_path):
            logger.info(f"输入为网络URL: {image_path}")
            return image_path
        elif ImageUtils._is_file_uri(image_path):
            logger.info(f"输入为file URI: {image_path}")
            return image_path
        else:
            logger.info(f"输入为本地路径，将自动转换为file URI: {image_path}")
            return ImageUtils._to_file_uri(image_path)
