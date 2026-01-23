"""
Profile Refinement Service - 用户画像精炼服务
协调日记分析和画像更新的流程
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import json

from app.models.profile_analysis import ProfileAnalysisLog, JobType, AnalysisStatus
from app.models.diary import UserDiary
from app.services.profile_service import profile_service
from app.services.diary_service import diary_service
from app.config import settings


class ProfileRefinementService:
    """用户画像精炼服务"""

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

    def create_analysis_log(
        self,
        user_id: str,
        job_type: JobType,
        period_start: datetime,
        period_end: datetime
    ) -> ProfileAnalysisLog:
        """创建分析日志"""
        log = ProfileAnalysisLog(
            user_id=user_id,
            job_type=job_type,
            analysis_period_start=period_start,
            analysis_period_end=period_end
        )

        db = self.get_session()
        try:
            log_data = json.dumps(log.to_dict())
            db.execute(
                text("""INSERT INTO profile_analysis_logs
                       (id, user_id, job_type, analysis_period_start, analysis_period_end,
                        diary_ids_analyzed, profile_changes, confidence_delta, status, created_at)
                       VALUES (:id, :user_id, :job_type, :period_start, :period_end,
                               :diary_ids, :changes, :delta, :status, :created_at)"""),
                {
                    "id": log.id,
                    "user_id": user_id,
                    "job_type": job_type.value,
                    "period_start": period_start.isoformat() if period_start else None,
                    "period_end": period_end.isoformat() if period_end else None,
                    "diary_ids": json.dumps([]),
                    "changes": json.dumps({}),
                    "delta": json.dumps({}),
                    "status": AnalysisStatus.PENDING.value,
                    "created_at": log.created_at.isoformat()
                }
            )
            db.commit()
            return log

        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def update_analysis_log(
        self,
        log_id: str,
        diary_ids: List[str] = None,
        profile_changes: Dict[str, Any] = None,
        confidence_delta: Dict[str, float] = None,
        status: AnalysisStatus = None,
        error_message: str = None
    ) -> bool:
        """更新分析日志"""
        db = self.get_session()
        try:
            updates = []
            params = {}

            if diary_ids is not None:
                updates.append("diary_ids_analyzed = :diary_ids")
                params["diary_ids"] = json.dumps(diary_ids)

            if profile_changes is not None:
                updates.append("profile_changes = :changes")
                params["changes"] = json.dumps(profile_changes)

            if confidence_delta is not None:
                updates.append("confidence_delta = :delta")
                params["delta"] = json.dumps(confidence_delta)

            if status is not None:
                updates.append("status = :status")
                params["status"] = status.value

            if error_message is not None:
                updates.append("error_message = :error")
                params["error"] = error_message

            if status == AnalysisStatus.COMPLETED:
                updates.append("completed_at = :completed_at")
                params["completed_at"] = datetime.utcnow().isoformat()

            if updates:
                params["log_id"] = log_id
                query = f"UPDATE profile_analysis_logs SET {', '.join(updates)} WHERE id = :log_id"
                db.execute(text(query), params)
                db.commit()
                return True

            return False

        except Exception as e:
            db.rollback()
            print(f"[Profile Refinement] Error updating log: {e}")
            return False
        finally:
            db.close()

    def get_analysis_logs(
        self,
        user_id: str,
        job_type: JobType = None,
        status: AnalysisStatus = None,
        limit: int = 20
    ) -> List[ProfileAnalysisLog]:
        """获取分析日志"""
        db = self.get_session()
        try:
            conditions = ["user_id = :user_id"]
            params = {"user_id": user_id}

            if job_type:
                conditions.append("job_type = :job_type")
                params["job_type"] = job_type.value

            if status:
                conditions.append("status = :status")
                params["status"] = status.value

            query = f"""SELECT log_data FROM profile_analysis_logs
                       WHERE {' AND '.join(conditions)}
                       ORDER BY created_at DESC
                       LIMIT :limit"""

            params["limit"] = limit

            results = db.execute(text(query), params).fetchall()

            logs = []
            for row in results:
                logs.append(ProfileAnalysisLog.from_dict(json.loads(row[0])))

            return logs

        except Exception as e:
            print(f"[Profile Refinement] Error getting logs: {e}")
            return []
        finally:
            db.close()

    def analyze_daily_profile(
        self,
        user_id: str,
        target_date: date
    ) -> ProfileAnalysisLog:
        """
        执行每日画像分析

        分析指定日期的日记，更新用户画像
        """
        # 计算分析周期
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())

        # 创建分析日志
        log = self.create_analysis_log(
            user_id=user_id,
            job_type=JobType.DAILY,
            period_start=start_datetime,
            period_end=end_datetime
        )

        try:
            # 标记为开始
            db = self.get_session()
            db.execute(
                text("UPDATE profile_analysis_logs SET started_at = :started, status = :status WHERE id = :log_id"),
                {"started": datetime.utcnow().isoformat(), "status": AnalysisStatus.PENDING.value, "log_id": log.id}
            )
            db.commit()
            db.close()

            # 获取当天日记
            diary = diary_service.get_diary_by_date(user_id, target_date)

            if not diary:
                # 没有日记，标记为完成但无变化
                self.update_analysis_log(
                    log.id,
                    diary_ids=[],
                    profile_changes={},
                    confidence_delta={},
                    status=AnalysisStatus.COMPLETED
                )
                log.status = AnalysisStatus.COMPLETED
                return log

            # 提取信号并更新画像
            changes, delta = self._apply_signals_to_profile(user_id, diary)

            # 更新日志
            self.update_analysis_log(
                log.id,
                diary_ids=[diary.id],
                profile_changes=changes,
                confidence_delta=delta,
                status=AnalysisStatus.COMPLETED
            )

            log.diary_ids_analyzed = [diary.id]
            log.profile_changes = changes
            log.confidence_delta = delta
            log.status = AnalysisStatus.COMPLETED

            return log

        except Exception as e:
            # 标记为失败
            self.update_analysis_log(
                log.id,
                status=AnalysisStatus.FAILED,
                error_message=str(e)
            )
            log.status = AnalysisStatus.FAILED
            log.error_message = str(e)
            raise e

    def analyze_weekly_profile(
        self,
        user_id: str,
        end_date: date = None
    ) -> ProfileAnalysisLog:
        """
        执行每周画像深度分析

        分析过去7天的日记，进行更全面的画像更新
        """
        if end_date is None:
            end_date = date.today()

        start_date = end_date - timedelta(days=6)

        # 计算分析周期
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        # 创建分析日志
        log = self.create_analysis_log(
            user_id=user_id,
            job_type=JobType.WEEKLY,
            period_start=start_datetime,
            period_end=end_datetime
        )

        try:
            # 标记为开始
            db = self.get_session()
            db.execute(
                text("UPDATE profile_analysis_logs SET started_at = :started, status = :status WHERE id = :log_id"),
                {"started": datetime.utcnow().isoformat(), "status": AnalysisStatus.PENDING.value, "log_id": log.id}
            )
            db.commit()
            db.close()

            # 获取过去7天的日记
            diaries = diary_service.get_diaries_by_period(user_id, start_date, end_date)

            if not diaries:
                # 没有日记，标记为完成但无变化
                self.update_analysis_log(
                    log.id,
                    diary_ids=[],
                    profile_changes={},
                    confidence_delta={},
                    status=AnalysisStatus.COMPLETED
                )
                log.status = AnalysisStatus.COMPLETED
                return log

            # 合并所有信号
            all_changes = {}
            all_delta = {}
            diary_ids = [d.id for d in diaries]

            for diary in diaries:
                changes, delta = self._apply_signals_to_profile(user_id, diary)

                # 合并变化
                for category, change in changes.items():
                    if category not in all_changes:
                        all_changes[category] = change
                    elif isinstance(change, dict):
                        all_changes[category].update(change)

                # 累加置信度变化
                for category, delta_val in delta.items():
                    all_delta[category] = all_delta.get(category, 0) + delta_val

            # 更新日志
            self.update_analysis_log(
                log.id,
                diary_ids=diary_ids,
                profile_changes=all_changes,
                confidence_delta=all_delta,
                status=AnalysisStatus.COMPLETED
            )

            log.diary_ids_analyzed = diary_ids
            log.profile_changes = all_changes
            log.confidence_delta = all_delta
            log.status = AnalysisStatus.COMPLETED

            return log

        except Exception as e:
            # 标记为失败
            self.update_analysis_log(
                log.id,
                status=AnalysisStatus.FAILED,
                error_message=str(e)
            )
            log.status = AnalysisStatus.FAILED
            log.error_message = str(e)
            raise e

    def _apply_signals_to_profile(
        self,
        user_id: str,
        diary: UserDiary
    ) -> tuple[Dict[str, Any], Dict[str, float]]:
        """
        将日记中的信号应用到用户画像

        Returns:
            (changes, delta): 变更内容和置信度变化
        """
        from app.models.event import ExtractedPoint

        # 获取当前画像
        profile = profile_service.get_or_create_profile(user_id)

        # 记录变更前的置信度
        confidence_before = {
            "relationships": profile.relationships.confidence,
            "identity": profile.identity.confidence,
        }

        # 将 extracted_signals 转换为 ExtractedPoint 格式
        points = []
        for signal in diary.extracted_signals:
            point = ExtractedPoint(
                type=signal.type,
                content=signal.value,
                confidence=signal.confidence,
                evidence=[signal.evidence] if signal.evidence else []
            )
            points.append(point.model_dump())

        # 应用更新
        profile.update_from_points(points)

        # 保存更新后的画像
        profile_service.save_profile(user_id, profile)

        # 计算变更
        confidence_after = {
            "relationships": profile.relationships.confidence,
            "identity": profile.identity.confidence,
        }

        delta = {
            category: confidence_after[category] - confidence_before[category]
            for category in confidence_before
        }

        # 构建变更描述
        changes = {}

        # 检查关系状态变化
        if profile.relationships.status != "unknown" and delta.get("relationships", 0) > 0:
            changes["relationships"] = {
                "status": profile.relationships.status,
                "from": "unknown",
                "confidence": profile.relationships.confidence
            }

        # 检查身份变化
        if profile.identity.occupation != "unknown" and delta.get("identity", 0) > 0:
            changes["identity"] = {
                "occupation": profile.identity.occupation,
                "industry": profile.identity.industry,
                "confidence": profile.identity.confidence
            }

        # 检查喜好变化
        if profile.preferences.activity_types:
            changes["preferences"] = {
                "activities": profile.preferences.activity_types[-3:],  # 最近添加的
                "social": profile.preferences.social_preference
            }

        # 检查习惯变化
        habit_changes = {}
        if profile.habits.sleep_schedule != "unknown":
            habit_changes["sleep"] = profile.habits.sleep_schedule
        if profile.habits.work_hours != "unknown":
            habit_changes["work_hours"] = profile.habits.work_hours
        if profile.habits.exercise_frequency != "unknown":
            habit_changes["exercise"] = profile.habits.exercise_frequency

        if habit_changes:
            changes["habits"] = habit_changes

        return changes, delta

    def get_profile_evolution(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """获取画像演变历史"""
        logs = self.get_analysis_logs(user_id, status=AnalysisStatus.COMPLETED, limit=limit)

        evolution = []
        for log in logs:
            if log.profile_changes:
                evolution.append({
                    "date": log.analysis_period_end.strftime("%Y-%m-%d") if log.analysis_period_end else log.created_at.strftime("%Y-%m-%d"),
                    "job_type": log.job_type.value,
                    "changes": log.profile_changes,
                    "confidence_delta": log.confidence_delta
                })

        return evolution

    def get_recent_analysis(
        self,
        user_id: str,
        job_type: JobType = None
    ) -> Optional[ProfileAnalysisLog]:
        """获取最近的分析记录"""
        logs = self.get_analysis_logs(user_id, job_type=job_type, limit=1)
        return logs[0] if logs else None


# 全局服务实例
profile_refinement_service = ProfileRefinementService()
