# -*- coding: utf-8 -*-
"""联网搜索脚本 —— 无需 API Key，多引擎备用。

引擎优先级：必应中国（cn.bing.com，国内直连）→ DuckDuckGo（备用）

用法：
    # 搜索
    python skills/web-search/scripts/search.py --query "人工智能最新进展" --num 5

    # 搜索（JSON 输出，供 Agent 程序化消费）
    python skills/web-search/scripts/search.py --query "AI" --num 5 --json

    # 抓取网页全文（提取正文）
    python skills/web-search/scripts/search.py --fetch "https://example.com/article"

    # 抓取网页全文（限制最大长度）
    python skills/web-search/scripts/search.py --fetch "https://example.com/article" --max-chars 3000

    # 指定引擎
    python skills/web-search/scripts/search.py --query "AI" --engine bing
    python skills/web-search/scripts/search.py --query "AI" --engine ddg

run_shell 的 cwd 是项目根目录，请用相对项目根的路径调用。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from html import unescape

import requests
from bs4 import BeautifulSoup

# 请求头（模拟浏览器）
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 请求超时（秒）
TIMEOUT = 15


# ──────────────────────────────────────── 必应搜索 ────────────────────────────────────────


def search_bing(query: str, num: int = 5) -> list[dict]:
    """通过必应中国搜索，返回结果列表。"""
    url = "https://cn.bing.com/search"
    params = {"q": query, "count": str(num * 2), "setlang": "zh-CN"}
    try:
        resp = requests.get(
            url, params=params, headers=HEADERS, timeout=TIMEOUT
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[Bing] 搜索请求失败: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    # 必应搜索结果的 class 结构
    for item in soup.select(".b_algo"):
        if len(results) >= num:
            break

        # 标题 + 链接（Bing 用 <strong> 高亮关键词，get_text(strip=True)
        # 会吃掉文本节点间的空格，所以用 get_text().strip() 保留内部空格）
        link_tag = item.select_one("h2 a")
        if not link_tag:
            continue
        title = link_tag.get_text().strip()
        raw_url = link_tag.get("href", "")

        # 摘要
        snippet_tag = item.select_one(".b_caption p, .b_algoSlug")
        snippet = snippet_tag.get_text().strip() if snippet_tag else ""

        if title and raw_url:
            results.append({"title": title, "url": raw_url, "snippet": snippet})

    return results[:num]


# ──────────────────────────────────────── DuckDuckGo 搜索 ────────────────────────────────────────


DDG_URL = "https://html.duckduckgo.com/html/"


def search_ddg(query: str, num: int = 5) -> list[dict]:
    """通过 DuckDuckGo HTML 接口搜索，返回结果列表。"""
    params = {"q": query, "b": ""}
    try:
        resp = requests.get(
            DDG_URL, params=params, headers=HEADERS, timeout=TIMEOUT
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[DuckDuckGo] 搜索请求失败: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    for item in soup.select(".result, .web-result"):
        if len(results) >= num:
            break

        link_tag = item.select_one(".result__a, .result__title a")
        if not link_tag:
            continue
        title = link_tag.get_text().strip()
        raw_url = link_tag.get("href", "")
        url = _extract_real_url(raw_url)

        snippet_tag = item.select_one(".result__snippet")
        snippet = snippet_tag.get_text().strip() if snippet_tag else ""

        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet})

    if not results:
        results = _regex_parse_ddg(resp.text, num)

    return results[:num]


def _extract_real_url(raw_url: str) -> str:
    """从 DuckDuckGo 跳转链接中提取真实 URL。"""
    if not raw_url:
        return ""
    if "uddg=" in raw_url:
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
        if "uddg" in parsed:
            return unescape(urllib.parse.unquote(parsed["uddg"][0]))
    if raw_url.startswith("http"):
        return raw_url
    if raw_url.startswith("//"):
        return "https:" + raw_url
    return raw_url


def _regex_parse_ddg(html: str, num: int) -> list[dict]:
    """正则兜底解析 DuckDuckGo HTML。"""
    results = []
    pattern = re.compile(
        r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
        r'class="result__snippet"[^>]*>(.*?)</span>',
        re.DOTALL,
    )
    for match in pattern.finditer(html):
        if len(results) >= num:
            break
        url = _extract_real_url(match.group(1))
        title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        snippet = re.sub(r"<[^>]+>", "", match.group(3)).strip()
        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet})
    return results


# ──────────────────────────────────────── 统一搜索入口 ────────────────────────────────────────


def search(query: str, num: int = 5, engine: str = "auto") -> list[dict]:
    """统一搜索入口。engine: auto（默认先 Bing 后 DDG）/ bing / ddg。"""
    if engine == "bing":
        return search_bing(query, num)
    elif engine == "ddg":
        return search_ddg(query, num)
    else:
        # auto: 先试 Bing，无结果再试 DDG
        results = search_bing(query, num)
        if results:
            return results
        print("[auto] Bing 无结果，尝试 DuckDuckGo...", file=sys.stderr)
        return search_ddg(query, num)


# ──────────────────────────────────────── 网页抓取 ────────────────────────────────────────


def fetch_page(url: str, max_chars: int = 5000) -> dict:
    """抓取网页并提取正文文本。"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.encoding = resp.apparent_encoding or "utf-8"
        resp.raise_for_status()
    except requests.RequestException as e:
        return {"url": url, "error": str(e), "title": "", "text": ""}

    soup = BeautifulSoup(resp.text, "html.parser")

    # 移除无关标签
    for tag in soup.find_all(
        ["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]
    ):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    # 提取正文：优先 article / main / .content
    body = soup.find("article") or soup.find("main") or soup.find(
        "div", class_=re.compile(r"content|article|post|entry", re.I)
    )
    if not body:
        body = soup

    text = body.get_text(separator="\n", strip=True)

    # 清理多余空行
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    text = "\n".join(lines)

    if len(text) > max_chars:
        text = text[:max_chars] + "\n...(内容已截断)"

    return {"url": url, "title": title, "text": text}


# ──────────────────────────────────────── 主入口 ────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="联网搜索 & 网页抓取工具")
    parser.add_argument("--query", "-q", help="搜索关键词")
    parser.add_argument("--num", "-n", type=int, default=5, help="返回结果数量（默认5）")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出搜索结果")
    parser.add_argument("--fetch", "-f", help="抓取指定 URL 的网页全文")
    parser.add_argument(
        "--max-chars", type=int, default=5000, help="抓取网页时的最大字符数（默认5000）"
    )
    parser.add_argument(
        "--engine", choices=["auto", "bing", "ddg"], default="auto",
        help="搜索引擎：auto（默认）/ bing / ddg",
    )
    args = parser.parse_args()

    # 模式 1：网页抓取
    if args.fetch:
        result = fetch_page(args.fetch, args.max_chars)
        if result.get("error"):
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # 模式 2：搜索
    if not args.query:
        parser.print_help()
        return 2

    results = search(args.query, args.num, args.engine)

    if not results:
        print("未找到搜索结果", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"搜索「{args.query}」—— 共 {len(results)} 条结果：\n")
        for i, r in enumerate(results, 1):
            print(f"## {i}. {r['title']}")
            print(f"   URL: {r['url']}")
            print(f"   摘要: {r['snippet']}")
            print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
