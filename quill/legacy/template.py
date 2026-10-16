# Derived from BetaStreetOmnis/DocuGen; see docs/PROVENANCE.md.
from __future__ import annotations
from typing import Dict, Any, List, Optional, Union
import os
import re
import time
import uuid
from pathlib import Path
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

class BaseTemplatesGenerator:
    def __init__(self, output_dir: Path, template_dir: Path | None = None):
        self.output_dir = output_dir
        self.template_dir = template_dir or output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_from_template(self, template_name: str, data: Dict[str, Any]) -> str:
        """
        根据模板和数据生成文档

        Args:
            template_name: 模板名称
            data: 用于填充模板的数据

        Returns:
            生成的文档路径
        """
        if not template_name:
            raise ValueError("模板名称不能为空")

        template_path = str(self.template_dir / f"{template_name}.docx")
        if not os.path.exists(template_path):
            raise ValueError(f"模板 '{template_name}' 不存在")

        try:
            # 打开模板文档
            doc = Document(template_path)

            # 填充模板内容
            self._fill_template(doc, data)

            # 生成随机文件名，避免冲突
            filename = f"{uuid.uuid4().hex}.docx"
            file_path = str(self.output_dir / filename)
            doc.save(file_path)

            return file_path

        except Exception as e:
            raise Exception(f"生成文档时出错: {str(e)}")

    def _fill_template(self, doc: Document, data: Dict[str, Any]) -> None:
        """
        填充文档模板

        Args:
            doc: 文档对象
            data: 用于填充的数据
        """
        # 遍历所有段落
        for paragraph in doc.paragraphs:
            self._replace_text_in_paragraph(paragraph, data)

        # 遍历所有表格
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        self._replace_text_in_paragraph(paragraph, data)

    def _replace_text_in_paragraph(self, paragraph, data: Dict[str, Any]) -> None:
        """
        在段落中替换占位符，支持占位符被拆分到多个run中的情况。
        这是一个复杂的操作，因为占位符可能横跨多个具有不同格式的run。
        """
        for key, value in data.items():
            # 同时兼容【】和{{}}两种格式
            placeholders = [f"【{key}】", f"{{{{{key}}}}}"]
            for p_text in placeholders:
                # Replace original occurrences from the end; inserted values are never re-expanded.
                full_text = "".join(r.text for r in paragraph.runs)
                positions = [match.start() for match in re.finditer(re.escape(p_text), full_text)]
                for start_char_index in reversed(positions):
                    runs = paragraph.runs
                    # --- 定位占位符所在的 runs ---
                    end_char_index = start_char_index + len(p_text)

                    run_cursor = 0
                    start_run, end_run = None, None
                    start_run_idx, end_run_idx = -1, -1
                    start_offset, end_offset = -1, -1

                    for i, run in enumerate(runs):
                        run_len = len(run.text)
                        if start_run is None and run_cursor + run_len > start_char_index:
                            start_run = run
                            start_run_idx = i
                            start_offset = start_char_index - run_cursor
                        if end_run is None and run_cursor + run_len >= end_char_index:
                            end_run = run
                            end_run_idx = i
                            end_offset = end_char_index - run_cursor
                            break
                        run_cursor += run_len

                    # --- 执行替换 ---
                    if start_run is None or end_run is None:
                        # 如果没有找到起始或结束run，可能存在问题，跳出循环
                        break

                    if start_run_idx == end_run_idx:
                        # 占位符在单个run内
                        start_run.text = start_run.text[:start_offset] + str(value) + end_run.text[end_offset:]
                    else:
                        # 占位符横跨多个run
                        # 1. 修改起始run
                        start_run.text = start_run.text[:start_offset] + str(value)
                        # 2. 修改结束run
                        end_run.text = end_run.text[end_offset:]
                        # 3. 清空中间的runs
                        for i in range(start_run_idx + 1, end_run_idx):
                            runs[i].text = ""

    def extract_variables_from_template(self, template_path: str) -> List[Dict[str, str]]:
        """
        从Word模板中提取所有变量

        Args:
            template_path: 模板文件路径

        Returns:
            变量列表，每个变量是一个包含name和description的字典
        """
        import re

        if not os.path.exists(template_path):
            raise ValueError(f"模板文件 '{template_path}' 不存在")

        try:
            # 打开模板文档
            doc = Document(template_path)

            # 存储找到的变量
            variables = []
            found_vars = set()

            # 正则表达式匹配【变量名】或{{变量名}}格式
            var_pattern = re.compile(r'【([^】]+?)】|\{\{([^}]+?)\}\}')

            # 从段落中提取变量
            for paragraph in doc.paragraphs:
                matches = var_pattern.findall(paragraph.text)
                for match_tuple in matches:
                    # findall会返回元组，(中文匹配, 英文匹配)，取非空的一个
                    var_name = next((v for v in match_tuple if v), None)
                    if var_name:
                        var_name = var_name.strip()
                        if var_name and var_name not in found_vars:
                            found_vars.add(var_name)
                            variables.append({
                                "name": var_name,
                                "description": f"{var_name}的值",
                                "default_value": ""
                            })

            # 从表格中提取变量
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            matches = var_pattern.findall(paragraph.text)
                            for match_tuple in matches:
                                var_name = next((v for v in match_tuple if v), None)
                                if var_name:
                                    var_name = var_name.strip()
                                    if var_name and var_name not in found_vars:
                                        found_vars.add(var_name)
                                        variables.append({
                                            "name": var_name,
                                            "description": f"{var_name}的值",
                                            "default_value": ""
                                        })

            return variables

        except Exception as e:
            raise Exception(f"提取模板变量时出错: {str(e)}")

    def get_template_content(self, template_path: str) -> str:
        """
        获取模板文件的文本内容

        Args:
            template_path: 模板文件路径

        Returns:
            模板的文本内容
        """
        try:
            if not os.path.exists(template_path):
                raise ValueError(f"模板文件 '{template_path}' 不存在")

            # 打开模板文档
            doc = Document(template_path)

            # 收集所有文本内容
            content_parts = []

            # 从段落中提取文本
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    content_parts.append(paragraph.text)

            # 从表格中提取文本
            for table in doc.tables:
                for row in table.rows:
                    row_texts = []
                    for cell in row.cells:
                        cell_text = ' '.join(p.text.strip() for p in cell.paragraphs if p.text.strip())
                        if cell_text:
                            row_texts.append(cell_text)
                    if row_texts:
                        content_parts.append(' | '.join(row_texts))

            # 合并所有内容
            return '\n'.join(content_parts)

        except Exception as e:
            raise Exception(f"获取模板内容时出错: {str(e)}")
