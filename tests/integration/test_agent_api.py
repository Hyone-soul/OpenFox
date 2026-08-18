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
    # 通过 lifespan 初始化组件
    return TestClient(app)


def test_agent_crud_flow(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    with client:
        # 创建
        r = client.post("/v1/agents", json={
            "id": "demo", "name": "演示", "model": "m1",
            "tools": ["read_file"],
        })
        assert r.status_code == 200
        assert r.json()["id"] == "demo"
        # 列表
        r = client.get("/v1/agents")
        assert r.status_code == 200
        assert any(a["id"] == "demo" for a in r.json()["agents"])
        # 更新
        r = client.put("/v1/agents/demo", json={"name": "新名"})
        assert r.status_code == 200
        assert r.json()["name"] == "新名"
        # 删除
        r = client.delete("/v1/agents/demo")
        assert r.status_code == 204
        r = client.get("/v1/agents/demo")
        assert r.status_code == 404


def test_agent_duplicate_id_409(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    with client:
        client.post("/v1/agents", json={"id": "demo", "name": "A"})
        r = client.post("/v1/agents", json={"id": "demo", "name": "B"})
        assert r.status_code == 409


def test_agent_invalid_model_400(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    with client:
        r = client.post("/v1/agents", json={"id": "demo", "name": "A", "model": "nope"})
        assert r.status_code == 400


def test_agent_update_invalid_model_400(tmp_path, monkeypatch):
    """PUT 更新时写入非法 model 应返回 400（合并后的完整配置需通过校验）。"""
    client = _client(tmp_path, monkeypatch)
    with client:
        # 先创建合法智能体
        client.post("/v1/agents", json={"id": "demo", "name": "A", "model": "m1"})
        # 更新成非法 model → 400
        r = client.put("/v1/agents/demo", json={"model": "nope"})
        assert r.status_code == 400
        assert "model" in r.json()["detail"]
        # 原配置未被污染（校验失败不应落盘）
        r = client.get("/v1/agents/demo")
        assert r.json()["model"] == "m1"
        # 更新不存在的智能体 → 404
        r = client.put("/v1/agents/unknown", json={"name": "X"})
        assert r.status_code == 404


def test_agent_test_connectivity(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    with client:
        # 有效模型：ok=true
        client.post("/v1/agents", json={"id": "demo", "name": "A", "model": "m1"})
        r = client.get("/v1/agents/demo/test")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        # 未绑定模型：使用全局默认（ok=true）
        client.post("/v1/agents", json={"id": "nodemo", "name": "B"})
        r = client.get("/v1/agents/nodemo/test")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        # 不存在：404
        r = client.get("/v1/agents/unknown/test")
        assert r.status_code == 404
