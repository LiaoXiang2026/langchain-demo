# RAG 本地知识库问答机器人 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 LangChain Agent 上新增 RAG 能力，支持上传本地文档构建知识库，Agent 自动检索回答问题。

**Architecture:** RAG 作为 Agent 的 `knowledge_search` 工具。文档通过管线（加载→分块→嵌入）存入 ChromaDB。用户提问时 Agent 自行决定是否调用知识库检索。前端新增知识库管理 Tab。

**Tech Stack:** ChromaDB, HuggingFace Embeddings (`text2vec-base-chinese`), LangChain Community Loaders, FastAPI, React + Tailwind CSS CDN

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `pyproject.toml` | Modify | 添加 RAG 相关 Python 依赖 |
| `backend/src/config/settings.py` | Modify | 新增 RAG 配置项 |
| `backend/src/rag/__init__.py` | Create | 导出公共接口 |
| `backend/src/rag/document_loader.py` | Create | 多格式文档加载 |
| `backend/src/rag/splitter.py` | Create | 文档分块 |
| `backend/src/rag/embeddings.py` | Create | 嵌入模型管理 |
| `backend/src/rag/vectorstore.py` | Create | ChromaDB CRUD |
| `backend/src/rag/pipeline.py` | Create | 文档处理管线 |
| `backend/src/tools/knowledge.py` | Create | knowledge_search 工具 |
| `backend/src/tools/__init__.py` | Modify | 导出 knowledge_search |
| `backend/src/agent/agent.py` | Modify | 注册工具 + 更新 prompt |
| `backend/server.py` | Modify | 新增 /knowledge API |
| `frontend/index.html` | Modify | 引入 Tailwind CSS CDN |
| `frontend/src/KnowledgePanel.tsx` | Create | 知识库管理组件 |
| `frontend/src/App.tsx` | Modify | Tab 切换聊天/知识库 |
| `frontend/src/App.css` | Modify | 清理旧样式（迁移到 Tailwind） |
| `frontend/vite.config.ts` | Modify | 新增 /knowledge 代理 |
| `tests/test_document_loader.py` | Create | 文档加载测试 |
| `tests/test_vectorstore.py` | Create | 向量存储测试 |
| `tests/test_pipeline.py` | Create | 管线测试 |
| `tests/test_knowledge_api.py` | Create | API 端点测试 |

---

### Task 1: 安装依赖并更新配置

**Files:**
- Modify: `pyproject.toml`
- Modify: `backend/src/config/settings.py`

- [ ] **Step 1: 添加 Python 依赖**

在 `pyproject.toml` 的 `dependencies` 列表末尾追加：

```toml
dependencies = [
    "fastapi>=0.115.0",
    "langchain>=1.3.2",
    "langchain-openai>=1.2.2",
    "python-dotenv>=1.2.2",
    "simpleeval>=0.9.13",
    "uvicorn>=0.34.0",
    # RAG 依赖
    "chromadb>=0.4.0",
    "langchain-community>=0.0.1",
    "sentence-transformers>=2.2.0",
    "pymupdf>=1.23.0",
    "docx2txt>=0.8",
    "openpyxl>=3.1.0",
]
```

- [ ] **Step 2: 同步依赖**

Run: `cd e:/my-app-py && uv sync`
Expected: 依赖安装成功，无报错

- [ ] **Step 3: 更新 Settings 添加 RAG 配置**

修改 `backend/src/config/settings.py`，在 `Settings` dataclass 中追加字段：

```python
"""配置管理"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


@dataclass
class Settings:
    # 小米模型配置
    api_key: str = ""
    base_url: str = "https://token-plan-cn.xiaomimimo.com/v1"
    model: str = "mimo-v2.5"

    # Agent 配置
    temperature: float = 0.7
    max_tokens: int = 2048

    # RAG 配置
    chroma_dir: str = "data/chroma_db"
    upload_dir: str = "data/uploads"
    embedding_model: str = "shibing624/text2vec-base-chinese"
    chunk_size: int = 500
    chunk_overlap: int = 50
    search_top_k: int = 4

    def __post_init__(self):
        self.api_key = os.getenv("MIMO_API_KEY") or self.api_key
        self.chroma_dir = os.getenv("CHROMA_DIR") or self.chroma_dir
        self.upload_dir = os.getenv("UPLOAD_DIR") or self.upload_dir
        self.embedding_model = os.getenv("EMBEDDING_MODEL") or self.embedding_model


settings = Settings()
```

