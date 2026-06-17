# My App Py

## 快速开始

### 1. 安装依赖

```bash
# 后端（Python 3.14，使用 uv）
uv sync
```

### 2. 配置环境变量

在项目根目录创建 `.env`（参考 `.env.example`）：

```env
# LLM
DEEPSEEK_API_KEY=sk-你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
MODEL_NAME=deepseek-chat

# Chroma Cloud
CHROMA_HOST=europe-west1.gcp.trychroma.com
CHROMA_TENANT=12e28eb4-2ece-483b-91b5-0cce2b3546e0
CHROMA_DATABASE=RAG
CHROMA_API_KEY=ck-你的密钥
CHROMA_COLLECTION=knowledge_base
```

### 3. 启动

```bash
uv run python server.py          # FastAPI 服务（端口 8000，启用 reload）
```

访问 http://localhost:8000

> 若前端仓库执行 `npm run build` 并将产物放到本仓库的 `frontend/dist/`，`server.py` 会自动挂载 `/assets` 静态资源 + SPA 兜底路由；否则后端仅作为 API 服务对外提供。

基于 LangChain 的 AI Agent，聚焦 RAG 知识库问答。前端 (React) 通过 SSE 与后端 (FastAPI) 通信，Agent 自主决定是否调用 `knowledge_search` 检索知识库文档回答问题。

## 功能

- 智能对话（SSE 流式输出，Vercel AI SDK 协议）
- **RAG 知识库**：上传本地文档构建知识库，Agent 自动检索并引用来源回答
- **Chroma Cloud 托管嵌入**：Qwen3-Embedding-0.6B dense 嵌入由 Cloud 端完成,本机零模型
- **内容去重**：基于清洗后正文 SHA256 的入库短路，重复文档不再走嵌入
- **微信公众号 HTML 专项清洗**：编码自动检测（GBK/GB18030/UTF-8）、JS 元数据抽取、噪声剥离、base64 图片占位化

## 架构

前端（独立仓库，React）通过 SSE 与 FastAPI 后端通信；LangChain Agent 自主决定是否调用 `knowledge_search` 工具检索知识库；向量嵌入与检索全部由 Chroma Cloud 托管，本机不持有任何模型或索引。

```
┌─────────────────────┐
│  前端（独立仓库）     │  React + Vercel AI SDK
│  聊天 / 知识库管理    │
└──────────┬──────────┘
           │  HTTP / SSE
           ▼
┌─────────────────────────────────────────────────────┐
│  后端  server.py  (FastAPI :8000)                    │
│  ┌──────────────┐         ┌────────────────────┐    │
│  │  /api/chat   │         │  /knowledge/*      │    │
│  │  SSE 流式     │         │  上传/列表/删除/搜索 │    │
│  └──────┬───────┘         └─────────┬──────────┘    │
└─────────┼───────────────────────────┼───────────────┘
          │                           │
          ▼                           ▼
┌─────────────────────┐     ┌─────────────────────────────────────┐
│  Agent 层  src/agent │     │  RAG 层  src/rag                     │
│  ┌───────────────┐  │     │  DocumentPipeline                    │
│  │ ChatOpenAI    │  │     │   ├─ document_loader  按扩展名分发     │
│  │ (DeepSeek)    │  │     │   ├─ cleaner          微信 HTML 清洗   │
│  │ + 多轮历史     │  │     │   ├─ splitter         中文分块 500/50 │
│  │ + 流式输出     │  │     │   ├─ dedup            SHA256 去重短路 │
│  └───────┬───────┘  │     │   └─ pipeline         ingest / batch  │
│          │ tool call │     └──────────────────┬────────────────────┘
│          ▼          │                        │
│  ┌───────────────┐  │                        ▼
│  │knowledge_search│◄─┼──────────────┐  ┌──────────────────────┐
│  │   @tool       │  │              │  │  VectorStore          │
│  └───────┬───────┘  │              │  │  Chroma Cloud 封装     │
│          │ 检索结果  │              └──┤  col.add / col.query  │
└──────────┼──────────┘                 └──────────┬───────────┘
           │                                        │  Cloud API (443)
           │     ┌──────────────────┐               │
           │     │  DeepSeek API    │               ▼
           └────►│  OpenAI 兼容协议  │     ┌─────────────────────────────┐
                 │  deepseek-v4-flash│     │  Chroma Cloud (europe-west1) │
                 └──────────────────┘     │  collection: knowledge_base_v2│
                          ▲               │  Qwen3-Embedding-0.6B dense  │
                          │               │  ← Cloud 端嵌入+检索,本机零模型│
                          └─ token 流 ◄───┘                              │
                                          (一次往返返回 chunks+metadatas) │
                                          └─────────────────────────────┘
```

