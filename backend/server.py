"""FastAPI 后端服务"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import time
import json

from src.agent import Agent, build_agent

DIST_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化 Agent，关闭时清理"""
    app.state.agent = build_agent()
    yield


app = FastAPI(title="AI Agent API", lifespan=lifespan)

# 允许前端跨域（开发模式 Vite 代理需要）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request_time(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    ms = (time.time() - start) * 1000
    print(f"{request.method} {request.url.path} -> {response.status_code} ({ms:.0f}ms)")
    return response


class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
def chat(req: ChatRequest):
    """单轮对话接口"""
    agent: Agent = app.state.agent
    response = agent.chat(req.message)
    return {"reply": response}


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """流式对话接口（SSE）"""
    agent: Agent = app.state.agent

    async def event_generator():
        start = time.time()
        async for chunk in agent.chat_stream(req.message):
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        yield "data: [DONE]\n\n"
        ms = (time.time() - start) * 1000
        print(f"POST /chat/stream 完成 ({ms:.0f}ms)")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
def health():
    """健康检查"""
    return {"status": "ok"}


# 挂载前端静态资源
if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA 兜底：非 API 路径返回 index.html"""
        file_path = DIST_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(DIST_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
