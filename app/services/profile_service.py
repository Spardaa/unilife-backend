"""
User Profile Service - 用户画像服务
管理用户画像的存储、聚合和查询
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, Session

from app.models.user_profile import UserProfile
from app.models.event import ExtractedPoint
from app.config import settings


class UserProfileService:
    """用户画像服务"""

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

    def get_or_create_profile(self, user_id: str) -> UserProfile:
        """获取或创建用户画像"""
        db = self.get_session()
        try:
            # 尝试从数据库读取（使用原生SQL）
            result = db.execute(
                text("""SELECT profile_data FROM user_profiles WHERE user_id = :user_id"""),
                {"user_id": user_id}
            ).fetchone()

            if result:
                profile_data = result[0]
                import json
                return UserProfile.from_dict(json.loads(profile_data))
            else:
                # 创建新画像
                profile = UserProfile(user_id=user_id)
                self.save_profile(user_id, profile)
                return profile

        except Exception as e:
            print(f"[Profile Service] Error loading profile: {e}")
            # 返回默认画像
            return UserProfile(user_id=user_id)
        finally:
            db.close()

    def save_profile(self, user_id: str, profile: UserProfile) -> bool:
        """保存用户画像"""
        db = self.get_session()
        try:
            import json

            profile_data = json.dumps(profile.to_dict())

            # 检查是否存在
            exists = db.execute(
                text("""SELECT id FROM user_profiles WHERE user_id = :user_id"""),
                {"user_id": user_id}
            ).fetchone()

            if exists:
                # 更新
                db.execute(
                    text("""UPDATE user_profiles SET profile_data = :profile_data, updated_at = :updated_at WHERE user_id = :user_id"""),
                    {
                        "profile_data": profile_data,
                        "updated_at": datetime.utcnow().isoformat(),
                        "user_id": user_id
                    }
                )
            else:
                # 插入
                db.execute(
                    text("""INSERT INTO user_profiles (id, user_id, profile_data, created_at, updated_at) VALUES (:id, :user_id, :profile_data, :created_at, :updated_at)"""),
                    {
                        "id": str(profile.id),
                        "user_id": user_id,
                        "profile_data": profile_data,
                        "created_at": profile.created_at.isoformat(),
                        "updated_at": profile.updated_at.isoformat()
                    }
                )

            db.commit()
            return True

        except Exception as e:
            db.rollback()
            print(f"[Profile Service] Error saving profile: {e}")
            return False
        finally:
            db.close()

    def add_extracted_points(
        self,
        user_id: str,
        points: List[Dict[str, Any]]
    ) -> UserProfile:
        """添加提取的画像点，更新用户画像"""
        profile = self.get_or_create_profile(user_id)
        profile.update_from_points(points)
        self.save_profile(user_id, profile)
        return profile

    def get_profile_summary(self, user_id: str) -> Dict[str, Any]:
        """获取用户画像摘要（用于展示或提供给Agent）"""
        profile = self.get_or_create_profile(user_id)

        return {
            "user_id": user_id,
            "relationships": {
                "status": profile.relationships.status,
                "confidence": profile.relationships.confidence
            },
            "identity": {
                "occupation": profile.identity.occupation,
                "industry": profile.identity.industry,
                "confidence": profile.identity.confidence
            },
            "preferences": {
                "activities": profile.preferences.activity_types[:5],  # 最多显示5个
                "social": profile.preferences.social_preference
            },
            "habits": {
                "sleep": profile.habits.sleep_schedule,
                "work_hours": profile.habits.work_hours
            },
            "total_points": profile.total_points,
            "updated_at": profile.updated_at.isoformat()
        }


# 全局服务实例
profile_service = UserProfileService()
