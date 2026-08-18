"""MCP 配置加载器单元测试。"""
import textwrap
from pathlib import Path

from open_fox.core.mcp.config_loader import load_mcp_configs


def _write(p: Path, content: str):
    p.write_text(textwrap.dedent(content), encoding="utf-8")


def test_loads_valid_yaml(tmp_path):
    _write(tmp_path / "fs.yaml", """
        name: fs
        transport: stdio
        command: npx
        args: ["@x/server-fs"]
    """)
    cfgs, errors = load_mcp_configs(tmp_path)
    assert errors == []
    assert len(cfgs) == 1
    assert cfgs[0].name == "fs" and cfgs[0].enabled is True


def test_loads_json(tmp_path):
    _write(tmp_path / "x.json", """{
        "name": "x", "transport": "streamable-http", "url": "http://h/mcp"
    }""")
    cfgs, errors = load_mcp_configs(tmp_path)
    assert errors == []
    assert cfgs[0].url == "http://h/mcp"


def test_enabled_false_skipped(tmp_path):
    _write(tmp_path / "x.yaml", """
        name: x
        transport: stdio
        command: echo
        enabled: false
    """)
    cfgs, errors = load_mcp_configs(tmp_path)
    assert errors == []
    assert len(cfgs) == 1 and cfgs[0].enabled is False


def test_missing_dir_returns_empty(tmp_path):
    cfgs, errors = load_mcp_configs(tmp_path / "nope")
    assert cfgs == [] and errors == []


def test_invalid_yaml_collected_as_error(tmp_path):
    _write(tmp_path / "bad.yaml", "name: : :")
    cfgs, errors = load_mcp_configs(tmp_path)
    assert cfgs == []
    assert len(errors) == 1 and "bad.yaml" in errors[0]["source"]


def test_duplicate_name_collected_as_error(tmp_path):
    _write(tmp_path / "a.yaml", "name: dup\ntransport: stdio\ncommand: echo")
    _write(tmp_path / "b.yaml", "name: dup\ntransport: stdio\ncommand: echo")
    cfgs, errors = load_mcp_configs(tmp_path)
    assert len(cfgs) == 1
    assert len(errors) == 1


def test_env_substitution_in_headers(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_TOKEN", "abc")
    _write(tmp_path / "x.yaml", """
        name: x
        transport: sse
        url: http://h/sse
        headers:
          Authorization: "Bearer ${MY_TOKEN}"
    """)
    cfgs, _ = load_mcp_configs(tmp_path)
    assert cfgs[0].headers["Authorization"] == "Bearer abc"


def test_unknown_transport_collected(tmp_path):
    _write(tmp_path / "x.yaml", """
        name: x
        transport: bogus
    """)
    cfgs, errors = load_mcp_configs(tmp_path)
    assert cfgs == [] and len(errors) == 1
