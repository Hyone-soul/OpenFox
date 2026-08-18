"""代码理解工具：ast_parse。

解析 Python 文件的 AST，提取函数、类、全局变量等结构信息。
不依赖外部命令，纯标准库 ast 模块实现。
"""

from __future__ import annotations

import ast
from pathlib import Path

from open_fox.core.exceptions import PathGuardViolation
from open_fox.core.security.path_guard import PathGuard
from open_fox.core.tools.base import BaseTool, ToolResult


class AstParseTool(BaseTool):
    """解析 Python 文件的抽象语法树，提取代码结构。"""

    name = "ast_parse"
    description = "解析 Python 文件的 AST 结构，提取函数、类、方法、全局变量定义及其行号。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Python 文件路径"},
            "include_body": {"type": "boolean", "description": "是否包含函数/类的 docstring，默认 true"},
        },
        "required": ["path"],
    }

    def __init__(self, path_guard: PathGuard):
        self._guard = path_guard

    def execute(self, **kwargs) -> ToolResult:
        try:
            p = self._guard.resolve(kwargs["path"])
        except PathGuardViolation as e:
            return ToolResult(success=False, error=str(e))

        if not p.exists():
            return ToolResult(success=False, error=f"文件不存在：{p}")
        if p.suffix != ".py":
            return ToolResult(success=False, error="仅支持 .py 文件")

        include_body = kwargs.get("include_body", True)

        try:
            source = p.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(p))
        except SyntaxError as e:
            return ToolResult(success=False, error=f"语法错误：{e}")
        except OSError as e:
            return ToolResult(success=False, error=f"读取失败：{e}")

        lines = []
        _walk_ast(tree, lines, indent=0, include_body=include_body)

        if not lines:
            return ToolResult(success=True, content="（空文件或无定义）")
        return ToolResult(success=True, content="\n".join(lines))


def _walk_ast(node, lines: list[str], indent: int, include_body: bool):
    prefix = "  " * indent
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef) or isinstance(child, ast.AsyncFunctionDef):
            args = [a.arg for a in child.args.args]
            decorators = ""
            if child.decorator_list:
                dec_names = []
                for d in child.decorator_list:
                    if isinstance(d, ast.Name):
                        dec_names.append(f"@{d.id}")
                    elif isinstance(d, ast.Attribute):
                        dec_names.append(f"@{ast.dump(d)}")
                    else:
                        dec_names.append("@...")
                decorators = " ".join(dec_names) + " "
            line = f"{prefix}{decorators}def {child.name}({', '.join(args)})  [L{child.lineno}]"
            if include_body and (docstring := ast.get_docstring(child)):
                line += f"\n{prefix}  \"{docstring[:80]}{'...' if len(docstring) > 80 else ''}\""
            lines.append(line)
            _walk_ast(child, lines, indent + 1, include_body=include_body)

        elif isinstance(child, ast.ClassDef):
            bases = [ast.dump(b) if not isinstance(b, ast.Name) else b.id for b in child.bases]
            line = f"{prefix}class {child.name}({', '.join(bases)})  [L{child.lineno}]"
            if include_body and (docstring := ast.get_docstring(child)):
                line += f"\n{prefix}  \"{docstring[:80]}{'...' if len(docstring) > 80 else ''}\""
            lines.append(line)
            _walk_ast(child, lines, indent + 1, include_body=include_body)

        elif isinstance(child, ast.Assign):
            # 全局变量赋值
            for target in child.targets:
                if isinstance(target, ast.Name):
                    lines.append(f"{prefix}VAR {target.id}  [L{child.lineno}]")
