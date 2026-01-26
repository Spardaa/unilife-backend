# UniLife 时间处理设计文档

## 概述

本文档描述 UniLife 后端的时间处理机制，包括当前存在的问题、设计策略、以及修复方案。

**核心原则**：UTC 存储，用户时区显示

---

## 1. 当前问题分析

### 1.1 问题清单

| 问题 | 文件 | 行号 | 影响 | 严重程度 |
|------|------|------|------|----------|
| `render_with_profile()` 不支持虚拟时间 | `app/services/prompt.py` | 138 | 测试时无法使用虚拟时间 | 中 |
| 时间解析无时区 | `app/services/time_parser.py` | 81 | 跨时区部署时间错乱 | 高 |
| Prompt 时间无时区标注 | `app/agents/executor.py` | 157, 165 | LLM 无法判断时区，理解偏差 | 中 |
| 数据库存储 naive datetime | `app/services/db.py` | 109-110 | 夏令时切换可能出错 | 高 |
| 时区剥离代码 | `app/services/db.py` | 461-468 | 跨时区用户冲突检测失效 | 高 |

### 1.2 详细问题描述

#### 问题 1：虚拟时间失效

**代码位置**：`app/services/prompt.py:138`

```python
def render_with_profile(
    self,
    template_name: str,
    user_profile: Optional[Dict[str, Any]] = None,
    user_decision_profile: Optional[Dict[str, Any]] = None,
    **extra_variables
) -> str:
    # ...
    variables["current_time"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
```

**问题**：函数不接受外部传入的 `current_time` 参数，导致 Executor/Persona 传入的虚拟时间被忽略。

**影响**：测试时无法模拟特定时间场景。

#### 问题 2：时间解析无时区

**代码位置**：`app/services/time_parser.py:81`

```python
if reference_date is None:
    reference_date = datetime.now()  # 无时区信息
```

**问题**：使用本地时间但无时区标注，在跨时区部署时会产生混乱。

#### 问题 3：Prompt 时间无标注

**代码位置**：`app/agents/executor.py:157`

```python
current_time = context.current_time or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
```

**问题**：时间格式为 `2026-01-24 15:00:00`，没有标注是 UTC 时间，LLM 无法判断。

#### 问题 4：数据库存储 naive datetime

**代码位置**：`app/services/db.py:109-110`

```python
start_time = Column(DateTime, nullable=True)
end_time = Column(DateTime, nullable=True)
```

**问题**：SQLAlchemy 的 `DateTime` 默认不带时区，存储的是 naive datetime。

#### 问题 5：主动剥离时区

**代码位置**：`app/services/db.py:461-468`

```python
if event_start and hasattr(event_start, 'tzinfo') and event_start.tzinfo is not None:
    event_start = event_start.replace(tzinfo=None)
```

**问题**：主动删除时区信息，导致跨时区用户的时间冲突检测不准确。

---

## 2. 时区策略设计

### 2.1 核心原则

**UTC 存储，用户时区显示**

```
┌─────────────┐     输入    ┌─────────────┐
│   用户      │ ──────────> │  TimeParser │
│ Asia/Shanghai│             │             │
└─────────────┘             └──────┬──────┘
                                   │
                                   v
                            ┌─────────────┐
                            │   转为 UTC   │
                            │   存储      │
                            └─────────────┘
                                   │
                                   v
                            ┌─────────────┐
                            │  数据库     │
                            │  (UTC)      │
                            └─────────────┘
                                   │
                                   v
                            ┌─────────────┐
                            │  读取时     │
                            │  转用户时区  │
                            └─────────────┘
                                   │
                                   v
                            ┌─────────────┐
                            │  前端显示   │
                            │ Asia/Shanghai│
                            └─────────────┘
```

### 2.2 设计规范

