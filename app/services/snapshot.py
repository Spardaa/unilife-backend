"""
Snapshot Service - Manages schedule snapshots and revert functionality
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.db import db_service
from app.models.snapshot import Snapshot, EventChange


class SnapshotManager:
    """
    Service for managing schedule snapshots and revert functionality
    """

    def __init__(self):
        self.db = db_service
        self.max_snapshots = 10  # Keep only the 10 most recent snapshots

    async def create_snapshot(
        self,
        user_id: str,
        trigger_message: str,
        changes: List[EventChange]
    ) -> Snapshot:
        """
        Create a snapshot for schedule changes

        Args:
            user_id: User ID
            trigger_message: Message that triggered this change
            changes: List of event changes

        Returns:
            Created snapshot
        """
        snapshot_data = {
            "user_id": user_id,
            "trigger_message": trigger_message,
            "trigger_time": datetime.utcnow(),
            "changes": [change.model_dump(mode='json') for change in changes],
            "is_reverted": False,
            "reverted_at": None,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow()  # Default 30 days in Snapshot model
        }

        # Create snapshot in database
        result = await self.db.create_snapshot(snapshot_data)

        # Clean up old snapshots (keep only max_snapshots)
        await self._cleanup_old_snapshots(user_id)

        return Snapshot.from_dict(result)

    async def undo_last_change(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Undo the most recent change (snapshot)

        Args:
            user_id: User ID

        Returns:
            Result of the undo operation
        """
        # Get most recent non-reverted snapshot
        snapshots = await self.db.get_snapshots(user_id, limit=1)

        if not snapshots:
            return {
                "success": False,
                "message": "没有可撤销的更改。",
                "snapshot": None
            }

        snapshot_data = snapshots[0]

        # Check if already reverted
        if snapshot_data.get("is_reverted"):
            return {
                "success": False,
                "message": "最近的更改已经被撤销过了。",
                "snapshot": None
            }

        # Revert changes
        return await self.revert_snapshot(snapshot_data["id"], user_id)

    async def revert_snapshot(
        self,
        snapshot_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Revert to a specific snapshot

        Args:
            snapshot_id: Snapshot ID to revert
            user_id: User ID

        Returns:
            Result of the revert operation
        """
        # Get snapshot
        snapshot_data = await self.db.get_snapshot(snapshot_id, user_id)

        if not snapshot_data:
            return {
                "success": False,
                "message": "未找到指定的快照。",
                "snapshot": None
            }

        # Check if already reverted
        if snapshot_data.get("is_reverted"):
            return {
                "success": False,
                "message": "此快照已经被撤销过了。",
                "snapshot": snapshot_data
            }

        # Process each change in reverse order
        reverted_events = []
        changes = snapshot_data["changes"]

        for change_data in reversed(changes):
            action = change_data["action"]
            event_id = change_data["event_id"]

            if action == "create":
                # Undo: delete the created event
                success = await self.db.delete_event(event_id, user_id)
                if success:
                    reverted_events.append(event_id)

            elif action == "update":
                # Undo: revert to previous state
                before_state = change_data.get("before")
                if before_state:
                    await self.db.update_event(event_id, user_id, before_state)
                    reverted_events.append(event_id)

            elif action == "delete":
                # Undo: recreate the deleted event
                after_state = change_data.get("after")
                if after_state:
                    await self.db.create_event(after_state)
                    reverted_events.append(after_state["id"])

        # Mark snapshot as reverted
        await self.db.update_snapshot(snapshot_id, {
            "is_reverted": True,
            "reverted_at": datetime.utcnow()
        })

        # Generate response message
        reply = f"已撤销上次修改，{len(reverted_events)} 个事件已恢复。"

        return {
            "success": True,
            "message": reply,
            "snapshot_id": snapshot_id,
            "reverted_events": reverted_events,
            "reverted_at": datetime.utcnow()
        }

    async def get_snapshot_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get snapshot history for a user

        Args:
            user_id: User ID
            limit: Maximum number of snapshots to return

        Returns:
            List of snapshots
        """
        return await self.db.get_snapshots(user_id, limit=limit)

    async def _cleanup_old_snapshots(self, user_id: int):
        """
        Clean up old snapshots, keeping only max_snapshots most recent ones

        Args:
            user_id: User ID
        """
        await self.db.delete_old_snapshots(user_id, keep_count=self.max_snapshots)

    def format_snapshot_summary(self, snapshot_data: Dict[str, Any]) -> str:
        """
        Format snapshot summary for display

        Args:
            snapshot_data: Snapshot data

        Returns:
            Formatted summary string
        """
        trigger_time = datetime.fromisoformat(snapshot_data["trigger_time"]).strftime("%m/%d %H:%M")
        changes_count = len(snapshot_data["changes"])
        is_reverted = snapshot_data.get("is_reverted", False)

        status = "已撤销" if is_reverted else ""

        return f"{trigger_time} - {snapshot_data['trigger_message']} ({changes_count}个变更) {status}"

    def format_snapshot_details(self, snapshot_data: Dict[str, Any]) -> str:
        """
        Format snapshot details for display

        Args:
            snapshot_data: Snapshot data

        Returns:
            Formatted details string
        """
        trigger_time = datetime.fromisoformat(snapshot_data["trigger_time"]).strftime("%Y-%m-%d %H:%M:%S")
        changes = snapshot_data["changes"]

        lines = [
            f"触发时间: {trigger_time}",
            f"触发消息: {snapshot_data['trigger_message']}",
            f"变更数量: {len(changes)}",
            "\n变更详情:"
        ]

        for i, change in enumerate(changes, 1):
            action_cn = {
                "create": "创建",
                "update": "更新",
                "delete": "删除"
            }.get(change["action"], change["action"])

            lines.append(f"  {i}. {action_cn} 事件: {change.get('event_id', 'unknown')}")

        return "\n".join(lines)


# Global snapshot manager instance
snapshot_manager = SnapshotManager()
