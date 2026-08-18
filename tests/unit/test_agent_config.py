# tests/unit/test_agent_config.py
from open_fox.agents import AgentConfig, validate_agent


def test_agent_config_defaults():
    a = AgentConfig(id="demo", name="演示")
    assert a.description == ""
    assert a.model == ""
    assert a.tools == []
    assert a.skills == []
    assert a.temperature is None
    assert a.max_steps == 500


def test_agent_config_roundtrip():
    a = AgentConfig(id="demo", name="演示", model="m1",
                    system_prompt="hello", tools=["read_file"],
                    skills=["db-helper"], temperature=0.5, max_steps=5)
    b = AgentConfig.from_dict(a.to_dict())
    assert b == a


def test_validate_ok():
    a = AgentConfig(id="demo", name="演示", model="m1")
    assert validate_agent(a, ["m1", "m2"]) == []


def test_validate_missing_id():
    a = AgentConfig(id="", name="演示")
    errors = validate_agent(a, [])
    assert any("id" in e for e in errors)


def test_validate_bad_model():
    a = AgentConfig(id="demo", name="演示", model="nope")
    errors = validate_agent(a, ["m1"])
    assert any("model" in e for e in errors)