- [ ] **Step 4: 验证配置加载**

Run: `cd e:/my-app-py && uv run python -c "from src.config import settings; print(settings.chroma_dir, settings.embedding_model)"`
Expected: `data/chroma_db shibing624/text2vec-base-chinese`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock backend/src/config/settings.py
git commit -m "feat: 添加 RAG 依赖和配置"
```

---

### Task 2: 文档加载器

**Files:**
- Create: `backend/src/rag/__init__.py`
- Create: `backend/src/rag/document_loader.py`
- Create: `tests/test_document_loader.py`

- [ ] **Step 1: 创建 RAG 包结构**

创建 `backend/src/rag/__init__.py`：

```python
"""RAG 知识库模块"""
```

- [ ] **Step 2: 编写文档加载器测试**

创建 `tests/test_document_loader.py`：

```python
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
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd e:/my-app-py && uv run pytest tests/test_document_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.rag.document_loader'`

- [ ] **Step 4: 实现文档加载器**

创建 `backend/src/rag/document_loader.py`：

```python
"""多格式文档加载器"""

from pathlib import Path
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    TextLoader,
    PyMuPDFLoader,
    Docx2txtLoader,
    UnstructuredExcelLoader,
)

LOADER_MAP = {
    ".txt": lambda path: TextLoader(path, encoding="utf-8"),
    ".md": lambda path: TextLoader(path, encoding="utf-8"),
    ".pdf": lambda path: PyMuPDFLoader(path),
    ".docx": lambda path: Docx2txtLoader(path),
    ".xlsx": lambda path: UnstructuredExcelLoader(path),
    ".xls": lambda path: UnstructuredExcelLoader(path),
}

SUPPORTED_FORMATS = ", ".join(sorted(LOADER_MAP.keys()))


def load_document(file_path: str) -> list[Document]:
    """加载单个文档，返回 Document 列表。

    Args:
        file_path: 文件路径

    Returns:
        Document 列表

    Raises:
        ValueError: 不支持的文件格式
    """
    ext = Path(file_path).suffix.lower()
    loader_factory = LOADER_MAP.get(ext)
    if not loader_factory:
        raise ValueError(f"不支持的文件格式: {ext}。支持的格式: {SUPPORTED_FORMATS}")
    loader = loader_factory(file_path)
    return loader.load()
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd e:/my-app-py && uv run pytest tests/test_document_loader.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add backend/src/rag/__init__.py backend/src/rag/document_loader.py tests/test_document_loader.py
git commit -m "feat: 添加多格式文档加载器"
```

---

### Task 3: 文档分块器

**Files:**
- Create: `backend/src/rag/splitter.py`

- [ ] **Step 1: 实现分块器**

创建 `backend/src/rag/splitter.py`：

```python
"""文档分块"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

CHINESE_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", " "]


def split_documents(
    docs: list[Document],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[Document]:
    """将文档列表分块。

    Args:
        docs: Document 列表
        chunk_size: 每块最大字符数
        chunk_overlap: 块间重叠字符数

    Returns:
        分块后的 Document 列表
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=CHINESE_SEPARATORS,
    )
    return splitter.split_documents(docs)
```

- [ ] **Step 2: 验证模块可导入**

Run: `cd e:/my-app-py && uv run python -c "from src.rag.splitter import split_documents; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/rag/splitter.py
git commit -m "feat: 添加文档分块器"
```

---

### Task 4: 嵌入模型与向量存储

**Files:**
- Create: `backend/src/rag/embeddings.py`
- Create: `backend/src/rag/vectorstore.py`
- Create: `tests/test_vectorstore.py`

- [ ] **Step 1: 编写向量存储测试**

