"""
Virtual Instance Expansion Service

Expands recurring event templates into virtual instances within a specified date range.
Virtual instances are NOT persisted to database - they exist only for query results.

This service moves virtual expansion logic from iOS client to backend,
ensuring Agent and App use the same data source.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pytz import timezone
import calendar


class VirtualExpansionService:
    """Service for expanding recurring event templates into virtual instances"""

    def __init__(self):
        self.tz = timezone("Asia/Shanghai")

    def expand_templates(
        self,
        templates: List[Dict[str, Any]],
        real_instances: List[Dict[str, Any]],
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Expand templates into virtual instances within date range.

        Args:
            templates: List of template events (is_template=True)
            real_instances: List of real instances (already exist in DB)
            start_date: Range start (inclusive)
            end_date: Range end (inclusive)

        Returns:
            List of virtual instance dictionaries
        """
        virtual_instances = []

        # Build lookup for real instances: (template_id, date) -> instance
        real_lookup = {}
        for inst in real_instances:
            # Try parent_event_id first (from API), then parent_routine_id (from DB)
            template_id = inst.get("parent_event_id") or inst.get("parent_routine_id")
            event_date = inst.get("event_date")
            if template_id and event_date:
                # Normalize to date string for comparison
                if isinstance(event_date, datetime):
                    date_key = event_date.strftime("%Y-%m-%d")
                else:
                    # Handle ISO format strings (e.g., "2026-02-09T00:00:00")
                    date_str = str(event_date)
                    if "T" in date_str:
                        date_key = date_str.split("T")[0]
                    else:
                        date_key = date_str
                real_lookup[(template_id, date_key)] = True

        print(f"🔍 Real lookup: {len(real_lookup)} entries for {len(real_instances)} instances")

        for template in templates:
            pattern = template.get("repeat_pattern")
            if not pattern or isinstance(pattern, str):
                # Skip if pattern is missing or not a dict
                continue

            # Get occurrence dates
            occurrences = self._calculate_occurrences(
                template=template,
                start_date=start_date,
                end_date=end_date
            )

            for occ_date in occurrences:
                date_key = occ_date.strftime("%Y-%m-%d")
                template_id = template.get("id")

                # Skip if real instance exists
                if real_lookup.get((template_id, date_key)):
                    print(f"⏭️ Skipping virtual for {template_id} on {date_key}")
                    continue

                # Create virtual instance
                virtual_instance = self._create_virtual_instance(
                    template=template,
                    occurrence_date=occ_date
                )
                virtual_instances.append(virtual_instance)

        return virtual_instances

    def _calculate_occurrences(
        self,
        template: Dict[str, Any],
        start_date: datetime,
        end_date: datetime
    ) -> List[datetime]:
        """Calculate all occurrence dates for a template within range"""
        pattern = template.get("repeat_pattern", {})
        if isinstance(pattern, str):
            try:
                import json
                pattern = json.loads(pattern)
            except:
                return []

        pattern_type = pattern.get("type")

        if not pattern_type:
            return []

        occurrences = []

        # Ensure start_date and end_date are timezone-aware and in the target timezone
        if start_date.tzinfo is None:
            start_date = self.tz.localize(start_date)
        else:
            start_date = start_date.astimezone(self.tz)
            
        if end_date.tzinfo is None:
            end_date = self.tz.localize(end_date)
        else:
            end_date = end_date.astimezone(self.tz)

        # Get reference date (when the pattern started)
        original_start = template.get("event_date") or template.get("created_at")
        if isinstance(original_start, str):
            try:
                original_start = datetime.fromisoformat(original_start.replace('Z', '+00:00'))
            except:
                original_start = datetime.utcnow()

        # Ensure timezone awareness and normalization
        if original_start.tzinfo is None:
            original_start = self.tz.localize(original_start)
        else:
            original_start = original_start.astimezone(self.tz)

        # Ensure we don't generate before the event started
        effective_start = max(start_date, self._start_of_day(original_start))

        # Check pattern end date
        pattern_end = None
        if pattern.get("end_date"):
            try:
                pattern_end = datetime.fromisoformat(pattern["end_date"])
                if pattern_end.tzinfo is None:
                    pattern_end = self.tz.localize(pattern_end)
                else:
                    pattern_end = pattern_end.astimezone(self.tz)
                pattern_end = self._end_of_day(pattern_end)
            except:
                pass

        current = effective_start

        if pattern_type == "daily":
            while current <= end_date:
                if pattern_end and current > pattern_end:
                    break
                occurrences.append(current)
                current += timedelta(days=1)

        elif pattern_type == "weekly":
            # Same weekday each week
            target_weekday = original_start.weekday()
            current = effective_start
            while current <= end_date:
                if pattern_end and current > pattern_end:
                    break
                if current.weekday() == target_weekday:
                    occurrences.append(current)
                current += timedelta(days=1)

        elif pattern_type == "monthly":
            # Same day of each month
            target_day = original_start.day
            current = effective_start
            while current <= end_date:
                if pattern_end and current > pattern_end:
                    break
                if current.day == target_day:
                    occurrences.append(current)
                current += timedelta(days=1)

        elif pattern_type == "custom":
            # Check for interval_days support (every N days)
            interval_days = pattern.get("interval_days")
            if interval_days and interval_days > 1:
                # Every N days pattern
                current = effective_start
                while current <= end_date:
                    if pattern_end and current > pattern_end:
                        break
                    occurrences.append(current)
                    current += timedelta(days=interval_days)
            else:
                # Specific weekdays (existing logic)
                weekdays = pattern.get("weekdays", [])
                if weekdays:
                    current = effective_start
                    while current <= end_date:
                        if pattern_end and current > pattern_end:
                            break
                        if current.weekday() in weekdays:
                            occurrences.append(current)
                        current += timedelta(days=1)

        return occurrences

    def _create_virtual_instance(
        self,
        template: Dict[str, Any],
        occurrence_date: datetime
    ) -> Dict[str, Any]:
        """Create a virtual instance from template for a specific date"""
        pattern = template.get("repeat_pattern", {})
        if isinstance(pattern, str):
            try:
                import json
                pattern = json.loads(pattern)
            except:
                pattern = {}

        # Ensure occurrence_date is timezone-aware and normalized
        if occurrence_date.tzinfo is None:
            occurrence_date = self.tz.localize(occurrence_date)
        else:
            occurrence_date = occurrence_date.astimezone(self.tz)

        # Calculate start time from pattern
        start_time = None
        end_time = None

        time_str = pattern.get("time")
        if time_str:
            try:
                hour, minute = map(int, time_str.split(":"))
                start_time = occurrence_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

                # Calculate end time from duration
                duration = template.get("duration") or 30
                end_time = start_time + timedelta(minutes=duration)
            except:
                pass

        event_date = self._start_of_day(occurrence_date)

        return {
            "id": f"virtual_{template['id']}_{occurrence_date.strftime('%Y%m%d')}",
            "user_id": template.get("user_id"),
            "title": template.get("title"),
            "description": template.get("description"),
            "notes": template.get("notes"),
            "event_date": event_date,
            "start_time": start_time,
            "end_time": end_time,
            "duration": template.get("duration"),
            "status": "PENDING",
            "event_type": template.get("event_type", "schedule"),
            "category": template.get("category"),
            "tags": template.get("tags", []),
            "created_at": template.get("created_at", datetime.utcnow()),  # Use template's created_at
            "updated_at": datetime.utcnow(),  # Virtual instance time
            "completed_at": None,
            "started_at": None,
            "created_by": template.get("created_by", "system"),  # Use template's created_by
            "ai_confidence": template.get("ai_confidence", 1.0),  # Use template's confidence
            "ai_reasoning": template.get("ai_reasoning"),
            "time_period": template.get("time_period"),
            "repeat_pattern": pattern,  # Include repeat pattern for iOS repeat icon display
            "is_virtual": True,  # Mark as virtual
            "template_id": template.get("id"),
            "parent_event_id": template.get("id"),
            "is_template": False,
            "project_id": template.get("project_id"),
            # Inherit energy and habit fields from template
            "is_physically_demanding": template.get("is_physically_demanding", False),
            "is_mentally_demanding": template.get("is_mentally_demanding", False),
            "energy_consumption": template.get("energy_consumption"),
            "habit_interval": template.get("habit_interval"),
            "habit_completed_count": template.get("habit_completed_count", 0),  # Inherit from template
            "habit_total_count": template.get("habit_total_count", 21),
            "subtasks": template.get("subtasks", []),
            "routine_batch_id": template.get("routine_batch_id"),
        }

    def _start_of_day(self, dt: datetime) -> datetime:
        """Get start of day in configured timezone"""
        if dt.tzinfo is None:
            dt = self.tz.localize(dt)
        else:
            dt = dt.astimezone(self.tz)
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)

    def _end_of_day(self, dt: datetime) -> datetime:
        """Get end of day in configured timezone"""
        if dt.tzinfo is None:
            dt = self.tz.localize(dt)
        else:
            dt = dt.astimezone(self.tz)
        return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


# Singleton instance
virtual_expansion_service = VirtualExpansionService()
