"""
Agent Tools - Callable functions for LLM Agent
类似 Cursor Agent 的工具系统，LLM 可以调用这些工具来操作数据库
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from app.services.db import db_service
from app.models.event import EventType, Category, EventStatus, EnergyLevel


class ToolRegistry:
    """工具注册中心 - 管理所有可调用的工具"""

    def __init__(self):
        self._tools = {}

    def register(self, name: str, description: str, parameters: Dict[str, Any], func):
        """注册工具"""
        self._tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "function": func
        }

    def get_tool(self, name: str):
        """获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有工具（用于发送给 LLM）"""
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"]
            }
            for tool in self._tools.values()
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """执行工具调用"""
        tool = self.get_tool(name)
        if not tool:
            return {"error": f"Tool '{name}' not found"}
        try:
            return await tool["function"](**arguments)
        except Exception as e:
            return {"error": str(e)}


# 全局工具注册表
tool_registry = ToolRegistry()


# ============ Tool 定义 ============

def register_all_tools():
    """注册所有 Agent 工具"""

    # 1. 创建事件工具
    tool_registry.register(
        name="create_event",
        description="创建一个新的日程事件。需要用户提供事件的标题、时间等信息。如果时间信息不完整，应该先询问用户。",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                },
                "title": {
                    "type": "string",
                    "description": "事件标题（必填）"
                },
                "description": {
                    "type": "string",
                    "description": "事件详细描述（可选）"
                },
                "start_time": {
                    "type": "string",
                    "description": "开始时间，ISO 8601 格式，例如 2026-01-21T15:00:00（可选，不填则为浮动事件）"
                },
                "end_time": {
                    "type": "string",
                    "description": "结束时间，ISO 8601 格式（可选）"
                },
                "duration": {
                    "type": "integer",
                    "description": "持续时长（分钟）"
                },
                "energy_required": {
                    "type": "string",
                    "enum": ["HIGH", "MEDIUM", "LOW"],
                    "description": "能量需求"
                },
                "urgency": {
                    "type": "integer",
                    "description": "紧急程度 1-5"
                },
                "importance": {
                    "type": "integer",
                    "description": "重要程度 1-5"
                },
                "category": {
                    "type": "string",
                    "enum": ["WORK", "STUDY", "SOCIAL", "LIFE", "HEALTH"],
                    "description": "事件类别"
                },
                "location": {
                    "type": "string",
                    "description": "地点（可选）"
                }
            },
            "required": ["user_id", "title"]
        },
        func=tool_create_event
    )

    # 2. 查询事件工具
    tool_registry.register(
        name="query_events",
        description="查询用户的日程事件。可以按日期、类别、状态等条件过滤。",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                },
                "category": {
                    "type": "string",
                    "enum": ["WORK", "STUDY", "SOCIAL", "LIFE", "HEALTH"],
                    "description": "按类别过滤（可选）"
                },
                "status": {
                    "type": "string",
                    "enum": ["PENDING", "COMPLETED", "CANCELLED"],
                    "description": "按状态过滤（可选）"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回结果数量限制（默认50）"
                }
            },
            "required": ["user_id"]
        },
        func=tool_query_events
    )

    # 3. 删除事件工具
    tool_registry.register(
        name="delete_event",
        description="取消/删除一个已存在的事件。需要事件ID。",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                },
                "event_id": {
                    "type": "string",
                    "description": "要删除的事件ID"
                }
            },
            "required": ["user_id", "event_id"]
        },
        func=tool_delete_event
    )

    # 4. 更新事件工具
    tool_registry.register(
        name="update_event",
        description="修改已存在的事件信息。可以修改时间、标题、状态等。",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                },
                "event_id": {
                    "type": "string",
                    "description": "要修改的事件ID"
                },
                "title": {
                    "type": "string",
                    "description": "新的事件标题"
                },
                "start_time": {
                    "type": "string",
                    "description": "新的开始时间，ISO 8601 格式"
                },
                "end_time": {
                    "type": "string",
                    "description": "新的结束时间，ISO 8601 格式"
                },
                "status": {
                    "type": "string",
                    "enum": ["PENDING", "COMPLETED", "CANCELLED"],
                    "description": "新状态"
                }
            },
            "required": ["user_id", "event_id"]
        },
        func=tool_update_event
    )

    # 5. 获取用户能量工具
    tool_registry.register(
        name="get_user_energy",
        description="获取用户当前的能量状态和能量档案信息",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                }
            },
            "required": ["user_id"]
        },
        func=tool_get_user_energy
    )

    # 6. 获取用户日程概览工具
    tool_registry.register(
        name="get_schedule_overview",
        description="获取用户的日程概览，包括最近的事件、统计信息等",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                }
            },
            "required": ["user_id"]
        },
        func=tool_get_schedule_overview
    )

    # 7. 检查时间冲突工具
    tool_registry.register(
        name="check_time_conflicts",
        description="检查特定时间段是否存在时间冲突",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                },
                "start_time": {
                    "type": "string",
                    "description": "开始时间，ISO 8601 格式"
                },
                "end_time": {
                    "type": "string",
                    "description": "结束时间，ISO 8601 格式"
                }
            },
            "required": ["user_id", "start_time", "end_time"]
        },
        func=tool_check_time_conflicts
    )

    # 8. 完成事件工具
    tool_registry.register(
        name="complete_event",
        description="标记一个事件为已完成",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                },
                "event_id": {
                    "type": "string",
                    "description": "要完成的事件ID"
                }
            },
            "required": ["user_id", "event_id"]
        },
        func=tool_complete_event
    )

    # 9. 获取快照列表工具
    tool_registry.register(
        name="get_snapshots",
        description="获取用户的历史快照列表",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量限制（默认10）"
                }
            },
            "required": ["user_id"]
        },
        func=tool_get_snapshots
    )

    # 10. 回滚快照工具
    tool_registry.register(
        name="revert_snapshot",
        description="回滚到指定的历史快照状态",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                },
                "snapshot_id": {
                    "type": "string",
                    "description": "要回滚的快照ID"
                }
            },
            "required": ["user_id", "snapshot_id"]
        },
        func=tool_revert_snapshot
    )


# ============ Tool 实现函数 ============

async def tool_create_event(
    user_id: str,
    title: str,
    description: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    duration: Optional[int] = None,
    energy_required: str = "MEDIUM",
    urgency: int = 3,
    importance: int = 3,
    category: str = "WORK",
    location: Optional[str] = None
) -> Dict[str, Any]:
    """创建新事件"""
    event_data = {
        "user_id": user_id,
        "title": title,
        "description": description,
        "start_time": datetime.fromisoformat(start_time) if start_time else None,
        "end_time": datetime.fromisoformat(end_time) if end_time else None,
        "duration": duration,
        "energy_required": energy_required,
        "urgency": urgency,
        "importance": importance,
        "event_type": EventType.SCHEDULE.value if start_time else EventType.FLOATING.value,
        "category": category,
        "location": location,
        "tags": [],
        "participants": [],
        "status": EventStatus.PENDING.value,
        "created_by": "agent",
        "is_deep_work": category == "STUDY" or category == "WORK"
    }

    created_event = await db_service.create_event(event_data)
    return {
        "success": True,
        "event": created_event,
        "message": f"已创建事件：{title}"
    }


async def tool_query_events(
    user_id: str,
    category: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """查询事件"""
    filters = {}
    if category:
        filters["category"] = category
    if status:
        filters["status"] = status

    events = await db_service.get_events(user_id, filters=filters, limit=limit)

    return {
        "success": True,
        "events": events,
        "count": len(events),
        "message": f"找到 {len(events)} 个事件"
    }


async def tool_delete_event(user_id: str, event_id: str) -> Dict[str, Any]:
    """删除事件"""
    # 先获取事件信息用于返回
    event = await db_service.get_event(event_id, user_id)
    if not event:
        return {
            "success": False,
            "error": "事件不存在"
        }

    success = await db_service.delete_event(event_id, user_id)

    if success:
        return {
            "success": True,
            "deleted_event": event,
            "message": f"已删除事件：{event['title']}"
        }
    else:
        return {
            "success": False,
            "error": "删除失败"
        }


async def tool_update_event(
    user_id: str,
    event_id: str,
    title: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """更新事件"""
    update_data = {}
    if title:
        update_data["title"] = title
    if start_time:
        update_data["start_time"] = datetime.fromisoformat(start_time)
    if end_time:
        update_data["end_time"] = datetime.fromisoformat(end_time)
    if status:
        update_data["status"] = status

    updated_event = await db_service.update_event(event_id, user_id, update_data)

    if updated_event:
        return {
            "success": True,
            "event": updated_event,
            "message": f"已更新事件：{updated_event['title']}"
        }
    else:
        return {
            "success": False,
            "error": "事件不存在或更新失败"
        }


async def tool_get_user_energy(user_id: str) -> Dict[str, Any]:
    """获取用户能量状态"""
    user = await db_service.get_user(user_id)

    if not user:
        return {
            "success": False,
            "error": "用户不存在"
        }

    current_energy = user.get("current_energy", 100)
    energy_profile = user.get("energy_profile", {})

    return {
        "success": True,
        "current_energy": current_energy,
        "energy_profile": energy_profile,
        "message": f"当前能量：{current_energy}%"
    }


async def tool_get_schedule_overview(user_id: str) -> Dict[str, Any]:
    """获取日程概览"""
    events = await db_service.get_events(user_id, limit=100)

    # 统计信息
    total = len(events)
    pending = sum(1 for e in events if e["status"] == "PENDING")
    completed = sum(1 for e in events if e["status"] == "COMPLETED")

    # 按类别统计
    by_category = {}
    for event in events:
        cat = event.get("category", "UNKNOWN")
        by_category[cat] = by_category.get(cat, 0) + 1

    return {
        "success": True,
        "statistics": {
            "total": total,
            "pending": pending,
            "completed": completed
        },
        "by_category": by_category,
        "recent_events": events[:10]
    }


async def tool_check_time_conflicts(
    user_id: str,
    start_time: str,
    end_time: str
) -> Dict[str, Any]:
    """检查时间冲突"""
    conflicts = await db_service.check_time_conflict(
        user_id=user_id,
        start_time=datetime.fromisoformat(start_time),
        end_time=datetime.fromisoformat(end_time)
    )

    return {
        "success": True,
        "has_conflicts": len(conflicts) > 0,
        "conflicts": conflicts,
        "message": f"发现 {len(conflicts)} 个时间冲突" if conflicts else "没有时间冲突"
    }


async def tool_complete_event(user_id: str, event_id: str) -> Dict[str, Any]:
    """完成事件"""
    updated = await db_service.update_event(
        event_id, user_id,
        {"status": EventStatus.COMPLETED.value}
    )

    if updated:
        return {
            "success": True,
            "event": updated,
            "message": f"已完成事件：{updated['title']}"
        }
    else:
        return {
            "success": False,
            "error": "事件不存在或标记失败"
        }


async def tool_get_snapshots(user_id: str, limit: int = 10) -> Dict[str, Any]:
    """获取快照列表"""
    snapshots = await db_service.get_snapshots(user_id, limit=limit)

    return {
        "success": True,
        "snapshots": snapshots,
        "count": len(snapshots)
    }


async def tool_revert_snapshot(user_id: str, snapshot_id: str) -> Dict[str, Any]:
    """回滚快照"""
    # 这里需要实现快照回滚逻辑
    # 暂时返回未实现
    return {
        "success": False,
        "error": "快照回滚功能待实现"
    }


# 初始化时注册所有工具
register_all_tools()
