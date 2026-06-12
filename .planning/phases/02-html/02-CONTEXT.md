# Phase 2: HTML 微信公众号知识库批量导入 - Context

**Gathered:** 2026-06-12
**Status:** Ready for planning
**Source:** /gsd:explore (Socratic ideation; no discuss-phase run)

<domain>
## Phase Boundary

把现有 LangChain + FastAPI + RAG 项目从"通用文档问答"聚焦为"个人微信公众号文章知识库"：
- 支持批量上传整个 HTML 文件夹
- 清洗微信公众号导出的 HTML 噪声
- 增量入库 + 去重
- Agent 调整为"跨文章挖观点 + 引用"模式

明确**不做**：多用户、鉴权、云存储、自动监听、其他文档格式。

</domain>

<decisions>
## Implementation Decisions

### 产品形态
- **D-01:** Q&A 类型固定为"挖观点"——跨多篇文章综合 + 引用具体文章标题
- **D-02:** 回答形式：**综合 + 引用**（综合一段流式文本，每条关键观点后跟"出处：xxx 文章"）
- **D-03:** 服务对象：仅用户本人，无多租户/无鉴权
- **D-04:** 文档来源：微信公众号导出的 HTML 文件

### 入库
- **D-05:** 上传方式：网页上传（与现有 UI 风格一致）
- **D-06:** 文件夹结构：用户可上传含嵌套子目录的整个文件夹；非 HTML 文件（CSS/JS/图片等）自动过滤
- **D-07:** 持续追加模式：用户会持续上传新文章，系统必须有去重机制
- **D-08:** 去重键：清洗后正文 SHA256（不依赖文件名）
- **D-09:** 重复处理：静默跳过 + 响应里说明"X 新增、Y 已存在"

### WeChat HTML 清洗
- **D-10:** 噪声剥离：`<script>`、`<noscript>`、`<style>`、关注卡片、推荐区、二维码全部剥掉
- **D-11:** 必须保留：`<pre>` / `<code>` 代码块、标题层级（`<h1>`~`<h6>`）、`<a href>` 链接
- **D-12:** `<img>` 处理：保留为标记（让 RAG 知道"这里有张图"），不下载/存图
- **D-13:** 编码处理：GBK/GB18030 编码的 HTML 必须正确解码

### 元数据
- **D-14:** 尽量从 WeChat HTML 的 `<script>` JS 变量（`var article_title = "..."`）里提取标题、作者、发布时间
- **D-15:** 元数据存入 ChromaDB metadata，便于后续过滤/统计

### Agent 行为
- **D-16:** 调整 Agent 系统 prompt 偏向"挖观点"任务
- **D-17:** Prompt 必须强制 LLM 在结论后附引用（具体文章标题）
- **D-18:** 保留原有 knowledge_search 工具的通用问答能力（不破坏现有功能）

### 范围
- **D-19:** 数据规模假设：最多 200 篇文章（中等量，嵌入成本可接受）
- **D-20:** 复用现有 RAG 基础设施：embeddings（shibing624/text2vec-base-chinese）、ChromaDB、knowledge_search tool

### Claude's Discretion
- 清洗器内部实现细节（用什么 HTML 解析库：BeautifulSoup4、lxml、还是正则）
- 去重表的具体存储方式（ChromaDB metadata filter vs. 独立 JSON/SQLite）
- 文件夹上传 API 的具体形式（multipart 多文件 vs. zip 上传 + 服务端解压）
- 前端 UI 调整的范围（最小改动 vs. 重新设计）
- 测试覆盖范围（关键路径单测 vs. 全面覆盖）

</decisions>

<specifics>
## Specific Ideas

- 用户表述：「到时候一个文件夹下面有多个文件夹，还会有css文件，需要过滤掉」——意思是 HTML 文件周围会有 CSS 等噪声文件，要过滤
- 「持续追加」——不是一次性导入，会反复往里加新文章
- 「挖观点」例：「我怎么看微前端」——期望跨 30 篇文章综合

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目结构与约定
- `./CLAUDE.md` — 项目总体说明（架构、命令、约定）
- `./.planning/notes/personal-wechat-knowledge-base.md` — 项目方向定位（why / who / what）
- `./.planning/REQUIREMENTS.md` — v1 需求清单（HTML / BATCH / DEDUP / AGENT 四类）
- `./.planning/todos/pending/wechat-html-cleaning-strategy.md` — HTML 清洗详细待办
- `./.planning/todos/pending/incremental-ingestion-dedup.md` — 去重机制详细待办

### 现有代码（必须复用）
- `src/rag/document_loader.py` — 当前 loader 注册表（`LOADER_MAP`），需扩展 `.html`
- `src/rag/pipeline.py` — 文档处理管线入口，需加去重钩子
- `src/rag/vectorstore.py` — ChromaDB 封装，metadata 操作
- `src/rag/embeddings.py` — 嵌入模型（shibing624/text2vec-base-chinese）
- `src/rag/splitter.py` — 文本分块
- `src/tools/knowledge.py` — Agent 的 knowledge_search 工具
- `src/agent/agent.py` — Agent 主类，系统 prompt 在这里
- `server.py` — FastAPI 入口（聊天 API + 知识库管理 API）

### 已有 plan 文档
- `docs/superpowers/plans/2026-05-28-rag-knowledge-base.md` — Phase 1 完成记录（12 个 task），可作为格式参考

</canonical_refs>

<existing_code>
## Existing Code Insights

### Reusable Assets
- `DocumentPipeline` (src/rag/pipeline.py): 已有 `ingest(file_path)` 流程，可扩展 `ingest_with_dedup(file_path)`
- `LOADER_MAP` (src/rag/document_loader.py): 注册表模式，扩展 `.html` 只需加一行 + 一个 cleaner
- ChromaDB metadata: 现有 store 已支持 metadata，可加 `{content_hash, source_path, ingested_at, title, author}`
- `Agent` (src/agent/agent.py): 系统 prompt 是 dataclass 字段，直接改 prompt 即可

### 注意点
- Windows 上 ChromaDB 需调用 `store.close()` 释放文件锁（CLAUDE.md 提到）
- 嵌入模型首次加载从 HF 缓存读取，约 400MB（CLAUDE.md 提到）
- 现有前端 `KnowledgePanel.tsx` 已有上传 UI 框架，文件夹上传可能需要前端配合（multi-file select 或 zip upload）

</existing_code>
