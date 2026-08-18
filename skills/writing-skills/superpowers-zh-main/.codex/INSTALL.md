# 为 Codex 安装 Superpowers 中文版

通过原生 skill 发现机制在 Codex 中启用 superpowers skills。只需克隆并创建符号链接。

## 前置条件

- Git

## 安装步骤

1. **克隆 superpowers-zh 仓库：**
   ```bash
   git clone https://github.com/jnMetaCode/superpowers-zh.git ~/.codex/superpowers
   ```

2. **创建 skills 符号链接：**
   ```bash
   mkdir -p ~/.agents/skills
   ln -s ~/.codex/superpowers/skills ~/.agents/skills/superpowers
   ```

   **Windows (PowerShell)：**
   ```powershell
   New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.agents\skills"
   cmd /c mklink /J "$env:USERPROFILE\.agents\skills\superpowers" "$env:USERPROFILE\.codex\superpowers\skills"
   ```

3. **重启 Codex**（退出并重新启动 CLI）以发现 skills。

## 从旧版引导方式迁移

如果你在原生 skill 发现机制之前安装过 superpowers，需要：

1. **更新仓库：**
   ```bash
   cd ~/.codex/superpowers && git pull
   ```

2. **创建 skills 符号链接**（上面的步骤 2）——这是新的发现机制。

3. **移除旧的引导代码块**——删除 `~/.codex/AGENTS.md` 中引用 `superpowers-codex bootstrap` 的代码块，已不再需要。

4. **重启 Codex。**

## 验证

```bash
ls -la ~/.agents/skills/superpowers
```

你应该看到一个符号链接（Windows 上为目录连接），指向你的 superpowers skills 目录。

## 更新

```bash
cd ~/.codex/superpowers && git pull
```

Skills 通过符号链接即时更新。

## 卸载

```bash
rm ~/.agents/skills/superpowers
```

可选：删除克隆的仓库：`rm -rf ~/.codex/superpowers`。
