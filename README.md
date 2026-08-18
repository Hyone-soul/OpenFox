# OpenFox

<img width="150" height="150" alt="OpenFox" src="https://github.com/user-attachments/assets/bf82e486-d418-48da-bcfc-81337b013af4" />

> 自研 **Agent Skills 框架**（Python + FastAPI 后端、Vue3 前端、Electron 桌面端）。OpenAI Chat Completions 完全兼容、Skill 渐进式披露、内置文件/Shell 工具、MCP 扩展，CLI + HTTP + Web + Desktop 四端入口。

[![Python](https://img.shields.io/badge/python-3.13%2B-blue?logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Vue](https://img.shields.io/badge/Vue-3.4%2B-4FC08D?logo=vuedotjs)](https://vuejs.org)
[![License](https://img.shields.io/badge/license-MIT-green)]()
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()

<img width="1200" height="800" alt="image" src="https://github.com/user-attachments/assets/545477d7-5222-40c8-befa-0d4db543c862" />


---

## ✨ 特性

- 🔌 **OpenAI 完全兼容 API**：标准 `/v1/chat/completions` 端点 + SSE 流式 + `/v1/models`，`openai.OpenAI(base_url=..., api_key="anything")` 直接连接
- 🧩 **Skill 渐进式披露**：启动只加载 skill 的 name + description（L1），模型判断相关后 `read_file` 读 SKILL.md 全文（L2），按工作流用 `run_shell` 执行脚本（L3）——多 skill 不占上下文
- 🔥 **Skill 热加载**：watchdog 监听 `./skills`，新增/修改/删除 `SKILL.md` 无需重启
- 🎨 **Claude Code 风格 CLI**：紫色 prompt、Rich Markdown、Tab 补全（`/` 开头才弹出）、`/`<skill名>` 手动激活技能、命令历史
- 🖥️ **平台感知**：AgentLoop 自动检测 OS / Shell / Python 命令名 / 路径分隔符，注入 system prompt，让 Agent 在 Windows 上用 `dir`、在 Linux 上用 `ls`，不再用错命令
- 💬 **结构化 CLI 输出**：spinner 思考指示（`✦ 思考中…` → `⚙ 调用 xxx…`）→ 💭 Thinking 推理面板（dim cyan）→ ⚙/✗ 工具调用轨迹（含结果预览）→ Markdown 渲染最终回复
- 💭 **推理实时展示（Web/桌面端）**：推理模型（如 DeepSeek-R1）的思考过程实时渲染为可折叠的「思考过程」区块，告别纯省略号等待
- 🛡️ **工具调用健壮性**：流式多 tool_call 并发解析（按 index 分组累积）、arguments JSON 解析失败 warning + 日志、连续 5 步全失败自动熔断
- 🛠️ **内置工具**：`read_file` / `write_file` / `edit_file` / `run_shell`，全部受路径白名单保护；`run_shell` cwd 为项目根
- 🔗 **MCP 扩展**：stdio / SSE / streamable-http 三种 transport，配置即可注册外部工具
- 🧠 **全局记忆系统**：跨会话持久记忆，`OPENFOX.md` 唯一存储 + 启动自动注入 system prompt + `memory_add/query/update/delete` 四工具 + 隐式记忆 AI 自动提炼
- 💾 **存储可插拔**：默认内存（CLI）/ JSON（Server），可换 MySQL
- 🌐 **Web 端**：Vue3 + Element-Plus 管理界面，9 个页面统一紫色品牌主题（详见下方 Web 端章节）
- ⚠️ **安全三层**：路径白名单 + 命令黑名单 + 脚本环境变量剥离
- 🔌 **`.env` 自动加载**：python-dotenv，密钥不进 YAML
- 👥 **多用户系统**：JWT 认证 + UserStore（JSON 持久化），Web / CLI 共享 auth 模块；每个用户拥有独立的智能体配置、会话、记忆，互不干扰
- 📊 **用量管理**：AgentLoop 自动累积 token 用量，UsageStore 按用户/月/模型维度持久化到 JSON；Web 端可视化图表展示用量趋势与模型分布
- 🎨 **Web 端全面重设计**：9 个页面统一紫色品牌主题 + 卡片式布局——登录页、介绍页、模型管理（卡片网格 + 供应商徽章）、智能体管理（卡片网格 + 工具/技能标签）、聊天工作台（双态切换）、用量管理（汇总卡片 + ECharts 图表）、记忆管理、Skill 管理、MCP 管理
- 💬 **聊天工作台**：主页态（欢迎屏 + 建议提示词卡片）/ 会话态（消息流 + 输入框）双视图切换；侧栏含智能体下拉切换、项目分组会话列表；输入框支持 IME 中文输入、自动高度、模型内嵌选择、/ 命令面板；消息支持 Markdown 渲染、推理过程折叠展示、工具调用轨迹折叠面板
- 🖥️ **桌面端 APP**：Electron 桌面端（类 Codex），极简黑白灰 UI、自动启动后端（PyInstaller 打包，无需 Python 环境）、系统托盘最小化、全局快捷键呼出、原生菜单栏、开机自启、启动屏、窗口状态记忆、NSIS 安装包一键分发
- 📦 **上下文管理**：Hermes 三层防御（预防→压缩→兜底），超阈值自动触发 5 步压缩算法（廉价预处理→保护头尾→中间摘要→重新组装），反抖动+冷却期+小窗口退化保护，CLI `/context` + HTTP `/v1/context/status` + Web 状态条三端可见

## 🚀 快速开始

### 环境要求

- **Python** ≥ 3.10
- **Node.js** ≥ 18（前端 / 桌面端 / shell/node 脚本）
- **Docker**（可选，脚本 Docker 隔离）

### 安装

```bash
pip install -e ".[dev]"          # 后端（含 dev 依赖）
cd web && npm install             # 前端
cd desktop && npm install         # 桌面端（可选）
```

如需 MySQL 持久化：`pip install -e ".[dev,mysql]"`

### 配置

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

编辑 `.env` 写入 API key：

```ini
OPENAI_API_KEY=sk-your-openai-key-here
# 或 DeepSeek（国内直连，config.yaml 默认已配好）
DEEPSEEK_API_KEY=sk-your-deepseek-key-here
```

编辑 `config.yaml` 配置模型：

```yaml
models:
  - name: deepseek-v4-flash
    base_url: https://api.deepseek.com/v1
    api_key_env: DEEPSEEK_API_KEY
    model: deepseek-v4-flash
```

> **配置加载优先级**：内置默认值 → `.env` → YAML → CLI 覆盖

### 启动

```bash
# 方式 A：交互式 CLI（首次需 --user 登录）
OpenFox --user myname

# 方式 B：HTTP 服务（OpenAI 兼容 + 框架 API）
openfox-server --host 0.0.0.0 --port 8000

# 方式 C：Web 端（Vite 代理 /v1 到后端 8000）
cd web && npm run dev    # → http://localhost:5173（首次访问需注册/登录）

# 方式 D：桌面端 APP（Electron，自动启动后端 + 原生窗口）
cd desktop && npm run dev
```

### 30 秒体验

```text
❯ 你好
你好！我是你的 AI 助手...

❯ /model deepseek-v4-flash          # 切换模型
✓ 已切换到模型：deepseek-v4-flash

❯ /db-helper 谁的流量最少            # 手动激活 db-helper 技能并查询
```

## 🎨 CLI 使用

启动后看到紫色 `❯` prompt。支持多行输入、命令历史、Tab 补全。

### 启动界面

启动时显示信息面板（紫色边框），含标题（⚡ OpenFox Framework）、ASCII 吉祥物小脸、模型/工具/技能统计、命令速查、三类工具表（内置 / 自定义 / MCP）和已加载 Skill 列表。

```text
┌─────────────────────── ⚡ OpenFox ───────────────────────┐
│  ⚡ OpenFox  Framework                                  │
│  Agent Skills 框架                                      │
│     /\ /\                                               │
│    ( o.o )                                              │
│     > ^ <                                               │
│  ────────────────────────────────────                   │
│  ✦ deepseek-v4-flash                                    │
│  ⚒ 8 内置 · 1 自定义 · 15 MCP(1) · ◆ 5 skills           │
│  ...                                                    │
└──────────────────────────────────────────────────────────┘
```

### AI 回复渲染

每次对话输出分四层，从上到下依次呈现：

1. **Spinner 思考指示** — `✦ 思考中…`（紫色），检测到工具调用时自动切换为 `⚙ 调用 xxx…`（黄色）
2. **💭 Thinking 推理面板** — 推理模型（如 DeepSeek-R1）的 `reasoning_content` 以 dim cyan 面板展示，超 800 字自动截断
3. **⚙/✗ 工具调用轨迹** — 每个工具调用两行：工具名(参数) + 结果预览（截断 200 字）；失败用红色 `✗` 标记
4. **Markdown 最终回复** — 用 Rich Markdown 渲染表格、标题、列表、代码块（monokai 主题）

```text
❯ 南京邮电大学到南通环城南路88号的距离

⠋ ✦ 思考中…                          ← spinner 自动切换

┌─ 💭 Thinking ───────────────────────┐
│ 我需要先获取两个地点的经纬度坐标…   │
└─────────────────────────────────────┘

  ⚙ amap__maps_geo(address='南京邮电大学')
    → {"location": "118.796,32.118", …}
  ⚙ amap__maps_geo(address='南通环城南路88号')
    → {"location": "120.866,32.014", …}

## 📏 距离汇总                          ← Markdown 渲染
| 校区 | 直线距离 | 驾车距离 | …
```

### 命令

| 命令 | 行为 |
|---|---|
| `/model [name]` | 查看或切换模型 |
| `/skills` | 列出已加载 Skill（绿表） |
| `/tools` | 列出可用工具（蓝表） |
| `/<skill名> [问题]` | **手动激活 Skill**：读 SKILL.md 全文注入会话后执行 |
| `/status` | 显示状态栏 |
| `/context` | 显示上下文使用状态（模型、窗口、Token 分布、压缩配置） |
| `/clear` | 清屏并重置会话上下文 |
| `/help` | 命令帮助 |
| `/exit` / `/quit` | 退出 REPL |

**交互特性**：
- **Tab 补全**：仅当输入以 `/` 开头时弹出（斜杠命令 + `/`<skill名>`），Tab 自动填入选中项，Shift+Tab 反向选择
- Rich Markdown 渲染（表格、列表、代码块 monokai）
- 状态栏：`✦ model ⚒ tools ◆ skills ⌬ mcp`
- 历史持久化：`~/.openfox_history`
- 非 TTY（Git Bash）自动降级 `input()`；prompt_toolkit 用 `prompt_async` 适配 asyncio 事件循环

### CLI 选项

```bash
OpenFox                         # 默认（首次启动需 login）
OpenFox --user myname           # 指定用户名（交互式登录/注册）
OpenFox --no-logo               # 跳过欢迎界面
OpenFox --no-color              # 关闭颜色（脚本/CI）
OpenFox --config my.yaml        # 指定配置
```

**CLI 登录**：首次运行 `OpenFox` 需通过 `--user` 交互式登录或注册。登录后状态栏显示用户名，智能体配置、会话、记忆均按用户隔离（与 Web 端共享 auth 模块）。

## 🌐 HTTP API

### 框架自有 REST

#### 认证（多用户系统）

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/v1/auth/register` | 注册用户（username + password + display_name） |
| `POST` | `/v1/auth/login` | 登录，返回 JWT token |
| `GET` | `/v1/auth/me` | 获取当前用户信息（需 Bearer token） |

#### 智能体 & 会话 & 聊天

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET/POST` | `/v1/agents` | 智能体列表 / 创建 |
| `GET/PUT/DELETE` | `/v1/agents/{id}` | 智能体详情 / 更新 / 删除 |
| `GET` | `/v1/agents/{id}/test` | 测试模型连通性 |
| `POST` | `/v1/agent-chat` | 按智能体聊天（过滤工具/技能 + 注入系统提示词） |
| `GET/POST` | `/v1/sessions` | 会话列表 / 创建 |
| `GET` | `/v1/sessions/{id}/messages` | 会话消息 |
| `DELETE` | `/v1/sessions/{id}` | 删除会话 |

#### 模型管理

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/v1/models/detail` | 模型配置列表 + 当前活跃模型 |
| `POST` | `/v1/models` | 新增模型配置 |
| `PUT` | `/v1/models/{name}` | 更新模型配置 |
| `DELETE` | `/v1/models/{name}` | 删除模型配置 |
| `PUT` | `/v1/models/{name}/active` | 设为默认模型 |
| `POST` | `/v1/models/{name}/test` | 测试模型连通性 |

#### 用量管理

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/v1/usage/records` | 用量记录列表（支持月份/模型过滤） |
| `GET` | `/v1/usage/summary` | 用量汇总（按模型/按月的 token 统计） |

#### 其他

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/v1/chat` | 一轮对话（高阶，含 Skill/工具自动处理） |
| `GET` | `/v1/skills` | 列出已加载 Skill |
| `GET` | `/v1/tools` | 列出工具 schema |
| `GET` | `/healthz` | 健康检查 |

### OpenAI 兼容（标准 API）⭐

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/v1/models` | 标准模型列表 |
| `POST` | `/v1/chat/completions` | 标准 Chat Completions，支持 `stream=true` SSE |
| `POST` | `/v1/reload` | 热重载 custom_tools + mcp + skills，返回加载报告 |
| `GET` | `/v1/mcps` | MCP server 列表 + 工具 + 来源文件 + 启停状态 |
| `GET` | `/v1/tools` | 工具 schema 列表（每个 tool 加 `source` 字段：`builtin` / `custom_python` / `mcp:<server>`） |

**任何 OpenAI 兼容客户端可直接连接**（`user` 字段作 session_id 实现多轮）：

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="anything")

resp = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[{"role": "user", "content": "你好"}],
    user="session-001",   # session_id，同一会话自动累积上下文
)
print(resp.choices[0].message.content)

# 流式
for chunk in client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[{"role": "user", "content": "讲个笑话"}],
    stream=True,
):
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

## 🧩 Skill 机制（渐进式披露）

按 [agentskills.io](https://agentskills.io) 官方规范实现。Skill 是文件夹，核心是 `SKILL.md`（YAML frontmatter 的 `name`/`description` + Markdown 正文），可选 `scripts/`、`references/`、`assets/`。

**三层渐进披露**：

1. **L1 Discovery**：启动只把每个 skill 的 `name + description` 注入 system prompt（`可用 Skill：` 列表，~100 token），模型据此判断相关性
2. **L2 Activation**：模型判断相关后，用 `read_file` 读 `./skills/<name>/SKILL.md` 全文，按其工作流执行
3. **L3 Execution**：按 SKILL.md 正文用 `run_shell` 执行 `./skills/<name>/scripts/` 下的脚本

```markdown
---
name: db-helper
description: 用自然语言查询 user_info.db 电信用户数据库（NL2SQL）...
---

# db_helper —— 自然语言查询 user_info.db

## 工作流
1. 先执行 `python skills/db-helper/scripts/query_db.py --schema` 自省
2. 生成 SQL，执行 `python .../query_db.py --sql "<SQL>"`
3. 用中文总结结果
```

**要点**：
- Skill 脚本**不注册**到 Registry、不进入 function calling schema——由模型读 SKILL.md 后用 `run_shell` 调用
- `run_shell` 的 cwd 是**项目根**，脚本用相对项目根路径执行（`python skills/db-helper/scripts/query_db.py --schema`）
- CLI 里 `/`<skill名>` 可手动激活（L2 注入 SKILL.md 全文到会话）

### 添加自定义 Skill

```bash
mkdir -p skills/my-skill/scripts
# 写 skills/my-skill/SKILL.md（frontmatter: name/description + 正文）
```

watchdog 会在 1-2 秒内自动发现新 Skill，**无需重启**。

## 🧠 全局记忆系统

跨会话的**持久化全局记忆**：项目根目录的 `OPENFOX.md` 是唯一存储（运行时按模板自动生成，**不入 git**），CLI / HTTP / Web 启动时自动加载并注入 system prompt，让 Agent 在新会话里也能记住用户偏好、项目约束与使用习惯。

**双通道记忆**：

- **📌 显式记忆**（用户指定）：说"记住我用 FastAPI" → Agent 调 `memory_add(explicit, ...)` 立即入库；高优先级、**不可被自动删除**
- **🧠 隐式记忆**（AI 自动提炼）：任务闭环后 `MemoryExtractionTask` 后台抽取长期稳态结论；需同时满足 **距上次抽取 ≥5 轮 + 本轮调用了工具 + 会话消息 ≥6 条** 才触发，按置信度（高/中/低）入库

**四个工具**（注册进 Registry，function calling 可直接调用）：

| 工具 | 参数 | 行为 |
|---|---|---|
| `memory_add` | `memory_type`(explicit/implicit)、`section`、`content`、`confidence`(高/中/低) | explicit 强制入库并去重；implicit 按 section 路由到子板块，>500 字拒绝 |
| `memory_query` | `keyword`(可空)、`memory_type`(可空) | keyword 空返回全部；否则按 content/meta 子串匹配（不区分大小写） |
| `memory_update` | `target_content`、`new_content`、`memory_type` | 旧内容替换并移入归档；无匹配退化为新增 |
| `memory_delete` | `target_content`、`archive`(默认 true) | archive=true 移入归档，false 物理删除；**目标在显式区 → 抛 `MemoryPermissionError` 拒绝自动删除** |

**防膨胀机制**：隐式抽取**节流**（多条件限制）+ **置信度**（低置信少注入）+ **归档**（废弃记忆只归档不注入，仅查询返回）。注入 system prompt 时归档区不注入、隐式条目截断 100 字、总注入上限 **2000 字**。

## 🏗️ 项目结构

```
open_fox/
├── pyproject.toml                       # 包元数据、依赖、CLI 入口
├── config.example.yaml                  # 配置示例
├── Makefile                             # install/test/cli/server 快捷命令
├── skills/                              # Skill 存放目录（自动扫描）
│   └── db-helper/
│       ├── SKILL.md
│       ├── assets/user_info.db
│       └── scripts/query_db.py
├── src/open_fox/
│   ├── cli.py                           # CLI REPL（prompt_toolkit + Rich + login）
│   ├── server.py                        # FastAPI HTTP（OpenAI 兼容 + 智能体/会话/认证/用量 API）
│   ├── config.py                        # 配置加载（YAML + .env + ENV）
│   ├── agents.py                        # 智能体配置模型 + AgentStore
│   ├── auth.py                          # 多用户认证（JWT + UserStore，Web/CLI 共享）
│   ├── usage_store.py                   # 用量持久化（按用户/月/模型 JSON 存储）
│   ├── model_store.py                   # 模型配置持久化 + 活跃模型管理
│   └── core/
│       ├── agent_loop.py                # Agent 主循环（流式/非流式）+ Vibe Coding 提示词 + 用量累积
│       ├── agent_filter.py              # 按智能体过滤工具/技能
│       ├── platform_context.py          # 平台感知（OS/Shell/路径检测 + 提示词注入）
│       ├── registry.py                  # 注册表（内置工具 + 自定义 + MCP，不含 skill 脚本）
│       ├── session.py                   # 会话状态（__meta__ 元数据）
│       ├── adapters/                    # 模型适配器（chat 非流式 / stream_chat 流式）
│       ├── skills/                      # Skill 解析与热加载
│       ├── tools/                       # 内置工具（文件 + Shell）+ @tool 装饰器
│       ├── custom_tools/                # 自定义工具：loader（watchdog）+ schema_builder + reload
│       ├── scripts/                     # 脚本执行引擎（保留，agent 走 run_shell）
│       ├── security/                    # 路径守卫 + 命令黑名单
│       ├── storage/                     # 存储抽象 + 3 个实现
│       ├── memory/                      # 全局记忆系统（OPENFOX.md 读写 + 4 工具 + 隐式抽取）
│       ├── context/                     # 上下文管理（三层防御：量化 → 阈值判定 → 压缩）
│       │   ├── token_estimator.py        #   Token 估算 + 模型上下文窗口查找表
│       │   ├── context_breakdown.py       #   8 类目 token 量化 + ContextSnapshot
│       │   └── context_compressor.py      #   5 步压缩算法 + 反抖动 + 冷却期 + 兜底
│       └── mcp/                         # MCP 客户端 + config_loader（mcps/ 目录扫描）
├── web/                                 # Vue3 前端
│   ├── public/OpenFox.png                 # 派蒙 logo（导航栏 + 聊天头像 + 欢迎屏）
│   └── src/
│       ├── views/                       # 9 个页面（详见下方 Web 端章节）
│       │   ├── IntroPage.vue             #   项目介绍页（/）
│       │   ├── Login.vue                 #   登录/注册页
│       │   ├── ChatWorkbench.vue         #   聊天工作台（双态切换）
│       │   ├── AgentManage.vue           #   智能体管理（卡片网格）
│       │   ├── ModelManage.vue           #   模型管理（卡片网格 + 供应商徽章）
│       │   ├── MemoryManage.vue          #   记忆管理
│       │   ├── SkillManage.vue           #   Skill 管理
│       │   ├── MCPManage.vue             #   MCP 管理
│       │   └── UsageManage.vue           #   用量管理（ECharts 图表）
│       ├── components/                  # AgentFormDialog / ModelFormDialog / ChatMessages / ChatInput / SessionList / ToolCallPanel
│       └── api/                         # axios API 封装（含 JWT 拦截器）
├── desktop/                              # Electron 桌面端
│   ├── main.js                           # 主进程（生命周期 + 窗口 + IPC + 全局快捷键）
│   ├── preload.js                        # 预加载脚本（contextBridge 安全 API 暴露）
│   ├── backend.js                        # 后端进程管理器（spawn + 健康检查 + 优雅关闭）
│   ├── tray.js                           # 系统托盘（最小化到托盘 + 快捷菜单）
│   ├── menu.js                           # 原生菜单栏（文件/编辑/视图/后端/帮助）
│   ├── updater.js                        # 自动更新（electron-updater + GitHub Releases）
│   ├── window-state.js                   # 窗口状态持久化（位置/大小/最大化）
│   ├── splash.html                       # 启动屏（紫色主题 + 进度条）
│   ├── assets/icon.png                   # 应用图标（派蒙）
│   └── package.json                      # 依赖 + electron-builder 打包配置
├── tests/                               # unit / integration / e2e
└── workspace/                           # 文件工具可操作的目录
```

## 🔧 架构

```
                    ┌──────────────────────────────────────────────────┐
                    │                Electron Desktop                   │
                    │  ┌────────────┐  ┌──────────┐  ┌───────────────┐  │
                    │  │ Splash 屏  │  │ 主窗口   │  │ 系统托盘      │  │
                    │  └─────┬──────┘  └────┬─────┘  └───────┬───────┘  │
                    │        │              │                │          │
                    │        └──────────────┼────────────────┘          │
                    │                       │ preload.js (contextBridge)│
                    │                       ▼                           │
                    │              Vue3 前端 (renderer)                  │
                    └───────────────────────┬──────────────────────────┘
                                            │ HTTP (/v1)
                    ┌───────────────────────┼──────────────────────────┐
                    │              ┌─────────▼─────────┐                │
                    │              │  BackendManager    │                │
                    │              │  (spawn python)    │                │
                    │              └─────────┬─────────┘                │
                    │                        │                          │
            CLI / HTTP / Web / Desktop → Auth（JWT）→ AgentLoop         │
                    │                                      │            │
                    │              ┌───────────────────────┤            │
                    │              │                       │            │
                    │   ┌──────────▼──────────┐  ┌────────▼────────┐   │
                    │   │ PlatformContext      │  │ Registry        │   │
                    │   │ (OS/Shell 感知)      │  │ (工具路由)       │   │
                    │   └─────────────────────┘  └────────┬────────┘   │
                    │                                      │            │
                    │              ┌───────────────────────▼────────┐   │
                    │              │     ModelAdapter → LLM Provider│   │
                    │              └────────────────────────────────┘   │
                    └──────────────────────────────────────────────────┘
```

- **Auth（多用户隔离）**：Web 端 JWT 登录，CLI 端 `--user` 交互式登录；每个用户拥有独立的 agents.json、sessions/目录、OPENFOX.md 记忆文件，互不干扰
- **AgentLoop**：注入 platform context + system + user → 调 LLM（非流式或流式累积 `ChatChunk`）→ 无 tool_calls 即返回终态；否则路由 tool_call 逐个执行并追加工具消息。`tool_trace` 记录每步调用，`accumulated_usage` 累积 token 用量
- **PlatformContext**：启动时检测 OS / Shell / Python 命令名 / 路径分隔符 / CPU 架构，生成平台提示词注入 system prompt 最前面。Windows 环境包含 15 项命令对照表（`dir` vs `ls`、`type` vs `cat` 等），让 Agent 不再用错命令
- **ModelAdapter**：`chat()`（非流式，返回协程）与 `stream_chat()`（流式，返回 `AsyncIterator[ChatChunk]`）拆分为两个方法，勿混淆
- **Registry**：只注册内置工具 + MCP 工具（`<server>__<tool>`）；Skill 脚本按渐进披露由模型用 run_shell 调用
- **UsageStore**：AgentLoop 每轮对话结束后将 `accumulated_usage`（prompt_tokens + completion_tokens + total_tokens）写入 `data/usage/<username>/<YYYY-MM>.json`，按模型维度累积
- **流式 tool_call 解析**：按 `index` 分组累积，支持 LLM 一次返回多个并发 tool_call；arguments JSON 跨 chunk 原样拼接后整体解析，解析失败加 warning 日志
- **推理模型支持**：`reasoning_content` 透传回传（DeepSeek-R1 等）；CLI 端以 dim cyan 面板展示
- **熔断机制**：连续 5 步所有工具调用全部失败时自动终止，防止 LLM 陷入无限重试循环
- **CLI 渲染**：spinner 思考指示 → 💭 Thinking 推理面板 → ⚙/✗ 工具调用轨迹（含结果预览）→ Markdown 最终回复

## 📦 上下文管理（Context Management）

参考 **Hermes 三层防御**设计，从源头控制上下文增长，超阈值自动压缩，压缩也救不了时兜底提示开新会话。

### 三层防御

| 层 | 名称 | 机制 |
|---|---|---|
| **第一层** | 预防 | Skill 渐进式披露（L1 name+description → L2 read SKILL.md → L3 run script），从源头控制注入量 |
| **第二层** | 压缩 | 超阈值时触发 5 步压缩算法（廉价预处理 → 保护头部 → 保护尾部 → 中间摘要 → 重新组装） |
| **第三层** | 兜底 | 压缩连续失败时建议 `/new` 开新会话，完整历史持久化到磁盘 |

### 压缩算法（5 步）

1. **廉价预处理**（不调 LLM）：截断过长工具结果（>2000 字符裁剪到 500 + `[truncated]`）、剔除空白回显
2. **保护头部**：`protect_first_n` 条消息原样保留（system + 初始指令锚点）
3. **保护尾部**：`protect_last_n` 条消息原样保留（最近上下文，不动）
4. **中间压缩**：中间部分交给 LLM 生成结构化摘要（Goal / Progress / Key Decisions / Files / Remaining Work）；LLM 不可用时降级为确定性回退摘要
5. **重新组装**：`__meta__ + head + [摘要, 确认] + tail`，清理孤儿 tool_call/tool_result，插入真实用户锚点保证角色交替

### 保护机制

- **反抖动**：连续两次压缩收益 <10% 则熔断，避免无效压缩
- **冷却期**：压缩失败后进入 30 秒冷却，不重复触发
- **小窗口退化**：若阈值 ≥ 整个窗口，改用窗口的 85%
- **显式失败**：压缩失败绝不静默，返回原文 + 错误信息

### 配置

```yaml
# config.yaml
compression:
  enabled: true
  threshold: 0.5              # 触发阈值 = effective_budget × 50%
  target_ratio: 0.2           # 压缩目标 = effective_budget × 20%
  protect_first_n: 3          # 保护头部 3 条
  protect_last_n: 20          # 保护尾部 20 条
  max_attempts: 3             # 最大重试
  anti_thrash_threshold: 0.1   # 反抖动阈值 10%
  cooldown_seconds: 30         # 冷却期 30 秒
  # context_window: 64000     # 手动指定窗口大小（默认自动检测）
```

### 使用

- **CLI**：输入 `/context` 查看当前上下文状态（模型、窗口、已用/剩余 token、分类明细）
- **HTTP API**：`GET /v1/context/status` 返回上下文配置与状态
- **Web**：聊天工作台标题栏下方自动显示上下文状态条（模型 + 窗口 + 压缩配置）

## 🌐 Web 端

Vue3 + Element Plus 管理界面，统一紫色品牌主题（#7c3aed）+ 卡片式布局，派蒙 logo 贯穿全局。

### 页面一览

| 路由 | 页面 | 说明 |
|---|---|---|
| `/` | 介绍页 | 项目落地页：hero 区 + 特性卡片 + 架构图 + 快速开始 |
| `/login` | 登录/注册 | 分屏式登录页，左侧品牌展示，右侧表单切换登录/注册 |
| `/chat` | 聊天工作台 | 双态切换：主页态（欢迎屏 + 建议提示词）/ 会话态（消息流 + 输入框） |
| `/agents` | 智能体管理 | 卡片网格：名称徽章 + 工具/技能标签 + 温度/步数参数 + 测试三态按钮 |
| `/models` | 模型管理 | 卡片网格：供应商彩色徽章 + 密钥脱敏 + 活跃模型标记 + 连通性测试 |
| `/memory` | 记忆管理 | 记忆条目列表 + 增删改查 |
| `/skills` | Skill 管理 | Skill 列表 + 在线编辑 SKILL.md + 版本回滚 + 导入/上传 |
| `/mcps` | MCP 管理 | MCP server 列表 + 启停 + 工具查看 + 配置编辑 |
| `/usage` | 用量管理 | 汇总卡片 + ECharts 趋势图 + 模型分布饼图 + 月度明细表 |

### 聊天工作台设计

- **侧栏**：紫色渐变"新建对话"按钮 + 智能体选择卡片（点击展开下拉切换）+ 历史会话列表（带图标 + 时间）
- **主页态**：无会话选中时显示，派蒙 logo + 智能体名称 + "开始新对话"按钮 + 4 个建议提示词卡片（点击自动建会话并发送）
- **会话态**：顶部标题栏（返回箭头 + 会话标题 + 智能体标签 + 消息计数）+ 消息流 + 输入区
- **消息流**：用户/AI 头像分侧布局，AI 消息 Markdown 渲染 + hover 复制按钮 + 工具调用轨迹折叠面板 + 打字指示器
- **输入区**：原生 textarea 自动高度 + IME 中文输入兼容 + 模型内嵌选择 + 渐变发送按钮 + 快捷键提示

### 前端基础设施

- **axios 拦截器**：请求自动附加 JWT（`Authorization: Bearer`），401 自动跳转登录
- **路由守卫**：未登录重定向 `/login`，已登录访问 `/login` 重定向 `/chat`
- **API 封装**：`api/index.js` 按模块分类（auth / agent / chat / meta / model / memory / skill / mcp / usage / context）
- **ECharts**：vue-echarts 用于用量管理页的图表渲染
- **Vite 代理**：开发时 `/v1` 代理到后端 8000 端口

## 🖥️ 桌面端

基于 **Electron** 的桌面端应用（类 TeleAgent / WorkBuddy 体验），将 Web 前端 + Python 后端打包为原生桌面应用。

### 核心功能

| 功能 | 说明 |
|---|---|
| **自动启动后端** | 启动 APP 时自动 spawn `openfox-server`，轮询 `/healthz` 等待就绪；若后端已在运行则直接复用 |
| **启动屏（Splash）** | 紫色渐变启动屏，实时显示后端启动状态和进度条 |
| **系统托盘** | 关闭窗口 → 最小化到托盘；首次提示用户；单击切换显示/隐藏；双击恢复 |
| **原生菜单栏** | 文件（新建会话 Ctrl+N）、编辑、视图（7 个页面快捷切换 Ctrl+1~7）、后端（重启/重载）、帮助 |
| **全局快捷键** | `Ctrl+Shift+Space` 呼出/隐藏窗口；`Ctrl+Shift+N` 新建会话 |
| **开机自启** | 托盘菜单一键开启，支持 `--hidden` 参数静默启动 |
| **自动更新** | 基于 electron-updater + GitHub Releases，启动 5 秒后静默检查，支持下载进度和安装提示 |
| **窗口状态记忆** | 自动保存和恢复窗口位置、大小、最大化状态 |
| **单实例锁** | 防止多开，二次启动自动聚焦到已有窗口 |
| **前端适配** | Electron 模式自动切换 hash 路由、API 直连后端、标题栏拖拽区域适配 |

### 文件结构

```
desktop/
├── main.js           # 主进程：生命周期 + 窗口创建 + IPC 通信 + 全局快捷键
├── preload.js        # 预加载脚本：contextBridge 安全暴露 Electron API
├── backend.js        # 后端进程管理器（spawn + /healthz 健康检查 + 优雅关闭）
├── tray.js           # 系统托盘（最小化到托盘 + 右键菜单 + 开机自启开关）
├── menu.js           # 原生菜单栏（文件/编辑/视图/后端/帮助 五组菜单）
├── updater.js        # 自动更新（electron-updater + 下载进度 + 安装提示）
├── window-state.js   # 窗口状态持久化（位置/大小/最大化 → userData JSON）
├── splash.html       # 启动屏（紫色渐变 + 派蒙 Logo + 状态指示 + 进度条）
├── assets/icon.png   # 应用图标（复用派蒙 logo）
└── package.json      # 依赖声明 + electron-builder NSIS 打包配置
```

### 使用方式

```bash
# 1. 安装依赖（首次）
cd desktop && npm install

# 2. 开发模式（同时启动 Vite 开发服务器 + Electron）
npm run dev
# 等价于：concurrently "cd ../web && npm run dev" "wait-on tcp:5173 && electron ."

# 3. 生产构建（Vue 前端 + Electron 打包）
npm run build
# 输出：desktop/dist/OpenFox-Setup-1.0.0.exe（NSIS 安装包）

# 4. 快速构建（仅打包目录，不生成安装包）
npm run build:dir
```

**前提条件**：Python 3.10+ 已安装且项目已 `pip install -e .`，后端进程由 Electron 自动管理。

### 桌面端架构

```
┌─────────────────────────────────────────────────────────┐
│                    Electron Main Process                  │
│                                                          │
│  1. createSplash()   → 显示启动屏（紫色渐变 + 进度条）     │
│  2. BackendManager.start()                              │
│     ├─ findPython()     → 查找 Python 3 可执行文件       │
│     ├─ spawn()          → 启动 openfox-server 子进程      │
│     └─ waitForHealth()  → 轮询 /healthz 直到后端就绪     │
│  3. createMainWindow() → 加载 Vue3 前端（hash 路由）      │
│  4. createTray()       → 系统托盘 + 右键菜单              │
│  5. buildMenu()        → 原生菜单栏                      │
│  6. registerShortcuts() → 全局快捷键                     │
│  7. updater.init()     → 自动更新（生产模式）              │
│                                                          │
│  关闭窗口 → 隐藏到托盘（不退出）                           │
│  托盘退出 → kill 后端进程 → 退出应用                      │
└─────────────────────────────────────────────────────────┘
         │                              │
    preload.js                   BackendManager
   (contextBridge)               (child_process)
         │                              │
         ▼                              ▼
   Vue3 前端                    Python 后端
  (hash 路由)               (FastAPI :8000)
   直连 /v1                   openfox-server
```

### 前端适配

Vue3 前端自动检测 Electron 环境（`window.electronAPI.isElectron`），适配点包括：

- **路由模式**：Electron 使用 `createWebHashHistory()`（兼容 `file://` 协议），Web 使用 `createWebHistory()`
- **API baseURL**：Electron 直连 `http://127.0.0.1:8000/v1`，Web 使用 Vite 代理 `/v1`
- **标题栏拖拽**：header 区域加 `-webkit-app-region: drag`，交互元素加 `no-drag`
- **菜单事件**：监听 `menu:action` / `menu:navigate` 实现原生菜单联动
- **退出应用**：用户下拉菜单新增"退出应用"选项（仅 Electron 可见）

### 构建产物

| 平台 | 格式 | 输出路径 | 说明 |
|---|---|---|---|
| Windows | `.exe` (NSIS) | `desktop/dist/OpenFox-Setup-1.0.0.exe` | 安装包，支持自定义安装目录、桌面快捷方式、开始菜单 |
| Windows | 目录 | `desktop/dist/win-unpacked/` | 免安装版，直接运行 `openfox.exe` |

## 🛠️ 自定义工具扩展

OpenFox 提供**两类外部工具**的动态加载能力：本地 Python 自定义函数 + MCP 第三方工具集。无需硬编码，约定优于配置，Vibe Coding 友好（AgentLoop 会主动引导用户如何新增工具）。

### 本地 Python 自定义工具（`./tools/`）

每个工具 = 一个 `.py` 文件 + `@tool` 装饰器。文件保存即可自动注册（watchdog 热加载），无需重启。

模板 `tools/example_tool.py`：

```python
from typing import Optional
from open_fox.tools import tool

@tool(name="read_head", description="读文件前 N 行")
def read_head(path: str, n: int = 10) -> str:
    """
    读取文本文件前 n 行。

    Args:
        path: 待读取的文件路径
        n: 返回的行数上限
    """
    ...
```

**约束**：
- `name` 全局唯一（不与 builtin / MCP 工具冲突）；`description` 必填
- 函数支持**同步** / **`async`**；返回值 `ToolResult` / `str` / 其他自动归一化
- 类型注解 → OpenAI schema（自动映射 `str` / `int` / `Optional[T]` / `List[T]` / `Literal` / `Dict`）
- docstring 支持 **Google** / **NumPy** / **Sphinx** 三风格；参数说明自动合并进 schema
- 异常自动捕获 → `ToolResult(success=False, error="本地工具异常：...")`
- 文件名不必等于 `name`，但建议一致；`__init__.py` 与 `_*.py` 会被跳过

### MCP 第三方工具（`./mcps/`）

每个 MCP server = 一份 `*.yaml` 或 `*.json` 配置文件。启动时自动扫描 + 连接，工具命名 `<server>__<tool>`。

**stdio 模式**（本地子进程）：

```yaml
# mcps/local-filesystem.yaml
name: local-filesystem-mcp
transport: stdio
command: "npx"
args:
  - "-y"
  - "@modelcontextprotocol/server-filesystem"
  - "./workspace"
enabled: true
timeout: 30
tool_allowlist: []
tool_denylist: []
permissions:
  allow_read: true
  allow_write: false
```

**streamable-http / SSE 模式**（远程服务）：

```yaml
# mcps/remote-kg.yaml
name: remote-kg
transport: streamable-http          # 或 sse
url: "https://example.com/mcp"
headers:
  Authorization: "Bearer ${MCP_TOKEN}"   # ${VAR} 运行时从环境变量替换
enabled: true
timeout: 30
tool_allowlist: []
tool_denylist: []
```

**关键约定**：
- **不要明文硬编码 token**，用 `${VAR}` 占位符 + 环境变量（或 `.env` 文件）
- `headers` value 走 `_substitute_env()` 替换（`${VAR}` 单花括号）；找不到变量 → 空串 + warning
- 一 server 一文件；重复 `name` → 后者跳过（按文件名字典序）
- YAML 解析注意：含 `-` 的值（如 `streamable-http`）要加引号
- `tool_allowlist` / `tool_denylist`：先 allow 后 deny；空 = 全部
- `enabled: false`：跳过该 server（不报错）

### 迁移旧配置

如果你之前在 `config.yaml` 的 `mcp_servers` 段配过 MCP：

```bash
python scripts/migrate_mcp_config.py
# 自动生成 mcps/<server-name>.yaml（不动原 config.yaml）
# 然后手动删除 config.yaml 的 mcp_servers 段
```

### 重载（hot reload）

| 入口 | 命令 | 作用 |
|---|---|---|
| CLI | `/reload` | 重扫 tools/ + mcps/，重连 MCP，**不重启进程** |
| HTTP | `POST /v1/reload` | 同上，返回 `{custom_tools, mcp_servers, mcp_tools, errors}` |
| Skill | watchdog 自动 | `./skills/` 新增 / 修改 / 删除自动热加载，无需重启 |

**`/reload` 局限**：重载 yaml 配置 + 重连 MCP，但**不**重新 import Python 模块。改 `src/open_fox/` 下的代码必须重启进程。

### 错误前缀分类

工具调用失败时 `ToolResult.error` 前缀：

| 前缀 | 来源 |
|---|---|
| `本地工具异常：` | 自定义 Python 工具异常（FunctionTool 自动捕获） |
| `MCP 连接失败：` | MCP transport 连接失败 |
| `MCP 调用失败：` | MCP server 业务错误 |

### 排错速查表

| 现象 | 可能原因 | 排查 |
|---|---|---|
| `tools/` 加了新文件但没注册 | `__init__.py` / `_*.py` 命名或 Python 语法错 | `AGENT_SKILLS_DEBUG=1` 重启看日志；用 `/reload` 兜底 |
| `mcps/` 文件加载失败 | YAML 语法 / 字段缺失 / 重复 `name` / transport 非法 | 启动日志 + 错误前缀 `MCP 配置 ... 跳过` |
| MCP 连接 `406 Not Acceptable` | streamable-http server 要求特定 `Accept` 头（已内置 `Accept: application/json, text/event-stream`） | 升级到最新 `transports/sse.py`；或自定义 `headers` |
| 错误前缀含 `[` 字符崩溃 Rich UI | render_error 未 escape markup（已修复） | 升级到最新 `cli.py` |
| CLI 启动时 MCP 没加载 | `repl()` 未调 `load_mcp_configs`（已修复） | 升级到最新 `cli.py`；或重启 + 检查日志 |
| `${VAR}` 未替换 | 环境变量未设 / `.env` 未加载 | `echo $MCP_TOKEN`；python-dotenv 自动加载 `.env` |

### 安全提示

- `./tools/` 等价于**信任区域**——装饰器函数是任意 Python 代码，无沙箱。请勿放入不受信任的代码
- `./mcps/` 启动的 stdio 子进程受 `command_blacklist` 保护（拦截 `rm -rf /`、`mkfs`、`shutdown` 等）
- `./mcps/` 远程 HTTP/SSE 调用的 headers 字段仅做 `${VAR}` 占位符替换，原样透传；鉴权由上游 server 负责

---

## 🧪 测试

```bash
python -m pytest -q                      # 全部测试
python -m pytest tests/unit/test_agent_config.py -v   # 单个文件
ruff check src tests                     # lint
```

**已知预存失败**：`tests/unit/test_config.py::test_load_config_with_defaults`（测试期望 `max_agent_steps==20`，config.yaml 实际是 50），跑全量测试时排除：

```bash
python -m pytest -q --deselect tests/unit/test_config.py::test_load_config_with_defaults
```

OpenAI 客户端集成测试需先启动 server 并设置环境变量：

```bash
openfox-server --host 127.0.0.1 --port 8765 &
AGENT_SKILLS_TEST_LIVE=1 AGENT_SKILLS_TEST_URL=http://127.0.0.1:8765/v1 \
  pytest tests/integration/test_openai_client.py -v
```

## ⚠️ 安全说明

- **路径白名单**：文件操作仅允许 `./skills/` 与 `./workspace/`，路径穿越（`..`）被拒绝
- **命令黑名单**：`rm -rf /`、`mkfs`、`shutdown`、fork bomb 等危险命令被拦截
- **脚本环境隔离**：Skill 脚本执行时剥离 `OPENAI_API_KEY` / `MCP_TOKEN` / `AWS_SECRET_ACCESS_KEY` 等敏感环境变量；超时自动杀进程
- **API key 安全**：通过 `.env` 管理（gitignore），不写入 YAML

> ⚠️ 框架的安全机制只能降低已知风险，请**只加载来自可信来源的 Skill**。

## 📄 许可证

MIT License

## 🙏 致谢

本项目参考 [agentskills.io](https://agentskills.io) 的标准 Skill 渐进式披露设计，并受 [Claude Code](https://claude.ai/code) CLI 体验启发。

> AI生成
