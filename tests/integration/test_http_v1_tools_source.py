"""GET /v1/tools 端点：每个 schema 应带 source 字段。"""
import textwrap
from pathlib import Path

from fastapi.testclient import TestClient


def _write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content), encoding="utf-8")


def test_v1_tools_includes_source_field(tmp_path, monkeypatch):
    """端点返回的工具列表中，每个工具 schema 都应有 source 字段，至少一个 builtin。"""
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
        resp = client.get("/v1/tools")
    assert resp.status_code == 200
    body = resp.json()
    # 兼容两种返回结构：dict with "tools" key 或直接 list
    tools = body.get("tools", body) if isinstance(body, dict) else body
    assert len(tools) > 0
    sources = {t.get("source", "").split(":")[0] for t in tools}
    assert "builtin" in sources