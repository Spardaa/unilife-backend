"""
Diaries API - User Observation Diaries API
用户观察日记 API 端点
"""
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.diary_service import diary_service
from app.agents.daily_diary_generator import daily_diary_generator
from app.services.profile_refinement_service import profile_refinement_service
from app.models.profile_analysis import JobType
from app.models.diary import DiaryStats


# Request/Response Schemas
class DiaryGenerateRequest(BaseModel):
    """手动触发日记生成请求"""
    user_id: str = Field(..., description="用户ID")
    target_date: Optional[str] = Field(default=None, description="目标日期 (YYYY-MM-DD)，默认为昨天")


class DiaryGenerateResponse(BaseModel):
    """日记生成响应"""
    success: bool
    skipped: bool = False
    reason: Optional[str] = None
    diary: Optional[Dict[str, Any]] = None


class DiaryResponse(BaseModel):
    """日记响应"""
    id: str
    user_id: str
    diary_date: str
    summary: str
    key_insights: Dict[str, Any]
    extracted_signals: List[Dict[str, Any]]
    conversation_count: int
    message_count: int
    tool_calls_count: int
    created_at: str


class DiariesListResponse(BaseModel):
    """日记列表响应"""
    diaries: List[DiaryResponse]
    total: int
    has_more: bool


class AnalyzeProfileRequest(BaseModel):
    """触发画像分析请求"""
    user_id: str = Field(..., description="用户ID")
    job_type: str = Field(default="daily", description="任务类型: daily | weekly")
    target_date: Optional[str] = Field(default=None, description="目标日期 (YYYY-MM-DD)，默认为今天/本周结束日")


class ProfileAnalysisResponse(BaseModel):
    """画像分析响应"""
    success: bool
    log_id: str
    job_type: str
    status: str
    profile_changes: Dict[str, Any] = Field(default_factory=dict)
    confidence_delta: Dict[str, float] = Field(default_factory=dict)
    error: Optional[str] = None


class ProfileEvolutionResponse(BaseModel):
    """画像演变响应"""
    evolution: List[Dict[str, Any]]


router = APIRouter()