创建 `tests/test_vectorstore.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd e:/my-app-py && uv run pytest tests/test_vectorstore.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现嵌入模型管理**

创建 `backend/src/rag/embeddings.py`：

```python
"""嵌入模型管理"""

from langchain_huggingface import HuggingFaceEmbeddings


def get_embeddings(model_name: str = "shibing624/text2vec-base-chinese") -> HuggingFaceEmbeddings:
    """获取 HuggingFace 嵌入模型实例。

    首次调用时会自动下载模型（约 100MB）。
    """
    return HuggingFaceEmbeddings(model_name=model_name)
```

- [ ] **Step 4: 实现向量存储**

创建 `backend/src/rag/vectorstore.py`：

```python
"""ChromaDB 向量存储管理"""

from pathlib import Path
from langchain_core.documents import Document
from langchain_chroma import Chroma
from src.rag.embeddings import get_embeddings


class VectorStore:
    def __init__(self, persist_dir: str, embedding_model: str = "shibing624/text2vec-base-chinese"):
        self.persist_dir = persist_dir
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self._embeddings = get_embeddings(embedding_model)
        self._store = Chroma(
            persist_directory=persist_dir,
            embedding_function=self._embeddings,
        )

    def add_documents(self, docs: list[Document], filename: str) -> int:
        """添加文档到向量存储。

        Args:
            docs: 分块后的 Document 列表
            filename: 来源文件名

        Returns:
            添加的 chunk 数量
        """
        for i, doc in enumerate(docs):
            doc.metadata["source"] = filename
            doc.metadata["chunk_id"] = i
        self._store.add_documents(docs)
        return len(docs)

    def search(self, query: str, k: int = 4) -> list[Document]:
        """相似度搜索。"""
        return self._store.similarity_search(query, k=k)

    def delete_by_filename(self, filename: str) -> None:
        """根据文件名删除所有相关 chunks。"""
        results = self._store.get(where={"source": filename})
        if results and results["ids"]:
            self._store.delete(ids=results["ids"])

    def list_documents(self) -> list[dict]:
        """列出已入库的文档信息。"""
        results = self._store.get()
        if not results or not results["metadatas"]:
            return []

        doc_map: dict[str, dict] = {}
        for meta in results["metadatas"]:
            fname = meta.get("source", "unknown")
            if fname not in doc_map:
                doc_map[fname] = {"filename": fname, "chunk_count": 0}
            doc_map[fname]["chunk_count"] += 1
        return list(doc_map.values())
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd e:/my-app-py && uv run pytest tests/test_vectorstore.py -v`
Expected: 3 passed（首次运行会下载嵌入模型，可能需要几分钟）

- [ ] **Step 6: Commit**

```bash
git add backend/src/rag/embeddings.py backend/src/rag/vectorstore.py tests/test_vectorstore.py
git commit -m "feat: 添加嵌入模型和 ChromaDB 向量存储"
```

---

### Task 5: 文档处理管线

**Files:**
- Create: `backend/src/rag/pipeline.py`
- Modify: `backend/src/rag/__init__.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: 编写管线测试**

创建 `tests/test_pipeline.py`：

```python
"""文档处理管线测试"""

import tempfile
import shutil
from src.rag.pipeline import DocumentPipeline


def test_ingest_txt_file():
    """测试完整管线：加载→分块→嵌入→存储"""
    tmpdir = tempfile.mkdtemp()
    try:
        pipeline = DocumentPipeline(
            persist_dir=tmpdir,
            embedding_model="shibing624/text2vec-base-chinese",
        )
        # 创建临时文本文件
        import os
        txt_path = os.path.join(tmpdir, "test.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("这是一段测试内容。" * 50)  # 足够长以产生多个 chunks

        result = pipeline.ingest(txt_path)
        assert result["filename"] == "test.txt"
        assert result["chunk_count"] > 0

        # 验证可以搜索到
        results = pipeline.search("测试内容", k=1)
        assert len(results) > 0
    finally:
        shutil.rmtree(tmpdir)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd e:/my-app-py && uv run pytest tests/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现文档处理管线**

创建 `backend/src/rag/pipeline.py`：

```python
"""文档处理管线：加载→分块→嵌入→存储"""

