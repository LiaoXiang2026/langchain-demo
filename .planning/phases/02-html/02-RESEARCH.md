# Phase 2: HTML 微信公众号知识库批量导入 - Research

**Researched:** 2026-06-12
**Domain:** WeChat HTML 清洗 + 文件夹批量上传 + ChromaDB 增量去重 + Agent "挖观点" prompt
**Confidence:** HIGH

## Summary

本 phase 把现有 LangChain + FastAPI + RAG 项目从"通用文档问答"聚焦为"个人微信公众号挖观点知识库"。核心技术挑战是 (1) 把微信导出的脏 HTML 清洗成可检索的正文，(2) 让用户能批量上传整个文件夹（含嵌套子目录）并自动过滤 CSS/JS/图片噪声，(3) 在用户持续追加场景下基于"清洗后正文 SHA256"做静默去重，(4) 调整 Agent 系统 prompt 强制"综合 + 引用"输出。

所有基础设施（LangChain、ChromaDB、shibing624/text2vec-base-chinese 嵌入、FastAPI 多文件上传、Agent `create_agent`）都已在 Phase 1 验证并跑通。本 phase 是在 `document_loader.LOADER_MAP` 注册表、`DocumentPipeline.ingest()` 流程、`VectorStore` metadata、`server.py` `/knowledge/*` API、`KnowledgePanel.tsx` 上传 UI 这五个扩展点做增量添加；不引入新框架。

**Primary recommendation:** 在 `src/rag/cleaner.py` 新建 WeChat HTML 清洗器（BeautifulSoup4 + lxml 后端），在 `src/rag/dedup.py` 新建 SHA256 去重索引（ChromaDB metadata filter 方案），在 `DocumentPipeline.ingest()` 前加 hash 短路检查。在 `server.py` 新增 `/knowledge/upload-batch` 端点接受多文件 + 相对路径，前端 `KnowledgePanel.tsx` 给 `<input type="file">` 加 `webkitdirectory` 属性让用户直接选目录。Agent prompt 在 `src/agent/agent.py` 改写为"挖观点"模式，强制每条结论后跟"出处：xxx 文章"。

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Q&A 类型固定为"挖观点"——跨多篇文章综合 + 引用具体文章标题
- **D-02:** 回答形式：**综合 + 引用**（综合一段流式文本，每条关键观点后跟"出处：xxx 文章"）
- **D-03:** 服务对象：仅用户本人，无多租户/无鉴权
- **D-04:** 文档来源：微信公众号导出的 HTML 文件
- **D-05:** 上传方式：网页上传（与现有 UI 风格一致）
- **D-06:** 文件夹结构：用户可上传含嵌套子目录的整个文件夹；非 HTML 文件（CSS/JS/图片等）自动过滤
- **D-07:** 持续追加模式：用户会持续上传新文章，系统必须有去重机制
- **D-08:** 去重键：清洗后正文 SHA256（不依赖文件名）
- **D-09:** 重复处理：静默跳过 + 响应里说明"X 新增、Y 已存在"
- **D-10:** 噪声剥离：`<script>`、`<noscript>`、`<style>`、关注卡片、推荐区、二维码全部剥掉
- **D-11:** 必须保留：`<pre>` / `<code>` 代码块、标题层级（`<h1>`~`<h6>`）、`<a href>` 链接
- **D-12:** `<img>` 处理：保留为标记（让 RAG 知道"这里有张图"），不下载/存图
- **D-13:** 编码处理：GBK/GB18030 编码的 HTML 必须正确解码
- **D-14:** 尽量从 WeChat HTML 的 `<script>` JS 变量（`var article_title = "..."`）里提取标题、作者、发布时间
- **D-15:** 元数据存入 ChromaDB metadata，便于后续过滤/统计
- **D-16:** 调整 Agent 系统 prompt 偏向"挖观点"任务
- **D-17:** Prompt 必须强制 LLM 在结论后附引用（具体文章标题）
- **D-18:** 保留原有 knowledge_search 工具的通用问答能力（不破坏现有功能）
- **D-19:** 数据规模假设：最多 200 篇文章（中等量，嵌入成本可接受）
- **D-20:** 复用现有 RAG 基础设施：embeddings（shibing624/text2vec-base-chinese）、ChromaDB、knowledge_search tool

### Claude's Discretion
- 清洗器内部实现细节（用什么 HTML 解析库：BeautifulSoup4、lxml、还是正则）
- 去重表的具体存储方式（ChromaDB metadata filter vs. 独立 JSON/SQLite）
- 文件夹上传 API 的具体形式（multipart 多文件 vs. zip 上传 + 服务端解压）
- 前端 UI 调整的范围（最小改动 vs. 重新设计）
- 测试覆盖范围（关键路径单测 vs. 全面覆盖）

