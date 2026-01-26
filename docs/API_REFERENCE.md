# UniLife API 接口文档

## 概述

本文档描述 UniLife 后端的所有 API 端点，包括现有的对话接口和计划中的新增端点。

**Base URL**: `http://localhost:8000` (开发环境)

**认证方式**：Bearer Token (JWT)

---

## 目录

- [1. 认证端点](#1-认证端点)
- [2. 对话端点](#2-对话端点)
- [3. 同步端点](#3-同步端点)
- [4. 事件管理端点](#4-事件管理端点)
- [5. 设备管理端点](#5-设备管理端点)
- [6. 微信端点](#6-微信端点)
- [7. 错误码](#7-错误码)
- [8. 数据模型](#8-数据模型)

---

## 1. 认证端点

### 1.1 用户注册

**端点**：`POST /api/v1/auth/register`

**请求**：
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "nickname": "string (required)",
  "user_id": "string (optional)",
  "email": "string (optional)",
  "timezone": "string (default: Asia/Shanghai)"
}
```

**响应**：
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 604800
}
```

**字段说明**：
- `expires_in`: Token 有效期（秒），默认 604800（7天）

### 1.2 用户登录

**端点**：`POST /api/v1/auth/login`

**请求**：
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "user_id": "string (required)"
}
```

**响应**：
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 604800
}
```

### 1.3 刷新 Token

**端点**：`POST /api/v1/auth/refresh`

**请求**：
```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "string (required)"
}
```

**响应**：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 604800
}
```

### 1.4 登出

**端点**：`POST /api/v1/auth/logout`

**请求头**：
```
Authorization: Bearer {access_token}
```

**响应**：
```json
{
  "success": true
}
```

---

## 2. 对话端点

### 2.1 发送消息

**端点**：`POST /api/v1/chat`

**请求**：
```http
POST /api/v1/chat
Content-Type: application/json
Authorization: Bearer {access_token} (可选)

{
  "user_id": "string (required)",
  "message": "string (required)",
  "conversation_id": "string (optional)",
  "current_time": "YYYY-MM-DD HH:MM:SS UTC (optional, 测试用)"
}
```

**响应**：
```json
{
  "reply": "排好了，明天下午3点开会（约1小时）",
  "actions": [
    {
      "type": "create_event",
      "event_id": "evt_123",
      "event": {
        "id": "evt_123",
        "title": "开会",
        "start_time": "2026-01-25T07:00:00Z",
        "end_time": "2026-01-25T08:00:00Z",
        "duration": 60
      }
    }
  ],
  "suggestions": [
    {
      "label": "明天上午8点",
      "value": "2026-01-25T00:00:00Z",
      "description": "2小时",
      "probability": 70
    },
    {
      "label": "自定义时间",
      "value": null,
      "description": "手动输入其他时间",
      "probability": 10
    }
  ],
  "conversation_id": "conv_456",
  "snapshot_id": "snap_789"
}
```

**字段说明**：
- `reply`: Agent 的自然语言回复
- `actions`: 执行的操作列表
- `suggestions`: 交互式选项（前端可渲染为按钮）
- `conversation_id`: 用于继续对话
- `snapshot_id`: 快照 ID（用于撤销操作）

### 2.2 获取对话历史

**端点**：`GET /api/v1/conversations/{id}/messages`

**请求头**：
```
Authorization: Bearer {access_token}
```

**查询参数**：
- `limit`: 每页消息数（默认 100）
- `offset`: 偏移量（默认 0）

**响应**：
```json
{
  "messages": [
    {
      "id": "msg_1",
      "role": "user",
      "content": "明天下午3点开会",
      "created_at": "2026-01-24T10:00:00Z"
    },
    {
      "id": "msg_2",
      "role": "assistant",
      "content": "排好了，明天下午3点开会（约1小时）",
      "created_at": "2026-01-24T10:00:01Z"
    }
  ],
  "total": 50,
  "limit": 100,
  "offset": 0
}
```

---

## 3. 同步端点

### 3.1 增量同步

**端点**：`GET /api/v1/sync`

**请求头**：
```
Authorization: Bearer {access_token}
```

**查询参数**：
- `since`: 起始时间戳（ISO 8601 格式）
- `include`: 包含的资源类型（逗号分隔，如 `events,routines`）
- `limit`: 每次返回的变更数量（默认 100）

**请求示例**：
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
      "created": [
        {
          "id": "evt_1",
          "title": "开会",
          "start_time": "2026-01-25T07:00:00Z",
          "end_time": "2026-01-25T08:00:00Z",
          "duration": 60,
          "status": "PENDING"
        }
      ],
      "updated": [
        {
          "id": "evt_2",
          "title": "健身",
          "start_time": "2026-01-26T07:00:00Z",
          "status": "COMPLETED"
        }
      ],
      "deleted": ["evt_3", "evt_4"]
    },
    "routines": {
      "created": [],
      "updated": [],
      "deleted": []
    }
  }
}
```

**字段说明**：
- `has_more`: 是否还有更多数据（分页）
- `changes`: 按资源类型分组的变更

---

## 4. 事件管理端点

### 4.1 获取今日日程

**端点**：`GET /api/v1/events/today`

**请求头**：
```
Authorization: Bearer {access_token}
```

**响应**：
```json
{
  "date": "2026-01-24",
  "events": [
    {
      "id": "evt_1",
      "title": "开会",
      "start_time": "2026-01-24T07:00:00Z",
      "end_time": "2026-01-24T08:00:00Z",
      "duration": 60,
      "status": "PENDING"
    }
  ],
  "routines": [
    {
      "id": "routine_1",
      "title": "健身",
      "template_id": "tpl_1",
      "is_flexible": true
    }
  ],
  "summary": {
    "total": 5,
    "completed": 2,
    "pending": 3
  }
}
```

### 4.2 快速创建事件

**端点**：`POST /api/v1/events/quick-add`

**请求头**：
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**请求**：
```json
{
  "title": "string (required)",
  "time": "string (required, 自然语言)",
  "duration": 60 (optional, 分钟)
}
```

**示例**：
```json
{
  "title": "开会",
  "time": "明天下午3点"
}
```

**响应**：
```json
{
  "event_id": "evt_123",
  "event": {
    "id": "evt_123",
    "title": "开会",
    "start_time": "2026-01-25T07:00:00Z",
    "end_time": "2026-01-25T08:00:00Z",
    "duration": 60
  }
}
```

### 4.3 延后事件

**端点**：`POST /api/v1/events/{id}/snooze`

**请求头**：
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**请求**：
```json
{
  "duration": 15 (必需, 延后分钟数)
}
```

**响应**：
```json
{
  "event_id": "evt_123",
  "new_start_time": "2026-01-25T07:15:00Z"
}
```

---

## 5. 设备管理端点

### 5.1 注册设备

**端点**：`POST /api/v1/devices/register`

**请求头**：
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**请求**：
```json
{
  "platform": "ios|android (required)",
  "token": "string (required, device token)",
  "metadata": {
    "model": "iPhone 14",
    "os_version": "17.2"
  }
}
```

**响应**：
```json
{
  "device_id": "dev_123",
  "registered_at": "2026-01-24T12:00:00Z"
}
```

### 5.2 获取用户设备列表

**端点**：`GET /api/v1/devices`

**请求头**：
```
Authorization: Bearer {access_token}
```

**响应**：
```json
{
  "devices": [
    {
      "id": "dev_123",
      "platform": "ios",
      "token": "****masked****",
      "metadata": {
        "model": "iPhone 14",
        "os_version": "17.2"
      },
      "created_at": "2026-01-24T12:00:00Z"
    }
  ]
}
```

### 5.3 删除设备

**端点**：`DELETE /api/v1/devices/{id}`

**请求头**：
```
Authorization: Bearer {access_token}
```

**响应**：
```json
{
  "success": true
}
```

---

## 6. 微信端点（可选）

### 6.1 Webhook 回调

**端点**：`POST /api/v1/wechat/webhook`

**请求**：
```json
{
  "message_type": "text|forwarded",
  "user_id": "wechat_user_123",
  "content": "string",
  "forwarded_content": "string (仅转发消息)",
  "timestamp": "2026-01-24T12:00:00Z"
}
```

**响应**：
```json
{
  "reply": "AI 回复内容"
}
```

---

## 7. 错误码

| 错误码 | 说明 | 示例 |
|--------|------|------|
| 200 | 成功 | 请求成功 |
| 400 | 请求参数错误 | 缺少必需字段 |
| 401 | 未认证 | Token 无效或过期 |
| 403 | 无权限 | 无法访问该资源 |
| 404 | 资源不存在 | 事件不存在 |
| 409 | 资源冲突 | 时间冲突 |
| 429 | 请求过于频繁 | 触发速率限制 |
| 500 | 服务器错误 | 内部错误 |

### 7.1 错误响应格式

```json
{
  "error": {
    "code": 400,
    "message": "Missing required field: title",
    "details": {
      "field": "title",
      "constraint": "required"
    }
  }
}
```

---

## 8. 数据模型

### 8.1 Event（事件）

```json
{
  "id": "string",
  "title": "string",
  "description": "string (optional)",
  "start_time": "ISO 8601 datetime",
  "end_time": "ISO 8601 datetime",
  "duration": "integer (minutes)",
  "status": "PENDING|IN_PROGRESS|COMPLETED|CANCELLED",
  "event_type": "schedule|deadline|floating|habit|reminder",
  "category": "WORK|STUDY|SOCIAL|LIFE|HEALTH",
  "energy_required": "HIGH|MEDIUM|LOW",
  "urgency": "integer (1-5)",
  "importance": "integer (1-5)",
  "tags": ["string"],
  "location": "string (optional)",
  "participants": ["string"],
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

### 8.2 Suggestion（选项）

```json
{
  "label": "显示给用户的标签",
  "value": "实际值（null=需要手动输入）",
  "description": "详细描述",
  "probability": "integer (0-100, AI 预测的概率)"
}
```

### 8.3 ActionResult（操作结果）

```json
{
  "type": "create_event|update_event|delete_event",
  "event_id": "string",
  "event": { /* Event 对象 */ }
}
```

---

## 9. 使用示例

### 9.1 登录并获取今日日程

```bash
# 1. 登录
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123"}' \
  | jq -r '.access_token')

# 2. 获取今日日程
curl -X GET http://localhost:8000/api/v1/events/today \
  -H "Authorization: Bearer $TOKEN"
```

### 9.2 Swift 示例

```swift
// 登录
let loginData = ["user_id": "user123"]
let loginResponse = try await api.post("/api/v1/auth/login", body: loginData)
let token = loginResponse["access_token"] as! String

// 获取今日日程
let todayResponse = try await api.get("/api/v1/events/today", token: token)
let events = todayResponse["events"] as! [[String: Any]]

// 发送消息
let chatData = [
    "user_id": userId,
    "message": "明天下午3点开会"
]
let chatResponse = try await api.post("/api/v1/chat", body: chatData, token: token)
let reply = chatResponse["reply"] as! String
```

---

## 10. 开发与测试

### 10.1 本地测试

```bash
# 启动服务
uvicorn app.main:app --reload

# 运行测试
pytest
```

### 10.2 API 文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
