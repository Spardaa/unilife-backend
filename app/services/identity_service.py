import logging
import re
from typing import Dict, Any
from app.models.identity import AgentIdentity
from app.services.user_data_service import user_data_service

logger = logging.getLogger("identity_service")

IDENTITY_FILENAME = "identity.md"


class IdentityService:
    def get_identity(self, user_id: str) -> AgentIdentity:
        """获取用户的 AI 身份配置"""
        content = user_data_service.read_file(user_id, IDENTITY_FILENAME)
        if content:
            return self._parse_identity(content)
        return AgentIdentity()
    
    def _parse_identity(self, content: str) -> AgentIdentity:
        """从 markdown 解析身份信息（兼容新旧格式）"""
        identity_data: Dict[str, Any] = {}
        
        for line in content.splitlines():
            line = line.strip()
            # 标题格式：# name emoji（由 _format_identity 生成）
            if line.startswith("# ") and "name" not in identity_data:
                title = line[2:].strip()
                # 用正则把末尾的 emoji 分离出来
                # emoji 范围覆盖常见 Unicode emoji + variation selector (FE0F) + ZWJ (200D)
                match = re.match(r'^(.+?)\s+([\U0001F300-\U0001FAFF\u2600-\u27BF\u2700-\u27BF\uFE0F\u200D]+)$', title)
                if match:
                    identity_data["name"] = match.group(1).strip()
                    identity_data["emoji"] = match.group(2).strip()
                else:
                    identity_data["name"] = title
            # 新格式：- **名字**: xxx
            elif line.startswith("- **名字**:"):
                identity_data["name"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **标志**:"):
                identity_data["emoji"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **物种**:") or line.startswith("- **身份:**"):
                identity_data["creature"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **性格**:"):
                identity_data["vibe"] = line.split(":", 1)[1].strip()
            # 旧格式兼容：- Name: xxx
            elif line.startswith("- Name:"):
                identity_data["name"] = line.split(":", 1)[1].strip()
            elif line.startswith("- Emoji:"):
                identity_data["emoji"] = line.split(":", 1)[1].strip()
            elif line.startswith("- Creature:"):
                identity_data["creature"] = line.split(":", 1)[1].strip()
            elif line.startswith("- Vibe:"):
                identity_data["vibe"] = line.split(":", 1)[1].strip()
        
        return AgentIdentity(**identity_data)
    
    def set_identity(self, user_id: str, identity: AgentIdentity):
        """保存用户的 AI 身份配置"""
        content = self._format_identity(identity)
        user_data_service.write_file(user_id, IDENTITY_FILENAME, content)

    def is_default(self, user_id: str) -> bool:
        """检查 AI 是否处于默认状态（名字或 emoji 为空表示尚未设置）"""
        identity = self.get_identity(user_id)
        return not identity.name or not identity.emoji

    def _format_identity(self, identity: AgentIdentity) -> str:
        """序列化身份信息到 markdown（更有人情味）"""
        return f"""# {identity.name} {identity.emoji}

- **身份:** {identity.creature}
- **性格:** {identity.vibe}

---

（等待你和用户一起写下更多故事...）
"""
    
    def format_identity_story(self, identity: AgentIdentity) -> str:
        """
        格式化身份故事（用于提示词注入）
        把 identity 转成一段自然的话，而不是配置列表
        """
        if not identity.name:
            return "你是一个刚刚被唤醒的 AI 助理，尚未拥有名字和身份。"
        return f"""你是 {identity.name} {identity.emoji}。

你是用户的{identity.creature}。
你的性格是：{identity.vibe}。"""


identity_service = IdentityService()
