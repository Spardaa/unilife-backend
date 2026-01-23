# UniLife 产品需求文档 (PRD) v1.0

| 项目名称 | UniLife |
| :---- | :---- |
| **文档版本** | v1.0 |
| **创建日期** | 2026-01-20 |
| **文档类型** | 产品需求规格书 (PRD) |
| **核心理念** | 顺应人性的"懒惰"，打造现实版的 AI 数字管家 (Jarvis) |
| **目标用户** | 追求高效生活但厌倦繁琐操作的大学生及年轻职场人 |

---

## 1. 产品概述

### 1.1 产品愿景

UniLife 是一个**具备自主决策能力的 AI 生活管家**。它理解用户的精力状态、任务的急迫程度以及社交关系，核心目标是：**消除"认知摩擦"，让用户从繁琐的日程安排中解放出来，专注于生活本身。**

### 1.2 核心差异化体验

| 特性 | 描述 |
|------|------|
| **零摩擦录入** | 用户只需动嘴/打字，Agent 自动解析意图并创建/修改日程 |
| **顺应人性的排程** | 基于 E-U (Energy-Urgency) 模型智能安排任务，顺应用户生物钟 |
| **自主执行 + 可回退** | Agent 直接执行决策后告知用户，支持快照回退 |
| **持续学习** | 从用户行为中学习习惯偏好，不断优化排程策略 |

### 1.3 MVP 功能优先级

```
P0 [核心] ─────────────────────────────────────────────────────────
│  ├── 自然语言交互（语音/文字输入，意图解析）
│  ├── 事件 CRUD（创建/查询/修改/删除日程）
│  ├── 智能时间解析（模糊时间理解，自动推断）
│  └── 快照系统（日程变更历史，支持回退）
│
P1 [精力系统] ─────────────────────────────────────────────────────
│  ├── E-U 智能排程（精力-紧急度匹配）
│  ├── 疲劳检测与提醒
│  ├── 智能缓冲（任务间自动插入休息）
│  └── 用户习惯学习引擎
│
P3 [生活控制台] ───────────────────────────────────────────────────
│  ├── 实时状态看板（当前精力值、下一行动建议）
│  ├── 时间统计（AI 节省的时间、专注时长等）
│  └── 生活节奏热力图
│
P2 [A2A 社交] ─────────────────────────────────────────────────────
   ├── Agent 代理谈判
   ├── Agent-Aware 通讯录
   └── 社交防火墙
```

> **MVP 范围**：P0 + P1（精力系统可根据开发进度简化）

---

## 2. 技术架构

### 2.1 技术栈选型

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| **后端框架** | Python + FastAPI | 异步高性能，AI 生态成熟 |
| **数据库** | Supabase (PostgreSQL) | 免费额度充足，JSONB 支持灵活元数据 |
| **LLM** | DeepSeek API | Function Calling 支持 |
| **部署** | Railway / Render | 一键部署，自动 CI/CD |
| **消息通道** | chatgpt-on-wechat | MVP 阶段微信交互入口 |

### 2.2 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端/消息入口                              │
├─────────────┬─────────────┬─────────────┬─────────────────────────┤
│ WeChatBot   │  小程序      │  iOS App    │  Web (Future)          │
│ (MVP)       │  (Phase 2)  │  (Phase 3)  │                        │
└──────┬──────┴──────┬──────┴──────┬──────┴────────────────────────┘
       │             │             │
       ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    UniLife Backend API                          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    API Gateway (FastAPI)                  │  │
│  │  ┌─────────────────┐  ┌─────────────────────────────────┐ │  │
│  │  │  /chat (对话式)  │  │  RESTful APIs                   │ │  │
│  │  │  自然语言处理    │  │  /events /users /snapshots     │ │  │
│  │  └────────┬────────┘  └─────────────────────────────────┘ │  │
│  └───────────┼───────────────────────────────────────────────┘  │
│              ▼                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  Multi-Agent System                       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐│  │
│  │  │ RouterAgent │  │ScheduleAgent│  │   MemoryAgent       ││  │
│  │  │ (意图路由)   │─▶│ (日程执行)   │  │ (用户画像/习惯学习) ││  │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘│  │
│  │  ┌─────────────┐  ┌─────────────┐                        │  │
│  │  │ EnergyAgent │  │ SnapshotMgr │                        │  │
│  │  │ (精力管理)   │  │ (快照回退)   │                        │  │
│  │  └─────────────┘  └─────────────┘                        │  │
│  └───────────────────────────────────────────────────────────┘  │
│              │                                                   │
│              ▼                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    Data Layer                             │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐ │  │
│  │  │  Events  │  │  Users   │  │ Snapshots│  │ UserMemory │ │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 与 chatgpt-on-wechat 集成方案

