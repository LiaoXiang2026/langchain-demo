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

def _mock_encode(self, texts: list[str]) -> np.ndarray:
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

    # 用完整原文搜索保证精确匹配（同文本 hash 相同 → 向量完全相同）
    results = store.search("Python 是一门很棒的编程语言", k=2)
    assert len(results) == 2
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
    assert store.list_documents()[0]["chunk_count"] == 2

    store.delete_by_filename("A.md")
    assert len(store.list_documents()) == 0

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
    with patch.object(VectorStore, "_encode", _mock_encode):
        vs2 = VectorStore(data_dir=str(data_dir))
        assert len(vs2.list_documents()) == 1
        results = vs2.search("持久化测试", k=1)
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
