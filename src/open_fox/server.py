"""HTTP 服务入口（FastAPI）。

对外接口（两套并存）：

框架自己的 REST API：
- POST /v1/chat                  发起一轮对话（高阶）
- GET  /v1/skills                列出 Skill
- GET  /v1/tools                 列出工具
- GET  /healthz                  健康检查

OpenAI Chat Completions 兼容 API（让 openai-python 等客户端可直接调用）：
- POST /v1/chat/completions      标准 chat completions
- POST /v1/chat/completions      支持 stream=true（SSE）
- GET  /v1/models                列出可用模型
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from open_fox.agents import AgentConfig, AgentStore, validate_agent
from open_fox.auth import JWT, UserStore
from open_fox.model_store import ModelStore
from open_fox.config import load_config, ModelConfig
from open_fox.usage_store import UsageStore
from open_fox.core.adapters.openai_chat import OpenAIChatAdapter
from open_fox.core.agent_filter import filter_registry, filter_skills
from open_fox.core.agent_loop import AgentLoop
from open_fox.core.custom_tools.loader import CustomToolsLoader
from open_fox.core.custom_tools.reload import _is_builtin_tool, reload_all
from open_fox.core.evolution import build_evolution
from open_fox.core.evolution.manager import SkillValidationError
from open_fox.core.mcp.client import McpClient
from open_fox.core.mcp.config_loader import load_mcp_configs
from open_fox.core.memory.extractor import MemoryExtractionTask
from open_fox.core.memory.manager import MemoryManager, MemoryManagerPool, set_current_user, get_current_user
from open_fox.core.memory.tools import register_memory_tools
from open_fox.core.memory.exceptions import MemoryPermissionError
from open_fox.core.registry import Registry
from open_fox.core.scripts.runner import ScriptRunner
from open_fox.core.security.path_guard import PathGuard
from open_fox.core.session import Session
from open_fox.core.skills.loader import SkillLoader
from open_fox.core.storage.json_store import JsonStorage
from open_fox.core.tools.file_tools import (
    EditFileTool,
    ReadFileTool,
    WriteFileTool,
)
from open_fox.core.tools.shell_tool import RunShellTool
from open_fox.core.tools.search_tools import GrepSearchTool, GlobFindTool
from open_fox.core.tools.dir_tools import ListDirTool, MakeDirTool, CopyFileTool, MoveFileTool
from open_fox.core.tools.git_tools import GitStatusTool, GitDiffTool, GitCommitTool, GitLogTool
from open_fox.core.tools.web_tools import WebSearchTool, WebFetchTool
from open_fox.core.tools.ast_tools import AstParseTool
from open_fox.core.tools.excel_tools import (
    ReadExcelTool,
    WriteExcelTool,
    EditExcelTool,
    ListSheetsTool,
)
from open_fox.core.tools.process_tools import (
    StartProcessTool,
    ReadProcessTool,
    StopProcessTool,
    ListProcessesTool,
)
from open_fox.core.project_store import ProjectStore


DEFAULT_AGENT_ID = "default"
DEFAULT_AGENT_NAME = "OpenFox"


def _usage_dict(usage) -> dict:
    """将内部 UsageInfo 统一序列化为 API 使用量结构。"""
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "cache_hit_tokens": usage.cache_hit_tokens,
        "cache_miss_tokens": usage.cache_miss_tokens,
        "reasoning_tokens": usage.reasoning_tokens,
    }
from open_fox.core.tools.todo_tools import TodoReadTool, TodoWriteTool

logger = logging.getLogger(__name__)


def build_components(config_path: str | None = None):
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
    # 代码搜索
    registry.register_tool(GrepSearchTool(path_guard=guard))
    registry.register_tool(GlobFindTool(path_guard=guard))
    # 目录与文件管理
    registry.register_tool(ListDirTool(path_guard=guard))
    registry.register_tool(MakeDirTool(path_guard=guard))
    registry.register_tool(CopyFileTool(path_guard=guard))
    registry.register_tool(MoveFileTool(path_guard=guard))
    # Git 操作
    registry.register_tool(GitStatusTool(path_guard=guard))
    registry.register_tool(GitDiffTool(path_guard=guard))
    registry.register_tool(GitCommitTool(path_guard=guard))
    registry.register_tool(GitLogTool(path_guard=guard))
    # 浏览器
    registry.register_tool(WebSearchTool())
    registry.register_tool(WebFetchTool())
    # 代码理解
    registry.register_tool(AstParseTool(path_guard=guard))
    # 任务管理
    registry.register_tool(TodoReadTool(todo_dir=cfg.workspace_dir))
    registry.register_tool(TodoWriteTool(todo_dir=cfg.workspace_dir))

    loader = SkillLoader(skills_dir=cfg.skills_dir)
    loader.start()

    storage = JsonStorage(base_dir=cfg.storage.json_dir)
    mcp = McpClient([])
    agent_store = AgentStore(config_path or "config.yaml")
    # 全局记忆管理器池：每用户一个 MemoryManager
    memory_pool = MemoryManagerPool(base_dir="./data/memory")
    # 自定义工具热加载：lifespan 里 start() 启动 watchdog
    custom_tools_loader = CustomToolsLoader(cfg.custom_tools_dir, registry)
    # Project 存储（会话级工作文件夹）
    project_store = ProjectStore(base_dir="./data/projects")

    return (cfg, adapter, registry, loader, storage, mcp, ScriptRunner(),
            agent_store, memory_pool, custom_tools_loader, project_store)


def _get_session_workdir(session: Session, components: tuple) -> str:
    """从 session meta 读取 project_id，查 ProjectStore 获取 workdir。"""
    try:
        meta = session.get_meta()
        project_id = meta.get("project_id", "")
        if not project_id:
            return ""
        project_store: ProjectStore = components[10]
        project = project_store.get(project_id)
        if project:
            return project.get("workdir", "")
    except Exception:
        pass
    return ""


def _build_session_tools(cfg, project_workdir: str, registry: Registry):
    """为单个会话构建受路径约束的工具实例，覆盖注册到 registry。

    - PathGuard 白名单 = skills_dir + workspace_dir + project_workdir（如有）
    - RunShellTool 的 cwd 锁定到 project_workdir（如无则回退到 skills_dir.parent）
    - Excel 工具走 PathGuard，天然安全
    """
    allowed_roots = [cfg.skills_dir, cfg.workspace_dir]
    if project_workdir:
        wd = Path(project_workdir)
        if wd.exists():
            allowed_roots.append(wd)

    # PathGuard 相对路径基准：优先用会话工作目录，使 `list_dir(".")` 等
    # 相对路径解析到用户实际工作目录而非后端进程 cwd。
    base_dir = Path(project_workdir) if project_workdir and Path(project_workdir).exists() else None
    guard = PathGuard(allowed_roots=allowed_roots, base_dir=base_dir)

    # 文件工具（PathGuard 覆盖）
    registry.register_tool(ReadFileTool(path_guard=guard))
    registry.register_tool(WriteFileTool(path_guard=guard))
    registry.register_tool(EditFileTool(path_guard=guard))
    registry.register_tool(GrepSearchTool(path_guard=guard))
    registry.register_tool(GlobFindTool(path_guard=guard))
    # 目录与文件管理
    registry.register_tool(ListDirTool(path_guard=guard))
    registry.register_tool(MakeDirTool(path_guard=guard))
    registry.register_tool(CopyFileTool(path_guard=guard))
    registry.register_tool(MoveFileTool(path_guard=guard))
    # Git 操作
    registry.register_tool(GitStatusTool(path_guard=guard))
    registry.register_tool(GitDiffTool(path_guard=guard))
    registry.register_tool(GitCommitTool(path_guard=guard))
    registry.register_tool(GitLogTool(path_guard=guard))
    # 代码理解
    registry.register_tool(AstParseTool(path_guard=guard))
    # 任务管理（todo 文件存到 workspace_dir）
    registry.register_tool(TodoReadTool(todo_dir=cfg.workspace_dir))
    registry.register_tool(TodoWriteTool(todo_dir=cfg.workspace_dir))
    # Shell（cwd 锁定到 project workdir 或项目根）
    shell_cwd = Path(project_workdir) if project_workdir else cfg.skills_dir.parent
    registry.register_tool(RunShellTool(cwd=shell_cwd,
                                         default_timeout=cfg.script_default_timeout))
    # Excel 工具
    registry.register_tool(ReadExcelTool(path_guard=guard))
    registry.register_tool(WriteExcelTool(path_guard=guard))
    registry.register_tool(EditExcelTool(path_guard=guard))
    registry.register_tool(ListSheetsTool(path_guard=guard))
    # 长进程管理（cwd 锁定到 project workdir 或项目根）
    registry.register_tool(StartProcessTool(cwd=shell_cwd))
    registry.register_tool(ReadProcessTool())
    registry.register_tool(StopProcessTool())
    registry.register_tool(ListProcessesTool())


@asynccontextmanager
async def lifespan(app: FastAPI):
    (cfg, adapter, registry, loader, storage, mcp, runner,
     agent_store, memory_pool, custom_tools_loader,
     project_store) = build_components(
        app.state.config_path)
    usage_store = UsageStore(base_dir="./data/usage")
    # 自定义工具热加载（启动 watchdog 监听 tools/ 目录）
    custom_tools_loader.start()
    # 从 mcps_dir 加载 MCP 配置并启动（替代空 McpClient([])）
    new_configs, _ = load_mcp_configs(cfg.mcps_dir)
    mcp._configs = new_configs
    await mcp.start_all()
    for tool in await mcp.get_tools():
        registry.register_mcp_tool(tool)
    logger.info(
        "自定义工具：%d / MCP：%d 服务共 %d 工具 / Skill：%d",
        len(custom_tools_loader.all()),
        len([c for c in new_configs if c.enabled]),
        len(registry._mcp_tools),
        len(loader.all()),
    )
    # 注册池感知记忆工具（工具执行时根据上下文自动解析当前用户的 MemoryManager）
    register_memory_tools(registry, memory_pool)
    # Skill 进化：构造组件 + 加载持久化 + 后台任务
    evo_manager, evo_tracker, _, evo_queue, evo_task = build_evolution(
        cfg, adapter, cfg.skills_dir)
    evo_manager.load_sync()  # 无持久化，空操作，保持对称（同步函数，勿 await）
    await evo_tracker.load()
    await evo_queue.load()
    app.state.evolution_task = evo_task
    await evo_task.start()
    # 隐式记忆抽取后台任务：每轮对话完成后 fire-and-forget 通知（内部 _should_extract 过滤）
    extractor = MemoryExtractionTask(memory_pool, adapter)
    await extractor.start()
    app.state.extractor = extractor
    app.state.components = (cfg, adapter, registry, loader, storage, mcp,
                            runner, agent_store, memory_pool,
                            custom_tools_loader, project_store)
    app.state.usage_store = usage_store
    # 模型配置 Store：读写 config.yaml 的 models 段，与 AgentStore 对称
    app.state.model_store = ModelStore(app.state.config_path or "config.yaml")
    # 用户认证：JWT + UserStore
    jwt_secret = os.environ.get("OPENFOX_JWT_SECRET", "openfox-default-jwt-secret")
    app.state.jwt = JWT(jwt_secret)
    user_store = UserStore(data_dir="./data")
    # 确保默认用户 Ciel 存在
    if not user_store.get("Ciel"):
        user_store.create_user("Ciel", "123456", "Ciel")
        logger.info("默认用户 Ciel 已创建（密码 123456）")
    app.state.user_store = user_store
    # 为已有智能体补充 owner 字段（向后兼容）
    for agent in agent_store.list():
        if not agent.owner:
            agent_store.update(agent.id, {"owner": "Ciel"})
    try:
        yield
    finally:
        await extractor.stop()
        await evo_task.stop()
        await mcp.stop_all()
        loader.stop()
        custom_tools_loader.stop()


app = FastAPI(title="OpenFox", lifespan=lifespan)


# ========== 认证中间件 ==========

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """认证中间件：验证 JWT 并注入用户信息。

    - 有 Bearer token 且有效 → request.state.user = payload, .authenticated = True
    - 无 token 或 token 无效 → 降级为默认用户 Ciel（向后兼容 CLI / OpenAI 客户端）
    """
    default_user = {"sub": "Ciel", "display_name": "Ciel"}
    request.state.user = default_user
    request.state.authenticated = False

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        jwt_instance: JWT | None = getattr(app.state, "jwt", None)
        if jwt_instance:
            payload = jwt_instance.decode(token)
            if payload:
                request.state.user = payload
                request.state.authenticated = True

    return await call_next(request)


def _username(request: Request) -> str:
    """从 request.state.user 提取当前用户名。"""
    return getattr(request.state, "user", {}).get("sub", "Ciel")


# ========== 认证 API ==========

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""


@app.post("/v1/auth/register")
async def register(req: RegisterRequest) -> dict:
    """用户注册，成功后自动登录返回 JWT token。"""
    import re
    if not req.username.strip():
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if len(req.username) > 32:
        raise HTTPException(status_code=400, detail="用户名不能超过 32 个字符")
    if not re.match(r"^[A-Za-z0-9_-]+$", req.username):
        raise HTTPException(status_code=400, detail="用户名只能包含字母、数字、下划线和连字符")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码长度不能少于 6 位")
    user_store: UserStore = app.state.user_store
    try:
        user = user_store.create_user(req.username, req.password, req.display_name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    jwt_instance: JWT = app.state.jwt
    token = jwt_instance.encode({
        "sub": user.username,
        "display_name": user.display_name,
    })
    return {
        "token": token,
        "user": {
            "username": user.username,
            "display_name": user.display_name,
        },
    }


@app.post("/v1/auth/login")
async def login(req: LoginRequest) -> dict:
    """用户登录，返回 JWT token。"""
    user_store: UserStore = app.state.user_store
    user = user_store.verify(req.username, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    jwt_instance: JWT = app.state.jwt
    token = jwt_instance.encode({
        "sub": user.username,
        "display_name": user.display_name,
    })
    return {
        "token": token,
        "user": {
            "username": user.username,
            "display_name": user.display_name,
        },
    }


@app.get("/v1/auth/me")
async def auth_me(request: Request) -> dict:
    """获取当前用户信息（需有效 token）。"""
    if not getattr(request.state, "authenticated", False):
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    user = request.state.user
    return {
        "username": user.get("sub", ""),
        "display_name": user.get("display_name", ""),
    }


def _check_api_key(adapter) -> None:
    """校验当前激活模型的 API Key 是否已配置。

    在调用 LLM 前检查，避免空 Key 导致 httpx 拼出 'Bearer ' 触发
    Illegal header value 底层错误。Key 为空时抛出 HTTPException(400)，
    前端可据此弹窗引导用户去设置里填写密钥。
    """
    mc = adapter._models.get(adapter.active)
    if mc is not None and not mc.api_key:
        raise HTTPException(
            status_code=400,
            detail="当前模型未配置 API 密钥，请在「设置 → 模型管理」中填写密钥后再发送消息。",
        )


def _build_server_compressor(cfg, adapter):
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

    # 包装 adapter.chat 为 compressor 所需的签名
    async def llm_chat_fn(messages: list[dict], tools: list[dict]) -> str:
        response = await adapter.chat(messages, tools=tools or None, stream=False)
        return response.content or ""

    return ContextCompressor(config=compress_config, llm_chat_fn=llm_chat_fn)


class ChatRequest(BaseModel):
    session_id: str
    message: str
    model: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    agent_id: str = DEFAULT_AGENT_ID
    # 真实 usage（来自上游 LLM API，可能为空 dict）
    usage: dict = Field(default_factory=dict)
    # 首次对话自动生成的标题（仅当原标题为默认值时返回）
    auto_title: str | None = None


def _generate_auto_title(session) -> str | None:
    """为首轮会话自动生成标题（过滤压缩摘要消息）。

    当标题仍为默认值且仅有 1 条真实用户消息（排除上下文压缩插入的
    ``role="user"`` 摘要/锚点消息）时，取该消息前 20 字作为标题。

    Returns:
        生成的标题字符串；若不满足条件则返回 None。
    """
    meta = session.get_meta()
    if meta.get("title", "") not in ("新会话", ""):
        return None

    # 过滤掉压缩摘要/锚点消息，只统计真实用户消息
    real_user_msgs = [
        m for m in session.chat_messages()
        if m.get("role") == "user" and not m.get("_compressed")
    ]
    if len(real_user_msgs) != 1:
        return None

    first_user_msg = real_user_msgs[0].get("content", "")
    if not first_user_msg:
        return None

    clean = first_user_msg.replace("\n", " ").strip()
    title = clean[:20]
    if len(clean) > 20:
        title += "…"
    session.set_meta(title=title)
    session.save()
    return title


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(request: Request, req: ChatRequest) -> ChatResponse:
    username = _username(request)
    token = set_current_user(username)
    try:
        cfg, adapter, registry, loader, storage, mcp, runner, _, memory_pool, _, _ = app.state.components
        usage_store = app.state.usage_store
        if req.model:
            adapter.set_active(req.model)
        _check_api_key(adapter)
        session = Session(session_id=req.session_id, storage=storage,
                          active_model=adapter.active)
        session.load()

        # 获取当前用户的 MemoryManager
        memory_manager = await memory_pool.get(username)

        # 包装 adapter.chat 捕获最后一次调用的真实 usage
        # 注意：必须捕获原始 chat 引用，否则会无限递归
        last_usage: dict | None = None
        original_chat = adapter.chat

        async def instrumented_chat(messages, tools=None, stream=False, temperature=None):
            nonlocal last_usage
            response = await original_chat(messages, tools=tools, stream=stream,
                                           temperature=temperature)
            from open_fox.core.adapters.base import AssistantMessage
            if isinstance(response, AssistantMessage) and response.usage:
                u = response.usage
                last_usage = {
                    "prompt_tokens": u.prompt_tokens,
                    "completion_tokens": u.completion_tokens,
                    "total_tokens": u.total_tokens,
                    "cache_hit_tokens": u.cache_hit_tokens,
                    "cache_miss_tokens": u.cache_miss_tokens,
                    "reasoning_tokens": u.reasoning_tokens,
                }
            return response

        adapter.chat = instrumented_chat
        try:
            # 构建上下文压缩器（每次请求创建，使用当前 adapter）
            compressor = _build_server_compressor(cfg, adapter)
            # 获取会话关联的工作目录
            session_workdir = _get_session_workdir(session, app.state.components)
            # 构建会话级工具（PathGuard 白名单 + Shell cwd 锁定）
            _build_session_tools(cfg, session_workdir, registry)
            loop = AgentLoop(
                adapter=adapter, registry=registry, session=session,
                script_runner=runner, skills=loader.all(),
                max_steps=cfg.max_agent_steps,
                memory_manager=memory_manager,
                compressor=compressor,
                workdir=session_workdir,
            )
            reply = await loop.run(req.message)
        finally:
            adapter.chat = original_chat

        # 隐式记忆抽取：AgentLoop.run() 完成后 fire-and-forget 通知（内部 _should_extract 过滤）
        extractor = getattr(app.state, "extractor", None)
        if extractor is not None:
            await extractor.notify(session.get_messages(), bool(loop.tool_trace), username)

        # Skill 进化：AgentLoop.run() 完成后通知（内部节流/触发判定过滤）
        evolution_task = getattr(app.state, "evolution_task", None)
        if evolution_task is not None:
            await evolution_task.notify(req.session_id, session.get_messages(), loop.tool_trace)

        # 用量记录：写入本次对话的 token 消耗
        au = loop.accumulated_usage
        usage_store.record(
            username=username,
            model=adapter.active,
            prompt_tokens=au.prompt_tokens,
            completion_tokens=au.completion_tokens,
            total_tokens=au.total_tokens,
            cache_hit_tokens=au.cache_hit_tokens,
            reasoning_tokens=au.reasoning_tokens,
            session_id=req.session_id,
        )

        # 自动标题：首轮会话从消息内容生成简短标题（过滤压缩摘要）
        auto_title = _generate_auto_title(session)

        # 显式 dump 保证所有字段都被序列化（pydantic 默认 exclude_unset 会过滤）
        return ChatResponse(
            session_id=req.session_id,
            reply=reply,
            agent_id=DEFAULT_AGENT_ID,
            usage=last_usage if last_usage else {},
            auto_title=auto_title,
        ).model_dump()  # type: ignore[return-value]
    finally:
        from open_fox.core.memory.manager import _current_user as _ctx_var
        _ctx_var.reset(token)


# ========== SSE 流式聊天端点 ==========

async def _chat_stream_generator(request: Request, req: ChatRequest):
    """SSE 事件生成器：实时推送工具调用和最终回复。"""
    import asyncio

    username = _username(request)
    token = set_current_user(username)

    try:
        cfg, adapter, registry, loader, storage, mcp, runner, _, memory_pool, _, _ = app.state.components
        usage_store = app.state.usage_store
        if req.model:
            adapter.set_active(req.model)
        session = Session(session_id=req.session_id, storage=storage,
                          active_model=adapter.active)
        session.load()

        # 内置 Agent 不暴露为管理对象，但会话始终保留明确的 Agent 元数据。
        meta = session.get_meta()
        if not meta:
            session.set_meta(
                agent_id=DEFAULT_AGENT_ID,
                agent_name=DEFAULT_AGENT_NAME,
                title="新会话",
                model=adapter.active,
                owner=username,
            )
        elif not meta.get("agent_id"):
            session.set_meta(agent_id=DEFAULT_AGENT_ID, agent_name=DEFAULT_AGENT_NAME)
        session.save()

        memory_manager = await memory_pool.get(username)

        # 事件队列：AgentLoop 回调写入，SSE 生成器读取
        event_queue: asyncio.Queue = asyncio.Queue()

        # 危险命令确认注册表：confirm_id → asyncio.Future[bool]
        # on_confirm 回调等待 Future，POST /v1/tool/confirm 端点设置 Future 结果
        _confirm_pending: dict[str, asyncio.Future] = {}

        async def on_tool_event(event_type: str, data: dict):
            await event_queue.put((event_type, data))

        async def on_chunk(chunk):
            if chunk.content_delta or chunk.reasoning_delta:
                await event_queue.put(("assistant_delta", {
                    "content": chunk.content_delta,
                    "reasoning": chunk.reasoning_delta,
                    "step": loop.current_step if loop is not None else 0,
                }))

        async def on_confirm(confirm_id: str) -> bool:
            """等待用户确认危险命令，返回 True（允许）或 False（拒绝）。"""
            loop_ref = asyncio.get_running_loop()
            future = loop_ref.create_future()
            _confirm_pending[confirm_id] = future
            _global_confirm_pending[confirm_id] = future  # 全局注册，POST /v1/tool/confirm 可访问
            try:
                result = await future
                return bool(result)
            finally:
                _confirm_pending.pop(confirm_id, None)
                _global_confirm_pending.pop(confirm_id, None)

        reply_text = ""
        loop = None
        loop_task = None
        cancelled = False

        try:
            compressor = _build_server_compressor(cfg, adapter)
            # 获取会话关联的工作目录
            session_workdir = _get_session_workdir(session, app.state.components)
            # 构建会话级工具（PathGuard 白名单 + Shell cwd 锁定）
            _build_session_tools(cfg, session_workdir, registry)
            loop = AgentLoop(
                adapter=adapter, registry=registry, session=session,
                script_runner=runner, skills=loader.all(),
                max_steps=cfg.max_agent_steps,
                memory_manager=memory_manager,
                compressor=compressor,
                on_chunk=on_chunk,
                on_tool_event=on_tool_event,
                on_confirm=on_confirm,
                workdir=session_workdir,
            )

            # 在后台运行 AgentLoop，同时从队列中读取事件并推送 SSE
            async def run_loop():
                nonlocal reply_text
                try:
                    reply_text = await loop.run(req.message)
                except asyncio.CancelledError:
                    await event_queue.put(("cancelled", {"message": "任务已停止"}))
                    raise
                except Exception as e:
                    await event_queue.put(("error", {"message": str(e)}))
                else:
                    await event_queue.put(("done", {"reply": reply_text}))

            loop_task = asyncio.create_task(run_loop())

            # 持续从队列读取事件，推送到 SSE
            # 双重保护机制：
            # 1. keepalive 心跳：每 15 秒无真实事件时发送 SSE 注释行（`: keepalive\n\n`），
            #    防止中间代理/浏览器因连接空闲而断开。前端应忽略以 `:` 开头的行。
            # 2. 空闲超时：连续 120 秒无真实事件（LLM/工具卡死），主动取消任务并推送 error。
            SSE_IDLE_TIMEOUT = 120  # 秒
            SSE_KEEPALIVE_INTERVAL = 15  # 秒
            idle_seconds = 0.0
            while True:
                try:
                    event_type, data = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                    idle_seconds = 0.0
                except asyncio.TimeoutError:
                    idle_seconds += 0.5
                    # 推送 keepalive 心跳，防止连接被代理/浏览器断开
                    if idle_seconds > 0 and idle_seconds % SSE_KEEPALIVE_INTERVAL < 0.5:
                        yield ": keepalive\n\n"
                    if idle_seconds >= SSE_IDLE_TIMEOUT:
                        # 超时：取消后端任务，通知前端
                        logger.warning(
                            "SSE 空闲 %ds 无事件，强制结束会话 %s",
                            int(idle_seconds), req.session_id,
                        )
                        if not loop_task.done():
                            loop_task.cancel()
                        timeout_msg = f"响应超时（{int(SSE_IDLE_TIMEOUT)}秒无活动），任务已自动终止。"
                        yield f'event: error\ndata: {json.dumps({"message": timeout_msg}, ensure_ascii=False)}\n\n'
                        break
                    if await request.is_disconnected():
                        cancelled = True
                        loop_task.cancel()
                        break
                    continue

                if event_type == "done":
                    # 最终回复事件：包含完整回复、usage、tool_trace、auto_title
                    auto_title = _generate_auto_title(session)

                    done_data = {
                        "reply": data.get("reply", ""),
                        "session_id": req.session_id,
                        "agent_id": DEFAULT_AGENT_ID,
                        "usage": _usage_dict(loop.accumulated_usage),
                        "auto_title": auto_title,
                        "tool_trace": loop.tool_trace,
                    }
                    yield f"event: done\ndata: {json.dumps(done_data, ensure_ascii=False)}\n\n"
                    break
                elif event_type == "cancelled":
                    yield f"event: cancelled\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                    break
                elif event_type == "error":
                    yield f"event: error\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                    break
                else:
                    yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

            # 等待 loop_task 完成（确保后续逻辑执行）
            if loop_task is not None:
                if cancelled and not loop_task.done():
                    loop_task.cancel()
                try:
                    await loop_task
                except asyncio.CancelledError:
                    pass

        finally:
            if loop_task is not None and not loop_task.done():
                loop_task.cancel()
                try:
                    await loop_task
                except asyncio.CancelledError:
                    pass

        # 后续逻辑：隐式记忆抽取、Skill 进化、用量记录
        if loop is not None:
            session.save()
            if not cancelled:
                extractor = getattr(app.state, "extractor", None)
                if extractor is not None:
                    await extractor.notify(session.get_messages(), bool(loop.tool_trace), username)
                evolution_task = getattr(app.state, "evolution_task", None)
                if evolution_task is not None:
                    await evolution_task.notify(req.session_id, session.get_messages(), loop.tool_trace)
            au = loop.accumulated_usage
            usage_store.record(
                username=username, model=adapter.active,
                prompt_tokens=au.prompt_tokens, completion_tokens=au.completion_tokens,
                total_tokens=au.total_tokens, cache_hit_tokens=au.cache_hit_tokens,
                reasoning_tokens=au.reasoning_tokens, session_id=req.session_id,
                agent_id=DEFAULT_AGENT_ID,
            )

    finally:
        from open_fox.core.memory.manager import _current_user as _ctx_var
        _ctx_var.reset(token)


@app.post("/v1/chat/stream")
async def chat_stream(request: Request, req: ChatRequest):
    """SSE 流式聊天端点：实时推送工具调用事件和最终回复。"""
    # 在进入 SSE 流之前校验 API Key，空 Key 直接返回 400
    # （在 generator 内抛 HTTPException 会被吞成 SSE 连接中断）
    adapter = app.state.components[1]
    if req.model:
        adapter.set_active(req.model)
    _check_api_key(adapter)
    # adapter.set_active 已改变 active，需恢复 generator 默认逻辑
    return StreamingResponse(
        _chat_stream_generator(request, req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ========== 危险命令确认端点 ==========

# 全局确认注册表：confirm_id → asyncio.Future[bool]
# _chat_stream_generator 内部创建的 on_confirm 回调会往这里注册 Future，
# 本端点设置 Future 结果，实现前端 → 后端的确认/拒绝通信。
_global_confirm_pending: dict[str, asyncio.Future] = {}


class ToolConfirmRequest(BaseModel):
    confirm_id: str
    approved: bool


@app.post("/v1/tool/confirm")
async def tool_confirm(req: ToolConfirmRequest) -> dict:
    """用户确认/拒绝危险命令。

    前端弹窗点击"允许"或"拒绝"后调用此端点，后端通过 Future 通知
    AgentLoop 继续执行或跳过。
    """
    future = _global_confirm_pending.get(req.confirm_id)
    if future is None:
        raise HTTPException(status_code=404, detail="确认请求不存在或已过期")
    if future.done():
        raise HTTPException(status_code=409, detail="确认请求已处理")
    future.set_result(req.approved)
    return {"confirm_id": req.confirm_id, "approved": req.approved}


@app.get("/v1/skills")
async def list_skills() -> dict:
    _, _, _, loader, *_ = app.state.components
    return {
        name: {"description": s.description, "scripts": [sc.id for sc in s.scripts]}
        for name, s in loader.all().items()
    }


# ========== Skill 管理 API ==========

@app.get("/v1/skills/detail")
async def list_skill_details() -> dict:
    """返回所有 Skill 的完整信息，供管理页面使用。"""
    loader = app.state.components[3]
    skills = loader.all()
    result = []
    for name, s in skills.items():
        result.append({
            "name": s.name,
            "description": s.description,
            "tools": s.tools,
            "scripts": [
                {"id": sc.id, "lang": sc.lang, "entry": sc.entry,
                 "timeout": sc.timeout, "description": sc.description}
                for sc in s.scripts
            ],
            "version": s.version,
            "deprecated": s.deprecated,
            "trigger": s.trigger,
            "body_preview": s.body[:200] if s.body else "",
            "source_dir": str(s.source_dir),
        })
    return {"skills": result}


@app.get("/v1/skills/{name}/content")
async def get_skill_content(name: str) -> dict:
    """读取 SKILL.md 原文。"""
    cfg = app.state.components[0]
    skill_md = cfg.skills_dir / name / "SKILL.md"
    if not skill_md.exists():
        raise HTTPException(status_code=404, detail=f"Skill '{name}' 不存在")
    return {"name": name, "content": skill_md.read_text(encoding="utf-8")}


class SkillContentUpdate(BaseModel):
    """手动编辑 SKILL.md 的请求体。"""
    content: str


@app.put("/v1/skills/{name}/content")
async def update_skill_content(name: str, req: SkillContentUpdate) -> dict:
    """手动编辑保存 SKILL.md（经 SkillEvolutionManager 校验 + 版本快照）。"""
    cfg = app.state.components[0]
    evo_manager = app.state.evolution_task.manager
    loader = app.state.components[3]
    skill_md = cfg.skills_dir / name / "SKILL.md"
    action = "fix" if skill_md.exists() else "create"
    try:
        msg = await evo_manager.apply_candidate(action, name, req.content)
    except SkillValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    loader.rescan()
    return {"message": msg}


class SkillCreateRequest(BaseModel):
    """手动创建新 Skill 的请求体。"""
    name: str
    description: str
    content: str = ""


@app.post("/v1/skills")
async def create_skill(req: SkillCreateRequest) -> dict:
    """手动创建新 Skill。"""
    evo_manager = app.state.evolution_task.manager
    loader = app.state.components[3]
    # 如果未提供 content，生成最小模板
    content = req.content or (
        f"---\nname: {req.name}\ndescription: {req.description}\n---\n\n"
        f"# {req.name}\n\nTODO: 在此编写 Skill 工作流\n"
    )
    try:
        msg = await evo_manager.apply_candidate("create", req.name, content)
    except SkillValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    loader.rescan()
    return {"message": msg}


@app.delete("/v1/skills/{name}", status_code=204, response_model=None)
async def delete_skill(name: str, mode: str = "deprecate") -> None:
    """删除 Skill：mode=deprecate 标记废弃（推荐），mode=delete 物理删除。"""
    cfg = app.state.components[0]
    evo_manager = app.state.evolution_task.manager
    loader = app.state.components[3]
    skill_dir = cfg.skills_dir / name
    if not skill_dir.exists():
        raise HTTPException(status_code=404, detail=f"Skill '{name}' 不存在")
    if mode == "deprecate":
        try:
            await evo_manager.deprecate(name)
        except SkillValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
    elif mode == "delete":
        import shutil
        shutil.rmtree(skill_dir, ignore_errors=True)
    else:
        raise HTTPException(status_code=400, detail="mode 必须为 deprecate 或 delete")
    loader.rescan()


@app.post("/v1/skills/{name}/rollback")
async def rollback_skill(name: str) -> dict:
    """回滚 Skill 到上一版本。"""
    evo_manager = app.state.evolution_task.manager
    loader = app.state.components[3]
    try:
        msg = await evo_manager.rollback(name)
    except SkillValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    loader.rescan()
    return {"message": msg}


@app.get("/v1/skills/{name}/stats")
async def get_skill_stats(name: str) -> dict:
    """返回 Skill 的调用统计。"""
    tracker = app.state.evolution_task.tracker
    st = tracker.skill_stats(name)
    return {
        "name": name,
        "invocations": st.invocations,
        "failures": st.failures,
        "last_success_at": st.last_success_at,
        "last_failed_at": st.last_failed_at,
        "error_samples": st.error_samples,
    }


@app.get("/v1/skills/{name}/versions")
async def get_skill_versions(name: str) -> dict:
    """返回 Skill 的版本历史。"""
    cfg = app.state.components[0]
    versions_dir = cfg.skills_dir / name / ".versions"
    if not versions_dir.exists():
        return {"name": name, "versions": []}
    versions = []
    for v in sorted(versions_dir.iterdir()):
        if not v.is_dir():
            continue
        skill_md = v / "SKILL.md"
        try:
            from open_fox.core.skills.parser import parse_skill_md
            skill = parse_skill_md(skill_md)
            versions.append({
                "version": v.name,
                "skill_version": skill.version,
                "description": skill.description,
            })
        except Exception:
            versions.append({"version": v.name, "skill_version": 0, "description": ""})
    return {"name": name, "versions": versions}


class SkillImportRequest(BaseModel):
    """导入本地 Skill 的请求体。"""
    source_path: str
    overwrite: bool = False


@app.post("/v1/skills/import")
async def import_skill(req: SkillImportRequest) -> dict:
    """从本地文件系统导入 Skill。

    支持两种模式：
    - source_path 指向目录：复制整个 Skill 目录（SKILL.md + scripts/ + 其他文件）
    - source_path 指向 SKILL.md 文件：仅导入该文件，自动创建 Skill 目录

    导入后会强制 version=1，并记录到 changelog。
    """
    import shutil
    from open_fox.core.skills.parser import parse_skill_md, parse_skill_md_text

    cfg = app.state.components[0]
    evo_manager = app.state.evolution_task.manager
    loader = app.state.components[3]

    src = Path(req.source_path).expanduser().resolve()
    if not src.exists():
        raise HTTPException(status_code=400, detail=f"路径不存在：{src}")

    # 判断是目录还是文件
    if src.is_dir():
        skill_md_path = src / "SKILL.md"
        if not skill_md_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"目录中未找到 SKILL.md：{src}",
            )
        content = skill_md_path.read_text(encoding="utf-8")
    elif src.is_file():
        if src.name != "SKILL.md":
            raise HTTPException(
                status_code=400,
                detail="文件路径必须指向 SKILL.md",
            )
        content = src.read_text(encoding="utf-8")
        skill_md_path = src
    else:
        raise HTTPException(status_code=400, detail="路径既不是目录也不是文件")

    # 解析 SKILL.md 获取技能名称
    try:
        skill = parse_skill_md_text(content)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"SKILL.md 解析失败：{e}",
        ) from e

    skill_name = skill.name
    skill_dir = cfg.skills_dir / skill_name

    # 名称冲突检查
    if skill_dir.exists():
        if not req.overwrite:
            raise HTTPException(
                status_code=409,
                detail=f"Skill 已存在：{skill_name}（如需覆盖请设置 overwrite=true）",
            )
        # 覆盖模式：先删除现有目录
        shutil.rmtree(skill_dir, ignore_errors=True)

    # 创建 Skill 目录
    skill_dir.mkdir(parents=True, exist_ok=False)

    if src.is_dir():
        # 目录模式：复制全部文件（排除 .versions/ 和 node_modules/）
        shutil.copytree(
            src,
            skill_dir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".versions", "node_modules", "__pycache__"),
        )
    else:
        # 文件模式：仅复制 SKILL.md
        shutil.copy2(src, skill_dir / "SKILL.md")

    # 强制 version=1（导入视为全新技能）
    final_md = skill_dir / "SKILL.md"
    text = final_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        close = 1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                close = i
                break
        meta = [l for l in lines[1:close] if not l.strip().startswith("version:")]
        meta.append("version: 1")
        text = "\n".join(["---", *meta, *lines[close:]])
        final_md.write_text(text, encoding="utf-8")

    # 记录到 changelog
    changelog = evo_manager._data_dir / "changelog.log"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ005
    with changelog.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] [Skill导入] {skill_name} | from {src} | version 1 | 覆盖={req.overwrite}\n")

    # 重新扫描
    loader.rescan()

    return {
        "message": f"导入成功：{skill_name}",
        "name": skill_name,
        "version": 1,
        "source": str(src),
    }


class SkillUploadRequest(BaseModel):
    """通过浏览器上传导入 Skill 的请求体。"""
    files: list[dict]  # [{"path": "SKILL.md", "content": "base64..."}, ...]
    overwrite: bool = False


@app.post("/v1/skills/upload")
async def upload_skill(req: SkillUploadRequest) -> dict:
    """通过浏览器文件上传导入 Skill。

    前端将用户选择的文件（单个 SKILL.md 或整个目录）以 base64 编码后
    通过 JSON 提交。后端重建 Skill 目录结构并写入。
    """
    import base64
    import shutil
    from open_fox.core.skills.parser import parse_skill_md_text

    cfg = app.state.components[0]
    evo_manager = app.state.evolution_task.manager
    loader = app.state.components[3]

    if not req.files:
        raise HTTPException(status_code=400, detail="未上传任何文件")

    # 标准化路径：统一用正斜杠，去除前导斜杠
    raw_paths = [f["path"].replace("\\", "/").lstrip("/") for f in req.files]

    # 找到 SKILL.md
    skill_md_idx = None
    for i, p in enumerate(raw_paths):
        if p.split("/")[-1].upper() == "SKILL.MD":
            skill_md_idx = i
            break
    if skill_md_idx is None:
        raise HTTPException(status_code=400, detail="未找到 SKILL.md 文件")

    # 如果是目录模式（路径含子目录），去除公共前缀使其相对于 Skill 目录
    skill_md_path = raw_paths[skill_md_idx]
    if "/" in skill_md_path:
        prefix = skill_md_path.rsplit("/", 1)[0]
        norm_paths = []
        for p in raw_paths:
            if p.startswith(prefix + "/"):
                norm_paths.append(p[len(prefix) + 1:])
            else:
                norm_paths.append(p)
    else:
        norm_paths = raw_paths

    # 解析 SKILL.md 内容获取技能名称
    skill_md_content = base64.b64decode(req.files[skill_md_idx]["content"]).decode("utf-8")
    try:
        skill = parse_skill_md_text(skill_md_content)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"SKILL.md 解析失败：{e}",
        ) from e

    skill_name = skill.name
    skill_dir = cfg.skills_dir / skill_name

    # 名称冲突检查
    if skill_dir.exists():
        if not req.overwrite:
            raise HTTPException(
                status_code=409,
                detail=f"Skill 已存在：{skill_name}（如需覆盖请开启覆盖选项）",
            )
        shutil.rmtree(skill_dir, ignore_errors=True)

    skill_dir.mkdir(parents=True, exist_ok=False)

    # 排除清单
    _EXCLUDE_DIRS = {"node_modules", ".versions", "__pycache__", ".git", "dist"}
    written = 0
    for i, norm_path in enumerate(norm_paths):
        # 安全检查：防止路径穿越
        if ".." in norm_path:
            continue
        parts = norm_path.split("/")
        if any(p in _EXCLUDE_DIRS for p in parts):
            continue

        target = skill_dir / norm_path
        # 确保写入目标在 skills_dir 内
        try:
            target.resolve().relative_to(cfg.skills_dir.resolve())
        except ValueError:
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(req.files[i]["content"]))
        written += 1

    # 强制 version=1
    final_md = skill_dir / "SKILL.md"
    text = final_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        close = 1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                close = i
                break
        meta = [l for l in lines[1:close] if not l.strip().startswith("version:")]
        meta.append("version: 1")
        text = "\n".join(["---", *meta, *lines[close:]])
        final_md.write_text(text, encoding="utf-8")

    # 记录到 changelog
    changelog = evo_manager._data_dir / "changelog.log"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ005
    with changelog.open("a", encoding="utf-8") as f:
        f.write(
            f"[{ts}] [Skill上传导入] {skill_name} | {written} files | "
            f"version 1 | 覆盖={req.overwrite}\n"
        )

    loader.rescan()

    return {
        "message": f"上传导入成功：{skill_name}（{written} 个文件）",
        "name": skill_name,
        "version": 1,
        "file_count": written,
    }


class SkillInstallUrlRequest(BaseModel):
    """从 URL 安装 Skill 的请求体。"""
    url: str
    overwrite: bool = False


@app.post("/v1/skills/install-url")
async def install_skill_from_url(req: SkillInstallUrlRequest) -> dict:
    """从 URL 安装 Skill。

    支持：
    - raw GitHub URL（自动识别并下载 SKILL.md 或整个目录）
    - 任意直链 SKILL.md 文件

    下载后写入 skills_dir，强制 version=1。
    """
    import shutil
    import urllib.request
    from open_fox.core.skills.parser import parse_skill_md_text

    cfg = app.state.components[0]
    evo_manager = app.state.evolution_task.manager
    loader = app.state.components[3]

    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL 不能为空")

    # 下载内容
    try:
        req_obj = urllib.request.Request(url, headers={"User-Agent": "OpenFox/1.0"})
        with urllib.request.urlopen(req_obj, timeout=30) as resp:
            content_bytes = resp.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"下载失败：{e}") from e

    # 尝试解码为文本
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="下载的内容不是有效的 UTF-8 文本") from None

    # 解析 SKILL.md
    try:
        skill = parse_skill_md_text(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SKILL.md 解析失败：{e}") from e

    skill_name = skill.name
    skill_dir = cfg.skills_dir / skill_name

    if skill_dir.exists():
        if not req.overwrite:
            raise HTTPException(
                status_code=409,
                detail=f"Skill 已存在：{skill_name}（如需覆盖请设置 overwrite=true）",
            )
        shutil.rmtree(skill_dir, ignore_errors=True)

    skill_dir.mkdir(parents=True, exist_ok=False)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    # 强制 version=1
    final_md = skill_dir / "SKILL.md"
    text = final_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        close = 1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                close = i
                break
        meta = [l for l in lines[1:close] if not l.strip().startswith("version:")]
        meta.append("version: 1")
        text = "\n".join(["---", *meta, *lines[close:]])
        final_md.write_text(text, encoding="utf-8")

    # 记录到 changelog
    changelog = evo_manager._data_dir / "changelog.log"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ005
    with changelog.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] [Skill URL安装] {skill_name} | from {url} | version 1 | 覆盖={req.overwrite}\n")

    loader.rescan()

    return {
        "message": f"安装成功：{skill_name}",
        "name": skill_name,
        "version": 1,
        "source": url,
    }


class SkillAiGenerateRequest(BaseModel):
    """AI 生成 Skill 模板的请求体。"""
    name: str
    description: str
    trigger: str = ""
    tools: str = ""


# 预设 Skill 模板（不依赖外部 LLM 调用，直接生成结构化模板）
_SKILL_TEMPLATES = {
    "文件处理": {
        "trigger": "用户需要处理文件时（如读取、转换、合并、分割文件）",
        "tools": "read_file, write_file",
        "body_template": """## 工作流程

