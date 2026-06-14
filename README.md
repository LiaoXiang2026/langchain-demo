# My App Py

基于 LangChain 的 AI Agent，支持工具调用和 RAG 本地知识库问答。

## 功能

- 智能对话（流式输出）
- 工具调用：计算器、搜索
- **RAG 知识库**：上传本地文档（TXT/MD/PDF/Word/Excel），Agent 自动检索回答问题

## 快速开始

### 1. 安装依赖

```bash
# 后端
uv sync

# 前端
cd frontend && npm install
```

### 2. 配置环境变量

创建 `.env` 文件：

```
DEEPSEEK_API_KEY=你的API密钥
```

### 3. 启动

**开发模式（推荐）：**

```bash
# 终端 1：启动后端
uv run backend/server.py

# 终端 2：启动前端
cd frontend && npm run dev
```

访问 http://localhost:5173

**生产模式：**

```bash
cd frontend && npm run build
uv run backend/server.py
```

访问 http://localhost:8000

**CLI 模式（纯命令行）：**

```bash
uv run backend/main.py
```

## 使用知识库

1. 打开前端，切换到「知识库管理」Tab
2. 上传文档（支持 TXT、Markdown、PDF、Word、Excel）
3. 切回「聊天」Tab，提问与文档相关的问题
4. Agent 会自动检索知识库并引用来源回答

## 项目结构

```
backend/
  main.py                   # CLI 入口
  server.py                 # FastAPI 服务（含知识库 API）
  src/
    agent/agent.py          # Agent 核心（工具调用 + RAG）
    config/settings.py      # 配置管理
    tools/
      calculator.py         # 计算器工具
      search.py             # 搜索工具
      knowledge.py          # 知识库检索工具
    rag/
      document_loader.py    # 多格式文档加载
      splitter.py           # 文档分块
      embeddings.py         # 嵌入模型管理
      vectorstore.py        # ChromaDB 向量存储
      pipeline.py           # 文档处理管线
frontend/
  src/
    App.tsx                 # Tab 切换（聊天/知识库）
    ChatPanel.tsx           # 聊天界面
    KnowledgePanel.tsx      # 知识库管理界面
  index.html
  vite.config.ts
data/
  chroma_db/                # ChromaDB 持久化存储
  uploads/                  # 用户上传的原始文件
```

## 技术栈

- **后端**：Python 3.14 + LangChain + FastAPI
- **前端**：React + TypeScript + Vite + Tailwind CSS
- **LLM**：OpenAI 兼容接口
- **RAG**：ChromaDB + HuggingFace Embeddings (`text2vec-base-chinese`)

## 测试

```bash
uv run pytest tests/ -v
```
