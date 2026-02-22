"""
User Data Service - 用户文件数据管理
MVP 阶段直接使用本地文件系统，以 user_id 分隔目录

目录结构:
  data/users/{user_id}/
    ├── soul.md          # 用户灵魂文件
    └── memory.md        # 用户记忆日记
"""
import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("user_data_service")

# 项目根目录下的 data 文件夹
_BASE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "users"


class UserDataService:
    """管理每个用户的本地文件数据（soul.md / memory.md 等）"""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or _BASE_DIR

    # ---- 目录 ----

    def _user_dir(self, user_id: str) -> Path:
        """获取用户专属目录，不存在则自动创建"""
        d = self.base_dir / user_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ---- 通用读写 ----

    def read_file(self, user_id: str, filename: str) -> Optional[str]:
        """读取用户目录下的文件，不存在返回 None"""
        path = self._user_dir(user_id) / filename
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def write_file(self, user_id: str, filename: str, content: str) -> Path:
        """写入/覆盖用户目录下的文件，返回文件路径"""
        path = self._user_dir(user_id) / filename
        path.write_text(content, encoding="utf-8")
        logger.debug(f"Written {path} ({len(content)} chars)")
        return path

    def append_file(self, user_id: str, filename: str, content: str) -> Path:
        """追加内容到文件末尾"""
        path = self._user_dir(user_id) / filename
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
        return path

    def file_exists(self, user_id: str, filename: str) -> bool:
        return (self._user_dir(user_id) / filename).exists()


# 全局实例
user_data_service = UserDataService()
