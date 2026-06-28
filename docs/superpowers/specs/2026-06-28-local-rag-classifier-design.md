# 本地 RAG + 自动分类系统 设计规格

**日期**：2026-06-28
**范围**：将 Chroma Cloud 依赖替换为本地 numpy 存储、新增 LLM 自动聚类分类管线

---

## 1. 背景与目标

当前系统依赖 Chroma Cloud（托管嵌入 + 向量存储），运行在 Mac mini（或 32G Windows）本地。目标：

1. **完全离线**：去掉 Chroma Cloud 依赖（存储 + 嵌入），改用本地 numpy + Qwen3-Embedding-0.6B
2. **自动分类**：对 ~300 篇公众号文章做 LLM 自动聚类，产出 5-10 个大类，供前端展示/导航

---

## 2. 核心决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 存储 | numpy 矩阵 + JSON，无向量数据库 | 300 篇规模，numpy 秒算余弦相似度，零额外依赖 |
| 嵌入 | Qwen3-Embedding-0.6B（sentence-transformers 本地加载） | 与之前 Cloud 端模型一致，维度 1024 |
| 聚类算法 | KMeans（sklearn），chunk 嵌入均值做篇级向量 | 可复现、秒级完成 |
| K 择定 | 5-10 范围内轮廓系数自动择优 | 无需人工干预 |
| 类目命名 | LLM 读每簇代表文章起 2-8 字中文名 | 语义准确 |
| 重聚类策略 | 全量重聚类、手动触发 | 类目随语料演化，用户控制触发时机 |
| 分类产物 | `data/clusters.json`，全量覆盖 | 文件存储最简单，幂等 |
| 分类用途 | 前端导航/浏览，不影响 RAG 检索 | 检索走全库，不按类过滤 |

---

## 3. 数据模型

### 3.1 存储文件

```
data/
  documents.json    # 元数据 + 清洗后全文（JSON object, keyed by doc_id）
  chunks.json       # 分块文本 + 索引（JSON array），不含嵌入
  embeddings.npy    # (N_chunks × 1024) float32 矩阵，与 chunks.json 行对齐
  clusters.json     # 聚类结果（手动触发后生成）
```

### 3.2 documents.json

```json
{
  "2024-03-15 某公众号标题": {
    "title": "从0到1做产品的方法论",
    "author": "某公众号",
    "publish_date": "2024-03-15",
    "text": "清洗后的全文...",
    "content_hash": "sha256...",
    "source_path": "data/uploads/2024-03-15/index.html",
    "ingested_at": "2026-06-28T12:00:00",
    "chunk_count": 8
  }
}
```

### 3.3 chunks.json

```json
[
  {
    "doc_id": "2024-03-15 某公众号标题",
    "chunk_i": 0,
    "text": "第一段…",
    "metadata": {"source": "…", "content_hash": "…"}
  },
  ...
]
```

嵌入矩阵 `embeddings.npy` 按 `doc_id + chunk_i` 排序与 `chunks.json` 严格同序同长。检索时 `argsort` 得到行号后直接查 `chunks.json`。

### 3.4 clusters.json

```json
{
  "updated_at": "2026-06-28T20:30:00",
  "total_docs": 100,
  "k": 7,
  "silhouette_score": 0.68,
  "clusters": [
    {
      "id": 0,
      "name": "产品方法论",
      "size": 18,
      "sample_titles": ["从0到1做产品…", "用户访谈的十个误区…"]
    }
  ],
  "docs": {
    "2024-03-15 某公众号标题": {"cluster_id": 0, "cluster_name": "产品方法论"}
  }
}
```

---

## 4. 模块设计

### 4.1 VectorStore（`src/rag/vectorstore.py`）— 重写

从 Chroma Cloud 封装改为 numpy 本地存储，**接口签名不变**，`pipeline.py` 零改动。

核心变化：

| 方法 | 实现 |
|---|---|
| `__init__` | 加载 `chunks.json` + `embeddings.npy` 到内存 |
| `add_documents(docs, filename)` | 对每个 doc 文本做 Qwen 嵌入，新行追加到矩阵 + chunks，持久化写回文件 |
| `search(query, k)` | query → Qwen 嵌入 → `numpy.dot` 余弦 → argsort top-k → 按索引取 chunks |
| `delete_by_filename(filename)` | 匹配 `doc_id` 的行从 chunks/embeddings 中标记删除 + 压缩 |
| `list_documents()` | 读 `documents.json` 按 filename 聚合 |
| `exists_by_metadata(where, limit)` | 扫描 chunks.json 的 metadata 字段，O(n) 线性匹配（供 DedupIndex 用） |
| `close()` | no-op（无文件锁） |

**检索算法**（伪代码）：

```python
q_vec = embedding_model.encode(query)              # (1024,)
scores = numpy.dot(embeddings, q_vec)              # (N,)  归一化后等价余弦
scores /= numpy.linalg.norm(embeddings, axis=1) * numpy.linalg.norm(q_vec)
top_k = numpy.argsort(scores)[-k:][::-1]
return [Document(page_content=chunks[i]["text"], metadata=chunks[i]["metadata"]) for i in top_k]
```

**依赖**：`sentence-transformers`（Qwen3-Embedding-0.6B）、`numpy`

