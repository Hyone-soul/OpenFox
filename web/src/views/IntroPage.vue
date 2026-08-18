<template>
  <div class="intro-page">
    <!-- Hero -->
    <section class="hero">
      <div class="hero-glow" />
      <div class="hero-content">
        <div class="hero-badge">
          <span class="badge-dot" />
          <span>开源 Agent Skills 框架</span>
        </div>
        <h1 class="hero-title">
          让 AI 拥有<br />
          <span class="gradient-text">可组装的技能</span>
        </h1>
        <p class="hero-desc">
          OpenFox 是一个自研的 Agent Skills 框架 —— Python + FastAPI 后端、Vue3 前端。
          OpenAI 完全兼容、Skill 渐进式披露、MCP 扩展、CLI + HTTP + Web 三端入口。
        </p>
        <div class="hero-actions">
          <router-link to="/login" class="btn-primary">开始使用</router-link>
          <a href="https://github.com" target="_blank" class="btn-ghost">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.009-.866-.013-1.7-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.646.35-1.086.634-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.268 2.75 1.025A9.578 9.578 0 0112 6.836a9.59 9.59 0 012.504.337c1.909-1.293 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.161 22 16.416 22 12c0-5.523-4.477-10-10-10z"/></svg>
            GitHub
          </a>
        </div>
        <div class="hero-techs">
          <span class="tech-tag">Python 3.10+</span>
          <span class="tech-tag">FastAPI</span>
          <span class="tech-tag">Vue 3</span>
          <span class="tech-tag">Element Plus</span>
          <span class="tech-tag">OpenAI API</span>
        </div>
      </div>
      <!-- Hero 右侧终端预览 -->
      <div class="hero-terminal">
        <div class="terminal-header">
          <span class="terminal-dot red" />
          <span class="terminal-dot yellow" />
          <span class="terminal-dot green" />
          <span class="terminal-title">openfox — CLI</span>
        </div>
        <pre class="terminal-body"><code>❯ 你好，帮我查一下南通今天的天气

✦ 思考中…

┌─ 💭 Thinking ──────────────┐
│ 用户需要查询南通天气，     │
│ 调用天气工具获取实时数据…   │
└────────────────────────────┘

  ⚙ amap__maps_weather(city='南通')
    → {"temperature": "32°C", "weather": "晴", …}

## 南通今日天气

| 指标 | 数据 |
|------|------|
| 天气 | 晴 |
| 温度 | 32°C |
| 湿度 | 65% |

