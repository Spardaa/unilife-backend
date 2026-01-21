"""
Database Snapshot Model - 数据库级增量快照模型
支持全表回退到某个时间点
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import uuid


class TableSnapshot(BaseModel):
    """单表快照（增量）"""
    table_name: str = Field(..., description="表名")
    change_type: str = Field(..., description="变更类型: insert | update | delete")
    affected_ids: List[str] = Field(default_factory=list, description="受影响的行ID")
    before: List[Dict[str, Any]] = Field(default_factory=list, description="变更前的数据（只存变更的行）")
    after: List[Dict[str, Any]] = Field(default_factory=list, description="变更后的数据（只存变更的行）")
    recorded_at: datetime = Field(default_factory=datetime.utcnow, description="记录时间")

    class Config:
        json_schema_extra = {
            "example": {
                "table_name": "events",
                "change_type": "update",
                "affected_ids": ["event-123", "event-456"],
                "before": [
                    {"id": "event-123", "title": "旧标题", "start_time": "..."}
                ],
                "after": [
                    {"id": "event-123", "title": "新标题", "start_time": "..."}
                ],
                "recorded_at": "2026-01-21T10:00:00"
            }
        }


class DatabaseSnapshot(BaseModel):
    """数据库快照（增量，支持多表）"""

    # Primary key
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Snapshot UUID")

    # User reference
    user_id: str = Field(..., description="User ID")

    # Trigger information
    trigger: str = Field(..., description="触发原因（如 '创建事件: 搬运设备'）")
    trigger_time: datetime = Field(default_factory=datetime.utcnow, description="触发时间")

    # Table snapshots（多表）
    table_snapshots: Dict[str, TableSnapshot] = Field(
        default_factory=dict,
        description="各表的增量快照 {table_name: TableSnapshot}"
    )

    # Revert information
    is_reverted: bool = Field(default=False, description="是否已回退")
    reverted_at: Optional[datetime] = Field(None, description="回退时间")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(days=30),
        description="过期时间（30天）"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "snap-123",
                "user_id": "user-456",
                "trigger": "批量创建事件",
                "trigger_time": "2026-01-21T10:00:00",
                "table_snapshots": {
                    "events": {
                        "table_name": "events",
                        "change_type": "insert",
                        "affected_ids": ["event-001", "event-002"],
                        "before": [],
                        "after": [
                            {"id": "event-001", "title": "会议A"},
                            {"id": "event-002", "title": "会议B"}
                        ]
                    },
                    "routine_instances": {
                        "table_name": "routine_instances",
                        "change_type": "update",
                        "affected_ids": ["instance-123"],
                        "before": [{"status": "pending"}],
                        "after": [{"status": "cancelled"}]
                    }
                },
                "is_reverted": False,
                "created_at": "2026-01-21T10:00:00",
                "expires_at": "2026-02-20T10:00:00"
            }
        }

    def to_dict(self) -> dict:
        """转换为字典（用于数据库存储）"""
        data = self.model_dump(mode='json')

        # 转换 table_snapshots
        if self.table_snapshots:
            data["table_snapshots"] = {
                table_name: snapshot.model_dump(mode='json')
                for table_name, snapshot in self.table_snapshots.items()
            }

        return data

    @classmethod
    def from_dict(cls, data: dict) -> "DatabaseSnapshot":
        """从字典创建（从数据库读取）"""
        # 恢复 table_snapshots
        if "table_snapshots" in data and data["table_snapshots"]:
            data["table_snapshots"] = {
                table_name: TableSnapshot(**snapshot_data)
                for table_name, snapshot_data in data["table_snapshots"].items()
            }

        return cls(**data)

    def mark_reverted(self):
        """标记为已回退"""
        self.is_reverted = True
        self.reverted_at = datetime.utcnow()
