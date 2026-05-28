# RAG 本地知识库问答机器人 — 设计文档

## 概述

在现有 LangChain Agent 基础上，新增 RAG（检索增强生成）能力，支持用户上传本地文档（TXT、Markdown、PDF、Word、Excel），构建向量知识库，Agent 自动决定何时检索知识库来回答问题。

## 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 向量数据库 | ChromaDB | 零依赖，本地 SQLite，适合开发和小规模使用 |
| 嵌入模型 | HuggingFace `shibing624/text2vec-base-chinese` | 中文效果好，本地运行，无需 API key |
| 文档加载 | LangChain Community Loaders | 统一接口，支持多种格式 |
| 分块器 | RecursiveCharacterTextSplitter | 中文友好的分隔符策略 |
| 前端样式 | Tailwind CSS CDN (v4) | 零构建配置，快速开发 |

## 架构

### 整体架构

```
用户提问
  ↓
Agent (LLM + Tools)
  ├── calculator     (已有)
  ├── search         (已有)
  └── knowledge_search  (新增) → ChromaDB → HuggingFace Embeddings
                                      ↑
                            文档处理管线 ← 用户上传文档
```

### 新增目录结构

```
backend/
  src/
    tools/
      knowledge.py          # knowledge_search 工具
    rag/
      __init__.py
      document_loader.py    # 文档加载（多格式）
      splitter.py           # 文档分块
      embeddings.py         # 嵌入模型管理
      vectorstore.py        # ChromaDB 管理
      pipeline.py           # 文档处理管线（加载→分块→嵌入→存储）
data/
  chroma_db/                # ChromaDB 持久化目录
  uploads/                  # 用户上传的原始文件
frontend/
  src/
    KnowledgePanel.tsx      # 知识库管理组件
```

## 文档处理管线

### 文档加载

按文件扩展名分发到对应的 Loader：

| 格式 | Loader | 依赖 |
|------|--------|------|
| `.txt` | `TextLoader` | 内置 |
| `.md` | `TextLoader` | 内置 |
| `.pdf` | `PyMuPDFLoader` | `pymupdf` |
| `.docx` | `Docx2txtLoader` | `docx2txt` |
| `.xlsx` / `.xls` | `UnstructuredExcelLoader` | `openpyxl` |

### 分块策略

```
RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "！", "？", "；", " "]
)
```

- 500 字符的 chunk_size 适合中文段落粒度
- 50 字符重叠保证上下文连续性
- 中文标点作为优先分隔符

### 向量化与存储

- 嵌入模型：`shibing624/text2vec-base-chinese`（首次运行自动下载，约 100MB）
- ChromaDB 持久化路径：`data/chroma_db/`
- 每个 chunk 存储：向量、文本内容、来源文件名、chunk 序号

## RAG 工具

### knowledge_search 工具定义

```python
@tool
def knowledge_search(query: str) -> str:
    """搜索本地知识库，查找与问题相关的文档内容。当用户询问可能在知识库中有答案的问题时使用此工具。"""
    # 1. ChromaDB similarity_search(query, k=4)
    # 2. 格式化结果：每个结果包含来源文件名和内容
    # 3. 返回拼接的上下文字符串
```

### Agent 集成

- 将 `knowledge_search` 加入 `agent.py` 的 `tools` 列表
- 更新 `SYSTEM_PROMPT`，新增指引：
  - 当用户问题可能与知识库中的文档相关时，优先使用 `knowledge_search`
  - 使用检索到的内容作为依据回答问题
  - 如果知识库中没有相关信息，如实告知

### 流式输出

`chat_stream` 方法无需修改。Agent 在工具调用和最终回答之间的流式输出保持不变。

## 后端 API

### 新增端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/knowledge/upload` | 上传文档，处理入库 |
| `GET` | `/knowledge/list` | 列出已入库文档 |
| `DELETE` | `/knowledge/{filename}` | 删除指定文档（filename 为原始文件名） |
| `POST` | `/knowledge/search` | 知识库检索（调试用） |

### 上传流程

1. 接收文件（`UploadFile`）
2. 保存到 `data/uploads/`
3. 调用文档处理管线：加载 → 分块 → 嵌入 → 存入 ChromaDB
4. 返回处理结果（文件名、chunk 数量）

### 删除流程

1. 根据 `filename` 从 ChromaDB 中删除 metadata 匹配的 chunks
2. 删除 `data/uploads/` 中的原始文件

## 前端 UI

### 布局

在现有聊天界面上方加一个 Tab 切换：
- **聊天**：现有的对话界面
- **知识库管理**：文档上传和管理

### Tailwind CSS CDN

在 `index.html` 中引入：
```html
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
```

所有样式使用 Tailwind 原子类，不写自定义 CSS。

### 知识库管理面板

1. **上传区**：拖拽上传 + 点击上传，显示支持格式提示
2. **文档列表**：文件名、上传时间、chunk 数量、删除按钮
3. **搜索测试**：输入查询词，展示检索结果和来源

### API 代理

Vite 开发服务器新增代理规则：
```ts
'/knowledge': { target: 'http://localhost:8000', changeOrigin: true }
```

## 依赖新增

### Python（pyproject.toml）

```
chromadb>=0.4.0
langchain-community>=0.0.1
sentence-transformers>=2.2.0
pymupdf>=1.23.0
docx2txt>=0.8
openpyxl>=3.1.0
```

### 前端

无新增 npm 依赖（Tailwind 通过 CDN 引入）。

## 配置

`Settings` dataclass 新增：

```python
# RAG 配置
chroma_dir: str = "data/chroma_db"
upload_dir: str = "data/uploads"
embedding_model: str = "shibing624/text2vec-base-chinese"
chunk_size: int = 500
chunk_overlap: int = 50
search_top_k: int = 4
```

所有配置可通过环境变量覆盖。

## 错误处理

- 上传不支持的格式 → 返回 400 + 格式提示
- 文档处理失败 → 返回 500 + 错误信息，不影响已有知识库
- ChromaDB 查询失败 → 工具返回错误信息，Agent 如实告知用户
- 嵌入模型下载失败 → 启动时检查，给出明确提示

## 测试策略

- 文档加载器：每种格式准备一个示例文件，验证加载和分块
- 向量存储：验证 CRUD 操作和相似度搜索
- API 端点：验证上传、列表、删除的 HTTP 响应
- Agent 集成：验证 Agent 能正确调用 knowledge_search 并基于检索结果回答
