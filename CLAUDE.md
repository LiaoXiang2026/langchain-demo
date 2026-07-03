# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

基于 LangChain 的 AI Agent，聚焦 RAG 知识库问答。前端（React，独立项目仓库）通过 SSE 与后端（FastAPI）通信，Agent 自主决定是否调用 `knowledge_search` 检索知识库文档回答问题。

LLM 通过 OpenAI 兼容协议接入（默认 DeepSeek）。**向量检索/嵌入走本地 sentence-transformers + numpy（Qwen3-Embedding-0.6B）**，数据存储在 data/ 目录下的 JSON/NPY 文件中。文档分块针对中文标点调优。

> 前端已剥离至独立项目（见 commit c0af3b3），本仓库只含后端。`server.py` 仍会在 `frontend/dist/` 存在时挂载其静态资源 + SPA 兜底路由，但本仓库不再持有前端源码。

## Commands

```bash
# 后端（要求 Python >=3.10）
uv sync                                  # 安装/同步 Python 依赖
uv run python server.py                  # FastAPI 服务（端口 8000，启用 reload）
uv run pytest tests/ -v                  # 运行全部测试
uv run pytest tests/test_cleaner.py -v   # 跑单个测试文件

# Docker 部署（生产）
docker compose up -d --build             # 构建并启动 backend（端口 8000，env_file=.env）
docker compose logs -f backend           # 跟随日志
docker compose down                      # 停止
```

配置从仓库根的 `.env` 读取（`settings.py` 调 `load_dotenv()`，环境变量优先于 dataclass 默认值）；参考 `.env.example`。

## Architecture

### 后端（`src/` + `server.py`）

**Agent 层** — `src/agent/agent.py`
- `Agent` 类封装 LLM（`ChatOpenAI`，走 `base_url` 兼容 OpenAI 协议）+ 工具列表 + 多轮历史
- `chat()` 单轮调用 `agent.invoke()`；`chat_stream()` 用 `agent.astream_events(version="v2")` 过滤 `on_chat_model_stream` 事件逐 token 输出
- 工具通过 `@tool` 装饰器定义（`src/tools/knowledge.py`），注册到 `Agent.tools`，目前仅 `knowledge_search` 一个工具
- `SYSTEM_PROMPT` 指导 Agent 优先使用 `knowledge_search` 回答文档相关问题，并要求引用来源文件名

**RAG 层** — `src/rag/`
- `document_loader.py`: `LOADER_MAP` 按扩展名分发（`.md` → `TextLoader`，`.pdf` → `PyMuPDFLoader`，`.html/.htm` → `WeChatHTMLLoader`）
- `cleaner.py`: 微信公众号 HTML 清洗器 — 编码检测（`chardet` 归一化到 GB18030，规避 GBK/GB2312 误判）→ BS4/lxml 解析 → **先**抽 JS 元数据 (`article_title`/`nickname`/`create_time`) **再** `decompose()` 掉 `<script>`（顺序不可换）→ 定位 `#js_content` → 剥关注卡片/推荐区/二维码 → 图片处理（剥 base64 `src`，保 `alt`，替换为 `[图片]` 占位防止 base64 撑爆 chunk）
- `splitter.py`: `RecursiveCharacterTextSplitter` 用中文分隔符 `["\n\n", "\n", "。", "！", "？", "；", " "]`，`chunk_size=500`
- `vectorstore.py`: 本地 numpy 存储封装（sentence-transformers + numpy 余弦相似度检索）。关键设计：
  - 使用 `sentence-transformers` 本地加载 Qwen3-Embedding-0.6B 模型生成嵌入
  - 嵌入向量存储为 `data/embeddings.npy`，文档块及元信息存储为 `data/chunks.json`
  - `add_documents()` 生成嵌入后追加至已有索引，documents 自动去重覆盖
  - `search()` 走余弦相似度暴力搜索，返回 K 个最相似 chunk 及元信息
  - `close()` 持久化内存索引到磁盘 JSON/NPY 文件
- `dedup.py`: `DedupIndex` 用清洗后正文 SHA256 作为去重键,存进 chunk metadata,通过 `VectorStore.exists_by_metadata(where={"content_hash": hash}, limit=1)` 短路重复入库。`exists()` 显式要求 `content_hash: str`,杜绝 `None` 流入 where filter
- `pipeline.py`: `DocumentPipeline` 暴露三个入口：
  - `ingest(file_path)` — 单文件,走 LOADER_MAP,不去重（向后兼容）
  - `ingest_cleaned(text, meta, content_hash)` — 底层接口,dedup 短路 → 注入 `content_hash` + `ingested_at` 到 metadata → 分块 → 入库
  - `ingest_batch(file_paths)` — 批量走 cleaner + dedup,单文件失败不中断批次,结果含 `new_count` / `skip_count` / `errors`