适合户外活动，注意防晒！</code></pre>
      </div>
    </section>

    <!-- 核心特性 -->
    <section class="section features">
      <div class="section-header">
        <h2>核心能力</h2>
        <p>从单次对话到复杂工作流，OpenFox 让 Agent 拥有可组装、可进化的技能体系</p>
      </div>
      <div class="feature-grid">
        <div v-for="f in features" :key="f.title" class="feature-card">
          <div class="feature-icon" :style="{ background: f.bg }">
            <span v-html="f.icon" />
          </div>
          <h3>{{ f.title }}</h3>
          <p>{{ f.desc }}</p>
        </div>
      </div>
    </section>

    <!-- 架构示意 -->
    <section class="section architecture">
      <div class="section-header">
        <h2>架构全景</h2>
        <p>三端入口共享同一套核心引擎，Skill 与 MCP 灵活插拔</p>
      </div>
      <div class="arch-diagram">
        <div class="arch-layer">
          <div class="arch-label">入口层</div>
          <div class="arch-nodes">
            <div class="arch-node cli">CLI (Rich + prompt_toolkit)</div>
            <div class="arch-node http">HTTP (FastAPI + OpenAI API)</div>
            <div class="arch-node web">Web (Vue3 + Element Plus)</div>
          </div>
        </div>
        <div class="arch-arrow">▼</div>
        <div class="arch-layer core">
          <div class="arch-label">核心引擎</div>
          <div class="arch-nodes">
            <div class="arch-node">AgentLoop</div>
            <div class="arch-node">Registry</div>
            <div class="arch-node">Session</div>
            <div class="arch-node">Memory</div>
          </div>
        </div>
        <div class="arch-arrow">▼</div>
        <div class="arch-layer plugin">
          <div class="arch-label">扩展层</div>
          <div class="arch-nodes">
            <div class="arch-node skill">Skills</div>
            <div class="arch-node mcp">MCP</div>
            <div class="arch-node tools">内置工具</div>
            <div class="arch-node custom">自定义工具</div>
          </div>
        </div>
      </div>
    </section>

    <!-- 渐进式披露 -->
    <section class="section progressive">
      <div class="section-header">
        <h2>Skill 渐进式披露</h2>
        <p>不是一次性塞满上下文，而是按需加载 —— 多 Skill 也不浪费 Token</p>
      </div>
      <div class="progressive-steps">
        <div class="step">
          <div class="step-num">L1</div>
          <div class="step-content">
            <h3>索引加载</h3>
            <p>启动时仅读取 Skill 的 <code>name</code> + <code>description</code>，注入系统提示词，几乎不占上下文</p>
          </div>
        </div>
        <div class="step-arrow">→</div>
        <div class="step">
          <div class="step-num">L2</div>
          <div class="step-content">
            <h3>按需全文</h3>
            <p>Agent 判断相关后，通过 <code>read_file</code> 读取 SKILL.md 全文，获取完整工作流指令</p>
          </div>
        </div>
        <div class="step-arrow">→</div>
        <div class="step">
          <div class="step-num">L3</div>
          <div class="step-content">
            <h3>脚本执行</h3>
            <p>按工作流调用 <code>run_shell</code> 执行脚本（Python / Shell / Node），获得结构化结果</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 快速开始 -->
    <section class="section quickstart">
      <div class="section-header">
        <h2>快速开始</h2>
        <p>三步启动你的第一个 Agent</p>
      </div>
      <div class="qs-cards">
        <div class="qs-card">
          <div class="qs-step">1</div>
          <h3>安装</h3>
          <div class="code-block">
            <code>pip install -e .<br/>cd web && npm install</code>
          </div>
        </div>
        <div class="qs-card">
          <div class="qs-step">2</div>
          <h3>配置</h3>
          <div class="code-block">
            <code>cp config.example.yaml config.yaml<br/>cp .env.example .env<br/># 编辑 .env 写入 API Key</code>
          </div>
        </div>
        <div class="qs-card">
          <div class="qs-step">3</div>
          <h3>启动</h3>
          <div class="code-block">
            <code>openfox-server --port 8000<br/>cd web && npm run dev<br/># → http://localhost:5173</code>
          </div>
        </div>
      </div>
    </section>

    <!-- 页脚 -->
    <footer class="intro-footer">
      <div class="footer-brand">
        <img src="/OpenFox.png" class="footer-logo" alt="OpenFox" />
        <span>OpenFox</span>
      </div>
      <p class="footer-copy">开源 Agent Skills 框架 · MIT License · 中电信人工智能公司</p>
    </footer>
  </div>
</template>

<script setup>
const features = [
  {
    title: 'OpenAI 完全兼容',
    desc: '标准 /v1/chat/completions 端点 + SSE 流式 + /v1/models，任何 OpenAI 客户端直连即用',
    icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>',
    bg: '#f1f5f9',
  },
  {
    title: 'Skill 渐进式披露',
    desc: 'L1 索引 → L2 全文 → L3 脚本执行，多 Skill 不浪费上下文 Token',
    icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>',
    bg: '#fef3c7',
  },
  {
    title: 'MCP 扩展生态',
    desc: 'stdio / SSE / streamable-http 三种 transport，一个 YAML 即可注册外部工具服务器',
    icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>',
    bg: '#dbeafe',
  },
  {
    title: '全局记忆系统',
    desc: '跨会话持久记忆，AI 自动提炼 + 四工具增删改查，Agent 越用越懂你',
    icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a7 7 0 017 7c0 2.38-1.19 4.47-3 5.74V17a1 1 0 01-1 1H9a1 1 0 01-1-1v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 017-7z"/><rect x="9" y="20" width="6" height="2" rx="1"/></svg>',
    bg: '#d1fae5',
  },
  {
    title: 'Claude Code 风格 CLI',
    desc: '紫色 prompt、Rich Markdown 渲染、Tab 补全、推理面板、工具轨迹、手动 Skill 激活',
    icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>',
    bg: '#fef3c7',
  },
  {
    title: '平台感知',
    desc: '自动检测 OS / Shell / Python 命令名，注入 system prompt，Windows 用 dir、Linux 用 ls',
    icon: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>',
    bg: '#e0e7ff',
  },
]
</script>

