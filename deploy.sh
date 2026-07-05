#!/bin/bash
set -e

echo "🧹 清理 Docker 构建缓存..."
docker builder prune -f

echo "🚀 开始构建并部署..."
docker compose up -d --build

echo "🧹 清理悬空镜像..."
docker image prune -f

echo "✅ 部署完成！"
