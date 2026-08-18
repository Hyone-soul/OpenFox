"""浏览器工具：web_search / web_fetch。

web_search：调用博查 AI 搜索 API 查询，返回高质量搜索结果。
web_fetch：抓取指定 URL 的网页内容。

博查 API 文档：https://open.bochaai.com/
需要在 .env 中配置 BOCHA_API_KEY。
"""

from __future__ import annotations

import os
import re
from html.parser import HTMLParser

import httpx

from open_fox.core.tools.base import BaseTool, ToolResult

_FETCH_TIMEOUT = 20
_MAX_CONTENT = 30000
_USER_AGENT = "OpenFox/1.0"

# 博查 API 配置
_BOCHA_API_URL = "https://api.bochaai.com/v1/web-search"


def _get_bocha_key() -> str:
    """运行时读取博查 API Key（避免模块导入时 .env 尚未加载的问题）。"""
    return os.environ.get("BOCHA_API_KEY", "")


class _HtmlStripper(HTMLParser):
    """简易 HTML→纯文本转换器。"""

    def __init__(self):
        super().__init__()
        self._pieces: list[str] = []

    def handle_data(self, data):
        self._pieces.append(data)

    def get_text(self) -> str:
        return " ".join(self._pieces)


def _html_to_text(html: str) -> str:
    s = _HtmlStripper()
    s.feed(html)
    text = s.get_text()
    # 合并多余空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _do_bocha_search(query: str, count: int, freshness: str = "") -> ToolResult:
    """调用博查 AI 搜索 API。"""
    api_key = _get_bocha_key()
    if not api_key:
        return ToolResult(
            success=False,
            error="博查 API Key 未配置。请在 .env 文件中添加 BOCHA_API_KEY=你的密钥",
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: dict = {
        "query": query,
        "count": count,
        "summary": True,  # 返回 AI 摘要
    }
    if freshness:
        payload["freshness"] = freshness

    try:
        resp = httpx.post(
            _BOCHA_API_URL,
            json=payload,
            headers=headers,
            timeout=_FETCH_TIMEOUT,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response else 0
        if status == 401 or status == 403:
            return ToolResult(success=False, error=f"博查 API 认证失败（{status}），请检查 BOCHA_API_KEY 是否正确")
        return ToolResult(success=False, error=f"博查搜索请求失败：HTTP {status}")
    except httpx.HTTPError as e:
        return ToolResult(success=False, error=f"博查搜索网络错误：{e}")

    try:
        data = resp.json()
    except Exception:
        return ToolResult(success=False, error="博查搜索返回数据解析失败")

    # 解析博查 API 响应
    # 响应结构：{ code, msg, data: { webPages: { value: [...] } } }
    inner = data.get("data", data)  # 兼容有无 data 包裹层
    web_pages = inner.get("webPages", {}).get("value", [])
    if not web_pages:
        return ToolResult(success=True, content="未找到搜索结果")

    results = []
    for i, item in enumerate(web_pages[:count]):
        title = item.get("name", "无标题")
        url = item.get("url", "")
        site_name = item.get("siteName", "")
        snippet = item.get("snippet", "")
        summary = item.get("summary", "")

        parts = [f"[{i + 1}] {title}"]
        if site_name:
            parts[0] += f"（{site_name}）"
        parts.append(f"    {url}")
        if summary:
            # 有 summary 时优先显示摘要（更完整）
            parts.append(f"    {summary}")
        elif snippet:
            parts.append(f"    {snippet}")

        results.append("\n".join(parts))

    return ToolResult(success=True, content="\n\n".join(results))


def _do_duckduckgo_search(query: str, count: int) -> ToolResult:
    """降级：使用 DuckDuckGo Lite HTML 抓取（无 API key 场景）。"""
    try:
        resp = httpx.get(
            "https://lite.duckduckgo.com/lite/",
            params={"q": query, "kl": "cn-zh"},
            headers={"User-Agent": _USER_AGENT},
            timeout=_FETCH_TIMEOUT,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        return ToolResult(success=False, error=f"搜索请求失败：{e}")

    html = resp.text
    results = []

    link_pattern = re.compile(
        r'<a[^>]+class="result-link"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    snippet_pattern = re.compile(
        r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>',
        re.DOTALL,
    )

    links = link_pattern.findall(html)
    snippets = snippet_pattern.findall(html)

    for i in range(min(len(links), count)):
        url = links[i][0]
        title = re.sub(r"<[^>]+>", "", links[i][1]).strip()
        snippet = ""
        if i < len(snippets):
            snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()
        results.append(f"[{i + 1}] {title}\n    {url}\n    {snippet}")

    if not results:
        all_links = re.findall(
            r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', html
        )
        seen = set()
        for url, title in all_links:
            url = url.replace("&amp;", "&")
            if url in seen or "duckduckgo" in url:
                continue
            seen.add(url)
            title = re.sub(r"<[^>]+>", "", title).strip() or url
            results.append(f"• {title}\n  {url}")
            if len(results) >= count:
                break

    if not results:
        return ToolResult(success=True, content="未找到搜索结果")
    return ToolResult(success=True, content="\n\n".join(results))


class WebSearchTool(BaseTool):
    """搜索引擎查询（优先博查 API，降级 DuckDuckGo）。"""

    name = "web_search"
    description = "通过搜索引擎查询关键词，返回摘要结果。用于获取最新信息或查找资料。支持中文自然语言查询。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词或自然语言问题"},
            "count": {"type": "integer", "description": "返回结果数，默认 5"},
            "freshness": {
                "type": "string",
                "description": "时间范围过滤（仅博查 API 生效）：oneDay / oneWeek / oneMonth / oneYear，留空不限",
            },
        },
        "required": ["query"],
    }

    def execute(self, **kwargs) -> ToolResult:
        query = kwargs["query"]
        count = min(kwargs.get("count", 5), 10)
        freshness = kwargs.get("freshness", "")

        # 优先使用博查 API
        if _get_bocha_key():
            return _do_bocha_search(query, count, freshness)

        # 降级到 DuckDuckGo（无 API key）
        return _do_duckduckgo_search(query, count)


class WebFetchTool(BaseTool):
    """抓取网页内容。"""

    name = "web_fetch"
    description = "抓取指定 URL 的网页内容，返回纯文本。用于阅读网页、API 文档等。"
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "要抓取的 URL"},
            "max_length": {"type": "integer", "description": "最大返回字符数，默认 30000"},
        },
        "required": ["url"],
    }

    def execute(self, **kwargs) -> ToolResult:
        url = kwargs["url"]
        max_length = kwargs.get("max_length", _MAX_CONTENT)

        if not url.startswith(("http://", "https://")):
            return ToolResult(success=False, error="URL 必须以 http:// 或 https:// 开头")

        try:
            resp = httpx.get(
                url,
                headers={"User-Agent": _USER_AGENT},
                timeout=_FETCH_TIMEOUT,
                follow_redirects=True,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            return ToolResult(success=False, error=f"请求失败：{e}")

        content_type = resp.headers.get("content-type", "")
        if "html" in content_type:
            text = _html_to_text(resp.text)
        else:
            text = resp.text

        if len(text) > max_length:
            text = text[:max_length] + "\n\n...（内容过长，已截断）"

        return ToolResult(
            success=True,
            content=text,
            metadata={"url": str(resp.url), "status": resp.status_code},
        )
