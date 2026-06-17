"""Chroma Cloud 向量存储管理(简化版)。

只用 dense 嵌入(Chroma Cloud Qwen3-Embedding-0.6B),走最简单的 col.query() API。
无 Rrf / Splade / GroupBy / 2-step search,代码量 < 100 行。
"""

from __future__ import annotations

import hashlib

import chromadb
from chromadb.utils.embedding_functions import ChromaCloudQwenEmbeddingFunction
from chromadb.utils.embedding_functions.chroma_cloud_qwen_embedding_function import (
    ChromaCloudQwenEmbeddingModel,
)
from langchain_core.documents import Document

from src.config import settings


class VectorStore:
    """Chroma Cloud 向量存储封装。"""

    def __init__(
        self,
        persist_dir: str | None = None,  # noqa: ARG002 - 兼容旧签名,Cloud 模式忽略
        embedding_model: str | None = None,  # noqa: ARG002 - 兼容旧签名,Cloud 模式忽略
    ):
        if not settings.chroma_api_key:
            raise RuntimeError(
                "CHROMA_API_KEY 未配置。请在 .env 设置 CHROMA_API_KEY=ck-... 后重启服务。"
            )

        self._client = chromadb.CloudClient(
            cloud_host=settings.chroma_host,
            cloud_port=settings.chroma_port,
            api_key=settings.chroma_api_key,
            tenant=settings.chroma_tenant,
            database=settings.chroma_database,
        )
        self._collection = None  # 懒加载

    def _get_collection(self):
        """懒加载 collection:首次访问时按默认 EF 初始化。"""
        if self._collection is None:
            # Cloud 端托管的 dense 嵌入函数(从 CHROMA_API_KEY 环境变量读 key)
            # task=None → Cloud 端用空 instructions(通用文本),适合中英混排的 RAG
            qwen_ef = ChromaCloudQwenEmbeddingFunction(
                model=ChromaCloudQwenEmbeddingModel.QWEN3_EMBEDDING_0p6B,
                task=None,
                api_key_env_var="CHROMA_API_KEY",
            )
            self._collection = self._client.get_or_create_collection(
                name=settings.chroma_collection,
                embedding_function=qwen_ef,
            )
        return self._collection

    def close(self) -> None:
        """no-op(Cloud 客户端无文件锁概念)。"""
        pass

    def add_documents(self, docs: list[Document], filename: str) -> int:
        """添加文档到向量存储,返回 chunk 数量。

        Cloud 端在收到 documents 后自动调用 hosted embedding 完成嵌入。
        元数据继承与隔离:重建新 dict 防止跨调用 metadata 引用污染。
        """
        if not docs:
            return 0

        col = self._get_collection()
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for i, doc in enumerate(docs):
            meta = dict(doc.metadata)  # 隔离:防止引用污染
            meta["source"] = filename
            meta["chunk_id"] = i
            # id 前缀优先用 content_hash(dedup 流程注入),无则用 filename 的短 hash 兜底。
            # 不能直接拿 filename 当 id 前缀:中文长标题 UTF-8 编码后易超 Chroma Cloud
            # 的 ID 字节数配额(128B),导致 "ID size exceeded quota" 入库失败。
            # 完整文件名仍保留在 metadata["source"] 供检索/列表/删除使用,不受 ID 限制。
            ch = meta.get("content_hash")
            id_prefix = ch if ch else hashlib.sha1(filename.encode("utf-8")).hexdigest()
            ids.append(f"{id_prefix}::chunk-{i}")
            documents.append(doc.page_content)
            metadatas.append(meta)

        col.add(documents=documents, metadatas=metadatas, ids=ids)
        return len(docs)

    def search(self, query: str, k: int = 4) -> list[Document]:
        """相似度搜索(单次往返,Cloud 端嵌入 + 检索)。"""
        col = self._get_collection()
        results = col.query(query_texts=[query], n_results=k)

        docs_out: list[Document] = []
        # query() 返回嵌套 list,外层是 query 维度(我们只发 1 个 query → [0])
        for i, doc_text in enumerate(results.get("documents", [[]])[0] or []):
            metas = results.get("metadatas", [[]])[0] or []
            meta = metas[i] if i < len(metas) else {}
            docs_out.append(Document(page_content=doc_text or "", metadata=meta or {}))
        return docs_out

    def delete_by_filename(self, filename: str) -> None:
        """根据文件名删除所有相关 chunks(走 where filter)。"""
        col = self._get_collection()
        col.delete(where={"source": filename})

    def list_documents(self) -> list[dict]:
        """列出已入库的文档(按 filename 聚合 chunk_count)。

        分页拉取全部 metadata:Chroma Cloud 对单次 get() 的 LimitValue 配额
        上限为 300,超过会报 "Limit value exceeded quota"。故以 200 为批分页,
        累计聚合,避免库增大后只统计到前 300 条 chunk。
        """
        col = self._get_collection()
        metas: list[dict] = []
        batch = 200  # 留余量,低于 Cloud Get 的 300 配额上限
        offset = 0
        while True:
            results = col.get(include=["metadatas"], limit=batch, offset=offset)
            batch_metas = results.get("metadatas") or []
            if not batch_metas:
                break
            metas.extend(batch_metas)
            if len(batch_metas) < batch:
                break
            offset += batch
        if not metas:
            return []

        doc_map: dict[str, dict] = {}
        for meta in metas:
            fname = meta.get("source", "unknown")
            if fname not in doc_map:
                doc_map[fname] = {"filename": fname, "chunk_count": 0}
            doc_map[fname]["chunk_count"] += 1
        return list(doc_map.values())

    def exists_by_metadata(self, where: dict, limit: int = 1) -> bool:
        """按 metadata where filter 查 Chroma,返回是否存在(供 DedupIndex 用)。"""
        col = self._get_collection()
        results = col.get(where=where, limit=limit)
        return bool(results and results.get("ids"))
