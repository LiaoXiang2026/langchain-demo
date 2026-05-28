"""多格式文档加载器"""

from pathlib import Path
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    TextLoader,
    PyMuPDFLoader,
    Docx2txtLoader,
    UnstructuredExcelLoader,
)

LOADER_MAP = {
    ".txt": lambda path: TextLoader(path, encoding="utf-8"),
    ".md": lambda path: TextLoader(path, encoding="utf-8"),
    ".pdf": lambda path: PyMuPDFLoader(path),
    ".docx": lambda path: Docx2txtLoader(path),
    ".xlsx": lambda path: UnstructuredExcelLoader(path),
    ".xls": lambda path: UnstructuredExcelLoader(path),
}

SUPPORTED_FORMATS = ", ".join(sorted(LOADER_MAP.keys()))


def load_document(file_path: str) -> list[Document]:
    """加载单个文档，返回 Document 列表。

    Raises:
        ValueError: 不支持的文件格式
    """
    ext = Path(file_path).suffix.lower()
    loader_factory = LOADER_MAP.get(ext)
    if not loader_factory:
        raise ValueError(f"不支持的文件格式: {ext}。支持的格式: {SUPPORTED_FORMATS}")
    loader = loader_factory(file_path)
    return loader.load()
