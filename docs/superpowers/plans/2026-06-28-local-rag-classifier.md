# 本地 RAG + 自动分类系统 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除 Chroma Cloud 依赖，改用本地 numpy 存储 + Qwen3-Embedding-0.6B，新增 LLM 自动聚类分类管线。

**Architecture:** VectorStore 从 Chroma Cloud 封装重写为 numpy/json 文件存储（`chunks.json` + `embeddings.npy` + `documents.json`），检索走 numpy 余弦相似度。新增 DocumentClassifier 走 KMeans 嵌入聚类 + LLM 起名，结果写入 `clusters.json`。Pipeline/Server 接口不变。

**Tech Stack:** sentence-transformers (Qwen3-Embedding-0.6B), scikit-learn (KMeans), numpy, FastAPI, LangChain (Agent 层保留)

---

### Task 1: 更新依赖配置

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 替换 chromadb 为 sentence-transformers + scikit-learn**

```toml
[project]
name = "my-app-py"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "beautifulsoup4>=4.15.0",
    "chardet>=7.4.3",
    "fastapi>=0.115.0",
    "langchain>=1.3.2",
    "langchain-community>=0.0.1",
    "langchain-openai>=1.2.2",
    "langchain-text-splitters>=0.0.1",
    "lxml>=6.1.1",
    "numpy>=1.26",
    "pymupdf>=1.23.0",
    "python-dotenv>=1.2.2",
    "python-multipart>=0.0.29",
    "scikit-learn>=1.4",
    "sentence-transformers>=3.0",
    "uvicorn>=0.34.0",
]

[dependency-groups]
dev = [
    "pytest>=9.0.3",
]
```

- [ ] **Step 2: 同步依赖**

```bash
uv sync
```

Expected: 无错误，chromadb 被移除，sentence-transformers + scikit-learn + numpy 被安装。

- [ ] **Step 3: 验证关键包可导入**

```bash
uv run python -c "import numpy; import sklearn; import sentence_transformers; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): 替换 chromadb 为 sentence-transformers + scikit-learn + numpy"
```

---

### Task 2: 更新配置

**Files:**
- Modify: `src/config/settings.py`

- [ ] **Step 1: 重写 settings.py**

```python
"""配置管理"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # LLM 配置(DeepSeek,OpenAI 兼容接口)
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"

    # Agent 配置
    temperature: float = 0.7
    max_tokens: int = 2048

    # 本地存储配置
    data_dir: str = "data"
    upload_dir: str = "data/uploads"

    # 嵌入模型配置(HuggingFace)
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"

    # 分块与检索参数
    chunk_size: int = 500
    chunk_overlap: int = 50
    search_top_k: int = 4

    # 聚类参数
    recluster_k_min: int = 5
    recluster_k_max: int = 10

    def __post_init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY") or self.api_key
        self.base_url = os.getenv("DEEPSEEK_BASE_URL") or self.base_url
        self.model = os.getenv("MODEL_NAME") or self.model
        self.data_dir = os.getenv("DATA_DIR") or self.data_dir
        self.upload_dir = os.getenv("UPLOAD_DIR") or self.upload_dir
        self.embedding_model = os.getenv("EMBEDDING_MODEL") or self.embedding_model


settings = Settings()
```

- [ ] **Step 2: 验证配置导入**

```bash
uv run python -c "from src.config import settings; print(settings.data_dir, settings.embedding_model)"
```

Expected: `data Qwen/Qwen3-Embedding-0.6B`

- [ ] **Step 3: Commit**

```bash
git add src/config/settings.py
git commit -m "refactor(config): 移除 Chroma Cloud 配置，新增本地存储和嵌入模型配置"
```

---

### Task 3: 重写 VectorStore (numpy 本地存储)

**Files:**
- Modify: `src/rag/vectorstore.py`

- [ ] **Step 1: 写完整重写**

