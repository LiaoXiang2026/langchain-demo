"""网页抓取工具 —— 抓取指定 URL 的网页正文。"""

from __future__ import annotations

import re
import urllib.error
import urllib.request

from bs4 import BeautifulSoup
from langchain_core.tools import tool

# 请求头，避免被部分站点拒绝
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 需要剥离的噪声标签
STRIP_TAGS = ["script", "style", "nav", "footer", "header", "aside", "noscript"]


def _extract_text(html: str) -> str:
    """从 HTML 中提取正文文本。"""
    soup = BeautifulSoup(html, "lxml")

    # 剥离噪声标签
    for tag in soup(STRIP_TAGS):
        tag.decompose()

    # 优先从常见内容容器中提取
    for selector in ["article", "main", '[role="main"]', ".post-content", ".article-content", "#content"]:
        container = soup.select_one(selector)
        if container:
            soup = container
            break

    text = soup.get_text(separator="\n", strip=True)

    # 合并多余空行（保留段落间距）
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


@tool("web_fetch")
def fetch_webpage(url: str) -> str:
    """抓取指定网页的文本内容，适合回答需要对某个网页进行总结、提取信息或核实内容的问题。
    参数 url 为完整的网页地址（含 https://）。"""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read()
            # 从 Content-Type 头解析 charset（get_content_charset() 在 3.13 已移除）
            content_type = response.headers.get("Content-Type", "")
            match = re.search(r"charset=([^\s;]+)", content_type)
            if match:
                html = raw.decode(match.group(1), errors="replace")
            else:
                import chardet

                detected = chardet.detect(raw)
                encoding = detected.get("encoding") or "utf-8"
                html = raw.decode(encoding, errors="replace")

        text = _extract_text(html)

        if not text:
            return f"网页 {url} 未提取到正文内容，可能为纯前端渲染页面。"

        # 截断过长内容，避免撑爆 LLM 上下文
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n…（内容已截断，原文共 {len(text)} 字符）"

        return text

    except urllib.error.HTTPError as exc:
        return f"无法访问 {url}：HTTP {exc.code} {exc.reason}"
    except urllib.error.URLError as exc:
        return f"无法访问 {url}：{exc.reason}"
    except Exception as exc:  # noqa: BLE001
        return f"网页抓取失败（{url}）：{exc}"
