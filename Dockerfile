# syntax=docker/dockerfile:1.7

# 后端镜像（不含前端静态资源，前端由独立项目托管）
# 基础镜像：python:3.14-slim（Debian Bookworm）
FROM python:3.14-slim

# 切换 apt 源到阿里云镜像（避免官方源在国内极慢）
# Debian 12+ 用 /etc/apt/sources.list.d/debian.sources（新格式），兼容老格式 sources.list
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && (sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list || true)

# 系统依赖：
#   build-essential       — 编译 lxml / pymupdf 等 C 扩展
#   libxml2-dev libxslt1-dev — lxml 头文件
#   libgomp1              — PyTorch / sentence-transformers 的 OpenMP
#   curl                  — healthcheck 用
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev libxslt1-dev \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 装 uv（替代 pip，速度快 10-100x，单二进制）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# 先装 Python 依赖：pyproject.toml / uv.lock 不变则这层命中缓存，不重装
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 把嵌入模型烘进镜像，避免每次冷启动下载
# HF_ENDPOINT 用国内镜像（hf-mirror.com），避开 huggingface.co 在国内的连接问题
# 当前模型 BAAI/bge-small-zh-v1.5 (95MB)，与 src/config/settings.py 保持一致
ENV HF_ENDPOINT=https://hf-mirror.com
ENV HF_HOME=/root/.cache/huggingface
RUN uv run python -c \
        "from sentence_transformers import SentenceTransformer; \
         SentenceTransformer('BAAI/bge-small-zh-v1.5')"

# 拷源码（变化最频繁，放最后）
COPY src ./src
COPY server.py ./

# 给 volume 挂载点占好位
RUN mkdir -p data/chroma_db data/uploads

EXPOSE 8000

# 单 worker 是有意为之：
#   1) 嵌入模型 400MB × N workers = 内存爆炸
#   2) ChromaDB SQLite 后端不支持多进程并发写
# 横向扩展：在 compose/K8s 里开多个容器实例，每个挂独立数据卷
# --proxy-headers：让 uvicorn 信任反代的 X-Forwarded-* 头
CMD ["uv", "run", "uvicorn", "server:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--proxy-headers"]
