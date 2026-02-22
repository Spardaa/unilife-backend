"""
Agent Base Classes - 基础抽象类和接口定义
定义所有 Agent 必须实现的核心接口
"""
from typing import List, Dict, Any, Optional, TypeVar, Generic
from abc import ABC, abstractmethod
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime


# ============ Intent Enums (从 intent.py 迁移) ============

class Intent(str, Enum):
    """用户意图分类"""

    # Event operations
    CREATE_EVENT = "create_event"
    QUERY_EVENT = "query_event"
    UPDATE_EVENT = "update_event"
    DELETE_EVENT = "delete_event"

    # Snapshot operations
    UNDO_CHANGE = "undo_change"
    RESTORE_SNAPSHOT = "restore_snapshot"

    # Energy related
    CHECK_ENERGY = "check_energy"
    SUGGEST_SCHEDULE = "suggest_schedule"

    # Query statistics
    GET_STATS = "get_stats"

    # User management
    UPDATE_PREFERENCES = "update_preferences"
    UPDATE_ENERGY_PROFILE = "update_energy_profile"

    # Small talk / general conversation
    CHITCHAT = "chitchat"
    GREETING = "greeting"
    THANKS = "thanks"
    GOODBYE = "goodbye"

    # Unknown / cannot understand
    UNKNOWN = "unknown"

    # New: Mixed intent (需要多个 Agent 处理)
    MIXED = "mixed"

    @classmethod
    def from_string(cls, value: str) -> "Intent":
        """将字符串转换为 Intent 枚举"""
        try:
            return cls(value)
        except ValueError:
            return cls.UNKNOWN


class IntentConfidence(BaseModel):
    """意图分类结果"""
    intent: Intent
    confidence: float  # 0.0 - 1.0
    reasoning: Optional[str] = None


# ============ Agent Response Models ============

class AgentResponse(BaseModel):
    """
    Agent 通用响应模型

    所有 Agent 的 process 方法都应该返回这个类型
    """
    content: str = Field(default="", description="自然语言回复内容")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(default=None, description="工具调用列表")
    actions: List[Dict[str, Any]] = Field(default_factory=list, description="执行的操作记录")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据（供下游 Agent 使用）")
    suggestions: Optional[List[Dict[str, Any]]] = None
    filtered_context: Optional[List[Dict[str, Any]]] = Field(default=None, description="Router筛选的相关上下文")

    class Config:
        arbitrary_types_allowed = True


# ============ Conversation Context ============

class ConversationContext(BaseModel):
    """
    对话上下文 - 在 Agent 之间传递

    包含：
    - 用户信息（ID、画像、决策偏好）
    - 对话历史
    - 当前意图
    - 上游 Agent 的执行结果
    """
    # 基础信息
    user_id: str
    conversation_id: str
    user_message: str

    # 意图信息
    current_intent: Optional[Intent] = None
    intent_confidence: float = 0.0
    intent_reasoning: Optional[str] = None

    # 用户画像
    user_profile: Optional[Dict[str, Any]] = None  # UserProfile (人格画像)
    user_decision_profile: Optional[Dict[str, Any]] = None  # UserDecisionProfile (决策偏好)

    # 对话历史（LLM 格式）
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)

    # 建议选项（从 Executor 的 provide_suggestions 工具返回）
    suggestions: Optional[List[Dict[str, Any]]] = None

    # 时间上下文
    current_time: Optional[str] = None  # 虚拟时间（用于测试）
    actual_time: datetime = Field(default_factory=datetime.utcnow)

    # 请求元数据
    request_metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True


# ============ Base Agent Interface ============

T = TypeVar('T', bound=AgentResponse)


class BaseAgent(ABC, Generic[T]):
    """
    Agent 基类 - 所有 Agent 必须实现的接口

    核心方法：
    - process(): 处理输入，返回 AgentResponse
    - get_system_prompt(): 获取系统提示词（可选）
    """

    name: str = "base_agent"

    @abstractmethod
    async def process(self, context: ConversationContext) -> AgentResponse:
        """
        处理输入并返回响应

        Args:
            context: 对话上下文，包含用户消息、画像、历史等

        Returns:
            AgentResponse: 包含回复、工具调用、元数据等
        """
        pass

    def get_system_prompt(self, context: Optional[ConversationContext] = None) -> str:
        """
        获取系统提示词（可选实现）

        Args:
            context: 对话上下文（用于动态生成提示词）

        Returns:
            系统提示词字符串
        """
        return ""

    async def validate_context(self, context: ConversationContext) -> bool:
        """
        验证上下文是否完整（可选实现）

        Args:
            context: 对话上下文

        Returns:
            是否通过验证
        """
        return context.user_id is not None and context.user_message is not None


