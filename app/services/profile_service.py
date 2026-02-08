"""
User Profile Service - 用户画像服务 (简化版)
管理用户画像的存储、聚合和查询
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, Session

from app.models.user_profile import UserProfile
from app.config import settings


class UserProfileService:
    """用户画像服务（简化版）"""

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

        # Ensure table exists
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        """确保 user_profiles 表存在"""
        try:
            with self.engine.connect() as connection:
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        profile_data TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """))
                # 创建索引
                connection.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id)
                """))
        except Exception as e:
            print(f"[Profile Service] Error creating table: {e}")

    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()

    def get_or_create_profile(self, user_id: str) -> UserProfile:
        """获取或创建用户画像"""
        db = self.get_session()
        try:
            result = db.execute(
                text("""SELECT profile_data FROM user_profiles WHERE user_id = :user_id"""),
                {"user_id": user_id}
            ).fetchone()

            if result:
                import json
                return UserProfile.from_dict(json.loads(result[0]))
            else:
                profile = UserProfile(user_id=user_id)
                self.save_profile(user_id, profile)
                return profile

        except Exception as e:
            if "no such table" in str(e) or "user_profiles" in str(e):
                return UserProfile(user_id=user_id)
            raise e
        finally:
            db.close()

    def save_profile(self, user_id: str, profile: UserProfile) -> bool:
        """保存用户画像"""
        db = self.get_session()
        try:
            import json
            profile_data = json.dumps(profile.to_dict())

            exists = db.execute(
                text("""SELECT id FROM user_profiles WHERE user_id = :user_id"""),
                {"user_id": user_id}
            ).fetchone()

            if exists:
                db.execute(
                    text("""UPDATE user_profiles SET profile_data = :profile_data, updated_at = :updated_at WHERE user_id = :user_id"""),
                    {
                        "profile_data": profile_data,
                        "updated_at": datetime.utcnow().isoformat(),
                        "user_id": user_id
                    }
                )
            else:
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
            if "no such table" in str(e) or "user_profiles" in str(e):
                return True
            print(f"[Profile Service] Error saving profile: {e}")
            return False
        finally:
            db.close()

    def get_profile_summary(self, user_id: str) -> Dict[str, Any]:
        """获取用户画像摘要（用于注入 Agent）"""
        profile = self.get_or_create_profile(user_id)
        return profile.get_summary()

    def update_preference(self, user_id: str, key: str, value: Any) -> bool:
        """更新单个偏好"""
        profile = self.get_or_create_profile(user_id)
        profile.update_preference(key, value)
        return self.save_profile(user_id, profile)

    def add_rule(self, user_id: str, rule: str) -> bool:
        """添加显式规则"""
        profile = self.get_or_create_profile(user_id)
        profile.add_explicit_rule(rule)
        return self.save_profile(user_id, profile)

    def update_pattern(self, user_id: str, pattern_name: str, confidence: float) -> bool:
        """更新学习模式"""
        profile = self.get_or_create_profile(user_id)
        profile.update_pattern(pattern_name, confidence)
        return self.save_profile(user_id, profile)


# 全局服务实例
profile_service = UserProfileService()
