"""配置加载测试。"""
from pathlib import Path

import pytest

from open_fox.config import AppConfig, load_config


def test_load_config_with_defaults(tmp_path: Path):
    """无配置文件时返回默认值。"""
    cfg = load_config()
    assert isinstance(cfg, AppConfig)
    assert cfg.skills_dir == Path("./skills")
    assert cfg.workspace_dir == Path("./workspace")
    assert cfg.max_agent_steps == 500


def test_load_config_from_yaml(tmp_path: Path):
    """从 YAML 文件加载配置。"""
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(
        "skills_dir: ./my-skills\n"
        "max_agent_steps: 10\n"
        "models:\n"
        "  - name: gpt-4o\n"
        "    base_url: https://api.openai.com/v1\n"
        "    api_key_env: OPENAI_API_KEY\n"
        "    model: gpt-4o\n",
        encoding="utf-8",
    )
    cfg = load_config(str(yaml_path))
    assert cfg.skills_dir == Path("./my-skills")
    assert cfg.max_agent_steps == 10
    assert len(cfg.models) == 1
    assert cfg.models[0].name == "gpt-4o"


def test_cli_overrides_take_precedence(tmp_path: Path):
    """CLI 参数覆盖 YAML。"""
    cfg = load_config(cli_overrides={"model": "deepseek-chat"})
    assert cfg.active_model == "deepseek-chat"


def test_env_var_substitution(monkeypatch, tmp_path: Path):
    """环境变量占位符被替换。"""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(
        "models:\n"
        "  - name: gpt-4o\n"
        "    base_url: https://api.openai.com/v1\n"
        "    api_key_env: OPENAI_API_KEY\n"
        "    model: gpt-4o\n",
        encoding="utf-8",
    )
    cfg = load_config(str(yaml_path))
    assert cfg.models[0].api_key == "sk-test"


def test_load_skill_evolution_config(tmp_path: Path):
    p = tmp_path / "c.yaml"
    p.write_text(
        "models: []\n"
        "skill_evolution:\n"
        "  enabled: false\n"
        "  min_failures: 3\n"
        "  data_dir: ./data/evo\n",
        encoding="utf-8",
    )
    cfg = load_config(str(p))
    se = cfg.skill_evolution
    assert se.enabled is False
    assert se.min_failures == 3
    assert se.data_dir == Path("./data/evo")
    assert se.require_confirmation is True  # 未配置走缺省


def test_skill_evolution_defaults(tmp_path: Path):
    p = tmp_path / "c2.yaml"
    p.write_text("models: []\n", encoding="utf-8")
    cfg = load_config(str(p))
    se = cfg.skill_evolution
    assert se.enabled is True
    assert se.require_confirmation is True
    assert se.min_failures == 2
    assert se.min_repeats == 2
    assert se.cooldown_turns == 20


class TestCustomToolPaths:
    def test_default_paths(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = AppConfig()
        assert cfg.custom_tools_dir == Path("./tools")
        assert cfg.mcps_dir == Path("./mcps")


class TestMcpServerConfigExtensions:
    def test_minimal_stdio_defaults(self):
        from open_fox.config import McpServerConfig
        cfg = McpServerConfig(name="x", transport="stdio", command="echo")
        assert cfg.enabled is True
        assert cfg.timeout == 30
        assert cfg.tool_allowlist == []
        assert cfg.tool_denylist == []
        assert cfg.permissions == {}
        assert cfg.source_file == ""


class TestMcpServersRemoved:
    def test_no_mcp_servers_attr(self):
        cfg = AppConfig()
        assert not hasattr(cfg, "mcp_servers") or "mcp_servers" not in cfg.__dataclass_fields__