```python
"""本地 numpy 向量存储管理。

用 sentence-transformers 本地加载 Qwen3-Embedding-0.6B 做嵌入，
numpy 矩阵存向量，JSON 存文本/元数据。检索走 numpy 余弦相似度。
"""

from __future__ import annotations

import hashlib
import json
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

    def _load(self) -> None:
        """从磁盘加载 chunks/embeddings/documents。"""
        if self._chunks_path.exists():
            self._chunks = json.loads(self._chunks_path.read_text(encoding="utf-8"))
        if self._embeddings_path.exists():
            self._embeddings = np.load(self._embeddings_path)
            if self._embeddings.ndim == 1:
                self._embeddings = self._embeddings.reshape(1, -1)
        if self._documents_path.exists():
            self._documents = json.loads(self._documents_path.read_text(encoding="utf-8"))

    def _persist_chunks(self) -> None:
        """持久化 chunks.json + embeddings.npy。"""
        self._chunks_path.write_text(
            json.dumps(self._chunks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if self._embeddings is not None and self._embeddings.size > 0:
            np.save(self._embeddings_path, self._embeddings)

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
        self._documents[doc_id] = data
        self._persist_documents()
```

- [ ] **Step 2: 验证导入**

```bash
uv run python -c "from src.rag.vectorstore import VectorStore; print('OK')"
```

Expected: `OK`（无模型加载，因为没调 `_encode`）

- [ ] **Step 3: Commit**

```bash
git add src/rag/vectorstore.py
git commit -m "refactor(vectorstore): 从 Chroma Cloud 迁移到本地 numpy 存储"
```

---

### Task 4: 更新 Pipeline

**Files:**
- Modify: `src/rag/pipeline.py`

- [ ] **Step 1: 更新 Pipeline 适配新 VectorStore + 增加 save_document 调用**

找到 `pipeline.py` 中 `__init__` 和 `ingest` / `ingest_cleaned`，做以下修改：

**`__init__`** — 去掉旧参数，新 VectorStore 只需要 data_dir：

```python
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
```

**`ingest`** — 末尾增加 documents.json 写入：

`ingest()` 方法中，在 `add_documents` 后增加：

```python
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
```

**`ingest_cleaned`** — 末尾增加 documents.json 写入：

在 `add_documents` 返回后：

```python
# 保存文档元信息到 documents.json
self._store.save_document(filename, {
    **merged_meta,
    "text": text,
    "source_path": str(source_path),
    "chunk_count": count,
    "ingested_at": merged_meta["ingested_at"],
})
```

- [ ] **Step 2: 补充 import**

查看 `pipeline.py` 顶部 import 区。当前没有 `import hashlib`，需要添加。在 `from pathlib import Path` 之前加：

```python
import hashlib
```

- [ ] **Step 3: 验证 Pipeline 导入**

```bash
uv run python -c "from src.rag.pipeline import DocumentPipeline; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/rag/pipeline.py
git commit -m "refactor(pipeline): 适配新 VectorStore,ingest 时同步写入 documents.json"
```

---

### Task 5: 更新 RAG 包导出

**Files:**
- Modify: `src/rag/__init__.py`

- [ ] **Step 1: 添加 DocumentClassifier 导出**

```python
"""RAG 知识库模块"""

from src.rag.pipeline import DocumentPipeline
from src.rag.classifier import DocumentClassifier

__all__ = ["DocumentPipeline", "DocumentClassifier"]
```

- [ ] **Step 2: 验证**

```bash
uv run python -c "from src.rag import DocumentPipeline, DocumentClassifier; print('OK')"
```

Expected: 暂时可能失败（classifier.py 还没创建），这是 Task 6 的前置检查，此时可以跳过验证，或先创建占位 `classifier.py`。

先创建占位文件：

```python
"""文档自动分类模块。"""


class DocumentClassifier:
    """文档聚类 + LLM 命名分类器。"""
    pass
```

然后验证导入 OK。

- [ ] **Step 3: Commit**

```bash
git add src/rag/__init__.py src/rag/classifier.py
git commit -m "feat(classifier): 添加 DocumentClassifier 骨架和包导出"
```

---

### Task 6: 实现分类器

**Files:**
- Modify: `src/rag/classifier.py`

- [ ] **Step 1: 写分类器完整实现**

