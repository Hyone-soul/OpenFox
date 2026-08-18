# Superpowers 中文版 · Kimi Code 指南

在 [Kimi Code](https://github.com/MoonshotAI/kimi-code) 上使用 superpowers-zh 的完整说明。

## 安装

superpowers-zh 通过 Kimi Code 的插件清单 `.kimi-plugin/plugin.json` 集成，**直接指向仓库现有的 `skills/` 目录**——不复制 skill、不建 symlink、不装 hook、无任何运行时依赖。

打开插件管理器：

```text
/plugins
```

如果 Kimi 插件市场已收录，进入 `Marketplace` > `Superpowers 中文版` 安装即可。

也可以直接从本仓库安装：

```text
/plugins install https://github.com/jnMetaCode/superpowers-zh
```

如需验证尚未发布的改动，显式指定分支：

```text
/plugins install https://github.com/jnMetaCode/superpowers-zh/tree/main
```

Kimi Code 在**新会话**才会应用插件变更。安装、更新、启用、禁用或重载插件后，用 `/new` 开一个新会话。

## 工作原理

Kimi 插件清单位于 `.kimi-plugin/plugin.json`，做三件事：

1. 把 Kimi Code 指向仓库现有的 `skills/` 目录；
2. 通过 `sessionStart.skill` 在会话开始时加载 `using-superpowers`（这是让 skill 在恰当时机自动触发的关键）；
3. 通过 `skillInstructions` 提供 Kimi 专属的工具映射。

## 工具映射

skill 内容描述的是「动作」而非写死某个运行时的工具名。在 Kimi Code 上它们对应到：

- 「向用户提问」/「问澄清问题」/「给出多选项」→ `AskUserQuestion`
- 「创建待办」/「在待办清单中标记完成」→ `TodoList`
- 「分派子智能体」/「Task tool (general-purpose)」→ `Agent`（用 Kimi 的 subagent 类型，如 `coder`/`explore`/`plan`，**不要**传 `general-purpose`）
- 「调用某个 skill」→ Kimi Code 原生 `Skill` 工具
- 「读文件」/「写文件」/「改文件」→ `Read` / `Write` / `Edit`
- 「跑 shell 命令」→ `Bash`
- 「搜索文件内容」→ `Grep`
- 「按路径/模式找文件」→ `Glob`
- 「抓取 URL」→ `FetchURL`
- 「联网搜索」→ `WebSearch`

完整映射写在清单的 `skillInstructions` 字段里，由 Kimi 在运行时读取。

## 更新

用 Kimi Code 的插件管理器：

```text
/plugins
```

选中 Superpowers 中文版更新，更新后用 `/new` 开新会话。

## 排错

### 插件没加载

1. 跑 `/plugins info superpowers-zh` 看诊断信息；
2. 确认插件已启用；
3. 安装或更新后用 `/new` 开新会话。

### 直接 GitHub 安装装到了旧版本

对于裸仓库 URL，Kimi Code 会装最新的 GitHub release（若存在）。要在下一个 release 前测试未发布的改动，显式指定分支：

```text
/plugins install https://github.com/jnMetaCode/superpowers-zh/tree/main
```

### skill 不触发

1. 用 `/plugins info superpowers-zh` 确认插件已启用；
2. 用 `/new` 开新会话；
3. 试验收提示词：`我们来做个 react todo list`。集成正常的话，会在写任何代码之前先加载 `brainstorming`。