<style scoped>
/* ===== 基础重置 ===== */
.intro-page {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  color: #1f2937;
  overflow-x: hidden;
}

.section {
  max-width: 1120px;
  margin: 0 auto;
  padding: 80px 24px;
}

.section-header {
  text-align: center;
  margin-bottom: 48px;
}

.section-header h2 {
  font-size: 32px;
  font-weight: 800;
  margin: 0 0 12px;
  letter-spacing: -0.5px;
}

.section-header p {
  font-size: 16px;
  color: #6b7280;
  margin: 0;
  max-width: 560px;
  margin-inline: auto;
}

/* ===== Hero ===== */
.hero {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 48px;
  max-width: 1120px;
  margin: 0 auto;
  padding: 80px 24px 60px;
  overflow: hidden;
}

.hero-glow {
  position: absolute;
  top: -200px;
  left: 50%;
  transform: translateX(-50%);
  width: 800px;
  height: 600px;
  background: radial-gradient(ellipse at center, rgba(30,41,59,0.06) 0%, rgba(30,41,59,0.02) 40%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}

.hero-content {
  flex: 1;
  position: relative;
  z-index: 1;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 100px;
  background: #f1f5f9;
  color: #1e293b;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 20px;
}

.badge-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #1e293b;
  animation: pulse-dot 2s infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.hero-title {
  font-size: 52px;
  font-weight: 800;
  line-height: 1.15;
  letter-spacing: -1.5px;
  margin: 0 0 20px;
}

.gradient-text {
  background: linear-gradient(135deg, #1e293b 0%, #334155 40%, #1e293b 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-desc {
  font-size: 17px;
  line-height: 1.7;
  color: #6b7280;
  margin: 0 0 28px;
  max-width: 520px;
}

.hero-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 28px;
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  padding: 12px 28px;
  border-radius: 10px;
  background: #1e293b;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  text-decoration: none;
  transition: all 0.15s;
  box-shadow: 0 2px 8px rgba(30, 41, 59, 0.15);
}

.btn-primary:hover {
  background: #334155;
  box-shadow: 0 4px 12px rgba(30, 41, 59, 0.2);
}

.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 12px 24px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #374151;
  font-size: 15px;
  font-weight: 500;
  text-decoration: none;
  transition: all 0.2s;
}

.btn-ghost:hover {
  border-color: #94a3b8;
  color: #1e293b;
}

.hero-techs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tech-tag {
  padding: 4px 12px;
  border-radius: 6px;
  background: #f3f4f6;
  color: #6b7280;
  font-size: 12px;
  font-weight: 500;
}

/* 终端预览 */
.hero-terminal {
  flex: 0 0 440px;
  position: relative;
  z-index: 1;
  border-radius: 12px;
  overflow: hidden;
  background: #1e1e2e;
  box-shadow: 0 20px 60px rgba(0,0,0,0.15), 0 0 0 1px rgba(255,255,255,0.05);
}

.terminal-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #181825;
  border-bottom: 1px solid #313244;
}