**服务层** — `server.py`
- `lifespan` 上下文管理器启动时构造 `app.state.agent` (Agent) 和 `app.state.pipeline` (DocumentPipeline),关闭时清理
- CORS 全开（`*`）;`X-Process-Time` 中间件记录耗时
- 前端构建产物在 `frontend/dist/` 存在时挂载 `/assets` 静态资源 + SPA 兜底路由返回 `index.html`
- 上传时严格校验扩展名（`ALLOWED_EXTENSIONS = {".md", ".pdf", ".html", ".htm"}`）,处理失败时 `unlink(missing_ok=True)` 清理已落盘文件
- `/api/chat` 实现 Vercel AI SDK UI Message Stream Protocol: 发送 `text-start` → 多个 `text-delta` → `text-end` → `[DONE]`
- 知识库与健康检查 HTTP 端点统一使用 `/api` 前缀（如 `/api/knowledge/*`、`/api/health`）

**配置** — `src/config/settings.py`
- `@dataclass` + `__post_init__` 从 `os.getenv` 覆盖默认值;环境变量优先
- 支持变量: `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `MODEL_NAME` / `DATA_DIR` / `EMBEDDING_MODEL` / `UPLOAD_DIR`
- `chunk_size=500` / `chunk_overlap=50` / `search_top_k=4` 硬编码在 dataclass,未暴露为环境变量
- **search_top_k 语义**:表示"最多 K 个 chunk"（按相似度排序,可能多个 chunk 来自同一 source）

### API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/chat` | AI SDK 流式对话（SSE,Vercel UI Message Stream Protocol） |
| `POST` | `/api/knowledge/upload` | 上传文档（multipart）,走 `DocumentPipeline.ingest()` |
| `GET` | `/api/knowledge/list` | 列出已入库文档（按 filename 聚合 chunk_count） |
| `DELETE` | `/api/knowledge/{filename}` | 删除向量库记录 + 本地文件 |
| `POST` | `/api/knowledge/search` | 直接检索（调试用）,请求体 `{"query": str, "k": int=4}` |
| `POST` | `/api/knowledge/recluster` | 重新聚类知识库文档 |
| `GET` | `/api/knowledge/clusters` | 获取聚类结果列表 |
| `GET` | `/api/health` | 健康检查 |

### 前端

前端为独立项目仓库，不在此处维护。后端契约约定：聊天走 `/api/chat`（Vercel AI SDK UI Message Stream Protocol，见上），知识库走 `/api/knowledge/*`。`/api/chat` 请求体为 AI SDK 格式 `{"messages": [{role, parts: [{type:"text", text}]}]}`，服务端只取最后一条 role=user 消息的文本。

### 数据目录

- `data/uploads/` — 用户上传的原始文件
- `data/chunks.json` + `data/embeddings.npy` — 向量存储；`data/documents.json` — 文档元信息；`data/clusters.json` — 聚类结果
- `data/` 在 `.gitignore` 中,运行期生成

### 部署（Docker）

- `Dockerfile`: 基于 `python:3.10-slim`（Debian Bookworm），用官方 apt 源（VPS 在国外），装 `build-essential` + lxml 头文件（编译 C 扩展），用 `uv sync --frozen --no-dev` 装依赖，`uv run uvicorn server:app --workers 1 --proxy-headers` 启动。
- `docker-compose.yml`: 单 `backend` 服务，`uploads` volume 持久化 `data/uploads`，`env_file: .env`，healthcheck 打 `/api/health`
- 本地模型加载后后端常驻内存，单 worker 配置保证线程安全；多 worker 场景需注意嵌入模型的多进程加载开销。

### 测试（`tests/`）

- `test_cleaner.py` — WeChat HTML 清洗（编码、JS 元数据、噪声剥离、img 占位）
- `test_dedup.py` — SHA256 去重索引
- `test_document_loader.py` — 加载器分发
- `tests/fixtures/` — `wechat_sample.html` (UTF-8) + `wechat_sample_gbk.html` (GBK 编码,覆盖 chardet 边界 case)

> 注:`test_pipeline.py` / `test_vectorstore.py` 已由 `test_cleaner` + 实际入库流程覆盖。`test_dedup.py` 保留用于验证去重索引。

## Conventions

- **中文注释和文档字符串**,包括 module/function docstring
- `src/` 按功能分包（`config` / `agent` / `tools` / `rag`）,每个包有 `__init__.py` 导出公共接口
- 工具新增流程:在 `src/tools/` 加 `@tool` 函数,导入到 `src/agent/agent.py` 的 `tools` 列表,并在 `SYSTEM_PROMPT` 中声明用法
- 新增文档格式:扩 `LOADER_MAP`（`src/rag/document_loader.py`）+ 同步 `server.py` 的 `ALLOWED_EXTENSIONS`
- 配置变更:加 dataclass 字段 + `__post_init__` 里 `os.getenv(...)` 覆盖
- README.md 中的 `backend/` 项目结构已过时（项目实际根目录布局,无 `backend/` 目录）,修改架构时以 `src/` 实际位置为准
