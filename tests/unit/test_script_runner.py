"""脚本执行沙箱测试。"""
import sys
from pathlib import Path

import pytest

from open_fox.core.exceptions import ScriptTimeout
from open_fox.core.scripts.runner import ScriptRunner
from open_fox.core.skills.models import ScriptSpec


def _write(skill_dir: Path, name: str, content: str):
    (skill_dir / name).write_text(content, encoding="utf-8")
    (skill_dir / name).chmod(0o755)


@pytest.fixture
def skill_dir(tmp_path: Path) -> Path:
    d = tmp_path / "my-skill"
    d.mkdir()
    return d


def test_run_python_script(skill_dir: Path):
    _write(skill_dir, "greet.py", "print('hi')\n")
    spec = ScriptSpec(id="greet", lang="python", entry="greet.py", timeout=10)
    runner = ScriptRunner()
    r = runner.run(spec, skill_dir)
    assert r.exit_code == 0
    assert "hi" in r.stdout


def test_run_shell_script(skill_dir: Path):
    _write(skill_dir, "echo.sh", "#!/usr/bin/env bash\necho shell-ok\n")
    spec = ScriptSpec(id="echo", lang="shell", entry="echo.sh", timeout=10)
    runner = ScriptRunner()
    r = runner.run(spec, skill_dir)
    assert r.exit_code == 0
    assert "shell-ok" in r.stdout


def test_run_node_script(skill_dir: Path):
    _write(skill_dir, "hello.js", "console.log('node-ok')\n")
    spec = ScriptSpec(id="hello", lang="node", entry="hello.js", timeout=10)
    runner = ScriptRunner()
    r = runner.run(spec, skill_dir)
    assert r.exit_code == 0
    assert "node-ok" in r.stdout


def test_run_with_args(skill_dir: Path):
    _write(skill_dir, "args.py", "import sys; print(sys.argv[1])\n")
    spec = ScriptSpec(id="args", lang="python", entry="args.py", timeout=10)
    runner = ScriptRunner()
    r = runner.run(spec, skill_dir, args=["world"])
    assert "world" in r.stdout


def test_script_timeout(skill_dir: Path):
    _write(skill_dir, "sleep.py", "import time; time.sleep(5)\n")
    spec = ScriptSpec(id="sleep", lang="python", entry="sleep.py", timeout=1)
    runner = ScriptRunner()
    with pytest.raises(ScriptTimeout):
        runner.run(spec, skill_dir)


def test_nonzero_exit(skill_dir: Path):
    _write(skill_dir, "fail.py", "import sys; sys.exit(3)\n")
    spec = ScriptSpec(id="fail", lang="python", entry="fail.py", timeout=10)
    runner = ScriptRunner()
    r = runner.run(spec, skill_dir)
    assert r.exit_code == 3


def test_missing_script_raises(skill_dir: Path):
    spec = ScriptSpec(id="x", lang="python", entry="nope.py", timeout=10)
    runner = ScriptRunner()
    with pytest.raises(FileNotFoundError):
        runner.run(spec, skill_dir)