**核心数据流**

- **对话**：前端 → `/api/chat` → Agent 调 DeepSeek 生成 →（按需）`knowledge_search` 工具 → Chroma Cloud 检索 → 引用来源逐 token SSE 回流
- **入库**：前端上传 → `DocumentPipeline` → 加载 → 微信清洗 → 中文分块 → SHA256 去重短路 → Chroma Cloud 嵌入入库
- **检索**：单次 `col.query(query_texts=[q], n_results=4)`，Cloud 端完成嵌入 + 相似度检索，一次往返返回 chunks + metadatas

**关键设计**

- 本机零模型：嵌入/检索全部在 Cloud 端，后端是纯编排层，轻量到 946M VPS 单 worker 可跑
- Agent 自主路由：是否检索由 LLM 决定，非强制 RAG
- 单 dense 嵌入：Qwen3-Embedding-0.6B，无 RRF/Splade/GroupBy，`vectorstore.py < 100 行`


## 使用知识库

1. 打开前端，切换到「知识库管理」Tab
2. 上传文档（支持 **Markdown** / **PDF** / **微信公众号 HTML**（`.html` / `.htm`））
3. 切回「聊天」Tab，提问与文档相关的问题
4. Agent 会自动调用 `knowledge_search` 工具检索知识库，并引用来源文件名回答

> 微信公众号导出的 HTML 经过 `src/rag/cleaner.py` 专项处理：自动检测编码、剥掉关注卡片/推荐区/二维码、把 base64 内联图片替换为 `[图片]` 占位符（避免撑爆 chunk）、从 `<script>` JS 变量里抽取标题/作者/发布时间元数据。

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/chat` | SSE 流式对话（Vercel AI SDK UI Message Stream Protocol） |
| `POST` | `/knowledge/upload` | 上传文档（multipart） |
| `GET` | `/knowledge/list` | 列出已入库文档 |
| `DELETE` | `/knowledge/{filename}` | 删除指定文档（向量库 + 本地文件） |
| `POST` | `/knowledge/search` | 直接检索（调试用） |
| `GET` | `/health` | 健康检查 |

## 项目结构

```
server.py                      # FastAPI 入口（lifespan 管理 Agent + DocumentPipeline）
src/
  agent/agent.py               # Agent 核心（LLM + tools + 多轮历史 + 流式输出）
  config/settings.py           # 配置管理（@dataclass + env 覆盖）
  tools/
    knowledge.py               # 知识库检索（@tool，Agent 按需调用）
  rag/
    document_loader.py         # LOADER_MAP 按扩展名分发加载器
    cleaner.py                 # 微信公众号 HTML 清洗器
    splitter.py                # 中文分块（RecursiveCharacterTextSplitter）
    vectorstore.py             # Chroma Cloud 封装（单 dense 嵌入，col.add / col.query）
    dedup.py                   # 基于 SHA256 的内容去重索引
    pipeline.py                # DocumentPipeline（ingest / ingest_cleaned / ingest_batch）
data/
  uploads/                     # 用户上传的原始文件（运行时生成，.gitignore）
tests/
  test_cleaner.py              # WeChat HTML 清洗
  test_dedup.py                # SHA256 去重（依赖 Chroma Cloud）
  test_document_loader.py      # 加载器分发
  fixtures/                    # wechat_sample.html (UTF-8) + wechat_sample_gbk.html (GBK)
```

## 技术栈

- **后端**：Python 3.14 + LangChain 1.3 + FastAPI + uv
- **LLM**：OpenAI 兼容接口（默认 DeepSeek `deepseek-chat`，可用 `MODEL_NAME` 覆盖）
- **向量库**：Chroma Cloud（Cloud 端持久化 + 托管嵌入，本机零模型）
- **嵌入模型**：Chroma Cloud 托管的 Qwen3-Embedding-0.6B (dense)，走 col.query() 单步检索
- **前端**：独立项目仓库（React + Vercel AI SDK），通过 SSE 调用 `/api/chat`

## 测试

```bash
uv run pytest tests/ -v
```

## 注意事项

- **Chroma Cloud 必填**：`CHROMA_API_KEY` 是必填环境变量，启动时若缺失会报 `RuntimeError`
- **Docker 镜像瘦身**：相比原本地嵌入栈,Cloud 模式不再需要 `libgomp1` / sentence-transformers / PyTorch / 本地模型烘焙,镜像显著减小
