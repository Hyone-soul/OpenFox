# LLM Provider Token 字段参考

> 框架通过 `UsageInfo` 统一暴露 token 统计。本文档说明不同 LLM provider 的 `usage` 字段差异。

## 标准字段（所有 provider 通用）

| 字段 | 含义 |
|---|---|
| `prompt_tokens` | 输入 token 数（不含缓存命中） |
| `completion_tokens` | 输出 token 数 |
| `total_tokens` | 总消耗 = prompt + completion |

## 缓存相关字段

| Provider | 字段 | 含义 |
|---|---|---|
| **OpenAI** | `prompt_tokens_details.cached_tokens` | 缓存命中（cache_read_input_tokens） |
| **Anthropic** | `cache_creation_input_tokens` | 新创建的缓存 token |
| **Anthropic** | `cache_read_input_tokens` | 缓存读取 token（命中） |
| **Anthropic** | `UsageInfo.cache_hit_tokens` ← | 我们映射后的统一字段 |
| **Anthropic** | `UsageInfo.cache_miss_tokens` ← | 未命中（首次写入） |
| **Gemini** | `cached_content_token_count` | 缓存命中 |
| **DeepSeek** | `prompt_cache_hit_tokens` | 缓存命中（与 OpenAI 类似） |
| **Ollama** | 不支持 | — |

## 推理 token 字段（思考模型）

| Provider | 字段 | 模型 |
|---|---|---|
| **OpenAI o1/o3** | `completion_tokens_details.reasoning_tokens` | 思考消耗 |
| **DeepSeek-R1** | `completion_tokens_details.reasoning_tokens`（新版本） | 思考消耗 |
| **Anthropic** | 无单独字段（计入 `output_tokens`） | — |
| **Gemini 2.5 Thinking** | `thoughts_token_count` | 思考消耗 |

## 当前框架 `UsageInfo` 字段

```python
@dataclass
class UsageInfo:
    prompt_tokens: int = 0          # 输入
    completion_tokens: int = 0       # 输出
    total_tokens: int = 0            # 总消耗
    cache_hit_tokens: int = 0        # 缓存命中
    cache_miss_tokens: int = 0       # 缓存未命中
    reasoning_tokens: int = 0       # 推理 token（思考模型）
```

## 已知兼容性

| Provider | prompt/completion/total | cache hit | reasoning | 测试覆盖 |
|---|---|---|---|---|
| OpenAI 官方 | ✅ | ✅ `cached_tokens` | ✅ `reasoning_tokens` | ✅ |
| DeepSeek | ✅ | ✅ `cached_tokens`（与 OpenAI 同） | ✅ `reasoning_tokens` | ✅ 实测 |
| Anthropic | ⚠️ 字段名不同 | ⚠️ 需 AnthropicAdapter | ⚠️ 计入 output | ❌ 待实现 |
| Gemini | ⚠️ 字段名不同 | ⚠️ 需 GeminiAdapter | ⚠️ `thoughts_token_count` | ❌ 待实现 |

## 示例：DeepSeek 实际响应

```json
{
  "prompt_tokens": 1028,
  "completion_tokens": 53,
  "total_tokens": 1081,
  "prompt_tokens_details": {
    "cached_tokens": 896
  },
  "completion_tokens_details": {
    "reasoning_tokens": 21
  }
}
```

→ 框架解析后 `UsageInfo`:
- `prompt_tokens = 1028`
- `completion_tokens = 53`
- `total_tokens = 1081`
- `cache_hit_tokens = 896`
- `cache_miss_tokens = 1028 - 896 = 132`
- `reasoning_tokens = 21`

## 客户端使用

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="anything")

resp = client.chat.completions.create(
    model="deepseek-reasoner",  # 推理模型
    messages=[{"role": "user", "content": "解释量子纠缠"}],
)

usage = resp.usage
print(f"输入: {usage.prompt_tokens}")
print(f"输出: {usage.completion_tokens}")
print(f"推理: {usage.completion_tokens_details.reasoning_tokens}")
print(f"缓存命中: {usage.prompt_tokens_details.cached_tokens}")
```

## 注意事项

1. **流式响应**：当前 `_stream_chat` 不返回 usage（设计取舍）。如需精确 token，请在响应结束后用非流式接口估算，或在外层 wrapper 中累计
2. **Mock 测试**：`AssistantMessage.usage` 默认值是 `UsageInfo()`（全 0）。E2E 测试用 `FakeAdapter` 不返回真实 usage
3. **Provider 兼容性**：当前仅 OpenAI Chat Completions 适配器读取 usage。Anthropic/Gemini 需要单独适配器
4. **缓存计费**：不同 provider 对缓存 hit/miss 的计费不同（如 Anthropic cache_write 比 cache_read 贵 5x）

## 未来工作

- [ ] 实现 `AnthropicAdapter`（不同 base_url + headers + cache 字段映射）
- [ ] 实现 `GeminiAdapter`（同样需要字段映射）
- [ ] 流式响应累积 usage（外层 wrapper）
- [ ] Session 持久化 usage（历史 token 报表）
- [ ] AgentLoop 多步累积（read_file + 总结 等场景的完整 token 追踪）