1. **接收请求**：解析用户意图，确定要处理的文件路径和操作类型
2. **读取文件**：使用 read_file 工具读取目标文件内容
3. **处理数据**：根据用户要求进行转换、过滤或合并
4. **输出结果**：使用 write_file 写入结果，或直接返回处理后的内容

## 注意事项

- 操作前确认文件路径正确
- 大文件处理时注意内存使用
- 写入前备份原始文件
""",
    },
    "数据分析": {
        "trigger": "用户需要对数据进行分析、统计、可视化时",
        "tools": "run_python",
        "body_template": """## 工作流程

1. **理解需求**：明确分析目标、数据来源和期望输出
2. **加载数据**：使用 run_python 执行 pandas/sql 读取数据
3. **清洗处理**：去重、填充缺失值、类型转换
4. **分析计算**：统计描述、分组聚合、相关性分析
5. **输出结果**：生成报告或图表

## 注意事项

- 大数据集使用分块读取
- 关键步骤输出中间结果供用户确认
- 图表使用 matplotlib 默认风格
""",
    },
    "API 调用": {
        "trigger": "用户需要调用外部 API 获取数据时",
        "tools": "http_request",
        "body_template": """## 工作流程

1. **解析参数**：确定 API 地址、请求方法、参数和认证信息
2. **构建请求**：使用 http_request 工具组装请求
3. **发送请求**：执行调用并获取响应
4. **处理响应**：解析 JSON/HTML，提取关键字段
5. **返回结果**：格式化输出给用户

