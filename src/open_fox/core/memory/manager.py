# src/open_fox/core/memory/manager.py
from __future__ import annotations

import asyncio
import contextvars
import logging
import os
from datetime import date
from pathlib import Path

from open_fox.core.memory.exceptions import MemoryPermissionError
from open_fox.core.memory.models import Entry, ImplicitSection, MemoryDocument
from open_fox.core.memory.parser import parse_memory_document
from open_fox.core.memory.renderer import render_memory_document
from open_fox.core.memory.template import (
    SUBSECTIONS,
    TEMPLATE_MD,
)

logger = logging.getLogger(__name__)

# 当前请求的用户名上下文变量，用于 Memory 工具按用户解析 MemoryManager
_current_user: contextvars.ContextVar[str] = contextvars.ContextVar(
    "OPENFOX_CURRENT_USER", default="Ciel"
)


def set_current_user(username: str) -> contextvars.Token:
    """设置当前请求用户名，返回 Token 供 reset 用。"""
    return _current_user.set(username)


def get_current_user() -> str:
    """获取当前请求用户名（默认 Ciel）。"""
    return _current_user.get()

_FILENAME = "OPENFOX.md"
_ARCHIVE_PREFIX = "废弃时间"
_MAX_CONTENT_LEN = 500
_INJECT_CHAR_LIMIT = 2000

# spec 八：注入超预算时按 confidence desc、updated desc 取前 N 条
_CONF_RANK = {"高": 2, "中": 1, "低": 0}
_UPDATED_PREFIX = "更新时间："


def _conf_rank(confidence: str) -> int:
    """置信度转排序权重：高=2/中=1/低=0（缺失按低处理）。"""
    return _CONF_RANK.get(confidence, 0)


def _updated_key(meta: str) -> str:
    """从 meta 提取 `更新时间：YYYY-MM-DD`，返回 ISO 日期用于新近排序。

    解析失败返回空串（字典序最小，排序时自然排最后）。
    """
    idx = meta.find(_UPDATED_PREFIX)
    if idx == -1:
        return ""
    return meta[idx + len(_UPDATED_PREFIX):][:10]


