"""集成测试：openai-python 客户端连接 openfox-server。

本测试需要 openfox-server 在 BASE_URL 上运行。
默认在 CI 之外跳过（除非显式设置 AGENT_SKILLS_TEST_LIVE=1）。

运行方式：
  1. 启动服务：
     openfox-server --host 127.0.0.1 --port 8765 &
  2. 运行测试：
     AGENT_SKILLS_TEST_LIVE=1 AGENT_SKILLS_TEST_URL=http://127.0.0.1:8765/v1 \
       pytest tests/integration/test_openai_client.py -v
"""

from __future__ import annotations

import os

import pytest

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore


# 默认值与覆盖
TEST_URL = os.environ.get("AGENT_SKILLS_TEST_URL", "http://127.0.0.1:8765/v1")
TEST_MODEL = os.environ.get("AGENT_SKILLS_TEST_MODEL", "deepseek-v4-flash")
TEST_API_KEY = os.environ.get("AGENT_SKILLS_TEST_API_KEY", "anything")
LIVE = os.environ.get("AGENT_SKILLS_TEST_LIVE") == "1"


pytestmark = pytest.mark.skipif(
    not LIVE or OpenAI is None,
    reason="需设置 AGENT_SKILLS_TEST_LIVE=1 并安装 openai 包",
)


@pytest.fixture(scope="module")
def client():
    """openai 客户端，连接到运行中的 openfox-server。"""
    return OpenAI(base_url=TEST_URL, api_key=TEST_API_KEY)


def test_models_list(client):
    """GET /v1/models 端点可用。"""
    models = client.models.list()
    assert models.object == "list"
    ids = [m.id for m in models.data]
    assert TEST_MODEL in ids, f"模型 {TEST_MODEL} 不在 {ids}"


def test_chat_non_stream(client):
    """POST /v1/chat/completions 非流式。"""
    resp = client.chat.completions.create(
        model=TEST_MODEL,
        messages=[{"role": "user", "content": "用一句话介绍你自己"}],
    )
    assert resp.object == "chat.completion"
    assert resp.model == TEST_MODEL
    assert len(resp.choices) == 1
    assert resp.choices[0].finish_reason == "stop"
    assert resp.choices[0].message.role == "assistant"
    assert len(resp.choices[0].message.content) > 0
    # usage 字段（可选，但应该存在）
    assert resp.usage.total_tokens > 0


def test_chat_stream(client):
    """POST /v1/chat/completions 流式（SSE）。"""
    stream = client.chat.completions.create(
        model=TEST_MODEL,
        messages=[{"role": "user", "content": "说一句话"}],
        stream=True,
    )
    chunks = list(stream)
    assert len(chunks) >= 2, "流式应至少有 role + content 两个 chunk"
    # 第一个 chunk 应含 role
    assert chunks[0].choices[0].delta.role == "assistant"
    # 收集 content
    content = "".join(
        c.choices[0].delta.content or "" for c in chunks
    )
    assert len(content) > 0
    # 最后一个 chunk 应有 finish_reason=stop
    assert chunks[-1].choices[0].finish_reason == "stop"


def test_multi_turn_with_user_field(client):
    """通过 user 字段实现多轮对话。"""
    session_id = "test-session-multi-turn"

    # 第一轮
    resp1 = client.chat.completions.create(
        model=TEST_MODEL,
        messages=[{"role": "user", "content": "请记住：我的名字叫测试机器人"}],
        user=session_id,
    )
    assert resp1.choices[0].message.content

    # 第二轮（同一 user）
    resp2 = client.chat.completions.create(
        model=TEST_MODEL,
        messages=[{"role": "user", "content": "我叫什么名字？"}],
        user=session_id,
    )
    content2 = resp2.choices[0].message.content
    assert "测试机器人" in content2 or "test" in content2.lower(), (
        f"多轮对话失败，预期记住名字，实际：{content2}"
    )


def test_unknown_model_fallback(client):
    """请求不存在的模型时不应崩溃，应回退到当前模型。"""
    resp = client.chat.completions.create(
        model="non-existent-model-xyz",
        messages=[{"role": "user", "content": "你好"}],
    )
    # 框架保留当前模型，返回 200
    assert resp.choices[0].message.content
    # model 字段应回退到当前激活模型
    assert resp.model == TEST_MODEL or resp.model in [
        m.id for m in client.models.list().data
    ]