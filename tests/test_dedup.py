"""DedupIndex + DocumentPipeline 批量去重测试。

覆盖 DEDUP-01~03 三条 must-have:
  - 同一清洗后正文重复入库被识别(DEDUP-01)
  - 改标题/改文件名但正文不变,仍被识别(DEDUP-02)
  - 正文加一字,被识别为新文档(DEDUP-03)

测试隔离策略:每个测试独立 tempfile.mkdtemp() 创建 ChromaDB,避免互相污染。
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from langchain_core.documents import Document

from src.rag.dedup import DedupIndex
from src.rag.pipeline import DocumentPipeline
from src.rag.vectorstore import VectorStore

EMBED_MODEL = "shibing624/text2vec-base-chinese"


# ---------- DedupIndex 单元测试 (Task 1) ----------


def test_dedup_01_same_text_repeated():
    """DEDUP-01: 同一清洗后 text 入库两次,第二次 exists() 返回 True。"""
    tmpdir = tempfile.mkdtemp()
    try:
        store = VectorStore(persist_dir=tmpdir, embedding_model=EMBED_MODEL)
        index = DedupIndex(store)
        text = "这是一段测试正文,用于验证去重。"
        h = DedupIndex.compute_hash(text)

        # 首次入库前不存在
        assert index.exists(h) is False

        # 入库一次,带 content_hash metadata
        store.add_documents(
            [Document(page_content=text, metadata={"content_hash": h})],
            filename="article-a.html",
        )
        assert index.exists(h) is True
        store.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_dedup_02_same_text_different_meta():
    """DEDUP-02: 正文相同 + meta.title/source 不同时,hash 仍一致。

    验证 hash 只依赖 text,不被 title/filename 干扰。
    """
    tmpdir = tempfile.mkdtemp()
    try:
        store = VectorStore(persist_dir=tmpdir, embedding_model=EMBED_MODEL)
        index = DedupIndex(store)
        text = "正文一致,标题与文件名不同。"
        h = DedupIndex.compute_hash(text)

        store.add_documents(
            [Document(page_content=text, metadata={
                "content_hash": h, "title": "标题甲"
            })],
            filename="article-a.html",
        )
        # 同一 text,不同 title + 不同 filename → hash 不变
        h2 = DedupIndex.compute_hash(text)
        assert h == h2
        assert index.exists(h2) is True
        store.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_dedup_03_text_modified():
    """DEDUP-03: 正文末尾加一字,exists() 返回 False(被识别为新文档)。"""
    tmpdir = tempfile.mkdtemp()
    try:
        store = VectorStore(persist_dir=tmpdir, embedding_model=EMBED_MODEL)
        index = DedupIndex(store)
        text_v1 = "正文版本一,用于测试微小改动。"
        text_v2 = text_v1 + "。"  # 末尾加一字
        h1 = DedupIndex.compute_hash(text_v1)
        h2 = DedupIndex.compute_hash(text_v2)

        store.add_documents(
            [Document(page_content=text_v1, metadata={"content_hash": h1})],
            filename="article.html",
        )
        assert h1 != h2
        assert index.exists(h2) is False
        store.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_compute_hash_empty():
    """空字符串返回 64 字符的合法 hex 字符串。"""
    h = DedupIndex.compute_hash("")
    assert isinstance(h, str)
    assert len(h) == 64
    int(h, 16)  # 必须是合法 hex,异常则用例失败


def test_compute_hash_stable():
    """同一 text 两次调用返回相同 hash。"""
    text = "稳定性测试"
    assert DedupIndex.compute_hash(text) == DedupIndex.compute_hash(text)


# ---------- DocumentPipeline.ingest_batch 集成测试 (Task 3) ----------


def _write_html_fixture(dirpath: str, name: str, body: str) -> str:
    """在 tmpdir 下写入一个最小 WeChat 风格 HTML(让 cleaner 输出确定性 text)。

    cleaner 会剥 script/style,保留正文 div;此处直接给 <body> 注入纯文本即可。
    """
    path = Path(dirpath) / name
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>fixture</title></head><body>"
        f"<div id='js_content'>{body}</div></body></html>"
    )
    path.write_text(html, encoding="utf-8")
    return str(path)


def test_ingest_batch_new_documents():
    """Test 6: 首次 ingest_batch 两个新文档,new_count=2 / skip_count=0。"""
    tmpdir = tempfile.mkdtemp()
    try:
        pipeline = DocumentPipeline(
            persist_dir=tmpdir, embedding_model=EMBED_MODEL
        )
        f1 = _write_html_fixture(tmpdir, "a.html", "文章甲的正文内容。" * 10)
        f2 = _write_html_fixture(tmpdir, "b.html", "文章乙的正文内容。" * 10)

        result = pipeline.ingest_batch([f1, f2])
        assert result["new_count"] == 2
        assert result["skip_count"] == 0
        assert result["errors"] == []
        assert len(result["results"]) == 2
        pipeline._store.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_ingest_batch_duplicate_skip():
    """Test 7: 重复 ingest 同样两个文件,new_count=0 / skip_count=2(短路)。"""
    tmpdir = tempfile.mkdtemp()
    try:
        pipeline = DocumentPipeline(
            persist_dir=tmpdir, embedding_model=EMBED_MODEL
        )
        f1 = _write_html_fixture(tmpdir, "a.html", "文章甲的正文内容。" * 10)
        f2 = _write_html_fixture(tmpdir, "b.html", "文章乙的正文内容。" * 10)

        pipeline.ingest_batch([f1, f2])
        result = pipeline.ingest_batch([f1, f2])
        assert result["new_count"] == 0
        assert result["skip_count"] == 2
        assert result["errors"] == []
        pipeline._store.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_ingest_batch_modified_text():
    """Test 8: 改文件正文加一字后再 ingest_batch,被识别为新文档。"""
    tmpdir = tempfile.mkdtemp()
    try:
        pipeline = DocumentPipeline(
            persist_dir=tmpdir, embedding_model=EMBED_MODEL
        )
        f2 = _write_html_fixture(tmpdir, "b.html", "文章乙的正文内容。" * 10)
        pipeline.ingest_batch([f2])

        # 改 f2 内容(加一字)
        _write_html_fixture(
            tmpdir, "b.html", "文章乙的正文内容。" * 10 + "新增片段。"
        )
        result = pipeline.ingest_batch([f2])
        assert result["new_count"] == 1
        assert result["skip_count"] == 0
        pipeline._store.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
