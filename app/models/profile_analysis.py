"""
Profile Analysis Log Model - 画像分析日志模型
记录画像分析的执行历史
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid
from enum import Enum


class JobType(str, Enum):
    """分析任务类型"""
    DAILY = "daily"
    WEEKLY = "weekly"


class AnalysisStatus(str, Enum):
    """分析状态"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ProfileAnalysisLog(BaseModel):
    """画像分析日志"""

    # Primary key
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Log ID")

    # User reference
    user_id: str = Field(..., description="User ID")

    # Job information
    job_type: JobType = Field(..., description="任务类型: daily | weekly")
    analysis_period_start: Optional[datetime] = Field(default=None, description="分析周期开始时间")
    analysis_period_end: Optional[datetime] = Field(default=None, description="分析周期结束时间")

    # Analysis results
    diary_ids_analyzed: List[str] = Field(default_factory=list, description="分析的日记ID列表")
    profile_changes: Dict[str, Any] = Field(default_factory=dict, description="画像变更内容")
    confidence_delta: Dict[str, float] = Field(default_factory=dict, description="置信度变化")

    # Status tracking
    status: AnalysisStatus = Field(default=AnalysisStatus.PENDING, description="分析状态")
    error_message: Optional[str] = Field(default=None, description="错误信息")

    # Timestamps
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user-123",
                "job_type": "daily",
                "analysis_period_start": "2026-01-23T00:00:00",
                "analysis_period_end": "2026-01-23T23:59:59",
                "diary_ids_analyzed": ["diary-1", "diary-2"],
                "profile_changes": {
                    "relationships": {"status": "dating", "from": "unknown"},
                    "habits": {"sleep_schedule": "early_bird", "from": "unknown"}
                },
                "confidence_delta": {
                    "relationships": 0.3,
                    "habits": 0.4
                },
                "status": "completed",
                "started_at": "2026-01-24T03:15:00",
                "completed_at": "2026-01-24T03:15:30"
            }
        }

    def to_dict(self) -> dict:
        """转换为字典（用于数据库存储）"""
        data = self.model_dump(mode='json')
        # 处理 datetime 类型
        for key in ['analysis_period_start', 'analysis_period_end', 'started_at', 'completed_at', 'created_at']:
            if data.get(key) and isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        # 处理 enum 类型
        if isinstance(data.get('job_type'), JobType):
            data['job_type'] = data['job_type'].value
        if isinstance(data.get('status'), AnalysisStatus):
            data['status'] = data['status'].value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ProfileAnalysisLog":
        """从字典创建"""
        # 处理 datetime 字符串
        for key in ['analysis_period_start', 'analysis_period_end', 'started_at', 'completed_at', 'created_at']:
            if data.get(key) and isinstance(data[key], str):
                data[key] = datetime.fromisoformat(data[key])
        # 处理 enum 字符串
        if isinstance(data.get('job_type'), str):
            data['job_type'] = JobType(data['job_type'])
        if isinstance(data.get('status'), str):
            data['status'] = AnalysisStatus(data['status'])
        return cls(**data)


class ProfileEvolution(BaseModel):
    """画像演变记录"""
    date: str = Field(..., description="日期")
    job_type: str = Field(..., description="分析类型")
    changes: Dict[str, Any] = Field(..., description="变更内容")
    confidence_before: Dict[str, float] = Field(default_factory=dict, description="变更前置信度")
    confidence_after: Dict[str, float] = Field(default_factory=dict, description="变更后置信度")
