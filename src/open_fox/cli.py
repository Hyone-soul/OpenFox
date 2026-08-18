"""CLI 入口：交互式 REPL（Claude Code 风格）。

特性：
- prompt_toolkit：多行输入、历史、Emacs 键位、自动补全
- Rich：Markdown 渲染、彩色面板、spinner
- 状态栏：当前模型、token 估算、Skill 数
- 斜杠命令：/model /skills /tools /help /clear /exit /quit
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import ConditionalCompleter, WordCompleter
from prompt_toolkit.filters import Condition
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.markup import escape
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax

from open_fox.config import load_config
from open_fox.auth import UserStore
from open_fox.core.adapters.openai_chat import OpenAIChatAdapter
from open_fox.core.agent_loop import AgentLoop
from open_fox.core.custom_tools.loader import CustomToolsLoader
from open_fox.core.custom_tools.reload import reload_all, _is_builtin_tool
from open_fox.core.evolution import build_evolution
from open_fox.core.evolution.manager import SkillValidationError
from open_fox.core.mcp.client import McpClient
from open_fox.core.mcp.config_loader import load_mcp_configs
from open_fox.core.memory.extractor import MemoryExtractionTask
from open_fox.core.memory.manager import MemoryManager, MemoryManagerPool
from open_fox.core.memory.tools import register_memory_tools
from open_fox.core.registry import Registry
from open_fox.core.scripts.runner import ScriptRunner
from open_fox.core.security.path_guard import PathGuard
from open_fox.core.session import Session
from open_fox.core.skills.loader import SkillLoader
from open_fox.core.storage.memory import MemoryStorage
from open_fox.core.tools.file_tools import (
    EditFileTool,
    ReadFileTool,
    WriteFileTool,
)
from open_fox.core.tools.shell_tool import RunShellTool


# ---- 颜色与样式 ----
PURPLE = "#a78bfa"
BLUE = "#60a5fa"
GREEN = "#34d399"
YELLOW = "#fbbf24"
RED = "#f87171"
GRAY = "#6b7280"
CYAN = "#22d3ee"

# ---- 全局状态 ----
_cli_username: str = "Ciel"   # 当前 CLI 登录用户名

PROMPTStyle = Style.from_dict({
    "prompt": f"{PURPLE} bold",
    "model": f"{BLUE}",
    "muted": f"{GRAY}",
    # 补全菜单样式
    "completion-menu": f"bg:{PURPLE} fg:white bold",
    "completion-menu.completion": "bg:#1e1e2e fg:#a78bfa",
    "completion-menu.completion.current": "bg:#a78bfa fg:#ffffff bold",
    "completion-menu.meta.completion": "bg:#1e1e2e fg:#6b7280",
    "completion-menu.meta.completion.current": "bg:#a78bfa fg:#f5f5f5",
    "completion-menu.multi-column-meta": "bg:#1e1e2e fg:#6b7280",
    "scrollbar.background": "bg:#313244",
    "scrollbar.button": "bg:#a78bfa",
})


def render_status_bar(console: Console, model: str, skills_count: int,
                      tools_count: int, mcp_count: int, username: str = "") -> None:
    """打印一行紧凑的状态栏（模拟 Claude Code 底部状态）。"""
    if not username:
        username = _cli_username
    bar = Table.grid(expand=False, padding=(0, 1))
    bar.add_column(justify="left", style=PURPLE)
    bar.add_column(justify="left", style=BLUE)
    bar.add_column(justify="left", style=GREEN)
    bar.add_column(justify="left", style=YELLOW)
    bar.add_column(justify="left", style=CYAN)
    bar.add_row(
        f"✦ {model}",
        f"⚒ {tools_count} tools",
        f"◆ {skills_count} skills",
        f"⌬ {mcp_count} mcp",
        f"👤 {username}",
    )
    console.print(bar)


def _build_compressor(cfg, adapter):
    """根据配置构建上下文压缩器（若禁用则返回 None）。"""
    from open_fox.core.context.context_compressor import (
        CompressionConfig,
        ContextCompressor,
    )

    if not cfg.compression.enabled:
        return None

    compress_config = CompressionConfig(
        enabled=True,
        threshold=cfg.compression.threshold,
        target_ratio=cfg.compression.target_ratio,
        protect_first_n=cfg.compression.protect_first_n,
        protect_last_n=cfg.compression.protect_last_n,
        max_attempts=cfg.compression.max_attempts,
        anti_thrash_threshold=cfg.compression.anti_thrash_threshold,
        cooldown_seconds=cfg.compression.cooldown_seconds,
        context_window=cfg.compression.context_window,
    )

    # 包装 adapter.chat 为 compressor 所需的签名：
    # async (messages, tools) -> str
    async def llm_chat_fn(messages: list[dict], tools: list[dict]) -> str:
        response = await adapter.chat(messages, tools=tools or None, stream=False)
        return response.content or ""

    return ContextCompressor(config=compress_config, llm_chat_fn=llm_chat_fn)


def build_app(config_path: str | None = None, username: str = "Ciel"):
    cfg = load_config(config_path)
    cfg.skills_dir.mkdir(parents=True, exist_ok=True)
    cfg.workspace_dir.mkdir(parents=True, exist_ok=True)

    guard = PathGuard(allowed_roots=[cfg.skills_dir, cfg.workspace_dir])
    adapter = OpenAIChatAdapter(models=cfg.models)
    if cfg.active_model:
        adapter.set_active(cfg.active_model)

    registry = Registry()
    registry.register_tool(ReadFileTool(path_guard=guard))
    registry.register_tool(WriteFileTool(path_guard=guard))
    registry.register_tool(EditFileTool(path_guard=guard))
    registry.register_tool(RunShellTool(cwd=cfg.skills_dir.parent,
                                        default_timeout=cfg.script_default_timeout))

    loader = SkillLoader(skills_dir=cfg.skills_dir)
    loader.start()

    mcp = McpClient([])

    # 全局记忆：按用户名隔离，CLI 使用 data/memory/<username>/ 目录
    memory_path = Path(f"./data/memory/{username}")
    memory_path.mkdir(parents=True, exist_ok=True)
    memory_manager = MemoryManager(memory_path=memory_path / "OPENFOX.md")
    memory_manager.load_sync()
    # CLI 不需要池，但工具需要 MemoryManagerPool，构造一个单用户池
    memory_pool = MemoryManagerPool(base_dir="./data/memory")
    register_memory_tools(registry, memory_pool)
    # 保留单返回值兼容性；REPL 从 manager 取回同一个池。
    memory_manager.pool = memory_pool

    # Skill 进化：构造组件 + 加载持久化（build_app 是同步函数）
    evo_manager, evo_tracker, _, evo_queue, evo_task = build_evolution(
        cfg, adapter, cfg.skills_dir)
    evo_manager.load_sync()
    evo_tracker.load_sync()
    evo_queue.load_sync()

    # 自定义工具热加载：监听 ./tools/ 下的 @tool 装饰函数
    custom_tools_loader = CustomToolsLoader(cfg.custom_tools_dir, registry)
    custom_tools_loader.start()

    return cfg, adapter, registry, loader, mcp, memory_manager, evo_task, custom_tools_loader


# ---- 登录 ----

def cli_login(console: Console, user_arg: str = "", no_color: bool = False) -> str:
    """CLI 登录流程：返回已验证的用户名。

    流程：
    1. --user 传入用户名 → 交互输入密码验证
    2. 未传 --user → 交互输入用户名 + 密码
    3. 用户不存在 → 询问是否注册
    4. 验证通过 → 返回 username
    """
    user_store = UserStore(data_dir="./data")

    # 确保默认用户 Ciel 存在
    if not user_store.get("Ciel"):
        user_store.create_user("Ciel", "123456", "Ciel")

    if user_arg:
        username = user_arg
    else:
        console.print()
        login_panel = Panel(
            Text.from_markup(
                f"[{PURPLE} bold]OpenFox 登录[/{PURPLE} bold]\n\n"
                f"默认用户: [{BLUE}]Ciel[/{BLUE}]  密码: [{BLUE}]123456[/{BLUE}]\n"
                f"输入用户名（回车使用默认 Ciel）："
            ),
            border_style=PURPLE,
            padding=(1, 2),
            expand=False,
        )
        console.print(login_panel)
        username = input("  用户名: ").strip() or "Ciel"

    # 检查用户是否存在
    if not user_store.get(username):
        console.print()
        register_choice = input(f"  用户 '{username}' 不存在，是否注册？(y/N): ").strip().lower()
        if register_choice != "y":
            console.print(f"[{RED}]登录取消[/{RED}]")
            raise SystemExit(0)
        # 注册流程
        password = input("  设置密码: ").strip()
        if len(password) < 6:
            console.print(f"[{RED}]密码长度不能少于 6 位[/{RED}]")
            raise SystemExit(1)
        display_name = input("  显示名称（回车跳过）: ").strip() or username
        user_store.create_user(username, password, display_name)
        console.print(f"[{GREEN}]注册成功！[/{GREEN}]")
    else:
        # 登录流程：输入密码
        password = input("  密码: ").strip()
        user = user_store.verify(username, password)
        if user is None:
            console.print(f"[{RED}]密码错误[/{RED}]")
            raise SystemExit(1)
        username = user.username  # 使用规范化的用户名

    console.print(f"[{GREEN}]欢迎，{username}！[/{GREEN}]")
    console.print()
    return username


# ---- 状态栏 ----
# render_status_bar 已在上面定义（含 cache_hit / reasoning 参数）


# ---- ASCII 艺术（OpenFox 吉祥物，取自项目根 ascii_art.txt）----


def render_welcome(console: Console, model: str, skills: dict,
                   builtin_tools: list, custom_tools: list,
                   mcp_tools: dict[str, list[dict]],
                   mcp_count: int) -> None:
    """启动时的欢迎横幅（信息面板）。

    三类工具分别展示：
    - builtin_tools: 内置工具 schemas list（read_file/write_file/edit_file/run_shell/memory_*）
    - custom_tools: 自定义 Python 工具 schemas list（@tool 装饰函数）
    - mcp_tools: dict[server_name -> [tool_schema, ...]]，按 server 分组
    """
    # ---- 信息面板 ----
    # 标题
    title = Text()
    title.append("⚡ ", style=YELLOW)
    title.append("OpenFox", style=f"bold {PURPLE}")
    title.append("  Framework", style=f"bold {BLUE}")
    title.append("\n", style=GRAY)
    title.append("Agent Skills 框架", style=GRAY)

    # 吉祥物 ASCII 小脸
    mascot = Text()
    mascot.append("\n", style=GRAY)
    mascot.append("   /\\ /\\\n", style=BLUE)
    mascot.append("  ( o.o )\n", style=YELLOW)
    mascot.append("   > ^ <", style=YELLOW)

    # 分隔线
    divider = Text("─" * 36, style=GRAY)

    # 统计行
    mcp_tool_total = sum(len(ts) for ts in mcp_tools.values())
    stats = Text()
    stats.append("👤 ", style=CYAN)
    stats.append(_cli_username, style=CYAN)
    stats.append("  ·  ", style=GRAY)
    stats.append("✦ ", style=PURPLE)
    stats.append(model, style=BLUE)
    stats.append("\n", style=GRAY)
    stats.append(f"⚒ {len(builtin_tools)}", style=BLUE)
    stats.append("  内置  ·  ", style=GRAY)
    stats.append(f"{len(custom_tools)}", style=YELLOW)
    stats.append(" 自定义  ·  ", style=GRAY)
    stats.append(f"{mcp_tool_total}", style=PURPLE)
    stats.append(" MCP(", style=GRAY)
    stats.append(f"{mcp_count}", style=PURPLE)
    stats.append(")  ·  ", style=GRAY)
    stats.append(f"◆ {len(skills)}", style=GREEN)
    stats.append(" skills", style=GRAY)

    # 命令提示
    def _cmd(key: str, desc: str) -> Text:
        t = Text()
        t.append(key, style=PURPLE)
        t.append("  ", style=GRAY)
        t.append(desc, style=GRAY)
        return t

    cmd_tbl = Table.grid(padding=(0, 3), expand=False)
    cmd_tbl.add_column(justify="left")
    cmd_tbl.add_column(justify="left")
    cmd_tbl.add_column(justify="left")
    cmd_tbl.add_column(justify="left")
    cmd_tbl.add_row(_cmd("/model", "切换模型"), _cmd("/skills", "Skill 列表"),
                    _cmd("/clear", "重置会话"), _cmd("/help", "帮助"))
    cmd_tbl.add_row(_cmd("/tools", "工具列表"), _cmd("/status", "状态"),
                    _cmd("/exit", "退出"), _cmd("/quit", "退出"))

    # 工具表格（三类垂直排列，各有自己的边框色 + emoji 前缀）
    def _tools_subtable(title_text: str, items: list, color: str) -> Table:
        tbl = Table(
            title=f"[{color}]{title_text}[/{color}]",
            border_style=color,
            show_header=True,
            expand=True,
        )
        tbl.add_column("名称", style=color, no_wrap=True, ratio=1)
        tbl.add_column("描述", style="white", ratio=3)
        for s in items:
            fn = s["function"]
            tbl.add_row(fn["name"], fn["description"])
        return tbl

    builtin_tbl = _tools_subtable("⚒ 内置工具 (built-in)", builtin_tools, BLUE)
    if custom_tools:
        custom_tbl = _tools_subtable("⚙️ 自定义工具 (./tools/*.py)", custom_tools, YELLOW)
    else:
        custom_tbl = Text("  ⚙️  自定义工具（./tools/*.py）：暂无", style=GRAY)

    # MCP 按 server 分组
    if mcp_tools:
        mcp_children = []
        for server_name, tool_schemas in sorted(mcp_tools.items()):
            mcp_children.append(Text(""))
            mcp_children.append(_tools_subtable(
                f"🛰 MCP · {server_name}  ({len(tool_schemas)} tools)",
                tool_schemas, PURPLE,
            ))
        mcp_section = Group(*mcp_children)
    else:
        mcp_section = Text("  🛰  MCP 工具（./mcps/*.yaml）：暂无", style=GRAY)

    # Skill 列表
    skills_tbl = Table(
        title="[green]已加载 Skill[/green]",
        border_style=GREEN,
        show_header=True,
        expand=True,
    )
    skills_tbl.add_column("名称", style=GREEN, no_wrap=True, ratio=1)
    skills_tbl.add_column("简介", style="white", ratio=3)
    for s in skills.values():
        summary = s.description.split("。", 1)[0].strip()
        if len(summary) > 60:
            summary = summary[:60] + "…"
        skills_tbl.add_row(f"/{s.name}", summary)

    # 右侧内容：标题 → 吉祥物 → 统计 → 命令 → 工具列表 → Skill 列表
    right_content = Group(
        title,
        mascot,
        Text(""),
        divider,
        Text(""),
        stats,
        Text(""),
        cmd_tbl,
        Text(""),
        builtin_tbl,
        Text(""),
        custom_tbl,
        mcp_section,
        Text(""),
        skills_tbl,
        Text(""),
        Text("type a message or /command to start", style=GRAY),
    )

    right_panel = Panel(
        right_content,
        border_style=PURPLE,
        padding=(1, 2),
        expand=False,
        title="[purple]⚡ OpenFox[/purple]",
        title_align="center",
    )

    console.print(right_panel)
    console.print()


def render_user_message(console: Console, text: str) -> None:
    console.print()
    console.print(Text("❯", style=f"bold {PURPLE}"), end=" ")
    console.print(Text(text, style="bold"))


def render_assistant_message(console: Console, content: str,
                             tool_calls: list | None = None) -> None:
    """渲染助手回复：优先用 Markdown，工具调用以面板列出。"""
    console.print()
    if tool_calls:
        # 工具调用面板
        tbl = Table.grid(padding=(0, 1))
        tbl.add_column(style=YELLOW)
        tbl.add_column(style=GRAY)
        for tc in tool_calls:
            tbl.add_row(
                f"⚙ {tc['name']}",
                _format_args(tc.get('args', {})),
            )
        console.print(Panel(tbl, border_style=YELLOW, title="[yellow]tool calls[/yellow]",
                             expand=False, padding=(0, 2)))

    if content:
        # Markdown 渲染
        console.print(Markdown(content, code_theme="monokai"))


def _format_args(args) -> Text:
    """格式化 tool args 用于面板展示。args 期望是 dict，但模型可能产出非 dict 字面量（数字、字符串等），需兜底。"""
    if not isinstance(args, dict):
        return Text(f"({args!r})", style=GRAY)
    if not args:
        return Text("()", style=GRAY)
    txt = Text()
    txt.append("(", style=GRAY)
    items = list(args.items())
    for i, (k, v) in enumerate(items):
        if i > 0:
            txt.append(", ", style=GRAY)
        txt.append(k, style=GRAY)
        txt.append("=", style=GRAY)
        txt.append(repr(v)[:60], style=BLUE)
    txt.append(")", style=GRAY)
    return txt


def render_error(console: Console, message: str) -> None:
    # 用 escape 转义 message 里的 [ ] 字符，避免 Rich markup 解析崩溃
    console.print(f"[{RED}]✗ 错误：{escape(message)}[/{RED}]")


def render_status(console: Console, message: str) -> None:
    console.print(f"[{GREEN}]✓ {escape(message)}[/{GREEN}]")


# ---- Agent 运行（spinner + 结构化输出）----

def _render_reasoning(console: Console, content: str) -> None:
    """渲染推理内容（dim 面板，截断过长内容）。"""
    if len(content) > 800:
        content = content[:800] + "\n  …(已截断)"
    console.print(Panel(
        Text(content.strip(), style="dim cyan"),
        border_style="dim",
        title="[dim cyan]💭 Thinking[/dim cyan]",
        title_align="left",
        padding=(0, 1),
        expand=False,
    ))
    console.print()


def _render_tool_trace(console: Console, trace: list[dict]) -> None:
    """渲染工具调用轨迹（含结果，紧凑两行格式）。"""
    for tc in trace:
        name = tc["name"]
        args = tc["args"]
        result = str(tc.get("result", ""))
        is_error = result.startswith("ERROR:")

        color = RED if is_error else YELLOW
        icon = "✗" if is_error else "⚙"

        # 第一行：工具调用
        line = Text()
        line.append(f"  {icon} ", style=color)
        line.append(name, style=color)
        line.append(_format_args(args))
        console.print(line)

        # 第二行：结果预览（截断到 200 字符）
        if result:
            preview = result[:200] + ("…" if len(result) > 200 else "")
            result_color = f"dim {RED}" if is_error else "dim"
            result_icon = "✗" if is_error else "→"
            console.print(Text(f"    {result_icon} {preview}", style=result_color))

    console.print()


async def run_agent_with_console(
    console: Console,
    adapter: OpenAIChatAdapter,
    registry: Registry,
    session: Session,
    script_runner: ScriptRunner,
    skills: dict,
    max_steps: int,
    user_input: str,
    memory_manager=None,
    extractor=None,
    evolution_task=None,
    compressor=None,
) -> str:
    """运行 Agent：spinner 思考指示 → 推理面板 → 工具轨迹 → Markdown 最终回复。

    输出结构：
    1. spinner（思考中… → 调用工具…）
    2. 💭 Thinking 面板（推理模型思考内容，dim cyan）
    3. ⚙/✗ 工具调用轨迹（含结果预览）
    4. Markdown 渲染的最终回复
    """
    from open_fox.core.adapters.base import (
        ChatChunk,
        UsageInfo,
    )

    accumulated_usage = UsageInfo()
    reasoning_parts: list[str] = []

    # spinner 状态指示器
    status = console.status(
        Text("✦ 思考中…", style=PURPLE),
        spinner="dots",
    )

    async def on_chunk(chunk: ChatChunk) -> None:
        # 收集推理内容
        if chunk.reasoning_delta:
            reasoning_parts.append(chunk.reasoning_delta)
        # 检测工具调用，更新 spinner 文本
        if chunk.tool_call_delta and chunk.tool_call_delta.name:
            tool_name = chunk.tool_call_delta.name
            short = tool_name.split("__")[-1] if "__" in tool_name else tool_name
            status.update(Text(f"⚙ 调用 {short}…", style=YELLOW))

    loop = AgentLoop(
        adapter=adapter, registry=registry, session=session,
        script_runner=script_runner, skills=skills,
        max_steps=max_steps,
        on_chunk=on_chunk,
        memory_manager=memory_manager,
        compressor=compressor,
    )

    status.start()
    try:
        final_response = await loop.run(user_input)
    except Exception as e:
        status.stop()
        render_error(console, str(e))
        return f"错误：{e}", None
    status.stop()

    console.print()

    # 1. 推理内容（如果有）
    reasoning_content = "".join(reasoning_parts).strip()
    if reasoning_content:
        _render_reasoning(console, reasoning_content)

    # 2. 工具调用轨迹（含结果）
    if loop.tool_trace:
        _render_tool_trace(console, loop.tool_trace)

    # 3. 最终回复（Markdown 渲染）
    if final_response:
        console.print(Markdown(final_response, code_theme="monokai"))

    console.print()

    # 隐式记忆抽取：AgentLoop.run() 完成后 fire-and-forget 通知（内部 _should_extract 过滤）
    if extractor is not None:
        await extractor.notify(session.get_messages(), bool(loop.tool_trace), username=_cli_username)

    # Skill 进化：AgentLoop 每轮完成后 fire-and-forget 通知
    if evolution_task is not None:
        await evolution_task.notify("default", session.get_messages(), loop.tool_trace)

    return final_response, accumulated_usage


async def _run_skill_activation(
    console, adapter, registry, session, script_runner, loader,
    max_steps: int, skill_name: str, question: str,
    memory_manager=None, extractor=None, compressor=None,
) -> None:
    """手动激活 skill（/skill名）：读 SKILL.md 全文注入 session，再处理附带问题。"""
    skill = loader.all().get(skill_name)
    if skill is None:
        render_error(console, f"未找到 Skill：{skill_name}")
        return
    # 读取 SKILL.md 全文（含 frontmatter 与正文），注入 session 供模型使用
    skill_md_path = skill.source_dir / "SKILL.md"
    try:
        skill_md = skill_md_path.read_text(encoding="utf-8")
    except OSError as e:
        render_error(console, f"读取 {skill_name}/SKILL.md 失败：{e}")
        return

    # 把 skill 全文作为 system 上下文注入，让后续对话带上完整指令（渐进披露 L2 激活）
    session.add_raw({
        "role": "system",
        "content": f"用户手动激活了 Skill「{skill_name}」。以下为 SKILL.md 全文，请按其工作流执行：\n\n{skill_md}",
    })
    render_status(console, f"已激活 Skill：{skill_name}")

    prompt = question.strip() if question else f"请使用 {skill_name} 技能：{skill.description}"
    await run_agent_with_console(
        console, adapter, registry, session, script_runner,
        loader.all(), max_steps, prompt,
        memory_manager=memory_manager,
        extractor=extractor,
        compressor=compressor,
    )


# ---- 主 REPL ----
async def repl(cfg, adapter, registry, loader, mcp, memory_manager,
              custom_tools_loader, *,
              username: str = "Ciel",
              show_logo: bool = True, no_color: bool = False,
              evolution_task=None) -> None:
    global _cli_username
    _cli_username = username
    memory_pool = getattr(memory_manager, "pool", MemoryManagerPool(base_dir="./data/memory"))
    # 启动时从 cfg.mcps_dir 加载 MCP 配置（与 server.py lifespan 一致）
    new_configs, _ = load_mcp_configs(cfg.mcps_dir)
    mcp._configs = new_configs
    await mcp.start_all()
    for tool in await mcp.get_tools():
        registry.register_mcp_tool(tool)

    session = Session(session_id="default", storage=MemoryStorage(),
                      active_model=adapter.active)
    script_runner = ScriptRunner()

    console = Console(no_color=no_color, force_terminal=not no_color)

    # 隐式记忆抽取后台任务：AgentLoop 每轮完成后 fire-and-forget 通知（不会拖慢主对话）
    extractor = MemoryExtractionTask(memory_pool, adapter)
    await extractor.start()

    # Skill 进化后台任务：AgentLoop 每轮完成后 fire-and-forget 通知
    if evolution_task is not None:
        await evolution_task.start()

    # 上下文压缩器
    compressor = _build_compressor(cfg, adapter)

    # 欢迎界面（可用 --no-logo 关闭）
    if show_logo:
        # 三类工具分类：内置 / 自定义 / MCP
        builtin_tools: list = []
        custom_tools: list = []
        for name, t in registry._tools.items():
            schema = t.to_schema()
            if _is_builtin_tool(name):
                builtin_tools.append(schema)
            else:
                custom_tools.append(schema)
        # MCP 按 server 分组（key 形如 "<server>__<tool>"）
        mcp_tools_grouped: dict[str, list] = {}
        for name, a in registry._mcp_tools.items():
            server = a._server_name
            mcp_tools_grouped.setdefault(server, []).append(a.to_schema())

        render_welcome(
            console,
            model=adapter.active,
            skills=loader.all(),
            builtin_tools=builtin_tools,
            custom_tools=custom_tools,
            mcp_tools=mcp_tools_grouped,
            mcp_count=len([c for c in mcp._configs if c.enabled]),
        )

    # 检测终端类型，决定用 prompt_toolkit 还是 input() fallback
    use_prompt_toolkit = _can_use_prompt_toolkit()

    try:
        if use_prompt_toolkit:
            await _repl_with_prompt_toolkit(
                console, cfg, adapter, registry, loader, mcp, session, script_runner,
                memory_manager, extractor, evolution_task, custom_tools_loader,
                compressor=compressor,
            )
        else:
            console.print(
                f"  [{YELLOW}]⚠ 当前终端不支持 prompt_toolkit（Git Bash 等），"
                f"回退为基础 input()[/]"
            )
            await _repl_with_basic_input(
                console, cfg, adapter, registry, loader, mcp, session, script_runner,
                memory_manager, extractor, evolution_task, custom_tools_loader,
                compressor=compressor,
            )
    finally:
        await extractor.stop()
        if evolution_task is not None:
            await evolution_task.stop()

    await mcp.stop_all()


def _can_use_prompt_toolkit() -> bool:
    """检测 prompt_toolkit 是否可用。stdout 非 TTY（重定向）时不用。"""
    if not sys.stdout.isatty():
        return False
    try:
        import prompt_toolkit  # noqa: F401
        return True
    except Exception:
        return False


async def _repl_with_basic_input(
    console, cfg, adapter, registry, loader, mcp, session, script_runner,
    memory_manager, extractor=None, evolution_task=None,
    custom_tools_loader=None, compressor=None,
) -> None:
    """降级方案：使用 input()。"""
    while True:
        try:
            # 状态栏
            mcp_count = len([c for c in mcp._configs if c.enabled])
            render_status_bar(
                console, adapter.active, len(loader.all()),
                len(registry.list_tool_schemas()),
                mcp_count,
            )

            # 待确认面板提示
            if evolution_task is not None and evolution_task.pending_count() > 0:
                render_pending_hint(console, evolution_task)

            user_input = input("❯ ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print(f"\n[{GRAY}]再见。[/]")
            break

        if not user_input:
            continue
        if user_input == "/reload":
            await _handle_reload_command(
                console, registry, custom_tools_loader, mcp, cfg.mcps_dir,
            )
            continue
        if user_input.startswith("/"):
            handled = _handle_command(console, user_input, adapter, registry,
                                     loader, session, evolution_task)
            if handled == "QUIT":
                break
            if isinstance(handled, tuple):
                if handled[0] == "SKILL":
                    _, skill_name, arg = handled
                    await _run_skill_activation(
                        console, adapter, registry, session, script_runner,
                        loader, cfg.max_agent_steps, skill_name, arg,
                        memory_manager, extractor, compressor=compressor,
                    )
                elif handled[0] == "EVO":
                    _, sub, arg = handled
                    await _run_skill_evolve(console, evolution_task, loader, sub, arg)
                continue
            continue

        await run_agent_with_console(
            console, adapter, registry, session, script_runner,
            loader.all(), cfg.max_agent_steps, user_input,
            memory_manager=memory_manager,
            extractor=extractor,
            evolution_task=evolution_task,
            compressor=compressor,
        )


async def _repl_with_prompt_toolkit(
    console, cfg, adapter, registry, loader, mcp, session, script_runner,
    memory_manager, extractor=None, evolution_task=None,
    custom_tools_loader=None, compressor=None,
) -> None:
    """主方案：prompt_toolkit + Rich。"""

    # prompt_toolkit session（持久化历史）
    history_file = Path.home() / ".openfox_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    slash_commands = ["/model", "/skills", "/tools", "/help", "/clear", "/quit", "/exit", "/status", "/context", "/skill-evolve", "/reload"]
    # 补全列表 = 斜杠命令 + /<skill名>（手动激活 skill）
    completion_words = slash_commands + [f"/{name}" for name in loader.all()]
    base_completer = WordCompleter(completion_words, ignore_case=True)
    # 仅当输入以 / 开头时才弹出补全（避免输入空格/普通文字也弹）
    def _only_slash() -> bool:
        from prompt_toolkit.application import get_app
        try:
            text = get_app().current_buffer.text
        except Exception:
            return False
        return text.lstrip().startswith("/")
    completer = ConditionalCompleter(
        base_completer,
        filter=Condition(_only_slash),
    )

    # Tab 键绑定：按 Tab 打开补全菜单并自动输入当前选中项
    kb = KeyBindings()

    @kb.add("tab")
    def _tab(event):
        buf = event.current_buffer
        if buf.complete_state and buf.complete_state.current_completion is not None:
            # 已有补全选中项 → 应用（自动输入）
            buf.apply_completion(buf.complete_state.current_completion)
        else:
            # 还没有补全 → 打开菜单但不预选（避免误填，用方向键选 → Enter 确认）
            buf.start_completion(select_first=False)

    @kb.add("s-tab")
    def _s_tab(event):
        buf = event.current_buffer
        buf.complete_previous()

    prompt_session: PromptSession = PromptSession(
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory(),
        completer=completer,
        complete_style=CompleteStyle.MULTI_COLUMN,
        key_bindings=kb,
        complete_while_typing=True,
    )

    while True:
        try:
            # 动态状态栏（使用进程级累计真实 usage）
            mcp_count = len([c for c in mcp._configs if c.enabled])
            render_status_bar(
                console, adapter.active, len(loader.all()),
                len(registry.list_tool_schemas()),
                mcp_count,
            )

            # 待确认面板提示
            if evolution_task is not None and evolution_task.pending_count() > 0:
                render_pending_hint(console, evolution_task)

            # 紫色 prompt（带 ❯，basic 模式由 input() 提供，prompt_toolkit 模式由样式提供）
            # 用 prompt_async()：我们已在 asyncio 事件循环内，prompt() 内部 asyncio.run() 会冲突
            user_input = (await prompt_session.prompt_async(
                [("class:prompt", "❯ ")],
                style=PROMPTStyle,
            )).strip()
        except (EOFError, KeyboardInterrupt):
            console.print(f"\n[{GRAY}]再见。[/]")
            break

        if not user_input:
            continue

        # /reload：重扫 ./tools/ 与 ./mcps/（独立分支，避免与 _handle_command 误处理）
        if user_input == "/reload":
            await _handle_reload_command(
                console, registry, custom_tools_loader, mcp, cfg.mcps_dir,
            )
            continue

        # 斜杠命令
        if user_input.startswith("/"):
            handled = _handle_command(console, user_input, adapter, registry,
                                     loader, session, evolution_task)
            if handled == "QUIT":
                break
            if isinstance(handled, tuple):
                if handled[0] == "SKILL":
                    _, skill_name, arg = handled
                    await _run_skill_activation(
                        console, adapter, registry, session, script_runner,
                        loader, cfg.max_agent_steps, skill_name, arg,
                        memory_manager, extractor, compressor=compressor,
                    )
                elif handled[0] == "EVO":
                    _, sub, arg = handled
                    await _run_skill_evolve(console, evolution_task, loader, sub, arg)
                continue
            continue

        # 普通对话（用户输入已在 prompt 中显示，无需重复）
        await run_agent_with_console(
            console, adapter, registry, session, script_runner,
            loader.all(), cfg.max_agent_steps, user_input,
            memory_manager=memory_manager,
            extractor=extractor,
            evolution_task=evolution_task,
            compressor=compressor,
        )


# ---- 斜杠命令 ----
def parse_skill_evolve_args(cmd: str) -> tuple[str, str]:
    """解析 '/skill-evolve <sub> <arg>'。cmd 为去掉 '/skill-evolve' 后的部分。"""
    parts = cmd.split(maxsplit=1)
    sub = parts[0] if parts else ""
    arg = parts[1] if len(parts) > 1 else ""
    return sub, arg


async def _handle_reload_command(console, registry, custom_tools_loader,
                                 mcp, mcps_dir) -> None:
    """处理 /reload 命令：重扫 ./tools/ 与 ./mcps/，打印加载报告。"""
    if custom_tools_loader is None:
        render_error(console, "/reload 需要 custom_tools_loader")
        return
    report = await reload_all(registry, custom_tools_loader, mcp, mcps_dir)
    console.print(f"[{GREEN}]自定义工具：{len(report['custom_tools'])}[/]")
    console.print(f"[{GREEN}]MCP 服务：{len(report['mcp_servers'])} / 工具：{len(report['mcp_tools'])}[/]")
    if report["errors"]:
        console.print(f"[{RED}]加载失败 {len(report['errors'])} 个：[/]")
        for e in report["errors"]:
            console.print(f"  - {e['source']}: {e['error']}")


def render_pending_hint(console, evolution_task) -> None:
    """REPL 顶部待确认面板提示。"""
    n = evolution_task.pending_count()
    console.print(Panel(
        f"有 {n} 个待确认的 Skill 进化候选，输入 /skill-evolve list 查看。",
        border_style=YELLOW, expand=False,
    ))


async def _run_skill_evolve(console, evolution_task, loader, sub: str, arg: str) -> None:
    """异步处理 /skill-evolve 的写操作子命令。"""
    queue = evolution_task.queue
    manager = evolution_task.manager
    if sub == "confirm":
        if not arg:
            render_error(console, "用法：/skill-evolve confirm <id>")
            return
        item = queue.get(arg)
        if item is None or item.status != "pending":
            render_error(console, f"候选不存在或已处理：{arg}")
            return
        try:
            summary = await manager.apply_candidate(item.action, item.skill_name, item.content)
        except SkillValidationError as e:
            render_error(console, str(e))
            return
        await queue.mark_status(arg, "confirmed")
        # 写盘后定向 rescan，让下一轮 prompt 立即看到新 skill（不依赖 watchdog 延迟）
        loader.rescan()
        render_status(console, summary)
        return
    if sub == "reject":
        if not arg:
            render_error(console, "用法：/skill-evolve reject <id>")
            return
        item = queue.get(arg)
        if item is None or item.status != "pending":
            render_error(console, f"候选不存在或已处理：{arg}")
            return
        await queue.mark_status(arg, "rejected")
        render_status(console, f"已拒绝候选：{arg}")
        return
    if sub == "rollback":
        if not arg:
            render_error(console, "用法：/skill-evolve rollback <skill名>")
            return
        try:
            msg = await manager.rollback(arg)
            render_status(console, msg)
        except SkillValidationError as e:
            render_error(console, str(e))
        return
    render_error(console, "未知子命令（list | confirm | reject | rollback）")


def _handle_command(console: Console, cmd: str, adapter, registry, loader,
                    session, evolution_task=None) -> str | tuple | None:
    """处理斜杠命令。返回 None / "QUIT" / ("SKILL", skill_name, arg)。"""
    parts = cmd.split(maxsplit=1)
    name = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    if name in ("/quit", "/exit"):
        return "QUIT"

    if name == "/help":
        _print_help(console)
        return None

    if name == "/clear":
        # 清屏 + 重置会话上下文（避免历史错误信息污染后续对话）
        console.clear()
        session.set_messages([])
        render_status(console, "已清屏并重置会话上下文")
        return None

    if name == "/status":
        # 仅显示当前可用工具/Skill/MCP 数（token 实时在状态栏）
        render_status(console, (
            f"模型：{adapter.active} | "
            f"工具：{len(registry.list_tool_schemas())} | "
            f"Skill：{len(loader.all())} | "
            f"session messages：{len(session.get_messages())}"
        ))
        return None

    if name == "/model":
        if not arg:
            render_status(console, f"当前模型：{adapter.active}")
            render_available_models(console, adapter)
        else:
            try:
                adapter.set_active(arg)
                render_status(console, f"已切换到模型：{arg}")
            except ValueError as e:
                render_error(console, str(e))
        return None

    if name == "/skills":
        skills = loader.all()
        if not skills:
            render_status(console, "暂无已加载的 Skill")
        else:
            tbl = Table(title="[green]已加载 Skill[/green]", border_style=GREEN)
            tbl.add_column("名称", style=GREEN, no_wrap=True)
            tbl.add_column("描述", style="white")
            tbl.add_column("脚本", style=PURPLE)
            for s in skills.values():
                scripts = ", ".join(sc.id for sc in s.scripts) or "—"
                tbl.add_row(s.name, s.description, scripts)
            console.print(tbl)
        return None

    if name == "/tools":
        schemas = registry.list_tool_schemas()
        if not schemas:
            render_status(console, "暂无可用工具")
        else:
            tbl = Table(title="[blue]可用工具[/blue]", border_style=BLUE)
            tbl.add_column("名称", style=BLUE, no_wrap=True)
            tbl.add_column("描述", style="white")
            for s in schemas:
                fn = s["function"]
                tbl.add_row(fn["name"], fn["description"])
            console.print(tbl)
        return None

    if name == "/skill-evolve":
        if evolution_task is None:
            render_error(console, "Skill 进化未启用")
            return None
        if not arg:
            render_error(console, "用法：/skill-evolve list | confirm <id> | reject <id> | rollback <skill>")
            return None
        sub, rest = parse_skill_evolve_args(arg)
        if sub == "list":
            items = evolution_task.queue.list("pending")
            if not items:
                render_status(console, "暂无待确认的 Skill 进化候选")
                return None
            tbl = Table(title="[purple]待确认 Skill 进化候选[/purple]",
                        border_style=PURPLE)
            tbl.add_column("ID", style=PURPLE)
            tbl.add_column("操作", style=YELLOW)
            tbl.add_column("Skill", style=GREEN)
            tbl.add_column("原因", style="white")
            for it in items:
                tbl.add_row(it.id, it.action, it.skill_name, it.reason[:40])
            console.print(tbl)
            return None
        if sub in ("confirm", "reject", "rollback"):
            return ("EVO", sub, rest)
        render_error(console, "未知子命令（list | confirm | reject | rollback）")
        return None

    if name == "/context":
        _handle_context_command(console, session, registry, adapter)
        return None

    # /<skill名>：手动激活 skill。返回 (skill_name, 附带问题) 供 REPL 处理
    skill_name = name[1:]  # 去掉开头的 /
    skills = loader.all()
    if skill_name in skills:
        return ("SKILL", skill_name, arg)

    render_error(console, f"未知命令：{name}（输入 /help 查看可用命令）")
    return None


def _print_help(console: Console) -> None:
    tbl = Table(title="[purple]斜杠命令帮助[/purple]", border_style=PURPLE,
                show_header=True)
    tbl.add_column("命令", style=PURPLE, no_wrap=True)
    tbl.add_column("说明", style="white")
    help_items = [
        ("/model [name]", "查看或切换当前模型"),
        ("/skills", "列出所有已加载 Skill"),
        ("/<skill名> [问题]", "手动激活 Skill 并执行（如 /db-helper 谁的流量最少）"),
        ("/tools", "列出所有可用工具"),
        ("/status", "显示当前状态栏"),
        ("/clear", "清屏并重置会话上下文"),
        ("/reload", "重载 ./tools/ 自定义工具与 ./mcps/ MCP 配置"),
        ("/skill-evolve", "查看/确认/拒绝 Skill 进化候选（list | confirm <id> | reject <id> | rollback <skill>）"),
        ("/help", "显示此帮助"),
        ("/exit /quit", "退出 CLI"),
    ]
    for cmd, desc in help_items:
        tbl.add_row(cmd, desc)
    console.print(tbl)


def _handle_context_command(
    console: Console, session, registry, adapter
) -> None:
    """处理 /context 命令：显示当前上下文使用状态。"""
    from open_fox.core.context.context_breakdown import ContextBreakdown
    from open_fox.core.context.token_estimator import get_model_context_window

    model_name = adapter.active or ""
    context_window = get_model_context_window(model_name)

    # 构建即时快照
    snapshot = ContextBreakdown.capture(
        messages=session.chat_messages(),
        tool_schemas=registry.list_tool_schemas(),
        model_name=model_name,
    )

    # ── 概览面板 ──
    overview = Table.grid(padding=(0, 2))
    overview.add_column(style=PURPLE)
    overview.add_column(style="white")
    overview.add_row("模型", model_name)
    overview.add_row("上下文窗口", f"{context_window:,}")
    overview.add_row("有效预算", f"{snapshot.effective_budget:,}")
    overview.add_row("已使用", f"{snapshot.total_tokens:,} ({snapshot.usage_percent:.1f}%)")
    overview.add_row("剩余", f"{snapshot.remaining_tokens:,}")
    console.print(Panel(overview, title="[purple]上下文状态[/purple]", border_style=PURPLE, expand=False))

    # ── 分类明细表 ──
    tbl = Table(
        title="[purple]Token 分布[/purple]",
        border_style=PURPLE,
        show_header=True,
        expand=False,
    )
    tbl.add_column("类目", style=PURPLE, no_wrap=True)
    tbl.add_column("Token", style=BLUE, justify="right")
    tbl.add_column("占比", style=GREEN, justify="right")
    tbl.add_column("进度", style=YELLOW)

    for c in sorted(snapshot.categories, key=lambda x: x.tokens, reverse=True):
        pct = (c.tokens / snapshot.effective_budget * 100) if snapshot.effective_budget > 0 else 0
        bar_len = min(20, max(0, round(pct / 5)))
        bar = "█" * bar_len + "░" * (20 - bar_len)
        if c.tokens > 0:
            tbl.add_row(c.category.value, f"{c.tokens:,}", f"{pct:.1f}%", bar)
    console.print(tbl)

    # ── 最近压缩结果（如果有）──
    # 注意：此函数是同步的，无法直接拿到 AgentLoop 实例的 last_compression_result
    # 但用户可以在 /context 输出中看到压缩配置信息
    console.print(f"[{GRAY}]提示：压缩会在上下文超过 {50:.0%} 预算时自动触发[/]")


def render_available_models(console: Console, adapter: OpenAIChatAdapter) -> None:
    """列出可用模型。"""
    models = adapter.list_models()
    if not models:
        return
    txt = Text()
    txt.append("可用：", style=GRAY)
    for i, m in enumerate(models):
        marker = "●" if m == adapter.active else "○"
        style = PURPLE if m == adapter.active else GRAY
        if i > 0:
            txt.append("  ")
        txt.append(f"{marker} {m}", style=style)
    console.print(txt)


# ---- 入口 ----
def main() -> None:
    parser = argparse.ArgumentParser(description="OpenFox 框架 CLI")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--user", default="", dest="user", help="登录用户名（省略则交互输入）")
    parser.add_argument("--no-logo", action="store_true", help="关闭 ASCII 欢迎 logo")
    parser.add_argument("--no-color", action="store_true", help="关闭颜色输出（脚本/CI 友好）")
    args = parser.parse_args()

    # --no-color：通过环境变量通知 Rich 与所有 Rich-aware 库
    if args.no_color:
        import os
        os.environ["NO_COLOR"] = "1"          # 通用标准
        os.environ["FORCE_NO_COLOR"] = "1"
        os.environ["TERM"] = "dumb"            # Rich fallback

    # CLI 自身的日志降级（除非 DEBUG）
    import os
    log_level = logging.DEBUG if os.environ.get("AGENT_SKILLS_DEBUG") else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # 登录流程（在 build_app 之前，因为 build_app 依赖用户名初始化记忆）
    console = Console(no_color=args.no_color, force_terminal=not args.no_color)
    username = cli_login(console, user_arg=args.user, no_color=args.no_color)

    global _cli_username
    _cli_username = username

    cfg, adapter, registry, loader, mcp, memory_manager, evolution_task, custom_tools_loader = build_app(args.config, username=username)
    try:
        asyncio.run(repl(
            cfg, adapter, registry, loader, mcp, memory_manager, custom_tools_loader,
            username=username,
            evolution_task=evolution_task,
            show_logo=not args.no_logo,
            no_color=args.no_color,
        ))
    finally:
        loader.stop()
        custom_tools_loader.stop()


if __name__ == "__main__":
    main()
