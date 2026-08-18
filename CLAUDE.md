---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '1fc42f54-7d8c-48d4-b34f-69a610ea4db2'
  PropagateID: '1fc42f54-7d8c-48d4-b34f-69a610ea4db2'
  ReservedCode1: 'be80d95e-6cc2-4c16-84c6-9b6aa63f31cc'
  ReservedCode2: 'be80d95e-6cc2-4c16-84c6-9b6aa63f31cc'
---

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

OpenFox 是一个自研 Agent Skills 框架（Python + FastAPI 后端、Vue3 前端）。核心能力：OpenAI Chat Completions 兼容多模型、Skill 渐进式披露、内置文件/Shell 工具、MCP 扩展、CLI + HTTP + Web 三端入口。

- 包名：`open_fox`（目录 `src/open_fox/`）
- 命令行：`OpenFox`（CLI）、`openfox-server`（HTTP 服务）
- 前端：独立 Vue3 工程 `web/`（Vite + Element-Plus）
- **Windows 优先**：路径用 `pathlib.Path`，不使用字符串拼接路径
- **本项目使用 git 管理**，远程仓库 `https://github.com/Hyone-soul/OpenFox`，主分支 `main`
- **Windows 优先**：路径用 `pathlib.Path`，不使用字符串拼接路径

## 常用命令

```bash
# 安装（开发模式，含 dev 依赖）
pip install -e ".[dev]"

# 运行全部测试
python -m pytest -q

# 运行单个测试文件 / 单个测试
python -m pytest tests/unit/test_agent_config.py -v
python -m pytest tests/integration/test_agent_chat.py::test_agent_chat_reply -v

# 已知预存失败：tests/unit/test_config.py::test_load_config_with_defaults
# （测试期望 max_agent_steps==20，但 config.yaml 实际是 50），
# 跑全量测试时用 --deselect 排除：
python -m pytest -q --deselect tests/unit/test_config.py::test_load_config_with_defaults

# Lint（ruff）
ruff check src tests

# 启动 CLI（交互式，prompt_toolkit）
OpenFox

# 启动 HTTP 服务（默认 127.0.0.1:8000）
openfox-server --host 127.0.0.1 --port 8000

# 启动前端（Web 端，Vite 代理 /v1 到后端 8000）
cd web && npm install   # 首次
cd web && npm run dev   # 开发 → http://localhost:5173
cd web && npm run build # 构建产物到 web/dist/
```

## 自定义工具扩展（动态加载两类外部工具）

用户在 `./tools/` 放带 `@tool` 装饰器的 `.py` 文件，框架自动扫描 + 生成 schema + 注册到 Registry（watchdog 热加载）。用户在 `./mcps/` 放 `*.yaml`/`*.json` 配置，框架启动时连接 MCP server 并注册工具（命名 `<server>__<tool>`）。详见 spec §4 与 `docs/superpowers/specs/2026-08-17-custom-tool-extensions-design.md`。

### 本地 Python 自定义工具（`./tools/`）

```python
# tools/example_tool.py
from open_fox.tools import tool

@tool(name="example_tool", description="一句话说明工具能力")
def example_tool(input_path: str, n: int = 10) -> str:
    """
    函数 docstring 自动解析为参数说明。

    Args:
        input_path: 输入文件路径
        n: 返回行数上限
    """
    return "..."
```

约束：
- 文件保存即可注册（watchdog 1-2 秒）；文件名不必等于 `name`，但建议一致
- `name` 全局唯一（不与 builtin / MCP 工具冲突）；`description` 必填
- 函数支持同步 / `async`；返回值 `ToolResult` / `str` / 其他自动归一化
- 类型注解 → OpenAI schema（str/int/float/bool/list/dict/Optional/Literal）
- docstring 支持 Google / NumPy / Sphinx 三风格

### MCP 配置（`./mcps/`）

```yaml
# mcps/local-filesystem.yaml
name: local-filesystem-mcp
transport: stdio                # stdio | sse | streamable-http
command: "npx"                  # stdio 必填
args: ["@modelcontextprotocol/server-filesystem", "./workspace"]
url: "http://127.0.0.1:8000/sse"  # sse/streamable-http 必填
headers:                          # value 走 ${VAR} 运行时替换
  Authorization: "Bearer ${MCP_TOKEN}"
enabled: true                     # 默认 true；false 跳过
timeout: 30
tool_allowlist: []                # 先 allow 后 deny
tool_denylist: []
permissions: {}                   # 仅记录，本版本不强制
```

