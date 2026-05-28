# My App Py

基于 LangChain + LangGraph 的 AI Agent，使用小米 MIMO 模型，提供工具调用能力。

## 快速开始

### 1. 安装依赖

```bash
# 后端
uv sync

# 前端
cd frontend && npm install
```

### 2. 配置环境变量

创建 `.env` 文件：

```
MIMO_API_KEY=你的API密钥
```

### 3. 启动

**开发模式（推荐）：**

```bash
# 终端 1：启动后端
uv run backend/server.py

# 终端 2：启动前端
cd frontend && npm run dev
```

访问 http://localhost:5173

**生产模式：**

```bash
cd frontend && npm run build
uv run backend/server.py
```

访问 http://localhost:8000

**CLI 模式（纯命令行）：**

```bash
uv run backend/main.py
```

## 项目结构

```
backend/
  main.py           # CLI 入口
  server.py         # FastAPI 服务
  src/
    agent/          # Agent 核心逻辑
    config/         # 配置管理
    tools/          # 工具（计算器、搜索）
frontend/
  src/
    App.tsx         # 聊天 UI 组件
    App.css         # 样式
  index.html        # SPA 入口
  vite.config.ts    # Vite 配置
```

## 技术栈

- 后端：Python 3.14 + LangChain + FastAPI
- 前端：React + TypeScript + Vite
- 小米 MIMO API（OpenAI 兼容）
