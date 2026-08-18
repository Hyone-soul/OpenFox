"""POST /v1/reload 端点：调用 reload_all 返回加载报告。"""
import textwrap
from pathlib import Path

from fastapi.testclient import TestClient


def _write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content), encoding="utf-8")


def test_v1_reload_returns_report(tmp_path, monkeypatch):
    """端点应返回 reload_all 报告（custom_tools/mcp_servers/mcp_tools/errors）。"""
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
        client = TestClient(app)
        resp = client.post("/v1/reload")
    assert resp.status_code == 200
    body = resp.json()
    assert "custom_tools" in body
    assert "mcp_servers" in body
    assert "mcp_tools" in body
    assert "errors" in body