**嵌入缓存**：模型首次 `encode` 时自动下载并加载到内存，后续调用直接走缓存。`VectorStore` 实例化时预加载模型，避免首次查询冷启动。

### 4.2 Classifier（`src/rag/classifier.py`）— 新增

**公开接口**：

```python
class DocumentClassifier:
    def __init__(self, store: VectorStore):
        ...

    def recluster(self, k_range: tuple[int, int] = (5, 10)) -> dict:
        """全量重聚类，返回 clusters.json 内容"""
```

**`recluster()` 流程**：

1. 从 `store` 获取所有 chunk 的嵌入矩阵 + `doc_id` 映射
2. **篇级聚合**：同一 `doc_id` 的 chunk 嵌入取均值 → `(M篇 × 1024)` 矩阵
3. **KMeans 扫描**：`k=5..10` 逐个跑，记录轮廓系数，取最优 k
4. **中心文档**：每簇取欧氏距离最近的前 3 篇
5. **LLM 起名**：每簇拼 `标题 + 正文前 500 字` → prompt → 2-8 字类目名
6. **写入** `data/clusters.json`，全量覆盖

**LLM prompt 模板**：

```
你是一个中文内容分类专家。以下是一个主题聚类中的几篇代表性公众号文章，
请读完后用 2-8 个中文字为这个主题起一个简洁、准确的类目名。

代表性文章：
- 标题：{title1}
  摘要：{text1[:500]}
- 标题：{title2}
  摘要：{text2[:500]}
...

只输出类目名（2-8 字），不要解释。
```

**依赖**：`scikit-learn`（KMeans, silhouette_score）、`numpy`

### 4.3 Pipeline（`src/rag/pipeline.py`）— 微调

接口不变。`ingest()` / `ingest_cleaned()` / `ingest_batch()` 照旧调用 `store.add_documents()`。新增：

- `ingest` 流程中调用 `store.add_documents()` 后，同步更新 `documents.json`
- 构造函数去掉 `persist_dir` / `embedding_model` 旧参数（不再需要兼容 Cloud）

### 4.4 Settings（`src/config/settings.py`）

**删除**：`CHROMA_HOST`, `CHROMA_PORT`, `CHROMA_TENANT`, `CHROMA_DATABASE`, `CHROMA_API_KEY`, `CHROMA_COLLECTION`

**新增**：

```python
DATA_DIR: str = "data"               # 数据目录，可覆盖
MODEL_NAME: str = "Qwen/Qwen3-Embedding-0.6B"  # HuggingFace 模型标识
CHUNK_SIZE: int = 500
CHUNK_OVERLAP: int = 50
SEARCH_TOP_K: int = 4
RECLUSTER_K_RANGE: tuple = (5, 10)   # 聚类 k 扫描范围
```

**保留**：`DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `MODEL_NAME`（Agent LLM），`UPLOAD_DIR`

---

## 5. API 变更

### 新增端点

| 方法 | 路径 | 请求体 | 响应 |
|---|---|---|---|
| `POST` | `/api/knowledge/recluster` | 可选 `{"k": 7}`（固定 k，不传则自动择最优） | `clusters.json` 内容 |
| `GET` | `/api/knowledge/clusters` | — | 当前 `clusters.json` 内容（不存在则 404） |

### 现有端点行为不变

`/api/chat`、`/api/knowledge/upload`、`/api/knowledge/list`、`/api/knowledge/search`、`/api/health` 全部保留，底层自动使用 numpy 存储。

`recluster` 同步执行（KMeans 毫秒级 + LLM 起名 3-5 秒，总计 <10 秒）。

---

## 6. 依赖变更

```diff
  pyproject.toml
- chromadb
+ sentence-transformers>=2.7
+ scikit-learn
  langchain (保留)
  langchain-openai (保留)
  fastapi (保留)
```

---

## 7. 错误处理

| 场景 | 处理 |
|---|---|
| 文档数 < 5 时触发 recluster | 返回错误 `{"error": "文档数不足，至少需要 5 篇"}` |
| clusters.json 不存在时 GET /clusters | 返回 404 `{"error": "尚未聚类，请先 POST /api/knowledge/recluster"}` |
| 嵌入模型下载失败 | `VectorStore.__init__` 抛出 RuntimeError，引导检查 HuggingFace 连通性 |
| 单篇 recluster 中 LLM 起名失败 | 该簇降级使用 `"类别 {k}"` 作为类目名，不中断整体流程 |
| ingest 时磁盘写入失败 | 文件操作抛 IOError，server 返回 500 |

---

## 8. 测试

| 测试文件 | 覆盖范围 |
|---|---|
| `tests/test_vectorstore.py` | numpy 存储 CRUD、搜索正确性（手动构造小矩阵验证余弦排序） |
| `tests/test_classifier.py` | KMeans 聚类一致性、轮廓系数计算、prompt 模板生成、降级类目名 |

测试不依赖外部 API：向量用随机矩阵 mock，LLM 起名用 mock callable。

---

## 9. 不在范围内

- 大规模（>1000 篇）优化（近似检索 ANN、增量聚类）
- 前端实现（独立项目仓库，后端只提供聚类 API 契约）
- 类目编辑/修正（前端直接改 `clusters.json` 或后续迭代）
- 按类筛选检索（当前决策：分类仅导航用）
