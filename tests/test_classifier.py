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
    """模拟 LLM,根据 prompt 中样本标题返回固定类目名。"""
    def invoke(self, prompt: str):
        m = MagicMock()
        # 从 prompt 取第一个标题的序号作为类目名
        if "标题 0" in prompt[:200]:
            m.content = "技术前沿"
        elif "标题 10" in prompt[:200]:
            m.content = "产品运营"
        else:
            m.content = "综合类目"
        return m


def test_recluster_basic(tmp_path):
    """基本聚类流程：输入 → 输出有效 JSON 结构。"""
    from src.rag.classifier import DocumentClassifier

    store = FakeStore(str(tmp_path))
    llm = FakeLLM()
    classifier = DocumentClassifier(store=store, llm=llm)
    classifier._clusters_path = tmp_path / "clusters.json"

    result = classifier.recluster(k_range=(3, 6))

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

    assert (tmp_path / "clusters.json").exists()
    loaded = json.loads((tmp_path / "clusters.json").read_text(encoding="utf-8"))
    assert loaded["total_docs"] == N_DOCS


def test_recluster_too_few_docs():
    """文档数不足 5 篇时抛 ValueError。"""
    from src.rag.classifier import DocumentClassifier

    empty_store = MagicMock()
    empty_store.get_all_chunks.return_value = []
    empty_store.get_all_embeddings.return_value = np.empty((0, DIM), dtype=np.float32)
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
