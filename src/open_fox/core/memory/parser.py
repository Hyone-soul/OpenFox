from __future__ import annotations

from open_fox.core.memory.models import Entry, ImplicitSection, MemoryDocument
from open_fox.core.memory.template import (
    SECTION_ARCHIVE,
    SECTION_EXPLICIT,
    SECTION_IMPLICIT,
)

# 模板占位行的 content 标签（无真实记忆内容，应跳过）
_PLACEHOLDER_CONTENTS = {"记忆内容：", "废弃时间："}


def _parse_entries(lines: list[str]) -> list[Entry]:
    """解析 `- 内容｜meta` 形式的条目列表。"""
    entries: list[Entry] = []
    for line in lines:
        line = line.strip()
        if not line.startswith("- "):
            continue
        body = line[2:].strip()
        # content 与 meta 用 ｜ 分隔
        parts = body.split("｜")
        content = parts[0].strip()
        # 仅当 content 精确等于模板占位标签时才跳过，避免误删真实条目
        if content in _PLACEHOLDER_CONTENTS:
            continue
        meta = "｜".join(parts[1:]).strip() if len(parts) > 1 else ""
        # 置信度提取：从 meta 里找 "置信度：高/中/低"
        confidence = ""
        for token in ("高", "中", "低"):
            if f"置信度：{token}" in meta:
                confidence = token
                break
        entries.append(Entry(content=content, meta=meta, confidence=confidence))
    return entries


def parse_memory_document(md_text: str) -> MemoryDocument:
    """把 OPENFOX.md 文本解析为 MemoryDocument。"""
    lines = md_text.splitlines()
    explicit: list[Entry] = []
    implicit: list[ImplicitSection] = []
    archive: list[Entry] = []
    current_section = ""      # 二级标题
    current_sub = ""          # 三级标题（隐式子板块）
    pending: list[str] = []   # 收集当前块的行

    def flush():
        nonlocal pending
        if not pending:
            return
        if current_section == SECTION_EXPLICIT:
            explicit.extend(_parse_entries(pending))
        elif current_section == SECTION_ARCHIVE:
            archive.extend(_parse_entries(pending))
        elif current_section == SECTION_IMPLICIT and current_sub:
            implicit.append(ImplicitSection(name=current_sub, entries=_parse_entries(pending)))
        pending = []

    for line in lines:
        if line.startswith("## "):
            flush()
            current_section = line[3:].split("（")[0].strip()
            # 去掉标题前装饰性 emoji（如 📌/🧠/🗑️），再与板块名常量比对
            while current_section and not current_section[0].isalnum():
                current_section = current_section[1:].lstrip()
            current_sub = ""
        elif line.startswith("### "):
            flush()
            current_sub = line[4:].strip()
        else:
            pending.append(line)
    flush()

    return MemoryDocument(explicit=explicit, implicit=implicit, archive=archive)
