# tests/unit/test_agent_filter.py
from open_fox.agents import AgentConfig
from open_fox.core.agent_filter import filter_registry, filter_skills
from open_fox.core.mcp.tool_adapter import McpToolAdapter
from open_fox.core.registry import Registry
from open_fox.core.tools.base import BaseTool, ToolResult


class FakeTool(BaseTool):
    name = "fake_tool"
    description = "fake"
    parameters = {}
    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content="ok")


class FakeTool2(BaseTool):
    name = "fake_tool2"
    description = "fake2"
    parameters = {}
    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, content="ok")


def _registry_with_two_tools() -> Registry:
    r = Registry()
    r.register_tool(FakeTool())
    r.register_tool(FakeTool2())
    return r


def test_registry_get_tool():
    r = _registry_with_two_tools()
    assert r.get_tool("fake_tool") is not None
    assert r.get_tool("nonexistent") is None


def test_filter_registry_all_tools_when_empty():
    r = _registry_with_two_tools()
    agent = AgentConfig(id="a", name="A", tools=[])
    filtered = filter_registry(agent, r)
    names = [s["function"]["name"] for s in filtered.list_tool_schemas()]
    assert set(names) == {"fake_tool", "fake_tool2"}


def test_filter_registry_subset():
    r = _registry_with_two_tools()
    agent = AgentConfig(id="a", name="A", tools=["fake_tool"])
    filtered = filter_registry(agent, r)
    names = [s["function"]["name"] for s in filtered.list_tool_schemas()]
    assert names == ["fake_tool"]


def test_filter_skills_empty_means_all():
    skills = {"s1": object(), "s2": object()}
    agent = AgentConfig(id="a", name="A", skills=[])
    assert set(filter_skills(agent, skills).keys()) == {"s1", "s2"}


def test_filter_skills_subset():
    skills = {"s1": object(), "s2": object()}
    agent = AgentConfig(id="a", name="A", skills=["s1"])
    assert set(filter_skills(agent, skills).keys()) == {"s1"}


# ---------- MCP 工具过滤用例 ----------

class FakeMcpTransport:
    """假的 MCP 传输层：call 返回 dict 即可。"""
    async def call_tool(self, tool_name: str, args: dict) -> dict:
        return {"content": [{"type": "text", "text": f"ok:{tool_name}"}]}


def _registry_with_mcp_tool() -> Registry:
    r = Registry()
    r.register_mcp_tool(McpToolAdapter(
        server_name="server_a",
        transport=FakeMcpTransport(),
        tool_name="search",
        description="搜索工具",
        input_schema={"type": "object", "properties": {}},
    ))
    return r


def test_filter_registry_all_tools_when_empty_includes_mcp():
    # agent.tools 为空（=全部）时，MCP 工具应保留在过滤结果里
    r = _registry_with_mcp_tool()
    agent = AgentConfig(id="a", name="A", tools=[])
    filtered = filter_registry(agent, r)
    names = [s["function"]["name"] for s in filtered.list_tool_schemas()]
    assert names == ["server_a__search"]


def test_filter_registry_explicit_mcp_tool_name():
    # agent.tools 显式指定 MCP 工具名 <server>__<tool> 时能过滤出来
    r = _registry_with_mcp_tool()
    agent = AgentConfig(id="a", name="A", tools=["server_a__search"])
    filtered = filter_registry(agent, r)
    names = [s["function"]["name"] for s in filtered.list_tool_schemas()]
    assert names == ["server_a__search"]


def test_filter_registry_mcp_tool_not_in_tools_is_dropped():
    # 指定不存在的 MCP 工具名时被丢弃
    r = _registry_with_mcp_tool()
    agent = AgentConfig(id="a", name="A", tools=["server_a__unknown"])
    filtered = filter_registry(agent, r)
    assert filtered.list_tool_schemas() == []
