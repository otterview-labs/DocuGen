# ！/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@Time   : 2025/8/1 14:00
@Author : 13594053100@163.com
@File   : file_utils.py
"""
import logging
from typing import List
import os

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
class FileUtils:

    @staticmethod
    def collect_file_paths_from_folder(folder_path: str, extensions: List[str]=['.jpg', '.jpeg', '.png', '.bmp','.svg']) -> list[str]:
        """
        收集指定文件夹下指定格式的所有文件路径。

        :param folder_path: 关键帧所在文件夹路径
        :param extensions: 支持的格式后缀列表，默认常见图片格式
        :return: 图片文件路径列表（按文件名排序）
        """

        if not os.path.isdir(folder_path):
            raise ValueError(f"指定路径不是有效文件夹: {folder_path}")

        file_paths_list = []
        for filename in os.listdir(folder_path):
            if any(filename.lower().endswith(ext) for ext in extensions):
                full_path = os.path.join(folder_path, filename)
                file_paths_list.append(full_path)

        # 按文件名排序
        file_paths_list.sort()
        # 如需按修改时间倒序，改为：
        # file_paths_list.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        return file_paths_list

    @staticmethod
    def sanitize_tag(tag: str,illegal:str) -> str:
        """清理标签字符串，替换非法字符

        Args:
            tag (str): 原始标签字符串。
            illegal(str)：非法字符集

        Returns:
            str: 清理后的标签字符串（非法字符被替换为下划线）。
        """
        tag = (tag or "").strip()
        return "".join("_" if ch in illegal else ch for ch in tag)
