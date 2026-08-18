# tests/unit/test_memory_extractor.py
import asyncio

import pytest

from open_fox.core.memory.extractor import MemoryExtractionTask
from open_fox.core.memory.manager import MemoryManager


@pytest.mark.asyncio
async def test_should_extract_respects_throttle(tmp_path):
    m = MemoryManager(tmp_path=tmp_path)
    await m.load()
    task = MemoryExtractionTask(m, adapter=None, min_interval_turns=5)
    # 距上次 <5 轮 → 不抽
    assert not task._should_extract(tool_used=True, msg_count=6)
    # 模拟 5 轮过去
    for _ in range(5):
        m.register_turn()
    assert task._should_extract(tool_used=True, msg_count=6)
    # 但纯聊天（未用工具）→ 不抽
    m2 = MemoryManager(tmp_path=tmp_path)
    await m2.load()
    task2 = MemoryExtractionTask(m2, adapter=None, min_interval_turns=5)
    for _ in range(5):
        m2.register_turn()
    assert not task2._should_extract(tool_used=False, msg_count=6)


@pytest.mark.asyncio
async def test_notify_and_extract_calls_manager(tmp_path):
    m = MemoryManager(tmp_path=tmp_path)
    await m.load()
    calls = []
    task = MemoryExtractionTask(m, adapter=None, min_interval_turns=5)
    async def fake_extract(messages):
        calls.append(messages[-1].get("content"))
    task._extract_once = fake_extract
    for _ in range(5):
        m.register_turn()
    await task.start()
    try:
        # _should_extract 要求 msg_count>=6，构造 6 条会话消息，末条为待验证内容
        messages = [
            {"role": "user", "content": "msg0"},
            {"role": "assistant", "content": "msg1"},
            {"role": "user", "content": "msg2"},
            {"role": "assistant", "content": "msg3"},
            {"role": "user", "content": "msg4"},
            {"role": "assistant", "content": "hi"},
        ]
        await task.notify(messages=messages, tool_used=True)
        # 给后台 _loop 一点时间消费队列
        for _ in range(50):
            if calls:
                break
            await asyncio.sleep(0.01)
        assert calls == ["hi"]
    finally:
        await task.stop()
