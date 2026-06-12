---
title: 实现增量入库去重机制
date: 2026-06-12
priority: high
context: /gsd:explore
---

# Todo: 增量入库去重机制

## 目标

用户在网页上传 HTML 时，**避免重复入库同一篇文章**。即使同一篇文章被多次上传、文件名改了、内容微调了，也要能识别出来。

## 背景

- 用户的使用模式是"持续追加"——写一篇新的就传一篇
- 200 篇的体量下，去重失误会导致向量库膨胀、检索噪声
- 当前 `src/rag/vectorstore.py` 和 `pipeline.py` 没有去重逻辑

## 要解决的具体问题

1. **去重键选什么？**
   - 文件名 → 不可靠，用户会改名字
   - 文件内容 hash (SHA256) → 改一个字就漏
   - 文章正文 hash（清洗后）→ 中等粒度
   - 文章标题 + 作者 → 业务键，但是清洗后才能拿
   - **建议方案**：清洗后的正文 SHA256 作为主键，标题作为辅助

2. **存储在哪？**
   - ChromaDB 本身没有"键索引"概念（只有向量 + metadata filter）
   - 可以利用 metadata：`{source_path, content_hash, ingested_at, title}`
   - 检索时先按 hash 查 metadata，命中则跳过
   - 或者独立维护一个 JSON / SQLite "入库登记表"

3. **重复时怎么办？**
   - 选项 A：静默跳过（最简单，但用户不知道）
   - 选项 B：返回"该文章已存在，是否覆盖？"让用户决定
   - 选项 C：自动覆盖（如果新版本 hash 不同）
   - **建议**：默认静默跳过 + 在响应里告诉用户"X 篇新增、Y 篇已存在"

4. **文件删除/更新场景？**
   - 如果用户改了文章再传，hash 变了——算新增还是更新？
   - 简单方案：算新增（旧的留在库里）。生产方案：先删旧的再加新的
   - 先用简单方案

## 验收标准

- [ ] `pipeline.py` 新增 `ingest_with_dedup(file_path)` 接口
- [ ] 同一篇文章上传两次，第二次的响应明确说"已存在"
- [ ] 改了标题、但正文一字未变的两个文件，能识别为重复
- [ ] 正文中加了一个字的两篇文章，被识别为不同的（粒度合理）
- [ ] 单元测试覆盖：新增 / 重复 / 内容微改 三种情况

## 关键文件

- `src/rag/pipeline.py` — 管线入口
- `src/rag/vectorstore.py` — ChromaDB 封装，metadata 操作
- `src/rag/embeddings.py` — 嵌入（去重后这一步才发生）
- 服务端 API：`server.py` 的 `/knowledge/upload`（或新增 `/knowledge/upload-batch`）

## 后续 phase 关联

本 todo 是 **HTML 知识库批量导入 phase** 的子任务。批量上传 phase 会引入"上传整个文件夹"的能力，本 todo 提供的去重能力是该 phase 的前置依赖。
