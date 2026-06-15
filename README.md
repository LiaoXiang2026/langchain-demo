# My App Py

基于 LangChain 的 AI Agent，支持工具调用和 RAG 本地知识库问答。前端 (React) 通过 SSE 与后端 (FastAPI) 通信，Agent 自主决定是否调用 `knowledge_search` 检索本地文档回答问题。

## 功能

- 智能对话（SSE 流式输出，Vercel AI SDK 协议）
- 工具调用：计算器（`simpleeval` 沙箱求值）、搜索（占位，待接入真实搜索 API）
- **RAG 知识库**：上传本地文档构建知识库，Agent 自动检索并引用来源回答
- **微信公众号 HTML 专项清洗**：编码自动检测（GBK/GB18030/UTF-8）、JS 元数据抽取、噪声剥离、base64 图片占位化
- **内容去重**：基于清洗后正文 SHA256 的入库短路，重复文档不再走嵌入

## 快速开始

### 1. 安装依赖

```bash
# 后端（Python 3.14，使用 uv）
uv sync

# 前端
cd frontend && npm install
```

### 2. 配置环境变量

在项目根目录创建 `.env`（参考 `.env.example`）：

```env
DEEPSEEK_API_KEY=sk-你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
MODEL_NAME=deepseek-chat
```

可选变量：`CHROMA_DIR`（默认 `data/chroma_db`）、`UPLOAD_DIR`（默认 `data/uploads`）、`EMBEDDING_MODEL`（默认 `shibing624/text2vec-base-chinese`）。

### 3. 启动

**开发模式（推荐）：**

```bash
# 终端 1：启动后端（端口 8000，启用 reload）
uv run python server.py

# 终端 2：启动前端（端口 5173，代理 /api /chat /knowledge /health → 8000）
cd frontend && npm run dev
```

访问 http://localhost:5173

**生产模式：**

```bash
cd frontend && npm run build     # tsc 类型检查 + Vite 构建到 frontend/dist
uv run python server.py          # 自动挂载 frontend/dist 作为静态资源
```

访问 http://localhost:8000

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
    calculator.py              # 计算器（@tool + simpleeval）
    search.py                  # 搜索（占位）
    knowledge.py               # 知识库检索（@tool，Agent 按需调用）
  rag/
    document_loader.py         # LOADER_MAP 按扩展名分发加载器
    cleaner.py                 # 微信公众号 HTML 清洗器
    splitter.py                # 中文分块（RecursiveCharacterTextSplitter）
    embeddings.py              # HuggingFace 嵌入（含 HF 缓存路径解析）
    vectorstore.py             # ChromaDB 封装（CRUD + 搜索 + metadata 隔离）
    dedup.py                   # 基于 SHA256 的内容去重索引
    pipeline.py                # DocumentPipeline（ingest / ingest_cleaned / ingest_batch）
frontend/
  src/
    App.tsx                    # Tab 切换（聊天 / 知识库）
    ChatPanel.tsx              # 聊天界面（useChat 钩子 + SSE）
    KnowledgePanel.tsx         # 知识库管理（上传 / 列表 / 搜索 / 删除）
  vite.config.ts               # 代理配置
data/
  chroma_db/                   # ChromaDB 持久化（运行时生成，.gitignore）
  uploads/                     # 用户上传的原始文件（运行时生成，.gitignore）
tests/
  test_cleaner.py              # WeChat HTML 清洗
  test_dedup.py                # SHA256 去重
  test_document_loader.py      # 加载器分发
  test_pipeline.py             # 管线端到端
  test_vectorstore.py          # ChromaDB CRUD + 搜索
  fixtures/                    # wechat_sample.html (UTF-8) + wechat_sample_gbk.html (GBK)
```

## 技术栈

- **后端**：Python 3.14 + LangChain 1.3 + FastAPI + uv
- **前端**：React 19 + TypeScript + Vite + Tailwind CSS v4（`@tailwindcss/vite` 插件）
- **前端 AI 集成**：Vercel AI SDK v6（`@ai-sdk/react` + `ai`）+ Ant Design X v2
- **LLM**：OpenAI 兼容接口（默认 DeepSeek `deepseek-chat`）
- **嵌入模型**：`shibing624/text2vec-base-chinese`（HuggingFace，~400MB 首次下载）
- **向量库**：ChromaDB 持久化到本地 `data/chroma_db/`

## 测试

```bash
uv run pytest tests/ -v
```

## 注意事项

- **Windows 平台**：删除 `data/chroma_db/` 前需先 `VectorStore.close()` 释放文件锁
- **首次运行**：嵌入模型从 HuggingFace Hub 下载，模型会缓存在 `~/.cache/huggingface/hub/`；`src/rag/embeddings.py` 会自动解析 `snapshots/<rev>/` 子目录（直接传外层 cache 路径会触发 "Unrecognized model" 错误）
- **`search` 工具**当前是占位实现，需要替换为 Tavily / SerpAPI 等真实搜索 API
