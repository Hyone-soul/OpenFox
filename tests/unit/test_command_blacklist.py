"""危险命令黑名单测试。"""
import pytest

from open_fox.core.exceptions import DangerousCommand
from open_fox.core.security.command_blacklist import check_command


@pytest.mark.parametrize("cmd", [
    "rm -rf /",
    "rm -fr /etc",
    "mkfs.ext4 /dev/sda",
    "shutdown -h now",
    "dd if=/dev/zero of=/dev/sda",
    ":(){:|:&};:",  # fork bomb
])
def test_dangerous_command_blocked(cmd):
    with pytest.raises(DangerousCommand):
        check_command(cmd)


@pytest.mark.parametrize("cmd", [
    "ls -la",
    "cat file.txt",
    "echo hello",
    "python script.py",
    "git status",
])
def test_safe_command_allowed(cmd):
    check_command(cmd)  # 不抛即通过