采用**解耦方案**：

```
┌────────────────────┐    HTTP API    ┌────────────────────┐
│  chatgpt-on-wechat │ ◀────────────▶ │  UniLife Backend   │
│  (消息收发)         │                │  (业务处理)         │
└────────────────────┘                └────────────────────┘
```

- chatgpt-on-wechat 作为**消息通道**，只负责收发微信消息
- 所有业务逻辑在 UniLife Backend 中处理
- 后续切换前端（小程序/iOS）时，后端无需任何改动

---

## 3. 数据模型设计

### 3.1 统一事件模型 (Event)

所有日程/任务统一为 `Event`，通过时间字段组合区分类型：

| 事件类型 | startTime | endTime (DDL) | 示例 |
|----------|-----------|---------------|------|
| **固定日程** | ✅ | ✅ | "周三 14:00-15:00 开会" |
| **DDL 任务** | ❌ | ✅ | "周五前提交报告" |
| **开始时间型** | ✅ | ❌ | "明早 9 点起床" |
| **浮动任务** | ❌ | ❌ | "本周完成 BP 修改" |

### 3.2 Event Schema

```python
class Event(BaseModel):
    id: str                          # UUID
    user_id: str                     # 用户 ID
    
    # 基础信息
    title: str                       # 事件标题
    description: Optional[str]       # 详细描述
    
    # 时间信息（均为可选）
    start_time: Optional[datetime]   # 开始时间
    end_time: Optional[datetime]     # 结束时间/DDL
    duration: Optional[int]          # 预估时长（分钟）
    
    # 排程相关
    energy_required: EnergyLevel     # 所需精力 (HIGH/MEDIUM/LOW)
    urgency: int                     # 紧急程度 (1-5)
    importance: int                  # 重要程度 (1-5)
    is_deep_work: bool               # 是否属于深度工作
    
    # 分类与标签
    event_type: EventType            # 事件类型
    category: Category               # 分类 (STUDY/WORK/SOCIAL/LIFE/HEALTH)
    tags: List[str]                  # 自定义标签
    
    # 地点与参与者
    location: Optional[str]          # 地点
    participants: List[str]          # 参与者
    
    # 状态管理
    status: EventStatus              # 状态 (PENDING/IN_PROGRESS/COMPLETED/CANCELLED)
    
    # 元数据
    created_at: datetime
    updated_at: datetime
    created_by: str                  # "user" or "agent"
    
    # AI 推理字段
    ai_confidence: float             # AI 创建时的置信度
    ai_reasoning: Optional[str]      # AI 决策理由
```

### 3.3 事件类型枚举

```python
class EventType(str, Enum):
    SCHEDULE = "schedule"      # 固定日程（有明确时间段）
    DEADLINE = "deadline"      # DDL 型任务
    FLOATING = "floating"      # 浮动任务（无时间约束，AI 自动安排）
    HABIT = "habit"            # 习惯/周期性任务
    REMINDER = "reminder"      # 提醒型事件
```

### 3.4 用户模型 (User)

```python
class User(BaseModel):
    id: str                          # UUID
    
    # 认证信息（统一账号系统）
    email: Optional[str]
    phone: Optional[str]
    wechat_id: Optional[str]         # 微信绑定
    
    # 个人资料
    nickname: str
    avatar_url: Optional[str]
    timezone: str = "Asia/Shanghai"
    
    # 精力配置
    energy_profile: EnergyProfile    # 精力模版
    current_energy: int              # 当前精力值 (0-100)
    
    # 偏好设置
    preferences: UserPreferences
    
    # 元数据
    created_at: datetime
    last_active_at: datetime
```

### 3.5 精力配置模型 (EnergyProfile)

```python
class EnergyProfile(BaseModel):
    # 默认精力曲线（每小时的基础精力值）
    hourly_baseline: Dict[int, int]  # {hour: energy_value}
    # 例: {9: 80, 10: 90, 11: 85, 14: 60, 15: 70, ...}
    
    # 任务类型消耗/恢复
    task_energy_cost: Dict[str, int]
    # 例: {"deep_work": -20, "meeting": -10, "break": +15, "coffee": +10}
    
    # 学习得到的个性化参数
    learned_adjustments: Dict[str, Any]
```

### 3.6 快照模型 (Snapshot)

