"""Agent 核心实现。"""

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import settings
from src.tools import get_weather, knowledge_search


SYSTEM_PROMPT = """你是一个拥有执行能力而不只是会聊天的 AI 实习生。
你可以使用以下工具：
- knowledge_search: 搜索本地知识库，查找已上传文档中的相关内容
- weather_query: 查询指定地点的当前天气，包括天气现象、气温、体感温度和风速

当用户的问题可能与知识库中的文档相关时，优先使用 knowledge_search 工具检索。
使用检索到的内容作为依据回答问题，并引用来源文件名。
如果知识库中没有相关信息，如实告知用户，然后再尝试用其他方式回答。

当用户询问某个城市或地区的实时天气时，优先使用 weather_query 工具获取最新天气信息，不要凭常识猜测。

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
        self.tools = [knowledge_search, get_weather]
        self.agent = create_agent(self.llm, self.tools)  # type: ignore[call-arg]
        self.history: list = []

    def _build_messages(self, message: str) -> list:
        """构建包含历史的消息列表。"""
        self.history.append(HumanMessage(content=message))
        return [SystemMessage(content=SYSTEM_PROMPT)] + self.history

    def chat(self, message: str) -> str:
        """多轮对话。"""
        messages = self._build_messages(message)
        response = self.agent.invoke({"messages": messages})
        self.history.append(response["messages"][-1])
        return response["messages"][-1].content

    async def chat_stream(self, message: str):
        """流式对话，逐 token 输出。"""
        from langchain_core.messages import AIMessage

        messages = self._build_messages(message)
        full_response = ""
        async for event in self.agent.astream_events({"messages": messages}, version="v2"):
            if event["event"] != "on_chat_model_stream":
                continue
            content = event["data"].get("chunk", None) and event["data"]["chunk"].content
            if not content:
                continue
            full_response += content
            yield content
        self.history.append(AIMessage(content=full_response))

    def clear_history(self):
        """清空对话历史。"""
        self.history.clear()


def build_agent() -> Agent:
    return Agent()
