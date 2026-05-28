"""FastAPI 后端服务"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

from src.agent import Agent, build_agent

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化 Agent，关闭时清理"""
    app.state.agent = build_agent()
    yield


app = FastAPI(title="AI Agent API", lifespan=lifespan)

# 允许前端跨域（生产环境应限制 origins）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
def chat(req: ChatRequest):
    """单轮对话接口"""
    agent: Agent = app.state.agent
    response = agent.chat(req.message)
    return {"reply": response}


@app.get("/health")
def health():
    """健康检查"""
    return {"status": "ok"}


@app.get("/")
def index():
    """返回前端页面"""
    return FileResponse(FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
