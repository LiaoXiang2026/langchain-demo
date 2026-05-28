# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

基于 LangChain + LangGraph 的 AI Agent，使用小米 MIMO 模型（OpenAI 兼容接口），提供工具调用能力（计算器、搜索）。

## Tech Stack

- Python 3.14，使用 uv 管理依赖（pyproject.toml + uv.lock）
- LangChain / LangGraph：Agent 框架，`langchain.agents.create_agent` 实现 ReAct 模式
- 小米 MIMO API（OpenAI 兼容，base_url: `https://token-plan-cn.xiaomimimo.com/v1`）
- .env 管理密钥（`MIMO_API_KEY`）

## Commands

```bash
uv run backend/main.py    # 启动交互式 Agent（CLI）
uv run backend/server.py  # 启动 FastAPI 服务（Web）
uv sync                   # 安装/同步依赖
```

## Architecture

```
backend/
  main.py                 # CLI 入口：创建 Agent，启动 REPL 循环
  server.py               # FastAPI 服务：提供 /chat、/health、/ 接口
  src/
    config/settings.py    # Settings dataclass，从 .env 读取配置
    agent/agent.py        # Agent 类：封装 LLM + tools，提供 chat/chat_stream；build_agent() 工厂函数
    tools/
      calculator.py       # @tool 计算器（eval 表达式）
      search.py           # @tool 搜索（TODO：未接入真实 API）
frontend/
  index.html              # 聊天页面，调用 /chat 接口
```

- `Agent.chat()` 单轮对话，`Agent.chat_stream()` 流式输出
- 工具通过 `@tool` 装饰器定义，在 `agent.py` 中注册到 `tools` 列表
- 搜索工具是 stub，需接入真实 API（Tavily/SerpAPI）

## Conventions

- 中文注释和文档字符串
- `backend/src/` 下按功能分包（config、agent、tools），每个包有 `__init__.py` 导出公共接口
- 配置集中在 `Settings` dataclass，环境变量优先于默认值
