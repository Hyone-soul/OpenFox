"""自定义异常测试。"""
import pytest

from open_fox.core.exceptions import (
    AgentLoopError,
    InvalidAssistantMessage,
    ModelAPIError,
    PathGuardViolation,
    ScriptTimeout,
    StreamInterrupted,
    ToolExecutionError,
)


def test_model_api_error_carries_status():
    err = ModelAPIError(429, "rate limited")
    assert err.status_code == 429
    assert "rate limited" in str(err)


def test_path_guard_violation_is_agent_loop_error():
    err = PathGuardViolation("../etc/passwd")
    assert isinstance(err, AgentLoopError)
    assert "../etc/passwd" in str(err)


def test_exception_hierarchy():
    """所有自定义异常继承 AgentLoopError。"""
    for cls in (ModelAPIError, StreamInterrupted, InvalidAssistantMessage,
                PathGuardViolation, ScriptTimeout, ToolExecutionError):
        assert issubclass(cls, AgentLoopError)
        assert issubclass(cls, Exception)


def test_script_timeout_carries_duration():
    err = ScriptTimeout("sleep 999", 30.0)
    assert err.command == "sleep 999"
    assert err.timeout == 30.0