"""计算器工具"""

from langchain_core.tools import tool
from simpleeval import simple_eval


@tool
def calculator(expression: str) -> str:
    """计算数学表达式。输入如: 2 + 3 * 4"""
    try:
        result = simple_eval(expression)
        return str(result)
    except Exception as e:
        return f"计算错误: {e}"
