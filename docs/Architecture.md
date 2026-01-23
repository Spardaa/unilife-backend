# UniLife 多智能体架构文档

> 基于当前实现状态的架构说明文档
> 更新时间：2026-01-23

## 1. 项目概述

UniLife 是一个基于 **FastAPI + DeepSeek LLM** 的智能生活日程助理，采用 **多智能体（Multi-Agent）架构**，实现了人格与逻辑分离、动态上下文注入和自我进化闭环。

### 核心特性

- **人格与逻辑分离**：Persona（陪伴者）负责拟人化交流，Executor（执行官）负责工具调用
- **动态上下文注入**：通过模板变量替换，将用户画像动态注入到 Agent 系统提示中
- **自我进化闭环**：Observer（观察者）异步分析对话，自动更新用户画像
- **双循环架构**：同步循环处理实时对话，异步循环进行画像学习

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                       用户请求                              │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   AgentOrchestrator                        │
│                   (app/agents/orchestrator.py)             │
└────────────────────────┬────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌───────────────┐ ┌──────────────┐ ┌──────────────┐
│  RouterAgent  │ │ExecutorAgent │ │PersonaAgent  │
│ (intent.py)    │ │(executor.py)  │ │(persona.py)  │
└───────┬────────┘ └──────┬───────┘ └──────┬───────┘
        │                 │                 │
        └────────┬────────┴─────────────────┘
                 │
        ┌────────▼────────┐
        │  Response       │
        └─────────────────┘
                 │
        ┌────────▼────────┐ (异步)
        │  ObserverAgent  │
        │  (observer.py)   │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │ 更新用户画像    │
        └─────────────────┘
```

### 2.2 同步循环（实时响应）

```
用户消息 → Orchestrator → Router（意图识别）
                                    ↓
                          ┌─────────┴─────────┐
                          ↓                   ↓
                    Executor           Persona
                  (工具调用)         (拟人回复)
                          ↓                   ↓
                          └─────────┬─────────┘
                                    ↓
                              回复用户
```

### 2.3 异步循环（后台学习）

```
对话结束 → Observer.on_conversation_end()
    ↓
分析对话内容 → 提取行为信号
    ↓
更新 UserProfile（人格画像）
更新 UserDecisionProfile（决策偏好）
```

---

## 3. Agent 详细说明

### 3.1 RouterAgent - 调度官

**文件**: `app/agents/router.py`
**Prompt**: `prompts/agents/router.txt`

**职责**:
- 识别用户意图（CREATE_EVENT, QUERY_EVENT, CHITCHAT 等）
- 决定路由策略：
  - `executor`: 需要工具调用
  - `persona`: 纯聊天
  - `both`: 混合意图

**输入**:
```python
ConversationContext(
    user_id: str,
    user_message: str,
    conversation_history: List[Dict]
)
```

**输出**:
```python
AgentResponse(
    content: "[路由] 意图: create_event, 路由: executor",
    metadata={
        "intent": "create_event",
        "routing": "executor",
        "confidence": 0.95
    },
    should_route_to=RoutingDecision.EXECUTOR
)
```

---

### 3.2 ExecutorAgent - 执行官

**文件**: `app/agents/executor.py`
**Prompt**: `prompts/agents/executor.txt`

**职责**:
- 理性、无情感地执行工具调用
- 注入用户决策偏好进行智能决策
- 返回结构化执行结果

**注入的用户决策偏好**:
```python
{
    "time_preference": {
        "start_of_day": "09:00",
        "deep_work_window": ["09:00", "12:00"]
    },
    "meeting_preference": {
        "stacking_style": "stacked",
        "max_back_to_back": 3
    },
    "conflict_resolution": {
        "strategy": "ask",
        "cancellation_threshold": 0.8
    }
}
```

**可用工具**（26个）:
- 事件管理: `create_event`, `query_events`, `update_event`, `delete_event`, `complete_event`
- 长期日程: `create_routine_template`, `get_events_with_routines`, `handle_routine_instance`
- 时间解析: `parse_time`
- 能量分析: `evaluate_energy_consumption`, `analyze_schedule`
- 用户偏好: `analyze_preferences`, `record_preference`, `provide_suggestions`

---

### 3.3 PersonaAgent - 陪伴者

**文件**: `app/agents/persona.py`
**Prompt**: `prompts/agents/persona.txt`

**职责**:
- 生成温暖、简洁、拟人化的回复
- 注入用户人格画像（情绪状态、交流风格）
- 无工具调用能力

**注入的用户人格信息**:
```python
{
    "personality": {
        "emotional_state": "平静",
        "communication_style": "balanced"
    }
}
```

**回复特点**:
- 简洁有力（1-3句话）
- 有同理心但不肉麻
- 能理解用户意图
- 展示查询结果

---

### 3.4 ObserverAgent - 观察者

**文件**: `app/agents/observer.py`
**Prompt**: `prompts/agents/observer.txt`

**职责**:
- 异步分析对话和操作
- 提取用户行为模式
- 更新用户画像（人格 + 决策偏好）

**触发时机**:
1. **事件触发**: 对话结束时（`on_conversation_end()`）
2. **定时触发**: 每日/每周分析（`analyze_period()`）

---

## 4. 数据模型

### 4.1 核心数据结构

**文件**: `app/agents/base.py`

```python
# 路由决策
class RoutingDecision(str, Enum):
    EXECUTOR = "executor"   # 只需要 Executor
    PERSONA = "persona"     # 只需要 Persona
    BOTH = "both"           # 先 Executor 后 Persona

