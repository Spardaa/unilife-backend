"""
Conversation Summary Service - 对话摘要服务
负责对话历史的压缩和摘要管理
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, desc, and_, or_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import json
import logging

from app.models.conversation import Conversation, Message, Base
from app.models.conversation_summary import ConversationSummary
from app.config import settings
from app.services.llm import llm_service
from app.services.prompt import prompt_service
from app.services.identity_service import identity_service
from app.services.soul_service import soul_service

logger = logging.getLogger("summary_service")


# 摘要触发阈值
SUMMARY_THRESHOLD = 15      # 未摘要消息 >= 15 条时触发
COMPRESS_THRESHOLD = 20     # 未摘要消息 >= 20 条时进行混合压缩
COMPRESS_KEEP_RECENT = 5    # 混合压缩时保留最近 N 条消息


class ConversationSummaryService:
    """对话摘要服务"""

    def __init__(self, db_path: str = None):
        """初始化摘要服务"""
        if db_path is None:
            db_path = settings.database_url.replace("sqlite:///", "")

        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )

        # 创建表（如果不存在）
        ConversationSummary.__table__.create(self.engine, checkfirst=True)

        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()

    async def check_and_generate_summary(
        self,
        user_id: str,
        conversation_id: str,
        current_message_count: int
    ) -> Optional[str]:
        """
        检查是否需要生成摘要，如果需要则生成

        Args:
            user_id: 用户ID
            conversation_id: 对话ID
            current_message_count: 当前消息总数

        Returns:
            生成的摘要文本（如果生成了），否则 None
        """
        db = self.get_session()
        try:
            # 获取当前活跃的摘要
            active_summary = db.query(ConversationSummary).filter(
                and_(
                    ConversationSummary.user_id == user_id,
                    ConversationSummary.conversation_id == conversation_id,
                    ConversationSummary.is_active == True
                )
            ).order_by(desc(ConversationSummary.created_at)).first()

            # 计算未摘要的消息数
            if active_summary:
                # 获取摘要后新增的消息数
                messages_since = db.query(Message).filter(
                    and_(
                        Message.conversation_id == conversation_id,
                        Message.created_at > active_summary.created_at
                    )
                ).count()
                unsummarized_count = messages_since
            else:
                # 没有摘要，所有消息都是未摘要的
                unsummarized_count = current_message_count

            logger.debug(f"Unsummarized messages: {unsummarized_count}")

            # 根据阈值决定操作
            if unsummarized_count >= COMPRESS_THRESHOLD:
                # 混合压缩：旧摘要 + 最近5条 → 新摘要
                return await self._compress_summaries(
                    db, user_id, conversation_id, active_summary
                )
            elif unsummarized_count >= SUMMARY_THRESHOLD:
                # 生成新摘要
                return await self._generate_new_summary(
                    db, user_id, conversation_id, active_summary
                )

            return None

        finally:
            db.close()

    async def _generate_new_summary(
        self,
        db: Session,
        user_id: str,
        conversation_id: str,
        existing_summary: Optional[ConversationSummary]
    ) -> Optional[str]:
        """生成新的对话摘要"""
        # 获取需要摘要的消息
        query = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at)

        if existing_summary:
            query = query.filter(Message.created_at > existing_summary.created_at)

        messages = query.limit(COMPRESS_THRESHOLD).all()

        if not messages:
            return None

        # 生成摘要
        summary_text = await self._call_llm_for_summary(messages, user_id)

        if not summary_text:
            return None

        # 保存摘要
        new_summary = ConversationSummary(
            conversation_id=conversation_id,
            user_id=user_id,
            summary_text=summary_text,
            start_message_id=messages[0].id,
            end_message_id=messages[-1].id,
            message_count=len(messages),
            is_active=True,
            compression_level=0
        )

        db.add(new_summary)
        db.commit()

        logger.info(f"Generated new summary for conversation {conversation_id}: {len(messages)} messages")
        return summary_text

    async def _compress_summaries(
        self,
        db: Session,
        user_id: str,
        conversation_id: str,
        existing_summary: Optional[ConversationSummary]
    ) -> Optional[str]:
        """混合压缩：旧摘要 + 最近消息 → 新摘要"""
        # 获取最近 N 条消息
        recent_messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(desc(Message.created_at)).limit(COMPRESS_KEEP_RECENT).all()

        recent_messages.reverse()  # 恢复时间顺序

        if not recent_messages:
            return None

        # 构建压缩输入
        old_summary_text = existing_summary.summary_text if existing_summary else ""
        recent_text = self._format_messages_for_summary(recent_messages)

        # 调用 LLM 进行压缩
        compressed_text = await self._call_llm_for_compression(
            old_summary_text, recent_text
        )

        if not compressed_text:
            return None

        # 停用旧摘要
        if existing_summary:
            existing_summary.is_active = False

        # 创建新摘要
        new_summary = ConversationSummary(
            conversation_id=conversation_id,
            user_id=user_id,
            summary_text=compressed_text,
            start_message_id=recent_messages[0].id if recent_messages else None,
            end_message_id=recent_messages[-1].id if recent_messages else None,
            message_count=len(recent_messages),
            is_active=True,
            compression_level=(existing_summary.compression_level + 1) if existing_summary else 0
        )

        db.add(new_summary)
        db.commit()

        logger.info(f"Compressed summaries for conversation {conversation_id}")
        return compressed_text

    async def _call_llm_for_summary(self, messages: List[Message], user_id: str) -> Optional[str]:
        """调用 LLM 生成摘要"""
        try:
            # 加载用户个性化数据
            identity = identity_service.get_identity(user_id)
            soul_content = soul_service.get_soul(user_id)
            identity_story = identity_service.format_identity_story(identity)

            # 格式化消息
            formatted = self._format_messages_for_summary(messages)

            # 获取摘要 prompt
            try:
                system_prompt = prompt_service.load_prompt("agents/conversation_summary")
            except:
                system_prompt = self._get_default_summary_prompt()

            # 变量替换
            system_prompt = system_prompt.replace("{agent_name}", identity.name or "AI助理")
            system_prompt = system_prompt.replace("{agent_emoji}", identity.emoji or "")
            system_prompt = system_prompt.replace("{identity_story}", identity_story)
            system_prompt = system_prompt.replace("{soul_content}", soul_content)

            messages_for_llm = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请将以下对话历史压缩为简洁的摘要：\n\n{formatted}"}
            ]

            response = await llm_service.chat_completion(
                messages=messages_for_llm,
                temperature=0.3,
                max_tokens=500
            )

            return response.get("content", "")

        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return None

    async def _call_llm_for_compression(
        self,
        old_summary: str,
        recent_messages: str
    ) -> Optional[str]:
        """调用 LLM 进行混合压缩"""
        try:
            system_prompt = """你是一个对话摘要压缩专家。请将旧摘要和最近的对话合并为一个简洁的新摘要。

