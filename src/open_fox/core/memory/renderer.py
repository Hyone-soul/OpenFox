from __future__ import annotations

from open_fox.core.memory.models import MemoryDocument
from open_fox.core.memory.template import (
    HEADER_DESC_LINES,
    SECTION_ARCHIVE,
    SECTION_ARCHIVE_DESC,
    SECTION_EXPLICIT,
    SECTION_EXPLICIT_DESC,
    SECTION_IMPLICIT,
    SUBSECTION_DESCS,
    SUBSECTIONS,
)


def _entry_line(e) -> str:
    if e.meta:
        return f"- {e.content}｜{e.meta}"
    return f"- {e.content}"


def render_memory_document(doc: MemoryDocument) -> str:
    """把 MemoryDocument 渲染回模板结构的 markdown。"""
    body: list[str] = []
    # 头部标题 + 固定说明行
    body.append("# OpenFox 全局记忆")
    body.extend(HEADER_DESC_LINES)
    # 显式区（标题 + 描述行 + 条目）
    body.append("")
    body.append(f"## {SECTION_EXPLICIT}")
    body.append(SECTION_EXPLICIT_DESC)
    for e in doc.explicit:
        body.append(_entry_line(e))
    # 隐式区（固定三个子板块，各含描述行 + 条目）
    body.append("")
    body.append(f"## {SECTION_IMPLICIT}")
    for sub in SUBSECTIONS:
        section = next((s for s in doc.implicit if s.name == sub), None)
        body.append(f"### {sub}")
        body.append(SUBSECTION_DESCS[sub])
        if section:
            for e in section.entries:
                body.append(_entry_line(e))
    # 归档区（标题 + 描述行 + 条目）
    body.append("")
    body.append(f"## {SECTION_ARCHIVE}")
    body.append(SECTION_ARCHIVE_DESC)
    for e in doc.archive:
        body.append(_entry_line(e))

    return "\n".join(body) + "\n"
