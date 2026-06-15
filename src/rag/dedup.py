"""基于 ChromaDB metadata 的内容去重索引。

D-08 锁定去重键为"清洗后正文 SHA256"——文件名不可靠,改标题/改文件名后
正文不变必须仍被识别为重复。

设计选择:不引入独立 JSON/SQLite 索引,直接复用 ChromaDB 的 where filter。
理由(02-RESEARCH.md Pattern 2):
  1. 不引新存储,与现有数据同源
  2. 200 篇 × ~10 chunks = 2000 条记录,< 10ms 可接受
  3. 与 vectorstore.add_documents 写入的 content_hash metadata 字段天然耦合

Pitfall 5:ChromaDB 的 where filter 不接受 None,必须始终传字符串。
本模块 exists() 显式声明 content_hash: str 参数,杜绝 None 流入。
"""

from __future__ import annotations

import hashlib

from src.rag.vectorstore import VectorStore


class DedupIndex:
    """基于 ChromaDB metadata 的去重索引。

    假设所有 chunk 的 metadata 都包含 'content_hash' 字段
    (由 vectorstore.add_documents 继承 doc.metadata 写入)。
    """

    def __init__(self, store: VectorStore):
        """初始化去重索引,绑定一个 VectorStore 实例。

        Args:
            store: 已初始化的 VectorStore(共享 Chroma 客户端)
        """
        self._store = store

    def exists(self, content_hash: str) -> bool:
        """检查 content_hash 是否已存在于向量库中。

        走 ChromaDB where filter 查 metadata.content_hash,limit=1 即可,
        命中表示至少有一个 chunk 的 content_hash 等于目标。

        Args:
            content_hash: 64 字符的 SHA256 hex 字符串(不可为 None)

        Returns:
            True 表示已存在(重复),False 表示未入库
        """
        # Pitfall 5:绝不能传 None,ChromaDB where filter 会异常
        # Cloud 模式下走 VectorStore.exists_by_metadata 公共接口(不再直接戳 _store)
        return self._store.exists_by_metadata(
            where={"content_hash": content_hash}, limit=1
        )

    @staticmethod
    def compute_hash(text: str) -> str:
        """对清洗后正文计算 SHA256 hex 摘要。

        选用 SHA256 而非 MD5 的理由:与 Python hashlib 教学一致,无安全风险;
        64 字符 hex 长度便于直接放进 ChromaDB metadata 字段。

        Args:
            text: 清洗后的字符串正文(utf-8 编码)

        Returns:
            64 字符的十六进制字符串
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