# ============ Utility Functions ============

def build_messages_from_context(
    context: ConversationContext,
    system_prompt: str,
    max_history: int = 15
) -> List[Dict[str, Any]]:
    """
    从 ConversationContext 构建 LLM 消息列表

    Args:
        context: 对话上下文
        system_prompt: 系统提示词
        max_history: 最大历史消息数量

    Returns:
        LLM 格式的消息列表
    """
    messages = []

    # 添加系统提示
    messages.append({"role": "system", "content": system_prompt})

    # 添加历史消息（保留最近 N 条）
    last_assistant_had_tool_calls = False

    for msg in context.conversation_history[-max_history:]:
        role = msg.get("role")

        if role == "user":
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")

            # 如果有时间戳，添加到内容前
            if timestamp:
                content = f"{timestamp} {content}"

            messages.append({
                "role": "user",
                "content": content
            })
            last_assistant_had_tool_calls = False

        elif role == "assistant":
            assistant_msg = {}
            if msg.get("content"):
                content = msg["content"]
                # 注意：不要给 assistant 消息添加时间戳
                # 否则 AI 会模仿 [HH:MM] 格式，导致回复中重复出现时间戳
                assistant_msg["content"] = content

            if msg.get("tool_calls"):
                assistant_msg["tool_calls"] = msg["tool_calls"]
                last_assistant_had_tool_calls = True
            else:
                last_assistant_had_tool_calls = False

            if assistant_msg:
                assistant_msg["role"] = "assistant"
                messages.append(assistant_msg)

        elif role == "tool":
            # 只保留有对应 tool_calls 的 tool 消息
            if last_assistant_had_tool_calls:
                messages.append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id"),
                    "content": msg.get("content", "")
                })

    # 添加当前用户消息
    messages.append({
        "role": "user",
        "content": context.user_message
    })

    return messages


def extract_profile_summary(profile: Dict[str, Any]) -> str:
    """
    从用户画像提取摘要字符串（用于注入系统提示词）

    Args:
        profile: 用户画像字典

    Returns:
        画像摘要字符串
    """
    if not profile:
        return ""

    parts = []

    # 关系状态
    relationships = profile.get("relationships", {})
    if relationships.get("confidence", 0) > 0.7:
        status_list = relationships.get("status", [])
        if status_list:
            status_map = {
                "single": "单身",
                "has_friends": "有朋友",
                "dating": "约会中",
                "married": "已婚",
                "has_family": "有家人",
                "complicated": "感情状态复杂",
                "unknown": "未知"
            }
            mapped = [status_map.get(s, s) for s in status_list if s != "unknown"]
            if mapped:
                parts.append(f"- 用户感情状态：{', '.join(mapped)}")

    # 用户身份
    identity = profile.get("identity", {})
    if identity.get("confidence", 0) > 0.7:
        occupation = identity.get("occupation", "")
        if occupation and occupation != "unknown":
            parts.append(f"- 用户职业：{occupation}")

    # 个人喜好
    preferences = profile.get("preferences", {})
    activities = preferences.get("activity_types", [])
    if activities:
        parts.append(f"- 用户喜欢的活动：{', '.join(activities[:5])}")

    social = preferences.get("social_preference", "")
    if social and social != "unknown":
        social_map = {
            "introverted": "偏内向",
            "extroverted": "偏外向",
            "balanced": "社交平衡"
        }
        parts.append(f"- 社交倾向：{social_map.get(social, social)}")

    # 个人习惯
    habits = profile.get("habits", {})
    sleep = habits.get("sleep_schedule", "")
    if sleep and sleep != "unknown":
        sleep_map = {
            "early_bird": "早起型",
            "night_owl": "夜猫子",
            "irregular": "作息不规律"
        }
        parts.append(f"- 作息习惯：{sleep_map.get(sleep, sleep)}")

    if not parts:
        return ""

    return """## 关于用户（基于观察学习）

以下信息来自对用户行为的长期观察，请据此提供更个性化的服务：

""" + "\n".join(parts)