```python
"""文档自动分类模块。

对已入库文档做 KMeans 嵌入聚类，LLM 起中文类目名，结果写入 clusters.json。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from src.config import settings

logger = logging.getLogger(__name__)


class DocumentClassifier:
    """文档聚类 + LLM 命名分类器。

    公开方法:
      recluster(k_range) → dict  全量重聚类，返回 clusters.json 内容
    """

    def __init__(
        self,
        store,
        llm,  # ChatOpenAI 或等价 callable: llm.invoke(prompt) → AIMessage
    ):
        self._store = store
        self._llm = llm
        self._clusters_path = Path(settings.data_dir) / "clusters.json"

    def recluster(self, k_range: tuple[int, int] | None = None) -> dict:
        """全量重聚类。

        Args:
            k_range: (min_k, max_k)，默认从 settings 取 (5, 10)

        Returns:
            clusters.json 内容

        Raises:
            ValueError: 文档数不足 5 篇时抛出
        """
        if k_range is None:
            k_range = (settings.recluster_k_min, settings.recluster_k_max)

        chunks = self._store.get_all_chunks()
        embeddings = self._store.get_all_embeddings()
        documents = self._store.get_documents()

        # ---- 1. 篇级聚合:同 doc_id 的 chunk 嵌入取均值 ----
        doc_embeddings: dict[str, list[np.ndarray]] = {}
        for i, chunk in enumerate(chunks):
            doc_id = chunk.get("doc_id", "")
            if doc_id and embeddings is not None:
                doc_embeddings.setdefault(doc_id, []).append(embeddings[i])

        if len(doc_embeddings) < 5:
            raise ValueError(f"文档数不足（{len(doc_embeddings)}），至少需要 5 篇才能聚类")

        doc_ids = list(doc_embeddings.keys())
        doc_vecs = np.array([
            np.mean(doc_embeddings[did], axis=0) for did in doc_ids
        ])  # (M, dim)

        # ---- 2. KMeans 扫描, 轮廓系数择最优 k ----
        min_k, max_k = k_range
        best_k = min_k
        best_score = -1.0
        best_labels: np.ndarray | None = None

        for k in range(min_k, min(max_k + 1, len(doc_ids))):
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = km.fit_predict(doc_vecs)
            if k == 1:
                # 轮廓系数对 k=1 无定义，直接接受
                best_labels = labels
                best_k = 1
                break
            score = silhouette_score(doc_vecs, labels)
            if score > best_score:
                best_score = score
                best_k = k
                best_labels = labels

        # ---- 3. 每簇抽代表文章(离中心最近的 top-3) ----
        centroids = KMeans(n_clusters=best_k, random_state=42, n_init=10).fit(doc_vecs).cluster_centers_

        cluster_samples: dict[int, list[dict]] = {}
        for cid in range(best_k):
            # 找该簇中离中心最近的 3 篇
            indices_in_cluster = np.where(best_labels == cid)[0]
            centroid = centroids[cid]
            distances = np.linalg.norm(doc_vecs[indices_in_cluster] - centroid, axis=1)
            nearest_idx = indices_in_cluster[np.argsort(distances)[:3]]

            samples = []
            for idx in nearest_idx:
                doc_id = doc_ids[idx]
                doc = documents.get(doc_id, {})
                samples.append({
                    "doc_id": doc_id,
                    "title": doc.get("title", doc_id),
                    "text": doc.get("text", "")[:500],
                })
            cluster_samples[cid] = samples

        # ---- 4. LLM 起中文类目名 ----
        cluster_names: dict[int, str] = {}
        for cid, samples in cluster_samples.items():
            cluster_names[cid] = self._name_cluster(samples, cid)

        # ---- 5. 构建结果并写入 ----
        result = {
            "updated_at": datetime.now().isoformat(),
            "total_docs": len(doc_ids),
            "k": best_k,
            "silhouette_score": round(float(best_score), 4),
            "clusters": [
                {
                    "id": cid,
                    "name": cluster_names[cid],
                    "size": int((best_labels == cid).sum()),
                    "sample_titles": [s["title"] for s in cluster_samples[cid]],
                }
                for cid in range(best_k)
            ],
            "docs": {
                doc_ids[i]: {
                    "cluster_id": int(best_labels[i]),
                    "cluster_name": cluster_names[int(best_labels[i])],
                }
                for i in range(len(doc_ids))
            },
        }

        self._clusters_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result

    def get_clusters(self) -> dict | None:
        """读取当前聚类结果。"""
        if not self._clusters_path.exists():
            return None
        return json.loads(self._clusters_path.read_text(encoding="utf-8"))

    def _name_cluster(self, samples: list[dict], cid: int) -> str:
        """让 LLM 为一个聚类起名。失败降级为 '类别 N'。"""
        prompt = (
            "你是一个中文内容分类专家。以下是一个主题聚类中的几篇代表性公众号文章，"
            "请读完后用 2-8 个中文字为这个主题起一个简洁、准确的类目名。"
            "只输出类目名（2-8 字），不要解释。\n\n"
            "代表性文章：\n"
        )
        for s in samples:
            prompt += f"- 标题：{s['title']}\n  摘要：{s['text'][:500]}\n"
        prompt += "\n类目名："

        try:
            response = self._llm.invoke(prompt)
            # ChatOpenAI 返回 AIMessage，取其 .content
            name = getattr(response, "content", str(response)).strip()
            # 清理可能的引号/换行
            name = name.strip("。，\"'“”‘’\n ")
            if not name or len(name) > 20:
                return f"类别 {cid}"
            return name
        except Exception:
            logger.exception("LLM 起名失败, cluster_id=%d", cid)
            return f"类别 {cid}"
```

