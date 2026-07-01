# syntax=docker/dockerfile:1.7

# 后端镜像（不含前端静态资源，前端由独立项目托管）
# 基础镜像：python:3.10-slim（Debian Bookworm），匹配 pyproject.toml 的 requires-python=">=3.10"
# VPS 在国外，直接用官方 apt 源（比国内镜像更快）
FROM python:3.10-slim

# 系统依赖：
#   build-essential       — 编译 lxml / pymupdf 等 C 扩展
#   libxml2-dev libxslt1-dev — lxml 头文件
#   libgomp1              — PyTorch (sentence-transformers) 的 OpenMP 运行时
#   curl                  — healthcheck 用
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev libxslt1-dev \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 装 uv（替代 pip，速度快 10-100x，单二进制）
# 锁定版本 0.11.21 保证构建可复现，避免 latest 标签未来引入不兼容变更
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /usr/local/bin/uv

WORKDIR /app

# 先装 Python 依赖：pyproject.toml / uv.lock 不变则这层命中缓存，不重装
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 预下载嵌入模型到镜像内，避免运行时首次下载（~1.2GB，依赖 HuggingFace 网络）
# 模型缓存在 /root/.cache/huggingface/，启动时 SentenceTransformer 直接从本地加载
COPY src/config ./src/config
RUN uv run python -c \
    "from sentence_transformers import SentenceTransformer; \
     SentenceTransformer('Qwen/Qwen3-Embedding-0.6B', trust_remote_code=True)" \
    && rm -rf /root/.cache/huggingface/hub/.locks

# 拷源码（变化最频繁，放最后）
COPY src ./src
COPY server.py ./

# data/ 目录挂载点（chunks.json / embeddings.npy / documents.json / clusters.json / uploads/）
RUN mkdir -p data/uploads

EXPOSE 8000

# 单 worker：sentence-transformers 模型常驻内存，多 worker 会重复加载导致 OOM
# --proxy-headers：让 uvicorn 信任反代的 X-Forwarded-* 头
CMD ["uv", "run", "uvicorn", "server:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--proxy-headers"]
