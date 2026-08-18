Output docs/assets/demo.gif
Set FontSize 16
Set Width 900
Set Height 520
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms
Set Padding 20

# Scene 1: Install superpowers-zh
Type "cd ~/my-project && npx superpowers-zh"
Enter
Sleep 1s

# Simulate install output
Set TypingSpeed 0ms
Type@0ms ""
Sleep 300ms

Ctrl+L

Set TypingSpeed 0ms

# Simulated install output line by line
Type "  superpowers-zh v1.2.0"
Enter
Sleep 200ms
Type "  Detected: Claude Code"
Enter
Sleep 200ms
Type "  Installing 20 skills to .claude/skills/ ..."
Enter
Sleep 500ms
Type "  ✓ 14 translated skills installed"
Enter
Sleep 200ms
Type "  ✓ 6 Chinese-specific skills installed"
Enter
Sleep 300ms
Type "  Done! Your AI assistant now has superpowers."
Enter
Enter
Sleep 1.5s

# Scene 2: User gives a task
Set TypingSpeed 40ms
Type `claude "给用户模块加一个批量导出功能"`
Enter
Sleep 1.5s

# Simulate AI brainstorming response
Set TypingSpeed 15ms
Type "  Using brainstorming to design this feature"
Enter
Enter
Sleep 300ms
Type "  在开始实现之前，我需要了解几个关键问题："
Enter
Enter
Sleep 200ms
Type "  1. 导出格式是 CSV 还是 Excel？是否需要支持多种格式？"
Enter
Sleep 200ms
Type "  2. 预计数据量多大？超过 1 万条需要考虑异步处理"
Enter
Sleep 200ms
Type "  3. 有权限要求吗？比如只允许管理员导出"
Enter
Sleep 200ms
Type "  4. 需要支持筛选条件导出吗？"
Enter
Enter
Sleep 500ms
Type "  基于常见场景，我初步提出 2 个方案："
Enter
Enter
Sleep 300ms
Type "  方案 A：同步导出（适合 < 5000 条）"
Enter
Type "    - 直接流式写入 Response，用户点击即下载"
Enter
Type "    - 优点：实现简单，无需额外基础设施"
Enter
Type "    - 缺点：大数据量会超时"
Enter
Enter
Sleep 300ms
Type "  方案 B：异步任务 + 下载链接（适合大数据量）"
Enter
Type "    - 后台 Worker 生成文件，完成后通知用户下载"
Enter
Type "    - 优点：不阻塞请求，支持任意数据量"
Enter
Type "    - 缺点：需要消息队列 + 对象存储"
Enter
Enter
Sleep 500ms
Type "  请确认需求细节，我再给出详细设计。"
Enter
Sleep 3s
