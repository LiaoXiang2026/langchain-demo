"""文档自动分类模块。

对已入库文档做 KMeans 嵌入聚类，LLM 起中文类目名，结果写入 clusters.json。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from src.config import settings

logger = logging.getLogger(__name__)


class DocumentClassifier:
    """文档聚类 + LLM 命名分类器。

    公开方法:
      recluster(k_range) → dict  全量重聚类，返回 clusters.json 内容
    """

    def __init__(
        self,
        store,
        llm,  # ChatOpenAI 或等价 callable: llm.invoke(prompt) → AIMessage
    ):
        self._store = store
        self._llm = llm
        self._clusters_path = Path(settings.data_dir) / "clusters.json"

    def recluster(self, k_range: tuple[int, int] | None = None) -> dict:
        """全量重聚类。

        Args:
            k_range: (min_k, max_k)，默认从 settings 取 (5, 10)

        Returns:
            clusters.json 内容

        Raises:
            ValueError: 文档数不足 5 篇时抛出
        """
        if k_range is None:
            k_range = (settings.recluster_k_min, settings.recluster_k_max)

        chunks = self._store.get_all_chunks()
        embeddings = self._store.get_all_embeddings()
        documents = self._store.get_documents()

        # ---- 1. 篇级聚合:同 doc_id 的 chunk 嵌入取均值 ----
        doc_embeddings: dict[str, list[np.ndarray]] = {}
        for i, chunk in enumerate(chunks):
            doc_id = chunk.get("doc_id", "")
            if doc_id and embeddings is not None:
                doc_embeddings.setdefault(doc_id, []).append(embeddings[i])

        if len(doc_embeddings) < 5:
            raise ValueError(f"文档数不足（{len(doc_embeddings)}），至少需要 5 篇才能聚类")

        doc_ids = list(doc_embeddings.keys())
        doc_vecs = np.array([
            np.mean(doc_embeddings[did], axis=0) for did in doc_ids
        ])  # (M, dim)

        # ---- 2. KMeans 扫描, 轮廓系数择最优 k ----
        min_k, max_k = k_range
        best_k = min_k
        best_score = -1.0
        best_labels: np.ndarray | None = None

        for k in range(min_k, min(max_k + 1, len(doc_ids))):
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = km.fit_predict(doc_vecs)
            if k == 1:
                best_labels = labels
                best_k = 1
                break
            score = silhouette_score(doc_vecs, labels)
            if score > best_score:
                best_score = score
                best_k = k
                best_labels = labels

        # ---- 3. 每簇抽代表文章(离中心最近的 top-3) ----
        centroids = KMeans(n_clusters=best_k, random_state=42, n_init=10).fit(doc_vecs).cluster_centers_

        cluster_samples: dict[int, list[dict]] = {}
        for cid in range(best_k):
            indices_in_cluster = np.where(best_labels == cid)[0]
            centroid = centroids[cid]
            distances = np.linalg.norm(doc_vecs[indices_in_cluster] - centroid, axis=1)
            nearest_idx = indices_in_cluster[np.argsort(distances)[:3]]

            samples = []
            for idx in nearest_idx:
                doc_id = doc_ids[idx]
                doc = documents.get(doc_id, {})
                samples.append({
                    "doc_id": doc_id,
                    "title": doc.get("title", doc_id),
                    "text": doc.get("text", "")[:500],
                })
            cluster_samples[cid] = samples

        # ---- 4. LLM 起中文类目名 ----
        cluster_names: dict[int, str] = {}
        for cid, samples in cluster_samples.items():
            cluster_names[cid] = self._name_cluster(samples, cid)

        # ---- 5. 构建结果并写入 ----
        result = {
            "updated_at": datetime.now().isoformat(),
            "total_docs": len(doc_ids),
            "k": best_k,
            "silhouette_score": round(float(best_score), 4),
            "clusters": [
                {
                    "id": cid,
                    "name": cluster_names[cid],
                    "size": int((best_labels == cid).sum()),
                    "sample_titles": [s["title"] for s in cluster_samples[cid]],
                }
                for cid in range(best_k)
            ],
            "docs": {
                doc_ids[i]: {
                    "cluster_id": int(best_labels[i]),
                    "cluster_name": cluster_names[int(best_labels[i])],
                }
                for i in range(len(doc_ids))
            },
        }

        self._clusters_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result

    def get_clusters(self) -> dict | None:
        """读取当前聚类结果。"""
        if not self._clusters_path.exists():
            return None
        return json.loads(self._clusters_path.read_text(encoding="utf-8"))

    def _name_cluster(self, samples: list[dict], cid: int) -> str:
        """让 LLM 为一个聚类起名。失败降级为 '类别 N'。"""
        prompt = (
            "你是一个中文内容分类专家。以下是一个主题聚类中的几篇代表性公众号文章，"
            "请读完后用 2-8 个中文字为这个主题起一个简洁、准确的类目名。"
            "只输出类目名（2-8 字），不要解释。\n\n"
            "代表性文章：\n"
        )
        for s in samples:
            prompt += f"- 标题：{s['title']}\n  摘要：{s['text'][:500]}\n"
        prompt += "\n类目名："

        try:
            response = self._llm.invoke(prompt)
            name = getattr(response, "content", str(response)).strip()
            name = name.strip("。，\"'""''\n ")
            if not name or len(name) > 20:
                return f"类别 {cid}"
            return name
        except Exception:
            logger.exception("LLM 起名失败, cluster_id=%d", cid)
            return f"类别 {cid}"