# 用户意图
class Intent(str, Enum):
    CREATE_EVENT = "create_event"
    QUERY_EVENT = "query_event"
    UPDATE_EVENT = "update_event"
    DELETE_EVENT = "delete_event"
    CHITCHAT = "chitchat"
    GREETING = "greeting"
    # ... 更多

# 对话上下文
class ConversationContext(BaseModel):
    user_id: str
    conversation_id: str
    user_message: str
    current_intent: Optional[Intent]
    conversation_history: List[Dict]
    user_profile: Optional[Dict]  # 人格画像
    user_decision_profile: Optional[Dict]  # 决策偏好
    executor_result: Optional[Dict]

# Agent 响应
class AgentResponse(BaseModel):
    content: str
    tool_calls: Optional[List[Dict]]
    actions: List[Dict]
    metadata: Dict
    should_route_to: Optional[RoutingDecision]
```

### 4.2 用户画像模型

**文件**: `app/models/user_decision_profile.py`

```python
class UserDecisionProfile(BaseModel):
    """用户决策偏好"""

    # 时间偏好
    time_preference: TimePreference
    start_of_day: str = "09:00"
    deep_work_window: List[str] = ["09:00", "12:00"]

    # 会议偏好
    meeting_preference: MeetingPreference
    stacking_style: str = "stacked"  # stacked | spaced | flexible

    # 能量模式
    energy_profile: EnergyProfile
    peak_hours: List[str] = ["09:00", "11:00"]
    energy_by_day: Dict[str, str]

    # 冲突解决
    conflict_resolution: ConflictResolution
    strategy: str = "ask"  # ask | prioritize_urgent | merge

    # 场景化偏好
    scenario_preferences: List[ScenarioPreference]

    # 显式规则
    explicit_rules: List[str]
```

---

## 5. Prompt 模板系统

**文件**: `app/services/prompt.py`

### 5.1 模板变量替换

```python
# 渲染模板
prompt_service.render_template(
    "agents/executor",
    current_time="2026-01-23 15:00:00",
    user_decision=decision_profile_dict
)

# 渲染带画像的模板
prompt_service.render_with_profile(
    "agents/persona",
    user_profile=profile_dict,
    current_time="2026-01-23 15:00:00"
)
```

### 5.2 可用变量

| 变量名 | 用途 | 注入目标 |
|-------|------|---------|
| `{current_time}` | 当前时间 | 所有 Agent |
| `{user_profile}` | 人格画像 JSON | Persona |
| `{user_decision}` | 决策偏好 JSON | Executor |
| `{personality}` | 人格摘要 | Persona |
| `{emotional_state}` | 情绪状态 | Persona |
| `{stress_level}` | 压力水平 | Persona |

### 5.3 Prompt 文件结构

```
prompts/
├── agents/
│   ├── router.txt      # Router 意图分类
│   ├── executor.txt    # Executor 执行逻辑
│   ├── persona.txt     # Persona 拟人化回复
│   └── observer.txt    # Observer 行为分析
├── jarvis_system.txt   # 已废弃，保留作为参考
└── examples/           # Few-shot 示例
```

---

## 6. API 接口

### 6.1 主聊天接口

**端点**: `POST /api/v1/chat`

**请求**:
```json
{
    "message": "明天下午3点开会",
    "user_id": "user-123",
    "conversation_id": "conv-456",  // 可选，延续对话
    "current_time": "2026-01-23 15:00:00"  // 可选，测试用
}
```

**响应**:
```json
{
    "reply": "排好了，明天下午3点。",
    "actions": [
        {
            "type": "create_event",
            "event_id": "evt-789",
            "event": { ... }
        }
    ],
    "suggestions": null,
    "snapshot_id": "snap-012",
    "conversation_id": "conv-456"
}
```

### 6.2 其他端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/conversations` | POST | 创建新对话 |
| `/api/v1/conversations` | GET | 获取对话列表 |
| `/api/v1/conversations/{id}` | GET | 获取对话详情 |
| `/api/v1/conversations/{id}/messages` | GET | 获取消息列表 |