- 文件命名 `<server-name>.yaml` 或 `.json`；扫描顶层 `*.yaml` + `*.json`，不递归
- transport 校验：stdio 必须有 `command`、http 必须有 `url`
- `headers` value 走 `_substitute_env`（`${VAR}` 单花括号）；找不到变量 → 空串 + warning
- **不要明文硬编码 token**，用 `${VAR}` 占位符 + 环境变量
- 一 server 一文件；重复 `name` → 后者跳过（按文件名字典序）
- YAML 解析注意：含 `-` 的值（如 `streamable-http`）要加引号

### 重载

- **CLI**：`/reload`（输入框打 `/reload` 回车）
- **HTTP**：`POST /v1/reload`，返回 `{custom_tools, mcp_servers, mcp_tools, errors}`
- `tools/` 由 watchdog 自动热加载（无需重启）；`mcps/` 需 `/reload` 重连

### 错误前缀分类

| 错误前缀 | 来源 |
|---|---|
| `本地工具异常：` | 自定义 Python 工具异常（被 FunctionTool 捕获） |
| `MCP 连接失败：` | MCP transport 连接失败 |
| `MCP 调用失败：` | MCP server 业务错误 |

排错时设 `AGENT_SKILLS_DEBUG=1` 重启，看完整堆栈。

## 架构

### 请求数据流

```
CLI / HTTP / Web → AgentLoop → ModelAdapter.chat|stream_chat → LLM Provider（OpenAI 兼容）
                          │
                          └→ Registry（内置工具 / MCP 工具）→ 工具执行
```

### Skill 渐进式披露（重要，按官方 agentskills.io 规范）

Skill 是文件夹，核心是 `SKILL.md`（frontmatter 的 `name`/`description` + Markdown 正文）。脚本/资源放 `scripts/`、`references/`、`assets/`。**三层披露**：

1. **L1 Discovery**：`AgentLoop._build_system()` 只把每个 skill 的 `name + description` 注入 system prompt（`可用 Skill：` 列表），模型据此判断相关性
2. **L2 Activation**：模型判断任务相关后，用 `read_file` 读 `./skills/<name>/SKILL.md` 全文，按其工作流执行
3. **L3 Execution**：按 SKILL.md 正文用 `run_shell` 执行脚本

**关键约定**：
- Skill 脚本**不注册**到 Registry、**不出现在** function calling schema——由模型读 SKILL.md 后用 run_shell 调用（`registry.list_tool_schemas()` 只含内置工具 + MCP 工具）
- `run_shell` 的 cwd 是**项目根**（`cfg.skills_dir.parent`），不是 workspace；skill 脚本用相对项目根路径执行，如 `python skills/db-helper/scripts/query_db.py --schema`
- SYSTEM_PROMPT 里给模型的路径提示要跟这个 cwd 一致

### 核心模块（`src/open_fox/`）

