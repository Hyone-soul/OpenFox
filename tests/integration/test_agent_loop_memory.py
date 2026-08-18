# tests/integration/test_agent_loop_memory.py
import pytest
from fastapi.testclient import TestClient

from open_fox.core.adapters.base import AssistantMessage
from open_fox.core.agent_loop import AgentLoop
from open_fox.core.memory.manager import MemoryManager
from open_fox.core.registry import Registry
from open_fox.core.session import Session
from open_fox.server import app


class FakeAdapter:
    """内存 FakeAdapter：chat 返回固定回复，不联网。"""

    active = "fake-model"

    def __init__(self):
        self.chat_calls = 0
        self.last_messages = None

    async def chat(self, messages, tools=None, stream=False, temperature=None):
        self.chat_calls += 1
        self.last_messages = messages
        return AssistantMessage(content="ok")

    def list_models(self):
        return ["fake-model"]

    def set_active(self, name):
        pass


def _inject_fake_adapter(fake):
    """把 app.state.components 中的 adapter 替换为 FakeAdapter（components[1]）。"""
    components = list(app.state.components)
    components[1] = fake
    app.state.components = tuple(components)


@pytest.mark.asyncio
async def test_agent_loop_injects_memory(tmp_path):
    """AgentLoop 直接注入：system prompt 应含记忆文本。"""
    m = MemoryManager(tmp_path=tmp_path)
    await m.load()
    await m.add("explicit", "用户显式记忆", "项目用 FastAPI")
    session = Session(session_id="s", storage=None)
    adapter = FakeAdapter()
    loop = AgentLoop(adapter=adapter, registry=Registry(), session=session,
                     script_runner=None, skills={}, max_steps=2,
                     memory_manager=m)
    await loop.run("你好")
    # system prompt 应含记忆
    system_msg = [x for x in session.get_messages() if x["role"] == "system"]
    assert system_msg
    assert "FastAPI" in system_msg[0]["content"]


def test_server_chat_injects_memory(tmp_path, monkeypatch):
    """server /v1/chat 端点：memory_manager 传入 AgentLoop → system prompt 含记忆。

    回归 C1：三处 AgentLoop 构造漏传 memory_manager 导致 HTTP/Web 端不注入记忆。
    chdir 到 tmp_path 使 server 的 MemoryManager(tmp_path=Path.cwd()) 指向临时目录，
    并预写带已知记忆的 OPENFOX.md 保证确定性。
    """
    monkeypatch.chdir(tmp_path)
    # 预写 OPENFOX.md（显式记忆含 FastAPI）
    (tmp_path / "OPENFOX.md").write_text(
        "# OpenFox 全局记忆\n"
        "## 📌 用户显式记忆\n"
        "- 项目用 FastAPI｜来源：会话描述｜优先级：最高\n",
        encoding="utf-8",
    )
    # 配置指向临时目录，隔离会话数据
    config_path = tmp_path / "config.yaml"
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

    fake = FakeAdapter()
    with TestClient(app) as client:
        _inject_fake_adapter(fake)
        r = client.post("/v1/chat", json={"session_id": "s1", "message": "你好"})
        assert r.status_code == 200
        assert r.json()["reply"] == "ok"
        # system prompt 应含记忆（证明 memory_manager 已传入 AgentLoop）
        system_msgs = [m for m in fake.last_messages
                       if m.get("role") == "system"]
        assert system_msgs
        assert "FastAPI" in system_msgs[0]["content"]
