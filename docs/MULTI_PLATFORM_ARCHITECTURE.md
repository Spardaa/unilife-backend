# UniLife 多平台架构设计文档

## 概述

本文档描述 UniLife 后端的多平台接入架构，采用**混合方案**：核心 API 共用 + 平台特定端点。

**前端类型**：
- 微信机器人（chatgpt-on-wechat）
- iOS 应用

---

## 1. 架构总览

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                    UniLife 后端                          │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   核心 API   │  │  平台特定API │  │  内部工具    │  │
│  │              │  │              │  │              │  │
│  │ /api/v1/chat│  │ /api/v1/auth │  │ Agent 编排   │  │
│  │ /api/v1/sync│  │ /api/v1/dev  │  │ Prompt 模板  │  │
│  │              │  │ /api/v1/wechat│ │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│         │                 │                 │          │
└─────────┼─────────────────┼─────────────────┼──────────┘
          │                 │                 │
    ┌─────┴─────┐     ┌────┴────┐      ┌────┴────┐
    │  微信前端  │     │ iOS 前端│      │  测试端  │
    └───────────┘     └─────────┘      └─────────┘
```

### 1.2 混合方案设计

#### 核心 API（共用）

| 端点 | 用途 | 支持平台 |
|------|------|----------|
| `/api/v1/chat` | 对话式接口 | 所有平台 |
| `/api/v1/sync` | 增量同步 | iOS, Web |
| `/api/v1/conversations` | 对话管理 | 所有平台 |

#### 平台特定 API

| 端点 | 用途 | 支持平台 |
|------|------|----------|
| `/api/v1/auth/*` | 认证系统 | iOS |
| `/api/v1/devices/*` | 设备管理 | iOS |
| `/api/v1/wechat/*` | 微信接入 | 微信 |

---

## 2. 4 层 Agent 架构

### 2.1 架构图

```
用户消息 → Orchestrator
                    ↓
        ┌───────────┼───────────┐
        ↓           ↓           ↓
    Router     Executor     Persona
   (意图)     (工具)       (共情)
        │           │           │
        └───────────┼───────────┘
                    ↓
            Response (同步)
                    ↓
            Observer (异步)
                    ↓
        更新用户画像
```

### 2.2 多平台场景下的应用

#### 微信机器人

```
┌─────────┐    文字消息    ┌──────────────┐
│ 用户    │ ────────────> │ chatgpt-on-  │
└─────────┘               │ wechat       │
                          └──────┬───────┘
                                 │
                                 v
┌──────────────────────────────────────────┐
│            /api/v1/chat                   │
│  - Router: 识别意图                      │
│  - Executor: 调用工具                    │
│  - Persona: 生成回复                     │
└──────────────────────────────────────────┘
                                 │
                                 v
                          ┌──────────────┐
                          │ 文字回复      │
                          └──────────────┘
```

#### iOS 应用

```
┌─────────┐    UI 操作     ┌──────────────┐
│ 用户    │ ────────────> │  iOS App     │
└─────────┘               └──────┬───────┘
                                 │
                ┌────────────────┴────────────────┐
                v                                 v
┌──────────────────────┐         ┌──────────────────────┐
│   认证流程            │         │   /api/v1/chat       │
│   /api/v1/auth/login  │         │   - 对话式操作        │
└──────────┬───────────┘         └──────────────────────┘
           │
           v
┌──────────────────────┐
│   增量同步            │
│   /api/v1/sync        │
└──────────────────────┘
```

### 2.3 Agent 职责

| Agent | 职责 | 多平台适配 |
|-------|------|------------|
| **Router** | 意图分类，上下文过滤 | 无需适配 |
| **Executor** | 工具执行，决策偏好注入 | 注入平台特定偏好 |
| **Persona** | 拟人化回复 | 根据平台调整回复风格 |
| **Observer** | 画像学习 | 记录平台特定行为模式 |

---

## 3. 认证系统设计

### 3.1 方案选择

**JWT Token 认证**

```
┌─────────┐     登录/注册      ┌─────────┐
│ 前端App │ ─────────────────> │ 后端API │
└─────────┘                     └─────────┘
                                返回 JWT
                                   │
                                   v
                            ┌─────────┐
                            │ 前端存储│
                            └─────────┘
                                   │
                              后续请求携带
                              Authorization: Bearer
```

### 3.2 Token 生命周期

| Token 类型 | 有效期 | 用途 |
|------------|--------|------|
| Access Token | 7 天 | API 访问 |
| Refresh Token | 30 天 | 刷新 Access Token |

### 3.3 认证流程

```
1. 用户注册/登录
   POST /api/v1/auth/register
   POST /api/v1/auth/login

2. 返回 Token
   {
     "access_token": "...",
     "refresh_token": "...",
     "expires_in": 604800
   }

3. 前端存储 Token
   - iOS: Keychain
   - 微信: 内存（无需持久化）

4. 每次请求携带
   Authorization: Bearer {access_token}

5. Token 过期时刷新
   POST /api/v1/auth/refresh
```

### 3.4 平台差异

| 平台 | 认证方式 | Token 存储 |
|------|----------|-----------|
| **iOS** | JWT Token | Keychain（持久化） |
| **微信** | 无需认证（wechat_id） | 内存（无需持久化） |
| **Web** | JWT Token | LocalStorage / Cookie |

---

## 4. 数据同步策略

### 4.1 增量同步设计

```
┌─────────┐     首次同步     ┌─────────┐
│ iOS App │ ─────────────> │ 后端API │
└─────────┘                 └─────────┘
     │                           │
     │ 首次获取全量数据          │
     v                           v
┌─────────┐                 ┌─────────┐
│ 本地存储 │ <───────────── │ 全量数据 │
└─────────┘                 └─────────┘

┌─────────┐     增量同步     ┌─────────┐
│ iOS App │ <────────────> │ 后端API │
└─────────┐  (since上次同步)  └─────────┘
```

### 4.2 同步端点

**请求**：
```http
GET /api/v1/sync?since=2026-01-24T00:00:00Z&include=events,routines
```

**响应**：
```json
{
  "since": "2026-01-24T00:00:00Z",
  "until": "2026-01-24T12:00:00Z",
  "has_more": false,
  "changes": {
    "events": {
      "created": [...],
      "updated": [...],
      "deleted": ["id1", "id2"]
    }
  }
}
```

### 4.3 离线支持

**策略**：乐观锁 + 冲突检测

```
1. 用户离线操作
   - 本地创建/修改事件
   - 记录操作日志

2. 重新连接时同步
   - 上传本地变更
   - 检测冲突

3. 冲突解决
   - 时间冲突：提示用户
   - 版本冲突：服务器版本优先
```

---

## 5. 时区处理策略

### 5.1 设计原则

**UTC 存储，用户时区显示**

```
用户输入（Asia/Shanghai）
    ↓
解析为 UTC
    ↓
存储（数据库 UTC）
    ↓
API 返回（ISO 8601 UTC）
    ↓
前端转换显示（用户时区）
```

### 5.2 时区传递链路

```
┌──────────┐    用户时区    ┌─────────────┐
│ 用户设置 │ ────────────> │  User Model │
└──────────┘               └─────────────┘
                                │
                                v
                         ┌─────────────┐
                         │ TimeParser   │
                         │ 转换为 UTC    │
                         └─────────────┘
                                │
                                v
                         ┌─────────────┐
                         │ 数据库      │
                         │ UTC 存储     │
                         └─────────────┘
```

### 5.3 前端显示转换

```swift
// Swift 示例
let utcTime = event.start_time  // ISO 8601
let formatter = ISO8601DateFormatter()
let date = formatter.date(from: utcTime)!

// 转换到用户时区
let userTimeZone = TimeZone(identifier: "Asia/Shanghai")!
let userCalendar = Calendar.current
userCalendar.timeZone = userTimeZone

// 格式化显示
let displayFormatter = DateFormatter()
displayFormatter.timeZone = userTimeZone
displayFormatter.dateFormat = "HH:mm"
let displayTime = displayFormatter.string(from: date)
```

---

## 6. 微信转发消息处理

### 6.1 处理流程

```
┌─────────┐    转发消息    ┌──────────────┐
│ 用户    │ ────────────> │ 微信接入层   │
└─────────┘               └──────┬───────┘
                               │
                               v
                        ┌──────────────┐
                        │ 前端预处理    │
                        │ - 识别转发    │
                        │ - 提取内容    │
                        │ - 添加标记    │
                        └──────┬───────┘
                               │
                               v
┌──────────────────────────────────────────┐
│          Router Agent                    │
│  - 检测 forwarded: true 标记             │
│  - 路由到专用处理流程                    │
└──────────────────────────────────────────┘
                               │
                               v
┌──────────────────────────────────────────┐
│   Executor + parse_forwarded_message     │
│  - 使用专用 prompt 解析转发内容           │
│  - 提取日程信息                          │
└──────────────────────────────────────────┘
```

### 6.2 数据结构

**转发消息请求**：
```json
{
  "message_type": "forwarded",
  "user_id": "wechat_user_123",
  "original_sender": "friend_name",
  "content": "转发的内容...",
  "timestamp": "2026-01-24T12:00:00Z"
}
```

### 6.3 新增工具

```python
tool_registry.register(
    name="parse_forwarded_message",
    description="解析用户转发的消息，提取其中可能包含的日程信息",
    parameters={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "转发消息的内容"
            },
            "original_sender": {
                "type": "string",
                "description": "原始发送者"
            }
        },
        "required": ["content"]
    },
    func=tool_parse_forwarded_message
)
```

---

## 7. 推送通知系统

### 7.1 架构设计

```
┌─────────────┐      注册设备       ┌──────────────┐
│  iOS App    │ ──────────────────> │  后端 API    │
│             │                     │              │
└─────────────┘                     └──────┬───────┘
                                          │
                                          v
                                   ┌──────────────┐
                                   │ 设备 Token   │
                                   │ 存储         │
                                   └──────────────┘
                                          │
                              ┌───────────┴───────────┐
                              v                       v
                      ┌──────────────┐       ┌──────────────┐
                      │ 后台定时任务  │       │ 事件触发     │
                      │ - 每日总结   │       │ - 15分钟提醒│
                      │ - 习惯打卡  │       │              │
                      └──────┬───────┘       └──────┬───────┘
                             │                      │
                             v                      v
                      ┌──────────────┐       ┌──────────────┐
                      │ 推送服务     │─────>│ APNs 服务    │
                      │ - 统一接口   │       │              │
                      │ - 多渠道支持│       └──────────────┘
                      └──────────────┘
```

### 7.2 推送类型

| 类型 | 触发时机 | 内容 |
|------|----------|------|
| **日程提醒** | 开始前 15 分钟 | "15分钟后开会" |
| **习惯打卡** | 每日约定时间 | "今天的阅读还没完成哦" |
| **灵活时间确认** | 习惯未安排时间 | "今天的健身还没安排，想什么时候做？" |
| **每日总结** | 每晚 22:00 | "今天完成了 3 个日程，坚持得不错！" |

### 7.3 推送服务抽象

```python
class PushService:
    async def send_notification(
        self,
        user_id: str,
        title: str,
        body: str,
        data: dict = None
    ):
        # 根据用户平台选择推送渠道
        devices = self.get_user_devices(user_id)

        for device in devices:
            if device.platform == "ios":
                await self.send_apns(device.token, title, body, data)
            elif device.platform == "android":
                await self.send_fcm(device.token, title, body, data)
```

---

## 8. 平台特定适配

### 8.1 iOS 适配

**需求**：
- 认证系统
- 增量同步
- 推送通知
- 快捷操作

**API 端点**：
- `/api/v1/auth/*` - 认证
- `/api/v1/sync` - 同步
- `/api/v1/devices/*` - 推送
- `/api/v1/events/today` - 快捷操作

### 8.2 微信适配

**需求**：
- 无需认证（使用 wechat_id）
- 转发消息处理
- 自然语言交互

**API 端点**：
- `/api/v1/chat` - 对话（共用）
- `/api/v1/wechat/webhook` - Webhook（可选）

### 8.3 适配差异

| 特性 | iOS | 微信 |
|------|-----|------|
| 认证 | JWT Token | wechat_id |
| 同步 | 增量同步 | 无需同步 |
| 推送 | APNs | 模板消息（可选） |
| UI | 按钮 + 输入 | 纯文字 |

---

## 9. 数据模型扩展

### 9.1 用户模型

```python
class User(BaseModel):
    id: str
    wechat_id: Optional[str]
    email: Optional[str]
    timezone: str = "Asia/Shanghai"
    device_tokens: List[str] = []  # 新增
    created_at: datetime
    updated_at: datetime
```

### 9.2 设备模型

```python
class Device(BaseModel):
    id: str
    user_id: str
    platform: str  # ios, android
    token: str
    metadata: dict
    created_at: datetime
```

---

## 10. 部署架构

### 10.1 生产环境

```
┌─────────────────────────────────────────┐
│              CDN / 负载均衡              │
└──────────────┬──────────────────────────┘
               │
      ┌────────┴────────┐
      v                 v
┌──────────┐      ┌──────────┐
│ 后端实例1 │      │ 后端实例2 │
│          │      │          │
└────┬─────┘      └────┬─────┘
     │                 │
     v                 v
┌─────────────────────────────┐
│      PostgreSQL 数据库      │
└─────────────────────────────┘
```

### 10.2 服务依赖

| 服务 | 用途 |
|------|------|
| **DeepSeek API** | LLM 推理 |
| **PostgreSQL** | 数据存储 |
| **Redis** | 缓存（可选） |
| **APNs** | iOS 推送 |

---

## 11. 关键文件路径

| 模块 | 文件 |
|------|------|
| **Agent 编排** | `app/agents/orchestrator.py` |
| **Agent 实现** | `app/agents/router.py`, `executor.py`, `persona.py`, `observer.py` |
| **工具注册** | `app/agents/tools.py` |
| **Prompt 模板** | `prompts/agents/*.txt` |
| **API 端点** | `app/api/*.py` |
| **认证** | `app/api/auth.py` (新增) |
| **同步** | `app/api/sync.py` (新增) |
| **设备** | `app/api/devices.py` (新增) |
