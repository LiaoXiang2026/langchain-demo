# Roadmap: 个人微信公众号挖观点知识库

## Overview

把现有 LangChain Agent + FastAPI + RAG 项目从通用文档问答演示聚焦为个人微信公众号文章知识库——上传微信文章 HTML,跨多篇文章挖观点,并附引用出处。

## Phases

- [x] **Phase 1: RAG 本地知识库基础能力** - TXT/MD/PDF/Word/Excel 文档加载、嵌入、检索、Agent 集成
- [ ] **Phase 2: HTML 微信公众号知识库批量导入** - WeChat HTML 清洗 + 文件夹批量上传 + 增量去重 + 挖观点 prompt

## Phase Details

### Phase 1: RAG 本地知识库基础能力
**Goal**: 提供通用文档问答能力,作为后续扩展的基础
**Depends on**: Nothing (first phase)
**Requirements**: [RAG-01, RAG-02, RAG-03, RAG-04, RAG-05]
**Success Criteria** (what must be TRUE):
  1. 用户可通过 Web 上传 TXT/MD/PDF/Word/Excel 文档
  2. 文档被分块、向量化、存入 ChromaDB
  3. Agent 可调用 knowledge_search 工具进行检索增强问答
  4. 前端聊天界面支持流式输出
  5. 嵌入模型 shibing624/text2vec-base-chinese 在本地加载并缓存

**Plans**: 12 plans (completed)

### Phase 2: HTML 微信公众号知识库批量导入
**Goal**: 支持批量导入微信公众号导出的 HTML 文件夹,清洗页面噪声,跨文章挖观点
**Depends on**: Phase 1
**Requirements**: [HTML-01, HTML-02, HTML-03, HTML-04, HTML-05, HTML-06, BATCH-01, BATCH-02, BATCH-03, DEDUP-01, DEDUP-02, DEDUP-03, DEDUP-04, AGENT-01, AGENT-02, AGENT-03, AGENT-04]
**Success Criteria** (what must be TRUE):
  1. 用户可通过 Web 上传整个文件夹
  2. 非 HTML 文件被自动过滤
  3. 微信公众号 HTML 噪声被剥
  4. 同一文章多次上传识别为重复
  5. Agent 跨多篇综合 + 出处
  6. 重传只处理新文件

**Plans**: 4 plans (planning complete)

Plans:
- [ ] 02-01: WeChat HTML 清洗器 + loader 扩展 (HTML-01~06)
- [ ] 02-02: DedupIndex + 批量入库管线 (DEDUP-01~03)
- [ ] 02-03: 文件夹批量上传 API + webkitdirectory (BATCH-01~03, DEDUP-04)
- [ ] 02-04: Agent 挖观点 prompt + title 输出 (AGENT-01~04)

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. RAG 基础能力 | 12/12 | Complete | 2026-05-29 |
| 2. HTML 微信知识库 | 0/4 | Planned | - |

**Execution Order:** Phase 2 next.
