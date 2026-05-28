"""文档加载器测试"""

import os
import tempfile
import pytest
from src.rag.document_loader import load_document


def test_load_txt():
    """测试加载纯文本文件"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("这是第一段内容。\n\n这是第二段内容。")
        f.flush()
        path = f.name
    try:
        docs = load_document(path)
        assert len(docs) > 0
        assert "第一段" in docs[0].page_content
        assert docs[0].metadata["source"] == path
    finally:
        os.unlink(path)


def test_load_markdown():
    """测试加载 Markdown 文件"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# 标题\n\n这是 Markdown 内容。")
        f.flush()
        path = f.name
    try:
        docs = load_document(path)
        assert len(docs) > 0
        assert "标题" in docs[0].page_content
    finally:
        os.unlink(path)


def test_unsupported_format():
    """测试不支持的文件格式"""
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
        f.write(b"some content")
        f.flush()
        path = f.name
    try:
        with pytest.raises(ValueError, match="不支持的文件格式"):
            load_document(path)
    finally:
        os.unlink(path)
