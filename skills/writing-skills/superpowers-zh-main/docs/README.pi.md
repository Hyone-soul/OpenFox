# Superpowers 中文版 · Pi 指南

在 [Pi](https://github.com/earendil-works/pi)（oh-my-pi）上使用 superpowers-zh 的完整说明。

## 安装

superpowers-zh 通过 Pi 的扩展机制集成，**直接指向仓库现有的 `skills/` 目录**——不复制 skill、不建 symlink、无额外运行时依赖。

集成由 `package.json` 里的 `pi` 字段声明：

```json
"pi": {
  "skills": ["./skills"],
  "extensions": ["./.pi/extensions/superpowers.ts"]
}
```

并带 `pi-package` keyword，便于 Pi 发现这是一个 Pi 包。

按 Pi 的包安装方式安装 `superpowers-zh`（参考 Pi 文档的包管理命令），Pi 会读取上述 `pi` 配置，挂载 `skills/` 并加载 `.pi/extensions/superpowers.ts` 扩展。

## 工作原理

`.pi/extensions/superpowers.ts` 注册了 Pi 的生命周期钩子：

1. **`resources_discover`** — 把仓库的 `skills/` 目录贡献给 Pi 的技能系统；
2. **`session_start` / `session_compact`** — 标记需要重新注入 bootstrap；
3. **`context`** — 在会话上下文中注入 `using-superpowers` 的内容（去除 frontmatter）+ Pi 工具映射，作为「You have superpowers」bootstrap，让 skill 在恰当时机被遵循；
4. **`agent_end`** — 一轮结束后停止重复注入。

注入带有唯一标记，已存在时不会重复注入；并且会插入到 compaction summary 之后，避免被压缩流程吞掉。

## 工具映射

Pi 有原生技能系统，但**不暴露** `Skill` 工具。skill 内容描述「动作」，在 Pi 上对应到小写工具：

- 「调用某个 skill」→ Pi 原生技能：用 `read` 加载对应 `SKILL.md`，或由人类显式 `/skill:name`
- 「读/写/改文件」→ `read` / `write` / `edit`
- 「跑 shell 命令」→ `bash`
- 「搜索文件内容」→ `grep`，「按名找文件」→ `find`，「列目录」→ `ls`
- 「分派子智能体」→ 若装了 `pi-subagents` 的 `subagent` 工具则用之；没有则在本会话内完成或说明能力缺失，**不要**臆造 `Task` 调用
- 「待办清单」→ 若装了 todo/task 工具则用之；否则用 plan 文件或仓库内 `TODO.md` 跟踪；旧的 `TodoWrite` 引用按此处理

完整映射见 [`skills/using-superpowers/references/pi-tools.md`](../skills/using-superpowers/references/pi-tools.md)，扩展也会把同样的映射注入会话。

## 验证

```bash
bash tests/pi/run-tests.sh
```

该测试动态加载扩展并校验：声明了 `pi` 包配置、注册了正确的生命周期钩子（且无 pre-compaction 注入）、`resources_discover` 贡献了 `skills/` 目录、`session_start` 注入了「You have superpowers」+「Pi tool mapping」、pi-tools 参考文档存在。

> 注：扩展是 TypeScript（仅 `import type`，运行时无类型依赖）。Node 22.6–23.5 需 `--experimental-strip-types`（run-tests.sh 已带），23.6+ 默认支持。