- **`core/agent_loop.py`**：Agent 主循环。注入系统提示词 → 调 LLM → 路由 tool_calls → 收敛。字段 `temperature`/`extra_system_prompt`/`tool_trace`/`on_chunk`。**`on_chunk` 非 None 时走流式**（`stream_chat`），chunk 喂给回调；`_call_llm` 区分流式/非流式。**注意 system 注入用 `any(role=="system")` 判断**（会话首部可能已有 `__meta__` 消息）。`_build_system()` 末尾追加 `VIBE_CODING_PROMPT` 引导 LLM 主动告诉用户如何新增 `@tool` 工具 / MCP 配置 / 重载 / 错误排查
- **`core/adapters/`**：模型适配器。`base.py` 定义 `ModelAdapter`（`chat` 含 `temperature`）+ `UsageInfo` + `AssistantMessage`（含 `reasoning_content`）+ `ChatChunk`（含 `tool_call_args_delta`）。`openai_chat.py` 是唯一实现，**`chat()` 非流式、`stream_chat()` 流式拆分成两个方法**（`chat` 始终返回协程，`stream_chat` 返回异步迭代器，勿混淆）。**流式 tool_call 的 arguments 是跨 chunk 的 JSON 片段**，`_parse_stream_chunk` 原样放 `tool_call_args_delta`，由 AgentLoop 累积完整后一次性解析——不要在其中 json.loads
- **`core/registry.py`**：统一注册表。只注册**内置工具**（`_tools`）和 **MCP 工具**（`_mcp_tools`，命名 `<server>__<tool>`）。`resolve()` 查这两类。**不含 skill 脚本**（渐进披露，脚本不注册）
- **`core/agent_filter.py`**：按智能体配置过滤工具/技能。`filter_registry` 用 `resolve()`（不是 get_tool，否则丢 MCP 工具）；空列表 = 全部启用
- **`core/session.py`**：会话状态。消息列表首部可有一条 `role="__meta__"` 消息存会话元数据。`chat_messages()` 过滤 `__meta__` 再发给 LLM
- **`core/skills/`**：SKILL.md 解析（YAML frontmatter + Markdown）+ watchdog 热加载。`SkillLoader` 扫描 `./skills`。`Skill.scripts`/`tools` 字段仅用于 `/v1/skills` 展示，不参与执行
- **`core/tools/`**：内置工具基类 `BaseTool`（`to_schema()` 生成 OpenAI function schema）+ 文件工具（ReadFile/WriteFile/EditFile，受 PathGuard 白名单）+ Shell 工具（RunShellTool，**cwd 为项目根**，受命令黑名单）
- **`core/security/`**：`path_guard.py`（路径白名单，`resolve()` 后校验）、`command_blacklist.py`（危险命令正则）
- **`core/scripts/`**：Skill 脚本执行引擎（subprocess/docker 后端），保留但**不再被 AgentLoop 直接调用**（模型走 run_shell）
- **`core/storage/`**：会话持久化抽象 + JsonStorage/MemoryStorage/MySqlStorage。**`json_store.py` 对 session_id 做白名单校验**（`^[A-Za-z0-9_.-]+$`）防路径穿越
- **`core/memory/`**：全局记忆系统。`manager.py` 是 `MemoryManager`（load/save/CRUD，`asyncio.Lock` + 原子写 `tmp + os.replace`，`memory_text()` 渲染注入文本：归档不注入、隐式截断 100 字、总上限 2000 字）；`models/parser/renderer` 负责 `MemoryDocument ↔ OPENFOX.md` 往返；`tools.py` 定义 4 个 `memory_*` 工具（走 `BaseTool.async_run`）；`extractor.py` 是 `MemoryExtractionTask` 后台隐式抽取（节流 ≥5 轮 + 本轮调工具 + 消息 ≥6 条）
- **`core/mcp/`**：MCP 客户端，三种 transport（stdio/SSE/streamable-http）。**`config_loader.py`** 从 `./mcps/*.yaml` 拆分文件加载（替代历史 config.yaml 内联段）
- **`core/custom_tools/`**：自定义工具加载与重载。`loader.py` 扫描 `./tools/`；`reload.py` 暴露 `CustomToolsReloadManager` + `reload_custom_tools()`；`schema_builder.py` 从 docstring/类型注解生成 OpenAI function schema
- **`tools/decorator.py`**：`@register_tool` 装饰器，把普通函数包装成 `FunctionTool`（BaseTool 子类），免去手写 class
- **`agents.py`**：智能体配置模型 `AgentConfig` + `AgentStore`（读写 config.yaml 的 `agents` 段，**写回时保留 models/storage 等其他段**）
- **`server.py`**：FastAPI 入口。`build_components` 返回 **10** 组件元组（含 `memory_manager` + `custom_tools_loader` + `mcp_config_loader`），存 `app.state.components`。**改组件数量时需同步所有解包处**。`lifespan` 里 `await memory_manager.load()` + `register_memory_tools` + `MemoryExtractionTask.start()` + `custom_tools_loader.reload()` + `mcp_config_loader.reload()`，三处端点 AgentLoop.run() 后 `await extractor.notify(...)`
- **`cli.py`**：`build_app` 返回 **8** 组件元组（比 server.py 少 `storage` / `runner` / 兼容位）。`repl()` 启动时调用 `load_mcp_configs(cfg.mcps_dir)` 加载 MCP 配置（与 server.py lifespan 对称）。注意 `repl()` 调用 `_repl_with_prompt_toolkit` / `_repl_with_basic_input` 时第 6 个参数必须是 `mcp`（McpClient），不是 `session`（Session 对象）—— 函数体内 `mcp._configs` 依赖此
- **`cli.py`**：prompt_toolkit REPL。**退出命令 `/exit` 和 `/quit`**；**`/<skill名>` 手动激活 skill**（读 SKILL.md 全文注入 session 后走对话）；**补全只在输入以 `/` 开头时弹出**（`ConditionalCompleter`），Tab 自动填入选中项；**新增 `/reload` 命令**重载 custom_tools + mcp + skills；MCP 清理在 `repl()` 末尾统一做。**不显示 token 统计**（流式 SSE 不带 usage）。**memory 集成**：`build_app` 返回 6 元组（含 memory_manager），`repl()` 里创建 `MemoryExtractionTask` + start/stop，`run_agent_with_console` 透传 manager/extractor 到 AgentLoop
- **`config.py`**：配置加载。优先级：默认值 → `.env` → YAML → CLI 覆盖。`max_agent_steps` 默认 50。`McpServerConfig` 字段扩展（`enabled` / `timeout` / `tool_allowlist` / `tool_denylist` / `permissions`）以支持 `MCPConfigLoader`；`AppConfig` 中历史内联 MCP 字段已**移除**（拆分文件方案不需该字段）