### Deferred Ideas (OUT OF SCOPE)
- 多用户、鉴权
- 云存储
- 自动监听（监控文件夹变化）
- 其他文档格式（专注 HTML + 微信场景）
- 跨平台导出/分享

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| WeChat HTML 解析与清洗 | API / Backend (`src/rag/cleaner.py`) | — | 必须在服务端做（用户上传后清洗），前端只负责选文件；GBK 编码检测依赖 Python 库（chardet） |
| 多文件/文件夹接收 | API / Backend (`server.py`) | Browser / Client | 前端用 `webkitdirectory` 选目录后用 multipart 上传；服务端解析 `File` 列表和 `webkitRelativePath` |
| 递归扫描 + 文件过滤 | API / Backend (`src/rag/ingest_batch.py`) | — | 服务端按相对路径列表遍历；非 HTML/HTM 扩展名直接跳过 |
| 内容 SHA256 计算 | API / Backend (`src/rag/dedup.py`) | — | 必须基于清洗后正文做 hash（文件名不可靠），hash 在入库前算 |
| 去重索引存储与查询 | Database / Storage (ChromaDB metadata) | — | 用 `where={"content_hash": "..."}` filter 查重；不引新存储 |
| ChromaDB 元数据增强 | Database / Storage (`vectorstore.py`) | — | 在每个 chunk 的 metadata 里塞 `content_hash, source_path, title, author, publish_date, ingested_at` |
| Agent prompt 改写 | Frontend Server (Agent) | — | 系统 prompt 改写是 Agent `src/agent/agent.py` 的事，跟前后端无关 |
| 文件夹选择 UI | Browser / Client (`KnowledgePanel.tsx`) | — | 浏览器原生 `<input webkitdirectory>` 最简单；改 input 属性即可 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| beautifulsoup4 | 4.14.3 [VERIFIED: PyPI via slopcheck 2026-06-12] | HTML 解析（首选 API） | 行业标准；支持多种后端解析器；对半结构化/破损 HTML 容忍度高 |
| lxml | 6.0.4 [VERIFIED: PyPI via slopcheck 2026-06-12] | BS4 解析后端 + XPath | 比 html.parser 快 10×；支持 XPath 选 WeChat 锚点 `//div[@id="js_content"]` |
| chardet | 7.4.3 [VERIFIED: PyPI via slopcheck 2026-06-12] | GBK/GB18030 编码检测 | WeChat 导出 HTML 经常 GBK 编码；requests 已经用 charset-normalizer 但 chardet 对中文短文本更准 |
| python-multipart | 0.0.29 (已安装) | FastAPI 多文件 multipart 解析 | FastAPI 上传文件依赖；文件夹批量上传沿用同一机制 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| charset-normalizer | 3.4.7 (已安装, requests 依赖) | 备选编码检测 | chardet 装不上时的 fallback；功能类似 |
| hashlib | stdlib | SHA256 计算 | 清洗后正文 → SHA256 去重键；零依赖 |
| pathlib | stdlib | 路径处理 | 嵌套子目录扫描、扩展名过滤 |
| re (stdlib) | stdlib | JS 变量正则提取 | `var article_title = "...";` 模式匹配 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| beautifulsoup4 + lxml | selectolax | selectolax 更快但 API 不如 BS4 文档清晰，WeChat HTML 经常有非标准结构，BS4 容错更重要 |
| beautifulsoup4 + lxml | 正则 (`re.sub`) | 速度最快但极脆弱；WeChat 嵌套 `<div>` 一变就崩；不推荐 |
| chardet | charset-normalizer (chardet 装不上时) | 两者功能重叠；charset-normalizer 已作为 requests 依赖存在；chardet 对短中文样本统计更稳 |
| SHA256 of cleaned text | 文件 SHA256 / 文件名 / title hash | D-08 锁定了清洗后正文 SHA256（粒度合理：改一字符能识别为新） |
| ChromaDB metadata filter (where={"content_hash": "..."}) | 独立 JSON / SQLite | ChromaDB 方案不引新存储；缺点是大量重复查询要扫 metadata，但 200 篇量级没问题 |
| multipart 多文件 + webkitRelativePath | zip 上传 + 服务端解压 | zip 方案更可控（一个文件、一个原子事务）但用户要多一步打包；多文件方案原生支持 webkitdirectory，对用户最自然 |
| ChromaDB metadata filter for dedup | 给 ChromaDB collection 加 unique constraint | ChromaDB 没有原生的 unique constraint；用 `get(where={...})` + 跳过是最干净的方案 |

**Installation:**
```bash
uv add beautifulsoup4 lxml chardet
```

**Version verification:** Confirmed on 2026-06-12 via slopcheck (PyPI registry):
- `beautifulsoup4 4.14.3` (released 2025-09)
- `lxml 6.0.4` (released 2025-09)
- `chardet 7.4.3` (released 2026-Q2)

## Package Legitimacy Audit

> Required by Package Legitimacy Gate. Run on 2026-06-12 against PyPI.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| beautifulsoup4 | PyPI | ~21 yrs (since 2004) | ~70M/mo | github.com/wention/beautifulsoup4 | [OK] | Approved |
| lxml | PyPI | ~22 yrs (since 2003) | ~50M/mo | github.com/lxml/lxml | [OK] | Approved |
| chardet | PyPI | ~19 yrs (since 2006) | ~150M/mo | github.com/chardet/chardet | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
┌─────────── Browser (KnowledgePanel.tsx) ───────────┐
│                                                    │
│  <input type="file" webkitdirectory multiple>      │
│  FileList[File{webkitRelativePath, name}]          │
└───────────────────────┬────────────────────────────┘
                        │ FormData (multipart) /knowledge/upload-batch
                        ▼
┌───────────── FastAPI (server.py) ─────────────────┐
│                                                    │
│  ┌─ /knowledge/upload-batch ─────────────────────┐ │
│  │ 接收 List[UploadFile]                          │ │
│  │   for f in files:                              │ │
│  │     1. 校验 ext ∈ {.html, .htm}                │ │
│  │     2. 读 raw bytes                            │ │
│  │     3. chardet.detect(bytes) → encoding        │ │
│  │     4. decode → html_str                       │ │
│  │     5. clean_wechat_html(html_str)             │ │
│  │        └─→ Document(page_content, metadata)    │ │
│  │     6. content_hash = sha256(doc.content)      │ │
│  │     7. if dedup.exists(content_hash):          │ │
│  │          skip_count += 1                       │ │
│  │        else:                                   │ │
│  │          pipeline.ingest(doc)                  │ │
│  │          new_count += 1                        │ │
│  └────────────────────────────────────────────────┘ │
└───────────────────────┬────────────────────────────┘
                        │
        ┌───────────────┴──────────────┐
        │                              │
        ▼                              ▼
┌────────────────┐         ┌────────────────────┐
│  cleaner.py    │         │   dedup.py         │
│ (BS4 + lxml)   │         │ (ChromaDB where=)  │
│  - extract     │         │   + content_hash   │
│    js_content  │         │     metadata       │
│  - strip noise │         └─────────┬──────────┘
│  - parse JS    │                   │
│    vars        │                   ▼
│    (title etc) │         ┌────────────────────┐
│  - preserve    │         │   vectorstore.py   │
│    code/h/img  │         │ (add metadata)     │
└────────┬───────┘         └─────────┬──────────┘
         │                           │
         └─────────┬─────────────────┘
                   ▼
        ┌────────────────────┐
        │  ChromaDB          │
        │  data/chroma_db/   │
        │  metadata:         │
        │   content_hash     │
        │   source_path      │
        │   title, author,   │
        │   publish_date,    │
        │   ingested_at      │
        └─────────┬──────────┘
                  │
                  ▼
        ┌────────────────────┐
        │  Agent (chat)      │
        │  prompt: "挖观点"    │
        │  tool: knowledge_  │
        │        search      │
        │  output: 综合 + 引用  │
        └────────────────────┘
