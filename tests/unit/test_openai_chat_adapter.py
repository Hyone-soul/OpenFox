"""OpenAI Chat Completions 适配器测试（mock HTTP）。"""
import json

import httpx
import pytest

from open_fox.config import ModelConfig
from open_fox.core.adapters.base import AssistantMessage, ChatChunk, ToolCall
from open_fox.core.adapters.openai_chat import OpenAIChatAdapter


@pytest.fixture
def adapter():
    return OpenAIChatAdapter(models=[
        ModelConfig(name="gpt-4o", base_url="https://api.example.com/v1",
                    api_key_env="X", api_key="sk-test", model="gpt-4o"),
    ])


def test_list_models(adapter):
    assert adapter.list_models() == ["gpt-4o"]


def test_set_active(adapter):
    adapter.set_active("gpt-4o")
    assert adapter.active == "gpt-4o"


@pytest.mark.asyncio
async def test_chat_non_stream(respx_mock, adapter):
    respx_mock.post("https://api.example.com/v1/chat/completions").respond(
        json={
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "hello",
                    "tool_calls": None,
                },
                "finish_reason": "stop",
            }]
        }
    )
    msg = await adapter.chat([{"role": "user", "content": "hi"}])
    assert isinstance(msg, AssistantMessage)
    assert msg.content == "hello"
    assert msg.tool_calls == []


@pytest.mark.asyncio
async def test_chat_with_tool_call(respx_mock, adapter):
    respx_mock.post("https://api.example.com/v1/chat/completions").respond(
        json={
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps({"path": "x.txt"}),
                        },
                    }],
                },
                "finish_reason": "tool_calls",
            }]
        }
    )
    msg = await adapter.chat(
        [{"role": "user", "content": "read x.txt"}],
        tools=[{"type": "function", "function": {"name": "read_file"}}],
    )
    assert len(msg.tool_calls) == 1
    assert msg.tool_calls[0].name == "read_file"
    assert msg.tool_calls[0].args == {"path": "x.txt"}


def test_parse_stream_chunk_tool_call_arguments_fragments(adapter):
    """流式 tool_call 的 arguments 是跨 chunk 的不完整 JSON 片段，必须原样返回供累积。"""
    # chunk1：第一个 chunk，带 id + name + arguments 开头
    c1 = adapter._parse_stream_chunk({
        "choices": [{"delta": {"tool_calls": [{
            "id": "call_1", "type": "function",
            "function": {"name": "read_file", "arguments": '{"pat'},
        }]}, "finish_reason": None}]
    })
    # chunk2：只追加 arguments 片段，无 id/name
    c2 = adapter._parse_stream_chunk({
        "choices": [{"delta": {"tool_calls": [{
            "id": None, "type": "function",
            "function": {"name": None, "arguments": 'h": "x.txt"}'},
        }]}, "finish_reason": None}]
    })

    assert isinstance(c1, ChatChunk)
    assert c1.tool_call_delta is not None
    assert c1.tool_call_delta.id == "call_1"
    assert c1.tool_call_delta.name == "read_file"
    # 关键：arguments 片段原样保留，不在这里被 json.loads 吃掉
    assert c1.tool_call_args_delta == '{"pat'
    assert c2.tool_call_args_delta == 'h": "x.txt"}'

    # 完整拼回后能正确解析
    import json as _json
    full = _json.loads(c1.tool_call_args_delta + c2.tool_call_args_delta)
    assert full == {"path": "x.txt"}


@pytest.mark.asyncio
async def test_chat_retry_on_429(respx_mock, adapter):
    route = respx_mock.post("https://api.example.com/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(429, json={"error": "rate limit"}),
            httpx.Response(200, json={"choices": [{
                "message": {"role": "assistant", "content": "ok", "tool_calls": None},
                "finish_reason": "stop",
            }]}),
        ]
    )
    msg = await adapter.chat([{"role": "user", "content": "hi"}])
    assert msg.content == "ok"
    assert route.call_count == 2


@pytest.mark.asyncio
async def test_chat_passes_temperature(respx_mock, adapter):
    respx_mock.post("https://api.example.com/v1/chat/completions").respond(
        json={"choices": [{
            "message": {"role": "assistant", "content": "ok", "tool_calls": None},
            "finish_reason": "stop",
        }]}
    )
    await adapter.chat([{"role": "user", "content": "hi"}], temperature=0.7)
    body = json.loads(respx_mock.calls.last.request.content)
    assert body["temperature"] == 0.7


@pytest.mark.asyncio
async def test_chat_omits_temperature_when_none(respx_mock, adapter):
    respx_mock.post("https://api.example.com/v1/chat/completions").respond(
        json={"choices": [{
            "message": {"role": "assistant", "content": "ok", "tool_calls": None},
            "finish_reason": "stop",
        }]}
    )
    await adapter.chat([{"role": "user", "content": "hi"}])
    body = json.loads(respx_mock.calls.last.request.content)
    assert "temperature" not in body
