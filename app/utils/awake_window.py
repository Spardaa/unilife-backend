"""
Awake Window Checker - 清醒窗口检查器

用于判断当前时间是否在用户的清醒时间窗口内，
决定是否应该发送通知。
"""
from datetime import datetime, time
from typing import Optional


class AwakeWindowChecker:
    """
    清醒窗口检查器
    
    根据用户设定的起床时间和睡觉时间，判断当前是否适合发送通知。
    特殊规则：
    - 早安简报（morning_briefing）作为唤醒信号，无论是否清醒都发送
    - 其他通知类型只在清醒窗口内发送
    """
    
    # 强制发送的通知类型（不受清醒窗口限制）
    FORCED_NOTIFICATION_TYPES = {"morning_briefing"}
    
    def __init__(self, wake_time: str = "08:00", sleep_time: str = "22:00"):
        """
        初始化清醒窗口检查器
        
        Args:
            wake_time: 起床时间，格式 HH:MM
            sleep_time: 睡觉时间，格式 HH:MM
        """
        self.wake_time = self._parse_time(wake_time)
        self.sleep_time = self._parse_time(sleep_time)
    
    def _parse_time(self, time_str: str) -> time:
        """
        解析 HH:MM 格式时间字符串
        
        Args:
            time_str: 时间字符串，格式 HH:MM
            
        Returns:
            time 对象
        """
        try:
            parts = time_str.split(":")
            return time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            # 解析失败时返回默认值
            return time(8, 0)
    
    def is_awake(self, current_time: Optional[datetime] = None) -> bool:
        """
        判断当前是否在清醒窗口内
        
        规则：
        - 正常情况（wake_time < sleep_time）：wake_time <= current < sleep_time → 清醒
        - 跨夜情况（wake_time > sleep_time）：current >= wake_time OR current < sleep_time → 清醒
        
        Args:
            current_time: 当前时间，默认使用系统时间
            
        Returns:
            True 表示用户可能清醒，False 表示用户可能在睡觉
        """
        if current_time is None:
            current_time = datetime.now()
        
        current = current_time.time()
        
        if self.wake_time <= self.sleep_time:
            # 正常情况：如 08:00 ~ 22:00
            return self.wake_time <= current < self.sleep_time
        else:
            # 跨夜情况：如 10:00 ~ 02:00（夜猫子作息）
            return current >= self.wake_time or current < self.sleep_time
    
    def should_send_notification(
        self, 
        notification_type: str,
        current_time: Optional[datetime] = None
    ) -> bool:
        """
        判断是否应该发送指定类型的通知
        
        特殊规则：
        - morning_briefing 类型作为唤醒信号，无论是否清醒都发送
        - 其他类型只在清醒窗口内发送
        
        Args:
            notification_type: 通知类型
            current_time: 当前时间，默认使用系统时间
            
        Returns:
            True 表示应该发送，False 表示应该静默
        """
        # 强制发送的通知类型
        if notification_type in self.FORCED_NOTIFICATION_TYPES:
            return True
        
        return self.is_awake(current_time)
    
    def get_next_wake_time(self, current_time: Optional[datetime] = None) -> datetime:
        """
        获取下一个起床时间
        
        Args:
            current_time: 当前时间，默认使用系统时间
            
        Returns:
            下一个起床时间的 datetime 对象
        """
        if current_time is None:
            current_time = datetime.now()
        
        today_wake = datetime.combine(current_time.date(), self.wake_time)
        
        if current_time.time() < self.wake_time:
            return today_wake
        else:
            # 明天的起床时间
            from datetime import timedelta
            return today_wake + timedelta(days=1)
    
    def get_closing_ritual_time(self, current_time: Optional[datetime] = None, advance_minutes: int = 15) -> datetime:
        """
        获取睡前仪式触发时间（睡觉时间前 N 分钟）
        
        Args:
            current_time: 当前时间
            advance_minutes: 提前多少分钟
            
        Returns:
            睡前仪式触发时间
        """
        if current_time is None:
            current_time = datetime.now()
        
        from datetime import timedelta
        
        today_sleep = datetime.combine(current_time.date(), self.sleep_time)
        ritual_time = today_sleep - timedelta(minutes=advance_minutes)
        
        # 如果已过今天的仪式时间，返回明天的
        if current_time >= ritual_time:
            ritual_time += timedelta(days=1)
        
        return ritual_time


def get_user_awake_checker(preferences: dict) -> AwakeWindowChecker:
    """
    从用户偏好字典创建清醒窗口检查器
    
    Args:
        preferences: UserProfile.preferences 字典
        
    Returns:
        配置好的 AwakeWindowChecker 实例
    """
    return AwakeWindowChecker(
        wake_time=preferences.get("wake_time", "08:00"),
        sleep_time=preferences.get("sleep_time", "22:00")
    )
