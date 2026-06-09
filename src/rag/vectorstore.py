"""ChromaDB 向量存储管理"""

from pathlib import Path
from langchain_core.documents import Document
from langchain_chroma import Chroma
from src.rag.embeddings import get_embeddings


class VectorStore:
    def __init__(self, persist_dir: str, embedding_model: str = "shibing624/text2vec-base-chinese"):
        self.persist_dir = persist_dir
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self._embeddings = get_embeddings(embedding_model)
        self._store = Chroma(
            persist_directory=persist_dir,
            embedding_function=self._embeddings,
        )

    def close(self) -> None:
        """关闭 ChromaDB 连接，释放文件锁。"""
        try:
            self._store._client.close()  # type: ignore[attr-defined]
        except Exception:
            pass

    def add_documents(self, docs: list[Document], filename: str) -> int:
        """添加文档到向量存储，返回 chunk 数量。"""
        for i, doc in enumerate(docs):
            doc.metadata["source"] = filename
            doc.metadata["chunk_id"] = i
        self._store.add_documents(docs)
        return len(docs)

    def search(self, query: str, k: int = 4) -> list[Document]:
        """相似度搜索。"""
        return self._store.similarity_search(query, k=k)

    def delete_by_filename(self, filename: str) -> None:
        """根据文件名删除所有相关 chunks。"""
        results = self._store.get(where={"source": filename})
        if results and results["ids"]:
            self._store.delete(ids=results["ids"])

    def list_documents(self) -> list[dict]:
        """列出已入库的文档信息。"""
        results = self._store.get()
        if not results or not results["metadatas"]:
            return []

        doc_map: dict[str, dict] = {}
        for meta in results["metadatas"]:
            fname = meta.get("source", "unknown")
            if fname not in doc_map:
                doc_map[fname] = {"filename": fname, "chunk_count": 0}
            doc_map[fname]["chunk_count"] += 1
        return list(doc_map.values())
