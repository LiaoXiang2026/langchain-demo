"""微信公众号 HTML 清洗器。

微信公众号导出的 HTML 包含大量噪声：<script> 内的 JS 变量、关注卡片、推荐区、
二维码、base64 内联图等。本模块把这些噪声剥掉，提取可被向量库索引的干净正文，
同时从 <script> JS 变量里尽量提取出文章元数据（标题/作者/发布时间）。
"""

from __future__ import annotations

import re

import chardet
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString


# 噪声标签黑名单（D-10）
_NOISE_TAGS = ("script", "noscript", "style", "iframe")

# 关注卡片 / 推荐区 / 二维码容器的 class 关键字（02-RESEARCH.md Pattern 1）
_CHROME_CLASS_PATTERNS = [
    re.compile(r"qr_code|profile_meta|follow_card"),
    re.compile(r"related|recommend|appmsg_card"),
]

# WeChat JS 变量 → 元数据字段名映射（D-14）
_JS_META_PATTERNS = {
    "title": re.compile(r'var\s+article_title\s*=\s*["\']([^"\']+)["\']'),
    "author": re.compile(r'var\s+nickname\s*=\s*["\']([^"\']+)["\']'),
    "publish_date": re.compile(r'var\s+create_time\s*=\s*["\']([^"\']+)["\']'),
}

# 归一化后的 GB 编码名集合：chardet 经常报 GB2312 或带连字符的 GB18030
_GB_ENCODING_VARIANTS = {"gb2312", "gbk", "gb18030"}


def _normalize_encoding(detected):
    """把 chardet 报出的 GB 系列编码统一归一化为 gb18030（GBK 超集，最安全）。

    Pitfall 1（02-RESEARCH.md）：chardet 对纯中文文本可能把 GBK 识别成 GB2312，
    直接 decode 会再次乱码。统一归到 GB18030 避免这个问题。
    """
    if not detected:
        return "utf-8"
    normalized = detected.lower().replace("-", "")
    if normalized in _GB_ENCODING_VARIANTS:
        return "gb18030"
    return detected


def _extract_js_meta(soup):
    """从 <script> 标签的 JS 变量里提取标题/作者/发布时间。

    必须在 decompose <script> 之前调用（D-14 + 02-RESEARCH.md Pitfall 顺序）。
    """
    meta = {}
    for script in soup.find_all("script"):
        code = script.string or ""
        if not code:
            continue
        for key, pattern in _JS_META_PATTERNS.items():
            if key in meta:
                continue
            match = pattern.search(code)
            if match:
                meta[key] = match.group(1)
    return meta


def _strip_noise(soup):
    """从 soup 里 decompose() 所有黑名单标签。"""
    for tag_name in _NOISE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()


def _locate_main(soup):
    """定位 WeChat 文章正文容器。

    优先级：div#js_content → 第一个 h1 的父 div → 整个 soup。
    """
    main = soup.find("div", id="js_content")
    if main is not None:
        return main
    h1 = soup.find("h1")
    if h1 is not None:
        parent = h1.find_parent("div")
        if parent is not None:
            return parent
    return soup


def _strip_chrome(main):
    """剥离关注卡片 / 推荐区 / 二维码容器。"""
    for pattern in _CHROME_CLASS_PATTERNS:
        for el in main.find_all(class_=pattern):
            el.decompose()


def _normalize_images(main):
    """把 <img> 处理成只剩 alt + [图片] 占位符。

    Pitfall 2：base64 src 字符串可能几十 MB，会撑爆 chunk。必须剥 src。
    D-12：保留为标记，让 RAG 知道"这里有张图"，但不下载/存图。

    实现：直接把 <img> 替换成 NavigableString 文本节点，确保 get_text() 能拿到占位符。
    占位符恒为 [图片]；alt 信息拼在前面一行，保留语义但不污染 chunk 长度。
    """
    for img in main.find_all("img"):
        alt = img.get("alt", "") or ""
        if alt:
            # 形如：流程图\n[图片]  —— alt 仍可见，主占位符固定
            img.replace_with(NavigableString(f"{alt}\n[图片]"))
        else:
            img.replace_with(NavigableString("[图片]"))


def clean_wechat_html(raw, source_path=""):
    """清洗微信公众号导出的 HTML，返回 (cleaned_text, metadata)。

    步骤（按此顺序不可换）：
    1. 编码检测 → 归一化到 utf-8 或 gb18030
    2. BS4 + lxml 解析
    3. 提取 JS 元数据（必须在剥 script 前）
    4. decompose 黑名单标签
    5. 定位主体
    6. 剥 chrome
    7. img 处理（剥 src，保 alt）
    8. get_text 序列化
    9. 附 source_path 到 meta

    Args:
        raw: HTML 文件的原始字节
        source_path: 源文件路径，可选；写入 meta["source_path"]

    Returns:
        (cleaned_text, meta_dict) — meta_dict 含 title/author/publish_date/source_path
    """
    # 1. 编码检测 + 归一化
    detected = chardet.detect(raw)
    encoding = _normalize_encoding(detected.get("encoding"))
    html_str = raw.decode(encoding, errors="replace")

    # 2. 解析
    soup = BeautifulSoup(html_str, "lxml")

    # 3. 元数据提取（必须在剥 script 前）
    meta = _extract_js_meta(soup)

    # 4. 剥黑名单
    _strip_noise(soup)

    # 5. 定位主体
    main = _locate_main(soup)

    # 6. 剥 chrome
    _strip_chrome(main)

    # 7. img 归一化
    _normalize_images(main)

    # 8. 文本化
    text = main.get_text(separator="\n", strip=True)

    # 9. 附加 source_path
    meta["source_path"] = source_path
    return text, meta
