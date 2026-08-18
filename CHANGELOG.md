---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '9d1fb1df-9bc7-460d-a8fc-9125bdfac72b'
  PropagateID: '9d1fb1df-9bc7-460d-a8fc-9125bdfac72b'
  ReservedCode1: 'ff638e70-db07-4fa1-ab2f-e6a76a7e6a7c'
  ReservedCode2: 'ff638e70-db07-4fa1-ab2f-e6a76a7e6a7c'
---

# CHANGELOG

OpenFox 项目的所有重要变更记录。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

### 新增能力

- **桌面端 Electron APP**：自动启动后端、系统托盘最小化、全局快捷键呼出、原生菜单栏、开机自启、启动屏、窗口状态记忆、NSIS 安装包一键分发
- **PyInstaller 后端打包**：后端独立打包为 `openfox-backend.exe`，安装包无需 Python 环境即可运行
- **聊天推理（Thinking）实时展示**：推理模型（如 DeepSeek-R1）的 `reasoning_content` 在 Web/桌面端实时渲染为可折叠的「思考过程」区块，替代纯省略号等待
- **项目关联**：会话可关联工作目录（项目），侧栏按项目分组展示会话
- **Slash 命令面板**：Codex 风格 `/` 命令面板（/model、/new、/compact、/skill、/memory、/help），`/model` 直接展开模型列表切换
- **上下文压缩**：`/compact` 命令触发 Hermes 三层压缩算法，聊天标题栏实时显示上下文用量状态
- **未配置 Key 友好提示**：模型 API Key 为空时返回 400 + 中文提示 + 「去设置」按钮，不再报 `Illegal header value`

### 修复

- **桌面端启动崩溃**：安装目录（Program Files）不可写 → 工作目录切到 `%APPDATA%\OpenFox`，首启自动拷贝 config/skills/tools/mcps
- **更新弹窗 404**：移除启动自动检查更新，手动检查失败改为静默不弹窗
- **会话切换消息丢失**：修复 `rebuildToolEvents` / `safeParseArgs` 函数误删导致切换会话后消息列表无法重建的问题
- **推理内容前端丢失**：修复 `assistant_delta` 事件中 `reasoning` 字段被前端忽略，导致推理模型思考阶段只显示省略号的问题

## [0.2.0] - 自定义工具扩展（custom-tool-extensions）

### ⚠️ 破坏性变更

- **移除 `config.yaml` 的 `mcp_servers` 内联段**：MCP server 配置改用拆分文件方案，统一放 `./mcps/<name>.yaml`，由 `core/mcp/config_loader.py` 加载。`AppConfig.mcp_servers` 字段已删除
- **迁移脚本**：`python scripts/migrate_mcp_config.py [--config config.yaml] [--out mcps/]` 一键从历史 config.yaml 把 mcp_servers 拆分为多个独立 YAML 文件。**不修改**原 config.yaml（用户手动删除原段）

### 新增能力

- **`./tools/` 本地自定义工具**：把继承 `BaseTool` 的 Python 文件放到 `./tools/`，启动自动加载（`core/custom_tools/loader.py`）
- **`@register_tool` 装饰器**（`core/tools/decorator.py`）：把普通函数一行包装成 `FunctionTool`，免去手写 class
- **`./mcps/<name>.yaml` 拆分配置**：每个 MCP server 独立文件，`${VAR}` 占位符运行时替换
- **`/reload` CLI 命令 + `POST /v1/reload` 端点**：热重载 custom_tools + mcp + skills（保护内置工具）
- **`GET /v1/mcps` 端点**：列出已加载的 MCP server 及其工具
- **`GET /v1/tools` 带 `source` 字段**：标识每个工具来源（`builtin` / `custom` / `mcp`）
- **`McpServerConfig` 字段扩展**：`enabled` / `timeout` / `tool_allowlist` / `tool_denylist` / `permissions` —— 支持细粒度控制

### 实现细节

- 新增模块：
  - `src/open_fox/core/custom_tools/loader.py` —— `./tools/` 扫描
  - `src/open_fox/core/custom_tools/reload.py` —— 热重载
  - `src/open_fox/core/custom_tools/schema_builder.py` —— 从 docstring/类型注解生成 schema
  - `src/open_fox/core/mcp/config_loader.py` —— `./mcps/*.yaml` 加载
  - `src/open_fox/tools/decorator.py` —— `@register_tool` 装饰器
  - `scripts/migrate_mcp_config.py` —— 一次性迁移脚本
- `server.py` 的 `build_components` 元组从 **9 组件扩展到 10 组件**（新增 `custom_tools_loader` + `mcp_config_loader`），所有解包点已同步更新
- `lifespan` 启动时自动 reload（custom_tools + mcp + skills）
- 新增测试：
  - `tests/unit/test_custom_tools_loader.py`
  - `tests/unit/test_decorator.py`
  - `tests/unit/test_function_tool.py`
  - `tests/unit/test_schema_builder.py`
  - `tests/unit/test_mcp_config_loader.py`
  - `tests/unit/test_mcp_filters.py`
  - `tests/unit/test_mcp_client_reload.py`
  - `tests/unit/test_reload_protects_builtin.py`
  - `tests/unit/test_migrate_script.py`

### 文档更新

- README.md 新增「🛠️ 自定义工具扩展」章节（含本地工具 / MCP / 重载 / 错误排查 / 安全 5 个子节）
- config.example.yaml 删除 `mcp_servers` 段，顶部加迁移提示注释
- CLAUDE.md 核心模块 +3 行、关键约定 +3 行、HTTP API +3 行

### 升级指引

1. 运行迁移脚本：`python scripts/migrate_mcp_config.py --config config.yaml --out mcps/`
2. 检查生成的 `./mcps/*.yaml` 文件，按需补充 `enabled: true` 等新字段
3. 手动删除 `config.yaml` 里的 `mcp_servers:` 段
4. 重启服务：`openfox-server` / `OpenFox`