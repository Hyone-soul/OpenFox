from open_fox.core.custom_tools.schema_builder import build_schema_from_signature


def _sig(func):
    return build_schema_from_signature(func)


def test_str_type():
    def f(x: str): ...
    s = _sig(f)
    assert s["properties"]["x"] == {"type": "string"}


def test_int_with_default_not_required():
    def f(x: int = 10): ...
    s = _sig(f)
    assert "x" not in s.get("required", [])
    assert s["properties"]["x"]["type"] == "integer"


def test_optional_str():
    def f(x: str | None = None): ...
    s = _sig(f)
    assert "x" not in s.get("required", [])
    assert "null" in str(s["properties"]["x"])


def test_list_str():
    def f(xs: list[str]): ...
    s = _sig(f)
    assert s["properties"]["xs"]["type"] == "array"
    assert s["properties"]["xs"]["items"]["type"] == "string"


def test_literal_enum():
    from typing import Literal
    def f(m: Literal["a", "b"]): ...
    s = _sig(f)
    assert s["properties"]["m"]["enum"] == ["a", "b"]


def test_no_annotation_falls_back_to_string():
    def f(x): ...
    s = _sig(f)
    assert s["properties"]["x"]["type"] == "string"


def test_required_field():
    def f(a: str, b: int): ...
    s = _sig(f)
    assert set(s["required"]) == {"a", "b"}
