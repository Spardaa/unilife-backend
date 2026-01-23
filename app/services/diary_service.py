"""
Diary Service - 用户观察日记服务
管理日记的存储、查询和统计
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine, text, and_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.models.diary import UserDiary, DiaryStats, KeyInsights, ExtractedSignal
from app.config import settings
import json


class DiaryService:
    """用户观察日记服务"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = settings.database_url.replace("sqlite:///", "")

        self.engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False
        )

        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()

    def create_daily_diary(
        self,
        user_id: str,
        diary_date: date,
        summary: str,
        key_insights: Dict[str, Any],
        extracted_signals: List[Dict[str, Any]],
        conversation_count: int = 0,
        message_count: int = 0,
        tool_calls_count: int = 0
    ) -> UserDiary:
        """创建日记"""
        db = self.get_session()
        try:
            # 检查是否已存在
            existing = db.execute(
                text("""SELECT id FROM user_diaries WHERE user_id = :user_id AND diary_date = :diary_date"""),
                {"user_id": user_id, "diary_date": diary_date.isoformat()}
            ).fetchone()

            if existing:
                raise ValueError(f"Diary already exists for user {user_id} on date {diary_date}")

            # 构建 KeyInsights 对象
            insights = KeyInsights(**key_insights)

            # 构建 ExtractedSignal 列表
            signals = [ExtractedSignal(**s) for s in extracted_signals]

            # 创建日记对象
            diary = UserDiary(
                user_id=user_id,
                diary_date=diary_date,
                summary=summary,
                key_insights=insights,
                extracted_signals=signals,
                conversation_count=conversation_count,
                message_count=message_count,
                tool_calls_count=tool_calls_count
            )

            # 插入数据库
            diary_data = json.dumps(diary.to_dict())
            db.execute(
                text("""INSERT INTO user_diaries (id, user_id, diary_date, summary, key_insights,
                       extracted_signals, conversation_count, message_count, tool_calls_count, created_at)
                       VALUES (:id, :user_id, :diary_date, :summary, :key_insights,
                               :extracted_signals, :conversation_count, :message_count, :tool_calls_count, :created_at)"""),
                {
                    "id": diary.id,
                    "user_id": user_id,
                    "diary_date": diary_date.isoformat(),
                    "summary": summary,
                    "key_insights": json.dumps(key_insights),
                    "extracted_signals": json.dumps(extracted_signals),
                    "conversation_count": conversation_count,
                    "message_count": message_count,
                    "tool_calls_count": tool_calls_count,
                    "created_at": datetime.utcnow().isoformat()
                }
            )

            db.commit()
            return diary

        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def get_diary_by_date(self, user_id: str, diary_date: date) -> Optional[UserDiary]:
        """获取指定日期的日记"""
        db = self.get_session()
        try:
            result = db.execute(
                text("""SELECT diary_data FROM user_diaries
                       WHERE user_id = :user_id AND diary_date = :diary_date"""),
                {"user_id": user_id, "diary_date": diary_date.isoformat()}
            ).fetchone()

            if result:
                return UserDiary.from_dict(json.loads(result[0]))
            return None

        except Exception as e:
            print(f"[Diary Service] Error getting diary: {e}")
            return None
        finally:
            db.close()

    def get_diaries_by_period(
        self,
        user_id: str,
        start_date: date,
        end_date: date
    ) -> List[UserDiary]:
        """获取指定时间段的日记"""
        db = self.get_session()
        try:
            results = db.execute(
                text("""SELECT diary_data FROM user_diaries
                       WHERE user_id = :user_id
                       AND diary_date >= :start_date
                       AND diary_date <= :end_date
                       ORDER BY diary_date DESC"""),
                {
                    "user_id": user_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }
            ).fetchall()

            diaries = []
            for row in results:
                diaries.append(UserDiary.from_dict(json.loads(row[0])))

            return diaries

        except Exception as e:
            print(f"[Diary Service] Error getting diaries by period: {e}")
            return []
        finally:
            db.close()

    def get_recent_diaries(self, user_id: str, days: int = 7) -> List[UserDiary]:
        """获取最近的日记"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        return self.get_diaries_by_period(user_id, start_date, end_date)

    def get_all_diaries(
        self,
        user_id: str,
        limit: int = 30,
        offset: int = 0
    ) -> List[UserDiary]:
        """获取用户的所有日记（分页）"""
        db = self.get_session()
        try:
            results = db.execute(
                text("""SELECT diary_data FROM user_diaries
                       WHERE user_id = :user_id
                       ORDER BY diary_date DESC
                       LIMIT :limit OFFSET :offset"""),
                {"user_id": user_id, "limit": limit, "offset": offset}
            ).fetchall()

            diaries = []
            for row in results:
                diaries.append(UserDiary.from_dict(json.loads(row[0])))

            return diaries

        except Exception as e:
            print(f"[Diary Service] Error getting all diaries: {e}")
            return []
        finally:
            db.close()

    def diary_exists(self, user_id: str, diary_date: date) -> bool:
        """检查日记是否存在"""
        db = self.get_session()
        try:
            result = db.execute(
                text("""SELECT id FROM user_diaries
                       WHERE user_id = :user_id AND diary_date = :diary_date"""),
                {"user_id": user_id, "diary_date": diary_date.isoformat()}
            ).fetchone()

            return result is not None

        except Exception as e:
            print(f"[Diary Service] Error checking diary existence: {e}")
            return False
        finally:
            db.close()

    def get_diary_stats(self, user_id: str, days: int = 30) -> DiaryStats:
        """获取日记统计信息"""
        db = self.get_session()
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days - 1)

            results = db.execute(
                text("""SELECT conversation_count, message_count, tool_calls_count, diary_date
                       FROM user_diaries
                       WHERE user_id = :user_id
                       AND diary_date >= :start_date
                       AND diary_date <= :end_date"""),
                {
                    "user_id": user_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }
            ).fetchall()

            stats = DiaryStats()

            if results:
                stats.total_diaries = len(results)
                stats.total_conversations = sum(r[0] or 0 for r in results)
                stats.total_messages = sum(r[1] or 0 for r in results)
                stats.total_tool_calls = sum(r[2] or 0 for r in results)
                stats.avg_conversations_per_day = round(stats.total_conversations / days, 2)
                stats.date_range = {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }

            return stats

        except Exception as e:
            print(f"[Diary Service] Error getting diary stats: {e}")
            return DiaryStats()
        finally:
            db.close()

    def get_conversations_for_date(
        self,
        user_id: str,
        target_date: date
    ) -> List[Dict[str, Any]]:
        """
        获取指定日期的所有对话（用于生成日记）
        返回包含消息和工具调用的完整对话数据
        """
        from app.services.conversation_service import conversation_service

        db = self.get_session()
        try:
            # 计算目标日期的时间范围
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())

            # 查询该日期创建的所有对话
            results = db.execute(
                text("""SELECT id, title, message_count, created_at, updated_at
                       FROM conversations
                       WHERE user_id = :user_id
                       AND created_at >= :start_date
                       AND created_at <= :end_date
                       ORDER BY created_at ASC"""),
                {
                    "user_id": user_id,
                    "start_date": start_datetime.isoformat(),
                    "end_date": end_datetime.isoformat()
                }
            ).fetchall()

            conversations = []
            for row in results:
                conv_id, title, message_count, created_at, updated_at = row

                # 获取该对话的所有消息
                messages = conversation_service.get_messages(conv_id)

                # 统计工具调用次数
                tool_calls_count = sum(
                    1 for msg in messages if msg.tool_calls is not None
                )

                # 构建消息摘要
                messages_summary = self._build_messages_summary(messages)

                conversations.append({
                    "id": conv_id,
                    "title": title,
                    "message_count": message_count,
                    "tool_calls_count": tool_calls_count,
                    "created_at": created_at.isoformat() if created_at else None,
                    "updated_at": updated_at.isoformat() if updated_at else None,
                    "messages": messages_summary
                })

            return conversations

        except Exception as e:
            print(f"[Diary Service] Error getting conversations for date: {e}")
            return []
        finally:
            db.close()

    def _build_messages_summary(self, messages: List) -> List[Dict[str, str]]:
        """构建消息摘要（用于提供给 LLM）"""
        summary = []

        for msg in messages:
            item = {
                "role": msg.role,
                "content": msg.content or ""
            }

            if msg.tool_calls:
                import json as json_lib
                try:
                    tool_calls_data = json_lib.loads(msg.tool_calls)
                    item["tool_calls"] = tool_calls_data
                except:
                    pass

            summary.append(item)

        return summary

    def get_total_tool_calls_for_date(
        self,
        user_id: str,
        target_date: date
    ) -> int:
        """获取指定日期的工具调用总数"""
        from app.services.conversation_service import conversation_service

        conversations = self.get_conversations_for_date(user_id, target_date)
        return sum(conv.get("tool_calls_count", 0) for conv in conversations)

    def update_diary(
        self,
        user_id: str,
        diary_date: date,
        **updates
    ) -> Optional[UserDiary]:
        """更新日记"""
        db = self.get_session()
        try:
            # 检查是否存在
            existing = db.execute(
                text("""SELECT diary_data FROM user_diaries
                       WHERE user_id = :user_id AND diary_date = :diary_date"""),
                {"user_id": user_id, "diary_date": diary_date.isoformat()}
            ).fetchone()

            if not existing:
                return None

            # 加载现有日记
            diary = UserDiary.from_dict(json.loads(existing[0]))

            # 应用更新
            for key, value in updates.items():
                if hasattr(diary, key):
                    setattr(diary, key, value)

            # 更新数据库
            diary_data = json.dumps(diary.to_dict())
            db.execute(
                text("""UPDATE user_diaries
                       SET summary = :summary,
                           key_insights = :key_insights,
                           extracted_signals = :extracted_signals,
                           conversation_count = :conversation_count,
                           message_count = :message_count,
                           tool_calls_count = :tool_calls_count
                       WHERE user_id = :user_id AND diary_date = :diary_date"""),
                {
                    "summary": diary.summary,
                    "key_insights": json.dumps(diary.key_insights.model_dump()),
                    "extracted_signals": json.dumps([s.model_dump() for s in diary.extracted_signals]),
                    "conversation_count": diary.conversation_count,
                    "message_count": diary.message_count,
                    "tool_calls_count": diary.tool_calls_count,
                    "user_id": user_id,
                    "diary_date": diary_date.isoformat()
                }
            )

            db.commit()
            return diary

        except Exception as e:
            db.rollback()
            print(f"[Diary Service] Error updating diary: {e}")
            return None
        finally:
            db.close()

    def delete_diary(self, user_id: str, diary_date: date) -> bool:
        """删除日记"""
        db = self.get_session()
        try:
            result = db.execute(
                text("""DELETE FROM user_diaries
                       WHERE user_id = :user_id AND diary_date = :diary_date"""),
                {"user_id": user_id, "diary_date": diary_date.isoformat()}
            )

            db.commit()
            return result.rowcount > 0

        except Exception as e:
            db.rollback()
            print(f"[Diary Service] Error deleting diary: {e}")
            return False
        finally:
            db.close()


# 全局服务实例
diary_service = DiaryService()
