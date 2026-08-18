# GIF 录制指南

## 方式一：macOS 录屏（推荐，最真实）

### 准备
1. 终端字体调到 18pt+，背景用深色
2. 准备一个测试项目目录 `~/demo-project`
3. 确保 superpowers-zh 已安装

### 录制步骤
1. **Cmd+Shift+5** 打开录屏，选择录制区域（只录终端窗口）
2. 执行以下操作：

```bash
# 第一步：安装（3秒）
cd ~/demo-project
npx superpowers-zh

# 第二步：给 AI 提需求（等 AI 回复）
claude "给用户模块加一个批量导出功能"
```

3. 等 AI 输出中文的头脑风暴内容（澄清问题 + 方案），录到这里就可以停了
4. 停止录屏

### 转 GIF
```bash
# mov 转 gif（用 ffmpeg）
ffmpeg -i recording.mov -vf "fps=10,scale=700:-1:flags=lanczos" -c:v gif docs/assets/demo.gif

# 如果太大（>2MB），降低 fps 或尺寸
ffmpeg -i recording.mov -vf "fps=8,scale=600:-1:flags=lanczos" -c:v gif docs/assets/demo.gif
```

## 方式二：VHS 脚本（模拟输入，输出需要手动编排）

```bash
cd /Users/yx/work/wenzhang/superpowers-zh
vhs docs/assets/demo.tape
```

注意：VHS 只模拟键盘输入，AI 输出需要在 tape 文件中用 Type 模拟。

## 最终效果要求
- 时长：15-20 秒
- 文件大小：< 2MB
- 关键帧：能看到 AI 用中文输出设计方案/澄清问题
