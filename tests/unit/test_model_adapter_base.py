"""模型适配器抽象测试。"""
import pytest

from open_fox.core.adapters.base import (
    AssistantMessage,
    ModelAdapter,
    ToolCall,
)


def test_tool_call_dataclass():
    tc = ToolCall(id="1", name="read_file", args={"path": "x"})
    assert tc.id == "1"
    assert tc.name == "read_file"
    assert tc.args == {"path": "x"}


def test_assistant_message_dataclass():
    msg = AssistantMessage(content="hi", tool_calls=[])
    assert msg.content == "hi"
    assert msg.tool_calls == []


def test_model_adapter_is_abstract():
    with pytest.raises(TypeError):
        ModelAdapter()