class MemoryManager:
    def __init__(
        self,
        memory_path: Path | None = None,
        *,
        tmp_path: Path | None = None,
    ):
        """创建记忆管理器。

        ``tmp_path`` 保留旧测试和 CLI 集成使用的目录式初始化方式；生产代码
        使用明确的 ``memory_path`` 文件路径。
        """
        path = memory_path or tmp_path
        if path is None:
            raise TypeError("memory_path 或 tmp_path 至少需要提供一个")
        path = Path(path)
        if path.suffix.lower() != ".md":
            path = path / _FILENAME
        self.memory_path: Path = path
        self._doc = MemoryDocument()
        self._lock = asyncio.Lock()
        self._last_extract_turn = 0  # 节流记录：上次抽取时的轮次计数
        self._turn_count = 0         # 每轮 +1（AgentLoop 通知）

    @property
    def document(self) -> MemoryDocument:
        # 供外部只读展示；同步读 _doc，单线程安全（见 memory_text 说明）
        return self._doc

    @staticmethod
    def _today() -> str:
        """写入/归档时取当天日期，避免模块级常量跨零点失效。"""
        return str(date.today())  # noqa: DTZ011

    def _archive(self, entry: Entry) -> None:
        """追加到归档区；同内容已存在则跳过（去重，避免历史记录累积重复）。"""
        if any(e.content == entry.content for e in self._doc.archive):
            return
        self._doc.archive.append(entry)

    def register_turn(self) -> None:
        """AgentLoop.run() 每执行一轮调用一次（节流用）。"""
        self._turn_count += 1

    @property
    def turns_since_extract(self) -> int:
        return self._turn_count - self._last_extract_turn

    async def load(self) -> None:
        async with self._lock:
            if not self.memory_path.exists():
                self.memory_path.parent.mkdir(parents=True, exist_ok=True)
                self.memory_path.write_text(TEMPLATE_MD, encoding="utf-8")
            try:
                md = self.memory_path.read_text(encoding="utf-8")
                self._doc = parse_memory_document(md)
            except Exception as e:  # noqa: BLE001
                logger.warning("OPENFOX.md 解析失败，用空文档继续：%s", e)
                self._doc = MemoryDocument()

    async def _save(self) -> None:
        text = render_memory_document(self._doc)
        tmp = self.memory_path.with_suffix(".md.tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self.memory_path)

    async def add(self, memory_type: str, section: str, content: str, confidence: str = "低") -> str:
        async with self._lock:
            return await self._add_unlocked(memory_type, section, content, confidence)

    async def _add_unlocked(self, memory_type: str, section: str, content: str, confidence: str = "低") -> str:
        """不持锁的新增逻辑。

        add() 持锁调用；update() 退化新增时也在持锁状态直接调用本方法，
        避免 asyncio.Lock 不可重入导致的二次加锁死锁。
        """
        content = content.strip()
        if not content:
            return "内容为空，跳过"
        if memory_type == "explicit":
            # explicit 强制入库，不受 500 字上限约束
            for e in self._doc.explicit:
                if e.content == content:
                    return "已存在，跳过"
            self._doc.explicit.append(Entry(content=content, meta="来源：会话描述｜优先级：最高"))
            await self._save()
            return "已写入用户显式记忆"
        # implicit：仅隐式记忆受 500 字上限约束
        if len(content) > _MAX_CONTENT_LEN:
            return f"内容超过 {_MAX_CONTENT_LEN} 字，已拒绝"
        if section not in SUBSECTIONS:
            section = SUBSECTIONS[0]  # 兜底路由
        for s in self._doc.implicit:
            if s.name == section:
                for e in s.entries:
                    if e.content == content:
                        return "已存在，跳过"
                s.entries.append(Entry(content=content, meta=f"置信度：{confidence}｜更新时间：{self._today()}", confidence=confidence))
                await self._save()
                return f"已写入隐式记忆（{section}）"
        # section 不存在 → 新建
        self._doc.implicit.append(ImplicitSection(name=section, entries=[Entry(content=content, meta=f"置信度：{confidence}｜更新时间：{self._today()}", confidence=confidence)]))
        await self._save()
        return f"已写入隐式记忆（{section}）"

    async def query(self, keyword: str = "", memory_type: str = "") -> list[str]:
        results: list[str] = []
        kw = keyword.lower()

        def _match(e: Entry) -> bool:
            if not kw:
                return True
            return kw in e.content.lower() or kw in e.meta.lower()

        def _fmt(e: Entry) -> str:
            return f"- {e.content}｜{e.meta}" if e.meta else f"- {e.content}"

        async with self._lock:
            if memory_type in ("", "explicit"):
                results.extend(f"[显式] {_fmt(e)}" for e in self._doc.explicit if _match(e))
            if memory_type in ("", "implicit"):
                for s in self._doc.implicit:
                    for e in s.entries:
                        if _match(e):
                            results.append(f"[{s.name}] {_fmt(e)}")
            if memory_type == "archive":
                results.extend(f"[归档] {_fmt(e)}" for e in self._doc.archive if _match(e))
        return results

    async def update(self, target_content: str, new_content: str, memory_type: str = "") -> str:
        async with self._lock:
            new_content = new_content.strip()
            if not new_content:
                return "内容为空，跳过"
            # 隐式区匹配
            for s in self._doc.implicit:
                for i, e in enumerate(s.entries):
                    if e.content == target_content:
                        s.entries[i] = Entry(content=new_content, meta=f"置信度：{e.confidence or '低'}｜更新时间：{self._today()}", confidence=e.confidence)
                        self._archive(Entry(content=target_content, meta=f"{_ARCHIVE_PREFIX}：{self._today()}｜原记忆内容：{target_content}｜废弃原因：新记忆覆盖"))
                        await self._save()
                        return "已更新并归档旧记忆"
            # 显式区
            # 说明：spec 仅禁止 delete 显式记忆，update 未排除显式区，故允许改写并归档旧记忆（模板语义张力由产品层定夺）
            for i, e in enumerate(self._doc.explicit):
                if e.content == target_content:
                    self._doc.explicit[i] = Entry(content=new_content, meta="来源：会话描述｜优先级：最高")
                    self._archive(Entry(content=target_content, meta=f"{_ARCHIVE_PREFIX}：{self._today()}｜原记忆内容：{target_content}｜废弃原因：新记忆覆盖"))
                    await self._save()
                    return "已更新并归档旧记忆"
            # 无匹配 → 退化新增（已持锁，直接调 _add_unlocked 避免二次加锁死锁；section 用默认子板块）
            return await self._add_unlocked(memory_type or "implicit", SUBSECTIONS[0], new_content)

    async def delete(self, target_content: str, archive: bool = True) -> str:
        async with self._lock:
            # 强权限：显式记忆禁止自动删除
            if any(e.content == target_content for e in self._doc.explicit):
                raise MemoryPermissionError("用户显式记忆不可自动删除，请用户确认")
            deleted_any = False
            # 归档区：先物理删除已有的同内容归档条目（避免与本次新增归档混淆）
            remaining = [e for e in self._doc.archive if e.content != target_content]
            if len(remaining) != len(self._doc.archive):
                self._doc.archive = remaining
                deleted_any = True
            # 隐式区：删除全部匹配并归档（同一内容可能出现在多个子板块）
            for s in self._doc.implicit:
                kept: list[Entry] = []
                for e in s.entries:
                    if e.content == target_content:
                        if archive:
                            self._archive(Entry(content=target_content, meta=f"{_ARCHIVE_PREFIX}：{self._today()}｜原记忆内容：{target_content}｜废弃原因：信息失效"))
                        deleted_any = True
                    else:
                        kept.append(e)
                s.entries = kept
            if deleted_any:
                await self._save()
                return "已删除（归档）" if archive else "已彻底删除"
            return "未找到匹配记忆"

    def memory_text(self) -> str:
        """渲染注入文本：归档不注入、隐式截断 100 字、总上限 2000 字。

        超预算时按 spec 八：explicit 恒保留（优先级最高），隐式条目按
        (confidence desc, updated desc) 全局排序取前 N 条，逐条追加直到超限停止。
        说明：本方法为纯同步函数、无 await 点，asyncio 单线程事件循环下遍历
        中途不会被切换，因此不加锁读 _doc 是安全的；若未来改为异步/跨线程访问需加锁。
        """
        lines: list[str] = ["# 全局记忆"]
        lines.append("## 📌 用户显式记忆")
        for e in self._doc.explicit:
            lines.append(f"- {e.content}｜{e.meta}")

        # 收集隐式条目并全局排序：(confidence desc, updated desc)
        items: list[tuple[int, str, str, str]] = []
        for s in self._doc.implicit:
            for e in s.entries:
                conf = f"[{e.confidence}] " if e.confidence else ""
                line = f"- {conf}{e.content[:100]}"
                items.append((_conf_rank(e.confidence), _updated_key(e.meta), s.name, line))
        items.sort(key=lambda it: (it[0], it[1]), reverse=True)

        # 隐式区渲染行：section 标题跟随首个入选条目，条目按排序后顺序
        implicit_lines: list[str] = ["## 🧠 隐式记忆"]
        current_section = ""
        for _, _, section_name, line in items:
            if section_name != current_section:
                current_section = section_name
                implicit_lines.append(f"### {section_name}")
            implicit_lines.append(line)

        # 预算控制：explicit 区恒保留，隐式区逐行追加直到超限停止
        result = list(lines)
        used = len("\n".join(result))
        for line in implicit_lines:
            add_len = 1 + len(line)  # 与上一行之间的换行符 + 本行
            if used + add_len > _INJECT_CHAR_LIMIT:
                break
            result.append(line)
            used += add_len
        return "\n".join(result)

    async def stop(self) -> None:
        """预留：关闭锁/后台任务由调用方管理。"""
        return

    def load_sync(self) -> None:
        """同步 load：用于 build_components 等无事件循环场景。"""
        return asyncio.run(self.load())


class MemoryManagerPool:
    """多用户记忆管理器池：每个用户一个独立的 MemoryManager 实例。

    存储路径：data/memory/<username>/OPENFOX.md
    """

    def __init__(self, base_dir: str | Path = "./data/memory"):
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        self._pool: dict[str, MemoryManager] = {}
        self._lock = asyncio.Lock()

    async def get(self, username: str) -> MemoryManager:
        """获取指定用户的 MemoryManager（懒加载，首次访问时创建并 load）。"""
        if username in self._pool:
            return self._pool[username]
        async with self._lock:
            # double-check
            if username in self._pool:
                return self._pool[username]
            user_dir = self._base / username
            user_dir.mkdir(parents=True, exist_ok=True)
            memory_path = user_dir / _FILENAME
            # 兼容早期单用户版本在项目根目录保存的 OPENFOX.md。
            legacy_path = Path.cwd() / _FILENAME
            if username == "Ciel" and legacy_path.exists() and not memory_path.exists():
                memory_path = legacy_path
            mgr = MemoryManager(memory_path)
            await mgr.load()
            self._pool[username] = mgr
            logger.info("用户 %s 的记忆管理器已初始化：%s", username, memory_path)
            return mgr

    async def load_all_existing(self) -> None:
        """启动时预加载所有已有用户目录（可选，非必须）。"""
        if not self._base.exists():
            return
        for user_dir in self._base.iterdir():
            if user_dir.is_dir() and (user_dir / _FILENAME).exists():
                username = user_dir.name
                if username not in self._pool:
                    mgr = MemoryManager(user_dir / _FILENAME)
                    await mgr.load()
                    self._pool[username] = mgr
                    logger.info("预加载用户 %s 的记忆", username)