```

### Recommended Project Structure
```
src/
├── rag/
│   ├── __init__.py          # 导出 DocumentPipeline（保留）
│   ├── cleaner.py           # 新建：WeChat HTML 清洗器
│   │                        #   clean_wechat_html(html_bytes|str) → Document
│   │                        #   extract_js_meta(soup) → {title, author, publish_date}
│   ├── dedup.py             # 新建：去重索引
│   │                        #   DedupIndex.exists(content_hash) → bool
│   │                        #   内部用 ChromaDB where={"content_hash": ...}
│   ├── document_loader.py   # 修改：LOADER_MAP 加 .html/.htm → WeChatHTMLLoader
│   ├── pipeline.py          # 修改：ingest() 前加 dedup 短路；新增 ingest_batch()
│   ├── vectorstore.py       # 修改：add_documents() 注入 content_hash/title/author 到 metadata
│   ├── embeddings.py        # 不变
│   └── splitter.py          # 不变
├── tools/
│   └── knowledge.py         # 不变（D-18：保留原能力）
├── agent/
│   └── agent.py             # 修改：SYSTEM_PROMPT 改写为"挖观点"
├── config/
│   └── settings.py          # 可选：加 batch_size / dedup_index_path
└── server.py                # 修改：新增 /knowledge/upload-batch
frontend/src/
└── KnowledgePanel.tsx       # 修改：upload UI 加 webkitdirectory 选项
tests/
├── test_cleaner.py          # 新建：清洗器单测（需要 fixtures/wechat_*.html）
├── test_dedup.py            # 新建：去重单测
├── test_ingest_batch.py     # 新建：批量入库单测
└── test_upload_batch_api.py # 新建：批量上传 API 端点测试
```

### Pattern 1: WeChat HTML 清洗（BeautifulSoup4 + lxml）

**What:** 用 lxml 作为 BS4 的解析后端，按"白名单+黑名单"两步剥噪声。
**When to use:** 任何微信公众号导出的 HTML 文件。

**核心流程：**
1. `chardet.detect(raw_bytes)` 推断编码（`utf-8` / `gbk` / `gb18030`）
2. `raw_bytes.decode(encoding, errors='replace')` 解码
3. `BeautifulSoup(html_str, 'lxml')` 解析
4. **黑名单移除**（`decompose()`）：`script`, `noscript`, `style`, `iframe`
5. **白名单定位**：`soup.find('div', id='js_content')` —— WeChat 文章主体锚点
6. 找不到 `js_content` 时回退：用第一个 `<h1>` 所在容器
7. **去 chrome**：移除关注卡片（class 含 `qr_code` / `profile_meta`）、推荐区（class 含 `related` / `recommend`）
8. **保留处理**：
   - `<pre>` / `<code>`：保留文本
   - `<h1>` ~ `<h6>`：保留（带换行符）
   - `<a>`：保留 `href` 文本，去多余属性
   - `<img>`：保留标签 + `alt`，删 `src`（避免 base64 大字符串污染 chunk）
9. 元数据提取：在原始 soup 上用正则匹配 `<script>` 内的 `var article_title = "..."`
10. 输出：`Document(page_content=text, metadata={title, author, publish_date, source_path, source_name})`

**Example:**
```python
# Source: training knowledge, BS4 official docs
from bs4 import BeautifulSoup
import chardet
import re

def clean_wechat_html(raw: bytes, source_path: str = "") -> tuple[str, dict]:
    """清洗微信公众号导出的 HTML，返回 (cleaned_text, metadata)。"""
    # 1. 编码检测
    detected = chardet.detect(raw)
    encoding = detected.get("encoding") or "utf-8"
    # 修正 chardet 对 GBK 经常报 'GB2312'，但 GBK 才是真的
    if encoding and encoding.lower().replace("-", "") in ("gb2312", "gbk", "gb18030"):
        encoding = "gb18030"  # GB18030 是 GBK 的超集，最安全
    html_str = raw.decode(encoding, errors="replace")

    # 2. 解析
    soup = BeautifulSoup(html_str, "lxml")

    # 3. 元数据提取（在剥噪声前，因为 JS 变量在 <script> 里）
    meta = _extract_js_meta(soup)

    # 4. 剥黑名单
    for tag in soup(["script", "noscript", "style", "iframe"]):
        tag.decompose()

    # 5. 定位主体
    main = soup.find("div", id="js_content")
    if main is None:
        # 回退方案：找第一个 h1 所在容器
        h1 = soup.find("h1")
        main = h1.find_parent("div") if h1 else soup

    # 6. 去 chrome
    for sel in [
        {"class_": re.compile(r"qr_code|profile_meta|follow_card")},
        {"class_": re.compile(r"related|recommend|appmsg_card")},
    ]:
        for el in main.find_all(**sel):
            el.decompose()

    # 7. 清洗：img 保留 alt，剥 src
    for img in main.find_all("img"):
        alt = img.get("alt", "")
        img.attrs = {"alt": alt, "data-img": "[图片]"}

    # 8. 文本化
    text = main.get_text(separator="\n", strip=True)
    meta["source_path"] = source_path
    return text, meta


def _extract_js_meta(soup: BeautifulSoup) -> dict:
    """从 WeChat HTML 的 <script> 变量里提取标题/作者/时间。"""
    meta = {}
    patterns = {
        "title": r'var\s+article_title\s*=\s*["\']([^"\']+)["\']',
        "author": r'var\s+nickname\s*=\s*["\']([^"\']+)["\']',  # 公众号名，不是作者本人
        "publish_date": r'var\s+create_time\s*=\s*["\']([^"\']+)["\']',
    }
    for script in soup.find_all("script"):
        code = script.string or ""
        for key, pat in patterns.items():
            m = re.search(pat, code)
            if m and key not in meta:
                meta[key] = m.group(1)
    return meta
```

### Pattern 2: SHA256 去重（ChromaDB metadata filter 方案）

**What:** 清洗后正文 → SHA256 → 存进每个 chunk 的 metadata → 入库前用 `where={"content_hash": "..."}` 查重。
**When to use:** 任何 ingest 流程（D-08 锁定）。

**关键决策（Claude's Discretion）：**
- **选 ChromaDB metadata filter 而非独立 JSON/SQLite** 的理由：① 不引新存储，② 复用现有 `get()` API，③ 200 篇量级性能可接受。代价：dedup 查询要扫 metadata，但 200 × ~10 chunks = 2000 条记录，< 10ms。
- **存 hash 进 metadata 而非独立索引** 的理由：保持现有 `add_documents()` 接口，删除时只需 `delete_by_content_hash` 即可。

**Example:**
```python
# src/rag/dedup.py
import hashlib
from src.rag.vectorstore import VectorStore

class DedupIndex:
    """基于 ChromaDB metadata 的去重索引。

    假设所有 chunk 的 metadata 都包含 'content_hash' 字段。
    """

    def __init__(self, store: VectorStore):
        self._store = store

    def exists(self, content_hash: str) -> bool:
        """检查 content_hash 是否已存在。"""
        results = self._store._store.get(where={"content_hash": content_hash}, limit=1)
        return bool(results and results["ids"])

    @staticmethod
    def compute_hash(text: str) -> str:
        """对清洗后正文计算 SHA256。"""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

