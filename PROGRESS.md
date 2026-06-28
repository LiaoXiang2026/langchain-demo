# 本地 RAG + 自动分类系统 — 开发进度

**日期**：2026-06-28
**分支**：master

## 概述

将 Chroma Cloud 托管方案完全迁移到本地，新增 LLM 自动聚类分类能力。

## 架构变化

```
之前                              现在
─────────────────────────────     ─────────────────────────────
Chroma Cloud (托管嵌入+存储)      本地 numpy + JSON/NPY
Qwen3-Embedding (Cloud 端)        Qwen3-Embedding-0.6B (本地)
chromadb.CloudClient              sentence-transformers
Collection + where filter         numpy.dot 余弦相似度
无分类                             KMeans + LLM 起名
```

## 数据文件

```
data/
  chunks.json       ← 分块文本 + 元数据
  embeddings.npy    ← float32 矩阵 (N_chunks × 1024)
  documents.json    ← 每篇文档的元信息（标题/作者/正文/哈希/入库时间）
  clusters.json     ← 聚类结果（手动触发后生成）
```

## 新增/变更模块

| 文件 | 说明 |
|---|---|
| `src/rag/vectorstore.py` | **重写**。Chromadb → numpy 本地存储，线程安全 + 原子持久化 + 损坏容错 |
| `src/rag/classifier.py` | **新增**。KMeans 嵌入聚类 + LLM 起名，输出 clusters.json |
| `src/rag/pipeline.py` | **适配**。新 VectorStore 构造函数，ingest 同步写 documents.json |
| `src/config/settings.py` | **精简**。删 Chroma Cloud 配置，加本地存储/嵌入/聚类参数 |
| `server.py` | **扩展**。+2 个 API 端点 |
| `pyproject.toml` | 依赖替换 |
| `tests/test_vectorstore.py` | **新增**。6 个单元测试 |
| `tests/test_classifier.py` | **新增**。4 个单元测试 |

## 新增 API

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/knowledge/recluster` | 手动触发全量重聚类。可选 `{"k": 7}` 固定类目数 |
| `GET` | `/api/knowledge/clusters` | 获取当前聚类结果 |

## 聚类流程

```
上传 → cleaner → 分块 → Qwen 嵌入 → chunks.json + embeddings.npy
                                          │
  手动 POST /api/knowledge/recluster       │
          ↓                                │
  chunk 嵌入按 doc 聚合(均值)               │
          ↓                                │
  KMeans k=5..10 扫描，轮廓系数择最优 k      │
          ↓                                │
  每簇取中心最近 3 篇 → LLM 起 2-8 字中文类目名
          ↓
  data/clusters.json（全量覆盖）
```

## 测试结果

```
tests/test_vectorstore.py:
  test_add_and_search .................... PASSED
  test_search_empty_store ................ PASSED
  test_delete_by_filename ................ PASSED
  test_exists_by_metadata ................ PASSED
  test_persistence ....................... PASSED
  test_list_documents_aggregation ........ PASSED

tests/test_classifier.py:
  test_recluster_basic ................... PASSED
  test_recluster_too_few_docs ............ PASSED
  test_get_clusters_not_found ............ PASSED
  test_fallback_name_on_llm_error ........ PASSED

10/10 passed
```

## 环境变量

```bash
DEEPSEEK_API_KEY=sk-...        # LLM（Agent 对话 + 类目起名）
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
MODEL_NAME=deepseek-chat
DATA_DIR=data                  # 数据目录
UPLOAD_DIR=data/uploads        # 上传目录
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B  # HuggingFace 模型标识
```

## 首次运行

下载 Qwen3-Embedding-0.6B（~1.2GB，从 HuggingFace），首次 `add_documents` 或 `search` 时自动触发。之后常驻内存。

## 待办

- [ ] 首批 100 篇文章上传入库
- [ ] 首次聚类触发
- [ ] 前端对接 `/api/knowledge/clusters` 展示类目导航
- [ ] 后续文章增量添加（自动重聚类）

## 提交记录

```
daf10f9 docs: 更新文档，移除 Chroma Cloud 引用
f1544eb test(classifier): 添加 DocumentClassifier 单元测试(4 cases)
2038070 test(vectorstore): 添加本地 numpy 存储单元测试(6 cases)
7dbb976 feat(server): 新增 /api/knowledge/recluster 和 /api/knowledge/clusters 端点
209a2c1 feat(classifier): 实现 DocumentClassifier(KMeans 聚类 + LLM 起名)
00dcefb feat(classifier): 添加 DocumentClassifier 骨架和包导出
777fe08 refactor(pipeline): 适配新 VectorStore,ingest 时同步写入 documents.json
c54f122 fix(vectorstore): 线程安全 + 原子持久化 + 损坏容错
cf7a182 refactor(vectorstore): 从 Chroma Cloud 迁移到本地 numpy 存储
bc9ddd9 refactor(config): 移除 Chroma Cloud 配置，新增本地存储和嵌入模型配置
18f94f3 chore(deps): 替换 chromadb 为 sentence-transformers + scikit-learn + numpy
```
