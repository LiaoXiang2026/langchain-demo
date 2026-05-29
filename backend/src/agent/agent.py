"""Agent 核心实现"""

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_agent

from src.config import settings
from src.tools import calculator, search, knowledge_search


SYSTEM_PROMPT = """你是一个有用的 AI 助手。

你可以使用以下工具:
- calculator: 计算数学表达式
- search: 搜索互联网获取信息
- knowledge_search: 搜索本地知识库，查找已上传文档中的相关内容

当用户的问题可能与知识库中的文档相关时，优先使用 knowledge_search 工具检索。
使用检索到的内容作为依据回答问题，并引用来源文件名。
如果知识库中没有相关信息，如实告知用户，然后尝试用其他方式回答。

请用中文回答用户的问题。"""


class Agent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.model,
            base_url=settings.base_url,
            api_key=settings.api_key,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,  # type: ignore[call-arg]
        )
        self.tools = [calculator, search, knowledge_search]
        self.agent = create_agent(self.llm, self.tools)  # type: ignore[call-arg]

    def chat(self, message: str) -> str:
        """单轮对话"""
        response = self.agent.invoke({
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=message),
            ]
        })
        return response["messages"][-1].content

    async def chat_stream(self, message: str):
        """流式对话（逐 token 输出）"""
        async for event in self.agent.astream_events({
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=message),
            ]
        }, version="v2"):
            if event["event"] == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    yield content


def build_agent() -> Agent:
    return Agent()
