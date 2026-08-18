# Superpowers 中文版 — Gemini CLI 安装指南

在 [Gemini CLI](https://github.com/google-gemini/gemini-cli) 中使用 superpowers-zh 的完整指南。

## 自动安装

```bash
cd /your/project
npx superpowers-zh
```

安装脚本会自动检测 `.gemini/` 目录并将 skills 复制到 `.gemini/skills/` 目录。

## 手动安装

```bash
git clone https://github.com/jnMetaCode/superpowers-zh.git
cp -r superpowers-zh/skills /your/project/.gemini/skills
```

或作为 Gemini 扩展安装（全局）：

```bash
mkdir -p ~/.gemini/extensions/superpowers-zh/skills
cp -r superpowers-zh/skills/* ~/.gemini/extensions/superpowers-zh/skills/
cp superpowers-zh/gemini-extension.json ~/.gemini/extensions/superpowers-zh/
```

## 通过 GEMINI.md 引用

在项目根目录的 `GEMINI.md` 中引用 skills：

```markdown
# 工作方法论

请参考 .gemini/skills/ 目录中的 SKILL.md 文件。
遇到新功能开发时，先使用 brainstorming skill。
编写代码时，遵循 test-driven-development skill。
```

## Skill 加载优先级

| 位置 | 优先级 | 说明 |
|------|--------|------|
| `.gemini/skills/` | 最高 | 项目级，仅当前项目 |
| `~/.gemini/extensions/*/skills/` | 中 | 扩展级，所有项目共享 |

## 故障排查

### Skills 未生效

1. 确认 `.gemini/skills/` 目录存在且包含 skill 文件夹
2. 每个 skill 需要包含有效 YAML frontmatter 的 `SKILL.md` 文件
3. 重启 Gemini CLI

### 扩展模式未加载

1. 检查 `gemini-extension.json` 是否正确放在扩展目录中
2. 确认扩展目录结构：`~/.gemini/extensions/superpowers-zh/`

## 获取帮助

- 提交 Issue：https://github.com/jnMetaCode/superpowers-zh/issues
- 项目主页：https://github.com/jnMetaCode/superpowers-zh
- Gemini CLI 文档：https://github.com/google-gemini/gemini-cli
