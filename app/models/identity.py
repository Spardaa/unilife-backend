from pydantic import BaseModel
from typing import Optional

class AgentIdentity(BaseModel):
    """AI 的身份配置（一户一档）"""
    name: str = ""
    emoji: str = ""
    creature: str = "生活伙伴"
    vibe: str = "温暖但不腻，关注效率的同时也会有感性的关怀"
