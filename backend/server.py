"""FastAPI 后端服务"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import time
import json
import shutil

from src.agent import Agent, build_agent
from src.rag import DocumentPipeline
from src.config import settings

DIST_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化 Agent 和管线，关闭时清理"""
    app.state.agent = build_agent()
    app.state.pipeline = DocumentPipeline()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="AI Agent API", lifespan=lifespan)

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


# ========== 知识库 API ==========

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".xlsx", ".xls"}


@app.post("/knowledge/upload")
async def knowledge_upload(file: UploadFile = File(...)):
    """上传文档到知识库"""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}。支持: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    upload_path = Path(settings.upload_dir) / (file.filename or "upload")
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    pipeline: DocumentPipeline = app.state.pipeline
    try:
        result = pipeline.ingest(str(upload_path))
        return result
    except Exception as e:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"文档处理失败: {e}")


@app.get("/knowledge/list")
async def knowledge_list():
    """列出已入库文档"""
    pipeline: DocumentPipeline = app.state.pipeline
    return pipeline.list_documents()


@app.delete("/knowledge/{filename}")
async def knowledge_delete(filename: str):
    """删除指定文档"""
    pipeline: DocumentPipeline = app.state.pipeline
    pipeline.delete(filename)

    upload_path = Path(settings.upload_dir) / filename
    upload_path.unlink(missing_ok=True)

    return {"deleted": filename}


class SearchRequest(BaseModel):
    query: str
    k: int = 4


@app.post("/knowledge/search")
async def knowledge_search_api(req: SearchRequest):
    """知识库检索（调试用）"""
    pipeline: DocumentPipeline = app.state.pipeline
    results = pipeline.search(req.query, k=req.k)
    return [
        {
            "content": doc.page_content,
            "source": doc.metadata.get("source", ""),
            "chunk_id": doc.metadata.get("chunk_id", 0),
        }
        for doc in results
    ]


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
