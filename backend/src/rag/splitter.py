"""文档分块"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

CHINESE_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", " "]


def split_documents(
    docs: list[Document],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[Document]:
    """将文档列表分块。"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=CHINESE_SEPARATORS,
    )
    return splitter.split_documents(docs)