- [ ] **Step 2: 验证分类器导入**

```bash
uv run python -c "from src.rag.classifier import DocumentClassifier; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/rag/classifier.py
git commit -m "feat(classifier): 实现 DocumentClassifier(KMeans 聚类 + LLM 起名)"
```

---

### Task 7: 新增 API 端点

**Files:**
- Modify: `server.py`

- [ ] **Step 1: 在 lifespan 中初始化 Classifier**

找到 `lifespan` 中的：

```python
app.state.agent = build_agent()
app.state.pipeline = DocumentPipeline()
```

在下面增加：

```python
app.state.classifier = DocumentClassifier(
    store=app.state.pipeline._store,
    llm=app.state.agent.llm,
)
```

需要新增 import：

```python
from src.rag import DocumentClassifier
```

- [ ] **Step 2: 添加 POST /api/knowledge/recluster 端点**

在知识库 API 区（`/api/knowledge/search` 后面、健康检查前面）加：

```python
class ReclusterRequest(BaseModel):
    """重聚类请求体"""
    k: int | None = None  # 可选固定 k，不传则自动择优


@app.post("/api/knowledge/recluster")
async def knowledge_recluster(req: ReclusterRequest | None = None):
    """手动触发全量重聚类。

    返回聚类结果（clusters.json 内容）。
    文档数不足 5 篇时返回 400 错误。
    """
    classifier: DocumentClassifier = app.state.classifier
    try:
        k = req.k if req and req.k else None
        k_range = (k, k) if k else None
        return classifier.recluster(k_range=k_range)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"聚类失败: {e}")
```

- [ ] **Step 3: 添加 GET /api/knowledge/clusters 端点**

```python
@app.get("/api/knowledge/clusters")
async def knowledge_clusters():
    """获取当前聚类结果。

    尚未聚类时返回 404。
    """
    classifier: DocumentClassifier = app.state.classifier
    result = classifier.get_clusters()
    if result is None:
        raise HTTPException(status_code=404, detail="尚未聚类，请先 POST /api/knowledge/recluster")
    return result
```

- [ ] **Step 4: 验证 server 导入**

```bash
uv run python -c "import server; print('OK')"
```

Expected: `OK`（不会启动服务，只验证导入）

- [ ] **Step 5: Commit**

```bash
git add server.py
git commit -m "feat(server): 新增 /api/knowledge/recluster 和 /api/knowledge/clusters 端点"
```

---

### Task 8: VectorStore 单元测试

**Files:**
- Create: `tests/test_vectorstore.py`

- [ ] **Step 1: 写测试**