from pathlib import Path
from langchain_core.documents import Document
from src.rag.document_loader import load_document
from src.rag.splitter import split_documents
from src.rag.vectorstore import VectorStore
from src.config import settings


class DocumentPipeline:
    def __init__(
        self,
        persist_dir: str | None = None,
        embedding_model: str | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        self.persist_dir = persist_dir or settings.chroma_dir
        self.embedding_model = embedding_model or settings.embedding_model
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self._store = VectorStore(
            persist_dir=self.persist_dir,
            embedding_model=self.embedding_model,
        )

    def ingest(self, file_path: str) -> dict:
        """处理单个文档：加载→分块→存入向量库。

        Returns:
            {"filename": str, "chunk_count": int}
        """
        filename = Path(file_path).name
        docs = load_document(file_path)
        chunks = split_documents(docs, self.chunk_size, self.chunk_overlap)
        count = self._store.add_documents(chunks, filename=filename)
        return {"filename": filename, "chunk_count": count}

    def search(self, query: str, k: int | None = None) -> list[Document]:
        """搜索知识库。"""
        return self._store.search(query, k=k or settings.search_top_k)

    def delete(self, filename: str) -> None:
        """删除指定文档。"""
        self._store.delete_by_filename(filename)

    def list_documents(self) -> list[dict]:
        """列出已入库文档。"""
        return self._store.list_documents()
```

- [ ] **Step 4: 更新 rag/__init__.py 导出**

修改 `backend/src/rag/__init__.py`：

```python
"""RAG 知识库模块"""

from src.rag.pipeline import DocumentPipeline

__all__ = ["DocumentPipeline"]
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd e:/my-app-py && uv run pytest tests/test_pipeline.py -v`
Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add backend/src/rag/pipeline.py backend/src/rag/__init__.py tests/test_pipeline.py
git commit -m "feat: 添加文档处理管线"
```

---

### Task 6: knowledge_search 工具

**Files:**
- Create: `backend/src/tools/knowledge.py`
- Modify: `backend/src/tools/__init__.py`

- [ ] **Step 1: 实现 knowledge_search 工具**

创建 `backend/src/tools/knowledge.py`：

```python
"""知识库检索工具"""

from langchain_core.tools import tool
from src.rag import DocumentPipeline

# 全局管线实例（延迟初始化）
_pipeline: DocumentPipeline | None = None


def _get_pipeline() -> DocumentPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = DocumentPipeline()
    return _pipeline


@tool
def knowledge_search(query: str) -> str:
    """搜索本地知识库，查找与问题相关的文档内容。当用户询问可能在知识库中有答案的问题时使用此工具。"""
    try:
        pipeline = _get_pipeline()
        results = pipeline.search(query)
        if not results:
            return "知识库中没有找到相关信息。"
        parts = []
        for i, doc in enumerate(results, 1):
            source = doc.metadata.get("source", "未知来源")
            parts.append(f"[来源: {source}]\n{doc.page_content}")
        return "\n\n---\n\n".join(parts)
    except Exception as e:
        return f"知识库检索出错: {e}"
```

- [ ] **Step 2: 更新 tools/__init__.py**

修改 `backend/src/tools/__init__.py`：

```python
from .search import search
from .calculator import calculator
from .knowledge import knowledge_search
```

- [ ] **Step 3: 验证模块可导入**

Run: `cd e:/my-app-py && uv run python -c "from src.tools import knowledge_search; print(knowledge_search.name)"`
Expected: `knowledge_search`

- [ ] **Step 4: Commit**

```bash
git add backend/src/tools/knowledge.py backend/src/tools/__init__.py
git commit -m "feat: 添加 knowledge_search 工具"
```

---

### Task 7: Agent 集成

**Files:**
- Modify: `backend/src/agent/agent.py`

- [ ] **Step 1: 更新 agent.py 注册工具和 prompt**

修改 `backend/src/agent/agent.py`：

```python
"""Agent 核心实现"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_agent

from src.config import settings
from src.tools import calculator, search, knowledge_search


SYSTEM_PROMPT = """你是一个有用的 AI 助手。

你可以使用以下工具:
- calculator: 计算数学表达式
- search: 搜索互联网获取信息
- knowledge_search: 搜索本地知识库，查找已上传文档中的相关内容

当用户的问题可能与知识库中的文档相关时，优先使用 knowledge_search 工具检索。
使用检索到的内容作为依据回答问题，并引用来源文件名。
如果知识库中没有相关信息，如实告知用户，然后尝试用其他方式回答。

请用中文回答用户的问题。"""


class Agent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.model,
            base_url=settings.base_url,
            api_key=settings.api_key,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,  # type: ignore[call-arg]
        )
        self.tools = [calculator, search, knowledge_search]
        self.agent = create_agent(self.llm, self.tools)  # type: ignore[call-arg]

    def chat(self, message: str) -> str:
        """单轮对话"""
        response = self.agent.invoke({
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=message),
            ]
        })
        return response["messages"][-1].content

    async def chat_stream(self, message: str):
        """流式对话（逐 token 输出）"""
        async for event in self.agent.astream_events({
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=message),
            ]
        }, version="v2"):
            if event["event"] == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    yield content


def build_agent() -> Agent:
    return Agent()
```

- [ ] **Step 2: 验证 Agent 可正常启动**

Run: `cd e:/my-app-py && uv run python -c "from src.agent import build_agent; a = build_agent(); print('Agent 工具:', [t.name for t in a.tools])"`
Expected: `Agent 工具: ['calculator', 'search', 'knowledge_search']`

- [ ] **Step 3: Commit**

```bash
git add backend/src/agent/agent.py
git commit -m "feat: Agent 集成 knowledge_search 工具"
```

---

### Task 8: 后端 API 端点

**Files:**
- Modify: `backend/server.py`

- [ ] **Step 1: 添加 /knowledge API 端点**

修改 `backend/server.py`，在现有代码基础上新增知识库路由。完整文件如下：

```python
"""FastAPI 后端服务"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import time
import json
import shutil

from src.agent import Agent, build_agent
from src.rag import DocumentPipeline
from src.config import settings

DIST_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化 Agent 和管线，关闭时清理"""
    app.state.agent = build_agent()
    app.state.pipeline = DocumentPipeline()
    # 确保上传目录存在
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="AI Agent API", lifespan=lifespan)

# 允许前端跨域（开发模式 Vite 代理需要）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request_time(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    ms = (time.time() - start) * 1000
    print(f"{request.method} {request.url.path} -> {response.status_code} ({ms:.0f}ms)")
    return response


class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
def chat(req: ChatRequest):
    """单轮对话接口"""
    agent: Agent = app.state.agent
    response = agent.chat(req.message)
    return {"reply": response}


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """流式对话接口（SSE）"""
    agent: Agent = app.state.agent

    async def event_generator():
        start = time.time()
        async for chunk in agent.chat_stream(req.message):
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        yield "data: [DONE]\n\n"
        ms = (time.time() - start) * 1000
        print(f"POST /chat/stream 完成 ({ms:.0f}ms)")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ========== 知识库 API ==========

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".xlsx", ".xls"}


@app.post("/knowledge/upload")
async def knowledge_upload(file: UploadFile = File(...)):
    """上传文档到知识库"""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}。支持: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # 保存文件
    upload_path = Path(settings.upload_dir) / file.filename
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 处理入库
    pipeline: DocumentPipeline = app.state.pipeline
    try:
        result = pipeline.ingest(str(upload_path))
        return result
    except Exception as e:
        # 处理失败时清理文件
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"文档处理失败: {e}")


@app.get("/knowledge/list")
async def knowledge_list():
    """列出已入库文档"""
    pipeline: DocumentPipeline = app.state.pipeline
    return pipeline.list_documents()


@app.delete("/knowledge/{filename}")
async def knowledge_delete(filename: str):
    """删除指定文档"""
    pipeline: DocumentPipeline = app.state.pipeline
    pipeline.delete(filename)

    # 删除原始文件
    upload_path = Path(settings.upload_dir) / filename
    upload_path.unlink(missing_ok=True)

    return {"deleted": filename}


class SearchRequest(BaseModel):
    query: str
    k: int = 4


@app.post("/knowledge/search")
async def knowledge_search_api(req: SearchRequest):
    """知识库检索（调试用）"""
    pipeline: DocumentPipeline = app.state.pipeline
    results = pipeline.search(req.query, k=req.k)
    return [
        {
            "content": doc.page_content,
            "source": doc.metadata.get("source", ""),
            "chunk_id": doc.metadata.get("chunk_id", 0),
        }
        for doc in results
    ]


@app.get("/health")
def health():
    """健康检查"""
    return {"status": "ok"}


# 挂载前端静态资源
if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA 兜底：非 API 路径返回 index.html"""
        file_path = DIST_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(DIST_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 2: 验证服务器可启动**

Run: `cd e:/my-app-py && timeout 5 uv run python backend/server.py || true`
Expected: 服务器启动日志，无 import 错误（5 秒后自动退出）

- [ ] **Step 3: Commit**

```bash
git add backend/server.py
git commit -m "feat: 添加知识库 API 端点"
```

---

### Task 9: 前端 — Tailwind CSS 和布局改造

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/src/App.css`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 在 index.html 引入 Tailwind CSS CDN**

修改 `frontend/index.html`：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AI Agent Chat</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: 清空 App.css（迁移到 Tailwind）**

清空 `frontend/src/App.css` 为：

```css
/* 样式已迁移到 Tailwind CSS */
```

- [ ] **Step 3: 用 Tailwind 重写 App.tsx**

修改 `frontend/src/App.tsx`，添加 Tab 切换和 Tailwind 样式：

```tsx
import { useState } from 'react'
import ChatPanel from './ChatPanel'
import KnowledgePanel from './KnowledgePanel'

type Tab = 'chat' | 'knowledge'

function App() {
  const [tab, setTab] = useState<Tab>('chat')

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col">
      <header className="bg-white shadow-sm">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-6">
          <h1 className="text-xl font-bold text-gray-800">AI Agent</h1>
          <nav className="flex gap-1">
            <button
              onClick={() => setTab('chat')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                tab === 'chat'
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              聊天
            </button>
            <button
              onClick={() => setTab('knowledge')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                tab === 'knowledge'
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              知识库管理
            </button>
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-4xl w-full mx-auto p-4">
        {tab === 'chat' ? <ChatPanel /> : <KnowledgePanel />}
      </main>
    </div>
  )
}

export default App
```

- [ ] **Step 4: 提取 ChatPanel 组件**

创建 `frontend/src/ChatPanel.tsx`，将原 App.tsx 中的聊天逻辑提取出来：

```tsx
import { useState, useRef, useEffect } from 'react'

interface Message {
  role: 'user' | 'ai'
  text: string
}

function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'ai', text: '你好！我是 AI 助手，有什么可以帮你的？' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    const text = input.trim()
    if (!text || loading) return

    setMessages(prev => [...prev, { role: 'user', text }])
    setInput('')
    setLoading(true)

    try {
      const res = await fetch('/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      })
      if (!res.ok) throw new Error('请求失败')

      const textStream = res.body!.pipeThrough(new TextDecoderStream())
      const reader = textStream.getReader()
      let aiText = ''
      let buffer = ''

      setMessages(prev => [...prev, { role: 'ai', text: '' }])

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += value
        const parts = buffer.split('\n\n')
        buffer = parts.pop()!

        for (const part of parts) {
          const dataLine = part.trim()
          if (!dataLine.startsWith('data: ')) continue
          const data = dataLine.slice(6)
          if (data === '[DONE]') return

          try {
            const parsed = JSON.parse(data)
            aiText += parsed.content
            setMessages(prev => {
              const updated = [...prev]
              updated[updated.length - 1] = { role: 'ai', text: aiText }
              return updated
            })
          } catch {
            // 忽略解析错误
          }
        }
      }
    } catch {
      setMessages(prev => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        if (last.role === 'ai' && !last.text) {
          updated[updated.length - 1] = { role: 'ai', text: '请求失败，请检查网络连接。' }
        }
        return updated
      })
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-120px)]">
      <div className="flex-1 overflow-y-auto space-y-3 mb-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] px-4 py-2 rounded-2xl text-sm ${
              msg.role === 'user'
                ? 'bg-blue-500 text-white rounded-br-md'
                : 'bg-white text-gray-800 shadow-sm rounded-bl-md'
            }`}>
              {msg.text || (loading && i === messages.length - 1 ? '思考中...' : '')}
            </div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息..."
          disabled={loading}
          className="flex-1 px-4 py-2 rounded-xl border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-50"
        />
        <button
          onClick={sendMessage}
          disabled={loading || !input.trim()}
          className="px-6 py-2 bg-blue-500 text-white rounded-xl hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          发送
        </button>
      </div>
    </div>
  )
}

