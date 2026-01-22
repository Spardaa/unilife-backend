"""
Agent Tools - Callable functions for LLM Agent
类似 Cursor Agent 的工具系统，LLM 可以调用这些工具来操作数据库
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from app.services.db import db_service
from app.models.event import EventType, Category, EventStatus, EnergyLevel
from app.agents.duration_estimator import duration_estimator_agent


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

    # 11. 提供交互式选项工具
    tool_registry.register(
        name="provide_suggestions",
        description="提供交互式选项供用户选择。用于降低用户使用难度，当需要用户输入或选择时，提供可点击的选项。适用于：信息缺失时提供选项、需要确认操作、AI建议时提供多个方案、模糊意图消解等场景。",
        parameters={
            "type": "object",
            "properties": {
                "suggestions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {
                                "type": "string",
                                "description": "显示给用户的标签文本"
                            },
                            "value": {
                                "type": ["string", "null"],
                                "description": "实际的值（如果为 null，表示需要用户手动输入）"
                            },
                            "description": {
                                "type": "string",
                                "description": "选项的详细描述（可选）"
                            }
                        },
                        "required": ["label"]
                    },
                    "description": "选项列表（2-4个选项）"
                }
            },
            "required": ["suggestions"]
        },
        func=tool_provide_suggestions
    )

    # 12. 分析用户偏好工具
    tool_registry.register(
        name="analyze_preferences",
        description="分析用户在特定场景下的历史偏好，预测用户最可能的选择。用于智能决策，基于用户的历史选择数据。",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                },
                "scenario_type": {
                    "type": "string",
                    "description": "场景类型，如：time_conflict（时间冲突）、event_cancellation（取消事件）、reschedule_choice（重新安排选择）等"
                },
                "context": {
                    "type": "object",
                    "description": "上下文信息（可选），如事件类型、时间段等，用于更精确的匹配"
                }
            },
            "required": ["user_id", "scenario_type"]
        },
        func=tool_analyze_preferences
    )

    # 13. 记录用户偏好工具
    tool_registry.register(
        name="record_preference",
        description="记录用户的决策选择，用于学习用户偏好。在用户做出选择后调用，帮助 AI 逐渐了解用户的行为模式。",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                },
                "scenario_type": {
                    "type": "string",
                    "description": "场景类型"
                },
                "decision": {
                    "type": "string",
                    "description": "用户做出的选择（如：merge, cancel, reschedule）"
                },
                "decision_type": {
                    "type": "string",
                    "description": "决策类型"
                },
                "context": {
                    "type": "object",
                    "description": "上下文信息（可选）"
                }
            },
            "required": ["user_id", "scenario_type", "decision", "decision_type"]
        },
        func=tool_record_preference
    )

    # ============ Routine/Habit Management Tools ============

    # 14. 创建长期日程工具
    tool_registry.register(
        name="create_routine",
        description="创建长期日程/习惯（Routine），用于管理重复性的生活安排，如每天健身、每周阅读等。与普通事件不同，routine具有灵活的重复规则、智能提醒和补课机制。",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                },
                "title": {
                    "type": "string",
                    "description": "长期日程标题（必填）"
                },
                "description": {
                    "type": "string",
                    "description": "详细描述，AI会根据此内容做智能判断（如：在健身房锻炼1小时，包括热身、力量训练和有氧运动）"
                },
                "frequency": {
                    "type": "string",
                    "enum": ["daily", "weekly", "custom"],
                    "description": "重复频率：daily（每天）、weekly（每周，需指定days）、custom（自定义）"
                },
                "days": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "当frequency=weekly时，指定星期几（0=周一, 6=周日），如[0,1,2,3,4]表示周一到周五"
                },
                "is_flexible": {
                    "type": "boolean",
                    "description": "时间是否灵活。True表示每天再决定具体时间，False表示固定时间"
                },
                "preferred_time_slots": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "string", "description": "开始时间，如18:00"},
                            "end": {"type": "string", "description": "结束时间，如20:00"},
                            "priority": {"type": "integer", "description": "优先级"}
                        }
                    },
                    "description": "偏好时间段列表，如[{\"start\": \"18:00\", \"end\": \"20:00\", \"priority\": 1}]"
                },
                "makeup_strategy": {
                    "type": "string",
                    "enum": ["ask_user", "auto_next_day", "auto_same_day_next_week", "skip"],
                    "description": "补课策略：ask_user（询问用户）、auto_next_day（自动顺延）、auto_same_day_next_week（下周同一天）、skip（跳过）"
                },
                "category": {
                    "type": "string",
                    "enum": ["WORK", "STUDY", "SOCIAL", "LIFE", "HEALTH"],
                    "description": "类别"
                },
                "duration": {
                    "type": "integer",
                    "description": "预计时长（分钟）"
                }
            },
            "required": ["user_id", "title", "frequency"]
        },
        func=tool_create_routine
    )

    # 15. 获取所有长期日程工具
    tool_registry.register(
        name="get_routines",
        description="获取用户的所有长期日程/习惯列表",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                },
                "active_only": {
                    "type": "boolean",
                    "description": "是否只显示活跃的routine（默认True）"
                }
            },
            "required": ["user_id"]
        },
        func=tool_get_routines
    )

    # 16. 获取今天的长期日程工具
    tool_registry.register(
        name="get_active_routines_for_today",
        description="获取今天应该执行的长期日程列表。用于每天早上询问用户今天的routine安排，或者检查哪些routine还未完成。",
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
        func=tool_get_active_routines_for_today
    )

    # 17. 标记长期日程已完成工具
    tool_registry.register(
        name="mark_routine_completed",
        description="标记某个长期日程在特定日期已完成。用于记录routine的完成情况，便于统计和追踪。",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                },
                "routine_id": {
                    "type": "string",
                    "description": "长期日程ID"
                },
                "completion_date": {
                    "type": "string",
                    "description": "完成日期（ISO格式，如2026-01-21，默认为今天）"
                }
            },
            "required": ["user_id", "routine_id"]
        },
        func=tool_mark_routine_completed
    )

    # 18. 获取长期日程统计工具
    tool_registry.register(
        name="get_routine_stats",
        description="获取某个长期日程的完成统计信息，包括完成率、完成天数等。用于向用户展示routine的坚持情况。",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                },
                "routine_id": {
                    "type": "string",
                    "description": "长期日程ID"
                },
                "days_back": {
                    "type": "integer",
                    "description": "统计最近多少天（默认30天）"
                }
            },
            "required": ["user_id", "routine_id"]
        },
        func=tool_get_routine_stats
    )

    # ============ Time Parsing Tools ============

    # 19. 智能时间解析工具
    tool_registry.register(
        name="parse_time",
        description="智能解析自然语言时间表达式。支持精确时间（明天下午3点）、相对日期（后天、下周三）、模糊时间（傍晚、上午晚些时候）、时间范围（本周三到周五）等多种表达方式。",
        parameters={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "时间文本（如'明天下午3点'、'下周三'、'傍晚'、'本周五到周日'）"
                },
                "reference_date": {
                    "type": "string",
                    "description": "参考日期 ISO 格式，如 '2026-01-21T15:00:00'（可选，默认为当前时间）"
                }
            },
            "required": ["text"]
        },
        func=tool_parse_time
    )

    # ============ New Routine Tools (Three-Layer Model) ============

    # 20. 创建 Routine 模板工具（支持序列）
    tool_registry.register(
        name="create_routine_template",
        description="创建新的长期重复日程模板（Routine），支持序列循环。例如：每周一到五健身，训练顺序是'胸肩背'循环。会自动管理每次应该训练的内容。",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                },
                "name": {
                    "type": "string",
                    "description": "Routine 名称（如'健身计划'）"
                },
                "description": {
                    "type": "string",
                    "description": "详细描述（可选）"
                },
                "category": {
                    "type": "string",
                    "description": "分类（fitness, study, work, life等）"
                },
                "frequency": {
                    "type": "string",
                    "enum": ["daily", "weekly", "monthly"],
                    "description": "重复频率"
                },
                "days": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "当frequency=weekly时，指定星期几（0=周一, 6=周日）"
                },
                "time": {
                    "type": "string",
                    "description": "时间（如'18:00'）"
                },
                "sequence": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "序列列表（如['胸', '肩', '背']）"
                },
                "is_flexible": {
                    "type": "boolean",
                    "description": "是否允许灵活调整（默认True）"
                }
            },
            "required": ["user_id", "name", "frequency"]
        },
        func=tool_create_routine_template
    )

    # 21. 获取事件（包含 Routine 实例）
    tool_registry.register(
        name="get_events_with_routines",
        description="获取指定时间范围内的事件（普通事件 + Routine实例）。Routine实例会标记为'长期'并显示序列项（如'健身计划 - 胸部训练'）。",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                },
                "start_date": {
                    "type": "string",
                    "description": "开始日期（YYYY-MM-DD）"
                },
                "end_date": {
                    "type": "string",
                    "description": "结束日期（YYYY-MM-DD）"
                }
            },
            "required": ["user_id", "start_date", "end_date"]
        },
        func=tool_get_events_with_routines
    )

    # 22. 操作 Routine 实例工具
    tool_registry.register(
        name="handle_routine_instance",
        description="操作某个 Routine 实例（取消、延期、完成等）。支持智能处理序列关联，例如：取消周二的训练，序列不前进，下次还是练同样的内容。",
        parameters={
            "type": "object",
            "properties": {
                "instance_id": {
                    "type": "string",
                    "description": "Routine 实例ID"
                },
                "action": {
                    "type": "string",
                    "enum": ["cancel", "complete", "reschedule", "skip"],
                    "description": "操作类型"
                },
                "reason": {
                    "type": "string",
                    "description": "原因（可选，如'急事'、'身体不适'）"
                },
                "notes": {
                    "type": "string",
                    "description": "详细说明（可选）"
                },
                "actual_date": {
                    "type": "string",
                    "description": "实际日期（如果延期，YYYY-MM-DD）"
                },
                "advance_sequence": {
                    "type": "boolean",
                    "description": "序列是否前进（默认true，设为false则下次还是同样的内容）"
                }
            },
            "required": ["instance_id", "action"]
        },
        func=tool_handle_routine_instance
    )

    # 23. 获取 Routine 模板列表
    tool_registry.register(
        name="list_routine_templates",
        description="列出用户的所有 Routine 模板（规则），显示每个模板的统计信息和序列配置。",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "用户ID"
                },
                "active_only": {
                    "type": "boolean",
                    "description": "是否只显示激活的（默认True）"
                }
            },
            "required": ["user_id"]
        },
        func=tool_list_routine_templates
    )

    # 24. 获取 Routine 实例详情
    tool_registry.register(
        name="get_routine_instance_detail",
        description="获取某个 Routine 实例的详细信息，包括执行历史、序列位置等。",
        parameters={
            "type": "object",
            "properties": {
                "instance_id": {
                    "type": "string",
                    "description": "实例ID"
                }
            },
            "required": ["instance_id"]
        },
        func=tool_get_routine_instance_detail
    )

    # ============ Enhanced Features Tools ============

    # 25. 评估精力消耗工具
    tool_registry.register(
        name="evaluate_energy_consumption",
        description="评估事件的精力消耗（体力+精神两个维度）。返回结构化评估结果，包括level（低/中/高）、score（0-10分）、description（自然语言描述）和factors（具体因素）。",
        parameters={
            "type": "object",
            "properties": {
                "event_title": {
                    "type": "string",
                    "description": "事件标题"
                },
                "event_description": {
                    "type": "string",
                    "description": "事件描述（可选）"
                },
                "event_duration": {
                    "type": "string",
                    "description": "时长（可选）"
                },
                "event_location": {
                    "type": "string",
                    "description": "地点（可选）"
                },
                "user_profile": {
                    "type": "object",
                    "description": "用户画像信息（可选）"
                }
            },
            "required": ["event_title"]
        },
        func=tool_evaluate_energy_consumption
    )

    # 26. 分析日程合理性工具
    tool_registry.register(
        name="analyze_schedule",
        description="分析日程安排的合理性，检测连续高强度体力/精神消耗，提供优化建议。输入事件列表（需包含energy_consumption），返回分析结果和建议。",
        parameters={
            "type": "object",
            "properties": {
                "events": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "事件列表（每个事件需包含 energy_consumption 信息）"
                },
                "user_context": {
                    "type": "object",
                    "description": "用户上下文（可选）"
                }
            },
            "required": ["events"]
        },
        func=tool_analyze_schedule
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
    """创建新事件（集成AI时长估计）"""

    # 解析时间
    start_dt = datetime.fromisoformat(start_time) if start_time else None
    end_dt = datetime.fromisoformat(end_time) if end_time else None

    # 时长估计逻辑
    duration_source = "user_exact"
    duration_confidence = 1.0
    ai_original_estimate = None

    # 如果用户没有提供时长和结束时间，AI估计
    if duration is None and end_dt is None and start_dt:
        # 获取用户最近的事件用于学习
        recent_events = await db_service.get_events(user_id, limit=10)

        # AI估计时长
        estimate = await duration_estimator_agent.estimate(
            event_title=title,
            event_description=description,
            user_id=user_id,
            recent_events=recent_events
        )

        duration = estimate.duration
        duration_source = estimate.source
        duration_confidence = estimate.confidence

        # 计算结束时间
        end_dt = start_dt + timedelta(minutes=duration)

    # 如果提供了结束时间但没提供时长，计算时长
    elif duration is None and end_dt and start_dt:
        duration = int((end_dt - start_dt).total_seconds() / 60)
        duration_source = "user_exact"
        duration_confidence = 1.0

    # 如果提供了时长但没提供结束时间，计算结束时间
    elif duration and end_dt is None and start_dt:
        end_dt = start_dt + timedelta(minutes=duration)

    event_data = {
        "user_id": user_id,
        "title": title,
        "description": description,
        "start_time": start_dt,
        "end_time": end_dt,
        "duration": duration,
        "duration_source": duration_source,
        "duration_confidence": duration_confidence,
        "ai_original_estimate": ai_original_estimate,
        "display_mode": "flexible",  # 默认柔性显示
        "energy_required": energy_required,
        "urgency": urgency,
        "importance": importance,
        "event_type": EventType.SCHEDULE.value if start_dt else EventType.FLOATING.value,
        "category": category,
        "location": location,
        "tags": [],
        "participants": [],
        "status": EventStatus.PENDING.value,
        "created_by": "agent",
        "is_deep_work": category == "STUDY" or category == "WORK"
    }

    created_event = await db_service.create_event(event_data)

    # 返回消息，根据时长来源显示不同信息
    message = f"已创建事件：{title}"
    if duration_source == "ai_estimate" and duration_confidence < 0.7:
        message += f"（时长约{duration}分钟，AI估计）"
    elif duration_source == "ai_estimate":
        message += f"（约{duration}分钟）"
    elif duration:
        message += f"（{duration}分钟）"

    return {
        "success": True,
        "event": created_event,
        "message": message
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
    end_time: str,
    duration_source: str = "user_exact"
) -> Dict[str, Any]:
    """
    检查时间冲突（支持柔性提示）

    Args:
        user_id: 用户ID
        start_time: 开始时间（ISO格式）
        end_time: 结束时间（ISO格式）
        duration_source: 时长来源，用于确定提示级别
    """
    conflicts = await db_service.check_time_conflict(
        user_id=user_id,
        start_time=datetime.fromisoformat(start_time),
        end_time=datetime.fromisoformat(end_time)
    )

    # 根据时长来源调整冲突提示
    has_conflicts = len(conflicts) > 0
    message = ""

    if has_conflicts:
        # 检查是否有AI估计时长的事件
        has_ai_estimate = any(
            c.get("duration_source") == "ai_estimate"
            for c in conflicts
        )

        if has_ai_estimate or duration_source == "ai_estimate":
            message = f"可能发现 {len(conflicts)} 个时间冲突（AI估计时长，实际可能不冲突）"
        else:
            message = f"发现 {len(conflicts)} 个时间冲突"
    else:
        message = "没有时间冲突"

    return {
        "success": True,
        "has_conflicts": has_conflicts,
        "conflicts": conflicts,
        "message": message
    }


async def tool_complete_event(user_id: str, event_id: str, actual_duration: Optional[int] = None) -> Dict[str, Any]:
    """
    完成事件（集成AI学习）

    Args:
        user_id: 用户ID
        event_id: 事件ID
        actual_duration: 实际时长（分钟），可选。如果不提供，则自动计算
    """

    # 获取事件信息
    event = await db_service.get_event(event_id, user_id)
    if not event:
        return {
            "success": False,
            "error": "事件不存在"
        }

    # 计算实际时长
    if actual_duration is None:
        # 如果提供了实际结束时间，计算时长
        # TODO: 这里可以添加一个 completed_at 字段来记录实际完成时间
        # 暂时使用预计时长
        actual_duration = event.get("duration", 0)

    # 准备更新数据
    update_data = {
        "status": EventStatus.COMPLETED.value,
        "duration_actual": actual_duration
    }

    # 如果是AI估计的，进行学习
    if event.get("duration_source") == "ai_estimate":
        estimated_duration = event.get("duration", 0)
        if estimated_duration > 0:
            # 调用学习
            await duration_estimator_agent.learn_from_completion(
                event_id=event_id,
                event_title=event.get("title", ""),
                estimated_duration=estimated_duration,
                actual_duration=actual_duration,
                user_id=user_id
            )

    # 更新事件
    updated = await db_service.update_event(event_id, user_id, update_data)

    if updated:
        message = f"已完成事件：{updated['title']}"
        if actual_duration:
            message += f"（实际用时{actual_duration}分钟）"

        return {
            "success": True,
            "event": updated,
            "message": message
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


async def tool_provide_suggestions(
    suggestions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    提供交互式选项供用户选择

    这是一个特殊的工具，不执行数据库操作，而是返回建议选项。
    LLM 使用这个工具来为用户提供可点击的选项，降低使用难度。

    Args:
        suggestions: 选项列表，每个选项包含:
            - label: 显示标签
            - value: 实际值（None 表示需要用户手动输入）
            - description: 详细描述（可选）
            - probability: AI 预测的用户选择此选项的概率 0-100（可选）

    Returns:
        包含 suggestions 的结果
    """
    return {
        "success": True,
        "suggestions": suggestions,
        "message": "[OPTIONS] 已生成选项供用户选择"
    }