### HTTP API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/chat` | 一轮对话（高阶，自动处理 Skill/工具） |
| GET | `/v1/skills` `/v1/tools` `/v1/models` | 资源列表 |
| GET | `/healthz` | 健康检查 |
| GET/POST/PUT/DELETE | `/v1/agents[/{id}]` | 智能体 CRUD |
| GET | `/v1/agents/{id}/test` | 测试模型连通性 |
| POST | `/v1/agent-chat` | 按智能体聊天（过滤工具/技能 + 注入系统提示词） |
| GET/POST/DELETE | `/v1/sessions[/{id}]` | 会话管理 |
| GET | `/v1/sessions/{id}/messages` | 会话消息 |
| POST | `/v1/chat/completions` | OpenAI 兼容端点（openai-python 可直接连接） |
| GET | `/v1/mcps` | 列出已加载的 MCP server 及其工具 |
| POST | `/v1/reload` | 热重载 custom_tools + mcp + skills |
| GET | `/v1/tools` | 列出工具 schema（带 `source` 字段：`builtin` / `custom` / `mcp`） |

## 关键约定

- **代码注释使用中文**
- `.env` 存 API key（gitignore），config.yaml 用 `api_key_env` 引用环境变量名，密钥不进 YAML
- 智能体/会话 API 用 `instrumented_chat` 包装 `adapter.chat` 捕获真实 usage，**必须捕获 `original_chat` 引用**（否则无限递归）
- **CLI 用流式 `stream_chat`**（`on_chunk`），SSE 通常不带 usage，所以不显示 token；server 用非流式 `chat`
- 会话元数据用消息内嵌 `__meta__` 方案，**不要改 Storage 抽象接口**
- 测试基类：`FakeAdapter`（chat 签名含 `temperature`）；集成测试用 `TestClient(app)` + `_inject_fake_adapter` 替换 `components[1]`
- 集成测试的临时 config.yaml 应显式配置 `storage.json_dir` 指向 tmp 目录，避免污染真实的 `./data/sessions`
- **调试工具调用**：在 `_dispatch` 加 `logger.info("tool_call: name=%s args=%r", tc.name, tc.args)`，用 `AGENT_SKILLS_DEBUG=1` 跑 server 看日志
- **全局记忆唯一存项目根 `OPENFOX.md`**：运行时按模板生成、**不入 git**；所有改动必须走 `memory_*` 工具（`register_memory_tools` 注册进 Registry），不要手动篡改其结构
- **显式记忆强权限**：`memory_delete` 目标在 explicit 区 → 抛 `MemoryPermissionError`（拒绝 LLM 自动删除显式记忆）
- **隐式抽取节流条件**：距上次抽取 ≥5 轮 + 本轮调用了工具 + 会话消息 ≥6 条，三者同时满足才触发；抽取失败只 `logger.warning`，不拖垮主对话
- **`memory_*` 工具走 `BaseTool.async_run`**：AgentLoop `_dispatch` 用 `type(target).async_run is not BaseTool.async_run` 判断走异步；MemoryManager 全异步，`cli` 用 `load_sync()`（`asyncio.run`），`server` lifespan 用 `await load()`
- **day06 镜像**：`C:\Users\86138\Desktop\day06\codes\agent_skills_framework` 是过期副本，Python 环境已指向本仓库（editable install），不要改 day06
- **本地工具放 `./tools/`**：`CustomToolsLoader` 启动时扫描，文件名 / 类名 / `name` 字段任一作为工具标识；`@register_tool` 装饰器（`core/tools/decorator.py`）可包装普通函数；**reload 保护内置工具**（只重建自定义 + MCP + skills）
- **MCP 配置放 `./mcps/`**：每个 server 一个 `<name>.yaml`（`MCPConfigLoader` 加载），**已废弃** config.yaml 内联 MCP 段——用 `python scripts/migrate_mcp_config.py` 一键迁移。`${VAR}` 占位符在 headers 字段运行时从环境变量替换
- **MCP server 配置字段扩展**：`McpServerConfig` 新增 `enabled` / `timeout` / `tool_allowlist` / `tool_denylist` / `permissions`；`AppConfig` 中历史内联 MCP 字段已**移除**（拆分文件方案不再需要）