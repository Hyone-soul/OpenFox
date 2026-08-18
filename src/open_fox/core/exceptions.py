"""自定义异常体系。

所有框架内抛出的业务异常都应继承 AgentLoopError，
便于在 AgentLoop 顶层统一捕获与日志记录。
"""

from __future__ import annotations


class AgentLoopError(Exception):
    """所有 Agent 框架异常的基类。"""


class ModelAPIError(AgentLoopError):
    """模型 API 返回非 2xx 或解析失败。"""

    def __init__(self, status_code: int, detail: str):
        super().__init__(f"Model API error {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class StreamInterrupted(AgentLoopError):
    """流式响应被截断。"""


class InvalidAssistantMessage(AgentLoopError):
    """模型返回的 assistant 消息缺少必要字段。"""


class PathGuardViolation(AgentLoopError):
    """路径校验失败，疑似路径穿越或越界。"""

    def __init__(self, path: str):
        super().__init__(f"路径校验失败：{path}")
        self.path = path


class ScriptTimeout(AgentLoopError):
    """脚本执行超时。"""

    def __init__(self, command: str, timeout: float):
        super().__init__(f"脚本执行超时（>{timeout}s）：{command}")
        self.command = command
        self.timeout = timeout


class ToolExecutionError(AgentLoopError):
    """内置工具执行失败。"""


class ScriptNotFound(AgentLoopError):
    """Skill 声明的脚本文件不存在。"""


class DangerousCommand(AgentLoopError):
    """命令命中黑名单。"""

    def __init__(self, command: str):
        super().__init__(f"危险命令被拦截：{command}")
        self.command = command