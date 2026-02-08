"""
Notification Settings Schema - 用户通知设置

用于前端提交和返回通知偏好配置
"""
from typing import Optional
from pydantic import BaseModel, Field


class NotificationSettings(BaseModel):
    """用户通知设置"""
    
    # 作息时间配置
    wake_time: str = Field(
        default="08:00",
        description="起床时间 (HH:MM 格式)",
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    sleep_time: str = Field(
        default="22:00",
        description="睡觉时间 (HH:MM 格式)",
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
    )
    
    # 各类通知开关
    morning_briefing_enabled: bool = Field(
        default=True,
        description="早安简报通知"
    )
    afternoon_checkin_enabled: bool = Field(
        default=True,
        description="午间检查通知"
    )
    evening_switch_enabled: bool = Field(
        default=True,
        description="晚间切换通知"
    )
    closing_ritual_enabled: bool = Field(
        default=True,
        description="睡前仪式通知"
    )
    event_reminders_enabled: bool = Field(
        default=True,
        description="日程提醒通知"
    )
    
    # 提前提醒时间（分钟）
    event_reminder_minutes: int = Field(
        default=15,
        ge=0,
        le=120,
        description="日程提前提醒时间（分钟，0-120）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "wake_time": "08:00",
                "sleep_time": "22:00",
                "morning_briefing_enabled": True,
                "afternoon_checkin_enabled": True,
                "evening_switch_enabled": True,
                "closing_ritual_enabled": True,
                "event_reminders_enabled": True,
                "event_reminder_minutes": 15
            }
        }

    @classmethod
    def from_preferences(cls, preferences: dict) -> "NotificationSettings":
        """从 UserProfile.preferences 字典创建"""
        return cls(
            wake_time=preferences.get("wake_time", "08:00"),
            sleep_time=preferences.get("sleep_time", "22:00"),
            morning_briefing_enabled=preferences.get("morning_briefing_enabled", True),
            afternoon_checkin_enabled=preferences.get("afternoon_checkin_enabled", True),
            evening_switch_enabled=preferences.get("evening_switch_enabled", True),
            closing_ritual_enabled=preferences.get("closing_ritual_enabled", True),
            event_reminders_enabled=preferences.get("event_reminders_enabled", True),
            event_reminder_minutes=preferences.get("event_reminder_minutes", 15),
        )

    def to_preferences_dict(self) -> dict:
        """转换为可合并到 UserProfile.preferences 的字典"""
        return {
            "wake_time": self.wake_time,
            "sleep_time": self.sleep_time,
            "morning_briefing_enabled": self.morning_briefing_enabled,
            "afternoon_checkin_enabled": self.afternoon_checkin_enabled,
            "evening_switch_enabled": self.evening_switch_enabled,
            "closing_ritual_enabled": self.closing_ritual_enabled,
            "event_reminders_enabled": self.event_reminders_enabled,
            "event_reminder_minutes": self.event_reminder_minutes,
        }