```python
"""VectorStore 本地 numpy 存储单元测试。

用随机向量 mock 嵌入模型，不依赖真实 HuggingFace 模型。
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from langchain_core.documents import Document


# ---- Mock 嵌入函数:生成固定维度的规范化随机向量 ----
DIM = 16

def _mock_encode(texts: list[str]) -> np.ndarray:
    """模拟嵌入：取文本长度 hash 作为随机种子，保证同文本同向量。"""
    vecs = []
    for t in texts:
        seed = hash(t) % (2**31)
        rng = np.random.RandomState(seed)
        v = rng.randn(DIM).astype(np.float32)
        v /= np.linalg.norm(v)
        vecs.append(v)
    return np.array(vecs, dtype=np.float32)


@pytest.fixture
def store():
    """创建临时目录的 VectorStore，注入 mock 嵌入函数。"""
    from src.rag.vectorstore import VectorStore

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(VectorStore, "_encode", _mock_encode):
            vs = VectorStore(data_dir=tmpdir)
            yield vs


def test_add_and_search(store):
    """基本 CRUD：添加文档后可检索到。"""
    docs = [
        Document(page_content="产品经理的核心能力是同理心", metadata={"source": "a"}),
        Document(page_content="Python 是一门很棒的编程语言", metadata={"source": "b"}),
        Document(page_content="如何做好用户访谈", metadata={"source": "a"}),
    ]
    count = store.add_documents(docs, filename="test.md")
    assert count == 3

    results = store.search("编程语言", k=2)
    assert len(results) == 2
    # 与 "Python" 相关的应该排第一
    assert "Python" in results[0].page_content


def test_search_empty_store(store):
    """空库检索返回空列表。"""
    assert store.search("任意查询") == []


def test_delete_by_filename(store):
    """删除后不再检索到。"""
    docs = [
        Document(page_content="文章 A 的内容", metadata={}),
        Document(page_content="文章 B 的内容", metadata={}),
    ]
    store.add_documents(docs, filename="A.md")
    assert store.list_documents()[0]["chunk_count"] == 1

    store.delete_by_filename("A.md")
    # 只剩 B
    assert len(store.list_documents()) == 0  # B 还没入库

    docs2 = [Document(page_content="文章 B 的内容", metadata={})]
    store.add_documents(docs2, filename="B.md")
    assert len(store.list_documents()) == 1
    assert store.list_documents()[0]["filename"] == "B.md"


def test_exists_by_metadata(store):
    """按 content_hash 去重。"""
    docs = [Document(
        page_content="去重测试内容",
        metadata={"content_hash": "abc123"},
    )]
    store.add_documents(docs, filename="test.md")

    assert store.exists_by_metadata({"content_hash": "abc123"})
    assert not store.exists_by_metadata({"content_hash": "not_found"})


def test_persistence(store):
    """持久化后重新加载不丢数据。"""
    from src.rag.vectorstore import VectorStore

    docs = [Document(page_content="持久化测试", metadata={})]
    store.add_documents(docs, filename="persist.md")

    data_dir = store._data_dir
    # 重新加载
    with patch.object(VectorStore, "_encode", _mock_encode):
        vs2 = VectorStore(data_dir=str(data_dir))
        assert len(vs2.list_documents()) == 1
        results = vs2.search("持久化", k=1)
        assert len(results) == 1
        assert results[0].page_content == "持久化测试"


def test_list_documents_aggregation(store):
    """同文件多个 chunk 聚合为一个条目。"""
    docs = [
        Document(page_content="第一段", metadata={}),
        Document(page_content="第二段", metadata={}),
        Document(page_content="第三段", metadata={}),
    ]
    store.add_documents(docs, filename="multi.md")
    result = store.list_documents()
    assert len(result) == 1
    assert result[0]["filename"] == "multi.md"
    assert result[0]["chunk_count"] == 3
```

- [ ] **Step 2: 运行测试（全部 PASS）**

```bash
uv run pytest tests/test_vectorstore.py -v
```

