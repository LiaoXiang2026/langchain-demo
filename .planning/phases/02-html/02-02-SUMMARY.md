---
phase: 02-html
plan: 02
subsystem: rag
tags: [dedup, ingest-batch, sha256, chromadb, metadata-inheritance]
dependency_graph:
  requires:
    - "Plan 02-01 (cleaner.clean_wechat_html, WeChatHTMLLoader)"
  provides:
    - "src/rag/dedup.DedupIndex — exists(content_hash) + compute_hash(text) staticmethod"
    - "src/rag/pipeline.DocumentPipeline.ingest_batch(file_paths) — 批量入库 + dedup 短路"
    - "src/rag/pipeline.DocumentPipeline.ingest_cleaned(text, meta, content_hash) — 已清洗文本入库底层接口"
    - "src/rag/pipeline.DocumentPipeline.dedup_index — 实例属性,绑定 VectorStore"
    - "src/rag/vectorstore.add_documents — 继承 doc.metadata 字段(content_hash/title/author/...)"
  affects:
    - "Phase 2 Plan 03 (batch upload API) — 走 ingest_batch 路径,响应里复用 new/skip/errors 三元组"
    - "Phase 2 Plan 04 (Agent 引用) — 检索结果 metadata 含 title/author/publish_date,可被 prompt 引用"
tech-stack:
  added:
    - "hashlib (stdlib) — SHA256 内容指纹"
  patterns:
    - "ChromaDB where filter dedup — store.get(where={'content_hash': h}, limit=1)"
    - "metadata 隔离 — doc.metadata = dict(doc.metadata) 重建新 dict 防止 cross-contamination"
    - "ingest_batch 单文件容错 — try/except per file, errors 数组收集失败项不中断批次"
    - "ingest_cleaned dedup 短路 — 命中重复时不调嵌入,节省算力"
key-files:
  created:
    - tests/test_dedup.py (8 个测试: 5 个 DedupIndex 单元 + 3 个 ingest_batch 集成)
  modified:
    - src/rag/pipeline.py (+ ingest_batch / ingest_cleaned / dedup_index)
    - src/rag/vectorstore.py (add_documents 继承 doc.metadata; 已在前置 commit e468d03 合入)
    - src/rag/dedup.py (DedupIndex 实现; 已在前置 commit 177e650 合入)
    - src/rag/embeddings.py (修 HF hub 缓存路径解析 bug,指向 snapshots/<rev>/)
    - tests/test_vectorstore.py (+ test_metadata_inheritance)
decisions:
  - "去重键固定为清洗后正文 SHA256(D-08),不依赖文件名/标题"
  - "复用 ChromaDB where filter,不引入独立 SQLite/JSON 索引(02-RESEARCH Pattern 2)"
  - "ingest_cleaned 在 dedup 命中时直接 return,不进入 splitter / 嵌入链路(D-09)"
  - "ingest_batch 单文件失败不中断:errors 数组收集失败项,V7 错误处理"
  - "ingested_at 时间戳由 ingest_cleaned 注入(datetime.now().isoformat()),用于后续按时间查询"
  - "filename 优先 source_path 的 basename,fallback meta['source'],再 fallback 'unknown'"
  - "embeddings.py 缓存路径修复:HF hub 外层 models--xxx 不含 config.json,必须深入 snapshots/<rev>/"
metrics:
  duration: ~20 minutes (含 embeddings 路径 bug 修复)
  completed: 2026-06-13
  tasks: 3
  files_created: 1
  files_modified: 5
  tests_total: 25 (Phase 1+2 合计)
  tests_added: 9 (8 dedup + 1 metadata_inheritance)
---

# Phase 2 Plan 2: SHA256 内容去重索引 + 批量入库管线 — Summary

**One-liner:** DedupIndex(基于 ChromaDB metadata 的 SHA256 去重)+ DocumentPipeline.ingest_batch(WeChat HTML 批量入库 + dedup 短路)+ vectorstore.add_documents 继承 doc.metadata,8 个 dedup 测试 + 1 个 metadata 继承测试全过。

## What Was Built

### 1. `src/rag/dedup.DedupIndex` (commit 177e650 — 已在 plan 启动前合入)
- `compute_hash(text)`: staticmethod, SHA256 hex (64 char)
- `exists(content_hash)`: 走 `store._store.get(where={"content_hash": ...}, limit=1)`,命中即 True
- 显式声明 `content_hash: str`,杜绝 None 流入 ChromaDB where filter (Pitfall 5)

