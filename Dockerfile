# 多阶段构建
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install
COPY frontend/ ./
RUN pnpm build

FROM python:3.14-slim
WORKDIR /app

# 安装 Python 依赖
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

# 复制后端代码
COPY backend/ ./backend/

# 复制前端构建产物
COPY --from=frontend /app/frontend/dist ./frontend/dist

# 创建数据目录
RUN mkdir -p data/chroma_db data/uploads

# 暴露端口
EXPOSE 8000

# 启动服务
CMD ["uv", "run", "python", "backend/server.py"]