## 注意事项

- 敏感信息（API Key 等）从环境变量读取
- 设置合理的超时时间
- 处理 HTTP 错误码和异常响应
""",
    },
    "通用": {
        "trigger": "根据 skill name 和 description 自动推断",
        "tools": "",
        "body_template": """## 工作流程

1. **理解需求**：分析用户请求，确定执行步骤
2. **执行操作**：使用合适的工具完成任务
3. **验证结果**：确认操作结果符合预期
4. **返回响应**：向用户报告执行结果

## 注意事项

- 每一步操作前确认参数正确
- 遇到错误时给出清晰的错误说明
- 记录关键操作日志
""",
    },
}


@app.post("/v1/skills/ai-generate")
async def ai_generate_skill(req: SkillAiGenerateRequest) -> dict:
    """根据名称和描述生成 Skill 模板（返回 SKILL.md 内容，不写盘）。

    使用预设模板 + 智能匹配，不依赖外部 LLM。
    """
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name 不能为空")

    description = req.description.strip()
    if not description:
        raise HTTPException(status_code=400, detail="description 不能为空")

    # 智能匹配模板
    desc_lower = description.lower()
    if any(kw in desc_lower for kw in ["文件", "读取", "写入", "转换", "合并", "分割", "file"]):
        template = _SKILL_TEMPLATES["文件处理"]
    elif any(kw in desc_lower for kw in ["分析", "统计", "数据", "图表", "可视化", "analy"]):
        template = _SKILL_TEMPLATES["数据分析"]
    elif any(kw in desc_lower for kw in ["api", "接口", "请求", "调用", "http"]):
        template = _SKILL_TEMPLATES["API 调用"]
    else:
        template = _SKILL_TEMPLATES["通用"]

    trigger = req.trigger.strip() or template["trigger"]
    tools = req.tools.strip() or template["tools"]

    # 生成 SKILL.md 内容
    content = f"""---
