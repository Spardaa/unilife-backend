"""
Observer Trigger Tracker - 追踪待分析的对话
实现 30min 延迟触发和 15 条消息阈值触发
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import asyncio


@dataclass
class PendingConversation:
    """待分析的对话"""
    conversation_id: str
    user_id: str
    last_message_at: datetime
    message_count: int = 1
    full_context: List[Dict] = field(default_factory=list)

    def add_message(self, context: List[Dict]) -> None:
        """添加消息到上下文"""
        self.message_count += 1
        self.last_message_at = datetime.utcnow()
        # 追加新的消息（从上次更新后开始）
        self.full_context.extend(context)

    def should_trigger_by_threshold(self, threshold: int = 15) -> bool:
        """检查是否达到消息阈值"""
        return self.message_count >= threshold

    def should_trigger_by_delay(self, delay_minutes: int = 30) -> bool:
        """检查是否超过延迟时间"""
        elapsed = (datetime.utcnow() - self.last_message_at).total_seconds() / 60
        return elapsed >= delay_minutes


class ObserverTriggerTracker:
    """
    Observer 触发追踪器

    两种触发方式：
    1. 延迟触发：用户最后一条消息后 30min 无新消息
    2. 阈值触发：连续累积 15 条消息后直接触发
    """

    def __init__(self):
        # 待分析的对话 {conversation_id: PendingConversation}
        self._pending: Dict[str, PendingConversation] = {}

        # 配置
        self.delay_trigger_minutes = 30
        self.message_threshold = 15

    def add_message(
        self,
        conversation_id: str,
        user_id: str,
        conversation_context: List[Dict]
    ) -> Optional[Dict[str, Any]]:
        """
        添加消息并检查是否应该触发

        Args:
            conversation_id: 对话ID
            user_id: 用户ID
            conversation_context: 完整对话上下文（从 Router 筛选前的原始历史）

        Returns:
            如果应该触发，返回触发信息；否则返回 None
        """
        now = datetime.utcnow()

        if conversation_id not in self._pending:
            # 新对话
            self._pending[conversation_id] = PendingConversation(
                conversation_id=conversation_id,
                user_id=user_id,
                last_message_at=now,
                full_context=conversation_context.copy()
            )
            return None

        pending = self._pending[conversation_id]

        # 添加新消息（只添加新增的部分）
        # 计算新增的消息数量
        current_count = len(conversation_context)
        previous_count = len(pending.full_context)
        new_messages = conversation_context[previous_count:] if current_count > previous_count else []

        if new_messages:
            pending.add_message(new_messages)

        # 检查阈值触发
        if pending.should_trigger_by_threshold(self.message_threshold):
            # 达到阈值，触发分析
            trigger_info = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "trigger_type": "threshold",
                "message_count": pending.message_count,
                "full_context": pending.full_context.copy()
            }
            # 清除待分析记录
            del self._pending[conversation_id]
            return trigger_info

        return None

    def check_delayed_triggers(self) -> List[Dict[str, Any]]:
        """
        检查所有待分析对话，返回应该延迟触发的列表

        Returns:
            应该触发的对话列表
        """
        triggered = []
        to_remove = []

        for conv_id, pending in self._pending.items():
            if pending.should_trigger_by_delay(self.delay_trigger_minutes):
                trigger_info = {
                    "conversation_id": conv_id,
                    "user_id": pending.user_id,
                    "trigger_type": "delay",
                    "elapsed_minutes": int((datetime.utcnow() - pending.last_message_at).total_seconds() / 60),
                    "message_count": pending.message_count,
                    "full_context": pending.full_context.copy()
                }
                triggered.append(trigger_info)
                to_remove.append(conv_id)

        # 清除已触发的记录
        for conv_id in to_remove:
            del self._pending[conv_id]

        return triggered

    def force_trigger(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        强制触发某个对话的分析（用于测试或手动触发）

        Returns:
            触发信息，如果对话不存在则返回 None
        """
        if conversation_id not in self._pending:
            return None

        pending = self._pending[conversation_id]
        trigger_info = {
            "conversation_id": conversation_id,
            "user_id": pending.user_id,
            "trigger_type": "manual",
            "message_count": pending.message_count,
            "full_context": pending.full_context.copy()
        }
        del self._pending[conversation_id]
        return trigger_info

    def get_pending_count(self) -> int:
        """获取待分析的对话数量"""
        return len(self._pending)

    def get_pending_info(self) -> List[Dict[str, Any]]:
        """获取所有待分析对话的信息"""
        return [
            {
                "conversation_id": conv_id,
                "user_id": pending.user_id,
                "message_count": pending.message_count,
                "last_message_at": pending.last_message_at.isoformat(),
                "elapsed_minutes": int((datetime.utcnow() - pending.last_message_at).total_seconds() / 60)
            }
            for conv_id, pending in self._pending.items()
        ]


# 全局追踪器实例
observer_trigger_tracker = ObserverTriggerTracker()