```python
class Snapshot(BaseModel):
    id: str                          # UUID
    user_id: str
    
    # 触发信息
    trigger_message: str             # 触发此次修改的用户消息
    trigger_time: datetime           # 触发时间
    
    # 变更内容
    changes: List[EventChange]       # 事件变更列表
    
    # 回退相关
    is_reverted: bool = False        # 是否已回退
    reverted_at: Optional[datetime]
    
    # 元数据
    created_at: datetime
    expires_at: datetime             # 过期时间（保留 10 次）

class EventChange(BaseModel):
    event_id: str
    action: str                      # "create" / "update" / "delete"
    before: Optional[Dict]           # 修改前的状态（JSON）
    after: Optional[Dict]            # 修改后的状态（JSON）
```

### 3.7 用户记忆模型 (UserMemory)

```python
class UserMemory(BaseModel):
    user_id: str
    
    # 时间偏好学习
    time_preferences: Dict[str, Any]
    # 例: {"deep_work_preferred_hours": [9, 10, 11], "meeting_preferred_hours": [14, 15]}
    
    # 社交画像
    social_profile: SocialProfile
    
    # 行为统计
    behavior_stats: Dict[str, Any]
    # 例: {"avg_task_overrun_ratio": 1.2, "common_locations": ["图书馆", "咖啡厅"]}
    
    # 对话历史摘要
    conversation_summary: str
    
    # 更新时间
    updated_at: datetime

class SocialProfile(BaseModel):
    contacts: Dict[str, ContactInfo]  # 联系人信息
    relationships: Dict[str, str]     # 关系类型 (friend/colleague/family)
    intimacy_scores: Dict[str, float] # 亲密度分数
```

---

## 4. Multi-Agent 架构设计

### 4.1 Agent 职责划分

| Agent | 职责 | 触发时机 |
|-------|------|----------|
| **RouterAgent** | 意图识别与路由，决定调用哪个下游 Agent | 每次用户输入 |
| **ScheduleAgent** | 日程 CRUD 执行、时间冲突处理、智能排程 | 涉及日程操作时 |
| **EnergyAgent** | 精力值计算、疲劳检测、排程建议 | ScheduleAgent 需要精力数据时 |
| **MemoryAgent** | 用户画像管理、习惯学习、长期记忆 | 每次交互完成后异步更新 |
| **SnapshotManager** | 快照创建与回退（非 LLM Agent，纯逻辑） | ScheduleAgent 修改日程时 |

### 4.2 Agent 调用流程

```
用户输入
    │
    ▼
┌─────────────┐
│ RouterAgent │  ← 意图识别："帮我约明天下午开会"
└─────┬───────┘
      │ 路由到 ScheduleAgent
      ▼
┌─────────────┐    查询精力    ┌─────────────┐
│ScheduleAgent│ ◀────────────▶ │ EnergyAgent │
└─────┬───────┘                └─────────────┘
      │ 
      ├─── 创建快照 ──▶ SnapshotManager
      │
      ├─── 执行操作 ──▶ Database
      │
      ▼
┌─────────────┐
│ MemoryAgent │  ← 异步更新用户习惯
└─────────────┘
```

### 4.3 RouterAgent 意图类别

```python
class Intent(str, Enum):
    # 日程操作
    CREATE_EVENT = "create_event"       # "帮我安排明天开会"
    QUERY_EVENT = "query_event"         # "我明天有什么安排"
    UPDATE_EVENT = "update_event"       # "把会议改到下午3点"
    DELETE_EVENT = "delete_event"       # "取消明天的会议"
    
    # 快照操作
    UNDO_CHANGE = "undo_change"         # "撤销上一次修改"
    RESTORE_SNAPSHOT = "restore_snapshot" # "恢复到之前的状态"
    
    # 精力相关
    CHECK_ENERGY = "check_energy"       # "我现在状态怎么样"
    SUGGEST_SCHEDULE = "suggest_schedule" # "帮我安排一下今天"
    
    # 查询统计
    GET_STATS = "get_stats"             # "这周我完成了多少任务"
    
    # 闲聊/其他
    CHITCHAT = "chitchat"               # 日常对话
    UNKNOWN = "unknown"                 # 无法识别
```

---

## 5. API 设计

### 5.1 对话式接口

```
POST /api/v1/chat
```

**请求体：**
```json
{
  "user_id": "uuid",
  "message": "帮我约明天下午3点开会，大概1小时",
  "context": {
    "channel": "wechat",
    "session_id": "optional"
  }
}
```

**响应体：**
```json
{
  "reply": "好的，已为您安排明天下午3点到4点的会议。精力预测显示这个时段您的状态不错。",
  "actions": [
    {
      "type": "create_event",
      "event_id": "uuid",
      "event": { ... }
    }
  ],
  "snapshot_id": "uuid"
}
```

### 5.2 RESTful 接口

