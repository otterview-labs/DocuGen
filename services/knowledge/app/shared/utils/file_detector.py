#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一的文件类型检测器
基于文件头、扩展名和内容的多重验证机制
"""

import os
import mimetypes
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import hashlib

from app.shared.response_models import ResponseHelper

class FileTypeDetector:
    """增强的文件类型检测器"""

    # 文件头魔数定义
    MAGIC_BYTES = {
        b'\xFF\xD8\xFF': 'image/jpeg',
        b'\x89PNG\x0D\x0A\x1A\x0A': 'image/png',
        b'GIF87a': 'image/gif',
        b'GIF89a': 'image/gif',
        b'BM': 'image/bmp',
        b'RIFF': 'image/webp',
        b'%PDF-': 'application/pdf',
        b'\x50\x4B\x03\x04': 'application/zip',  # DOCX, XLSX等Office文件
        b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1': 'application/msword',  # DOC
        b'{\rtf': 'application/rtf',
        b'%!PS-Adobe': 'application/postscript',
        b'\x00\x00\x00\x20\x66\x74\x79\x70': 'video/mp4',
        b'ftypisom': 'video/mp4',
        b'ftypmp42': 'video/mp4',
        b'ftyp3gp4': 'video/3gpp',
        b'ftypqt': 'video/quicktime',
        b'RIFF': 'video/avi',
        b'\x1A\x45\xDF\xA3': 'video/webm',
        b'\x00\x00\x01\xBA': 'video/mpeg',
        b'\x00\x00\x01\xB3': 'video/mpeg',
        # 音频文件魔数
        b'ID3': 'audio/mpeg',  # MP3 with ID3 tag
        b'\xFF\xFB': 'audio/mpeg',  # MP3 without ID3
        b'\xFF\xF3': 'audio/mpeg',  # MP3 without ID3
        b'\xFF\xF2': 'audio/mpeg',  # MP3 without ID3
        b'OggS': 'audio/ogg',  # OGG Vorbis
        b'fLaC': 'audio/flac',  # FLAC
        b'\x00\x00\x00\x20ftypM4A ': 'audio/mp4',  # M4A
        b'FORM': 'audio/aiff',  # AIFF
        b'RIFF': 'audio/wav',  # WAV (需要进一步检查WAVE标记)
    }

    # 支持的文件类型映射
    SUPPORTED_TYPES = {
        'video': {
            'extensions': ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'],
            'mime_types': ['video/mp4', 'video/avi', 'video/quicktime', 'video/x-msvideo',
                          'video/webm', 'video/x-flv', 'video/x-ms-wmv'],
            'max_size': 200 * 1024 * 1024,  # 200MB
        },
        'document': {
            'extensions': ['.pdf', '.txt', '.md', '.docx', '.doc', '.xlsx', '.xls', '.csv'],
            'mime_types': ['application/pdf', 'text/plain', 'text/markdown',
                          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                          'application/msword', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                          'application/vnd.ms-excel', 'text/csv'],
            'max_size': 50 * 1024 * 1024,  # 50MB
        },
        'image': {
            'extensions': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'],
            'mime_types': ['image/jpeg', 'image/png', 'image/gif', 'image/webp',
                          'image/bmp', 'image/tiff'],
            'max_size': 10 * 1024 * 1024,  # 10MB
        },
        'audio': {
            'extensions': ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.aiff', '.opus'],
            'mime_types': ['audio/mpeg', 'audio/wav', 'audio/wave', 'audio/x-wav', 'audio/flac',
                          'audio/aac', 'audio/ogg', 'audio/mp4', 'audio/x-m4a',
                          'audio/x-ms-wma', 'audio/aiff', 'audio/x-aiff', 'audio/opus'],
            'max_size': 100 * 1024 * 1024,  # 100MB
        }
    }

    def __init__(self):
        self.max_file_size = 200 * 1024 * 1024  # 200MB 总体限制

    def calculate_file_hash(self, file_path: str) -> str:
        """计算文件MD5哈希值"""
        file_path = Path(file_path)
        if not file_path.exists():
            return ""

        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""

    def detect_file_type_by_content(self, file_path: str) -> Tuple[str, str]:
        """基于文件内容检测类型"""
        file_path = Path(file_path)
        if not file_path.exists():
            return "unknown", "文件不存在"

        try:
            with open(file_path, 'rb') as f:
                header = f.read(32)  # 读取前32字节

            # 检查文件头
            for magic, mime_type in self.MAGIC_BYTES.items():
                if header.startswith(magic.encode() if isinstance(magic, str) else magic):
                    return mime_type.split('/')[-1], mime_type

            # 尝试检测文本文件（Markdown、TXT、CSV等）
            try:
                # 尝试以UTF-8解码
                with open(file_path, 'r', encoding='utf-8') as f:
                    f.read(1024)  # 读取前1KB验证编码
                return "text", "text/plain"
            except (UnicodeDecodeError, UnicodeError):
                pass

            return "unknown", "application/octet-stream"

        except Exception as e:
            return "error", str(e)

    def validate_file(self, file_path: str, content_type: Optional[str] = None) -> Dict[str, Any]:
        """
        全面验证文件

        Args:
            file_path: 文件路径
            content_type: 声明的内容类型（可选）

        Returns:
            验证结果字典
        """
        try:
            file_path = Path(file_path).resolve()

            # 基础验证
            if not file_path.exists():
                return ResponseHelper.error("文件不存在")

            if not file_path.is_file():
                return ResponseHelper.error("路径不是文件")

            file_size = file_path.stat().st_size

            # 总体大小检查
            if file_size > self.max_file_size:
                return ResponseHelper.error(
                    f"文件大小{file_size/1024/1024:.1f}MB超过系统限制{self.max_file_size/1024/1024:.0f}MB"
                )

            # 扩展名检查
            file_extension = file_path.suffix.lower()

            # 内容类型检测
            content_type_by_content, mime_type = self.detect_file_type_by_content(str(file_path))

            # 确定文件类型
            detected_type = None

            # 优先使用扩展名匹配（对于文本文件更可靠）
            for type_name, config in self.SUPPORTED_TYPES.items():
                if file_extension in config['extensions']:
                    detected_type = type_name
                    break

            # 如果扩展名不匹配，尝试按内容类型
            if not detected_type:
                for type_name, config in self.SUPPORTED_TYPES.items():
                    if mime_type in config['mime_types']:
                        detected_type = type_name
                        break

            # 如果还是没匹配，但是文本文件且扩展名是.md/.txt/.csv，强制识别为document
            if not detected_type and content_type_by_content == "text":
                text_extensions = ['.md', '.txt', '.csv', '.markdown', '.text']
                if file_extension in text_extensions:
                    detected_type = "document"
                    mime_type = "text/plain"

            if not detected_type:
                return ResponseHelper.error(
                    f"不支持的文件类型: 扩展名{file_extension}, 内容类型{content_type_by_content}"
                )

            # 类型特定验证
            type_config = self.SUPPORTED_TYPES[detected_type]
            max_size = type_config['max_size']

            if file_size > max_size:
                return ResponseHelper.error(
                    f"{detected_type}文件大小{file_size/1024/1024:.1f}MB超过限制{max_size/1024/1024:.0f}MB"
                )

            # 计算文件哈希用于缓存
            file_hash = self.calculate_file_hash(str(file_path))

            return ResponseHelper.success({
                "type": detected_type,
                "extension": file_extension,
                "mime_type": mime_type,
                "size": file_size,
                "file_hash": file_hash,
                "is_supported": True
            })

        except Exception as e:
            return ResponseHelper.error(f"文件验证失败: {str(e)}")

    def get_supported_types(self) -> Dict[str, Any]:
        """获取支持的文件类型信息"""
        return {
            "video": {
                "extensions": self.SUPPORTED_TYPES["video"]["extensions"],
                "max_size_mb": self.SUPPORTED_TYPES["video"]["max_size"] / (1024 * 1024),
                "mime_types": self.SUPPORTED_TYPES["video"]["mime_types"]
            },
            "document": {
                "extensions": self.SUPPORTED_TYPES["document"]["extensions"],
                "max_size_mb": self.SUPPORTED_TYPES["document"]["max_size"] / (1024 * 1024),
                "mime_types": self.SUPPORTED_TYPES["document"]["mime_types"]
            },
            "image": {
                "extensions": self.SUPPORTED_TYPES["image"]["extensions"],
                "max_size_mb": self.SUPPORTED_TYPES["image"]["max_size"] / (1024 * 1024),
                "mime_types": self.SUPPORTED_TYPES["image"]["mime_types"]
            },
            "audio": {
                "extensions": self.SUPPORTED_TYPES["audio"]["extensions"],
                "max_size_mb": self.SUPPORTED_TYPES["audio"]["max_size"] / (1024 * 1024),
                "mime_types": self.SUPPORTED_TYPES["audio"]["mime_types"]
            }
        }

# 创建全局实例
file_detector = FileTypeDetector()
