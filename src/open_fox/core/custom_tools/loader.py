"""扫描 ./tools/*.py 加载 @tool 装饰函数，支持 watchdog 热加载。"""
from __future__ import annotations

import importlib.util
import inspect as _inspect
import logging
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from open_fox.core.registry import Registry
from open_fox.tools.decorator import _TOOL_INSTANCE, FunctionTool

logger = logging.getLogger(__name__)


class CustomToolsLoader:
    def __init__(self, tools_dir: Path, registry: Registry,
                 on_change: Callable | None = None):
        self._dir = Path(tools_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._registry = registry
        self._on_change = on_change or (lambda _: None)
        self._loaded: dict[str, FunctionTool] = {}
        self._observer: Observer | None = None

    def rescan(self) -> list[dict]:
        errors: list[dict] = []
        new_loaded: dict[str, FunctionTool] = {}
        for f in sorted(self._dir.iterdir()):
            if not f.name.endswith(".py"):
                continue
            if f.name == "__init__.py" or f.name.startswith("_"):
                continue
            try:
                ft = self._import_file(f)
                if ft is not None:
                    new_loaded[ft.name] = ft
            except Exception as e:  # noqa: BLE001
                logger.warning("自定义工具 %s 加载失败：%s", f.name, e)
                errors.append({"source": str(f), "error": str(e)})

        # diff 注册：保留 builtin 与当前仍存在的自定义
        for name in list(self._registry._tools):
            if name in new_loaded:
                continue
            if name in self._loaded:
                self._registry.unregister_tool(name)
        for name, ft in new_loaded.items():
            if self._loaded.get(name) is not ft:
                self._registry.register_tool(ft)
        self._loaded = new_loaded
        self._on_change(self._loaded)
        return errors

    def _import_file(self, path: Path) -> FunctionTool | None:
        spec = importlib.util.spec_from_file_location(
            f"_openfox_tools_{path.stem}", path,
        )
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for _, obj in _inspect.getmembers(module):
            ft = getattr(obj, _TOOL_INSTANCE, None)
            if isinstance(ft, FunctionTool):
                return ft
        return None

    def start(self) -> None:
        self.rescan()
        handler = _Handler(self)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._dir), recursive=False)
        self._observer.start()
        logger.info("自定义工具热加载监听已启动：%s", self._dir)

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None

    def all(self) -> dict[str, FunctionTool]:
        return dict(self._loaded)


class _Handler(FileSystemEventHandler):
    def __init__(self, loader: CustomToolsLoader):
        self._loader = loader

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if event.src_path.endswith(".py"):
            self._loader.rescan()