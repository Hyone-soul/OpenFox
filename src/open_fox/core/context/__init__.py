# OpenFox Context Management
#
# 上下文管理模块：量化 → 阈值判定 → 压缩 → 兜底
#
# 参考 Hermes 三层防御设计：
#   第一层：预防（从源头控制增长）
#   第二层：压缩（核心机制 — 结构化摘要替换中间轮）
#   第三层：兜底（压缩也救不了时建议开新会话）

from .token_estimator import estimate_tokens, estimate_messages_tokens, estimate_tool_schemas_tokens
from .context_breakdown import ContextBreakdown, ContextCategory, ContextSnapshot
from .context_compressor import ContextCompressor, CompressionResult
