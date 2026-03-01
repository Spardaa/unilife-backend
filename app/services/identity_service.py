import logging
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
        """从 markdown 解析身份信息"""
        identity_data: Dict[str, Any] = {}
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("- **名字**:"):
                identity_data["name"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **标志**:"):
                identity_data["emoji"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **物种**:"):
                identity_data["creature"] = line.split(":", 1)[1].strip()
            elif line.startswith("- **性格**:"):
                identity_data["vibe"] = line.split(":", 1)[1].strip()
        
        # Merge with defaults
        return AgentIdentity(**identity_data)
    
    def set_identity(self, user_id: str, identity: AgentIdentity) -> None:
        """设置 AI 身份"""
        content = self._format_identity(identity)
        user_data_service.write_file(user_id, IDENTITY_FILENAME, content)

    def _format_identity(self, identity: AgentIdentity) -> str:
        """序列化身份信息到 markdown"""
        return f"""# 你的身份

- **名字**: {identity.name}
- **物种**: {identity.creature}
- **标志**: {identity.emoji}
- **性格**: {identity.vibe}
"""

identity_service = IdentityService()
