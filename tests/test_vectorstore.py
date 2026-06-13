"""向量存储测试"""

import tempfile
import shutil
from langchain_core.documents import Document
from src.rag.vectorstore import VectorStore


def test_add_and_search():
    """测试添加文档和相似度搜索"""
    tmpdir = tempfile.mkdtemp()
    try:
        store = VectorStore(persist_dir=tmpdir, embedding_model="shibing624/text2vec-base-chinese")
        docs = [
            Document(page_content="Python 是一种编程语言", metadata={"source": "test.txt", "chunk_id": 0}),
            Document(page_content="今天天气很好", metadata={"source": "test.txt", "chunk_id": 1}),
        ]
        store.add_documents(docs, filename="test.txt")

        results = store.search("编程语言", k=1)
        assert len(results) == 1
        assert "Python" in results[0].page_content
        store.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_delete_by_filename():
    """测试按文件名删除"""
    tmpdir = tempfile.mkdtemp()
    try:
        store = VectorStore(persist_dir=tmpdir, embedding_model="shibing624/text2vec-base-chinese")
        docs = [
            Document(page_content="内容A", metadata={"source": "a.txt", "chunk_id": 0}),
            Document(page_content="内容B", metadata={"source": "b.txt", "chunk_id": 0}),
        ]
        store.add_documents(docs[:1], filename="a.txt")
        store.add_documents(docs[1:], filename="b.txt")

        store.delete_by_filename("a.txt")
        results = store.search("内容", k=10)
        assert all("b.txt" == r.metadata["source"] for r in results)
        store.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_list_documents():
    """测试列出已入库文档"""
    tmpdir = tempfile.mkdtemp()
    try:
        store = VectorStore(persist_dir=tmpdir, embedding_model="shibing624/text2vec-base-chinese")
        docs = [
            Document(page_content="内容A", metadata={"source": "a.txt", "chunk_id": 0}),
            Document(page_content="内容B", metadata={"source": "b.txt", "chunk_id": 0}),
        ]
        store.add_documents(docs[:1], filename="a.txt")
        store.add_documents(docs[1:], filename="b.txt")

        doc_list = store.list_documents()
        filenames = [d["filename"] for d in doc_list]
        assert "a.txt" in filenames
        assert "b.txt" in filenames
        store.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_metadata_inheritance():
    """add_documents 应继承 doc.metadata 自带字段(content_hash/title/author),
    同时仍由本函数覆盖 source/chunk_id。"""
    tmpdir = tempfile.mkdtemp()
    try:
        store = VectorStore(persist_dir=tmpdir, embedding_model="shibing624/text2vec-base-chinese")
        doc = Document(
            page_content="测试正文",
            metadata={
                "content_hash": "abc123",
                "title": "测试标题",
                "author": "作者",
            },
        )
        store.add_documents([doc], filename="test.html")

        doc_list = store.list_documents()
        assert any(d["filename"] == "test.html" and d["chunk_count"] == 1 for d in doc_list)

        results = store.search("测试正文", k=1)
        assert len(results) == 1
        meta = results[0].metadata
        assert meta["content_hash"] == "abc123"
        assert meta["title"] == "测试标题"
        assert meta["author"] == "作者"
        # source/chunk_id 由 add_documents 强制注入
        assert meta["source"] == "test.html"
        assert meta["chunk_id"] == 0
        store.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