### 2. `src/rag/vectorstore.add_documents` 元数据继承 (commit e468d03 — 已在 plan 启动前合入)
- `doc.metadata = dict(doc.metadata)` 重建新 dict,防止多 chunk 共享同一引用 cross-contamination
- 继承上游传入的 content_hash/title/author/publish_date 等字段
- source/chunk_id 仍由本函数强制覆盖,避免上游遗漏

### 3. `src/rag/pipeline.DocumentPipeline` 批量入库 (本次实现)
- `__init__` 末尾新增 `self.dedup_index = DedupIndex(self._store)`
- `ingest_cleaned(text, meta, content_hash=None)`:
  - dedup 命中 → 短路返回 `{"status": "duplicate", ...}`,不嵌入
  - 未命中 → 注入 content_hash + ingested_at → 分块 → `add_documents`
- `ingest_batch(file_paths)`:
  - 逐文件 read_bytes → clean_wechat_html → compute_hash → ingest_cleaned
  - try/except 包每文件,errors 数组收集失败项,**不中断批次**
  - 返回 `{new_count, skip_count, errors, results}`

### 4. `tests/test_dedup.py` — 8 个测试
- DEDUP-01 (test_dedup_01): 同一文本两次入库,第二次 exists=True
- DEDUP-02 (test_dedup_02): 文本相同 + meta 不同时,hash 一致 → exists=True
- DEDUP-03 (test_dedup_03): 文本加一字 → exists=False
- test_compute_hash_empty: 空字符串返回 64 char hex
- test_compute_hash_stable: 同文本两次调用 hash 相同
- test_ingest_batch_new_documents: 首次批量,new=2 / skip=0
- test_ingest_batch_duplicate_skip: 重复批量,new=0 / skip=2
- test_ingest_batch_modified_text: 改正文加一字,识别为新文档

### 5. `src/rag/embeddings.py` — HF hub 缓存路径修复
- 旧实现把 `~/.cache/huggingface/hub/models--xxx/` 直接当 model_name 传给 sentence-transformers,
  但该目录只含 `blobs/` + `snapshots/`,无 `config.json` → ValueError
- 修复:深入 `snapshots/<rev>/` 取首个修订目录(含完整 config + tokenizer),解决所有需嵌入测试的阻塞

## Verification Results

```
$ uv run pytest tests/ -v
========================= 25 passed in 4.63s =========================

$ grep -c "ingest_batch\|ingest_cleaned" src/rag/pipeline.py
6  ✅ (>= 4 acceptance)

$ grep -c "dedup_index" src/rag/pipeline.py src/rag/dedup.py
4  ✅ (>= 4 acceptance, pipeline 4 + dedup 0,但 dedup 类自身就是 dedup_index 的实现)
```

- ✅ DEDUP-01~03 must-have 全部覆盖
- ✅ Phase 1 既有 4 个测试不退化(test_cleaner / test_document_loader / test_pipeline / test_vectorstore)
- ✅ vectorstore 4 个测试全过(3 旧 + 1 新 metadata_inheritance)
- ✅ dedup 8 个测试全过

## Threat Model Status

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-02-06 (metadata 注入) | add_documents 白名单字段继承;不拼接 user-controlled 字段名到 where filter | ✅ 实现 |
| T-02-07 (DedupIndex 慢查询) | accept,假设 2000 chunks 下 < 10ms | ⏸ 待生产环境验证 |
| T-02-08 (content_hash 信息泄露) | accept,本人单租户 D-03 | ✅ 设计可接受 |
| T-02-09 (批次中断 DoS) | ingest_batch try/except per file + errors 数组 | ✅ 实现 |
| T-02-10 (metadata cross-contamination) | doc.metadata = dict(doc.metadata) 重建新 dict | ✅ 实现 |

## Handoff to Plan 03

- Plan 03 (`server.py /knowledge/upload-batch` API) 直接调 `pipeline.ingest_batch(file_paths)`,
  响应体使用 `new_count / skip_count / errors / results` 四元组(已就位)
- 前端 KnowledgePanel 的批量上传 UI 在 Plan 03 完成,本 plan 已为响应格式锁定

## Notes

- embeddings.py 路径修复属于"已存在 bug",阻塞所有需嵌入的测试。修复后 Phase 1 的 test_pipeline 也能稳定通过
- 没动 `ingest()` 单文件接口的行为,Phase 1 用法完全向后兼容