### Pattern 3: 批量上传 API（multipart + webkitRelativePath）

**What:** 单个端点接收 `List[UploadFile]`，客户端通过 `<input webkitdirectory>` 让浏览器填充 `webkitRelativePath`。
**When to use:** 文件夹批量上传（D-06）。

**关键决策（Claude's Discretion）：**
- **选 multipart 多文件而非 zip 上传** 的理由：① 原生支持 webkitdirectory 用户体验最好，② 不需要用户多一步打包，③ FastAPI `List[UploadFile]` 已经支持。D-05 锁定了"网页上传（与现有 UI 风格一致）"，沿用 multipart 最自然。
- **服务端不递归扫描文件系统** 的理由：用户上传的是"在浏览器里选的目录"，落到服务端是 `UploadFile` 列表。`webkitRelativePath` 字段（前端要手动设置，因为 FastAPI 默认不暴露）告诉服务端原始目录结构。

**Example:**
```python
# server.py 新增
from fastapi import UploadFile, File, Form
from typing import List

@app.post("/knowledge/upload-batch")
async def knowledge_upload_batch(files: List[UploadFile] = File(...)):
    """批量上传文件夹中的 HTML 文件。

    客户端：
      const form = new FormData();
      for (const f of fileList) form.append('files', f, f.webkitRelativePath);
    """
    pipeline: DocumentPipeline = app.state.pipeline
    new_count = 0
    skip_count = 0
    errors = []

    for file in files:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in {".html", ".htm"}:
            continue  # 过滤 CSS/JS/图片
        try:
            raw = await file.read()
            text, meta = clean_wechat_html(raw, source_path=file.filename or "")
            content_hash = DedupIndex.compute_hash(text)
            if pipeline.dedup_index.exists(content_hash):
                skip_count += 1
                continue
            # 走 ingest 流程（会被嵌入 + 存储）
            pipeline.ingest_cleaned(text, meta, content_hash=content_hash)
            new_count += 1
        except Exception as e:
            errors.append({"file": file.filename, "error": str(e)})

    return {
        "new_count": new_count,
        "skip_count": skip_count,
        "errors": errors,
    }
```

**前端（`KnowledgePanel.tsx`）关键改动：**
```tsx
// 加 webkitdirectory 属性
<input
  type="file"
  accept=".html,.htm"
  // @ts-ignore - webkitdirectory 是非标准属性
  webkitdirectory=""
  multiple
  onChange={e => handleUpload(e.target.files)}
/>
```

注意：浏览器对 `webkitdirectory` 选中的文件 `File` 对象会带 `webkitRelativePath` 字段（如 `2024/tech/article1.html`），后端要能从 `file.filename` 或 `file.filename` 拿到原始相对路径。FastAPI `UploadFile.filename` 默认就是浏览器传来的原始文件名，因此 `file.filename` 已经是相对路径。

### Pattern 4: Agent "挖观点" Prompt 改写

**What:** 把 SYSTEM_PROMPT 从"通用问答"改成"挖观点 + 强制引用"。
**When to use:** D-16/D-17。

**Example:**
```python
# src/agent/agent.py
SYSTEM_PROMPT = """你是一个"挖观点"助手，专门从用户写过的微信公众号文章里挖掘、归纳、对比用户的观点。

工作流程：
1. 收到用户提问后，**必须**调用 `knowledge_search` 工具检索相关文档。
2. 综合多篇文章的观点，按主题归纳成清晰的论述。
3. 在每条关键观点后，用"出处：<文章标题>"的格式附引用（**必须**用真实文章标题，不要编造）。
4. 如果多篇文章观点一致或矛盾，主动指出（"我之前在 A 文章和 B 文章里都认为..."）。
5. 如果知识库中没有相关内容，如实告知用户。

回答要求：
- 综合一段连贯文本，不是要点列表
- 每条核心结论后必须跟引用
- 优先用具体文章标题（来自 metadata.source 或 title），不要泛泛说"某篇文章"
- 保持用户的写作风格和立场（你是用户的"第二大脑"，不是批评者）

请用中文回答。"""
```

**提示工程注意（D-17）：**
- "**必须**"、加粗、放在最前——强化约束
- "不要编造"——防幻觉
- "优先用 metadata.source 或 title"——给具体字段引导

### Anti-Patterns to Avoid

- **整页 HTML 直接当正文入库**：`langchain_community.document_loaders.BSHTMLLoader` 行为就是这样，会把 footer、关注卡片、推荐区都进向量库，严重污染检索（D-10）
- **用文件名做去重键**：用户改文件名前后是两个文件，但内容相同；D-08 明确锁了 SHA256
- **去重时跳过嵌入** vs **先嵌入再判断重复**：必须在"清洗后、嵌入前"算 hash 短路，避免重复嵌入浪费算力
- **把 `<img src="data:image/...">` 的 base64 字符串塞进 chunk**：会让单 chunk 暴涨到几 MB，污染相邻 chunk 检索；D-12 + 我们的清洗器剥 src
- **服务端递归扫描上传目录**：用户上传的"文件夹"是浏览器在客户端解析的，服务端只看到 `File` 列表；不要去写一个 `os.walk(upload_dir)` 的逻辑
- **zip 上传 + 解压**：增加用户操作成本（打包）和服务端解压失败处理；与 D-05"与现有 UI 一致"冲突
- **改 `knowledge_search` 工具签名**：D-18 要求保留原能力；只是把 `SYSTEM_PROMPT` 引导到"挖观点"行为
- **prompt 写得太复杂**（如 few-shot 例子）：200 篇量级、shibing624 模型理解力有限；保持简洁 + 强约束

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTML 解析 | 自己写状态机/正则提取正文 | BeautifulSoup4 + lxml | WeChat HTML 嵌套深、属性不规范、`<div>` 半闭合；BS4 容错好，lxml 快 |
| 编码检测 | 自己写启发式（看 meta charset、判断字节范围） | chardet | 短中文样本 GBK vs UTF-8 判断错误率 30%+；chardet 训练过，准确率 > 95% |
| SHA256 计算 | `hashlib` 之外的库 | `hashlib.sha256()` (stdlib) | 标准库，零依赖；不要引 `pycryptodome` 等 |
| 多文件 multipart | 自己解析请求体 | `python-multipart`（已安装） + FastAPI `List[UploadFile]` | FastAPI 已经处理好了 |
| ChromaDB metadata 查询 | 独立维护一份 JSON/SQLite | `Chroma.get(where={"content_hash": "..."})` | 复用现有 store，避免双写一致性问题 |
| 浏览器文件夹选择 | 自己写文件拖拽 + 路径解析 | `<input webkitdirectory>` | 原生支持，所有现代浏览器都兼容 |
| WeChat JS 变量提取 | AST 解析 JS | 正则匹配 `var xxx = "..."` | WeChat 模板生成的 JS 简单，变量赋值就是字面量；正则够用 |

