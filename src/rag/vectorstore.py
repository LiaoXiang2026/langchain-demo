"""本地 numpy 向量存储管理。

用 sentence-transformers 本地加载 Qwen3-Embedding-0.6B 做嵌入，
numpy 矩阵存向量，JSON 存文本/元数据。检索走 numpy 余弦相似度。
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

import numpy as np
from langchain_core.documents import Document
from sentence_transformers import SentenceTransformer

from src.config import settings


class VectorStore:
    """本地 numpy 向量存储。"""

    def __init__(self, data_dir: str | None = None):
        self._data_dir = Path(data_dir or settings.data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._chunks_path = self._data_dir / "chunks.json"
        self._embeddings_path = self._data_dir / "embeddings.npy"
        self._documents_path = self._data_dir / "documents.json"

        # 加载已有数据
        self._chunks: list[dict] = []
        self._embeddings: np.ndarray | None = None  # (N, dim)
        self._documents: dict[str, dict] = {}

        self._load()

        # 延迟加载嵌入模型(首次 encode 时初始化)
        self._model: SentenceTransformer | None = None
        self._model_lock = threading.Lock()
        self._write_lock = threading.Lock()

    def _load(self) -> None:
        """从磁盘加载 chunks/embeddings/documents。"""
        if self._chunks_path.exists():
            self._chunks = json.loads(self._chunks_path.read_text(encoding="utf-8"))
        if self._embeddings_path.exists():
            try:
                self._embeddings = np.load(self._embeddings_path)
                if self._embeddings.ndim == 1:
                    self._embeddings = self._embeddings.reshape(1, -1)
            except (ValueError, OSError) as e:
                import logging
                logging.getLogger(__name__).warning(
                    "嵌入文件损坏，忽略: %s", e
                )
                self._embeddings = None
        if self._documents_path.exists():
            self._documents = json.loads(self._documents_path.read_text(encoding="utf-8"))
        # 一致性检查
        if self._embeddings is not None and len(self._chunks) != self._embeddings.shape[0]:
            import logging
            logging.getLogger(__name__).warning(
                "chunks 与 embeddings 行数不一致(%d vs %d)，重置",
                len(self._chunks), self._embeddings.shape[0],
            )
            self._chunks = []
            self._embeddings = None

    def _persist_chunks(self) -> None:
        """持久化 chunks.json + embeddings.npy(原子写入)。"""
        tmp_chunks = self._chunks_path.with_suffix(".json.tmp")
        tmp_chunks.write_text(
            json.dumps(self._chunks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp_chunks, self._chunks_path)
        if self._embeddings is not None and self._embeddings.size > 0:
            tmp_emb = self._embeddings_path.with_stem(self._embeddings_path.stem + "_tmp")
            np.save(tmp_emb, self._embeddings)
            os.replace(tmp_emb, self._embeddings_path)

    def _persist_documents(self) -> None:
        """持久化 documents.json。"""
        self._documents_path.write_text(
            json.dumps(self._documents, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _get_model(self) -> SentenceTransformer:
        """懒加载嵌入模型(线程安全,首次调用时下载/加载)。"""
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    self._model = SentenceTransformer(
                        settings.embedding_model,
                        trust_remote_code=True,
                    )
        return self._model

    def _encode(self, texts: list[str]) -> np.ndarray:
        """将文本列表编码为嵌入矩阵 (len(texts), dim)。"""
        model = self._get_model()
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,  # 归一化后点积即余弦相似度
            show_progress_bar=False,
        )
        return np.array(embeddings, dtype=np.float32)

    def close(self) -> None:
        """no-op。"""

    # ---- 对外接口(与 Chroma 版本签名一致) ----

    def add_documents(self, docs: list[Document], filename: str) -> int:
        """添加文档到向量存储，返回 chunk 数量。"""
        if not docs:
            return 0
        with self._write_lock:
            texts = [doc.page_content for doc in docs]
            new_embeddings = self._encode(texts)  # (N, dim)

            # 追加 chunks
            for i, doc in enumerate(docs):
                meta = dict(doc.metadata)
                meta["source"] = filename
                meta["chunk_id"] = i
                ch = meta.get("content_hash")
                id_prefix = ch if ch else hashlib.sha1(filename.encode("utf-8")).hexdigest()
                self._chunks.append({
                    "id": f"{id_prefix}::chunk-{i}",
                    "doc_id": filename,
                    "chunk_i": i,
                    "text": doc.page_content,
                    "metadata": meta,
                })

            # 追加嵌入矩阵
            if self._embeddings is None:
                self._embeddings = new_embeddings
            else:
                self._embeddings = np.vstack([self._embeddings, new_embeddings])

            self._persist_chunks()
            return len(docs)

    def search(self, query: str, k: int = 4) -> list[Document]:
        """相似度搜索(余弦相似度,已归一化向量点积等价于余弦)。"""
        if self._embeddings is None or len(self._chunks) == 0:
            return []

        q_vec = self._encode([query])[0]  # (dim,)
        scores = np.dot(self._embeddings, q_vec)
        # 取 top-k(降序)
        if k >= len(scores):
            top_indices = np.argsort(scores)[::-1]
        else:
            top_indices = np.argpartition(scores, -k)[-k:]
            top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

        results: list[Document] = []
        for idx in top_indices:
            if scores[idx] <= 0:
                continue
            chunk = self._chunks[idx]
            results.append(Document(
                page_content=chunk["text"],
                metadata=chunk.get("metadata", {}),
            ))
        return results

    def delete_by_filename(self, filename: str) -> None:
        """根据文件名删除所有相关 chunks。"""
        with self._write_lock:
            keep_indices = [
                i for i, c in enumerate(self._chunks)
                if c.get("doc_id") != filename
            ]
            if len(keep_indices) == len(self._chunks):
                return  # 没有匹配的

            self._chunks = [self._chunks[i] for i in keep_indices]
            if self._embeddings is not None:
                self._embeddings = self._embeddings[keep_indices]

            self._persist_chunks()

    def list_documents(self) -> list[dict]:
        """列出已入库的文档(按 filename 聚合 chunk_count)。"""
        doc_map: dict[str, dict] = {}
        for chunk in self._chunks:
            fname = chunk.get("doc_id") or chunk.get("metadata", {}).get("source", "unknown")
            if fname not in doc_map:
                doc_map[fname] = {"filename": fname, "chunk_count": 0}
            doc_map[fname]["chunk_count"] += 1
        return list(doc_map.values())

    def exists_by_metadata(self, where: dict, limit: int = 1) -> bool:
        """按 metadata 字段查重(供 DedupIndex 用)。

        where 形如 {"content_hash": "sha256..."}，
        扫描 chunks 的 metadata，命中即返回 True。
        """
        count = 0
        for chunk in self._chunks:
            meta = chunk.get("metadata", {})
            if all(meta.get(k) == v for k, v in where.items()):
                count += 1
                if count >= limit:
                    return True
        return False

    # ---- 供 Classifier 使用的内部方法 ----

    def get_all_chunks(self) -> list[dict]:
        """返回所有 chunks(含 metadata),供分类器聚合篇级向量。"""
        return list(self._chunks)

    def get_all_embeddings(self) -> np.ndarray | None:
        """返回嵌入矩阵,供分类器使用。"""
        return self._embeddings

    def get_documents(self) -> dict[str, dict]:
        """返回 documents.json 内容。"""
        return dict(self._documents)

    def save_document(self, doc_id: str, data: dict) -> None:
        """保存/更新单篇文档信息到 documents.json。"""
        with self._write_lock:
            self._documents[doc_id] = data
            self._persist_documents()
