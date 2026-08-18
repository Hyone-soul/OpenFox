"""lifespan 应装载自定义工具 + MCP configs，并把 components 升级为 11 元。"""
import textwrap
from pathlib import Path

from fastapi.testclient import TestClient


def _write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content), encoding="utf-8")


def test_lifespan_loads_custom_tools_and_mcps(tmp_path, monkeypatch):
    (tmp_path / "tools").mkdir()
    _write(tmp_path / "tools" / "hi.py", """
        from open_fox.tools import tool
        @tool(name="hi", description="say hi")
        def hi(): return "ok"
    """)
    (tmp_path / "mcps").mkdir()
    _write(tmp_path / "mcps" / "fs.yaml", """
        name: fs
        transport: stdio
        command: echo
        args: ["hi"]
    """)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"""
        models:
          - name: m1
            base_url: http://test
            api_key_env: M1_KEY
            model: m1
        custom_tools_dir: {(tmp_path / "tools").as_posix()}
        mcps_dir: {(tmp_path / "mcps").as_posix()}
        storage:
            backend: json
            json_dir: {(tmp_path / 'data' / 'sessions').as_posix()}
    """, encoding="utf-8")
    monkeypatch.setenv("M1_KEY", "k")

    from open_fox.server import app
    app.state.config_path = str(config_path)
    with TestClient(app):
        comps = app.state.components
        assert len(comps) == 11
        registry = comps[2]
        assert "hi" in registry._tools
        # custom_tools_loader 在第 10 位
        loader = comps[9]
        assert loader is not None
        assert "hi" in loader.all()
