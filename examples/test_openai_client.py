"""手动测试 openai-python 客户端连接 openfox-server。

此脚本需要 openfox-server 在运行中。

使用方法：
  1. 启动服务（另开终端）：
     openfox-server --host 127.0.0.1 --port 8000 &

  2. 运行此脚本：
     python examples/test_openai_client.py

可通过环境变量定制：
  AGENT_SKILLS_URL  默认 http://localhost:8000/v1
  AGENT_SKILLS_MODEL 默认 deepseek-v4-flash
"""

from __future__ import annotations

import os
import sys

try:
    from openai import OpenAI
except ImportError:
    print("✗ 请先安装 openai：pip install openai", file=sys.stderr)
    sys.exit(1)


BASE_URL = os.environ.get("AGENT_SKILLS_URL", "http://localhost:8000/v1")
MODEL = os.environ.get("AGENT_SKILLS_MODEL", "deepseek-v4-flash")
API_KEY = "anything"  # 框架不校验


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def test_models(client: OpenAI) -> None:
    section("1. 列出可用模型（GET /v1/models）")
    try:
        models = client.models.list()
        print(f"  object: {models.object}")
        for m in models.data:
            print(f"  - {m.id}")
    except Exception as e:
        print(f"  ✗ 错误：{e}")


def test_non_stream(client: OpenAI) -> None:
    section("2. 非流式对话（POST /v1/chat/completions）")
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "用一句话介绍你自己"}],
        )
        print(f"  reply: {resp.choices[0].message.content}")
        print(f"  usage: {resp.usage.total_tokens} tokens")
    except Exception as e:
        print(f"  ✗ 错误：{e}")


def test_stream(client: OpenAI) -> None:
    section("3. 流式对话（stream=true）")
    try:
        stream = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "讲一个简短的笑话"}],
            stream=True,
        )
        print("  reply: ", end="", flush=True)
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                print(delta.content, end="", flush=True)
        print()
    except Exception as e:
        print(f"  ✗ 错误：{e}")


def test_multi_turn(client: OpenAI) -> None:
    section("4. 多轮对话（user 字段做 session_id）")
    session_id = "demo-session-001"
    try:
        # 第一轮
        resp1 = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "请记住：我的名字叫小红"}],
            user=session_id,
        )
        print(f"  第 1 轮: {resp1.choices[0].message.content[:60]}...")

        # 第二轮
        resp2 = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "我叫什么名字？"}],
            user=session_id,
        )
        print(f"  第 2 轮: {resp2.choices[0].message.content}")
    except Exception as e:
        print(f"  ✗ 错误：{e}")


def test_tools(client: OpenAI) -> None:
    section("5. 工具调用（function calling）")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读取白名单目录下的文本文件",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"}
                    },
                    "required": ["path"],
                },
            },
        }
    ]
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "user", "content": "读取 workspace 下的 README.md 看看"}
            ],
            tools=tools,
        )
        # 框架的 /v1/chat/completions 端点不返回 tool_calls（已在内部处理）
        # 返回的是 AgentLoop 处理完工具后的最终自然语言回复
        print(f"  reply: {resp.choices[0].message.content}")
    except Exception as e:
        print(f"  ✗ 错误：{e}")


def main() -> None:
    print(f"\n正在连接 {BASE_URL}（model={MODEL}）...")

    client = OpenAI(base_url=BASE_URL, api_key=API_KEY, timeout=60)

    # 健康检查
    try:
        client.models.list()
        print("✓ 服务可达")
    except Exception as e:
        print(f"\n✗ 无法连接 {BASE_URL}")
        print(f"  请先启动：openfox-server --host 127.0.0.1 --port 8000")
        print(f"  错误详情：{e}")
        sys.exit(1)

    test_models(client)
    test_non_stream(client)
    test_stream(client)
    test_multi_turn(client)
    test_tools(client)

    print(f"\n{'=' * 60}")
    print("  全部测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()