Expected: 6 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_vectorstore.py
git commit -m "test(vectorstore): 添加本地 numpy 存储单元测试(6 cases)"
```

---

### Task 9: Classifier 单元测试

**Files:**
- Create: `tests/test_classifier.py`

- [ ] **Step 1: 写测试**

```python
"""DocumentClassifier 单元测试。

用随机向量 mock store + LLM，验证聚类流程和数据输出格式。
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest


DIM = 16
N_DOCS = 20


class FakeStore:
    """构造 20 篇文档 × 3 chunks 的假数据。"""

    def __init__(self, tmpdir: str):
        self._tmpdir = Path(tmpdir)
        self._chunks = []
        self._embeddings = []
        self._documents = {}

        rng = np.random.RandomState(42)
        for doc_i in range(N_DOCS):
            doc_id = f"doc-{doc_i:02d}"
            text = f"这是第 {doc_i} 篇文章的正文内容，用于测试聚类效果。"
            self._documents[doc_id] = {
                "title": f"文章标题 {doc_i}",
                "text": text * 20,
                "source_path": f"data/uploads/doc-{doc_i:02d}/index.html",
            }
            # 每篇 3 个 chunk,嵌入在某个中心附近（模拟天然聚类）
            center = rng.randn(DIM).astype(np.float32)
            for ci in range(3):
                self._chunks.append({
                    "id": f"doc-{doc_i:02d}::chunk-{ci}",
                    "doc_id": doc_id,
                    "chunk_i": ci,
                    "text": f"{text} chunk {ci}",
                    "metadata": {"source": doc_id},
                })
                v = center + 0.1 * rng.randn(DIM).astype(np.float32)
                v /= np.linalg.norm(v)
                self._embeddings.append(v)

        self._embeddings = np.array(self._embeddings, dtype=np.float32)

    def get_all_chunks(self):
        return self._chunks

    def get_all_embeddings(self):
        return self._embeddings

    def get_documents(self):
        return dict(self._documents)


class FakeLLM:
    """模拟 LLM,按 cluster_id 返回固定类目名。"""
    def invoke(self, prompt: str):
        m = MagicMock()
        # 根据 prompt 中的 cluster id 返回不同名字
        if "产品" in prompt[:100]:
            m.content = "产品方法论"
        else:
            m.content = f"类目-{hash(prompt) % 100}"
        return m


def test_recluster_basic(tmp_path):
    """基本聚类流程：输入 → 输出有效 JSON 结构。"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.rag.classifier import DocumentClassifier

    store = FakeStore(str(tmp_path))
    llm = FakeLLM()
    classifier = DocumentClassifier(store=store, llm=llm)
    # 覆写路径到 tmp
    classifier._clusters_path = tmp_path / "clusters.json"

    result = classifier.recluster(k_range=(3, 6))

    # 检查输出结构
    assert result["total_docs"] == N_DOCS
    assert 3 <= result["k"] <= 6
    assert len(result["clusters"]) == result["k"]
    assert len(result["docs"]) == N_DOCS

    for cluster in result["clusters"]:
        assert "id" in cluster
        assert "name" in cluster
        assert "size" in cluster
        assert cluster["size"] > 0
        assert len(cluster["sample_titles"]) <= 3

    # 验证持久化
    assert (tmp_path / "clusters.json").exists()
    loaded = json.loads((tmp_path / "clusters.json").read_text(encoding="utf-8"))
    assert loaded["total_docs"] == N_DOCS


def test_recluster_too_few_docs():
    """文档数不足 5 篇时抛 ValueError。"""
    from src.rag.classifier import DocumentClassifier

    empty_store = MagicMock()
    empty_store.get_all_chunks.return_value = []
    empty_store.get_all_embeddings.return_value = np.array([])
    empty_store.get_documents.return_value = {}

    classifier = DocumentClassifier(store=empty_store, llm=MagicMock())
    with pytest.raises(ValueError, match="文档数不足"):
        classifier.recluster()


def test_get_clusters_not_found(tmp_path):
    """未聚类时 get_clusters 返回 None。"""
    from src.rag.classifier import DocumentClassifier

    classifier = DocumentClassifier(store=MagicMock(), llm=MagicMock())
    classifier._clusters_path = tmp_path / "nonexistent.json"
    assert classifier.get_clusters() is None


def test_fallback_name_on_llm_error(tmp_path):
    """LLM 起名失败时降级为 '类别 N'。"""
    from src.rag.classifier import DocumentClassifier

    store = FakeStore(str(tmp_path))
    bad_llm = MagicMock()
    bad_llm.invoke.side_effect = RuntimeError("LLM 挂了")

    classifier = DocumentClassifier(store=store, llm=bad_llm)
    classifier._clusters_path = tmp_path / "clusters.json"

    result = classifier.recluster(k_range=(3, 3))
    for cluster in result["clusters"]:
        assert cluster["name"].startswith("类别 ")
