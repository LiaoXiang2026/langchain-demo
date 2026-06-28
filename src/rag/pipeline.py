"""文档处理管线：加载→分块→嵌入→存储。

本模块提供两套入口:
  - ingest(file_path):Phase 1 既有的单文件加载入口,走 LOADER_MAP,不去重(向后兼容)
  - ingest_batch(file_paths):Phase 2 批量入口,专用于 WeChat HTML,走 cleaner + dedup_index 短路
  - ingest_cleaned(text, meta, content_hash):底层接口,接受已清洗文本,可被 ingest_batch
    或上游 server 路由复用(如批量上传 API 已在请求层做了清洗)

dedup 短路保证 D-09:重复文档不再走嵌入(节省算力),仅在响应里说明 "skip_count"。
"""

import hashlib
from datetime import datetime
from pathlib import Path

from langchain_core.documents import Document

from src.config import settings
from src.rag.cleaner import clean_wechat_html
from src.rag.dedup import DedupIndex
from src.rag.document_loader import load_document
from src.rag.splitter import split_documents
from src.rag.vectorstore import VectorStore


class DocumentPipeline:
    def __init__(
        self,
        data_dir: str | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self._store = VectorStore(data_dir=data_dir)
        self.dedup_index = DedupIndex(self._store)

    def ingest(self, file_path: str) -> dict:
        """处理单个文档：加载→分块→存入向量库。"""
        filename = Path(file_path).name
        docs = load_document(file_path)
        chunks = split_documents(docs, self.chunk_size, self.chunk_overlap)
        count = self._store.add_documents(chunks, filename=filename)
        # 保存文档元信息到 documents.json
        self._store.save_document(filename, {
            "title": filename,
            "author": "",
            "publish_date": "",
            "text": "\n".join(doc.page_content for doc in docs),
            "content_hash": hashlib.sha256(
                "\n".join(doc.page_content for doc in docs).encode("utf-8")
            ).hexdigest(),
            "source_path": file_path,
            "chunk_count": count,
            "ingested_at": datetime.now().isoformat(),
        })
        return {"filename": filename, "chunk_count": count}

    def ingest_cleaned(
        self,
        text: str,
        meta: dict,
        content_hash: str | None = None,
    ) -> dict:
        """处理已清洗的文本:dedup 短路 → 分块 → 入库。

        若 content_hash 命中 dedup_index,直接返回 status=duplicate(不走嵌入)。
        否则注入 content_hash + ingested_at 到 metadata,分块写入 ChromaDB。

        Args:
            text: 清洗后的正文(utf-8)
            meta: cleaner 输出的元数据(title/author/publish_date/source/source_path 等)
            content_hash: 可选,若 None 则就地计算

        Returns:
            {"status": "duplicate"|"new", "content_hash": str, "chunk_count": int}
        """
        if content_hash is None:
            content_hash = DedupIndex.compute_hash(text)

        # dedup 短路:不进嵌入,节省算力(D-09)
        if self.dedup_index.exists(content_hash):
            return {
                "status": "duplicate",
                "content_hash": content_hash,
                "chunk_count": 0,
            }

        merged_meta = {
            **meta,
            "content_hash": content_hash,
            "ingested_at": datetime.now().isoformat(),
        }
        doc = Document(page_content=text, metadata=merged_meta)
        chunks = split_documents([doc], self.chunk_size, self.chunk_overlap)
        # 文件名优先用 source_path 推导:
        #   - index.html 这类通用名(微信存档形如 "2023-09-11 标题/index.html")无辨识度,
        #     且多篇文章会撞名导致 Chroma id 冲突,改用父目录名(含日期+标题)
        #   - 其余文件用 basename
        source_path = meta.get("source_path") or meta.get("source") or "unknown"
        p = Path(str(source_path))
        if p.stem in ("index",) and p.parent.name:
            filename = p.parent.name
        else:
            filename = p.name or "unknown"
        count = self._store.add_documents(chunks, filename=filename)
        # 保存文档元信息到 documents.json
        self._store.save_document(filename, {
            **merged_meta,
            "text": text,
            "source_path": str(source_path),
            "chunk_count": count,
            "ingested_at": merged_meta["ingested_at"],
        })
        return {
            "status": "new",
            "content_hash": content_hash,
            "chunk_count": count,
        }

    def ingest_batch(self, file_paths: list[str]) -> dict:
        """批量入库 WeChat HTML:逐个走 cleaner + dedup 短路。

        单文件解析失败不中断整个批次(V7 错误处理),错误塞 errors 数组。

        Returns:
            {
                "new_count": int,        # 实际入库的文件数
                "skip_count": int,       # dedup 命中跳过的文件数
                "errors": [{"file": str, "error": str}, ...],
                "results": [{"file": str, **ingest_cleaned 返回}, ...]
            }
        """
        new_count = 0
        skip_count = 0
        errors: list[dict] = []
        results: list[dict] = []

        for file_path in file_paths:
            try:
                raw = Path(file_path).read_bytes()
                text, meta = clean_wechat_html(raw, source_path=file_path)
                content_hash = DedupIndex.compute_hash(text)
                result = self.ingest_cleaned(text, meta, content_hash=content_hash)
                if result["status"] == "duplicate":
                    skip_count += 1
                else:
                    new_count += 1
                results.append({"file": file_path, **result})
            except Exception as exc:  # noqa: BLE001 — 批次容错,需吞所有异常
                errors.append({"file": file_path, "error": str(exc)})

        return {
            "new_count": new_count,
            "skip_count": skip_count,
            "errors": errors,
            "results": results,
        }

    def search(self, query: str, k: int | None = None) -> list[Document]:
        """搜索知识库。"""
        return self._store.search(query, k=k or settings.search_top_k)

    def delete(self, filename: str) -> None:
        """删除指定文档。"""
        self._store.delete_by_filename(filename)

    def list_documents(self) -> list[dict]:
        """列出已入库文档。"""
        return self._store.list_documents()