---

## 7. 开发指南

### 7.1 项目结构

```
unilife-backend/
├── app/
│   ├── agents/
│   │   ├── base.py              # 基础接口和枚举
│   │   ├── router.py            # Router Agent
│   │   ├── executor.py          # Executor Agent
│   │   ├── persona.py           # Persona Agent
│   │   ├── observer.py           # Observer Agent
│   │   ├── orchestrator.py      # 编排器
│   │   └── tools.py             # 工具注册表
│   ├── api/
│   │   └── chat.py              # 聊天 API
│   ├── models/
│   │   └── user_decision_profile.py
│   ├── services/
│   │   ├── llm.py               # LLM 服务
│   │   ├── prompt.py            # Prompt 模板
│   │   └── profile_service.py   # 画像服务
│   └── main.py                  # 应用入口
├── prompts/
│   └── agents/                  # Agent Prompt 文件
└── migrations/
    └── migrate_add_decision_profile.py
```

### 7.2 添加新 Agent

1. 继承 `BaseAgent`
2. 实现 `process()` 方法
3. 在 `orchestrator.py` 中注册
4. 创建对应的 Prompt 文件

示例：
```python
# app/agents/my_agent.py
from app.agents.base import BaseAgent, ConversationContext, AgentResponse

class MyAgent(BaseAgent):
    name = "my_agent"

    async def process(self, context: ConversationContext) -> AgentResponse:
        # 处理逻辑
        return AgentResponse(content="回复内容")

# 在 orchestrator.py 中使用
from app.agents.my_agent import my_agent
result = await my_agent.process(context)
```

### 7.3 添加新工具

1. 在 `app/agents/tools.py` 中定义工具函数
2. 在 `register_all_tools()` 中注册

示例：
```python
def tool_my_function(user_id: str, param: str) -> Dict[str, Any]:
    """工具实现"""
    return {"success": True, "result": "..."}

tool_registry.register(
    name="my_function",
    description="工具描述",
    parameters={...},  # JSON Schema
    func=tool_my_function
)
```

---

## 8. 配置说明

### 8.1 环境变量

```bash
# .env 文件
DEEPSEEK_API_KEY=sk-***
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

DB_TYPE=sqlite
SQLITE_PATH=unilife.db

JWT_SECRET_KEY=your-secret-key
```

### 8.2 启动服务

```bash
# 开发模式
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或使用 Python
python -m app.main
```

### 8.3 数据库迁移

```bash
# 创建决策偏好表
python migrations/migrate_add_decision_profile.py

# 创建增强功能表（如需人格画像）
python migrate_enhanced_features.py
```

---

## 9. 故障排查

### 9.1 常见问题

**Q: 查询日程时只说"我帮你查"但不显示结果**
A: 这是 Persona 没有正确格式化 Executor 的查询结果。已在 `_format_executor_result()` 中修复。

**Q: 看到 `user_profiles` 表不存在的错误**
A: 这不影响核心功能。运行 `migrate_enhanced_features.py` 或忽略（系统会优雅处理）。

**Q: Agent 没有调用工具**
A: 检查 `tools.py` 中工具是否正确注册，确认 `user_id` 参数处理正确。

### 9.2 日志解读

```
[LLM] Attempt 1/3: /chat/completions
[LLM] Success: /chat/completions
```
- 表示 LLM 调用成功

```
[Router] 意图: create_event, 路由: executor
```
- Router 识别意图并决定路由

```
[Executor] 已创建事件：明天下午3点开会（60分钟）
```
- Executor 执行了工具调用

---

## 10. 扩展计划

### 10.1 短期优化

- [ ] 为不同 Agent 配置不同模型（成本/性能优化）
- [ ] 添加更多 Few-shot 示例到 Prompt
- [ ] 完善用户画像表的自动创建

### 10.2 长期规划

- [ ] 添加 Memory Agent（长期记忆管理）
- [ ] 实现 Planner Agent（多步骤任务规划）
- [ ] 支持 WebSocket 实时推送
- [ ] 添加用户反馈学习循环

---

## 11. 参考资源

- **OpenAI Tools API**: https://platform.openai.com/docs/guides/function-calling
- **DeepSeek API**: https://platform.deepseek.com/api-docs/
- **FastAPI**: https://fastapi.tiangolo.com/
- **Pydantic**: https://docs.pydantic.dev/

---

*文档版本: 1.0*
*最后更新: 2026-01-23*