```

- [ ] **Step 2: 运行测试（全部 PASS）**

```bash
uv run pytest tests/test_classifier.py -v
```

Expected: 4 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_classifier.py
git commit -m "test(classifier): 添加 DocumentClassifier 单元测试(4 cases)"
```

---

### Task 10: 清理旧的 Chroma Cloud trace

**Files:**
- Modify: `.env.example` (如存在)
- Modify: CLAUDE.md

- [ ] **Step 1: 检查 .env.example 是否需要更新**

```bash
cat .env.example 2>/dev/null || echo "文件不存在"
```

如存在且有 `CHROMA_*` 变量，删除它们，替换为：

```
DATA_DIR=data
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
```

- [ ] **Step 2: 更新 CLAUDE.md**

CLAUDE.md 中的 Chroma Cloud 相关段落需要更新。具体修改点：

**第 21-26 行**（"LLM 通过 OpenAI 兼容协议接入"段落）：将

```
向量检索/嵌入走 Chroma Cloud 托管（Qwen3-Embedding-0.6B dense），
本机不再持嵌入模型/向量索引。
```

改为：

```
向量检索/嵌入走本地 sentence-transformers + numpy（Qwen3-Embedding-0.6B），
数据存储在 data/ 目录下的 JSON/NPY 文件中。
```

**第 29-33 行**（Commands 段落）数据目录说明：将

```
不再有 `data/chroma_db/`（Chroma Cloud 端持久化）
```

改为：

```
`data/chunks.json` + `data/embeddings.npy` — 向量存储
`data/documents.json` — 文档元信息
`data/clusters.json` — 聚类结果
```

**第 37-42 行**（向量存储说明）将 `vectorstore.py` 的描述从"Chroma Cloud 封装"改为"本地 numpy 存储封装"。

**删除**整个 "Cloud 模式" 相关段落（如 `close()` 是 no-op 那几行），保留分块/检索参数说明但删掉 Cloud 端点句。

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "docs: 更新文档，移除 Chroma Cloud 引用"
```

---

### Task 11: 端到端验证

- [ ] **Step 1: 启动服务**

```bash
uv run python server.py &
sleep 3
```

Expected: 服务启动在 8000 端口，无 Chroma API key 错误。

- [ ] **Step 2: 测试健康检查**

```bash
curl -s http://localhost:8000/api/health | python -m json.tool
```

Expected: `{"status": "ok"}`

- [ ] **Step 3: 上传测试文档**

```bash
curl -s -X POST http://localhost:8000/api/knowledge/upload \
  -F "file=@tests/fixtures/wechat_sample.html" | python -m json.tool
```

Expected: 返回 `{"filename": "...", "chunk_count": N}`（首次会下载 Qwen 模型，需等待）

- [ ] **Step 4: 测试检索**

```bash
curl -s -X POST http://localhost:8000/api/knowledge/search \
  -H "Content-Type: application/json" \
  -d '{"query": "测试", "k": 2}' | python -m json.tool
```

Expected: 返回 chunks 数组

- [ ] **Step 5: 测试聚类**

```bash
# 先多上传几个文件让文档数 ≥ 5
curl -s -X POST http://localhost:8000/api/knowledge/recluster | python -m json.tool
```

Expected: 聚类结果（如果文档数不足 5 返回 400，把 wechat_sample 多传几次）。

- [ ] **Step 6: 测试获取聚类结果**

```bash
curl -s http://localhost:8000/api/knowledge/clusters | python -m json.tool
```

Expected: 聚类结果

- [ ] **Step 7: 停止服务**

```bash
kill %1
```

- [ ] **Step 8: 验证数据文件**

```bash
ls -la data/*.json data/*.npy
```

Expected: `chunks.json`, `embeddings.npy`, `clusters.json` 存在

- [ ] **Step 9: Commit (如有残留变更)**

```bash
git status
git add -A && git commit -m "chore: 端到端验证通过，清理残留" || echo "无残留变更"
```
