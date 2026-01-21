"""
Routine Models - 长期重复日程的三层数据模型
Layer 1: Template（规则层）- 用户定义的重复模式
Layer 2: Instance（实例层）- 根据规则生成的具体实例
Layer 3: Execution（执行层）- 实际执行记录
Layer 4: Memory（记忆层）- 学习用户习惯
"""
from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, JSON, Text, ForeignKey, Index
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import uuid
from typing import Dict, Any, List, Optional

Base = declarative_base()


class RoutineTemplate(Base):
    """
    Routine 模板（规则层）
    定义长期重复事件的模式
    """
    __tablename__ = "routine_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)

    # 基本信息
    name = Column(String, nullable=False)  # 如："健身计划"
    description = Column(Text)  # 详细描述
    category = Column(String)  # 分类：fitness, study, work, etc.

    # 重复规则
    repeat_rule = Column(JSON, nullable=False)  # {
        # "frequency": "weekly",
        # "days": [1, 2, 3, 4, 5],  # 周一到五
        # "time": "18:00",
        # "end_date": "2026-12-31"  # 可选
    # }

    # 序列定义（可选）
    sequence = Column(JSON)  # ["胸", "肩", "背"] 或 None
    sequence_position = Column(Integer, default=0)  # 下次应该是序列中的哪个

    # 灵活性设置
    is_flexible = Column(Boolean, default=True)  # 是否允许灵活调整
    preferred_time_slots = Column(JSON)  # 偏好时间段 [{"start": "17:00", "end": "20:00"}]
    makeup_strategy = Column(String)  # 补偿策略：skip, reschedule, extend

    # 状态
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 统计
    total_instances = Column(Integer, default=0)  # 生成的实例总数
    completed_instances = Column(Integer, default=0)  # 已完成的实例数

    # 关联
    instances = relationship("RoutineInstance", back_populates="template", cascade="all, delete-orphan")
    memories = relationship("RoutineMemory", back_populates="template", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "repeat_rule": self.repeat_rule,
            "sequence": self.sequence,
            "sequence_position": self.sequence_position,
            "is_flexible": self.is_flexible,
            "preferred_time_slots": self.preferred_time_slots,
            "makeup_strategy": self.makeup_strategy,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "total_instances": self.total_instances,
            "completed_instances": self.completed_instances
        }


class RoutineInstance(Base):
    """
    Routine 实例（实例层）
    根据模板规则生成的具体某一天的日程
    """
    __tablename__ = "routine_instances"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String, ForeignKey("routine_templates.id"), index=True, nullable=False)

    # 时间信息
    scheduled_date = Column(String, index=True, nullable=False)  # "2026-01-21"
    scheduled_time = Column(String)  # "18:00"

    # 序列信息（如果有）
    sequence_item = Column(String)  # 这一次应该是"胸部训练"

    # 状态
    status = Column(String, default="pending")  # pending, completed, cancelled, rescheduled, skipped

    # 关联到 events 表（如果已经创建了普通事件）
    # 注意：不使用外键约束，因为 events 表在不同的 Base 中
    generated_event_id = Column(String)  # 存储 event ID 作为引用

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 执行记录（一对多）
    executions = relationship("RoutineExecution", back_populates="instance", cascade="all, delete-orphan")

    # 关联回模板
    template = relationship("RoutineTemplate", back_populates="instances")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "template_id": self.template_id,
            "scheduled_date": self.scheduled_date,
            "scheduled_time": self.scheduled_time,
            "sequence_item": self.sequence_item,
            "status": self.status,
            "generated_event_id": self.generated_event_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def to_event_format(self) -> Dict[str, Any]:
        """
        转换为类似 event 的格式（用于查询时显示）
        """
        # 避免 lazy loading，使用 template_id 而不是 template.name
        # 名称需要在调用方查询时加入
        return {
            "id": self.generated_event_id or self.id,
            "type": "routine_instance",
            "template_id": self.template_id,
            "title": f"Routine{f' - {self.sequence_item}' if self.sequence_item else ''}",  # 简化标题
            "date": self.scheduled_date,
            "time": self.scheduled_time,
            "sequence_item": self.sequence_item,
            "status": self.status,
            "is_routine": True,
            "routine_template_id": self.template_id,
            "routine_instance_id": self.id
        }


class RoutineExecution(Base):
    """
    Routine 执行记录（执行层）
    记录实例实际发生了什么
    """
    __tablename__ = "routine_executions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_id = Column(String, ForeignKey("routine_instances.id"), index=True, nullable=False)

    # 执行动作
    action = Column(String, nullable=False)  # completed, cancelled, rescheduled, skipped, modified

    # 实际执行信息
    actual_date = Column(String)  # 如果延后，记录实际执行的日期
    actual_time = Column(String)  # 如果改时间，记录实际时间

    # 原因和备注
    reason = Column(String)  # "急事"、"身体不适"等
    notes = Column(Text)  # 详细说明

    # 对序列的影响
    sequence_advanced = Column(Boolean, default=True)  # 这次执行后，序列是否前进

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联回实例
    instance = relationship("RoutineInstance", back_populates="executions")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "instance_id": self.instance_id,
            "action": self.action,
            "actual_date": self.actual_date,
            "actual_time": self.actual_time,
            "reason": self.reason,
            "notes": self.notes,
            "sequence_advanced": self.sequence_advanced,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class RoutineMemory(Base):
    """
    Routine 记忆（记忆层）
    记录用户的习惯和模式，用于智能建议
    """
    __tablename__ = "routine_memories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String, ForeignKey("routine_templates.id"), index=True, nullable=False)

    # 记忆类型
    memory_type = Column(String, nullable=False)  # skip_pattern, time_preference, sequence_adjustment, etc.

    # 记忆内容
    pattern = Column(JSON, nullable=False)  # {
        # "type": "经常周二取消",
        # "confidence": 0.8,
        # "sample_count": 5,
        # "suggestion": "是否要将周二从训练日中移除？"
    # }

    # 统计
    hit_count = Column(Integer, default=0)  # 这条记忆被匹配到的次数
    applied_count = Column(Integer, default=0)  # 这条记忆被应用的次数

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_triggered_at = Column(DateTime)  # 上次被触发的时间

    # 关联回模板
    template = relationship("RoutineTemplate", back_populates="memories")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "template_id": self.template_id,
            "memory_type": self.memory_type,
            "pattern": self.pattern,
            "hit_count": self.hit_count,
            "applied_count": self.applied_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_triggered_at": self.last_triggered_at.isoformat() if self.last_triggered_at else None
        }


# 创建索引
Index('idx_routine_templates_user_active', RoutineTemplate.user_id, RoutineTemplate.active)
Index('idx_routine_instances_template_date', RoutineInstance.template_id, RoutineInstance.scheduled_date)
Index('idx_routine_instances_date_status', RoutineInstance.scheduled_date, RoutineInstance.status)
Index('idx_routine_executions_instance', RoutineExecution.instance_id, RoutineExecution.created_at)
Index('idx_routine_memory_template_type', RoutineMemory.template_id, RoutineMemory.memory_type)
