# syntax=docker/dockerfile:1.7

# 后端镜像（不含前端静态资源，前端由独立项目托管）
# 基础镜像：python:3.10-slim（Debian Bookworm），匹配 pyproject.toml 的 requires-python=">=3.10"
# VPS 在国外，直接用官方 apt 源（比国内镜像更快）
FROM python:3.10-slim

# 系统依赖：
#   build-essential       — 编译 lxml / pymupdf 等 C 扩展
#   libxml2-dev libxslt1-dev — lxml 头文件
#   curl                  — healthcheck 用
#
# 注意：不再需要 libgomp1（sentence-transformers 及其 PyTorch 依赖已删除），
# 不再烘本地嵌入模型（Chroma Cloud 端托管 Qwen + Splade）。
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev libxslt1-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 装 uv（替代 pip，速度快 10-100x，单二进制）
# 锁定版本 0.11.21 保证构建可复现，避免 latest 标签未来引入不兼容变更
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /usr/local/bin/uv

WORKDIR /app

# 先装 Python 依赖：pyproject.toml / uv.lock 不变则这层命中缓存，不重装
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 拷源码（变化最频繁，放最后）
COPY src ./src
COPY server.py ./

# 给 volume 挂载点占好位（Cloud 模式下 chroma-data 不再需要，但保留兼容旧 docker-compose）
RUN mkdir -p data/uploads

EXPOSE 8000

# Cloud 模式下：
#   - 不再持有本地嵌入模型/向量索引,启动即连 Chroma Cloud
#   - 多 worker 现在安全了（共享状态在 Cloud），但保留单 worker 配置以便复用旧 compose
# --proxy-headers：让 uvicorn 信任反代的 X-Forwarded-* 头
CMD ["uv", "run", "uvicorn", "server:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--proxy-headers"]