## 要求
1. 保留用户的主要意图和需求
2. 保留 AI 执行的关键操作（创建/修改/删除事件等）
3. 保留重要的决策和用户偏好
4. 移除已过时的细节
5. 控制在 300 字以内"""

            user_content = f"""## 旧摘要
{old_summary}

## 最近对话
{recent_messages}

请生成合并后的新摘要："""

            messages_for_llm = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]

            response = await llm_service.chat_completion(
                messages=messages_for_llm,
                temperature=0.3,
                max_tokens=500
            )

            return response.get("content", "")

        except Exception as e:
            logger.error(f"Failed to compress summaries: {e}")
            return None

    def _format_messages_for_summary(self, messages: List[Message]) -> str:
        """格式化消息用于摘要生成"""
        lines = []
        for msg in messages:
            role = msg.role
            content = msg.content or ""

            # 截断过长的内容
            if len(content) > 200:
                content = content[:200] + "..."

            # 简化角色名称
            role_name = {
                "user": "用户",
                "assistant": "AI",
                "tool": "工具"
            }.get(role, role)

            lines.append(f"[{role_name}] {content}")

        return "\n".join(lines)

    def _get_default_summary_prompt(self) -> str:
        """获取默认摘要 prompt（当文件加载失败时使用）"""
        return """# {agent_name} {agent_emoji}

{identity_story}

---

## 你的价值观

{soul_content}

---

# 对话摘要任务

你正在整理与用户的对话记录。请将对话历史压缩为简洁的摘要。

## 要求
1. 保留用户的主要意图和需求
2. 保留 AI 执行的关键操作（创建/修改/删除事件等）
3. 保留重要的决策和用户偏好
4. 忽略闲聊和无关内容
5. 控制在 200 字以内

## 输出格式
- 用户意图：...
- 执行操作：...
- 关键决策：..."""

    def get_active_summary(
        self,
        user_id: str,
        conversation_id: str
    ) -> Optional[str]:
        """获取活跃的对话摘要"""
        db = self.get_session()
        try:
            summary = db.query(ConversationSummary).filter(
                and_(
                    ConversationSummary.user_id == user_id,
                    ConversationSummary.conversation_id == conversation_id,
                    ConversationSummary.is_active == True
                )
            ).order_by(desc(ConversationSummary.created_at)).first()

            return summary.summary_text if summary else None

        finally:
            db.close()

    def deactivate_summaries(self, user_id: str, conversation_id: str = None):
        """
        停用用户的摘要（清空缓存时调用）

        Args:
            user_id: 用户ID
            conversation_id: 对话ID（可选，如果不提供则停用该用户所有摘要）
        """
        db = self.get_session()
        try:
            query = db.query(ConversationSummary).filter(
                ConversationSummary.user_id == user_id,
                ConversationSummary.is_active == True
            )

            if conversation_id:
                query = query.filter(ConversationSummary.conversation_id == conversation_id)

            count = query.update({"is_active": False})
            db.commit()

            logger.info(f"Deactivated {count} summaries for user {user_id}")
            return count

        finally:
            db.close()

    def get_unsummarized_message_count(
        self,
        user_id: str,
        conversation_id: str
    ) -> int:
        """获取未摘要的消息数量"""
        db = self.get_session()
        try:
            # 获取最新的活跃摘要
            summary = db.query(ConversationSummary).filter(
                and_(
                    ConversationSummary.user_id == user_id,
                    ConversationSummary.conversation_id == conversation_id,
                    ConversationSummary.is_active == True
                )
            ).order_by(desc(ConversationSummary.created_at)).first()

            # 计算未摘要消息数
            query = db.query(Message).filter(
                Message.conversation_id == conversation_id
            )

            if summary:
                query = query.filter(Message.created_at > summary.created_at)

            return query.count()

        finally:
            db.close()


# 全局摘要服务实例
conversation_summary_service = ConversationSummaryService()
