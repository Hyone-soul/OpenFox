import textwrap
import time
from pathlib import Path

from open_fox.core.custom_tools.loader import CustomToolsLoader
from open_fox.core.registry import Registry


def _write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content), encoding="utf-8")


def test_watchdog_detects_modification(tmp_path):
    f = tmp_path / "live.py"
    _write(f, """
        from open_fox.tools import tool
        @tool(name="live", description="v1")
        def live(): return "v1"
    """)
    reg = Registry()
    loader = CustomToolsLoader(tmp_path, reg)
    loader.start()
    try:
        time.sleep(2)  # watchdog 启动稳定
        _write(f, """
            from open_fox.tools import tool
            @tool(name="live", description="v2")
            def live(): return "v2"
        """)
        deadline = time.time() + 8
        while time.time() < deadline:
            if "v2" in loader.all().get("live", type("X", (), {"description": ""})()).description:
                break
            time.sleep(0.3)
        assert "v2" in loader.all()["live"].description
    finally:
        loader.stop()