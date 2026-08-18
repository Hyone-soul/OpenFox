import textwrap
from pathlib import Path

from open_fox.core.custom_tools.loader import CustomToolsLoader
from open_fox.core.registry import Registry


def _write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content), encoding="utf-8")


def test_scan_loads_decorated_function(tmp_path):
    _write(tmp_path / "hello.py", """
        from open_fox.tools import tool
        @tool(name="hi", description="say hi")
        def hi(name: str) -> str:
            return f"hi {name}"
    """)
    reg = Registry()
    loader = CustomToolsLoader(tmp_path, reg)
    errors = loader.rescan()
    assert errors == []
    tools = loader.all()
    assert "hi" in tools
    assert "hi" in reg._tools


def test_scan_skips_underscore_files(tmp_path):
    _write(tmp_path / "_private.py", """
        from open_fox.tools import tool
        @tool(name="priv", description="x")
        def priv(): return ""
    """)
    reg = Registry()
    loader = CustomToolsLoader(tmp_path, reg)
    loader.rescan()
    assert loader.all() == {}


def test_scan_skips_init_py(tmp_path):
    _write(tmp_path / "__init__.py", "from open_fox.tools import tool")
    reg = Registry()
    loader = CustomToolsLoader(tmp_path, reg)
    loader.rescan()
    assert loader.all() == {}


def test_scan_collects_errors_for_bad_file(tmp_path):
    _write(tmp_path / "bad.py", "this is not python !@#")
    reg = Registry()
    loader = CustomToolsLoader(tmp_path, reg)
    errors = loader.rescan()
    assert len(errors) == 1
    assert "bad.py" in errors[0]["source"]


def test_rescan_unregisters_removed_tool(tmp_path):
    _write(tmp_path / "a.py", """
        from open_fox.tools import tool
        @tool(name="a", description="x")
        def a(): return ""
    """)
    reg = Registry()
    loader = CustomToolsLoader(tmp_path, reg)
    loader.rescan()
    assert "a" in reg._tools

    (tmp_path / "a.py").unlink()
    loader.rescan()
    assert "a" not in reg._tools