export default ChatPanel
```

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html frontend/src/App.css frontend/src/App.tsx frontend/src/ChatPanel.tsx
git commit -m "feat: 前端迁移到 Tailwind CSS，添加 Tab 布局"
```

---

### Task 10: 前端 — 知识库管理面板

**Files:**
- Create: `frontend/src/KnowledgePanel.tsx`

- [ ] **Step 1: 实现 KnowledgePanel 组件**

创建 `frontend/src/KnowledgePanel.tsx`：

```tsx
import { useState, useEffect, useCallback } from 'react'

interface DocInfo {
  filename: string
  chunk_count: number
}

interface SearchResult {
  content: string
  source: string
  chunk_id: number
}

const ALLOWED_FORMATS = '.txt,.md,.pdf,.docx,.xlsx,.xls'

function KnowledgePanel() {
  const [docs, setDocs] = useState<DocInfo[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)

  const fetchDocs = useCallback(async () => {
    try {
      const res = await fetch('/knowledge/list')
      const data = await res.json()
      setDocs(data)
    } catch {
      // 静默处理
    }
  }, [])

  useEffect(() => {
    fetchDocs()
  }, [fetchDocs])

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setUploading(true)
    setUploadMsg('')

    for (const file of Array.from(files)) {
      const form = new FormData()
      form.append('file', file)
      try {
        const res = await fetch('/knowledge/upload', { method: 'POST', body: form })
        if (!res.ok) {
          const err = await res.json()
          setUploadMsg(`上传失败: ${err.detail}`)
          continue
        }
        const result = await res.json()
        setUploadMsg(`已上传 ${result.filename}，${result.chunk_count} 个片段`)
      } catch {
        setUploadMsg('上传失败，请检查网络连接')
      }
    }

    setUploading(false)
    fetchDocs()
  }

  const handleDelete = async (filename: string) => {
    if (!confirm(`确定删除 ${filename}？`)) return
    try {
      await fetch(`/knowledge/${encodeURIComponent(filename)}`, { method: 'DELETE' })
      fetchDocs()
    } catch {
      // 静默处理
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const res = await fetch('/knowledge/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery }),
      })
      const data = await res.json()
      setSearchResults(data)
    } catch {
      setSearchResults([])
    }
    setSearching(false)
  }

  return (
    <div className="space-y-6">
      {/* 上传区 */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">上传文档</h2>
        <div
          className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-blue-400 transition-colors cursor-pointer"
          onDragOver={e => e.preventDefault()}
          onDrop={e => {
            e.preventDefault()
            handleUpload(e.dataTransfer.files)
          }}
          onClick={() => document.getElementById('file-input')?.click()}
        >
          <input
            id="file-input"
            type="file"
            accept={ALLOWED_FORMATS}
            multiple
            className="hidden"
            onChange={e => handleUpload(e.target.files)}
          />
          <p className="text-gray-500">
            {uploading ? '处理中...' : '拖拽文件到此处，或点击选择文件'}
          </p>
          <p className="text-xs text-gray-400 mt-2">
            支持格式：TXT、Markdown、PDF、Word、Excel
          </p>
        </div>
        {uploadMsg && (
          <p className="mt-2 text-sm text-green-600">{uploadMsg}</p>
        )}
      </div>

      {/* 文档列表 */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">已入库文档</h2>
        {docs.length === 0 ? (
          <p className="text-gray-400 text-sm">暂无文档，请上传文件</p>
        ) : (
          <div className="divide-y divide-gray-100">
            {docs.map(doc => (
              <div key={doc.filename} className="flex items-center justify-between py-3">
                <div>
                  <p className="text-sm font-medium text-gray-700">{doc.filename}</p>
                  <p className="text-xs text-gray-400">{doc.chunk_count} 个片段</p>
                </div>
                <button
                  onClick={() => handleDelete(doc.filename)}
                  className="text-red-500 hover:text-red-700 text-sm transition-colors"
                >
                  删除
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 搜索测试 */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">知识库搜索</h2>
        <div className="flex gap-2 mb-4">
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="输入搜索内容..."
            className="flex-1 px-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <button
            onClick={handleSearch}
            disabled={searching}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors"
          >
            {searching ? '搜索中...' : '搜索'}
          </button>
        </div>
        {searchResults.length > 0 && (
          <div className="space-y-3">
            {searchResults.map((r, i) => (
              <div key={i} className="bg-gray-50 rounded-lg p-4">
                <p className="text-xs text-gray-400 mb-1">来源: {r.source} (片段 #{r.chunk_id})</p>
                <p className="text-sm text-gray-700">{r.content}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default KnowledgePanel
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/KnowledgePanel.tsx
git commit -m "feat: 添加知识库管理面板"
```

