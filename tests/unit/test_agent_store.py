# tests/unit/test_agent_store.py
import yaml
from pathlib import Path
from open_fox.agents import AgentConfig, AgentStore


def _write_base_yaml(path: Path):
    """带 models 段的初始 config.yaml，验证写回不破坏其他段。"""
    path.write_text(
        yaml.safe_dump({
            "models": [{"name": "m1", "base_url": "http://x",
                        "api_key_env": "K", "model": "m1"}],
            "storage": {"backend": "json", "json_dir": "./data/sessions"},
        }),
        encoding="utf-8",
    )


def test_create_and_list(tmp_path: Path):
    p = tmp_path / "config.yaml"
    _write_base_yaml(p)
    store = AgentStore(p)
    a = store.create(AgentConfig(id="demo", name="演示", model="m1"))
    assert a.created_at  # 自动补时间
    assert a.updated_at
    got = store.get("demo")
    assert got is not None
    assert got.name == "演示"
    assert got.model == "m1"


def test_preserve_other_sections(tmp_path: Path):
    p = tmp_path / "config.yaml"
    _write_base_yaml(p)
    store = AgentStore(p)
    store.create(AgentConfig(id="demo", name="演示"))
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert "models" in raw          # 原段保留
    assert "storage" in raw         # 原段保留
    assert raw["storage"]["backend"] == "json"
    assert len(raw["agents"]) == 1  # agents 段已写入


def test_update(tmp_path: Path):
    p = tmp_path / "config.yaml"
    _write_base_yaml(p)
    store = AgentStore(p)
    store.create(AgentConfig(id="demo", name="旧名"))
    updated = store.update("demo", {"name": "新名", "temperature": 0.7})
    assert updated.name == "新名"
    assert updated.temperature == 0.7
    assert store.get("demo").name == "新名"


def test_delete(tmp_path: Path):
    p = tmp_path / "config.yaml"
    _write_base_yaml(p)
    store = AgentStore(p)
    store.create(AgentConfig(id="demo", name="演示"))
    store.delete("demo")
    assert store.get("demo") is None
    store.delete("demo")  # 幂等不抛错


def test_agent_store_duplicate_id_rejected(tmp_path: Path):
    p = tmp_path / "config.yaml"
    _write_base_yaml(p)
    store = AgentStore(p)
    store.create(AgentConfig(id="demo", name="A"))
    try:
        store.create(AgentConfig(id="demo", name="B"))
        assert False, "应拒绝重复 id"
    except ValueError as e:
        assert "已存在" in str(e)