.terminal-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.terminal-dot.red { background: #f38ba8; }
.terminal-dot.yellow { background: #f9e2af; }
.terminal-dot.green { background: #a6e3a1; }

.terminal-title {
  margin-left: auto;
  font-size: 12px;
  color: #6c7086;
  font-family: monospace;
}

.terminal-body {
  margin: 0;
  padding: 16px;
  font-size: 12.5px;
  line-height: 1.65;
  color: #cdd6f4;
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace;
  overflow-x: auto;
  white-space: pre;
}

.terminal-body code {
  font-family: inherit;
}

/* ===== 特性卡片 ===== */
.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.feature-card {
  padding: 28px 24px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #f3f4f6;
  transition: all 0.25s;
}

.feature-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 32px rgba(0,0,0,0.06);
  border-color: #e5e7eb;
}

.feature-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  color: #374151;
}

.feature-card h3 {
  font-size: 16px;
  font-weight: 700;
  margin: 0 0 8px;
}

.feature-card p {
  font-size: 14px;
  line-height: 1.6;
  color: #6b7280;
  margin: 0;
}

/* ===== 架构图 ===== */
.arch-diagram {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
}

.arch-layer {
  width: 100%;
  padding: 24px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #f3f4f6;
}

.arch-layer.core {
  background: #f8fafc;
  border-color: #e2e8f0;
}

.arch-label {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #9ca3af;
  margin-bottom: 12px;
}

.arch-nodes {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.arch-node {
  padding: 10px 18px;
  border-radius: 8px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  transition: all 0.2s;
}

.arch-node:hover {
  border-color: #1e293b;
  color: #1e293b;
}

.arch-node.cli { border-color: #f9e2af; background: #fefce8; }
.arch-node.http { border-color: #a6e3a1; background: #f0fdf4; }
.arch-node.web { border-color: #89b4fa; background: #eff6ff; }
.arch-node.skill { border-color: #f97316; background: #fff7ed; }
.arch-node.mcp { border-color: #67e8f9; background: #ecfeff; }
.arch-node.tools { border-color: #fbbf24; background: #fffbeb; }
.arch-node.custom { border-color: #f472b6; background: #fdf2f8; }

.arch-arrow {
  font-size: 20px;
  color: #d1d5db;
  padding: 4px 0;
}

/* ===== 渐进式披露 ===== */
.progressive-steps {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  justify-content: center;
}

.step {
  flex: 1;
  max-width: 280px;
  padding: 28px 24px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #f3f4f6;
  transition: all 0.25s;
}

.step:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 32px rgba(0,0,0,0.06);
}

.step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: #1e293b;
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  margin-bottom: 16px;
}

.step-content h3 {
  font-size: 16px;
  font-weight: 700;
  margin: 0 0 8px;
}

.step-content p {
  font-size: 14px;
  line-height: 1.6;
  color: #6b7280;
  margin: 0;
}

.step-content code {
  padding: 2px 6px;
  border-radius: 4px;
  background: #f3f4f6;
  font-size: 13px;
  color: #f97316;
}

.step-arrow {
  font-size: 24px;
  color: #d1d5db;
  padding-top: 60px;
  font-weight: 300;
}

/* ===== 快速开始 ===== */
.qs-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.qs-card {
  padding: 28px 24px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #f3f4f6;
  transition: all 0.25s;
}

.qs-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 32px rgba(0,0,0,0.06);
}

.qs-step {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f1f5f9;
  color: #1e293b;
  font-size: 14px;
  font-weight: 800;
  margin-bottom: 14px;
}

.qs-card h3 {
  font-size: 16px;
  font-weight: 700;
  margin: 0 0 14px;
}

.code-block {
  padding: 14px 16px;
  border-radius: 10px;
  background: #1e1e2e;
}

.code-block code {
  font-size: 13px;
  line-height: 1.7;
  color: #cdd6f4;
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  white-space: pre;
}

/* ===== 页脚 ===== */
.intro-footer {
  text-align: center;
  padding: 40px 24px;
  border-top: 1px solid #f3f4f6;
}

.footer-brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
}

.footer-logo {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  object-fit: cover;
}

.footer-copy {
  font-size: 13px;
  color: #9ca3af;
  margin: 0;
}

/* ===== 响应式 ===== */
@media (max-width: 900px) {
  .hero {
    flex-direction: column;
    padding-top: 40px;
  }
  .hero-terminal {
    flex: none;
    width: 100%;
  }
  .hero-title {
    font-size: 36px;
  }
  .feature-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .progressive-steps {
    flex-direction: column;
    align-items: center;
  }
  .step-arrow {
    transform: rotate(90deg);
    padding: 0;
  }
  .step {
    max-width: 100%;
    width: 100%;
  }
  .qs-cards {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  .feature-grid {
    grid-template-columns: 1fr;
  }
  .hero-title {
    font-size: 30px;
  }
}
</style>