---

### Task 11: Vite 代理配置

**Files:**
- Modify: `frontend/vite.config.ts`

- [ ] **Step 1: 添加 /knowledge 代理规则**

修改 `frontend/vite.config.ts`：

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/chat': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/knowledge': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': 'http://localhost:8000',
    }
  }
})
```

- [ ] **Step 2: Commit**

```bash
git add frontend/vite.config.ts
git commit -m "feat: 添加 /knowledge API 代理"
```

---

### Task 12: 端到端验证

- [ ] **Step 1: 启动后端服务**

Run: `cd e:/my-app-py && uv run python backend/server.py &`
Expected: 服务启动在 8000 端口

- [ ] **Step 2: 启动前端开发服务器**

Run: `cd e:/my-app-py/frontend && npm run dev &`
Expected: Vite 启动在 5173 端口

- [ ] **Step 3: 验证健康检查**

Run: `curl http://localhost:8000/health`
Expected: `{"status":"ok"}`

- [ ] **Step 4: 验证知识库列表（空）**

Run: `curl http://localhost:8000/knowledge/list`
Expected: `[]`

- [ ] **Step 5: 验证文件上传**

创建测试文件并上传：
```bash
echo "这是一个测试文档，用于验证 RAG 知识库功能。" > /tmp/test.txt
curl -X POST http://localhost:8000/knowledge/upload -F "file=@/tmp/test.txt"
```
Expected: `{"filename": "test.txt", "chunk_count": ...}`

- [ ] **Step 6: 验证知识库列表（有数据）**

Run: `curl http://localhost:8000/knowledge/list`
Expected: `[{"filename": "test.txt", "chunk_count": ...}]`

- [ ] **Step 7: 验证知识库搜索**

Run: `curl -X POST http://localhost:8000/knowledge/search -H "Content-Type: application/json" -d '{"query": "RAG 知识库"}'`
Expected: 返回包含测试文档内容的搜索结果

- [ ] **Step 8: 验证前端 UI**

在浏览器打开 `http://localhost:5173`，确认：
1. Tab 切换正常
2. 知识库管理面板显示已上传文档
3. 搜索功能返回结果
4. 聊天功能正常工作

- [ ] **Step 9: 运行全部测试**

Run: `cd e:/my-app-py && uv run pytest tests/ -v`
Expected: 全部通过

- [ ] **Step 10: 最终 Commit**

```bash
git add -A
git commit -m "feat: RAG 本地知识库问答机器人完成"
```
