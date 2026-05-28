"""搜索工具（示例，需要接入真实搜索 API）"""

from langchain_core.tools import tool


@tool
def search(query: str) -> str:
    """搜索互联网获取信息。输入搜索关键词。"""
    # TODO: 接入真实搜索 API（如 Tavily、SerpAPI）
    return f"搜索结果: {query}（需要接入搜索 API）"
