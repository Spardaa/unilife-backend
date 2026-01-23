"""
Decision Profile Service - 决策偏好服务
管理用户决策偏好的存储、更新和查询
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker, Session
import json

from app.models.user_decision_profile import (
    UserDecisionProfile, TimePreference, MeetingPreference,
    EnergyProfile, ConflictResolution, ScenarioPreference
)
from app.config import settings


class DecisionProfileService:
    """决策偏好服务"""

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
            # 使用原生 SQL 查询
            result = db.execute(
                text("""SELECT * FROM user_decision_profiles WHERE user_id = :user_id"""),
                {"user_id": user_id}
            ).fetchone()

            if result:
                # 从数据库加载
                return self._result_to_profile(result)
            else:
                # 创建新决策偏好
                profile = UserDecisionProfile(user_id=user_id)
                self.save_profile(user_id, profile)
                return profile

        except Exception as e:
            # 表不存在或其他数据库错误
            if "no such table" in str(e) or "user_decision_profiles" in str(e):
                # 表不存在，返回默认决策偏好（静默处理）
                return UserDecisionProfile(user_id=user_id)
            else:
                # 其他错误，仍然抛出
                raise e
        finally:
            db.close()

    def _result_to_profile(self, result) -> UserDecisionProfile:
        """将数据库查询结果转换为 UserDecisionProfile"""
        import json

        # 处理场景偏好中的 datetime
        scenarios_data = self._parse_json(result[6] or "[]")
        scenario_preferences = []
        for s in scenarios_data:
            s_dict = s.copy()
            if "last_updated" in s_dict and isinstance(s_dict["last_updated"], str):
                s_dict["last_updated"] = datetime.fromisoformat(s_dict["last_updated"])
            scenario_preferences.append(ScenarioPreference(**s_dict))

        # 安全解析 JSON，过滤掉 None 值避免 Pydantic 验证错误
        def safe_parse_to_model(json_str, model_class):
            """安全解析 JSON 并创建模型实例，过滤 None 值"""
            data = self._parse_json(json_str)
            if not isinstance(data, dict):
                data = {}
            # 过滤掉 None 值
            filtered_data = {k: v for k, v in data.items() if v is not None}
            return model_class(**filtered_data)

        return UserDecisionProfile(
            id=result[0],  # id
            user_id=result[1],  # user_id
            time_preference=safe_parse_to_model(result[2], TimePreference),
            meeting_preference=safe_parse_to_model(result[3], MeetingPreference),
            energy_profile=safe_parse_to_model(result[4], EnergyProfile),
            conflict_resolution=safe_parse_to_model(result[5], ConflictResolution),
            scenario_preferences=scenario_preferences,
            explicit_rules=self._parse_json(result[7] or "[]"),
            confidence_scores=self._parse_json(result[8] or "{}"),
            created_at=datetime.fromisoformat(result[9]),
            updated_at=datetime.fromisoformat(result[10])
        )

    def _parse_json(self, json_str: str) -> Any:
        """安全解析 JSON 字符串"""
        if not json_str or json_str == "":
            return {} if not json_str.startswith("[") else []
        try:
            return json.loads(json_str)
        except:
            return {}

    def save_profile(self, user_id: str, profile: UserDecisionProfile) -> bool:
        """保存决策偏好"""
        db = self.get_session()
        try:
            import json

            # 检查是否存在
            exists = db.execute(
                text("""SELECT id FROM user_decision_profiles WHERE user_id = :user_id"""),
                {"user_id": user_id}
            ).fetchone()

            # 准备 JSON 数据
            time_pref_json = json.dumps(profile.time_preference.model_dump())
            meeting_pref_json = json.dumps(profile.meeting_preference.model_dump())
            energy_pref_json = json.dumps(profile.energy_profile.model_dump())
            conflict_json = json.dumps(profile.conflict_resolution.model_dump())

            # 场景偏好需要特殊处理 datetime
            scenarios_list = []
            for p in profile.scenario_preferences:
                scenario_dict = p.model_dump()
                scenario_dict["last_updated"] = scenario_dict["last_updated"].isoformat()
                scenarios_list.append(scenario_dict)
            scenarios_json = json.dumps(scenarios_list)

            rules_json = json.dumps(profile.explicit_rules)
            scores_json = json.dumps(profile.confidence_scores)

            if exists:
                # 更新
                db.execute(
                    text("""UPDATE user_decision_profiles
                           SET time_preference = :time_pref,
                               meeting_preference = :meeting_pref,
                               energy_profile = :energy_pref,
                               conflict_resolution = :conflict,
                               scenario_preferences = :scenarios,
                               explicit_rules = :rules,
                               confidence_scores = :scores,
                               updated_at = :updated_at
                           WHERE user_id = :user_id"""),
                    {
                        "time_pref": time_pref_json,
                        "meeting_pref": meeting_pref_json,
                        "energy_pref": energy_pref_json,
                        "conflict": conflict_json,
                        "scenarios": scenarios_json,
                        "rules": rules_json,
                        "scores": scores_json,
                        "updated_at": datetime.utcnow().isoformat(),
                        "user_id": user_id
                    }
                )
            else:
                # 插入
                db.execute(
                    text("""INSERT INTO user_decision_profiles
                           (id, user_id, time_preference, meeting_preference, energy_profile,
                            conflict_resolution, scenario_preferences, explicit_rules,
                            confidence_scores, created_at, updated_at)
                           VALUES (:id, :user_id, :time_pref, :meeting_pref, :energy_pref,
                                   :conflict, :scenarios, :rules, :scores, :created_at, :updated_at)"""),
                    {
                        "id": str(profile.id),
                        "user_id": user_id,
                        "time_pref": time_pref_json,
                        "meeting_pref": meeting_pref_json,
                        "energy_pref": energy_pref_json,
                        "conflict": conflict_json,
                        "scenarios": scenarios_json,
                        "rules": rules_json,
                        "scores": scores_json,
                        "created_at": profile.created_at.isoformat(),
                        "updated_at": profile.updated_at.isoformat()
                    }
                )

            db.commit()
            return True

        except Exception as e:
            db.rollback()
            # 表不存在时静默处理，不影响核心功能
            if "no such table" in str(e) or "user_decision_profiles" in str(e):
                # 表不存在，静默返回 True（表示"已处理"）
                return True
            else:
                # 其他错误仍然打印
                print(f"[Decision Profile Service] Error saving profile: {e}")
                return False
        finally:
            db.close()

    def update_scenario_preference(
        self,
        user_id: str,
        scenario_type: str,
        action: str,
        confidence: float = 0.5
    ) -> bool:
        """
        更新场景偏好（带置信度加权平均）

        Args:
            user_id: 用户ID
            scenario_type: 场景类型（如 time_conflict, event_cancellation）
            action: 采取的行动
            confidence: 置信度 (0.0-1.0)

        Returns:
            是否成功更新
        """
        profile = self.get_or_create_profile(user_id)
        profile.update_scenario_preference(scenario_type, action, confidence)
        return self.save_profile(user_id, profile)

    def add_explicit_rule(self, user_id: str, rule: str) -> bool:
        """
        添加显式规则

        Args:
            user_id: 用户ID
            rule: 规则文本

        Returns:
            是否成功添加
        """
        profile = self.get_or_create_profile(user_id)
        profile.add_explicit_rule(rule)
        return self.save_profile(user_id, profile)

    def remove_explicit_rule(self, user_id: str, rule: str) -> bool:
        """
        移除显式规则

        Args:
            user_id: 用户ID
            rule: 规则文本

        Returns:
            是否成功移除
        """
        profile = self.get_or_create_profile(user_id)
        result = profile.remove_explicit_rule(rule)
        if result:
            return self.save_profile(user_id, profile)
        return False

    def update_time_preference(
        self,
        user_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        更新时间偏好

        Args:
            user_id: 用户ID
            updates: 更新的字段字典

        Returns:
            是否成功更新
        """
        profile = self.get_or_create_profile(user_id)
        for key, value in updates.items():
            if hasattr(profile.time_preference, key) and value is not None:
                setattr(profile.time_preference, key, value)
        profile.updated_at = datetime.utcnow()
        return self.save_profile(user_id, profile)

    def update_meeting_preference(
        self,
        user_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        更新会议偏好

        Args:
            user_id: 用户ID
            updates: 更新的字段字典

        Returns:
            是否成功更新
        """
        profile = self.get_or_create_profile(user_id)
        for key, value in updates.items():
            if hasattr(profile.meeting_preference, key) and value is not None:
                setattr(profile.meeting_preference, key, value)
        profile.updated_at = datetime.utcnow()
        return self.save_profile(user_id, profile)

    def update_conflict_resolution(
        self,
        user_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        更新冲突解决偏好

        Args:
            user_id: 用户ID
            updates: 更新的字段字典

        Returns:
            是否成功更新
        """
        profile = self.get_or_create_profile(user_id)
        for key, value in updates.items():
            if hasattr(profile.conflict_resolution, key) and value is not None:
                setattr(profile.conflict_resolution, key, value)
        profile.updated_at = datetime.utcnow()
        return self.save_profile(user_id, profile)

    def get_profile_summary(self, user_id: str) -> Dict[str, Any]:
        """
        获取格式化的摘要供 LLM 注入

        Args:
            user_id: 用户ID

        Returns:
            决策偏好摘要字典
        """
        profile = self.get_or_create_profile(user_id)

        # 获取所有场景偏好
        scenario_summary = {}
        for pref in profile.scenario_preferences:
            scenario_summary[pref.scenario_type] = {
                "action": pref.preferred_action,
                "confidence": pref.confidence,
                "samples": pref.sample_count
            }

        return {
            "user_id": user_id,
            "time_preference": {
                "start_of_day": profile.time_preference.start_of_day,
                "end_of_day": profile.time_preference.end_of_day,
                "deep_work_window": profile.time_preference.deep_work_window,
                "shallow_work_window": profile.time_preference.shallow_work_window
            },
            "meeting_preference": {
                "stacking_style": profile.meeting_preference.stacking_style,
                "max_back_to_back": profile.meeting_preference.max_back_to_back,
                "buffer_time": profile.meeting_preference.buffer_time,
                "preferred_days": profile.meeting_preference.preferred_days
            },
            "conflict_resolution": {
                "strategy": profile.conflict_resolution.strategy,
                "cancellation_threshold": profile.conflict_resolution.cancellation_threshold,
                "reschedule_preference": profile.conflict_resolution.reschedule_preference
            },
            "scenario_preferences": scenario_summary,
            "explicit_rules": profile.explicit_rules,
            "confidence_scores": profile.confidence_scores,
            "updated_at": profile.updated_at.isoformat()
        }

    def apply_updates(
        self,
        user_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        应用来自 Observer 的决策偏好更新

        Args:
            user_id: 用户ID
            updates: 更新字典，包含：
                - scenarios: 场景偏好更新
                - explicit_rules: 显式规则更新
                - time_preference: 时间偏好更新
                - meeting_preference: 会议偏好更新
                - conflict_resolution: 冲突解决偏好更新

        Returns:
            是否成功应用
        """
        profile = self.get_or_create_profile(user_id)

        # 更新场景偏好
        scenarios = updates.get("scenarios", {})
        for scenario_type, data in scenarios.items():
            action = data.get("action")
            confidence = data.get("confidence", 0.5)
            profile.update_scenario_preference(scenario_type, action, confidence)

        # 更新显式规则
        rules = updates.get("explicit_rules", [])
        for rule in rules:
            profile.add_explicit_rule(rule)

        # 更新时间偏好
        time_pref = updates.get("time_preference", {})
        if time_pref:
            for key, value in time_pref.items():
                if hasattr(profile.time_preference, key) and value is not None:
                    setattr(profile.time_preference, key, value)

        # 更新会议偏好
        meeting_pref = updates.get("meeting_preference", {})
        if meeting_pref:
            for key, value in meeting_pref.items():
                if hasattr(profile.meeting_preference, key) and value is not None:
                    setattr(profile.meeting_preference, key, value)

        # 更新冲突解决偏好
        conflict_pref = updates.get("conflict_resolution", {})
        if conflict_pref:
            for key, value in conflict_pref.items():
                if hasattr(profile.conflict_resolution, key) and value is not None:
                    setattr(profile.conflict_resolution, key, value)

        # 保存
        return self.save_profile(user_id, profile)


# 全局服务实例
decision_profile_service = DecisionProfileService()