| 层级 | 时区处理 | 格式示例 |
|------|----------|----------|
| **用户输入** | 用户时区 | "明天下午3点" |
| **解析** | 转为 UTC | `2026-01-25T07:00:00Z` |
| **存储** | UTC | `2026-01-25T07:00:00Z` (naive 或 aware) |
| **API 响应** | UTC (ISO 8601) | `2026-01-25T07:00:00Z` |
| **Prompt 传递** | UTC + 标注 | `2026-01-25 15:00:00 UTC` |
| **前端显示** | 用户时区 | `15:00 开会（约1小时）` |

### 2.3 ISO 8601 格式

**推荐格式**：
```json
{
  "start_time": "2026-01-25T07:00:00Z",
  "end_time": "2026-01-25T08:00:00Z"
}
```

**格式说明**：
- `T` 分隔日期和时间
- `Z` 表示 UTC 时区
- 明确、可解析、跨语言兼容

---

## 3. 时间解析机制（TimeParser）

### 3.1 设计目标

```python
# 输入：自然语言时间 + 用户时区
time_parser.parse("明天下午3点", timezone="Asia/Shanghai")

# 输出：UTC 时间字符串（ISO 8601）
"2026-01-25T07:00:00Z"
```

### 3.2 处理流程

```
1. 获取当前 UTC 时间
   datetime.now(timezone.utc)

2. 转换到用户时区
   utc_time.astimezone(user_timezone)

3. 解析相对时间（"明天"）
   计算相对于当前日期的偏移

4. 解析具体时间（"下午3点"）
   提取小时、分钟

5. 转换回 UTC 存储
   user_local_time.astimezone(timezone.utc)
```

### 3.3 支持的时间表达

| 类型 | 示例 | 解析结果 |
|------|------|----------|
| 精确时间 | "明天下午3点" | 明天 15:00 |
| 相对日期 | "后天" | 今天+2天 |
| 星期几 | "下周三" | 下个周三 |
| 模糊时间 | "傍晚" | 17:00-19:00 |
| 时间范围 | "本周三到周五" | 起止时间 |

---

## 4. Prompt 时间传递规范

### 4.1 规范格式

**修复前**：
```
当前时间：2026-01-24 15:00:00
```

**修复后**：
```
当前时间：2026-01-24 15:00:00 UTC
用户时区：Asia/Shanghai (UTC+8)
用户本地时间：2026-01-24 23:00:00
```

### 4.2 虚拟时间支持

**用途**：测试时模拟特定时间

**格式**：
```http
POST /api/v1/chat
{
  "user_id": "test",
  "message": "现在几点了？",
  "current_time": "2026-01-25 15:00:00 UTC"
}
```

**传递链路**：
```
API Request → Orchestrator.context → Executor → render_with_profile()
```

### 4.3 修复方案

**文件**：`app/services/prompt.py`

```python
def render_with_profile(
    self,
    template_name: str,
    user_profile: Optional[Dict[str, Any]] = None,
    user_decision_profile: Optional[Dict[str, Any]] = None,
    current_time: Optional[str] = None,  # 新增参数
    **extra_variables
) -> str:
    # ...
    # 优先使用传入的 current_time，否则使用 UTC 时间并标注
    if current_time:
        variables["current_time"] = current_time
    else:
        variables["current_time"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
```

---

## 5. 前端时间显示格式

### 5.1 双时间架构显示

**柔性显示（前端）**：
```
10:00 开会（约1小时，到11:00左右）
```

**刚性存储（后端）**：
```json
{
  "start_time": "2026-01-25T02:00:00Z",
  "end_time": "2026-01-25T03:00:00Z",
  "duration": 60,
  "duration_source": "ai_estimate",
  "duration_confidence": 0.7
}
```

### 5.2 前端处理建议

```swift
// Swift 示例
let utcTime = event.start_time // ISO 8601 格式
let dateFormatter = ISO8601DateFormatter()
let date = dateFormatter.date(from: utcTime)!

// 转换到用户时区
let userTimeZone = TimeZone(identifier: "Asia/Shanghai")!
let userCalendar = Calendar.current
userCalendar.timeZone = userTimeZone

// 格式化显示
let displayFormatter = DateFormatter()
displayFormatter.timeZone = userTimeZone
displayFormatter.dateFormat = "HH:mm"
let displayTime = displayFormatter.string(from: date)

// 输出: "15:00"
```