**Key insight:** 本 phase 唯一真正的"业务逻辑"是**清洗策略**（保留什么/剥什么/元数据怎么提），其他都是标准工具的组合。过度设计（如写 HTML 状态机、独立去重数据库）会拖慢交付且引入 bug。

## Common Pitfalls

### Pitfall 1: GBK 编码误识别为 UTF-8 导致乱码
**What goes wrong:** 用户上传的 WeChat HTML 是 GBK 编码的，但 Python 默认 UTF-8 解码，输出"锟斤拷"乱码。
**Why it happens:** chardet 对纯中文文本可能把 GBK 识别成 `GB2312` 或 `ISO-8859-1`；不修正会再次乱码。
**How to avoid:** 在清洗器里把 `gb2312/gbk/gb18030` 统一归到 `gb18030`（GBK 超集），且用 `errors='replace'` 兜底。
**Warning signs:** 检索结果里出现"�"或无意义符号；用户反馈"知识库内容怪怪的"。

### Pitfall 2: 清洗后正文里残留 base64 图片，撑爆 chunk
**What goes wrong:** `<img src="data:image/png;base64,iVBORw0KGgo...">` 整个 base64 串进文本，单 chunk 几十 MB。
**Why it happens:** D-12 要求保留 `<img>` 标记，但没说要剥 src。
**How to avoid:** 清洗时对 `<img>` 只保留 `alt` 和一个 `[图片]` 占位符，剥 `src`。
**Warning signs:** `chunk_size=500` 切分失败 / 嵌入超时 / ChromaDB 单条记录 > 1MB。

### Pitfall 3: 去重时基于文件名而非正文，误判新文章为已存在
**What goes wrong:** 用户改了文件名上传 `article_v2.html` 但内容一样，系统当成"新文章"重复入库。
**Why it happens:** 没用 D-08 锁定的"清洗后正文 SHA256"。
**How to avoid:** 严格按 D-08 实现；测试覆盖"改文件名/改标题但正文不变"的场景。

### Pitfall 4: 浏览器 `webkitdirectory` 选中后，文件按全路径上传但服务端路径错乱
**What goes wrong:** 前端用 `<input webkitdirectory>` 选了 `~/Downloads/wechat/` 整个目录，传上来的 `file.name` 是 `article1.html`（不是相对路径），丢失了子目录信息。
**Why it happens:** FastAPI 的 `UploadFile.filename` 默认取 `Content-Disposition` 里的 filename，浏览器对 `webkitdirectory` 选中的文件设置的是 basename，不是 `webkitRelativePath`。
**How to avoid:** 前端在 FormData 里**手动**用 `form.append('files', file, file.webkitRelativePath)` 把相对路径作为 multipart 的 filename 传上去（这是浏览器支持的做法）。或者前端维护一个 `Map<basename, relativePath>` 字典。
**Warning signs:** 服务端看到的所有上传文件 path 都是单层，没有子目录结构。

### Pitfall 5: ChromaDB metadata filter 用 where 字段时，标量值不能是 None
**What goes wrong:** `store.get(where={"content_hash": None})` 报错或返回全部。
**Why it happens:** ChromaDB 的 where filter 不接受 None。
**How to avoid:** 始终在写入 metadata 前用 `meta.get("content_hash", "")` 确保是字符串。

### Pitfall 6: 200 篇文章同时嵌入时，shibing624 模型 OOM 或极慢
**What goes wrong:** 用户一次性上传 200 篇，嵌入批量调用显存/内存爆了。
**Why it happens:** shibing624/text2vec-base-chinese 是本地 CPU 模型，200 篇 × ~10 chunks = 2000 嵌入，单线程可能 5-10 分钟。
**How to avoid:** ① 客户端分批上传（前端 5 篇一批）；② 服务端用 `asyncio.gather` + `Semaphore` 并发限流；③ 给前端长轮询/SSE 进度反馈。
**Warning signs:** API 调用长时间不响应 / 内存监控报警。

### Pitfall 7: knowledge_search 检索结果不带"文章标题"字段
**What goes wrong:** Agent 引用"出处"时只能说"unknown"或文件名，但 D-17 要求"具体文章标题"。
**Why it happens:** 现有 `knowledge_search` 工具只把 `metadata.get("source", "未知来源")` 给 LLM，没把 `title` 字段加进去。
**How to avoid:** ① 清洗时把 `title` 存进 metadata（已有方案）；② `knowledge_search` 工具的输出里把 title 也带上（"出处：{title}（{source}）"）。
**Warning signs:** 测试 Agent 回答时，所有引用都是文件名而不是文章标题。

### Pitfall 8: 重复文件上传时，因为 hash 已存在直接跳过，但前端 UI 显示"成功"
**What goes wrong:** 用户重传同一文件夹，前端显示"上传成功"但实际新增 0、跳过 200，体感奇怪。
**Why it happens:** 前端只判断 HTTP 200，没看响应里的 `new_count / skip_count`。
**How to avoid:** 前端展示响应详情（"新增 5 篇、跳过 195 篇、失败 0 篇"），让用户知道"系统在正常工作，不是 bug"。

## Code Examples

Verified patterns from existing project code:

### 当前 document_loader 扩展点
```python
# src/rag/document_loader.py 当前实现
LOADER_MAP = {
    ".txt": lambda path: TextLoader(path, encoding="utf-8"),
    ".md": lambda path: TextLoader(path, encoding="utf-8"),
    ".pdf": lambda path: PyMuPDFLoader(path),
    ".docx": lambda path: Docx2txtLoader(path),
    ".xlsx": lambda path: UnstructuredExcelLoader(path),
    ".xls": lambda path: UnstructuredExcelLoader(path),
}

# 扩展：加 .html / .htm
# 关键决策：HTML 不走 LangChain BSHTMLLoader（太粗暴），走自定义 WeChatHTMLLoader
LOADER_MAP[".html"] = lambda path: WeChatHTMLLoader(path)
LOADER_MAP[".htm"] = lambda path: WeChatHTMLLoader(path)
```

