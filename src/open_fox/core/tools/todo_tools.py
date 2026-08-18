"""任务管理工具：todo_read / todo_write。

为 Agent 提供任务规划和追踪能力。任务数据存储在白名单目录的
.openfox_todos.json 文件中，按会话隔离。
"""

from __future__ import annotations

import json
from pathlib import Path

from open_fox.core.tools.base import BaseTool, ToolResult

_TODO_FILENAME = ".openfox_todos.json"

_VALID_STATUSES = {"pending", "in_progress", "completed", "cancelled"}
_VALID_PRIORITIES = {"high", "medium", "low"}


def _todo_path(todo_dir: Path) -> Path:
    """获取任务文件路径（指定目录下）。"""
    return todo_dir / _TODO_FILENAME


def _load_todos(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_todos(path: Path, todos: list[dict]) -> None:
    path.write_text(json.dumps(todos, ensure_ascii=False, indent=2), encoding="utf-8")


class TodoReadTool(BaseTool):
    """读取任务列表。"""

    name = "todo_read"
    description = "读取当前任务列表，用于规划和追踪工作进度。"
    parameters = {
        "type": "object",
        "properties": {
            "filter": {
                "type": "string",
                "description": "按状态过滤：pending / in_progress / completed / all，默认 all",
            },
        },
        "required": [],
    }

    def __init__(self, todo_dir: Path):
        self._todo_dir = todo_dir

    def execute(self, **kwargs) -> ToolResult:
        path = _todo_path(self._todo_dir)
        todos = _load_todos(path)
        filter_status = kwargs.get("filter", "all")

        if filter_status != "all":
            todos = [t for t in todos if t.get("status") == filter_status]

        if not todos:
            return ToolResult(success=True, content="（无任务）")

        lines = []
        for i, t in enumerate(todos, 1):
            status = t.get("status", "pending")
            priority = t.get("priority", "medium")
            content = t.get("content", "")
            # 状态图标
            icon = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]", "cancelled": "[-]"}.get(status, "[ ]")
            lines.append(f"  {i}. {icon} ({priority}) {content}")

        return ToolResult(success=True, content="\n".join(lines))


class TodoWriteTool(BaseTool):
    """写入/更新任务列表。"""

    name = "todo_write"
    description = "创建、更新或删除任务。支持设置任务内容、优先级和状态。"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "操作类型：add（添加）/ update（更新）/ remove（删除）/ clear（清空已完成）",
                "enum": ["add", "update", "remove", "clear"],
            },
            "content": {"type": "string", "description": "任务内容（add 时必填）"},
            "index": {"type": "integer", "description": "任务序号（update/remove 时必填，1-based）"},
            "status": {
                "type": "string",
                "description": "状态：pending / in_progress / completed / cancelled",
                "enum": ["pending", "in_progress", "completed", "cancelled"],
            },
            "priority": {
                "type": "string",
                "description": "优先级：high / medium / low",
                "enum": ["high", "medium", "low"],
            },
        },
        "required": ["action"],
    }

    def __init__(self, todo_dir: Path):
        self._todo_dir = todo_dir

    def execute(self, **kwargs) -> ToolResult:
        path = _todo_path(self._todo_dir)

        action = kwargs["action"]
        todos = _load_todos(path)

        if action == "add":
            content = kwargs.get("content", "").strip()
            if not content:
                return ToolResult(success=False, error="任务内容不能为空")
            status = kwargs.get("status", "pending")
            priority = kwargs.get("priority", "medium")
            if status not in _VALID_STATUSES:
                status = "pending"
            if priority not in _VALID_PRIORITIES:
                priority = "medium"
            todos.append({"content": content, "status": status, "priority": priority})
            _save_todos(path, todos)
            return ToolResult(success=True, content=f"已添加任务：{content}")

        elif action == "update":
            idx = kwargs.get("index", 0)
            if idx < 1 or idx > len(todos):
                return ToolResult(success=False, error=f"无效序号：{idx}（共 {len(todos)} 条）")
            t = todos[idx - 1]
            if "content" in kwargs and kwargs["content"]:
                t["content"] = kwargs["content"]
            if "status" in kwargs:
                if kwargs["status"] in _VALID_STATUSES:
                    t["status"] = kwargs["status"]
            if "priority" in kwargs:
                if kwargs["priority"] in _VALID_PRIORITIES:
                    t["priority"] = kwargs["priority"]
            _save_todos(path, todos)
            return ToolResult(success=True, content=f"已更新任务 #{idx}")

        elif action == "remove":
            idx = kwargs.get("index", 0)
            if idx < 1 or idx > len(todos):
                return ToolResult(success=False, error=f"无效序号：{idx}（共 {len(todos)} 条）")
            removed = todos.pop(idx - 1)
            _save_todos(path, todos)
            return ToolResult(success=True, content=f"已删除任务：{removed.get('content', '')}")

        elif action == "clear":
            before = len(todos)
            todos = [t for t in todos if t.get("status") != "completed"]
            _save_todos(path, todos)
            return ToolResult(success=True, content=f"已清理 {before - len(todos)} 条已完成任务")

        else:
            return ToolResult(success=False, error=f"未知操作：{action}")
