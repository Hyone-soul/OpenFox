"""GET /v1/mcps 端点：列出 MCP server + 工具 + 启停状态。"""
import textwrap
from pathlib import Path

from fastapi.testclient import TestClient


def _write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content), encoding="utf-8")


def test_v1_mcps_returns_empty_when_no_mcps(tmp_path, monkeypatch):
    """无任何 MCP 配置时，端点应返回空 servers 列表。"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"""
        models:
          - name: m1
            base_url: http://test
            api_key_env: M1_KEY
            model: m1
        custom_tools_dir: {(tmp_path / 'tools').as_posix()}
        mcps_dir: {(tmp_path / 'mcps').as_posix()}
        storage:
            backend: json
            json_dir: {(tmp_path / 'data' / 'sessions').as_posix()}
    """, encoding="utf-8")
    monkeypatch.setenv("M1_KEY", "k")

    from open_fox.server import app
    app.state.config_path = str(config_path)
    with TestClient(app):
        r = app.state  # noqa: F841 触发状态访问
        client = TestClient(app)
        resp = client.get("/v1/mcps")
    assert resp.status_code == 200
    assert resp.json() == {"servers": [], "total_servers": 0, "total_tools": 0}