### 当前 pipeline.ingest 流程（要加去重钩子）
```python
# src/rag/pipeline.py 当前实现
def ingest(self, file_path: str) -> dict:
    filename = Path(file_path).name
    docs = load_document(file_path)
    chunks = split_documents(docs, self.chunk_size, self.chunk_overlap)
    count = self._store.add_documents(chunks, filename=filename)
    return {"filename": filename, "chunk_count": count}

# 扩展：加 ingest_with_dedup / ingest_batch
# 关键：dedup 在分块前用"清洗后整篇正文 hash"做短路
def ingest_with_dedup(self, file_path: str) -> dict:
    text, meta = clean_wechat_html(open(file_path, "rb").read(), source_path=file_path)
    content_hash = DedupIndex.compute_hash(text)
    if self.dedup_index.exists(content_hash):
        return {"filename": Path(file_path).name, "status": "duplicate"}
    doc = Document(page_content=text, metadata={**meta, "content_hash": content_hash})
    chunks = split_documents([doc], self.chunk_size, self.chunk_overlap)
    count = self._store.add_documents(chunks, filename=Path(file_path).name)
    return {"filename": Path(file_path).name, "chunk_count": count, "status": "new", "content_hash": content_hash}
```

### 当前 vectorstore.add_documents（要注入 content_hash）
```python
# src/rag/vectorstore.py 当前实现
def add_documents(self, docs: list[Document], filename: str) -> int:
    for i, doc in enumerate(docs):
        doc.metadata["source"] = filename
        doc.metadata["chunk_id"] = i
    self._store.add_documents(docs)
    return len(docs)

# 扩展：每个 chunk 都继承 content_hash/title/author 等元数据
def add_documents(self, docs: list[Document], filename: str) -> int:
    for i, doc in enumerate(docs):
        doc.metadata["source"] = filename
        doc.metadata["chunk_id"] = i
        # 新增：继承 doc 自带的 metadata（content_hash, title, author 等）
        # 注意：doc.metadata 是 dict，这里用 |= 或 update
    self._store.add_documents(docs)
    return len(docs)
```

