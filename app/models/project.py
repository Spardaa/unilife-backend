"""
Project Model - Database model for Life Projects (人生项目)

Life Projects represent long-term goals and areas of focus.
Tasks are associated with projects and classified as:
- Main Quest: Tier 0 projects OR projects in SPRINT mode
- Side Quest: Tier 1/2 projects in NORMAL mode
- Daily Quest: Orphan tasks (no project association)
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class ProjectType(str, Enum):
    """Project types"""
    FINITE = "FINITE"      # 登山型 - has clear endpoint (融资、考试)
    INFINITE = "INFINITE"  # 长跑型 - ongoing habits (健身、学英语)


class ProjectMode(str, Enum):
    """Project modes"""
    NORMAL = "NORMAL"      # 平稳模式
    SPRINT = "SPRINT"      # 冲刺模式 - all tasks promoted to Main Quest


class EnergyType(str, Enum):
    """Primary energy type consumed by project tasks"""
    MENTAL = "MENTAL"      # 偏脑力
    PHYSICAL = "PHYSICAL"  # 偏体力
    BALANCED = "BALANCED"  # 平衡


class QuestType(str, Enum):
    """Quest type - dynamically derived from project"""
    MAIN = "MAIN"          # 主线任务 - critical path
    SIDE = "SIDE"          # 支线任务 - enhancement
    DAILY = "DAILY"        # 日常任务 - maintenance


class Project(BaseModel):
    """Life Project model
    
    Represents a long-term goal or area of focus.
    Replaces and enhances the old habit system with RPG-style quest classification.
    """
    
    # Primary key
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Project UUID")
    
    # User reference
    user_id: str = Field(..., description="User ID")
    
    # Basic information
    title: str = Field(..., description="Project title, e.g. '考研', '健身'")
    description: Optional[str] = Field(None, description="Detailed description")
    
    # Project classification
    type: ProjectType = Field(default=ProjectType.FINITE, description="FINITE (登山型) or INFINITE (长跑型)")
    base_tier: int = Field(default=1, ge=0, le=2, description="Priority tier: 0=核心, 1=成长, 2=兴趣")
    current_mode: ProjectMode = Field(default=ProjectMode.NORMAL, description="NORMAL or SPRINT mode")
    
    # Energy characteristics
    energy_type: EnergyType = Field(default=EnergyType.BALANCED, description="Primary energy consumption type")
    
    # Target KPIs (for tracking progress, especially for INFINITE projects)
    target_kpi: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Target metrics, e.g. {'weekly_hours': 20, 'total_days': 21, 'completed_days': 0}"
    )
    
    # Status
    is_active: bool = Field(default=True, description="Whether project is active")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    # Statistics (computed/cached)
    total_tasks: int = Field(default=0, description="Total tasks in this project (Legacy - use one_off_tasks_total)")
    completed_tasks: int = Field(default=0, description="Completed tasks count (Legacy - use one_off_tasks_completed)")
    total_focus_minutes: int = Field(default=0, description="Total focus time spent")
    
    # Enhanced Statistics
    one_off_tasks_total: int = Field(default=0, description="Total one-off tasks")
    one_off_tasks_completed: int = Field(default=0, description="Completed one-off tasks")
    routine_stats: Dict[str, int] = Field(
        default_factory=lambda: {"total_executions": 0, "completed_executions": 0},
        description="Routine execution stats"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user-123",
                "title": "考研",
                "description": "2026年研究生入学考试准备",
                "type": "FINITE",
                "base_tier": 0,
                "current_mode": "SPRINT",
                "energy_type": "MENTAL",
                "target_kpi": {
                    "target_date": "2026-12-25",
                    "weekly_hours": 30
                },
                "is_active": True,
                "total_tasks": 15,
                "completed_tasks": 8,
                "total_focus_minutes": 1200
            }
        }
    
    def to_dict(self) -> dict:
        """Convert model to dictionary for database storage"""
        return self.model_dump(mode='json')
    
    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        """Create Project from dictionary (from database)"""
        return cls(**data)
    
    @property
    def is_main_quest_source(self) -> bool:
        """Check if this project generates Main Quests"""
        return self.base_tier == 0 or self.current_mode == ProjectMode.SPRINT
    
    def compute_quest_type(self) -> QuestType:
        """Compute the quest type for tasks in this project"""
        if self.base_tier == 0 or self.current_mode == ProjectMode.SPRINT:
            return QuestType.MAIN
        else:
            return QuestType.SIDE


def compute_quest_type_for_event(event_project_id: Optional[str], projects_cache: Dict[str, Project]) -> QuestType:
    """
    Compute quest type for an event based on its project association
    
    Args:
        event_project_id: The project_id of the event (None for orphan tasks)
        projects_cache: Dict mapping project_id to Project objects
        
    Returns:
        QuestType - MAIN, SIDE, or DAILY
    """
    if event_project_id is None:
        return QuestType.DAILY
    
    project = projects_cache.get(event_project_id)
    if project is None:
        return QuestType.DAILY
    
    return project.compute_quest_type()