---

## 6. 数据库时间字段设计

### 6.1 当前状态

**SQLite**：
```python
start_time = Column(DateTime, nullable=True)
```

**PostgreSQL**：
```python
start_time = Column(DateTime(timezone=True), nullable=True)
```

### 6.2 推荐方案

**应用层统一处理**：
1. 存储时：所有时间转换为 UTC
2. 读取时：保持 UTC 格式（ISO 8601）
3. 显示时：前端根据用户时区转换

**优势**：
- 与数据库无关
- 迁移成本低
- 前端灵活控制

### 6.3 用户时区存储

**用户模型**：`app/models/user.py`

```python
timezone: str = Field(default="Asia/Shanghai", description="User timezone")
```

**使用方式**：
```python
# 获取用户时区
user = db_service.get_user(user_id)
user_tz = pytz.timezone(user.timezone)

# 时间解析时传入
parsed_time = time_parser.parse("明天下午3点", timezone=user_tz)
```

---

## 7. 修复优先级和步骤

### 7.1 优先级

| 优先级 | 问题 | 预估时间 |
|--------|------|----------|
| **高** | 时间解析无时区 | 30 分钟 |
| **高** | Prompt 时间无标注 | 15 分钟 |
| **高** | 时区剥离代码 | 15 分钟 |
| **中** | 虚拟时间支持 | 30 分钟 |

### 7.2 修复步骤

#### 步骤 1：修复 Prompt 时间标注

**文件**：`app/agents/executor.py`, `app/agents/persona.py`

```python
# 修改前
current_time = context.current_time or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

# 修改后
current_time = context.current_time or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
```

#### 步骤 2：修复 PromptService 支持虚拟时间

**文件**：`app/services/prompt.py`

```python
def render_with_profile(
    self,
    template_name: str,
    user_profile: Optional[Dict[str, Any]] = None,
    user_decision_profile: Optional[Dict[str, Any]] = None,
    current_time: Optional[str] = None,  # 新增
    **extra_variables
) -> str:
    # ...
    if current_time:
        variables["current_time"] = current_time
    else:
        variables["current_time"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
```

#### 步骤 3：修复时间解析时区

**文件**：`app/services/time_parser.py`

```python
from datetime import timezone

if reference_date is None:
    reference_date = datetime.now(timezone.utc)
```

#### 步骤 4：删除时区剥离代码

**文件**：`app/services/db.py`

```python
# 删除或修改 Line 461-468
# 改用时区感知的比较
```

---

## 8. 验证方式

### 8.1 单元测试

```bash
pytest test_dual_time_architecture.py
```

### 8.2 手动测试

**虚拟时间测试**：
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test",
    "message": "现在几点了？",
    "current_time": "2026-01-25 15:00:00 UTC"
  }'
```

**预期结果**：AI 应该知道当前是 2026-01-25 15:00 UTC

### 8.3 跨时区测试

```bash
# 创建用户（时区：Asia/Tokyo）
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"nickname": "Tokyo User", "timezone": "Asia/Tokyo"}'

# 创建日程
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "{user_id}",
    "message": "明天下午3点开会"
  }'

# 验证返回的 start_time 是 UTC 时间
```

---

## 9. 关键文件路径

| 文件 | 行号 | 修改内容 |
|------|------|----------|
| `app/services/prompt.py` | 138 | 添加 `current_time` 参数 |
| `app/services/time_parser.py` | 81 | 使用 `datetime.now(timezone.utc)` |
| `app/agents/executor.py` | 157, 165 | 添加 UTC 标注 |
| `app/agents/persona.py` | 109, 117 | 添加 UTC 标注 |
| `app/services/db.py` | 461-468 | 删除时区剥离代码 |

---

## 10. 参考资料

- [Python datetime 时区处理](https://docs.python.org/3/library/datetime.html)
- [ISO 8601 标准](https://en.wikipedia.org/wiki/ISO_8601)
- [pytz 文档](https://pythonhosted.org/pytz/)