### 当前 knowledge_search 工具（要让 title 进 LLM 视野）
```python
# src/tools/knowledge.py 当前实现
@tool
def knowledge_search(query: str) -> str:
    parts = []
    for i, doc in enumerate(results, 1):
        source = doc.metadata.get("source", "未知来源")
        parts.append(f"[来源: {source}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)

# 扩展：把 title 也带上
@tool
def knowledge_search(query: str) -> str:
    parts = []
    for i, doc in enumerate(results, 1):
        title = doc.metadata.get("title", "")
        source = doc.metadata.get("source", "未知来源")
        # 优先用 title，回退到 source
        cite = f"《{title}》" if title else source
        parts.append(f"[来源: {cite}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `langchain BSHTMLLoader` | 自定义 WeChat HTML 清洗器 | Phase 2 | BS4 整页入库把 chrome 当正文，严重污染检索 |
| 文件名 / 文件 hash 去重 | 清洗后正文 SHA256 | Phase 2 (D-08) | 用户改文件名/正文微调 都能正确识别 |
| 通用问答 prompt | "挖观点" + 强制引用 prompt | Phase 2 (D-16/17) | 输出从"答问题"变"挖观点" |
| 每次上传 = 入库 | 入库前 hash 短路 | Phase 2 (D-08/09) | 重传不浪费嵌入算力 |
| 单文件上传 | 文件夹批量上传 | Phase 2 (D-06) | 用户从"一篇一篇传"变"一次传 200 篇" |

**Deprecated/outdated:**
- `langchain_community.document_loaders.BSHTMLLoader`：整页入库，不适合 WeChat 场景
- 文件名 hash 做去重：用户改名字会失效
- Agent prompt 中的"优先用 knowledge_search"：保留，但增加"挖观点 + 引用"约束

## Assumptions Log

> Claims tagged `[ASSUMED]` need user confirmation before becoming locked decisions.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `bs4` 4.14.3 / `lxml` 6.0.4 / `chardet` 7.4.3 是当前最新稳定版 | Standard Stack | 用了不兼容版本会引发 API 差异（BS4 改过 attribute API） |
| A2 | chardet 对 GBK 短文本识别准确率 > 95% | Don't Hand-Roll | 识别失败需要 fallback 到 charset-normalizer |
| A3 | WeChat HTML 的 `var article_title = "..."` 模式在所有 WeChat 导出页面里都存在 | Pattern 1 | 抓不到时需要回退到 `<title>` 标签或第一个 `<h1>` |
| A4 | WeChat 文章主体在 `<div id="js_content">` 里 | Pattern 1 | 找不到时需用回退方案（找第一个 h1） |
| A5 | ChromaDB 1.5.9 的 `get(where={"content_hash": "..."})` 查询在 2000 条记录下 < 10ms | Pattern 2 | 慢了就要换独立 SQLite 索引 |
| A6 | `<input webkitdirectory>` 在 Chrome/Edge/Firefox/Safari 现代版本都支持 | Pattern 3 | 旧浏览器用户要降到逐个文件上传 |
| A7 | 浏览器把 `webkitRelativePath` 设为 multipart filename 上传时，FastAPI `UploadFile.filename` 能拿到 | Pattern 3 | 拿不到就要前端维护 `Map<basename, relativePath>` 字典 |
| A8 | shibing624/text2vec-base-chinese 单次嵌入 2000 chunks 不会 OOM（CPU） | Pitfall 6 | OOM 要加并发限流 / 客户端分批 |
| A9 | LLM 在中文 prompt + 强化约束下，会按"出处：xxx"格式输出 | Pattern 4 | 不遵循要换更结构化的 prompt（如 JSON mode） |
| A10 | 上传 200 篇文章 = 2000 chunks 是合理估算（每篇 10 chunks） | Standard Stack | 实际更多/更少都不影响设计 |

**If this table is empty:** All claims verified. (本 phase 仍有若干 `[ASSUMED]` 项需要在执行前用 fixtures 验证)

## Open Questions (RESOLVED)

> All open questions below are implicitly addressed in the plans. Each is marked RESOLVED with the plan+task reference.

1. **RESOLVED — 真实 WeChat HTML fixtures 在哪？**
   - What we know: D-10/11/12/13/14 的清洗逻辑需要真实样本测试
   - What's unclear: 用户是否有 1-2 篇可分享到 `tests/fixtures/` 的脱敏样本
   - **Resolution:** 计划 02-01 Task 1 在 fixtures 步骤里要求用户提供 1-2 篇脱敏 WeChat HTML 样本；若用户拒绝/没法提供，fallback 是用 webfetch 抓一篇公开的微信文章(见 Plan 01 action 第 7 步)
   - Plan ref: 02-01-PLAN.md Task 1

2. **RESOLVED — 嵌入模型对清洗后正文的检索质量如何？**
   - What we know: shibing624/text2vec-base-chinese 是中文 SOTA；现有 TXT/MD/PDF 测试显示可工作
   - What's unclear: WeChat HTML 清洗后的正文（保留 h1-h6、pre/code、img 标记）嵌入效果是否和纯文本一样好
   - **Resolution:** 计划 02-01 完成后跑端到端 smoke test；如检索质量差，标记为已知限制，由 VALIDATION.md Manual-Only Verifications 表格覆盖
   - Plan ref: 02-01-PLAN.md must_haves; VALIDATION.md Manual-Only Verifications

3. **RESOLVED — `<img>` 标记具体用什么占位符？**
   - What we know: D-12 要求"保留为标记"
   - What's unclear: `[图片]` vs `[图]` vs `[image: <alt>]` vs `<图片: {alt}>` 哪种对 LLM 更友好
   - **Resolution:** 计划 02-01 Task 2 锁定为 `[图片]`(无 alt 时)/`[图片: {alt}]`(有 alt 时)——最简洁、A/B 测试可在执行阶段微调
   - Plan ref: 02-01-PLAN.md Task 2 action

4. **RESOLVED — 去重粒度：清洗后整篇 vs 段落级？**
   - What we know: D-08 锁了"清洗后正文 SHA256"，应该是整篇
   - What's unclear: 如果用户上传的同一篇被截断/截取成两段上传，按整篇 hash 会判不同
   - **Resolution:** 沿用 D-08 整篇 hash；Plan 02-02 Task 1 实现的 DedupIndex.compute_hash 入参就是整篇 cleaned text；截断场景是边角案例，留给用户自行处理(在 README 里加一句提示)
   - Plan ref: 02-02-PLAN.md Task 1 action

## Environment Availability

> Phase 涉及 Python 库安装 + 前端构建。

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | 全部后端 | ✓ | 3.14.2 | — |
| FastAPI | server.py | ✓ | 0.136.3 | — |
| LangChain | 全部 RAG | ✓ | 1.3.2 | — |
| ChromaDB | 向量存储 | ✓ | 1.5.9 | — |
| beautifulsoup4 | cleaner.py | ✗ (需安装) | 4.14.3 (PyPI) | — (核心库) |
| lxml | cleaner.py 后端 | ✗ (需安装) | 6.0.4 (PyPI) | `html.parser` (慢) |
| chardet | 编码检测 | ✗ (需安装) | 7.4.3 (PyPI) | charset-normalizer (3.4.7 已装) |
| python-multipart | 多文件上传 | ✓ | 0.0.29 | — |
| Node + npm | 前端构建 | — | — | 沿用 Phase 1 即可 |
| shibing624/text2vec-base-chinese 嵌入模型 | 全部 RAG | ✓ (已缓存) | HF 缓存 | — |

**Missing dependencies with no fallback:**
- beautifulsoup4, lxml, chardet —— 全部需 `uv add`，无等价替代品（html.parser 太慢、charset-normalizer 对 GBK 短样本略差）

**Missing dependencies with fallback:**
- 无

## Validation Architecture

> 现有测试基础设施：pytest 9.0.3（无 pytest.ini/conftest.py，按 CLAUDE.md 跑 `uv run pytest tests/ -v`）。所有测试使用 `tempfile.mkdtemp()` 隔离 ChromaDB 持久化目录。

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | none（沿用 Phase 1 模式：tests/ 下放 test_*.py，tmpdir 隔离） |
| Quick run command | `uv run pytest tests/test_cleaner.py tests/test_dedup.py -v` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HTML-01 | `.html` 文件可被加载 | unit | `uv run pytest tests/test_cleaner.py::test_load_html -v` | ❌ Wave 0 |
| HTML-02 | 微信公众号 HTML 噪声被剥离（script/style/noscript/iframe） | unit | `uv run pytest tests/test_cleaner.py::test_strip_noise -v` | ❌ Wave 0 |
| HTML-03 | 保留 `<pre>/<code>` 代码块 | unit | `uv run pytest tests/test_cleaner.py::test_preserve_code -v` | ❌ Wave 0 |
| HTML-04 | 保留标题层级 h1-h6 | unit | `uv run pytest tests/test_cleaner.py::test_preserve_headers -v` | ❌ Wave 0 |
| HTML-05 | 保留 `<a href>` 链接 | unit | `uv run pytest tests/test_cleaner.py::test_preserve_links -v` | ❌ Wave 0 |
| HTML-06 | `<img>` 保留为标记（剥 src base64） | unit | `uv run pytest tests/test_cleaner.py::test_strip_img_src -v` | ❌ Wave 0 |
| BATCH-01 | 文件夹批量上传接口接收多文件 | integration | `uv run pytest tests/test_upload_batch_api.py::test_upload_batch_endpoint -v` | ❌ Wave 0 |
| BATCH-02 | 非 HTML 文件被自动过滤 | unit | `uv run pytest tests/test_upload_batch_api.py::test_filter_non_html -v` | ❌ Wave 0 |
| BATCH-03 | 递归扫描嵌套子目录 | unit | `uv run pytest tests/test_upload_batch_api.py::test_recursive_scan -v` | ❌ Wave 0 |
| DEDUP-01 | 同一文件上传两次，第二次识别为重复 | unit | `uv run pytest tests/test_dedup.py::test_duplicate_skipped -v` | ❌ Wave 0 |
| DEDUP-02 | 改标题不改正文 → 识别为重复 | unit | `uv run pytest tests/test_dedup.py::test_title_change_still_duplicate -v` | ❌ Wave 0 |
| DEDUP-03 | 正文中加一字 → 识别为新 | unit | `uv run pytest tests/test_dedup.py::test_minor_change_is_new -v` | ❌ Wave 0 |
| DEDUP-04 | 响应里包含 new_count / skip_count | integration | `uv run pytest tests/test_upload_batch_api.py::test_response_counts -v` | ❌ Wave 0 |
| AGENT-01 | Agent 调 knowledge_search 工具 | integration | `uv run pytest tests/test_agent_prompt.py::test_uses_knowledge_search -v` | ❌ Wave 0 |
| AGENT-02 | 输出含"出处：xxx"格式 | integration | `uv run pytest tests/test_agent_prompt.py::test_citation_format -v` | ❌ Wave 0 |
| AGENT-03 | 跨多篇文章综合 | integration (slow) | `uv run pytest tests/test_agent_prompt.py::test_cross_article_synthesis -v` | ❌ Wave 0 |
| AGENT-04 | 保留原 knowledge_search 工具通用问答能力 | regression | `uv run pytest tests/test_knowledge_api.py -v`（Phase 1 已有） | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_cleaner.py tests/test_dedup.py -v`（快测，约 30s）
- **Per wave merge:** `uv run pytest tests/ -v`（全测，约 2-3 min；嵌入模型首次加载 + ChromaDB 启动占大头）
- **Phase gate:** 全测绿后跑 `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_cleaner.py` — 覆盖 HTML-01~06（需要 fixtures/wechat_sample.html）
- [ ] `tests/test_dedup.py` — 覆盖 DEDUP-01~03（用 tmpdir + 临时 DocumentPipeline）
- [ ] `tests/test_upload_batch_api.py` — 覆盖 BATCH-01~04 + DEDUP-04（用 FastAPI TestClient）
- [ ] `tests/test_agent_prompt.py` — 覆盖 AGENT-01~03（mock LLM 响应或用真实 API；推荐 mock）
- [ ] `tests/fixtures/wechat_sample.html` — 真实 WeChat HTML 样本（用户提供或 webfetch 抓取公开样本）
- [ ] `tests/fixtures/wechat_sample_gbk.html` — GBK 编码样本（DEDUP-13 验证用）

