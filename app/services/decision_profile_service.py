"""
Decision Profile Service - 决策偏好服务 (简化版)
管理用户决策偏好的存储、更新和查询
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, Session
import json

from app.models.user_decision_profile import UserDecisionProfile
from app.config import settings


class DecisionProfileService:
    """决策偏好服务（简化版）"""

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

    def get_or_create_profile(self, user_id: str) -> UserDecisionProfile:
        """获取或创建决策偏好"""
        db = self.get_session()
        try:
            result = db.execute(
                text("""SELECT profile_data FROM user_decision_profiles WHERE user_id = :user_id"""),
                {"user_id": user_id}
            ).fetchone()

            if result:
                return UserDecisionProfile.from_dict(json.loads(result[0]))
            else:
                profile = UserDecisionProfile(user_id=user_id)
                self.save_profile(user_id, profile)
                return profile

        except Exception as e:
            if "no such table" in str(e) or "user_decision_profiles" in str(e):
                return UserDecisionProfile(user_id=user_id)
            raise e
        finally:
            db.close()

    def save_profile(self, user_id: str, profile: UserDecisionProfile) -> bool:
        """保存决策偏好"""
        db = self.get_session()
        try:
            profile_data = json.dumps(profile.to_dict())

            exists = db.execute(
                text("""SELECT id FROM user_decision_profiles WHERE user_id = :user_id"""),
                {"user_id": user_id}
            ).fetchone()

            if exists:
                db.execute(
                    text("""UPDATE user_decision_profiles 
                           SET profile_data = :profile_data, updated_at = :updated_at 
                           WHERE user_id = :user_id"""),
                    {
                        "profile_data": profile_data,
                        "updated_at": datetime.utcnow().isoformat(),
                        "user_id": user_id
                    }
                )
            else:
                db.execute(
                    text("""INSERT INTO user_decision_profiles 
                           (id, user_id, profile_data, created_at, updated_at) 
                           VALUES (:id, :user_id, :profile_data, :created_at, :updated_at)"""),
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
            if "no such table" in str(e) or "user_decision_profiles" in str(e):
                return True
            print(f"[Decision Profile Service] Error saving profile: {e}")
            return False
        finally:
            db.close()

    def update_scenario(
        self,
        user_id: str,
        scenario_type: str,
        action: str,
        confidence: float = 0.5
    ) -> bool:
        """记录场景决策"""
        profile = self.get_or_create_profile(user_id)
        profile.update_scenario(scenario_type, action, confidence)
        return self.save_profile(user_id, profile)

    def add_explicit_rule(self, user_id: str, rule: str) -> bool:
        """添加显式规则"""
        profile = self.get_or_create_profile(user_id)
        profile.add_explicit_rule(rule)
        return self.save_profile(user_id, profile)

    def update_conflict_strategy(self, user_id: str, strategy: str) -> bool:
        """更新冲突策略"""
        profile = self.get_or_create_profile(user_id)
        profile.conflict_strategy = strategy
        profile.updated_at = datetime.utcnow()
        return self.save_profile(user_id, profile)

    def get_profile_summary(self, user_id: str) -> Dict[str, Any]:
        """获取摘要供 Executor 注入"""
        profile = self.get_or_create_profile(user_id)
        return profile.get_summary_for_executor()

    def apply_updates(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """应用来自 Observer 的更新"""
        profile = self.get_or_create_profile(user_id)

        # 更新冲突策略
        if "conflict_strategy" in updates:
            profile.conflict_strategy = updates["conflict_strategy"]

        # 更新场景统计
        for scenario_type, data in updates.get("scenarios", {}).items():
            action = data.get("action")
            confidence = data.get("confidence", 0.5)
            if action:
                profile.update_scenario(scenario_type, action, confidence)

        # 添加显式规则
        for rule in updates.get("explicit_rules", []):
            profile.add_explicit_rule(rule)

        return self.save_profile(user_id, profile)


# 全局服务实例
decision_profile_service = DecisionProfileService()
