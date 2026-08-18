from fastapi.testclient import TestClient

from open_fox.server import app


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


def test_session_create_list_delete(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    with client:
        # 先建智能体
        client.post("/v1/agents", json={"id": "demo", "name": "演示", "model": "m1"})
        # 建会话
        r = client.post("/v1/sessions", json={"agent_id": "demo", "title": "测试会话"})
        assert r.status_code == 200
        sid = r.json()["id"]
        # 列表
        r = client.get("/v1/sessions")
        assert r.status_code == 200
        s = next(x for x in r.json()["sessions"] if x["id"] == sid)
        assert s["agent_id"] == "demo"
        assert s["title"] == "测试会话"
        # messages 端点
        r = client.get(f"/v1/sessions/{sid}/messages")
        assert r.status_code == 200
        assert r.json()["agent_id"] == "demo"
        # 删除
        r = client.delete(f"/v1/sessions/{sid}")
        assert r.status_code == 204
        # 删除后列表为空
        r = client.get("/v1/sessions")
        assert all(x["id"] != sid for x in r.json()["sessions"])
