# Superpowers 中文版 — OpenCode 安装指南

在 [OpenCode.ai](https://opencode.ai) 中使用 superpowers-zh 的完整指南。

## 安装

在 `opencode.json`（全局或项目级）的 `plugin` 数组中添加：

```json
{
  "plugin": ["superpowers@git+https://github.com/jnMetaCode/superpowers-zh.git"]
}
```

重启 OpenCode。插件通过 Bun 自动安装并注册所有 skills。

验证方式：问 "告诉我你有哪些 superpowers"

## 使用

### 查找 Skills

使用 OpenCode 原生的 `skill` 工具列出所有可用 skills：

```
use skill tool to list skills
```

### 加载 Skill

```
use skill tool to load superpowers/brainstorming
```

### 个人 Skills

在 `~/.config/opencode/skills/` 中创建你自己的 skills：

```bash
mkdir -p ~/.config/opencode/skills/my-skill
```

创建 `~/.config/opencode/skills/my-skill/SKILL.md`：

```markdown
---
name: my-skill
description: 当 [条件] 时使用 - [功能描述]
---

# 我的 Skill

[你的 skill 内容]
```

### 项目 Skills

在项目的 `.opencode/skills/` 目录中创建项目级 skills。

**Skill 优先级：** 项目 skills > 个人 skills > Superpowers skills

## 更新

重启 OpenCode 时自动更新。插件每次启动都从 git 仓库重新安装。

锁定特定版本：

```json
{
  "plugin": ["superpowers@git+https://github.com/jnMetaCode/superpowers-zh.git#v1.0.0"]
}
```

## 工作原理

插件做两件事：

1. **注入引导上下文** — 通过 `experimental.chat.system.transform` hook，为每次对话添加 superpowers 意识
2. **注册 skills 目录** — 通过 `config` hook，让 OpenCode 发现所有 skills，无需符号链接或手动配置

### 工具映射

为 Claude Code 编写的 skills 自动适配 OpenCode：

- `TodoWrite` → `todowrite`
- `Task`（子代理）→ OpenCode 的 `@mention` 系统
- `Skill` 工具 → OpenCode 原生 `skill` 工具
- 文件操作 → OpenCode 原生工具

## 故障排查

### 插件未加载

1. 检查 OpenCode 日志：`opencode run --print-logs "hello" 2>&1 | grep -i superpowers`
2. 确认 `opencode.json` 中的插件配置正确
3. 确保运行的是最新版本的 OpenCode

### Skills 未找到

1. 使用 `skill` 工具列出可用 skills
2. 检查插件是否正确加载（见上）
3. 每个 skill 需要包含有效 YAML frontmatter 的 `SKILL.md` 文件

## 获取帮助

- 提交 Issue：https://github.com/jnMetaCode/superpowers-zh/issues
- 项目主页：https://github.com/jnMetaCode/superpowers-zh
- OpenCode 文档：https://opencode.ai/docs/
