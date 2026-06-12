"""多格式文档加载器"""

from pathlib import Path
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    TextLoader,
    PyMuPDFLoader,
    Docx2txtLoader,
    UnstructuredExcelLoader,
)
from src.rag.cleaner import clean_wechat_html


class WeChatHTMLLoader:
    """微信公众号 HTML 加载器。

    与 langchain 内置 BSHTMLLoader 不同，本加载器走 cleaner.clean_wechat_html
    自定义清洗流程：剥噪声、提取 JS 元数据、剥 base64 图片（详见 cleaner.py）。
    """

    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self) -> list[Document]:
        """加载并清洗 WeChat HTML，返回单个 Document 列表。"""
        try:
            raw = Path(self.file_path).read_bytes()
        except FileNotFoundError as exc:
            raise ValueError(f"文件不存在: {self.file_path}") from exc

        text, meta = clean_wechat_html(raw, source_path=self.file_path)
        # source 字段沿用基线（与 vectorstore.add_documents 的 "source" 一致）
        meta.setdefault("source", Path(self.file_path).name)
        return [Document(page_content=text, metadata=meta)]


LOADER_MAP = {
    ".txt": lambda path: TextLoader(path, encoding="utf-8"),
    ".md": lambda path: TextLoader(path, encoding="utf-8"),
    ".pdf": lambda path: PyMuPDFLoader(path),
    ".docx": lambda path: Docx2txtLoader(path),
    ".xlsx": lambda path: UnstructuredExcelLoader(path),
    ".xls": lambda path: UnstructuredExcelLoader(path),
    ".html": WeChatHTMLLoader,
    ".htm": WeChatHTMLLoader,
}

SUPPORTED_FORMATS = ", ".join(sorted(LOADER_MAP.keys()))


def load_document(file_path: str) -> list[Document]:
    """加载单个文档，返回 Document 列表。

    Raises:
        ValueError: 不支持的文件格式 / 文件不存在
    """
    ext = Path(file_path).suffix.lower()
    loader_factory = LOADER_MAP.get(ext)
    if not loader_factory:
        raise ValueError(f"不支持的文件格式: {ext}。支持的格式: {SUPPORTED_FORMATS}")
    loader = loader_factory(file_path)
    return loader.load()
