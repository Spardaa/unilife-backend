"""
EnergyAgent - Energy management and scheduling optimization
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from typing import Tuple

from app.services.db import db_service
from app.models.user import User, EnergyProfile
from app.models.event import Event, EventStatus, EnergyLevel, EventType


class EnergyAgent:
    """
    Agent responsible for energy calculation, fatigue detection, and scheduling optimization
    """

    def __init__(self):
        self.db = db_service

    async def check_energy(self, user_id: str) -> Dict[str, Any]:
        """
        Check current energy status for user

        Args:
            user_id: User ID

        Returns:
            Energy status with level, score, and recommendations
        """
        # Get user data
        user_data = await self.db.get_user(user_id)

        if not user_data:
            return {
                "energy_level": "MEDIUM",
                "energy_score": 70,
                "message": "获取用户信息失败。"
            }

        current_energy = user_data.get("current_energy", 100)

        # Determine energy level
        energy_level = self._get_energy_level(current_energy)

        # Generate recommendations based on current state
        recommendations = self._generate_recommendations(user_data, current_energy)

        return {
            "energy_level": energy_level.value,
            "energy_score": current_energy,
            "message": self._generate_energy_message(energy_level, current_energy),
            "recommendations": recommendations
        }

    async def suggest_schedule(
        self,
        user_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        floating_events_only: bool = True
    ) -> Dict[str, Any]:
        """
        Suggest optimal schedule based on energy profile

        Args:
            user_id: User ID
            start_time: Start time for scheduling window
            end_time: End time for scheduling window
            floating_events_only: Only suggest for floating events

        Returns:
            Suggested schedule with energy-optimized timing
        """
        # Get user data
        user_data = await self.db.get_user(user_id)

        if not user_data:
            return {
                "success": False,
                "message": "获取用户信息失败。",
                "schedule": []
            }

        # Get user's energy profile
        energy_profile = EnergyProfile(**user_data.get("energy_profile", {}))

        # Get events to schedule
        filters = {"status": EventStatus.PENDING.value}
        if floating_events_only:
            filters["event_type"] = EventType.FLOATING.value

        events = await self.db.get_events(user_id, filters=filters, limit=50)

        if not events:
            return {
                "success": True,
                "message": "没有需要安排的事件。",
                "schedule": []
            }

        # Filter events that have no time set
        floating_events = [e for e in events if not e.get("start_time")]

        if not floating_events:
            return {
                "success": True,
                "message": "所有事件都已有时间安排。",
                "schedule": []
            }

        # Get existing events for time slot availability
        all_events = await self.db.get_events(user_id, limit=1000)

        # Generate schedule suggestions
        suggestions = self._generate_schedule_suggestions(
            floating_events=floating_events,
            existing_events=all_events,
            energy_profile=energy_profile,
            start_time=start_time or datetime.now(),
            end_time=end_time or (datetime.now() + timedelta(days=7))
        )

        # Format response
        schedule_summary = self._format_schedule_summary(suggestions)

        return {
            "success": True,
            "message": schedule_summary,
            "schedule": suggestions
        }

    async def detect_fatigue(self, user_id: str) -> Dict[str, Any]:
        """
        Detect if user is fatigued based on recent activity

        Args:
            user_id: User ID

        Returns:
            Fatigue detection result with warning level and message
        """
        # Get user data
        user_data = await self.db.get_user(user_id)

        if not user_data:
            return {
                "fatigue_level": "NONE",
                "message": "无法检测疲劳状态。"
            }

        current_energy = user_data.get("current_energy", 100)
        fatigue_level = self._get_fatigue_level(current_energy)

        if fatigue_level != "NONE":
            warning_message = self._generate_fatigue_warning(fatigue_level, current_energy)
            return {
                "fatigue_level": fatigue_level,
                "current_energy": current_energy,
                "message": warning_message,
                "recommendations": [
                    "建议休息一下",
                    "可以做一些轻松的任务",
                    "避免安排高强度的深度工作"
                ]
            }

        return {
            "fatigue_level": "NONE",
            "current_energy": current_energy,
            "message": "当前状态良好，可以继续工作。"
        }

    async def update_user_energy(
        self,
        user_id: str,
        delta: int,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update user's current energy value

        Args:
            user_id: User ID
            delta: Energy change (positive or negative)
            reason: Reason for energy change

        Returns:
            Updated energy status
        """
        user_data = await self.db.get_user(user_id)

        if not user_data:
            return {
                "success": False,
                "message": "用户不存在。"
            }

        current_energy = user_data.get("current_energy", 100)
        new_energy = max(0, min(100, current_energy + delta))

        # Update user energy in database
        await self.db.update_user(user_id, {"current_energy": new_energy})

        # Generate response
        change_desc = "恢复" if delta > 0 else "消耗"
        return {
            "success": True,
            "previous_energy": current_energy,
            "current_energy": new_energy,
            "delta": delta,
            "reason": reason,
            "message": f"精力{change_desc}了 {abs(delta)} 点，当前为 {new_energy}。"
        }

    # ============ Helper Methods ============

    def _get_energy_level(self, energy_score: int) -> EnergyLevel:
        """Convert energy score to energy level"""
        if energy_score >= 70:
            return EnergyLevel.HIGH
        elif energy_score >= 40:
            return EnergyLevel.MEDIUM
        else:
            return EnergyLevel.LOW

    def _get_fatigue_level(self, energy_score: int) -> str:
        """Determine fatigue level based on energy score"""
        if energy_score < 20:
            return "SEVERE"
        elif energy_score < 40:
            return "MODERATE"
        elif energy_score < 60:
            return "MILD"
        else:
            return "NONE"

    def _generate_energy_message(self, energy_level: EnergyLevel, energy_score: int) -> str:
        """Generate natural language energy status message"""
        messages = {
            EnergyLevel.HIGH: [
                "你现在的状态很棒！是处理高强度任务的好时机。",
                "精力充沛，可以挑战一些有难度的任务。",
                "状态非常好！适合安排重要的深度工作。"
            ],
            EnergyLevel.MEDIUM: [
                "状态还不错，可以处理一些常规任务。",
                "精力尚可，适合安排中等难度的工作。",
                "你的状态平稳，可以按计划进行。"
            ],
            EnergyLevel.LOW: [
                "你现在可能需要休息一下，状态不太理想。",
                "精力有些不足，建议处理一些轻松的任务。",
                "你可能有些疲惫，注意适当休息。"
            ]
        }

        import random
        return random.choice(messages.get(energy_level, ["状态正常。"]))

    def _generate_recommendations(self, user_data: Dict[str, Any], current_energy: int) -> List[str]:
        """Generate recommendations based on current energy state"""
        recommendations = []

        if current_energy < 30:
            recommendations.append("建议立即休息")
            recommendations.append("避免安排任何重要任务")
            recommendations.append("可以喝杯咖啡或小憩一下")
        elif current_energy < 50:
            recommendations.append("优先处理紧急但简单的任务")
            recommendations.append("避免进行深度工作")
            recommendations.append("适当安排休息时间")
        elif current_energy > 80:
            recommendations.append("适合安排重要的深度工作")
            recommendations.append("可以处理复杂任务")
            recommendations.append("这是高效工作的好时机")
        else:
            recommendations.append("按计划进行即可")
            recommendations.append("保持当前工作节奏")

        return recommendations

    def _generate_schedule_suggestions(
        self,
        floating_events: List[Dict[str, Any]],
        existing_events: List[Dict[str, Any]],
        energy_profile: EnergyProfile,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Generate schedule suggestions using E-U (Energy-Urgency) model

        Args:
            floating_events: Events that need scheduling
            existing_events: Already scheduled events
            energy_profile: User's energy profile
            start_time: Scheduling window start
            end_time: Scheduling window end

        Returns:
            List of scheduled events with suggested times
        """
        suggestions = []

        # Sort floating events by urgency and importance
        sorted_events = sorted(
            floating_events,
            key=lambda e: (-e.get("urgency", 0), -e.get("importance", 0))
        )

        # Build time slot availability map
        time_slots = self._build_time_slots(
            existing_events=existing_events,
            start_time=start_time,
            end_time=end_time,
            working_hours_start=9,
            working_hours_end=18
        )

        # Schedule each event
        for event in sorted_events:
            suggested_time = self._find_best_time_slot(
                event=event,
                time_slots=time_slots,
                energy_profile=energy_profile
            )

            if suggested_time:
                suggestions.append({
                    "event_id": event["id"],
                    "event_title": event["title"],
                    "suggested_start_time": suggested_time[0].isoformat(),
                    "suggested_end_time": suggested_time[1].isoformat(),
                    "reason": self._explain_time_choice(suggested_time, energy_profile)
                })

        return suggestions

    def _build_time_slots(
        self,
        existing_events: List[Dict[str, Any]],
        start_time: datetime,
        end_time: datetime,
        working_hours_start: int = 9,
        working_hours_end: int = 18
    ) -> List[Tuple[datetime, datetime]]:
        """
        Build available time slots considering existing events and working hours

        Returns:
            List of (start, end) time tuples
        """
        slots = []

        # Generate slots for each day in range
        current = start_time.replace(hour=working_hours_start, minute=0, second=0, microsecond=0)

        while current < end_time:
            day_end = current.replace(hour=working_hours_end, minute=0)

            # Filter events for this day
            day_events = [
                e for e in existing_events
                if e.get("start_time") and datetime.fromisoformat(e["start_time"]).date() == current.date()
            ]

            # Sort events by start time
            day_events.sort(key=lambda e: datetime.fromisoformat(e["start_time"]))

            # Build slots between events
            slot_start = current

            for event in day_events:
                event_start = datetime.fromisoformat(event["start_time"])
                event_end = datetime.fromisoformat(event["end_time"]) if event.get("end_time") else event_start

                # If there's a gap, add a slot
                if event_start > slot_start:
                    slots.append((slot_start, event_start))

                slot_start = event_end

            # Add slot after last event
            if slot_start < day_end:
                slots.append((slot_start, day_end))

            # Move to next day
            current = (current + timedelta(days=1)).replace(hour=working_hours_start, minute=0)

        return slots

    def _find_best_time_slot(
        self,
        event: Dict[str, Any],
        time_slots: List[Tuple[datetime, datetime]],
        energy_profile: EnergyProfile
    ) -> Optional[Tuple[datetime, datetime]]:
        """
        Find the best time slot for an event based on energy requirements

        Returns:
            (start_time, end_time) tuple or None
        """
        event_energy = event.get("energy_required", EnergyLevel.MEDIUM.value)
        duration = event.get("duration", 60)

        # Map energy level to desired energy score
        target_energy = {
            EnergyLevel.HIGH.value: 70,
            EnergyLevel.MEDIUM.value: 50,
            EnergyLevel.LOW.value: 30
        }.get(event_energy, 50)

        best_slot = None
        best_score = -1

        for slot_start, slot_end in time_slots:
            slot_duration = (slot_end - slot_start).total_seconds() / 60

            if slot_duration < duration:
                continue  # Not enough time

            # Evaluate this slot
            avg_energy = self._calculate_slot_energy(slot_start, slot_end, energy_profile)

            # Score based on energy match and urgency
            urgency_bonus = event.get("urgency", 3) * 5
            energy_match_score = max(0, 100 - abs(avg_energy - target_energy))
            total_score = energy_match_score + urgency_bonus

            if total_score > best_score:
                best_score = total_score
                best_slot = (slot_start, slot_start + timedelta(minutes=duration))

        return best_slot

    def _calculate_slot_energy(
        self,
        start_time: datetime,
        end_time: datetime,
        energy_profile: EnergyProfile
    ) -> float:
        """
        Calculate average energy for a time slot

        Args:
            start_time: Slot start time
            end_time: Slot end time
            energy_profile: User's energy profile

        Returns:
            Average energy score
        """
        total_energy = 0
        count = 0

        current = start_time
        while current < end_time:
            hour = current.hour
            energy = energy_profile.get_energy_at_hour(hour)
            total_energy += energy
            count += 1
            current += timedelta(hours=1)

        return total_energy / count if count > 0 else 50

    def _explain_time_choice(
        self,
        time_slot: Tuple[datetime, datetime],
        energy_profile: EnergyProfile
    ) -> str:
        """Generate explanation for why a time was chosen"""
        start_time = time_slot[0]
        hour = start_time.hour
        energy = energy_profile.get_energy_at_hour(hour)

        if energy >= 70:
            return f"这个时段您的精力通常很充沛（约{energy}分），适合处理重要任务。"
        elif energy >= 50:
            return f"这个时段您的精力状态不错（约{energy}分），适合安排常规工作。"
        else:
            return f"这个时段相对轻松（约{energy}分），适合处理简单任务。"

    def _format_schedule_summary(self, suggestions: List[Dict[str, Any]]) -> str:
        """Format schedule suggestions for display"""
        if not suggestions:
            return "没有可安排的事件。"

        lines = ["以下是建议的安排："]
        for i, s in enumerate(suggestions, 1):
            start = datetime.fromisoformat(s["suggested_start_time"]).strftime("%m/%d %H:%M")
            end = datetime.fromisoformat(s["suggested_end_time"]).strftime("%H:%M")
            lines.append(f"{i}. {s['event_title']} - {start} 至 {end}")
            lines.append(f"   理由: {s['reason']}")

        return "\n".join(lines)

    def _generate_fatigue_warning(self, fatigue_level: str, current_energy: int) -> str:
        """Generate fatigue warning message"""
        warnings = {
            "SEVERE": f"警告：您的精力已严重不足（{current_energy}/100），强烈建议立即休息！",
            "MODERATE": f"注意：您感到有些疲惫（{current_energy}/100），建议适当休息后再继续工作。",
            "MILD": f"提醒：您的精力略有下降（{current_energy}/100），可以安排短暂休息。"
        }

        return warnings.get(fatigue_level, "")


# Global EnergyAgent instance
energy_agent = EnergyAgent()
