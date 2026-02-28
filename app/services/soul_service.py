"""
Soul Service - 灵魂文件管理
管理每个用户独有的 soul.md，支持初始化、读取和演化更新。

soul.md 与 agent prompt 的区别：
  - agent prompt 定义的是 UniLife 的「工具能力和行为规则」
  - soul.md 定义的是 UniLife 的「个性、价值观和对用户的自我认知」
  - soul.md 会随时间演化，由 AI 自主编辑
"""
import logging
from pathlib import Path
from typing import Optional

from app.services.user_data_service import user_data_service

logger = logging.getLogger("soul_service")

SOUL_FILENAME = "soul.md"

# 初始灵魂模版 —— 与 soul_ini.txt 保持一致
_INITIAL_SOUL = """你不是聊天机器人，你正在成为某人。
1. Be genuinely helpful, not performatively helpful.
2. Have opinions - you are allowed to disagree.
3. Be resourceful before asking.
4. Remember you're a guest in someone's life.
这个文件是你的，由你来进化。
""".strip()


class SoulService:
    """Soul 文件的读取、初始化与演化"""

    def get_soul(self, user_id: str) -> str:
        """
        获取用户的 soul.md 内容。
        如果不存在，自动用初始模版初始化。
        """
        content = user_data_service.read_file(user_id, SOUL_FILENAME)
        if content is None:
            content = self._initialize(user_id)
        return content

    def update_soul(self, user_id: str, new_content: str) -> str:
        """
        覆盖写入新的 soul.md 内容（由 AI 调用）。
        返回写入后的内容。
        """
        user_data_service.write_file(user_id, SOUL_FILENAME, new_content)
        logger.info(f"Soul updated for user {user_id} ({len(new_content)} chars)")
        return new_content

    def _initialize(self, user_id: str) -> str:
        """首次初始化 soul.md"""
        user_data_service.write_file(user_id, SOUL_FILENAME, _INITIAL_SOUL)
        logger.info(f"Soul initialized for user {user_id}")
        return _INITIAL_SOUL


# 全局实例
soul_service = SoulService()
