"""Skill 进化 REST API 集成测试。"""
import asyncio

from fastapi.testclient import TestClient

from open_fox.server import app


def _client(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "skills_dir: " + (tmp_path / "skills").as_posix() + "\n"
        "models:\n"
        "  - name: m1\n"
        "    base_url: http://test\n"
        "    api_key_env: M1_KEY\n"
        "    model: m1\n"
        "storage:\n"
        "  backend: json\n"
        f"  json_dir: {(tmp_path / 'sessions').as_posix()}\n"
        "skill_evolution:\n"
        f"  data_dir: {(tmp_path / 'evo').as_posix()}\n"
        f"  require_confirmation: true\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("M1_KEY", "k")
    app.state.config_path = str(config_path)
    return TestClient(app)


def _enqueue(pending, content):
    """同步入队（测试内无运行中的事件循环，asyncio.run 安全）。"""
    return asyncio.run(pending.enqueue("create", "evo-demo", "测试候选", content))


def test_evolution_confirm_writes_skill(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    with client:
        # 防真实网络：FakeAdapter 已由既有注入模式提供，这里直接短路 _chat
        app.state.evolution_task._chat = None
        item = _enqueue(app.state.evolution_task.queue,
                        "---\nname: evo-demo\ndescription: 进化测试\n---\n正文")
        r = client.post(f"/v1/evolution/pending/{item.id}/confirm")
        assert r.status_code == 200
        assert "Skill新增" in r.json()["summary"]
        # 写盘生效：/v1/skills 应包含新 skill
        r2 = client.get("/v1/skills")
        assert "evo-demo" in r2.json()
        # 确认后不再出现在 pending
        r3 = client.get("/v1/evolution/pending")
        assert all(i["id"] != item.id for i in r3.json()["pending"])


def test_evolution_reject_and_404(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    with client:
        app.state.evolution_task._chat = None
        item = _enqueue(app.state.evolution_task.queue,
                        "---\nname: evo-demo\ndescription: d\n---\n正文")
        r = client.post(f"/v1/evolution/pending/{item.id}/reject")
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"
        # 已处理的不能再 confirm
        r2 = client.post(f"/v1/evolution/pending/{item.id}/confirm")
        assert r2.status_code == 400
        # 未知 id → 404
        r3 = client.post("/v1/evolution/pending/evo-nope/confirm")
        assert r3.status_code == 404
