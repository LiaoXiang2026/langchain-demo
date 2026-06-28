"""FastAPI 后端服务

提供以下功能：
- 聊天接口（流式输出，AI SDK 协议）
- 知识库管理（上传、列表、删除、检索）
- 前端静态资源托管
"""

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
from src.rag import DocumentPipeline, DocumentClassifier
from src.config import settings

# 前端构建产物目录
DIST_DIR = Path(__file__).parent / "frontend" / "dist"


# ========== 应用生命周期 ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化资源，关闭时清理"""
    # 启动时：创建 Agent 实例和文档处理管线
    app.state.agent = build_agent()
    app.state.pipeline = DocumentPipeline()
    app.state.classifier = DocumentClassifier(
        store=app.state.pipeline._store,
        llm=app.state.agent.llm,
    )
    # 确保上传目录存在
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    yield
    # 关闭时：可在此处添加清理逻辑


# 创建 FastAPI 应用实例，绑定生命周期
app = FastAPI(title="AI Agent API", lifespan=lifespan)

# CORS 中间件：允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# ========== 请求/响应模型 ==========

class VercelMessagePart(BaseModel):
    """AI SDK 消息部分（文本、图片等）"""
    type: str
    text: str | None = None


class VercelMessage(BaseModel):
    """AI SDK 消息格式（支持多轮对话）"""
    role: str
    parts: list[VercelMessagePart] = []


class VercelChatRequest(BaseModel):
    """AI SDK 聊天请求体"""
    messages: list[VercelMessage]


def _extract_latest_user_text(messages: list[VercelMessage]) -> str:
    """从消息列表中提取最后一条用户消息的文本内容

    Args:
        messages: AI SDK 格式的消息列表

    Returns:
        最后一条用户消息的文本

    Raises:
        HTTPException: 未找到用户消息时抛出 400 错误
    """
    for message in reversed(messages):
        if message.role != "user":
            continue
        # 提取所有文本类型的部分并拼接
        text_parts = [part.text for part in message.parts if part.type == "text" and part.text]
        text = "".join(text_parts).strip()
        if text:
            return text
    raise HTTPException(status_code=400, detail="No user message found")


# ========== 聊天接口 ==========

@app.post("/api/chat")
async def vercel_chat(req: VercelChatRequest):
    """AI SDK 流式对话接口（SSE 协议）

    使用 Vercel AI SDK 的 UI Message Stream Protocol：
    - text-start: 文本开始
    - text-delta: 文本增量（流式内容）
    - text-end: 文本结束
    - [DONE]: 流结束标记
    """
    agent: Agent = app.state.agent
    message = _extract_latest_user_text(req.messages)

    async def event_generator():
        # 生成唯一的文本 ID
        text_id = f"text-{int(time.time() * 1000)}"
        # 发送 text-start 事件，标记文本开始
        yield f"data: {json.dumps({'type': 'text-start', 'id': text_id})}\n\n"
        # 流式发送文本增量，逐 token 输出
        async for chunk in agent.chat_stream(message):
            yield f"data: {json.dumps({'type': 'text-delta', 'id': text_id, 'delta': chunk})}\n\n"
        # 发送 text-end 事件，标记文本结束
        yield f"data: {json.dumps({'type': 'text-end', 'id': text_id})}\n\n"
        # 发送 [DONE] 标记，通知前端流结束
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ========== 知识库 API ==========

# 允许上传的文件扩展名
ALLOWED_EXTENSIONS = {".md", ".pdf", ".html", ".htm"}


@app.post("/api/knowledge/upload")
async def knowledge_upload(file: UploadFile = File(...)):
    """上传文档到知识库

    流程：保存文件 → 加载 → 分块 → 嵌入 → 存入向量库
    """
    # 校验文件扩展名
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}。支持: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # 保存上传文件到本地
    upload_path = Path(settings.upload_dir) / (file.filename or "upload")
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 调用文档处理管线进行向量化
    pipeline: DocumentPipeline = app.state.pipeline
    try:
        result = pipeline.ingest(str(upload_path))
        return result
    except Exception as e:
        # 处理失败时删除已上传的文件
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"文档处理失败: {e}")


@app.get("/api/knowledge/list")
async def knowledge_list():
    """列出已入库的所有文档"""
    pipeline: DocumentPipeline = app.state.pipeline
    return pipeline.list_documents()


@app.delete("/api/knowledge/{filename}")
async def knowledge_delete(filename: str):
    """删除指定文档（同时删除向量库记录和本地文件）"""
    pipeline: DocumentPipeline = app.state.pipeline
    # 从向量库中删除
    pipeline.delete(filename)
    # 删除本地上传文件
    upload_path = Path(settings.upload_dir) / filename
    upload_path.unlink(missing_ok=True)

    return {"deleted": filename}


class SearchRequest(BaseModel):
    """知识库检索请求体"""
    query: str  # 检索查询文本
    k: int = 4  # 返回结果数量


@app.post("/api/knowledge/search")
async def knowledge_search_api(req: SearchRequest):
    """知识库检索接口（调试用）

    直接检索向量库，返回最相似的文档片段
    """
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


class ReclusterRequest(BaseModel):
    """重聚类请求体"""
    k: int | None = None  # 可选固定 k，不传则自动择优


@app.post("/api/knowledge/recluster")
async def knowledge_recluster(req: ReclusterRequest | None = None):
    """手动触发全量重聚类。

    返回聚类结果（clusters.json 内容）。
    文档数不足 5 篇时返回 400 错误。
    """
    classifier: DocumentClassifier = app.state.classifier
    try:
        k = req.k if req and req.k else None
        k_range = (k, k) if k else None
        return classifier.recluster(k_range=k_range)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"聚类失败: {e}")


@app.get("/api/knowledge/clusters")
async def knowledge_clusters():
    """获取当前聚类结果。

    尚未聚类时返回 404。
    """
    classifier: DocumentClassifier = app.state.classifier
    result = classifier.get_clusters()
    if result is None:
        raise HTTPException(status_code=404, detail="尚未聚类，请先 POST /api/knowledge/recluster")
    return result


# ========== 健康检查 ==========

@app.get("/api/health")
def health():
    """健康检查接口，用于监控服务状态"""
    return {"status": "ok"}


# ========== 前端静态资源托管 ==========

# 挂载前端构建产物（仅在 dist 目录存在时生效）
if DIST_DIR.exists():
    # 挂载静态资源目录（JS、CSS、图片等）
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA 兜底路由：非 API 路径返回 index.html

        这样前端路由（如 /chat、/knowledge）可以正常工作
        """
        file_path = DIST_DIR / full_path
        # 如果是真实文件（如 favicon.ico），直接返回
        if file_path.is_file():
            return FileResponse(file_path)
        # 否则返回 index.html，由前端路由处理
        return FileResponse(DIST_DIR / "index.html")


# ========== 启动入口 ==========

if __name__ == "__main__":
    import uvicorn
    # 启动开发服务器，监听所有网络接口，启用热重载
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