async def tool_analyze_preferences(
    user_id: str,
    scenario_type: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    分析用户在特定场景下的偏好

    用于智能决策：基于历史选择预测用户最可能的选择

    Args:
        user_id: 用户ID
        scenario_type: 场景类型（如 "time_conflict", "event_cancellation"）
        context: 上下文信息（事件类型、时间段等）

    Returns:
        {
            "predictions": [
                {"option": "merge", "probability": 75, "confidence": "high"},
                ...
            ],
            "recommended_action": "merge",  # 如果概率 > 50%
            "confidence": 75,
            "sample_size": 12
        }
    """
    from app.services.db import db_service

    analysis = await db_service.analyze_user_preferences(
        user_id=user_id,
        scenario_type=scenario_type,
        context=context
    )

    return {
        "success": True,
        **analysis
    }


async def tool_record_preference(
    user_id: str,
    scenario_type: str,
    decision: str,
    decision_type: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    记录用户的决策，用于学习用户偏好

    Args:
        user_id: 用户ID
        scenario_type: 场景类型
        decision: 用户做出的选择
        decision_type: 决策类型（merge, cancel, reschedule 等）
        context: 上下文信息

    Returns:
        记录结果
    """
    from app.services.db import db_service

    result = await db_service.record_user_preference(
        user_id=user_id,
        scenario_type=scenario_type,
        decision=decision,
        decision_type=decision_type,
        context=context
    )

    return {
        "success": True,
        "preference": result,
        "message": "[LEARNING] 已记录用户偏好"
    }


# ============ Routine/Habit Management Tools ============

async def tool_create_routine(
    user_id: str,
    title: str,
    description: Optional[str] = None,
    frequency: str = "daily",
    days: Optional[List[int]] = None,
    is_flexible: bool = False,
    preferred_time_slots: Optional[List[Dict[str, Any]]] = None,
    makeup_strategy: str = "ask_user",
    category: str = "LIFE",
    duration: Optional[int] = None
) -> Dict[str, Any]:
    """
    创建长期日程/习惯（Routine）

    用于创建重复性的长期安排，如每天健身、每周阅读等。

    Args:
        user_id: 用户ID
        title: 日程标题
        description: 详细描述（AI会根据此内容做智能判断）
        frequency: 重复频率 ("daily", "weekly", "custom")
        days: 当frequency="weekly"时，指定星期几 (0=周一, 6=周日)
        is_flexible: 时间是否灵活（True表示每天再定时间）
        preferred_time_slots: 偏好时间段 [{"start": "18:00", "end": "20:00", "priority": 1}]
        makeup_strategy: 补课策略 ("ask_user", "auto_next_day", "auto_same_day_next_week", "skip")
        category: 类别
        duration: 预计时长（分钟）

    Returns:
        创建的routine
    """
    from app.services.db import db_service

    # Build repeat_rule
    repeat_rule = {"frequency": frequency}
    if days:
        repeat_rule["days"] = days

    routine = await db_service.create_routine(
        user_id=user_id,
        title=title,
        description=description,
        repeat_rule=repeat_rule,
        is_flexible=is_flexible,
        preferred_time_slots=preferred_time_slots,
        makeup_strategy=makeup_strategy,
        category=category,
        duration=duration
    )

    return {
        "success": True,
        "routine": routine,
        "message": f"[ROUTINE] 已创建长期日程：{title}"
    }


async def tool_get_routines(user_id: str, active_only: bool = True) -> Dict[str, Any]:
    """
    获取用户的所有长期日程/习惯

    Args:
        user_id: 用户ID
        active_only: 是否只显示活跃的

    Returns:
        Routine列表
    """
    from app.services.db import db_service

    routines = await db_service.get_routines(user_id, active_only)

    return {
        "success": True,
        "routines": routines,
        "count": len(routines),
        "message": f"[ROUTINE] 找到 {len(routines)} 个长期日程"
    }


async def tool_get_active_routines_for_today(user_id: str) -> Dict[str, Any]:
    """
    获取今天应该执行的长期日程

    用于每天早上询问用户今天的routine安排。

    Args:
        user_id: 用户ID

    Returns:
        今天活跃的routines列表
    """
    from app.services.db import db_service
    from datetime import datetime

    today = datetime.now()
    routines = await db_service.get_active_routines_for_date(user_id, today)

    return {
        "success": True,
        "routines": routines,
        "count": len(routines),
        "date": today.strftime("%Y-%m-%d"),
        "message": f"[ROUTINE] 今天有 {len(routines)} 个长期待办"
    }


async def tool_mark_routine_completed(
    user_id: str,
    routine_id: str,
    completion_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    标记长期日程在某天已完成

    Args:
        user_id: 用户ID
        routine_id: Routine ID
        completion_date: 完成日期 (ISO格式，默认今天)

    Returns:
        更新后的routine
    """
    from app.services.db import db_service
    from datetime import datetime

    if completion_date:
        date = datetime.fromisoformat(completion_date)
    else:
        date = datetime.now()

    routine = await db_service.mark_routine_completed_for_date(
        routine_id=routine_id,
        user_id=user_id,
        completion_date=date
    )

    if routine:
        return {
            "success": True,
            "routine": routine,
            "message": f"[ROUTINE] 已标记完成：{routine['title']}"
        }
    else:
        return {
            "success": False,
            "error": "Routine not found"
        }


async def tool_get_routine_stats(
    user_id: str,
    routine_id: str,
    days_back: int = 30
) -> Dict[str, Any]:
    """
    获取长期日程的完成统计

    Args:
        user_id: 用户ID
        routine_id: Routine ID
        days_back: 统计最近多少天（默认30天）

    Returns:
        统计信息
    """
    from app.services.db import db_service

    stats = await db_service.get_routine_completion_stats(
        routine_id=routine_id,
        user_id=user_id,
        days_back=days_back
    )

    if stats:
        return {
            "success": True,
            "stats": stats,
            "message": f"[ROUTINE] 完成率：{stats['completion_rate']}%"
        }
    else:
        return {
            "success": False,
            "error": "Routine not found"
        }


# ============ Time Parsing Tools ============

async def tool_parse_time(
    text: str,
    reference_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    智能解析时间表达式

    支持多种自然语言时间表达方式，包括精确时间、相对日期、模糊时间、时间范围等。

    Args:
        text: 时间文本（如"明天下午3点"、"下周三"、"傍晚"、"本周五到周日"）
        reference_date: 参考日期 ISO 格式（可选，默认为当前时间）

    Returns:
        解析结果，包含类型、时间、置信度、说明等信息
    """
    from app.services.time_parser import parse_time_expression
    from datetime import datetime

    ref_date = None
    if reference_date:
        ref_date = datetime.fromisoformat(reference_date)

    result = parse_time_expression(text, ref_date)

    if result["success"]:
        return {
            "success": True,
            "parsed": result,
            "message": f"[TIME] 解析成功：{result.get('explanation', text)}"
        }
    else:
        return {
            "success": False,
            "error": result.get("error", "解析失败"),
            "suggestions": result.get("suggestions", []),
            "message": f"[TIME] 无法识别时间表达：{text}"
        }


# ============ New Routine Tools Implementation ============

async def tool_create_routine_template(
    user_id: str,
    name: str,
    frequency: str,
    description: Optional[str] = None,
    category: Optional[str] = None,
    days: Optional[List[int]] = None,
    time: Optional[str] = None,
    sequence: Optional[List[str]] = None,
    is_flexible: bool = True
) -> Dict[str, Any]:
    """
    创建 Routine 模板（支持序列循环）

    示例：
    - "每周一到五健身，训练顺序是胸肩背循环"
      → frequency="weekly", days=[0,1,2,3,4], sequence=["胸", "肩", "背"]
    """
    from app.services.routine_service import routine_service

    # 构建重复规则
    repeat_rule = {"frequency": frequency}
    if days:
        repeat_rule["days"] = days
    if time:
        repeat_rule["time"] = time

    # 创建模板
    template = routine_service.create_template(
        user_id=user_id,
        name=name,
        description=description,
        category=category,
        repeat_rule=repeat_rule,
        sequence=sequence,
        is_flexible=is_flexible
    )

    result = template.to_dict()
    result["sequence_info"] = {
        "has_sequence": sequence is not None,
        "sequence_length": len(sequence) if sequence else 0,
        "current_position": 0,
        "next_item": sequence[0] if sequence else None
    }

    return {
        "success": True,
        "template": result,
        "message": f"[ROUTINE] 已创建长期日程：{name}" + (f"，序列：{' → '.join(sequence)}" if sequence else "")
    }


async def tool_get_events_with_routines(
    user_id: str,
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    获取事件（普通 + Routine 实例）

    返回统一格式的事件列表，Routine 实例会标记 is_routine=True
    """
    from app.services.routine_service import routine_service

    events = routine_service.get_events_with_routines(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date
    )

    # 统计
    normal_count = sum(1 for e in events if not e.get("is_routine"))
    routine_count = sum(1 for e in events if e.get("is_routine"))

    return {
        "success": True,
        "events": events,
        "count": len(events),
        "normal_events": normal_count,
        "routine_instances": routine_count,
        "message": f"[EVENTS] {start_date} 至 {end_date}：共{len(events)}个日程（{normal_count}个普通，{routine_count}个长期）"
    }


async def tool_handle_routine_instance(
    instance_id: str,
    action: str,
    reason: Optional[str] = None,
    notes: Optional[str] = None,
    actual_date: Optional[str] = None,
    advance_sequence: bool = True
) -> Dict[str, Any]:
    """
    操作 Routine 实例（取消、延期、完成等）

    关键：通过 advance_sequence 控制序列是否前进
    - 取消某次训练：advance_sequence=False，下次还是同样的内容
    - 完成某次训练：advance_sequence=True，下次是序列中的下一个
    """
    from app.services.routine_service import routine_service

    # 映射 action
    action_map = {
        "cancel": "cancelled",
        "complete": "completed",
        "reschedule": "rescheduled",
        "skip": "skipped"
    }

    execution_action = action_map.get(action, action)

    # 记录执行
    execution = routine_service.record_execution(
        instance_id=instance_id,
        action=execution_action,
        reason=reason,
        notes=notes,
        actual_date=actual_date,
        sequence_advanced=advance_sequence
    )

    # 获取实例详情
    instance = routine_service.get_instance(instance_id)

    result = {
        "success": True,
        "action": action,
        "execution": execution.to_dict(),
        "sequence_advanced": advance_sequence
    }

    if instance:
        result["instance"] = instance.to_dict()
        result["message"] = f"[ROUTINE] 已{action}：{instance.template.name} ({instance.scheduled_date})"

        if not advance_sequence and instance.sequence_item:
            result["message"] += f"，序列未前进，下次还是{instance.sequence_item}"

    return result


async def tool_list_routine_templates(
    user_id: str,
    active_only: bool = True
) -> Dict[str, Any]:
    """列出用户的所有 Routine 模板"""
    from app.services.routine_service import routine_service

    templates = routine_service.list_templates(
        user_id=user_id,
        active_only=active_only
    )

    result_templates = []
    for t in templates:
        t_dict = t.to_dict()
        # 添加序列信息
        if t.sequence:
            next_item = t.sequence[t.sequence_position % len(t.sequence)]
            t_dict["next_sequence_item"] = next_item
        result_templates.append(t_dict)

    return {
        "success": True,
        "templates": result_templates,
        "count": len(templates),
        "message": f"[ROUTINE] 找到 {len(templates)} 个长期日程模板"
    }


async def tool_get_routine_instance_detail(instance_id: str) -> Dict[str, Any]:
    """获取 Routine 实例详情"""
    from app.services.routine_service import routine_service

    instance = routine_service.get_instance(instance_id)
    if not instance:
        return {
            "success": False,
            "error": "Instance not found"
        }

    # 获取执行历史
    executions = routine_service.get_executions(instance_id)

    return {
        "success": True,
        "instance": instance.to_dict(),
        "template": instance.template.to_dict(),
        "executions": [e.to_dict() for e in executions],
        "execution_count": len(executions),
        "message": f"[ROUTINE] 实例详情：{instance.template.name} ({instance.scheduled_date}) - {instance.sequence_item or '常规'}"
    }


# ============ Enhanced Features Tools Implementation ============

async def tool_evaluate_energy_consumption(
    event_title: str,
    event_description: Optional[str] = None,
    event_duration: Optional[str] = None,
    event_location: Optional[str] = None,
    user_profile: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    评估事件的精力消耗（体力 + 精神）

    用于分析事件在不同维度的精力消耗程度，帮助合理安排日程。

    Args:
        event_title: 事件标题
        event_description: 事件描述
        event_duration: 时长
        event_location: 地点
        user_profile: 用户画像（可选）

    Returns:
        精力消耗评估结果
    """
    from app.agents.energy_evaluator import energy_evaluator_agent

    event_data = {
        "title": event_title,
        "description": event_description,
        "duration": event_duration,
        "location": event_location
    }

    context = {}
    if user_profile:
        context["user_profile"] = user_profile

    try:
        evaluation = await energy_evaluator_agent.evaluate(event_data, context)

        return {
            "success": True,
            "evaluation": evaluation.model_dump(),
            "message": f"[ENERGY] 精力评估完成：体力 {evaluation.physical.level}({evaluation.physical.score}分)，精神 {evaluation.mental.level}({evaluation.mental.score}分)"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"[ENERGY] 评估失败：{str(e)}"
        }


async def tool_analyze_schedule(
    events: List[Dict[str, Any]],
    user_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    分析日程安排的合理性

    检测连续高强度体力/精神消耗，提供优化建议。

    Args:
        events: 事件列表（每个事件需包含 energy_consumption）
        user_context: 用户上下文（可选）

    Returns:
        分析结果和建议
    """
    from app.agents.smart_scheduler import smart_scheduler_agent

    try:
        # 先用快速检查
        quick_result = await smart_scheduler_agent.quick_check(events)

        # 如果有问题或有用户上下文，调用深度分析
        if quick_result.get("has_issues") or user_context:
            analysis = await smart_scheduler_agent.analyze_schedule(events, user_context)

            return {
                "success": True,
                "analysis": analysis,
                "message": analysis.get("message", "日程分析完成")
            }
        else:
            return quick_result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"[SCHEDULER] 分析失败：{str(e)}"
        }


# 初始化时注册所有工具
register_all_tools()
