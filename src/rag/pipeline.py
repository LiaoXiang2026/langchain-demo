"""文档处理管线：加载→分块→嵌入→存储"""

from pathlib import Path
from langchain_core.documents import Document
from src.rag.document_loader import load_document
from src.rag.splitter import split_documents
from src.rag.vectorstore import VectorStore
from src.config import settings


class DocumentPipeline:
    def __init__(
        self,
        persist_dir: str | None = None,
        embedding_model: str | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        self.persist_dir = persist_dir or settings.chroma_dir
        self.embedding_model = embedding_model or settings.embedding_model
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self._store = VectorStore(
            persist_dir=self.persist_dir,
            embedding_model=self.embedding_model,
        )

    def ingest(self, file_path: str) -> dict:
        """处理单个文档：加载→分块→存入向量库。"""
        filename = Path(file_path).name
        docs = load_document(file_path)
        chunks = split_documents(docs, self.chunk_size, self.chunk_overlap)
        count = self._store.add_documents(chunks, filename=filename)
        return {"filename": filename, "chunk_count": count}

    def search(self, query: str, k: int | None = None) -> list[Document]:
        """搜索知识库。"""
        return self._store.search(query, k=k or settings.search_top_k)

    def delete(self, filename: str) -> None:
        """删除指定文档。"""
        self._store.delete_by_filename(filename)

    def list_documents(self) -> list[dict]:
        """列出已入库文档。"""
        return self._store.list_documents()
