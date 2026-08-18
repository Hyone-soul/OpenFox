"""Agent 主循环端到端测试（mock LLM）。"""
import pytest

from open_fox.core.adapters.base import AssistantMessage, ToolCall
from open_fox.core.agent_loop import AgentLoop
from open_fox.core.registry import Registry
from open_fox.core.session import Session
from open_fox.core.tools.base import BaseTool, ToolResult


class FakeAdapter:
    """可编程的 mock adapter，按顺序返回预设消息。"""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0
        self.last_temperature = None

    async def chat(self, messages, tools=None, stream=False, temperature=None):
        self.calls += 1
        self.last_temperature = temperature
        if self._responses:
            return self._responses.pop(0)
        # 响应耗尽时返回默认消息（支撑 tool_trace 清空等多次 run 场景）
        return AssistantMessage(content="ok")


class GreetingTool(BaseTool):
    name = "greet"
    description = "say hi"
    parameters = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content=f"hi {kwargs['name']}")


@pytest.mark.asyncio
async def test_loop_single_turn_text():
    adapter = FakeAdapter([AssistantMessage(content="hello back")])
    registry = Registry()
    session = Session("t1")
    loop = AgentLoop(
        adapter=adapter,
        registry=registry,
        session=session,
        script_runner=None,
        skills={},
    )
    out = await loop.run("hi")
    assert out == "hello back"


@pytest.mark.asyncio
async def test_loop_with_tool_call():
    # 第一轮：模型要求调用 greet(name="bob")
    # 第二轮：模型返回纯文本
    adapter = FakeAdapter([
        AssistantMessage(content="", tool_calls=[
            ToolCall(id="c1", name="greet", args={"name": "bob"}),
        ]),
        AssistantMessage(content="done"),
    ])
    registry = Registry()
    registry.register_tool(GreetingTool())
    session = Session("t2")
    loop = AgentLoop(
        adapter=adapter, registry=registry, session=session,
        script_runner=None, skills={},
    )
    out = await loop.run("say hi to bob")
    assert out == "done"
    assert adapter.calls == 2
    # messages 中应能看到 tool 角色结果
    msgs = session.get_messages()
    assert any(m["role"] == "tool" for m in msgs)


@pytest.mark.asyncio
async def test_loop_max_steps_guard():
    # 让模型永远返回 tool_call，最终应被 max_steps 截断
    adapter = FakeAdapter([
        AssistantMessage(content="", tool_calls=[
            ToolCall(id=f"c{i}", name="greet", args={"name": str(i)})
        ]) for i in range(25)
    ])
    registry = Registry()
    registry.register_tool(GreetingTool())
    session = Session("t3")
    loop = AgentLoop(
        adapter=adapter, registry=registry, session=session,
        script_runner=None, skills={}, max_steps=5,
    )
    out = await loop.run("loop")
    assert "达到最大步数" in out or "max" in out.lower()
    # 中断原因已作为 system 消息写入会话（供前端渲染中断提示）
    msgs = session.get_messages()
    assert any(
        m["role"] == "system" and "已达到最大步数" in m.get("content", "")
        for m in msgs
    )


@pytest.mark.asyncio
async def test_loop_temperature_and_tool_trace():
    adapter = FakeAdapter([
        AssistantMessage(content="", tool_calls=[
            ToolCall(id="c1", name="greet", args={"name": "bob"}),
        ]),
        AssistantMessage(content="done"),
    ])
    registry = Registry()
    registry.register_tool(GreetingTool())
    session = Session("t4")
    loop = AgentLoop(
        adapter=adapter, registry=registry, session=session,
        script_runner=None, skills={}, temperature=0.3,
        extra_system_prompt="你是测试助手",
    )
    out = await loop.run("say hi")
    assert out == "done"
    assert adapter.last_temperature == 0.3
    # 工具轨迹已记录
    assert len(loop.tool_trace) == 1
    assert loop.tool_trace[0]["name"] == "greet"
    assert loop.tool_trace[0]["args"] == {"name": "bob"}
    # 系统提示词含智能体指令
    sys_msg = session.get_messages()[0]
    assert "你是测试助手" in sys_msg["content"]


@pytest.mark.asyncio
async def test_loop_tool_trace_cleared_each_run():
    adapter = FakeAdapter([AssistantMessage(content="hi")])
    registry = Registry()
    session = Session("t5")
    loop = AgentLoop(
        adapter=adapter, registry=registry, session=session,
        script_runner=None, skills={},
    )
    await loop.run("first")
    await loop.run("second")
    assert loop.tool_trace == []