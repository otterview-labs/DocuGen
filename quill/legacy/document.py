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

class DocumentGenerator:
    def __init__(self, output_dir: Path, template_dir: Path | None = None):
        self.output_dir = output_dir
        self.template_dir = template_dir or output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def clean_markdown_text(self, text: str) -> str:
        """
        移除Markdown格式中的特殊符号

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        # 移除*符号（同时保留文本）
        text = text.replace('*', '')
        # 移除其他可能的Markdown格式符号
        text = text.replace('`', '')
        text = text.replace('>', '')
        # 处理其他可能的格式符号
        text = text.replace('<br>', '')
        text = text.replace('<br/>', '')
        text = text.replace('&nbsp;', ' ')
        # 移除多余空格
        while '  ' in text:
            text = text.replace('  ', ' ')
        return text.strip()

    def process_document_headings(self, content: str) -> str:
        """
        处理文档中的标题，确保格式一致、层级合理且不重复

        Args:
            content: 原始内容

        Returns:
            处理后的内容
        """
        lines = content.split('\n')
        processed_lines = []
        seen_headings = {}  # 用于记录已经出现过的标题
        current_level = 0
        last_heading_level = 0

        for line in lines:
            line = line.strip()
            if not line:
                processed_lines.append('')
                continue

            # 检测是否是标题行
            heading_level = 0
            for i in range(4, 0, -1):  # 从#### 到 # 依次检查
                prefix = '#' * i + ' '
                if line.startswith(prefix):
                    heading_level = i
                    title_text = line[len(prefix):].strip()
                    title_text = self.clean_markdown_text(title_text)

                    # 标题内容清理和规范化
                    title_text = title_text.strip('.,;:')  # 移除可能的结尾标点

                    # 检查是否是重复或极度相似的标题
                    lower_title = title_text.lower()
                    if lower_title in seen_headings:
                        # 如果完全相同的标题已经存在，跳过这个标题
                        if seen_headings[lower_title] == heading_level:
                            continue

                    # 确保标题层级合理（不能从一级跳到三级）
                    if heading_level > last_heading_level + 1 and last_heading_level > 0:
                        heading_level = last_heading_level + 1

                    # 记录该标题
                    seen_headings[lower_title] = heading_level
                    last_heading_level = heading_level

                    # 更新为正确的标记和格式
                    line = '#' * heading_level + ' ' + title_text
                    break

            processed_lines.append(line)

        return '\n'.join(processed_lines)

    def export_to_doc(self, content: str, content_type: str = "outline") -> str:
        """
        将内容导出为Word文档

        Args:
            content: 要导出的内容
            content_type: 内容类型，"outline"或"fulltext"

        Returns:
            生成的文档路径
        """
        if not content:
            raise ValueError("内容不能为空")

        try:
            # 预处理内容，确保标题格式一致且不重复
            content = self.process_document_headings(content)

            # 创建Word文档
            doc = Document()

            # 设置文档基本属性
            core_properties = doc.core_properties
            core_properties.title = "智能文档生成器" + ("大纲" if content_type == "outline" else "完整文档")
            core_properties.language = "zh-CN"

            # 设置页面边距和纸张大小
            sections = doc.sections
            for section in sections:
                section.top_margin = Inches(1)
                section.bottom_margin = Inches(1)
                section.left_margin = Inches(1.25)
                section.right_margin = Inches(1.25)
                section.page_height = Inches(11.69)  # A4纸高度
                section.page_width = Inches(8.27)    # A4纸宽度

            # 获取主标题（从内容的第一行提取，如果有#号）
            main_title = "生成的文档"
            if content and "\n" in content:
                first_line = content.split('\n')[0].strip()
                if first_line.startswith("# "):
                    main_title = self.clean_markdown_text(first_line[2:].strip())

            # 添加封面
            doc.add_paragraph()  # Start the cover without a leading blank page.
            p = doc.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run("\n\n\n\n\n")  # 添加空行

            # 封面使用从内容提取的标题，而不是固定文本
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(main_title)
            run.font.size = Pt(26)
            run.font.name = '黑体'
            run.font.bold = True

            # 日期
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(f"\n\n{time.strftime('%Y年%m月%d日')}")
            run.font.size = Pt(12)
            run.font.name = '宋体'

            # 添加分页符开始正文
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

            # 添加目录（仅适用于全文）
            if content_type != "outline":
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = p.add_run("目 录")
                run.font.size = Pt(16)
                run.font.name = '黑体'
                run.font.bold = True

                doc.add_paragraph("\n")

                # 使用字段代码添加目录（这是一个占位符，Word会自动填充）
                field = OxmlElement("w:fldSimple")
                field.set(qn("w:instr"), 'TOC \\o "1-3" \\h \\z \\u')
                doc.add_paragraph()._p.append(field)

                # 添加分页符开始正文
                doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

            # 定义样式
            # 设置默认字体
            style = doc.styles['Normal']
            font = style.font
            font.name = '宋体'
            font.size = Pt(12)

            # 为不同级别标题设置样式
            for i in range(1, 5):
                heading_style = doc.styles[f'Heading {i}']
                heading_style.font.name = '黑体'
                heading_style.font.bold = True
                heading_style.font.size = Pt(18 - (i*2))  # 标题1-4级字体大小递减
                heading_style.paragraph_format.space_before = Pt(12)
                heading_style.paragraph_format.space_after = Pt(8)
                # 确保标题是黑色的
                heading_style.font.color.rgb = RGBColor(0, 0, 0)
                # 设置标题样式和段落格式
                heading_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
                heading_style.paragraph_format.keep_with_next = True  # 确保标题不会和内容分开

            # 解析内容并添加到文档
            if content_type == "outline":
                # 处理大纲内容
                lines = content.split("\n")
                current_level = 0
                is_first_heading = True  # 标记第一个标题

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    # 清理文本中的*符号
                    cleaned_line = self.clean_markdown_text(line)

                    # 根据行的格式确定标题级别，并确保移除#符号
                    if cleaned_line.startswith("# "):
                        if is_first_heading:
                            # 跳过第一个标题（已经在封面添加过）
                            is_first_heading = False
                            continue
                        title_text = cleaned_line[2:].strip()  # 确保清理干净
                        heading = doc.add_heading(title_text, level=1)
                        # 确保标题文本是黑色的
                        for run in heading.runs:
                            run.font.color.rgb = RGBColor(0, 0, 0)
                    elif cleaned_line.startswith("## "):
                        title_text = cleaned_line[3:].strip()
                        heading = doc.add_heading(title_text, level=2)
                        for run in heading.runs:
                            run.font.color.rgb = RGBColor(0, 0, 0)
                    elif cleaned_line.startswith("### "):
                        title_text = cleaned_line[4:].strip()
                        heading = doc.add_heading(title_text, level=3)
                        for run in heading.runs:
                            run.font.color.rgb = RGBColor(0, 0, 0)
                    elif cleaned_line.startswith("#### "):
                        title_text = cleaned_line[5:].strip()
                        heading = doc.add_heading(title_text, level=4)
                        for run in heading.runs:
                            run.font.color.rgb = RGBColor(0, 0, 0)
                    elif cleaned_line.startswith("- "):
                        p = doc.add_paragraph(cleaned_line[2:], style='List Bullet')
                        p.paragraph_format.left_indent = Inches(0.25)
                    else:
                        p = doc.add_paragraph(cleaned_line)
                        p.paragraph_format.first_line_indent = Pt(24)
            else:
                # 处理全文内容
                in_paragraph_block = False
                paragraph_text = ""

                lines = content.split("\n")
                is_first_heading = True  # 标记第一个标题

                for line in lines:
                    # 清理文本中的*符号
                    cleaned_line = self.clean_markdown_text(line.strip())

                    # 处理标题和缩进
                    if not cleaned_line:
                        if paragraph_text:
                            # 结束上一个段落块并添加
                            p = doc.add_paragraph()
                            p.paragraph_format.first_line_indent = Pt(24)
                            p.paragraph_format.line_spacing = 1.5
                            run = p.add_run(paragraph_text)
                            paragraph_text = ""
                        in_paragraph_block = False
                        continue

                    # 处理标题，确保移除#符号并设置为黑色
                    if cleaned_line.startswith("#"):
                        # 如果有缓存的段落文本，先添加
                        if paragraph_text:
                            p = doc.add_paragraph()
                            p.paragraph_format.first_line_indent = Pt(24)
                            p.paragraph_format.line_spacing = 1.5
                            run = p.add_run(paragraph_text)
                            paragraph_text = ""

                        # 根据行的格式确定标题级别并添加
                        if cleaned_line.startswith("# "):
                            if is_first_heading:
                                # 跳过第一个标题（已经在封面添加过）
                                is_first_heading = False
                                continue
                            title_text = cleaned_line[2:].strip()
                            heading = doc.add_heading(title_text, level=1)
                            for run in heading.runs:
                                run.font.color.rgb = RGBColor(0, 0, 0)
                        elif cleaned_line.startswith("## "):
                            title_text = cleaned_line[3:].strip()
                            heading = doc.add_heading(title_text, level=2)
                            for run in heading.runs:
                                run.font.color.rgb = RGBColor(0, 0, 0)
                        elif cleaned_line.startswith("### "):
                            title_text = cleaned_line[4:].strip()
                            heading = doc.add_heading(title_text, level=3)
                            for run in heading.runs:
                                run.font.color.rgb = RGBColor(0, 0, 0)
                        elif cleaned_line.startswith("#### "):
                            title_text = cleaned_line[5:].strip()
                            heading = doc.add_heading(title_text, level=4)
                            for run in heading.runs:
                                run.font.color.rgb = RGBColor(0, 0, 0)

                        in_paragraph_block = False

                    # 处理列表
                    elif cleaned_line.startswith("- "):
                        # 如果有缓存的段落文本，先添加
                        if paragraph_text:
                            p = doc.add_paragraph()
                            p.paragraph_format.first_line_indent = Pt(24)
                            p.paragraph_format.line_spacing = 1.5
                            run = p.add_run(paragraph_text)
                            paragraph_text = ""

                        p = doc.add_paragraph(cleaned_line[2:], style='List Bullet')
                        p.paragraph_format.left_indent = Inches(0.25)
                        in_paragraph_block = False

                    # 处理普通段落
                    else:
                        # 累积段落文本
                        if not in_paragraph_block:
                            in_paragraph_block = True
                            paragraph_text = cleaned_line
                        else:
                            paragraph_text += " " + cleaned_line

                # 添加最后一个可能未处理的段落
                if paragraph_text:
                    p = doc.add_paragraph()
                    p.paragraph_format.first_line_indent = Pt(24)
                    p.paragraph_format.line_spacing = 1.5
                    run = p.add_run(paragraph_text)

            # 添加页码
            section = doc.sections[-1]
            footer = section.footer
            p = footer.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            # 使用正确的页码添加方法
            p.text = "第 "
            run = p.add_run()
            fldChar = OxmlElement('w:fldChar')
            fldChar.set(qn('w:fldCharType'), 'begin')
            instrText = OxmlElement('w:instrText')
            instrText.set(qn('xml:space'), 'preserve')
            instrText.text = 'PAGE'
            fldChar2 = OxmlElement('w:fldChar')
            fldChar2.set(qn('w:fldCharType'), 'end')

            run._element.append(fldChar)
            run._element.append(instrText)
            run._element.append(fldChar2)
            p.add_run(" 页")

            # 生成随机文件名，避免冲突
            filename = f"{uuid.uuid4().hex}.docx"
            file_path = str(self.output_dir / filename)
            doc.save(file_path)

            return file_path

        except Exception as e:
            raise Exception(f"创建Word文档时出错: {str(e)}")
