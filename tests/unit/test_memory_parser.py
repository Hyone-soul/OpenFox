from open_fox.core.memory.models import MemoryDocument
from open_fox.core.memory.parser import parse_memory_document
from open_fox.core.memory.renderer import render_memory_document
from open_fox.core.memory.template import TEMPLATE_MD


def test_parse_empty_template():
    doc = parse_memory_document(TEMPLATE_MD)
    assert isinstance(doc, MemoryDocument)
    assert doc.explicit == []
    assert len(doc.implicit) == 3
    assert doc.archive == []


def test_parse_and_render_roundtrip():
    md = TEMPLATE_MD.replace(
        "- 记忆内容：｜来源：会话描述｜优先级：最高",
        "- 我用 FastAPI 开发后端｜来源：用户对话｜优先级：最高",
    )
    doc = parse_memory_document(md)
    out = render_memory_document(doc)
    assert "我用 FastAPI 开发后端" in out
    assert "优先级：最高" in out
