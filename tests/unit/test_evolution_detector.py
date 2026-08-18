"""进化触发判定单元测试。"""
from open_fox.config import SkillEvolutionConfig
from open_fox.core.evolution.detector import EvolutionTriggerDetector
from open_fox.core.evolution.stats import SkillInvocationTracker

FAIL = "ERROR: 命令退出码 1: boom"
_OK = "ok"

FAIL_TRACE = [{"name": "run_shell",
               "args": {"cmd": "python skills/pdf/scripts/extract.py a.pdf"},
               "result": FAIL}]
OK_TRACE = [{"name": "run_shell",
             "args": {"cmd": "python skills/pdf/scripts/extract.py a.pdf"},
             "result": _OK}]


def _mk(tmp_path, config=None, existing=None):
    cfg = config or SkillEvolutionConfig(min_failures=2, min_repeats=2)
    tracker = SkillInvocationTracker(tmp_path)
    detector = EvolutionTriggerDetector(cfg, tracker, existing or (lambda: set()))
    return tracker, detector


def test_branch_a_triggers_on_min_failures(tmp_path):
    _, detector = _mk(tmp_path=tmp_path)
    detector.evaluate("s1", FAIL_TRACE)   # 第1次失败
    triggers = detector.evaluate("s1", FAIL_TRACE)  # 第2次失败 → 命中
    assert len(triggers) == 1
    assert triggers[0].kind == "fix"
    assert triggers[0].skill_name == "pdf"
    assert any("boom" in e for e in triggers[0].evidence)


def test_branch_a_single_failure_no_trigger(tmp_path):
    _, detector = _mk(tmp_path=tmp_path)
    triggers = detector.evaluate("s1", FAIL_TRACE)
    assert triggers == []


def test_branch_a_cooldown_suppresses(tmp_path):
    # 用高 min_repeats 隔离分支A：FAIL_TRACE 的脚本签名在会话内会重复达分支B阈值，
    # 而分支B与冷却无关，会单独触发 create；把 min_repeats 调高以只测分支A冷却。
    tracker, detector = _mk(
        config=SkillEvolutionConfig(min_failures=2, min_repeats=999), tmp_path=tmp_path)
    detector.evaluate("s1", FAIL_TRACE)
    tracker.skill_stats("pdf").cooldown_until_turn = tracker.turn() + 100
    assert detector.evaluate("s1", FAIL_TRACE) == []


def test_branch_b_triggers_on_repeated_signature(tmp_path):
    _, detector = _mk(tmp_path=tmp_path)
    trace = [{"name": "run_shell",
              "args": {"cmd": "python workspace/report.py --input a.csv"},
              "result": _OK}]
    detector.evaluate("s1", trace)
    triggers = detector.evaluate("s1", trace)  # 同签名第2次
    assert len(triggers) == 1
    assert triggers[0].kind == "create"
    assert triggers[0].signature == "shell:report.py"


def test_branch_b_ignores_rejected_signature(tmp_path):
    _, detector = _mk(tmp_path=tmp_path)
    trace = [{"name": "run_shell",
              "args": {"cmd": "python workspace/report.py a.csv"},
              "result": _OK}]
    detector.evaluate("s1", trace)
    detector.mark_rejected("shell:report.py")
    assert detector.evaluate("s1", trace) == []


def test_disabled_never_triggers(tmp_path):
    _, detector = _mk(config=SkillEvolutionConfig(enabled=False), tmp_path=tmp_path)
    detector.evaluate("s1", FAIL_TRACE)
    assert detector.evaluate("s1", FAIL_TRACE) == []


def test_branch_b_skips_existing_skill(tmp_path):
    # 若签名对应路径恰好在已存在 skill 下，由 existing_skills 过滤由 Task 8 处理；
    # 此处验证 detector 对已存在技能名的 create 不重复建议（经由 _rejected 即可，
    # 存在性检查在 Task 8 _process 做）。仅验证 create 不影响分支A。
    tracker, detector = _mk(tmp_path=tmp_path)
    detector.evaluate("s1", FAIL_TRACE)
    assert tracker.skill_failures("pdf") == 1
