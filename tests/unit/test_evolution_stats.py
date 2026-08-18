"""Skill 调用轨迹统计单元测试。"""
import asyncio

from open_fox.core.evolution.stats import (
    SkillInvocationTracker,
    _coarse_signature,
    _extract_skill_refs,
)

FAIL = "ERROR: 命令退出码 1: boom"


def test_extract_skill_refs():
    assert _extract_skill_refs(
        {"name": "run_shell", "args": {"cmd": "python skills/pdf/scripts/extract.py a.pdf"}}
    ) == ["shell:pdf"]
    assert _extract_skill_refs(
        {"name": "read_file", "args": {"path": "skills/pdf/SKILL.md"}}
    ) == ["read:pdf"]
    assert _extract_skill_refs({"name": "run_shell", "args": {"cmd": "ls"}}) == []


def test_coarse_signature():
    a = _coarse_signature({"name": "run_shell", "args": {"cmd": "python workspace/report.py --input a.csv"}})
    b = _coarse_signature({"name": "run_shell", "args": {"cmd": "python workspace/report.py --input b.csv"}})
    assert a == b  # 不同输入 → 相同签名（流程复用）
    assert a == "shell:report.py"


def test_record_trace_counts(tmp_path):
    t = SkillInvocationTracker(tmp_path)
    t.record_trace("s1", [
        {"name": "run_shell", "args": {"cmd": "python skills/pdf/scripts/extract.py a.pdf"}, "result": "ok"},
        {"name": "run_shell", "args": {"cmd": "python skills/pdf/scripts/extract.py b.pdf"}, "result": FAIL},
    ])
    assert t.skill_invocations("pdf") == 2
    assert t.skill_failures("pdf") == 1
    # 分支B 粗化签名按脚本 basename 计（Ruling-2：面向任意工具调用，非仅 skills/ 路径）
    assert t.signature_count("s1", "shell:extract.py") == 2


def test_save_load_roundtrip(tmp_path):
    t = SkillInvocationTracker(tmp_path)
    t.record_trace("s1", [
        {"name": "run_shell", "args": {"cmd": "python skills/pdf/scripts/extract.py a.pdf"}, "result": FAIL},
        {"name": "run_shell", "args": {"cmd": "python skills/pdf/scripts/extract.py a.pdf"}, "result": FAIL},
    ])
    asyncio.run(t.save())
    t2 = SkillInvocationTracker(tmp_path)
    asyncio.run(t2.load())
    assert t2.skill_failures("pdf") == 2
    assert t2.skill_invocations("pdf") == 2


def test_session_lru_eviction(tmp_path):
    t = SkillInvocationTracker(tmp_path)
    for i in range(25):
        t.record_trace(f"s{i}", [
            {"name": "run_shell", "args": {"cmd": "python skills/pdf/scripts/extract.py a.pdf"}, "result": "ok"},
        ])
    # 只保留最近 20 个会话的签名计数，最早 5 个被淘汰
    assert t.signature_count("s0", "shell:extract.py") == 0
    assert t.signature_count("s24", "shell:extract.py") == 1


def test_turn_counter(tmp_path):
    t = SkillInvocationTracker(tmp_path)
    assert t.turn() == 0
    t.register_turn()
    t.register_turn()
    assert t.turn() == 2


def test_load_rebuilds_lru(tmp_path):
    """重启恢复的会话桶应参与 LRU 淘汰，避免死会话无界增长。"""
    t = SkillInvocationTracker(tmp_path)
    t.record_trace("s1", [{"name": "run_shell", "args": {"cmd": "python skills/pdf/scripts/extract.py a.pdf"}, "result": "ok"}])
    asyncio.run(t.save())
    t2 = SkillInvocationTracker(tmp_path)
    asyncio.run(t2.load())
    # 灌入 25 个新会话，超出 _MAX_SESSIONS=20 → s1（最早恢复）应被淘汰
    for i in range(25):
        t2.record_trace(f"n{i}", [{"name": "run_shell", "args": {"cmd": "python skills/pdf/scripts/extract.py a.pdf"}, "result": "ok"}])
    assert t2.signature_count("s1", "shell:extract.py") == 0