#### 事件管理
```
GET    /api/v1/events              # 获取事件列表（支持筛选）
POST   /api/v1/events              # 创建事件
GET    /api/v1/events/{id}         # 获取单个事件
PUT    /api/v1/events/{id}         # 更新事件
DELETE /api/v1/events/{id}         # 删除事件
```

#### 用户管理
```
POST   /api/v1/users/register      # 注册
POST   /api/v1/users/login         # 登录
GET    /api/v1/users/me            # 获取当前用户信息
PUT    /api/v1/users/me            # 更新用户信息
PUT    /api/v1/users/me/energy     # 更新精力配置
```

#### 快照管理
```
GET    /api/v1/snapshots           # 获取快照列表
POST   /api/v1/snapshots/{id}/revert # 回退到指定快照
```

#### 统计数据
```
GET    /api/v1/stats/energy        # 获取精力统计
GET    /api/v1/stats/productivity  # 获取效率统计
GET    /api/v1/stats/time-saved    # 获取节省时间统计
```

---

## 6. Jarvis 人格配置

Jarvis 的人格通过 Prompt 文档配置，便于快速调整。

### 6.1 默认人格：高效秘书

```yaml
# jarvis_persona.yaml

persona:
  name: "Jarvis"
  role: "高效秘书"
  
  personality:
    - 专业且高效，注重执行力
    - 语气简洁明了，不啰嗦
    - 有适度的幽默感，但不过度
    - 尊重用户意愿，但会给出专业建议
    
  communication_style:
    tone: "professional_friendly"  # 专业友好
    verbosity: "concise"           # 简洁
    emoji_usage: "minimal"         # 少量使用
    
  behaviors:
    - 执行完任务后简短汇报结果
    - 检测到潜在问题时主动提醒
    - 给出建议时解释原因
    - 记住用户的偏好和习惯
    
  sample_responses:
    task_created: "好的，已安排。{event_summary}"
    conflict_detected: "检测到时间冲突。建议改到 {suggested_time}，那时你的精力更充沛。"
    energy_warning: "温馨提示：你已连续工作 3 小时，建议休息一下。"
    undo_confirm: "已撤销上次修改，日程已恢复。"
```

---

## 7. 开发计划

### 7.1 Phase 1：核心后端 (P0) — 2-3 周

| 任务 | 预估时间 | 产出 |
|------|----------|------|
| 项目初始化 (FastAPI + Supabase) | 2 天 | 基础项目结构 |
| 用户认证系统 | 2 天 | 注册/登录/JWT |
| Event CRUD API | 3 天 | 事件增删改查 |
| RouterAgent 实现 | 2 天 | 意图识别路由 |
| ScheduleAgent 实现 | 3 天 | 日程执行逻辑 |
| 快照系统 | 2 天 | 变更记录与回退 |
| chatgpt-on-wechat 集成 | 2 天 | 微信消息接入 |

### 7.2 Phase 2：精力系统 (P1) — 2 周

| 任务 | 预估时间 | 产出 |
|------|----------|------|
| EnergyAgent 实现 | 3 天 | 精力计算逻辑 |
| 精力配置 API | 1 天 | 用户精力设置 |
| E-U 排程算法 | 3 天 | 智能时间安排 |
| 疲劳检测 | 2 天 | 连续工作提醒 |
| MemoryAgent 基础版 | 3 天 | 习惯记录 |

### 7.3 Phase 3：生活控制台 (P3) — 1-2 周

| 任务 | 预估时间 | 产出 |
|------|----------|------|
| 统计 API | 2 天 | 各类数据统计 |
| 精力热力图数据 | 2 天 | 周维度精力分布 |
| 效率报告 | 2 天 | 时间节省等指标 |

### 7.4 Phase 4：A2A 社交 (P2) — 待定

> 需要积累用户基数后再启动

---

## 8. 验证计划

### 8.1 单元测试
- 使用 pytest 编写 Agent 逻辑测试
- 覆盖意图识别、日程排程、快照回退等核心场景

### 8.2 集成测试
- 端到端测试 `/chat` 接口
- 模拟多轮对话场景

### 8.3 手动测试
- 通过 WeChatBot 进行真实对话测试
- 验证各类自然语言指令的处理效果

---

## 附录 A：术语表

| 术语 | 定义 |
|------|------|
| **E-U 模型** | Energy-Urgency，基于精力和紧急度的排程模型 |
| **浮动任务** | 无固定时间约束，由 Agent 自动安排的任务 |
| **快照** | 日程变更的版本记录，支持回退 |
| **Agent** | 具备特定职责的 AI 模块 |
| **A2A** | Agent-to-Agent，用户 Agent 间的自动协商 |
