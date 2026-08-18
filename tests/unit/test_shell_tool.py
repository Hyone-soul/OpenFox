"""Shell 工具测试。"""
import sys
from pathlib import Path

import pytest

from open_fox.core.tools.shell_tool import RunShellTool


@pytest.fixture
def tool(tmp_path):
    return RunShellTool(cwd=tmp_path, default_timeout=10)


def test_run_echo(tool):
    r = tool.execute(cmd=f"{sys.executable} -c \"print('hi')\"")
    assert r.success is True
    assert "hi" in r.content


def test_run_timeout(tool):
    r = tool.execute(cmd=f"{sys.executable} -c \"import time; time.sleep(5)\"", timeout=1)
    assert r.success is False
    assert "超时" in r.error or "Timeout" in r.error or "timeout" in r.error


def test_nonzero_exit(tool):
    r = tool.execute(cmd=f"{sys.executable} -c \"import sys; sys.exit(2)\"")
    assert r.success is False
    assert "exit" in r.error.lower() or "退出" in r.error


def test_dangerous_command_blocked(tool):
    r = tool.execute(cmd="rm -rf /")
    assert r.success is False
    assert "危险" in r.error or "danger" in r.error.lower()
