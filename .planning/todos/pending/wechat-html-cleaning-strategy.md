---
title: 设计 WeChat 微信公众号 HTML 清洗策略
date: 2026-06-12
priority: high
context: /gsd:explore
---

# Todo: WeChat HTML 清洗策略

## 目标

为微信公众号导出的 HTML 写一个专用清洗器，把噪声（脚本、广告、推荐、装饰元素）剥掉，保留**文章主体内容**，让 RAG 检索看到的是真正的"作者观点"，而不是页面 chrome。

## 背景

- 现有 `src/rag/document_loader.py` 只支持 TXT/MD/PDF/Word/Excel，**没有 HTML loader**
- LangChain 自带 `BSHTMLLoader` 太粗暴，会把整页（包括 footer、相关推荐）当内容
- 微信公众号页面典型结构：
  - `<div id="js_content">` 包裹文章主体（关键锚点）
  - 大量 `<script>` 块（统计、分享）
  - 文末"喜欢此内容的人还喜欢"推荐区
  - 公众号关注卡片、二维码
  - `<style>` 内联样式

## 要解决的具体问题

1. **锚点定位**：如何稳定找到"文章主体"边界？仅靠 `id="js_content"` 够吗？要不要回退方案（找 `<h1>` 到文末之间的区域）？
2. **噪声剥离**：`<script>` / `<noscript>` / `<style>` / 关注卡片 / 推荐区 怎么移除？
3. **保留决策**：
   - `<img>` 图片——保留 `<img>` 标签（让 RAG 知道"这里有一张图"）还是直接剥掉？图片里可能有信息
   - `<code>` / `<pre>` 代码块——必须保留，技术文章的核心
   - 标题层级（`<h1>` ~ `<h6>`）——保留，作为分块边界参考
   - 链接（`<a href="...">`）——保留，可能指向相关文章引用
4. **元数据提取**：能从 HTML 里提取出**文章标题、发布时间、作者**吗？WeChat 页面通常有 `var article_title = "..."` 这种 JS 变量挂在 `<script>` 里。
5. **编码**：WeChat 导出 HTML 经常出现 GBK / GB18030 编码误识别为 UTF-8 导致的乱码，怎么处理？

## 验收标准

- [ ] 写一个 `cleaner.py`（或扩展 `document_loader.py`）的模块
- [ ] 输入：原始 WeChat HTML 路径
- [ ] 输出：LangChain `Document`，`page_content` 为清洗后正文，`metadata` 包含 `title` / `author` / `publish_date`（如果能提取）
- [ ] 提供 1-2 个真实 WeChat HTML 样本的单元测试，确认噪声被剥、主体被保
- [ ] 嵌入了 RAG 流程后，端到端检索质量肉眼可验证（"挖观点"答案有意义）

## 关键文件

- `src/rag/document_loader.py` — 当前 loader 注册表
- `src/rag/pipeline.py` — 当前管线（可能需要把 HTML 走专用清洗路径）
- `tests/` — 单元测试
- 需要真实样本：让用户从他自己微信文章里导 1-2 篇放到 `tests/fixtures/`

## 开放问题

- 是否需要同时支持"非微信"的普通 HTML（比如技术博客）作为扩展？先聚焦微信。
- 提取出来的元数据要不要进 ChromaDB 的 metadata 字段？这影响后续能不能按时间/作者过滤。
