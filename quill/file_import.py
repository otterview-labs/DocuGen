"""Extract text for knowledge ingestion; OCR is deliberately not simulated."""

import io
import zipfile
from pathlib import Path

from docx import Document
from docx.table import Table
from pypdf import PdfReader

SUPPORTED = {".pdf", ".docx", ".md", ".txt", ".csv", ".json"}


class ImportError(Exception):
    pass


def extract_text(data: bytes, filename: str, max_expanded_mb: int = 100) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED:
        raise ImportError("支持 PDF、DOCX、Markdown、TXT、CSV 和 JSON，请先转换其他格式。")
    try:
        if suffix == ".pdf":
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted and not reader.decrypt(""):
                raise ImportError("PDF 已加密，请解除密码后重新导入。")
            if len(reader.pages) > 200:
                raise ImportError("PDF 超过 200 页，请拆分后导入。")
            parts = []
            for page in reader.pages:
                parts.append(page.extract_text() or "")
                if sum(len(part) for part in parts) > 200000:
                    raise ImportError("资料超过 20 万字符，请拆分后导入。")
            text = "\n\n".join(parts)
        elif suffix == ".docx":
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sum(item.file_size for item in archive.infolist()) > max_expanded_mb * 1024 * 1024:
                    raise ImportError("Word 文档解压后过大，请拆分后导入。")
            document = Document(io.BytesIO(data))
            parts = []
            for element in document.iter_inner_content():
                if isinstance(element, Table):
                    parts.extend(" | ".join(cell.text for cell in row.cells) for row in element.rows)
                else:
                    parts.append(element.text)
            text = "\n\n".join(parts)
        else:
            try:
                text = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = data.decode("gb18030")
        text = text.replace("\r\n", "\n").strip()
        if "\x00" in text:
            raise ImportError("文件包含无法读取的二进制内容，请另存为文本格式。")
        if not text:
            raise ImportError("未提取到文字。扫描版 PDF 需要先进行 OCR 识别。")
        if len(text) > 200000:
            raise ImportError("资料超过 20 万字符，请拆分后导入。")
        return text
    except ImportError:
        raise
    except Exception as exc:
        raise ImportError("文件解析失败，请检查文件是否损坏或转换为可读取的文本。") from exc
