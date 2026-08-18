# 为 OpenCode 安装 Superpowers 中文版

## 前置条件

- 已安装 [OpenCode.ai](https://opencode.ai)

## 安装步骤

在你的 `opencode.json`（全局或项目级别）中将 superpowers-zh 添加到 `plugin` 数组：

```json
{
  "plugin": ["superpowers@git+https://github.com/jnMetaCode/superpowers-zh.git"]
}
```

重启 OpenCode。完成——插件会自动安装并注册所有 skills。

通过询问来验证："告诉我你的超能力"

## 从旧版符号链接安装方式迁移

如果你之前使用 `git clone` 和符号链接安装过 superpowers，请移除旧的配置：

```bash
# 移除旧的符号链接
rm -f ~/.config/opencode/plugins/superpowers.js
rm -rf ~/.config/opencode/skills/superpowers

# 可选：移除克隆的仓库
rm -rf ~/.config/opencode/superpowers

# 如果你在 opencode.json 中为 superpowers 添加过 skills.paths，请将其移除
```

然后按照上面的安装步骤操作。

## 使用方法

使用 OpenCode 的原生 `skill` 工具：

```
use skill tool to list skills
use skill tool to load superpowers/brainstorming
```

## 更新

Superpowers 会在你重启 OpenCode 时自动更新。

要固定到特定版本：

```json
{
  "plugin": ["superpowers@git+https://github.com/jnMetaCode/superpowers-zh.git#v1.0.0"]
}
```

## 故障排除

### 插件未加载

1. 检查日志：`opencode run --print-logs "hello" 2>&1 | grep -i superpowers`
2. 验证 `opencode.json` 中的插件配置
3. 确保你运行的是最新版本的 OpenCode

### Skills 未找到

1. 使用 `skill` 工具列出已发现的内容
2. 检查插件是否已加载（见上文）

### 工具映射

当 skills 引用 Claude Code 工具时：
- `TodoWrite` → `todowrite`
- `Task` 子代理 → `@mention` 语法
- `Skill` 工具 → OpenCode 的原生 `skill` 工具
- 文件操作 → 你的原生工具

## 获取帮助

- 报告问题：https://github.com/jnMetaCode/superpowers-zh/issues
- 完整文档：https://github.com/jnMetaCode/superpowers-zh
