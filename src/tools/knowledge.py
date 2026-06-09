"""知识库检索工具"""

from langchain_core.tools import tool
from src.rag import DocumentPipeline

# 全局管线实例（延迟初始化）
_pipeline: DocumentPipeline | None = None


def _get_pipeline() -> DocumentPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = DocumentPipeline()
    return _pipeline


@tool
def knowledge_search(query: str) -> str:
    """搜索本地知识库，查找与问题相关的文档内容。当用户询问可能在知识库中有答案的问题时使用此工具。"""
    try:
        pipeline = _get_pipeline()
        results = pipeline.search(query)
        if not results:
            return "知识库中没有找到相关信息。"
        parts = []
        for i, doc in enumerate(results, 1):
            source = doc.metadata.get("source", "未知来源")
            parts.append(f"[来源: {source}]\n{doc.page_content}")
        return "\n\n---\n\n".join(parts)
    except Exception as e:
        return f"知识库检索出错: {e}"
