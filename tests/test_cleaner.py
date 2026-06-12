"""微信公众号 HTML 清洗器测试

覆盖 HTML-01~06 验收点 + 编码处理 + 元数据提取。
"""

from pathlib import Path

import pytest

from src.rag.cleaner import clean_wechat_html


FIXTURE_DIR = Path(__file__).parent / "fixtures"
UTF8_FIXTURE = FIXTURE_DIR / "wechat_sample.html"
GBK_FIXTURE = FIXTURE_DIR / "wechat_sample_gbk.html"


def _load_bytes(path):
    return path.read_bytes()


def test_clean_utf8_basic():
    """Test 1: UTF-8 编码 → 标题/正文保留 + 噪声剥除（HTML-01/02）"""
    text, meta = clean_wechat_html(_load_bytes(UTF8_FIXTURE), source_path=str(UTF8_FIXTURE))
    # 标题被保留
    assert "微前端架构思考" in text
    # pre/code 内代码被保留
    assert "registerMicroApp" in text
    # 噪声：var article_title JS 变量被剥
    assert "var article_title" not in text
    # 噪声：关注卡片/二维码容器文本被剥
    assert "qr_code" not in text
    # 噪声：base64 字符串被剥
    assert "base64," not in text


def test_clean_gbk_encoding():
    """Test 2: GBK 编码 → 不出乱码（HTML + Pitfall 1）"""
    text, _meta = clean_wechat_html(_load_bytes(GBK_FIXTURE), source_path=str(GBK_FIXTURE))
    # 不能出现 U+FFFD 替换字符
    assert "�" not in text
    # 不能出现经典乱码
    assert "锟斤拷" not in text
    # 中文标题应可读
    assert "微前端架构思考" in text


def test_metadata_extraction():
    """Test 3: meta 字典含 title/author/publish_date/source_path（D-14）"""
    _text, meta = clean_wechat_html(_load_bytes(UTF8_FIXTURE), source_path=str(UTF8_FIXTURE))
    assert meta.get("title") == "微前端架构思考"
    assert meta.get("author") == "技术沉思录"
    assert meta.get("publish_date") == "1701234567"
    assert meta.get("source_path") == str(UTF8_FIXTURE)


def test_preserve_code_block():
    """Test 4: <pre><code> 多行代码被完整保留（HTML-03）"""
    text, _meta = clean_wechat_html(_load_bytes(UTF8_FIXTURE))
    # 第一个代码块：microApp 配置
    assert "const microApp" in text
    assert "activeRule" in text
    # 第二个代码块：主应用加载
    assert "registerMicroApps" in text
    # 多行缩进被保留（get_text separator='\n' + strip=True 仍保留换行）
    assert "qiankun" in text


def test_preserve_links():
    """Test 5: <a href> 链接文本被保留（HTML-05）"""
    text, _meta = clean_wechat_html(_load_bytes(UTF8_FIXTURE))
    # 链接锚文本保留
    assert "qiankun" in text
    assert "Micro Frontends" in text
    assert "Martin Fowler" in text


def test_strip_img_src_keep_placeholder():
    """Test 6: <img src="data:..." base64 被剥，保留 [图片] 占位（HTML-06）"""
    text, _meta = clean_wechat_html(_load_bytes(UTF8_FIXTURE))
    # base64 src 串一定不在 text 里
    assert "base64," not in text
    # 占位符在
    assert "[图片]" in text


def test_strip_noise_tags():
    """Test 7: <script>/<noscript>/<style>/<iframe> 噪声标签被完全剥除（HTML-02）"""
    text, _meta = clean_wechat_html(_load_bytes(UTF8_FIXTURE))
    # script 内的 JS 变量不在正文
    assert "var js_title" not in text
    assert "console.log" not in text
    # style 内的 CSS 不在正文
    assert "font-family" not in text
    # noscript 提示文本不在正文
    assert "请启用 JavaScript" not in text
    # iframe src 链接不在正文
    assert "https://example.com/widget" not in text


def test_fallback_without_js_content_anchor():
    """Test 8: 找不到 <div id="js_content"> 时回退到 h1 所在容器，不崩"""
    # 构造一个没有 js_content 锚点的 HTML（用 str 构造后再 encode 避免 bytes literal 限制）
    html_str = """
    <html><head>
    <script>var article_title = "回退测试";</script>
    </head><body>
    <section>
        <h1>回退测试标题</h1>
        <p>这是 fallback 路径下的正文内容。</p>
    </section>
    </body></html>
    """
    text, meta = clean_wechat_html(html_str.encode("utf-8"), source_path="fallback.html")
    # 标题文本被保留
    assert "回退测试标题" in text
    assert "这是 fallback 路径下的正文内容" in text
    # meta 仍然提取到 title
    assert meta.get("title") == "回退测试"
    # source_path 被记录
    assert meta.get("source_path") == "fallback.html"


def test_cleaned_text_shorter_than_raw():
    """Test: 清洗后 text 长度严格小于原始 HTML 字节长度"""
    raw = _load_bytes(UTF8_FIXTURE)
    text, _meta = clean_wechat_html(raw)
    # text 字符数（不是字节数）应远小于 raw 字节数
    assert len(text) < len(raw)
    # text 不应包含原文中已剥离的 chrome 元素
    assert "qr_code" not in text
    assert "var article_title" not in text


def test_empty_html_does_not_crash():
    """Test: 空 / 极简 HTML 不崩（边缘情况）"""
    text, meta = clean_wechat_html(b"<html><body></body></html>", source_path="empty.html")
    assert isinstance(text, str)
    assert meta.get("source_path") == "empty.html"
