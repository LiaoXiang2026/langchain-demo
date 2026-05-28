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
    finally:
        shutil.rmtree(tmpdir)


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
    finally:
        shutil.rmtree(tmpdir)


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
    finally:
        shutil.rmtree(tmpdir)
