# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

基于 LangChain 的 AI Agent，支持工具调用（计算器、搜索）和 RAG 本地知识库问答。用户可上传文档（TXT/MD/PDF/Word/Excel）构建知识库，Agent 自动检索回答问题。

## Commands

```bash
# 后端
uv sync                       # 安装/同步 Python 依赖
uv run python backend/server.py  # FastAPI 服务（端口 8000）
uv run pytest tests/ -v        # 运行全部测试

# 前端
cd frontend
npm install                    # 安装前端依赖
npm run dev                    # Vite 开发服务器（端口 5173，代理 /chat 和 /knowledge 到 8000）
npm run build                  # 构建到 frontend/dist
```

## Architecture

**后端**：Python 3.14 + LangChain + FastAPI，uv 管理依赖

- `Agent`（`backend/src/agent/agent.py`）：封装 LLM + tools，`chat()` 单轮，`chat_stream()` SSE 流式输出
- 工具通过 `@tool` 装饰器定义，注册到 `agent.py` 的 `tools` 列表
- `DocumentPipeline`（`backend/src/rag/pipeline.py`）：文档处理管线（加载→分块→嵌入→存储）
- `VectorStore`（`backend/src/rag/vectorstore.py`）：ChromaDB 封装，支持 CRUD 和相似度搜索
- `knowledge_search` 工具（`backend/src/tools/knowledge.py`）：延迟初始化管线，Agent 按需调用

**RAG 流程**：文档上传 → `document_loader.py` 加载 → `splitter.py` 分块 → `embeddings.py` 向量化 → `vectorstore.py` 存入 ChromaDB → Agent 的 `knowledge_search` 工具检索

**前端**：React + TypeScript + Vite + Tailwind CSS v4（npm 包集成，`@tailwindcss/vite` 插件）

- `ChatPanel.tsx`：聊天界面，SSE 流式输出
- `KnowledgePanel.tsx`：知识库管理（上传、列表、搜索）
- `App.tsx`：Tab 切换聊天/知识库

**数据目录**：`data/chroma_db/`（向量库）、`data/uploads/`（原始文件）

## Conventions

- 中文注释和文档字符串
- `backend/src/` 下按功能分包（config、agent、tools、rag），每个包有 `__init__.py` 导出公共接口
- 配置集中在 `Settings` dataclass（`backend/src/config/settings.py`），环境变量优先于默认值
- 嵌入模型 `shibing624/text2vec-base-chinese`，首次加载从 HF 缓存读取（约 400MB）
- Windows 上 ChromaDB 需调用 `store.close()` 释放文件锁后再删除临时目录
