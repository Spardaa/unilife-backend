"""
Memory Service - 记忆日记管理
管理每个用户的 memory.md，由 Observer 定期编写日记。

memory.md 结构：
  # UniLife Memory

  ## Weekly Summary (历史摘要归档)
  ...精炼后的旧记忆...

  ## Recent Diary (近一周完整日记)
  ### 2026-02-22 Saturday
  今天和用户聊了很多关于……

策略：
  - 近 7 天保留完整日记条目
  - 更早的内容由 LLM 压缩为 Weekly Summary
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, List

from app.services.user_data_service import user_data_service

logger = logging.getLogger("memory_service")

MEMORY_FILENAME = "memory.md"

_INITIAL_MEMORY = """# 记忆

## 关于用户

_（暂无记录，Observer 会在每日复盘时更新这里）_

---

## 本周观察


---

## 近期日记

""".strip()

_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class MemoryService:
    """记忆日记的读取、写入与精炼"""

    # ---- 读取 ----

    def get_memory(self, user_id: str) -> str:
        """获取完整 memory.md，不存在则初始化"""
        content = user_data_service.read_file(user_id, MEMORY_FILENAME)
        if content is None:
            content = self._initialize(user_id)
        return content

    def get_long_term_memory(self, user_id: str) -> str:
        """提取「关于用户」长期记忆区块（每次对话都注入）"""
        full = self.get_memory(user_id)
        # 新格式：## 关于用户
        match = re.search(r"## 关于用户[^\n]*\n(.*?)(?=\n---|\n## |$)", full, re.DOTALL)
        if match:
            content = match.group(1).strip()
            # 过滤掉初始占位符
            if content and content != "_（暂无记录，Observer 会在每日复盘时更新这里）_" and content != "_（暂无记录）_":
                return content
        # 兼容旧格式：## UniLife 眼中的用户
        match = re.search(r"## UniLife 眼中的用户[^\n]*\n(.*?)(?=\n## |$)", full, re.DOTALL)
        if match:
            content = match.group(1).strip()
            if content and content != "_（暂无记录）_":
                return content
        return ""

    def get_recent_diary(self, user_id: str, days: int = 7) -> str:
        """提取近 N 天的日记条目（供 ContextFilter 注入）"""
        full = self.get_memory(user_id)
        # 兼容新旧格式
        match = re.search(r"## (?:近期日记|Recent Diary)\s*\n(.*)", full, re.DOTALL)
        if not match:
            return ""
        return match.group(1).strip()

    def get_weekly_summary(self, user_id: str) -> str:
        """提取历史摘要部分"""
        full = self.get_memory(user_id)
        match = re.search(r"## (?:本周观察|Weekly Summary)\s*\n(.*?)(?=\n---|\n## )", full, re.DOTALL)
        if not match:
            return ""
        return match.group(1).strip()

    def get_relevant_memory(self, user_id: str, query: str, days: int = 14) -> str:
        """
        根据 query 关键词，从日记中选择性提取最相关的片段。

        策略：
        1. 解析所有最近 N 天的日记条目
        2. 对每条日记按关键词重叠度打分
        3. 返回评分最高的 1-3 条（或全部，如果总量很少）

        Args:
            user_id: 用户 ID
            query: 检索描述（一句话）
            days: 最多追溯多少天

        Returns:
            相关的记忆片段文本，如无相关内容则返回近 3 天日记
        """
        full = self.get_memory(user_id)
        diary_match = re.search(r"## (?:近期日记|Recent Diary)\s*\n(.*)", full, re.DOTALL)
        if not diary_match:
            return ""

        diary_body = diary_match.group(1)

        # 分割成单独条目
        raw_entries = re.split(r"(?=### \d{4}-\d{2}-\d{2})", diary_body)
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        scored = []
        query_words = set(query.lower().split())
        for entry in raw_entries:
            entry = entry.strip()
            if not entry:
                continue
            date_m = re.match(r"### (\d{4}-\d{2}-\d{2})", entry)
            if date_m and date_m.group(1) < cutoff:
                continue

            # 关键词重叠评分
            entry_words = set(re.sub(r"[^\w\s]", "", entry.lower()).split())
            overlap = len(query_words & entry_words)
            scored.append((overlap, entry))

        if not scored:
            return self.get_recent_diary(user_id, days=3)

        # 排序取最相关的 1-3 条
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [e for _, e in scored[:3] if _ > 0] or [scored[0][1]]

        return "\n\n".join(top)

    def update_user_perception(self, user_id: str, perception: str, pattern_notes: list = None) -> None:
        """
        更新 memory.md 中「关于用户」长期记忆区块。
        
        由 Observer 每日调用，用自然语言描述对用户的认识。
        该区块会被替换（而非追加），保持简洁。

        Args:
            user_id: 用户 ID
            perception: 自然语言描述
            pattern_notes: 行为模式列表
        """
        full = self.get_memory(user_id)
        today = datetime.now().strftime("%Y-%m-%d")
        patterns_str = ""
        if pattern_notes:
            patterns_str = "\n" + "\n".join(f"- {p}" for p in pattern_notes)

        new_block = f"## 关于用户\n\n_（最后更新：{today}）_\n\n{perception}{patterns_str}\n"

        # 尝试替换新格式
        if "## 关于用户" in full:
            new_full = re.sub(
                r"## 关于用户[^\n]*\n.*?(?=\n---|\n## |\Z)",
                new_block,
                full,
                flags=re.DOTALL
            )
        # 兼容旧格式
        elif "## UniLife 眼中的用户" in full:
            new_full = re.sub(
                r"## UniLife 眼中的用户.*?(?=\n## |\Z)",
                new_block + "\n",
                full,
                flags=re.DOTALL
            )
        else:
            # 插入到标题后面
            new_full = re.sub(
                r"(# (?:记忆|UniLife Memory)\s*)",
                f"\\1\n{new_block}\n",
                full
            )

        user_data_service.write_file(user_id, MEMORY_FILENAME, new_full)
        logger.info(f"User perception updated for {user_id}")

    # ---- 写入 ----

    def append_diary_entry(self, user_id: str, date_str: str, entry: str) -> None:
        """
        追加一条日记到 Recent Diary 段落末尾。

        Args:
            user_id: 用户 ID
            date_str: 日期 YYYY-MM-DD
            entry: 日记正文（第一人称）
        """
        full = self.get_memory(user_id)

        # 解析 weekday
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            weekday = _WEEKDAY_NAMES[dt.weekday()]
        except Exception:
            weekday = ""

        new_block = f"\n### {date_str} {weekday}\n{entry}\n"

        # 插入到 Recent Diary 末尾
        if "## 近期日记" in full or "## Recent Diary" in full:
            full = full.rstrip() + "\n" + new_block
        else:
            full += f"\n## 近期日记\n{new_block}"

        user_data_service.write_file(user_id, MEMORY_FILENAME, full)
        logger.info(f"Diary appended for user {user_id} on {date_str}")

    # ---- 精炼 / 老化 ----

    def consolidate_old_entries(self, user_id: str, summary_text: str, cutoff_date: str) -> None:
        """
        将 cutoff_date 之前的日记条目替换为 summary_text，
        追加到 Weekly Summary 段落。

        Args:
            user_id: 用户 ID
            summary_text: LLM 压缩后的本周摘要
            cutoff_date: 截止日期 YYYY-MM-DD，该日期之前的条目会被移除
        """
        full = self.get_memory(user_id)

        # 提取 Recent Diary 区域
        diary_match = re.search(r"(## (?:近期日记|Recent Diary)\s*\n)(.*)", full, re.DOTALL)
        if not diary_match:
            return

        diary_header = diary_match.group(1)
        diary_body = diary_match.group(2)

        # 按 ### YYYY-MM-DD 分割日记条目
        entries = re.split(r"(?=### \d{4}-\d{2}-\d{2})", diary_body)
        kept = []
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue
            date_m = re.match(r"### (\d{4}-\d{2}-\d{2})", entry)
            if date_m and date_m.group(1) >= cutoff_date:
                kept.append(entry)

        # 重建 Recent Diary
        new_diary = diary_header + "\n".join(kept) + "\n"

        # 追加摘要到 Weekly Summary
        summary_match = re.search(r"(## (?:本周观察|Weekly Summary)\s*\n)(.*?)(?=\n---|\n## )", full, re.DOTALL)
        if summary_match:
            old_summary = summary_match.group(2).strip()
            new_summary_block = (old_summary + "\n\n" + summary_text).strip()
            before = full[:summary_match.start(2)]
            after_summary = full[summary_match.end(2):diary_match.start()]
            new_full = before + new_summary_block + "\n" + after_summary + new_diary
        else:
            new_full = full[:diary_match.start()] + f"## 本周观察\n{summary_text}\n\n" + new_diary

        user_data_service.write_file(user_id, MEMORY_FILENAME, new_full)
        logger.info(f"Memory consolidated for user {user_id}, cutoff={cutoff_date}")

    # ---- 内部 ----

    def _initialize(self, user_id: str) -> str:
        user_data_service.write_file(user_id, MEMORY_FILENAME, _INITIAL_MEMORY)
        logger.info(f"Memory initialized for user {user_id}")
        return _INITIAL_MEMORY


# 全局实例
memory_service = MemoryService()