@router.get("", response_model=DiariesListResponse)
async def list_diaries(
    user_id: str = Query(..., description="用户ID"),
    days: int = Query(default=7, ge=1, le=30, description="最近多少天"),
    limit: int = Query(default=30, ge=1, le=100, description="返回数量限制")
):
    """
    获取用户日记列表

    支持两种查询模式：
    1. 指定 days：获取最近 N 天的日记
    2. 指定 limit：获取最近 N 条日记（按日期倒序）
    """
    try:
        if days > 0:
            # 按日期范围查询
            diaries = diary_service.get_recent_diaries(user_id, days)
            # 获取总数（用于 has_more 判断）
            all_diaries = diary_service.get_all_diaries(user_id, limit=limit + 1)
            has_more = len(all_diaries) > len(diaries)
        else:
            # 按数量查询
            diaries = diary_service.get_all_diaries(user_id, limit=limit)
            has_more = len(diaries) == limit

        return DiariesListResponse(
            diaries=[_serialize_diary(d) for d in diaries],
            total=len(diaries),
            has_more=has_more
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list diaries: {str(e)}")


@router.get("/{date_str}", response_model=DiaryResponse)
async def get_diary_by_date(
    date_str: str,
    user_id: str = Query(..., description="用户ID")
):
    """
    获取指定日期的日记

    date_str 格式: YYYY-MM-DD
    """
    try:
        target_date = date.fromisoformat(date_str)
        diary = diary_service.get_diary_by_date(user_id, target_date)

        if not diary:
            raise HTTPException(status_code=404, detail="Diary not found")

        return _serialize_diary(diary)

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get diary: {str(e)}")


@router.get("/stats", response_model=DiaryStats)
async def get_diary_stats(
    user_id: str = Query(..., description="用户ID"),
    days: int = Query(default=30, ge=1, le=90, description="统计周期（天）")
):
    """
    获取日记统计信息
    """
    try:
        stats = diary_service.get_diary_stats(user_id, days)
        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/generate", response_model=DiaryGenerateResponse)
async def generate_diary(request: DiaryGenerateRequest):
    """
    手动触发指定日期的日记生成

    通常由定时任务自动执行，此接口用于手动触发或测试
    """
    try:
        # 确定目标日期
        if request.target_date:
            target_date = date.fromisoformat(request.target_date)
        else:
            # 默认为昨天
            target_date = date.today() - timedelta(days=1)

        # 检查日记是否已存在
        if diary_service.diary_exists(request.user_id, target_date):
            existing = diary_service.get_diary_by_date(request.user_id, target_date)
            return DiaryGenerateResponse(
                success=True,
                skipped=True,
                reason="Diary already exists for this date",
                diary=_serialize_diary(existing) if existing else None
            )

        # 生成日记
        result = await daily_diary_generator.generate_daily_diary(
            user_id=request.user_id,
            target_date=target_date
        )

        diary_data = None
        if result.get("diary"):
            diary_data = _serialize_diary(result["diary"])

        return DiaryGenerateResponse(
            success=result["success"],
            skipped=result.get("skipped", False),
            reason=result.get("reason"),
            diary=diary_data
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate diary: {str(e)}")


@router.post("/profile/analyze", response_model=ProfileAnalysisResponse)
async def analyze_profile(request: AnalyzeProfileRequest):
    """
    手动触发画像分析

    分析日记数据，更新用户画像
    """
    try:
        # 确定任务类型
        job_type = JobType.DAILY if request.job_type == "daily" else JobType.WEEKLY

        # 确定目标日期
        if request.target_date:
            target_date = date.fromisoformat(request.target_date)
        else:
            target_date = date.today()

        # 执行分析
        if job_type == JobType.DAILY:
            log = await profile_refinement_service.analyze_daily_profile(
                user_id=request.user_id,
                target_date=target_date
            )
        else:
            log = await profile_refinement_service.analyze_weekly_profile(
                user_id=request.user_id,
                end_date=target_date
            )

        return ProfileAnalysisResponse(
            success=log.status.value == "completed",
            log_id=log.id,
            job_type=log.job_type.value,
            status=log.status.value,
            profile_changes=log.profile_changes,
            confidence_delta=log.confidence_delta,
            error=log.error_message
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze profile: {str(e)}")


@router.get("/profile/evolution", response_model=ProfileEvolutionResponse)
async def get_profile_evolution(
    user_id: str = Query(..., description="用户ID"),
    limit: int = Query(default=20, ge=1, le=50, description="返回数量限制")
):
    """
    获取画像演变历史

    展示画像如何随着时间推移而变化
    """
    try:
        evolution = profile_refinement_service.get_profile_evolution(
            user_id=user_id,
            limit=limit
        )

        return ProfileEvolutionResponse(evolution=evolution)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get profile evolution: {str(e)}")


def _serialize_diary(diary) -> Dict[str, Any]:
    """序列化日记对象为响应格式"""
    return {
        "id": diary.id,
        "user_id": diary.user_id,
        "diary_date": diary.diary_date.isoformat() if isinstance(diary.diary_date, date) else diary.diary_date,
        "summary": diary.summary,
        "key_insights": diary.key_insights.model_dump() if hasattr(diary.key_insights, 'model_dump') else diary.key_insights,
        "extracted_signals": [
            s.model_dump() if hasattr(s, 'model_dump') else s
            for s in diary.extracted_signals
        ],
        "conversation_count": diary.conversation_count,
        "message_count": diary.message_count,
        "tool_calls_count": diary.tool_calls_count,
        "created_at": diary.created_at.isoformat() if isinstance(diary.created_at, datetime) else diary.created_at
    }
