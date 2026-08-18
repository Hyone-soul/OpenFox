"""Skill 进化后台任务单元测试。"""
import asyncio

import pytest

from open_fox.config import SkillEvolutionConfig
from open_fox.core.adapters.base import AssistantMessage
from open_fox.core.evolution.detector import EvolutionTriggerDetector
from open_fox.core.evolution.generator import EvolutionTask
from open_fox.core.evolution.manager import SkillEvolutionManager
from open_fox.core.evolution.pending import PendingQueue
from open_fox.core.evolution.stats import SkillInvocationTracker

FAIL = "ERROR: 命令退出码 1: boom"
FAIL_TRACE = [{"name": "run_shell",
               "args": {"cmd": "python skills/pdf/scripts/extract.py a.pdf"},
               "result": FAIL}]


class FakeChat:
    def __init__(self, reply_text):
        self._reply = reply_text
        self.calls = 0

    async def chat(self, messages, tools=None, stream=False, temperature=None):
        self.calls += 1
        return AssistantMessage(content=self._reply)


def _build(tmp_path, reply_text, existing=None, min_failures=2):
    cfg = SkillEvolutionConfig(min_failures=min_failures, min_repeats=2)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    data_dir = tmp_path / "data"
    manager = SkillEvolutionManager(skills_dir, data_dir)
    tracker = SkillInvocationTracker(data_dir)
    detector = EvolutionTriggerDetector(cfg, tracker, existing or (lambda: set()))
    queue = PendingQueue(data_dir / "pending.json")
    fake = FakeChat(reply_text)
    task = EvolutionTask(
        cfg, manager, tracker, detector, queue, fake,
        existing_skills=existing or (lambda: set()),
        get_skill_md=lambda n: "---\nname: pdf\ndescription: old\n---\nold正文",
    )
    return task, tracker, queue, fake


@pytest.mark.asyncio
async def test_generate_parses_valid_json(tmp_path):
    task, _, _, _ = _build(
        tmp_path,
        '{"action":"fix","skill_name":"pdf","reason":"测试","content":"---\\nname: pdf\\ndescription: new\\n---\\nnew"}',
    )
    from open_fox.core.evolution.detector import EvolutionTrigger
    result = await task._generate(
        EvolutionTrigger(kind="fix", skill_name="pdf", evidence=["boom"], signature=""),
        [{"role": "user", "content": "hi"}],
    )
    assert result is not None
    assert result["action"] == "fix"
    assert "new" in result["content"]


@pytest.mark.asyncio
async def test_generate_skip_returns_none(tmp_path):
    task, _, _, _ = _build(tmp_path, '{"action":"skip"}')
    from open_fox.core.evolution.detector import EvolutionTrigger
    result = await task._generate(
        EvolutionTrigger(kind="fix", skill_name="pdf", evidence=[], signature=""),
        [{"role": "user", "content": "hi"}],
    )
    assert result is None


@pytest.mark.asyncio
async def test_generate_invalid_json_returns_none(tmp_path):
    task, _, _, _ = _build(tmp_path, "这不是 JSON")
    from open_fox.core.evolution.detector import EvolutionTrigger
    result = await task._generate(
        EvolutionTrigger(kind="fix", skill_name="pdf", evidence=[], signature=""),
        [{"role": "user", "content": "hi"}],
    )
    assert result is None


@pytest.mark.asyncio
async def test_notify_enqueues_pending_after_min_failures(tmp_path):
    reply = ('{"action":"fix","skill_name":"pdf","reason":"test",'
             '"content":"---\\nname: pdf\\ndescription: fixed\\n---\\nfixed"}')
    task, _tracker, queue, _ = _build(tmp_path, reply)
    await task.start()
    try:
        msgs = [{"role": "user", "content": f"m{i}"} for i in range(6)]
        # 前 5 轮无工具 → 只累计轮次不触发
        for _ in range(5):
            await task.notify("s1", msgs, [])
        # 第 6 轮：1 次失败；第 7 轮：2 次失败 → 命中分支A
        await task.notify("s1", msgs, FAIL_TRACE)
        await task.notify("s1", msgs, FAIL_TRACE)
        for _ in range(50):
            if queue.list("pending"):
                break
            await asyncio.sleep(0.01)
        pending = queue.list("pending")
        assert len(pending) == 1
        assert pending[0].skill_name == "pdf"
        assert pending[0].action == "fix"
        assert "fixed" in pending[0].content
    finally:
        await task.stop()


