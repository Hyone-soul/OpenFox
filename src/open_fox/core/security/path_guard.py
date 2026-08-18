"""路径安全守卫。

将任意输入路径解析为绝对路径，校验其必须落在白名单根目录之内。
防止 LLM 通过 `..` 穿越或绝对路径访问框架外的文件。
"""

from __future__ import annotations

from pathlib import Path

from open_fox.core.exceptions import PathGuardViolation


class PathGuard:
    """路径白名单守卫。"""

    def __init__(self, allowed_roots: list[Path], base_dir: Path | None = None):
        # 统一解析为绝对路径，便于后续比较
        self._roots: list[Path] = [r.resolve() for r in allowed_roots]
        # 相对路径基准：默认 cwd，便于测试时注入临时目录
        self._base_dir = base_dir.resolve() if base_dir else Path.cwd()

    def is_allowed(self, path: Path) -> bool:
        """检查路径是否落在任一允许的根目录内。"""
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError):
            return False
        return any(self._is_inside(resolved, root) for root in self._roots)

    def resolve(self, path: str | Path) -> Path:
        """解析并校验路径，越界则抛 PathGuardViolation。

        支持相对路径（相对 base_dir）与绝对路径。
        """
        p = Path(path)
        if not p.is_absolute():
            p = self._base_dir / p
        try:
            resolved = p.resolve()
        except (OSError, RuntimeError) as e:
            raise PathGuardViolation(str(path)) from e
        if not self.is_allowed(resolved):
            raise PathGuardViolation(str(path))
        return resolved

    @staticmethod
    def _is_inside(child: Path, parent: Path) -> bool:
        """判断 child 是否在 parent 之内。"""
        try:
            child.relative_to(parent)
            return True
        except ValueError:
            return False