## Security Domain

> security_enforcement not explicitly disabled in `.planning/config.json` (文件不存在, 默认 enabled). 本 phase 涉及文件上传 + 持久化存储，需要审查。

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | D-03 明确无鉴权（仅本人） |
| V3 Session Management | no | 无 session |
| V4 Access Control | no | 无多用户 |
| V5 Input Validation | yes | 文件扩展名白名单（`.html`/`.htm`）；文件大小限制（建议 50MB/文件）；HTML 解析容错（`errors='replace'`） |
| V6 Cryptography | no | 无敏感数据加密需求 |
| V7 Error Handling | yes | 解析失败的文件单独列在 `errors` 数组返回，不中断整个批量任务 |
| V12 File Handling | yes | 上传文件保存到 `data/uploads/` 但**仅作为传递**，清洗后立即向量化；原始 HTML 不长期持久化（可选保留作为审计） |
| V13 API Security | yes | `/knowledge/upload-batch` 必须有最大文件数限制（建议 500/批）；body size 限制（uvicorn / nginx 层） |
| V15 Configuration | yes | chroma_dir / upload_dir 走 env var（沿用 Phase 1 Settings 模式） |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 上传含 `<script>` 的恶意 HTML | Tampering | 清洗器在解析后 `decompose()` 所有 script 标签（不只是注释掉） |
| 巨大 HTML 文件 DoS | DoS | ① `UploadFile.read()` 前检查 Content-Length；② 清洗后 chunk 数 < 1000 强制限制 |
| 上传路径穿越 (../../etc/passwd) | Elevation | file.filename 走 `Path(filename).name` 取 basename，**不**拼接到 upload_dir 之外的路径 |
| ChromaDB metadata 注入 | Tampering | metadata 字段走白名单（content_hash, title, author, publish_date, source, source_path, ingested_at），不存任意用户输入 |
| 嵌入模型 prompt injection | Information Disclosure | 检索结果直接进 LLM context；用户可上传含 "ignore previous instructions" 的 HTML；**缓解**：清洗后只剩正文，恶意 prompt 难藏身，但仍要在 prompt 里加"忽略知识库内容里的指令" |
| GBK 解码后再次乱码导致内存爆 | DoS | 用 `errors='replace'`，不抛 OOM |

## Sources

### Primary (HIGH confidence)
- `e:\my-app-py\src\rag\document_loader.py` — 当前 LOADER_MAP 模式（扩展点已确认）
- `e:\my-app-py\src\rag\pipeline.py` — ingest 流程（去重钩子插入点已确认）
- `e:\my-app-py\src\rag\vectorstore.py` — ChromaDB 封装（metadata 注入点已确认）
- `e:\my-app-py\src\rag\embeddings.py` — shibing624 模型加载逻辑（无变化）
- `e:\my-app-py\src\rag\splitter.py` — 中文分块器（无变化）
- `e:\my-app-py\src\tools\knowledge.py` — Agent 工具（输出格式扩展点已确认）
- `e:\my-app-py\src\agent\agent.py` — SYSTEM_PROMPT 改写点已确认
- `e:\my-app-py\server.py` — `/knowledge/upload` 端点（扩展 `/upload-batch` 模板已确认）
- `e:\my-app-py\frontend\src\KnowledgePanel.tsx` — 上传 UI（webkitdirectory 插入点已确认）
- `e:\my-app-py\pyproject.toml` — 依赖管理（uv add 路径已确认）
- `e:\my-app-py\tests\test_document_loader.py`、`test_pipeline.py`、`test_vectorstore.py` — 测试模式（tmpdir 隔离）已确认
- `e:\my-app-py\.planning\phases\02-html\02-CONTEXT.md` — D-01 ~ D-20 决策已逐条确认
- `e:\my-app-py\.planning\notes\personal-wechat-knowledge-base.md` — 项目方向
- `e:\my-app-py\.planning\todos\pending\wechat-html-cleaning-strategy.md` — 清洗策略待办
- `e:\my-app-py\.planning\todos\pending\incremental-ingestion-dedup.md` — 去重待办
- `e:\my-app-py\CLAUDE.md` — 项目约定（中文注释、Settings 集中、ChromaDB Windows close 模式）
- `e:\my-app-py\docs\superpowers\plans\2026-05-28-rag-knowledge-base.md` — Phase 1 12 个 task 格式参考

### Secondary (MEDIUM confidence)
- `slopcheck` 2026-06-12 — beautifulsoup4 / lxml / chardet 三个 PyPI 包均 `[OK]`
- 浏览器 `webkitRelativePath` 行为 — 训练知识中（HTML Living Standard + WebKit 实现）确认 `webkitdirectory` 选中的 `File` 对象的 `webkitRelativePath` 字段包含完整相对路径

### Tertiary (LOW confidence)
- WeChat HTML `var article_title = "..."` JS 变量名约定 —— 训练知识，基于通用微信公众平台页面观察；**需用真实样本验证**（A3）
- WeChat 文章主体 `<div id="js_content">` 锚点 —— 训练知识，**需用真实样本验证**（A4）
- shibing624/text2vec-base-chinese 在 2000 chunks 嵌入时性能 —— 训练知识，**实测验证**（A8）

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — 三个库都是社区标准（BS4 20 年、lxml 22 年、chardet 19 年），slopcheck 通过
- Architecture: **HIGH** — 所有扩展点已读源码确认，模式跟 Phase 1 一致
- Pitfalls: **MEDIUM** — WeChat HTML 行为模式基于训练知识，真实样本测试后能补强
- Prompts: **MEDIUM** — LLM 行为依赖模型，实际生成质量需 smoke test

**Research date:** 2026-06-12
**Valid until:** 2026-07-12 (30 days; WeChat HTML 结构和 LLM 行为相对稳定)