@pytest.mark.asyncio
async def test_create_candidate_with_existing_name_skipped(tmp_path):
    reply = ('{"action":"create","skill_name":"pdf","reason":"r",'
             '"content":"---\\nname: pdf\\ndescription: d\\n---\\nbody"}')
    existing = lambda: {"pdf"}  # pdf 已存在 → 新建应跳过（existing 必须是 callable）
    task, _tracker, queue, _ = _build(tmp_path, reply, existing=existing)
    # 用重复签名触发分支B
    trace = [{"name": "run_shell",
              "args": {"cmd": "python workspace/report.py a.csv"},
              "result": "ok"}]
    await task.start()
    try:
        msgs = [{"role": "user", "content": f"m{i}"} for i in range(6)]
        for _ in range(5):
            await task.notify("s1", msgs, [])
        await task.notify("s1", msgs, trace)
        await task.notify("s1", msgs, trace)
        for _ in range(50):
            if queue.list("pending"):
                break
            await asyncio.sleep(0.01)
        assert queue.list("pending") == []  # 已存在 → 不入队
    finally:
        await task.stop()


@pytest.mark.asyncio
async def test_skip_trigger_resets_throttle(tmp_path):
    """LLM 判 skip 也应重置节流闸门，避免每 5 轮重复调 LLM。"""
    task, _tracker, queue, fake = _build(tmp_path, '{"action":"skip"}')
    await task.start()
    try:
        msgs = [{"role": "user", "content": f"m{i}"} for i in range(6)]
        for _ in range(5):
            await task.notify("s1", msgs, [])
        await task.notify("s1", msgs, FAIL_TRACE)  # 第1次失败，无触发
        await task.notify("s1", msgs, FAIL_TRACE)  # 触发 fix → LLM skip → 不入队但应重置节流
        for _ in range(50):
            if fake.calls >= 1:
                break
            await asyncio.sleep(0.01)
        assert queue.list("pending") == []
        assert fake.calls == 1  # 触发过一次 LLM 调用
        # 立即再触发：距上次触发仅 1 轮 <5 → 节流生效，不再调 LLM
        await task.notify("s1", msgs, FAIL_TRACE)
        await asyncio.sleep(0.05)
        assert fake.calls == 1  # 未新增调用
    finally:
        await task.stop()


@pytest.mark.asyncio
async def test_max_pending_full_keeps_throttle(tmp_path):
    """队列满（_MAX_PENDING=5）后再次触发应被放弃且不入队。"""
    from open_fox.core.evolution.generator import _MAX_PENDING
    task, _tracker, queue, fake = _build(tmp_path, reply_text='{"action":"skip"}')
    # 直接灌满 5 个 pending 候选，绕过 LLM（节流语义独立于 LLM 输出）
    for i in range(_MAX_PENDING):
        await queue.enqueue(
            action="fix", skill_name=f"pdf{i}", reason="seed", content="x",
        )
    assert len(queue.list("pending")) == _MAX_PENDING
    await task.start()
    try:
        msgs = [{"role": "user", "content": f"m{i}"} for i in range(6)]
        for _ in range(5):
            await task.notify("s1", msgs, [])
        # 第 6 轮起触发分支A（连续 2 次失败）：队列已满 → 应被放弃，不入队、不再调 LLM
        await task.notify("s1", msgs, FAIL_TRACE)
        await task.notify("s1", msgs, FAIL_TRACE)
        for _ in range(50):
            if fake.calls >= 1:
                break
            await asyncio.sleep(0.01)
        assert len(queue.list("pending")) == _MAX_PENDING  # 没有新增
        assert fake.calls == 0  # 队列已满时直接 return，不会再调 LLM
    finally:
        await task.stop()


class _BoomChat:
    """模拟 LLM 调用抛异常的 fake。"""

    async def chat(self, messages, tools=None, stream=False, temperature=None):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_llm_exception_returns_none(tmp_path):
    """LLM 抛异常时 _generate 应捕获并返回 None，不炸后台循环。"""
    cfg = SkillEvolutionConfig(min_failures=2, min_repeats=2)
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    data_dir = tmp_path / "data"
    manager = SkillEvolutionManager(skills_dir, data_dir)
    tracker = SkillInvocationTracker(data_dir)
    detector = EvolutionTriggerDetector(cfg, tracker, lambda: set())
    queue = PendingQueue(data_dir / "pending.json")
    task = EvolutionTask(
        cfg, manager, tracker, detector, queue, _BoomChat(),
        existing_skills=lambda: set(),
        get_skill_md=lambda n: "x",
    )
    from open_fox.core.evolution.detector import EvolutionTrigger
    result = await task._generate(
        EvolutionTrigger(kind="fix", skill_name="pdf", evidence=["boom"], signature=""),
        [{"role": "user", "content": "hi"}],
    )
    assert result is None