name: {name}
description: {description}
version: 1
trigger: {trigger}
tools: {tools}
---

# {name}

{template["body_template"]}
"""

    return {
        "name": name,
        "description": description,
        "content": content,
        "template_type": next(k for k, v in _SKILL_TEMPLATES.items() if v is template),
    }


# ── 工具分类映射（用于 /v1/tools 接口返回 category 字段）──
_TOOL_CATEGORIES = {
    "builtin": {
        "read_file": "文件操作", "write_file": "文件操作", "edit_file": "文件操作",
        "list_dir": "文件操作", "make_dir": "文件操作", "copy_file": "文件操作",
        "move_file": "文件操作",
        "run_shell": "Shell",
        "grep_search": "代码搜索", "glob_find": "代码搜索",
        "git_status": "Git", "git_diff": "Git", "git_commit": "Git", "git_log": "Git",
        "web_search": "浏览器", "web_fetch": "浏览器",
        "ast_parse": "代码分析",
        "todo_read": "任务管理", "todo_write": "任务管理",
    },
}


@app.get("/v1/tools")
async def list_tools() -> dict:
    """列出所有工具（内置 + 记忆 + 自定义 + MCP），含分类和参数 schema。"""
    _, _, registry, *_ = app.state.components
    out = []

    # 内置 + 自定义工具
    for name, t in registry._tools.items():
        schema = t.to_schema()
        is_builtin = _is_builtin_tool(name)
        if is_builtin:
            source = "builtin"
            category = _TOOL_CATEGORIES["builtin"].get(name, "其他")
        else:
            source = "custom"
            category = "自定义工具"
        # 记忆工具单独归类
        if name.startswith("memory_"):
            source = "memory"
            category = "记忆"
        out.append({
            "name": schema["function"]["name"],
            "description": schema["function"]["description"],
            "source": source,
            "category": category,
            "parameters": schema["function"].get("parameters", {}),
        })

    # MCP 工具
    for name, a in registry._mcp_tools.items():
        schema = a.to_schema()
        server_name = a._server_name
        out.append({
            "name": schema["function"]["name"],
            "description": schema["function"]["description"],
            "source": f"mcp:{server_name}",
            "category": "MCP",
            "parameters": schema["function"].get("parameters", {}),
        })

    return {"tools": out}


@app.get("/v1/mcps")
async def list_mcps() -> dict:
    """列出所有 MCP server + 工具 + 来源文件 + 启停状态。"""
    _, _, _, _, _, mcp, *_ = app.state.components
    servers = []
    for cfg_item in mcp._configs:
        server_tools = [
            a._tool_name for a in mcp._tools if a._server_name == cfg_item.name
        ]
        servers.append({
            "name": cfg_item.name,
            "transport": cfg_item.transport,
            "source_file": cfg_item.source_file,
            "enabled": cfg_item.enabled,
            "connected": cfg_item.name in mcp._transports,
            "tool_count": len(server_tools),
            "tools": server_tools,
        })
    return {
        "servers": servers,
        "total_servers": len(servers),
        "total_tools": sum(s["tool_count"] for s in servers),
    }


@app.post("/v1/reload")
async def v1_reload() -> dict:
    """重扫 tools/ 和 mcps/，返回加载报告。"""
    cfg, _, registry, _, _, mcp, *_ = app.state.components
    custom_tools_loader = app.state.components[9]
    return await reload_all(registry, custom_tools_loader, mcp, cfg.mcps_dir)


# ========== MCP 管理 CRUD API ==========

class McpServerRequest(BaseModel):
    """创建/更新 MCP 服务器的请求体。"""
    name: str
    transport: str  # stdio | sse | streamable-http
    command: str = ""
    url: str = ""
    headers: dict = {}
    enabled: bool = True
    timeout: int = 30
    tool_allowlist: list[str] = []
    tool_denylist: list[str] = []


def _mcp_yaml_path(name: str) -> Path:
    """根据 server name 推导 YAML 配置文件路径。"""
    cfg = app.state.components[0]
    return cfg.mcps_dir / f"{name}.yaml"


def _write_mcp_yaml(name: str, data: dict) -> Path:
    """将 MCP 配置写入 YAML 文件（原子写）。"""
    import yaml as _yaml
    path = _mcp_yaml_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".yaml.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        _yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    import os
    os.replace(tmp, path)
    return path


@app.post("/v1/mcps")
async def create_mcp_server(req: McpServerRequest) -> dict:
    """创建新的 MCP 服务器配置。"""
    import re
    if not re.match(r"^[a-zA-Z0-9_-]+$", req.name):
        raise HTTPException(status_code=400, detail="名称只能包含字母、数字、下划线和连字符")
    if req.transport not in ("stdio", "sse", "streamable-http"):
        raise HTTPException(status_code=400, detail=f"不支持的 transport：{req.transport}")
    if req.transport == "stdio" and not req.command:
        raise HTTPException(status_code=400, detail="stdio transport 必须指定 command")
    if req.transport in ("sse", "streamable-http") and not req.url:
        raise HTTPException(status_code=400, detail=f"{req.transport} transport 必须指定 url")

    path = _mcp_yaml_path(req.name)
    if path.exists():
        raise HTTPException(status_code=409, detail=f"MCP 服务器已存在：{req.name}")

    # 构建 YAML 数据
    data = {
        "name": req.name,
        "transport": req.transport,
        "enabled": req.enabled,
        "timeout": req.timeout,
    }
    if req.transport == "stdio":
        data["command"] = req.command
    else:
        data["url"] = req.url
    if req.headers:
        data["headers"] = req.headers
    if req.tool_allowlist:
        data["tool_allowlist"] = req.tool_allowlist
    if req.tool_denylist:
        data["tool_denylist"] = req.tool_denylist

    _write_mcp_yaml(req.name, data)

    # 重载所有 MCP
    cfg, _, registry, _, _, mcp, *_ = app.state.components
    for name in list(registry._mcp_tools):
        registry._mcp_tools.pop(name, None)
    new_configs, mcp_errors = load_mcp_configs(cfg.mcps_dir)
    mcp._configs = new_configs
    await mcp.reload()
    for tool in await mcp.get_tools():
        registry.register_mcp_tool(tool)

    errors_msg = ""
    if mcp_errors:
        errors_msg = "; ".join(e["error"] for e in mcp_errors)

    return {"message": f"已创建 MCP 服务器：{req.name}", "name": req.name, "errors": errors_msg}


@app.put("/v1/mcps/{name}")
async def update_mcp_server(name: str, req: McpServerRequest) -> dict:
    """更新现有 MCP 服务器配置。"""
    path = _mcp_yaml_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"MCP 服务器不存在：{name}")
    if req.transport not in ("stdio", "sse", "streamable-http"):
        raise HTTPException(status_code=400, detail=f"不支持的 transport：{req.transport}")
    if req.transport == "stdio" and not req.command:
        raise HTTPException(status_code=400, detail="stdio transport 必须指定 command")
    if req.transport in ("sse", "streamable-http") and not req.url:
        raise HTTPException(status_code=400, detail=f"{req.transport} transport 必须指定 url")

    data = {
        "name": name,
        "transport": req.transport,
        "enabled": req.enabled,
        "timeout": req.timeout,
    }
    if req.transport == "stdio":
        data["command"] = req.command
    else:
        data["url"] = req.url
    if req.headers:
        data["headers"] = req.headers
    if req.tool_allowlist:
        data["tool_allowlist"] = req.tool_allowlist
    if req.tool_denylist:
        data["tool_denylist"] = req.tool_denylist

    _write_mcp_yaml(name, data)

    # 重载
    cfg, _, registry, _, _, mcp, *_ = app.state.components
    for n in list(registry._mcp_tools):
        registry._mcp_tools.pop(n, None)
    new_configs, mcp_errors = load_mcp_configs(cfg.mcps_dir)
    mcp._configs = new_configs
    await mcp.reload()
    for tool in await mcp.get_tools():
        registry.register_mcp_tool(tool)

    return {"message": f"已更新 MCP 服务器：{name}", "name": name}


@app.delete("/v1/mcps/{name}", status_code=204, response_model=None)
async def delete_mcp_server(name: str) -> None:
    """删除 MCP 服务器配置文件。"""
    path = _mcp_yaml_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"MCP 服务器不存在：{name}")

    import os
    os.remove(path)

    # 重载
    cfg, _, registry, _, _, mcp, *_ = app.state.components
    for n in list(registry._mcp_tools):
        registry._mcp_tools.pop(n, None)
    new_configs, _ = load_mcp_configs(cfg.mcps_dir)
    mcp._configs = new_configs
    await mcp.reload()
    for tool in await mcp.get_tools():
        registry.register_mcp_tool(tool)


@app.post("/v1/mcps/{name}/toggle")
async def toggle_mcp_server(name: str) -> dict:
    """切换 MCP 服务器启用/禁用状态。"""
    import yaml as _yaml
    path = _mcp_yaml_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"MCP 服务器不存在：{name}")

    raw = _yaml.safe_load(path.read_text(encoding="utf-8"))
    current = bool(raw.get("enabled", True))
    raw["enabled"] = not current
    _write_mcp_yaml(name, raw)

    # 重载
    cfg, _, registry, _, _, mcp, *_ = app.state.components
    for n in list(registry._mcp_tools):
        registry._mcp_tools.pop(n, None)
    new_configs, _ = load_mcp_configs(cfg.mcps_dir)
    mcp._configs = new_configs
    await mcp.reload()
    for tool in await mcp.get_tools():
        registry.register_mcp_tool(tool)

    return {"name": name, "enabled": not current, "message": f"已{'启用' if not current else '禁用'} {name}"}


@app.post("/v1/mcps/{name}/test")
async def test_mcp_server(name: str) -> dict:
    """测试 MCP 服务器连接（尝试建立连接并列出工具）。"""
    from open_fox.core.mcp.client import _make_transport
    cfg = app.state.components[0]
    _, _, _, _, _, mcp, *_ = app.state.components

    # 从内存中找配置
    target_cfg = None
    for c in mcp._configs:
        if c.name == name:
            target_cfg = c
            break
    if target_cfg is None:
        raise HTTPException(status_code=404, detail=f"MCP 服务器不存在：{name}")

    try:
        t = _make_transport(target_cfg)
        await t.connect()
        tools = await t.list_tools()
        await t.close()
        return {
            "name": name,
            "success": True,
            "tool_count": len(tools),
            "tools": [tm["name"] for tm in tools],
            "message": f"连接成功，发现 {len(tools)} 个工具",
        }
    except Exception as e:
        return {
            "name": name,
            "success": False,
            "tool_count": 0,
            "tools": [],
            "message": f"连接失败：{e}",
        }


@app.get("/v1/mcps/{name}/tools")
async def get_mcp_server_tools(name: str) -> dict:
    """获取 MCP 服务器的工具详情（含 schema）。"""
    _, _, _, _, _, mcp, *_ = app.state.components
    tools = []
    for t in mcp._tools:
        if t._server_name == name:
            schema = t.to_schema()
            tools.append({
                "name": t._tool_name,
                "full_name": t.name,
                "description": t._description,
                "parameters": schema["function"]["parameters"],
            })
    return {"name": name, "tools": tools, "count": len(tools)}


@app.get("/v1/mcps/{name}/detail")
async def get_mcp_server_detail(name: str) -> dict:
    """获取 MCP 服务器的完整配置详情（含 command/url/headers 等敏感字段）。

    用于编辑时回填表单。直接从 YAML 文件读取，确保返回最新配置。
    """
    import yaml as _yaml
    path = _mcp_yaml_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"MCP 服务器不存在：{name}")

    raw = _yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise HTTPException(status_code=500, detail=f"配置文件格式异常：{path}")

    return {
        "name": raw.get("name", name),
        "transport": raw.get("transport", ""),
        "command": raw.get("command", ""),
        "url": raw.get("url", ""),
        "headers": raw.get("headers", {}) or {},
        "enabled": raw.get("enabled", True),
        "timeout": raw.get("timeout", 30),
        "tool_allowlist": raw.get("tool_allowlist", []) or [],
        "tool_denylist": raw.get("tool_denylist", []) or [],
        "source_file": str(path),
    }


class McpImportRequest(BaseModel):
    """通过 YAML/JSON 文本导入 MCP 服务器配置。"""
    content: str
    format: str = "yaml"  # yaml | json


@app.post("/v1/mcps/import")
async def import_mcp_server(req: McpImportRequest) -> dict:
    """从 YAML/JSON 文本导入 MCP 服务器配置。

    支持用户粘贴配置文本快速导入。会校验格式并解析。
    """
    import re
    import yaml as _yaml

    try:
        if req.format == "json":
            raw = json.loads(req.content)
        else:
            raw = _yaml.safe_load(req.content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"配置解析失败：{e}") from e

    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="配置根必须是对象")

    name = raw.get("name", "")
    if not name or not re.match(r"^[a-zA-Z0-9_-]+$", str(name)):
        raise HTTPException(status_code=400, detail="name 字段缺失或格式错误（只能包含字母、数字、下划线和连字符）")

    transport = raw.get("transport", "")
    if transport not in ("stdio", "sse", "streamable-http"):
        raise HTTPException(status_code=400, detail=f"不支持的 transport：{transport}")
    if transport == "stdio" and not raw.get("command"):
        raise HTTPException(status_code=400, detail="stdio transport 必须指定 command")
    if transport in ("sse", "streamable-http") and not raw.get("url"):
        raise HTTPException(status_code=400, detail=f"{transport} transport 必须指定 url")

    path = _mcp_yaml_path(name)
    if path.exists():
        raise HTTPException(status_code=409, detail=f"MCP 服务器已存在：{name}")

    _write_mcp_yaml(name, raw)

    # 重载
    cfg, _, registry, _, _, mcp, *_ = app.state.components
    for n in list(registry._mcp_tools):
        registry._mcp_tools.pop(n, None)
    new_configs, mcp_errors = load_mcp_configs(cfg.mcps_dir)
    mcp._configs = new_configs
    await mcp.reload()
    for tool in await mcp.get_tools():
        registry.register_mcp_tool(tool)

    errors_msg = ""
    if mcp_errors:
        errors_msg = "; ".join(e["error"] for e in mcp_errors)

    return {"message": f"已导入 MCP 服务器：{name}", "name": name, "errors": errors_msg}


@app.get("/healthz")
async def health() -> dict:
    cfg, adapter, registry, loader, *_ = app.state.components
    return {
        "status": "ok",
        "active_model": adapter.active,
        "skills_count": len(loader.all()),
        "tools_count": len(registry.list_tool_schemas()),
        "storage": cfg.storage.backend,
    }


# ========== 上下文状态 API ==========

@app.get("/v1/context/status")
async def context_status(request: Request) -> dict:
    """返回当前用户的上下文使用状态。"""
    cfg, adapter, registry, loader, *_ = app.state.components
    user = _username(request)

    # 尝试获取最近活跃的 loop 实例的上下文快照
    # 如果没有活跃 loop，则构建一次即时快照
    from open_fox.core.context.context_breakdown import ContextBreakdown
    from open_fox.core.context.token_estimator import get_model_context_window

    # 从会话中获取最近消息来估算
    user_sessions_dir = Path(cfg.storage.json_dir) / "sessions" / user
    session_files = []
    if user_sessions_dir.exists():
        session_files = sorted(
            user_sessions_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

    # 获取当前模型名和上下文窗口
    model_name = adapter.active or ""
    context_window = cfg.compression.context_window or get_model_context_window(model_name)

    # 返回配置和估算信息
    return {
        "model": model_name,
        "context_window": context_window,
        "compression": {
            "enabled": cfg.compression.enabled,
            "threshold": cfg.compression.threshold,
            "target_ratio": cfg.compression.target_ratio,
            "protect_first_n": cfg.compression.protect_first_n,
            "protect_last_n": cfg.compression.protect_last_n,
        },
        "available_sessions": len(session_files),
    }


@app.post("/v1/context/compact")
async def context_compact(request: Request) -> dict:
    """手动触发上下文压缩（/compact 命令）。"""
    cfg, adapter, *_ = app.state.components
    user = _username(request)

    compressor = _build_server_compressor(cfg, adapter)
    if not compressor:
        return {"success": False, "error": "Context compression is disabled"}

    # 找到最近活跃的会话消息
    user_sessions_dir = Path(cfg.storage.json_dir) / "sessions" / user
    if not user_sessions_dir.exists():
        return {"success": False, "error": "No sessions found"}

    session_files = sorted(
        user_sessions_dir.glob("*.json"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    if not session_files:
        return {"success": False, "error": "No sessions found"}

    # 读取最近会话的消息
    import json as _json
    session_data = _json.loads(session_files[0].read_text(encoding="utf-8"))
    messages = session_data if isinstance(session_data, list) else session_data.get("messages", [])

    if not messages:
        return {"success": False, "error": "No messages to compress"}

    # 检查是否需要压缩
    should, snapshot = compressor.should_compress(messages, model_name=adapter.active or "")
    if not should:
        return {
            "success": False,
            "skipped": True,
            "reason": "Context is below compression threshold",
            "current_tokens": snapshot.total_tokens,
            "threshold": int(snapshot.effective_budget * cfg.compression.threshold),
        }

    # 执行压缩
    compressed_messages, result = await compressor.compress(
        messages, model_name=adapter.active or ""
    )

    # 如果压缩成功，写回会话文件
    if result.success:
        if isinstance(session_data, list):
            session_files[0].write_text(
                _json.dumps(compressed_messages, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        else:
            session_data["messages"] = compressed_messages
            session_files[0].write_text(
                _json.dumps(session_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    return {
        "success": result.success,
        "method": result.method,
        "original_tokens": result.original_tokens,
        "compressed_tokens": result.compressed_tokens,
        "savings_percent": round(result.savings_percent, 1),
        "messages_before": result.messages_before,
        "messages_after": result.messages_after,
        "error": result.error,
    }


# ========== 智能体 CRUD API ==========

class AgentCreateRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    model: str = ""
    system_prompt: str = ""
    tools: list[str] = []
    skills: list[str] = []
    temperature: float | None = None
    max_steps: int = 500


class AgentUpdateRequest(BaseModel):
    """部分更新模型：所有字段可选，只合并传入字段。"""

    id: str | None = None
    name: str | None = None
    description: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    tools: list[str] | None = None
    skills: list[str] | None = None
    temperature: float | None = None
    max_steps: int | None = None


def _available_models() -> list[str]:
    """返回所有已配置模型名。"""
    cfg = app.state.components[0]
    return [m.name for m in cfg.models]


@app.get("/v1/agents")
async def list_agents(request: Request) -> dict:
    current_user = _username(request)
    agent_store = app.state.components[7]
    agents = agent_store.list()
    # 按用户过滤：owner 为空（全局）或属于当前用户
    filtered = [a for a in agents if a.owner in ("", current_user)]
    return {"agents": [a.to_dict() for a in filtered]}


@app.post("/v1/agents")
async def create_agent(request: Request, req: AgentCreateRequest) -> dict:
    current_user = _username(request)
    agent_store = app.state.components[7]
    agent = AgentConfig(**req.model_dump())
    agent.owner = current_user  # 自动绑定所属用户
    errors = validate_agent(agent, _available_models())
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    try:
        return agent_store.create(agent).to_dict()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/v1/agents/{agent_id}")
async def get_agent(agent_id: str) -> dict:
    agent_store = app.state.components[7]
    agent = agent_store.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="智能体不存在")
    return agent.to_dict()


@app.put("/v1/agents/{agent_id}")
async def update_agent(agent_id: str, req: AgentUpdateRequest) -> dict:
    agent_store = app.state.components[7]
    existing = agent_store.get(agent_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="智能体不存在")
    # 部分更新：把请求字段合并到现有智能体上，形成完整配置
    data = {k: v for k, v in req.model_dump(exclude_none=True).items() if k != "id"}
    for k, v in data.items():
        setattr(existing, k, v)
    # 用合并后的完整智能体做校验，避免写入非法 model 后 agent-chat 在
    # adapter.set_active(agent.model) 处抛 ValueError 导致 500
    errors = validate_agent(existing, _available_models())
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    return agent_store.update(agent_id, data).to_dict()


@app.get("/v1/agents/{agent_id}/test")
async def test_agent(agent_id: str) -> dict:
    """测试智能体配置连通性（验证绑定模型是否在可用模型列表中）。

    注意：仅做配置校验，不实际调用上游 LLM，避免测试产生真实请求与消耗。
    """
    agent_store = app.state.components[7]
    adapter = app.state.components[1]
    agent = agent_store.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="智能体不存在")
    if agent.model:
        if agent.model not in adapter.list_models():
            return {"ok": False, "message": f"模型 '{agent.model}' 不在可用模型列表中"}
        return {"ok": True, "message": f"模型 '{agent.model}' 可用"}
    # 未绑定模型：使用全局默认模型
    default_model = adapter.active
    return {"ok": True, "message": f"使用全局默认模型 '{default_model}'"}


@app.delete("/v1/agents/{agent_id}", status_code=204, response_model=None)
async def delete_agent(agent_id: str) -> None:
    agent_store = app.state.components[7]
    agent_store.delete(agent_id)


# ========== 按智能体聊天 API ==========

class AgentChatRequest(BaseModel):
    session_id: str
    agent_id: str
    message: str
    model: str | None = None  # 用户在聊天界面选择的模型（优先于智能体配置）


@app.post("/v1/agent-chat")
async def agent_chat(request: Request, req: AgentChatRequest) -> dict:
    username = _username(request)
    token = set_current_user(username)
    try:
        (cfg, adapter, registry, loader, storage, mcp, runner,
         agent_store, memory_pool, _, _) = app.state.components
        usage_store = app.state.usage_store
        # 获取当前用户的 MemoryManager
        memory_manager = await memory_pool.get(username)

        agent = agent_store.get(req.agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="智能体不存在")
        if not req.message.strip():
            raise HTTPException(status_code=400, detail="消息不能为空")

        # 按智能体配置过滤工具/技能
        agent_registry = filter_registry(agent, registry)
        agent_skills = filter_skills(agent, loader.all())

        # 会话（复用/新建），写入元数据
        session = Session(session_id=req.session_id, storage=storage,
                          active_model=agent.model or adapter.active)
        session.load()
        if not session.get_meta():
            session.set_meta(agent_id=agent.id, title=f"{agent.name} 会话",
                             model=agent.model or adapter.active,
                             temperature=agent.temperature,
                             owner=username)

        # 切模型：用户在聊天界面选择的模型优先于智能体配置
        target_model = req.model or agent.model
        if target_model:
            adapter.set_active(target_model)
        _check_api_key(adapter)

        # 包装 adapter.chat 捕获最后一次调用的真实 usage（参照 /v1/chat）
        last_usage: dict | None = None
        original_chat = adapter.chat

        async def instrumented_chat(messages, tools=None, stream=False, temperature=None):
            nonlocal last_usage
            response = await original_chat(messages, tools=tools, stream=stream,
                                           temperature=temperature)
            from open_fox.core.adapters.base import AssistantMessage as _AM
            if isinstance(response, _AM) and response.usage:
                u = response.usage
                last_usage = {
                    "prompt_tokens": u.prompt_tokens,
                    "completion_tokens": u.completion_tokens,
                    "total_tokens": u.total_tokens,
                    "cache_hit_tokens": u.cache_hit_tokens,
                    "cache_miss_tokens": u.cache_miss_tokens,
                    "reasoning_tokens": u.reasoning_tokens,
                }
            return response

        adapter.chat = instrumented_chat
        try:
            compressor = _build_server_compressor(cfg, adapter)
            # 获取会话关联的工作目录
            session_workdir = _get_session_workdir(session, app.state.components)
            # 构建会话级工具（PathGuard 白名单 + Shell cwd 锁定）
            _build_session_tools(cfg, session_workdir, registry)
            loop = AgentLoop(
                adapter=adapter,
                registry=agent_registry,
                session=session,
                script_runner=runner,
                skills=agent_skills,
                max_steps=agent.max_steps or cfg.max_agent_steps,
                temperature=agent.temperature,
                extra_system_prompt=agent.system_prompt,
                memory_manager=memory_manager,
                compressor=compressor,
                workdir=session_workdir,
            )
            reply = await loop.run(req.message)
        finally:
            adapter.chat = original_chat

        session.save()

        # 隐式记忆抽取：AgentLoop.run() 完成后 fire-and-forget 通知（内部 _should_extract 过滤）
        extractor = getattr(app.state, "extractor", None)
        if extractor is not None:
            await extractor.notify(session.get_messages(), bool(loop.tool_trace), username)

        # Skill 进化：AgentLoop.run() 完成后通知（内部节流/触发判定过滤）
        evolution_task = getattr(app.state, "evolution_task", None)
        if evolution_task is not None:
            await evolution_task.notify(req.session_id, session.get_messages(), loop.tool_trace)

        # 用量记录
        au = loop.accumulated_usage
        usage_store.record(
            username=username,
            model=adapter.active,
            prompt_tokens=au.prompt_tokens,
            completion_tokens=au.completion_tokens,
            total_tokens=au.total_tokens,
            cache_hit_tokens=au.cache_hit_tokens,
            reasoning_tokens=au.reasoning_tokens,
            session_id=req.session_id,
            agent_id=req.agent_id,
        )

        return {
            "session_id": req.session_id,
            "agent_id": agent.id,
            "reply": reply,
            "usage": last_usage if last_usage else {},
            "tool_trace": loop.tool_trace,
        }
    finally:
        from open_fox.core.memory.manager import _current_user as _ctx_var
        _ctx_var.reset(token)


# ========== 项目管理 API ==========

class ProjectCreateRequest(BaseModel):
    workdir: str
    name: str = ""


class ProjectRenameRequest(BaseModel):
    name: str


class ProjectPinRequest(BaseModel):
    pinned: bool


@app.get("/v1/projects")
async def list_projects(request: Request) -> dict:
    current_user = _username(request)
    project_store: ProjectStore = app.state.components[10]
    projects = project_store.list(owner=current_user)
    return {"projects": projects}


@app.post("/v1/projects")
async def create_project(request: Request, req: ProjectCreateRequest) -> dict:
    current_user = _username(request)
    project_store: ProjectStore = app.state.components[10]
    if not req.workdir or not Path(req.workdir).exists():
        raise HTTPException(status_code=400, detail="工作目录不存在")
    project = project_store.create(workdir=req.workdir, name=req.name or None,
                                   owner=current_user)
    return project


@app.get("/v1/projects/{project_id}")
async def get_project(project_id: str) -> dict:
    project_store: ProjectStore = app.state.components[10]
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@app.delete("/v1/projects/{project_id}")
async def delete_project(project_id: str) -> dict:
    project_store: ProjectStore = app.state.components[10]
    deleted = project_store.delete(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"deleted": True}


@app.put("/v1/projects/{project_id}")
async def rename_project(project_id: str, req: ProjectRenameRequest) -> dict:
    project_store: ProjectStore = app.state.components[10]
    project = project_store.rename(project_id, req.name)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@app.put("/v1/projects/{project_id}/pin")
async def pin_project(project_id: str, req: ProjectPinRequest) -> dict:
    project_store: ProjectStore = app.state.components[10]
    project = project_store.set_pinned(project_id, req.pinned)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@app.delete("/v1/projects/{project_id}/cascade")
async def delete_project_cascade(request: Request, project_id: str) -> dict:
    """删除项目并级联删除其下所有会话。"""
    project_store: ProjectStore = app.state.components[10]
    project = project_store.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    current_user = _username(request)
    _, _, _, _, storage, *_ = app.state.components
    # 找到该 project 下的所有会话并删除
    deleted_sessions = []
    for sid in storage.list_ids():
        s = Session(session_id=sid, storage=storage)
        s.load()
        meta = s.get_meta()
        owner = meta.get("owner", "Ciel")
        if owner != current_user:
            continue
        if meta.get("project_id") == project_id:
            storage.delete(sid)
            deleted_sessions.append(sid)
    project_store.delete(project_id)
    return {"deleted": True, "sessions_removed": len(deleted_sessions),
            "session_ids": deleted_sessions}


# ========== 会话管理 API ==========

class SessionCreateRequest(BaseModel):
    id: str | None = None
    agent_id: str = ""
    title: str = ""
    project_id: str = ""


class SessionUpdateRequest(BaseModel):
    title: str | None = None
    project_id: str | None = None
    pinned: bool | None = None


@app.get("/v1/sessions")
async def list_sessions(request: Request) -> dict:
    current_user = _username(request)
    _, _, _, _, storage, *_ = app.state.components
    sessions = []
    for sid in storage.list_ids():
        s = Session(session_id=sid, storage=storage)
        s.load()
        meta = s.get_meta()
        # 按用户过滤：旧会话无 owner 默认归 Ciel
        owner = meta.get("owner", "Ciel")
        if owner != current_user:
            continue
        sessions.append({
            "id": sid,
            "agent_id": meta.get("agent_id") or DEFAULT_AGENT_ID,
            "agent_name": meta.get("agent_name") or DEFAULT_AGENT_NAME,
            "title": meta.get("title", ""),
            "model": meta.get("model", ""),
            "temperature": meta.get("temperature"),
            "created_at": meta.get("created_at", ""),
            "project_id": meta.get("project_id", ""),
            "pinned": meta.get("pinned", False),
            "message_count": len([m for m in s.chat_messages()
                                  if m["role"] in ("user", "assistant")]),
        })
    return {"sessions": sessions}


@app.post("/v1/sessions")
async def create_session(request: Request, req: SessionCreateRequest) -> dict:
    current_user = _username(request)
    _, _, _, _, storage, *_ = app.state.components
    sid = req.id or f"s-{uuid.uuid4().hex[:12]}"
    session = Session(session_id=sid, storage=storage)
    created_at = datetime.now(timezone.utc).isoformat()
    agent_id = req.agent_id or DEFAULT_AGENT_ID
    session.set_meta(
        agent_id=agent_id,
        agent_name=DEFAULT_AGENT_NAME if agent_id == DEFAULT_AGENT_ID else agent_id,
        title=req.title or "新会话",
        created_at=created_at,
        owner=current_user,
        project_id=req.project_id,
    )
    session.save()
    return {"id": sid, "agent_id": agent_id, "title": req.title or "新会话",
            "project_id": req.project_id}


@app.get("/v1/sessions/{session_id}/messages")
async def session_messages(session_id: str) -> dict:
    _, _, _, _, storage, *_ = app.state.components
    s = Session(session_id=session_id, storage=storage)
    s.load()
    meta = s.get_meta()
    return {
        "messages": s.chat_messages(),
        "agent_id": meta.get("agent_id") or DEFAULT_AGENT_ID,
        "agent_name": meta.get("agent_name") or DEFAULT_AGENT_NAME,
    }


@app.put("/v1/sessions/{session_id}")
async def update_session(session_id: str, req: SessionUpdateRequest) -> dict:
    _, _, _, _, storage, *_ = app.state.components
    s = Session(session_id=session_id, storage=storage)
    s.load()
    meta = s.get_meta()
    if not meta:
        raise HTTPException(status_code=404, detail="会话不存在")
    if req.title is not None:
        s.set_meta(title=req.title)
    if req.project_id is not None:
        s.set_meta(project_id=req.project_id)
    if req.pinned is not None:
        s.set_meta(pinned=req.pinned)
    s.save()
    meta = s.get_meta()
    return {"id": session_id, "title": meta.get("title", ""),
            "project_id": meta.get("project_id", ""),
            "pinned": meta.get("pinned", False)}


@app.delete("/v1/sessions/{session_id}", status_code=204, response_model=None)
async def delete_session(session_id: str) -> None:
    _, _, _, _, storage, *_ = app.state.components
    storage.delete(session_id)


# ========== Skill 进化 API ==========

@app.get("/v1/evolution/pending")
async def evolution_pending() -> dict:
    """列出待确认的 Skill 进化候选。"""
    queue = app.state.evolution_task.queue
    return {"pending": [asdict(i) for i in queue.list("pending")]}


@app.post("/v1/evolution/pending/{item_id}/confirm")
async def evolution_confirm(item_id: str) -> dict:
    """用户确认后写入 Skill 库（校验 + 版本快照 + 变更日志）。"""
    queue = app.state.evolution_task.queue
    manager = app.state.evolution_task.manager
    item = queue.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="候选不存在")
    if item.status != "pending":
        raise HTTPException(status_code=400, detail=f"候选已处理：{item.status}")
    try:
        summary = await manager.apply_candidate(item.action, item.skill_name, item.content)
    except SkillValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await queue.mark_status(item_id, "confirmed")
    # 写盘后定向 rescan，让 chat 端点（用 loader.all() 内存快照）立即看到新 skill
    app.state.components[3].rescan()
    # 冷却：防止修复后立即再次建议同一 skill
    tracker = app.state.evolution_task.tracker
    cfg = app.state.components[0]
    tracker.skill_stats(item.skill_name).cooldown_until_turn = \
        tracker.turn() + cfg.skill_evolution.cooldown_turns
    await tracker.save()
    return {"id": item_id, "summary": summary}


@app.post("/v1/evolution/pending/{item_id}/reject")
async def evolution_reject(item_id: str) -> dict:
    """拒绝候选并进入冷却，避免反复建议。"""
    queue = app.state.evolution_task.queue
    tracker = app.state.evolution_task.tracker
    item = queue.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="候选不存在")
    if item.status != "pending":
        raise HTTPException(status_code=400, detail=f"候选已处理：{item.status}")
    await queue.mark_status(item_id, "rejected")
    cfg = app.state.components[0]
    tracker.skill_stats(item.skill_name).cooldown_until_turn = \
        tracker.turn() + cfg.skill_evolution.cooldown_turns
    await tracker.save()
    return {"id": item_id, "status": "rejected"}


# ========== OpenAI Chat Completions 兼容 API ==========

class OAChatRequest(BaseModel):
    """OpenAI Chat Completions 标准请求体。"""

    model: str
    messages: list[dict]
    tools: list[dict] | None = None
    tool_choice: str | dict | None = None
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    # 非标准字段（用于会话隔离）
    user: str | None = None  # 作为 session_id


def _resolve_session_id(req_user: str | None) -> str:
    """从请求头/字段提取 session_id。"""
    if req_user:
        return req_user
    return f"oai-{uuid.uuid4().hex[:16]}"


@app.get("/v1/models")
async def list_models() -> dict:
    """OpenAI 标准 /v1/models 端点。"""
    cfg, adapter, *_ = app.state.components
    return {
        "object": "list",
        "data": [
            {
                "id": m,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "openfox",
            }
            for m in adapter.list_models()
        ],
    }


# ========== 模型配置管理 API ==========

class ModelCreateRequest(BaseModel):
    name: str
    base_url: str
    model: str
    api_key: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    retry_count: int | None = None


class ModelUpdateRequest(BaseModel):
    """部分更新：所有字段可选，只合并传入字段。"""
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    retry_count: int | None = None


@app.get("/v1/models/detail")
async def list_model_details() -> dict:
    """返回模型完整配置列表（不含 api_key 明文），供管理页面使用。"""
    model_store = app.state.model_store
    adapter = app.state.components[1]
    return {
        "models": model_store.list(),
        "active_model": adapter.active,
    }


class FetchModelsRequest(BaseModel):
    """拉取供应商可用模型列表请求。"""
    base_url: str
    api_key: str = ""


@app.post("/v1/models/fetch")
async def fetch_available_models(req: FetchModelsRequest) -> dict:
    """用指定 base_url + api_key 调用供应商的 /v1/models 接口，返回可用模型列表。"""
    url = req.base_url.rstrip("/")
    # 兼容各种供应商的模型列表端点
    models_url = f"{url}/models"
    headers = {"Content-Type": "application/json"}
    if req.api_key:
        headers["Authorization"] = f"Bearer {req.api_key}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(models_url, headers=headers)
        if resp.status_code != 200:
            return {"ok": False, "message": f"上游返回 {resp.status_code}", "models": []}
        data = resp.json()
        # OpenAI 标准 /v1/models 返回 { object: "list", data: [...] }
        if isinstance(data, dict) and "data" in data:
            model_ids = [m.get("id", "") for m in data["data"] if m.get("id")]
        elif isinstance(data, list):
            model_ids = [m.get("id", str(m)) if isinstance(m, dict) else str(m) for m in data]
        else:
            model_ids = []
        return {"ok": True, "message": f"获取到 {len(model_ids)} 个模型", "models": sorted(model_ids)}
    except httpx.TimeoutException:
        return {"ok": False, "message": "连接超时（15s），请检查 API 地址和网络", "models": []}
    except httpx.ConnectError:
        return {"ok": False, "message": "无法连接，请检查 API 地址是否正确", "models": []}
    except Exception as e:
        return {"ok": False, "message": f"拉取失败：{e}", "models": []}


@app.post("/v1/models")
async def create_model(req: ModelCreateRequest) -> dict:
    """新增模型配置，同步更新内存中的 adapter。"""
    model_store = app.state.model_store
    cfg = app.state.components[0]
    adapter = app.state.components[1]
    try:
        result = model_store.create(req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    # 同步内存：构造 ModelConfig 并加入 adapter
    mc = ModelConfig(
        name=result["name"],
        base_url=result["base_url"],
        model=result["model"],
        api_key=result.get("api_key", ""),
        temperature=result.get("temperature"),
        max_tokens=result.get("max_tokens"),
        retry_count=result.get("retry_count"),
    )
    cfg.models.append(mc)
    adapter._models[mc.name] = mc
    return result


@app.put("/v1/models/{name}")
async def update_model(name: str, req: ModelUpdateRequest) -> dict:
    """更新模型配置（name 不可改），同步更新内存中的 adapter。"""
    model_store = app.state.model_store
    cfg = app.state.components[0]
    adapter = app.state.components[1]
    try:
        result = model_store.update(name, req.model_dump(exclude_none=True))
    except ValueError as e:
        msg = str(e)
        raise HTTPException(
            status_code=404 if "不存在" in msg else 409, detail=msg)
    # 同步内存 adapter
    if name in adapter._models:
        m = adapter._models[name]
        if result.get("base_url"):
            m.base_url = result["base_url"]
        if result.get("model"):
            m.model = result["model"]
        if "api_key" in result:
            m.api_key = result["api_key"]
        # 可选参数：含 key 即更新（允许显式置空）
        for k in ("temperature", "max_tokens", "retry_count"):
            if k in result:
                setattr(m, k, result[k])
    # 同步 cfg.models 列表
    for m in cfg.models:
        if m.name == name:
            if result.get("base_url"):
                m.base_url = result["base_url"]
            if result.get("model"):
                m.model = result["model"]
            if "api_key" in result:
                m.api_key = result["api_key"]
            for k in ("temperature", "max_tokens", "retry_count"):
                if k in result:
                    setattr(m, k, result[k])
            break
    return result


@app.delete("/v1/models/{name}", status_code=204, response_model=None)
async def delete_model(name: str) -> None:
    """删除模型配置，同步更新内存中的 adapter。"""
    model_store = app.state.model_store
    cfg = app.state.components[0]
    adapter = app.state.components[1]
    try:
        model_store.delete(name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    # 同步内存
    if name in adapter._models:
        del adapter._models[name]
    cfg.models = [m for m in cfg.models if m.name != name]
    # 删除的是当前激活模型 → 切换到剩余的第一个
    if adapter.active == name and adapter._models:
        adapter._active = next(iter(adapter._models))


@app.put("/v1/models/{name}/active")
async def set_active_model(name: str) -> dict:
    """将指定模型设为当前激活模型，同步内存 adapter 并持久化到 config.yaml。"""
    model_store = app.state.model_store
    adapter = app.state.components[1]
    cfg = app.state.components[0]
    try:
        model_store.set_active_model(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    adapter.set_active(name)
    cfg.active_model = name
    return {"active_model": name}


@app.post("/v1/models/{name}/test")
async def test_model(name: str) -> dict:
    """测试模型连通性：发送最小请求验证 API 可达性和密钥有效性。"""
    adapter = app.state.components[1]
    if name not in adapter._models:
        raise HTTPException(status_code=404, detail=f"模型 '{name}' 不存在")
    mc = adapter._models[name]
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{mc.base_url}/chat/completions",
                json={
                    "model": mc.model,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 5,
                    "stream": False,
                },
                headers={
                    "Authorization": f"Bearer {mc.api_key}",
                    "Content-Type": "application/json",
                },
            )
        if resp.status_code == 200:
            return {"ok": True, "message": "连接正常", "status": resp.status_code}
        # 常见错误码友好提示
        if resp.status_code == 401:
            detail = "密钥无效或已过期"
        elif resp.status_code == 404:
            detail = "模型标识不存在或 API 地址错误"
        elif resp.status_code == 429:
            detail = "请求频率超限（429）"
        else:
            detail = f"上游返回 {resp.status_code}"
        return {"ok": False, "message": detail, "status": resp.status_code}
    except httpx.TimeoutException:
        return {"ok": False, "message": "连接超时（15s），请检查 API 地址和网络"}
    except httpx.ConnectError:
        return {"ok": False, "message": "无法连接，请检查 API 地址是否正确"}
    except Exception as e:
        return {"ok": False, "message": f"拉取失败：{e}", "models": []}


# ========== 记忆管理 API ==========

class MemoryAddRequest(BaseModel):
    memory_type: str  # explicit | implicit
    section: str = ""
    content: str
    confidence: str = "低"  # 高/中/低


class MemoryUpdateRequest(BaseModel):
    target_content: str
    new_content: str
    memory_type: str = ""


class MemoryDeleteRequest(BaseModel):
    target_content: str
    archive: bool = True


async def _get_user_memory_manager(request: Request) -> MemoryManager:
    """根据当前请求用户获取对应的 MemoryManager。"""
    username = _username(request)
    memory_pool: MemoryManagerPool = app.state.components[8]
    return await memory_pool.get(username)


@app.get("/v1/memory")
async def get_memory(request: Request) -> dict:
    """返回完整记忆文档（显式 + 隐式 + 归档），结构化数据供管理页面。"""
    mgr = await _get_user_memory_manager(request)
    doc = mgr.document
    return {
        "explicit": [
            {"content": e.content, "meta": e.meta, "confidence": e.confidence}
            for e in doc.explicit
        ],
        "implicit": [
            {
                "name": s.name,
                "entries": [
                    {"content": e.content, "meta": e.meta, "confidence": e.confidence}
                    for e in s.entries
                ],
            }
            for s in doc.implicit
        ],
        "archive": [
            {"content": e.content, "meta": e.meta, "confidence": e.confidence}
            for e in doc.archive
        ],
    }


@app.post("/v1/memory")
async def add_memory(request: Request, req: MemoryAddRequest) -> dict:
    """新增一条记忆。"""
    mgr = await _get_user_memory_manager(request)
    try:
        msg = await mgr.add(
            req.memory_type, req.section, req.content, req.confidence,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": msg}


@app.put("/v1/memory")
async def update_memory(request: Request, req: MemoryUpdateRequest) -> dict:
    """更新一条记忆（旧内容移入归档）。"""
    mgr = await _get_user_memory_manager(request)
    try:
        msg = await mgr.update(
            req.target_content, req.new_content, req.memory_type,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": msg}


@app.delete("/v1/memory", status_code=204, response_model=None)
async def delete_memory(request: Request, req: MemoryDeleteRequest) -> None:
    """删除一条记忆。archive=true 归档，false 物理删除；显式记忆不可删。"""
    mgr = await _get_user_memory_manager(request)
    try:
        await mgr.delete(req.target_content, req.archive)
    except MemoryPermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== 用量管理 API ==========

@app.get("/v1/usage/records")
async def usage_records(
    request: Request,
    start_date: str = "",
    end_date: str = "",
    model: str = "",
    agent_id: str = "",
    limit: int = 500,
    offset: int = 0,
) -> dict:
    """查询当前用户的用量记录（分页）。"""
    username = _username(request)
    usage_store: UsageStore = app.state.usage_store
    records, total = usage_store.list_records(
        username=username,
        start_date=start_date,
        end_date=end_date,
        model=model,
        agent_id=agent_id,
        limit=limit,
        offset=offset,
    )
    return {"records": records, "total": total}


@app.get("/v1/usage/summary")
async def usage_summary(
    request: Request,
    start_date: str = "",
    end_date: str = "",
) -> dict:
    """查询当前用户的用量汇总统计。"""
    username = _username(request)
    usage_store: UsageStore = app.state.usage_store
    return usage_store.get_summary(
        username=username,
        start_date=start_date,
        end_date=end_date,
    )


@app.post("/v1/chat/completions")
async def openai_chat_completions(request: Request, req: OAChatRequest):
    """OpenAI Chat Completions 标准端点。

    转换逻辑：
      - model: 切换激活模型
      - messages: 取最后一条 user 消息作为本轮输入
      - tools: 透传给 LLM（OpenAI function calling 标准）
      - stream: True 时返回 SSE 文本流（伪流式，实际逐字符 emit 整段 reply）

    注意：本端点为了让 openai-python 等标准客户端可用，不支持工具调用的
    多轮循环（AgentLoop 内部已经处理）—— 如果 reply 中需要 tool_calls，
    应使用框架自己的 /v1/chat 端点。
    """
    username = _username(request)
    token = set_current_user(username)
    try:
        cfg, adapter, registry, loader, storage, mcp, runner, _, memory_pool, _, _ = app.state.components
        usage_store = app.state.usage_store

        # 获取当前用户的 MemoryManager
        memory_manager = await memory_pool.get(username)

        # 切换模型（如指定）
        if req.model and req.model in adapter.list_models():
            adapter.set_active(req.model)

        # 取最后一条 user 消息作为本轮输入
        user_msg = ""
        for m in reversed(req.messages):
            if m.get("role") == "user":
                user_msg = m.get("content") or ""
                break

        session_id = _resolve_session_id(req.user)
        session = Session(
            session_id=session_id,
            storage=storage,
            active_model=adapter.active,
        )
        session.load()

        # 构建/复用 AgentLoop（同一 session 内多轮会累积到 session.messages）
        # 包装 adapter.chat 以捕获最后一次 LLM 调用的 usage
        last_usage: dict | None = None

        def _capture_usage(usage):
            nonlocal last_usage
            if usage:
                last_usage = {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "prompt_tokens_details": {
                        "cached_tokens": usage.cache_hit_tokens,
                    } if usage.cache_hit_tokens else None,
                    "completion_tokens_details": {
                        "reasoning_tokens": usage.reasoning_tokens,
                    } if usage.reasoning_tokens else None,
                }

        original_chat = adapter.chat

        async def instrumented_chat(messages, tools=None, stream=False, temperature=None):
            response = await original_chat(messages, tools=tools, stream=stream,
                                           temperature=temperature)
            from open_fox.core.adapters.base import AssistantMessage
            if isinstance(response, AssistantMessage):
                _capture_usage(response.usage)
            return response

        adapter.chat = instrumented_chat
        try:
            compressor = _build_server_compressor(cfg, adapter)
            loop = AgentLoop(
                adapter=adapter, registry=registry, session=session,
                script_runner=runner, skills=loader.all(),
                max_steps=cfg.max_agent_steps,
                memory_manager=memory_manager,
                compressor=compressor,
            )
            reply = await loop.run(user_msg)
        finally:
            adapter.chat = original_chat

        # 隐式记忆抽取：AgentLoop.run() 完成后 fire-and-forget 通知（内部 _should_extract 过滤）
        extractor = getattr(app.state, "extractor", None)
        if extractor is not None:
            await extractor.notify(session.get_messages(), bool(loop.tool_trace), username)

        # Skill 进化：AgentLoop.run() 完成后通知（内部节流/触发判定过滤）
        evolution_task = getattr(app.state, "evolution_task", None)
        if evolution_task is not None:
            await evolution_task.notify(session_id, session.get_messages(), loop.tool_trace)

        # 用量记录
        au = loop.accumulated_usage
        usage_store.record(
            username=username,
            model=adapter.active,
            prompt_tokens=au.prompt_tokens,
            completion_tokens=au.completion_tokens,
            total_tokens=au.total_tokens,
            cache_hit_tokens=au.cache_hit_tokens,
            reasoning_tokens=au.reasoning_tokens,
            session_id=session_id,
        )

        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created_ts = int(time.time())

        if req.stream:
            # 流式响应（SSE）
            async def event_stream() -> AsyncIterator[str]:
                # chunk 1: role
                yield _sse_chunk({
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created_ts,
                    "model": adapter.active,
                    "choices": [{
                        "index": 0,
                        "delta": {"role": "assistant", "content": ""},
                        "finish_reason": None,
                    }],
                })
                # chunk 2: content
                yield _sse_chunk({
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created_ts,
                    "model": adapter.active,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": reply},
                        "finish_reason": None,
                    }],
                })
                # chunk 3: finish
                yield _sse_chunk({
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created_ts,
                    "model": adapter.active,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop",
                    }],
                })
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
            )

        # 非流式响应：透传上游 LLM 的真实 usage
        # AgentLoop 内部会把 usage 累加到 reply（如果有的话），我们取最终一次的
        # 注意：当前 AgentLoop 不暴露累加 usage（每个 AssistantMessage 自带单次 usage），
        # 这里取最后一次 chat() 的 usage（reply 来自最后一次调用）
        return {
            "id": completion_id,
            "object": "chat.completion",
            "created": created_ts,
            "model": adapter.active,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": reply,
                },
                "finish_reason": "stop",
            }],
            "usage": last_usage or {},  # 上游 API 真实 usage（fallback 到空 dict）
        }
    finally:
        from open_fox.core.memory.manager import _current_user as _ctx_var
        _ctx_var.reset(token)


def _sse_chunk(data: dict) -> str:
    """格式化一个 SSE chunk。"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _count_tokens_from_text(text: str) -> int:
    """粗略估算 token 数（4 字符 ≈ 1 token，与 CLI 一致）。"""
    return max(1, len(text or "") // 4)


def _count_tokens_from_messages(messages: list[dict]) -> int:
    total = 0
    for m in messages:
        total += 4
        total += _count_tokens_from_text(m.get("content") or "")
    return total


# ========== 入口 ==========

def main() -> None:
    parser = argparse.ArgumentParser(description="OpenFox 框架 HTTP 服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--no-color", action="store_true",
                        help="关闭日志颜色（脚本/CI 友好）")
    args = parser.parse_args()

    # --no-color：禁用 uvicorn 与 Python logging 的 ANSI 颜色
    if args.no_color:
        import os
        os.environ["NO_COLOR"] = "1"
        os.environ["FORCE_NO_COLOR"] = "1"
        os.environ["TERM"] = "dumb"

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    import uvicorn
    app.state.config_path = args.config
    # --no-color 时使用默认无颜色 log config；否则让 uvicorn 自动注入
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_config=None if args.no_color else uvicorn.config.LOGGING_CONFIG,
    )


if __name__ == "__main__":
    main()
