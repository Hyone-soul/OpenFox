# tests/integration/test_agent_chat.py
from fastapi.testclient import TestClient

from open_fox.core.adapters.base import AssistantMessage
from open_fox.server import app


class FakeAdapter:
    """按智能体聊天的 mock adapter：总是返回固定回复。"""

    def __init__(self, reply="这是测试回复"):
        self._reply = reply
        self.calls = 0
        self.last_messages = None

    def set_active(self, name: str) -> None:
        # 模拟真实 adapter 的模型切换（端点会对绑定模型的智能体调用）
        self.active = name

    async def chat(self, messages, tools=None, stream=False, temperature=None):
        self.calls += 1
        self.last_messages = messages
        return AssistantMessage(content=self._reply)


def _client(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    # storage 指向 tmp 目录，隔离会话数据，避免测试互相污染真实的 ./data/sessions
    config_path.write_text(
        "models:\n"
        "  - name: m1\n"
        "    base_url: http://test\n"
        "    api_key_env: M1_KEY\n"
        "    model: m1\n"
        "storage:\n"
        "  backend: json\n"
        f"  json_dir: {(tmp_path / 'sessions').as_posix()}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("M1_KEY", "k")
    app.state.config_path = str(config_path)
    return TestClient(app)


def _inject_fake_adapter(fake):
    """把 app.state.components 中的 adapter 替换为 FakeAdapter。"""
    components = list(app.state.components)
    components[1] = fake
    app.state.components = tuple(components)


def test_agent_chat_reply(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    fake = FakeAdapter()
    with client:
        # 替换 adapter 为 FakeAdapter（避免真实网络请求）
        _inject_fake_adapter(fake)
        # 先创建智能体
        client.post("/v1/agents", json={
            "id": "demo", "name": "演示", "model": "m1",
            "system_prompt": "你是测试助手",
            "tools": [],
        })
        r = client.post("/v1/agent-chat", json={
            "session_id": "s1", "agent_id": "demo", "message": "你好",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["agent_id"] == "demo"
        assert data["reply"] == "这是测试回复"
        assert "usage" in data
        assert "tool_trace" in data
        # adapter 被调用过（消息真正经过 AgentLoop）
        assert fake.calls >= 1
        # 系统提示词应包含智能体专属指令
        assert any("你是测试助手" in (m.get("content") or "") for m in fake.last_messages)


def test_agent_chat_unknown_agent_404(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    with client:
        _inject_fake_adapter(FakeAdapter())
        r = client.post("/v1/agent-chat", json={
            "session_id": "s1", "agent_id": "nope", "message": "hi",
        })
        assert r.status_code == 404


def test_agent_chat_empty_message_400(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    with client:
        _inject_fake_adapter(FakeAdapter())
        client.post("/v1/agents", json={"id": "demo", "name": "演示", "model": "m1"})
        r = client.post("/v1/agent-chat", json={
            "session_id": "s1", "agent_id": "demo", "message": "   ",
        })
        assert r.status_code == 400


def test_agent_chat_system_injected_once_per_session(tmp_path, monkeypatch):
    """同会话多轮 agent-chat 只注入一次 system 提示词，避免上下文膨胀。

    回归背景：会话首部有 __meta__ 消息导致 get_messages()[0] 永远不是 system，
    原条件恒为 True，第二轮会再追加一条 system。
    """
    client = _client(tmp_path, monkeypatch)
    fake = FakeAdapter()
    with client:
        _inject_fake_adapter(fake)
        client.post("/v1/agents", json={
            "id": "demo", "name": "演示", "model": "m1",
            "system_prompt": "你是测试助手",
        })
        # 第一轮
        r1 = client.post("/v1/agent-chat", json={
            "session_id": "s1", "agent_id": "demo", "message": "你好",
        })
        assert r1.status_code == 200
        # 第二轮（同一会话）
        r2 = client.post("/v1/agent-chat", json={
            "session_id": "s1", "agent_id": "demo", "message": "继续",
        })
        assert r2.status_code == 200
        # 第二次调用时消息里 system 只有 1 条（FakeAdapter 记录的是最后一次 chat 的输入）
        system_msgs = [m for m in fake.last_messages
                       if m.get("role") == "system"]
        assert len(system_msgs) == 1
        assert "你是测试助手" in system_msgs[0]["content"]
        # 第二轮只新增了 1 条 user 消息（未追加重复 system）
        user_msgs = [m for m in fake.last_messages if m.get("role") == "user"]
        assert len(user_msgs) == 2
