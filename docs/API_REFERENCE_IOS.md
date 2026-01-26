# UniLife API 参考文档 - iOS 前端开发

> 更新时间：2026-01-24
> 后端版本：Phase 2.5（新增 CRUD API）

---

## 快速开始

### Base URL
- 开发环境：`http://localhost:8000`
- 生产环境：待配置

### 认证方式
所有需要认证的请求都需要在 Header 中携带 JWT Token：
```
Authorization: Bearer <access_token>
```

### 交互式 API 文档
- Swagger UI：`http://localhost:8000/docs`
- ReDoc：`http://localhost:8000/redoc`

---

## API 端点列表

### 1. 认证 (Authentication)

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 用户注册 |
| POST | `/api/v1/auth/login` | 用户登录 |
| POST | `/api/v1/auth/refresh` | 刷新 Token |

#### 1.1 登录

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "user_id": "string"
}
```

**响应**：
```json
{
  "user_id": "uuid (数据库主键)",
  "access_token": "eyJhbG...",
  "refresh_token": "eyJhbG...",
  "expires_in": 604800
}
```

**Swift 示例**：
```swift
struct LoginRequest: Codable {
    let user_id: String
}

struct LoginResponse: Codable {
    let user_id: String
    let access_token: String
    let refresh_token: String
    let expires_in: Int
}

func login(userId: String) async throws -> LoginResponse {
    let request = LoginRequest(user_id: userId)
    let url = URL(string: "\(baseURL)/api/v1/auth/login")!
    var urlRequest = URLRequest(url: url)
    urlRequest.httpMethod = "POST"
    urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
    urlRequest.httpBody = try JSONEncoder().encode(request)

    let (data, _) = try await URLSession.shared.data(for: urlRequest)
    return try JSONDecoder().decode(LoginResponse.self, from: data)
}
```

---

### 2. 用户管理 (Users)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/users/me` | 获取当前用户信息 |
| PUT | `/api/v1/users/me` | 更新用户资料 |
| PUT | `/api/v1/users/me/energy` | 更新精力配置 |
| GET | `/api/v1/users/me/stats` | 获取用户统计 |
| GET | `/api/v1/users/me/profile` | 获取完整用户画像 |

#### 2.1 获取当前用户信息

```http
GET /api/v1/users/me
Authorization: Bearer <token>
```

**响应**：
```json
{
  "id": "uuid",
  "user_id": "test_user",
  "nickname": "测试用户",
  "timezone": "Asia/Shanghai",
  "email": null,
  "phone": null,
  "avatar_url": null,
  "current_energy": 100,
  "energy_profile": {
    "hourly_baseline": {
      "6": 40, "7": 50, "8": 70, "9": 80,
      "10": 90, "11": 85, "12": 70, "13": 65,
      "14": 60, "15": 70, "16": 75, "17": 65,
      "18": 60, "19": 55, "20": 50, "21": 40,
      "22": 30, "23": 20
    },
    "task_energy_cost": {
      "deep_work": -20, "meeting": -10,
      "study": -15, "break": 15, "coffee": 10,
      "sleep": 100
    },
    "learned_adjustments": {}
  },
  "preferences": {
    "notification_enabled": true,
    "auto_schedule_enabled": true,
    "energy_based_scheduling": true,
    "working_hours_start": 9,
    "working_hours_end": 18
  },
  "created_at": "2026-01-24T14:54:58.999326",
  "last_active_at": "2026-01-24T14:54:58.999329"
}
```

#### 2.2 更新用户资料

```http
PUT /api/v1/users/me
Content-Type: application/json
Authorization: Bearer <token>

{
  "nickname": "新昵称",
  "timezone": "Asia/Shanghai"
}
```

#### 2.3 获取用户统计

```http
GET /api/v1/users/me/stats
Authorization: Bearer <token>
```

**响应**：
```json
{
  "user_id": "test_user",
  "total_events": 5,
  "pending_events": 3,
  "completed_events": 2,
  "cancelled_events": 0,
  "events_by_category": {
    "WORK": 3,
    "STUDY": 2
  },
  "events_by_type": {
    "schedule": 4,
    "deadline": 1
  },
  "profile_points": 12,
  "last_active_at": "2026-01-24T14:54:58.999329",
  "created_at": "2026-01-24T14:54:58.999326"
}
```

---

### 3. 事件管理 (Events)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/events` | 获取事件列表 |
| GET | `/api/v1/events/today` | 获取今日事件 |
| GET | `/api/v1/events/{id}` | 获取单个事件 |
| POST | `/api/v1/events` | 创建事件 |
| PUT | `/api/v1/events/{id}` | 更新事件 |
| DELETE | `/api/v1/events/{id}` | 删除事件 |
| POST | `/api/v1/events/{id}/complete` | 标记事件为完成 |
| GET | `/api/v1/events/conflicts` | 检查时间冲突 |

#### 3.1 获取事件列表

```http
GET /api/v1/events
Authorization: Bearer <token>

# 可选查询参数:
?start_date=2026-01-24T00:00:00Z
&end_date=2026-01-25T23:59:59Z
&status=PENDING
&event_type=schedule
&category=WORK
&limit=100
```

**响应**：
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "title": "开会",
    "description": "团队周会",
    "start_time": "2026-01-25T10:00:00",
    "end_time": null,
    "duration": 60,
    "energy_required": "MEDIUM",
    "urgency": 3,
    "importance": 3,
    "is_deep_work": false,
    "event_type": "floating",
    "category": "WORK",
    "tags": [],
    "location": null,
    "participants": [],
    "status": "PENDING",
    "created_at": "2026-01-24T14:54:59.103227",
    "updated_at": "2026-01-24T14:54:59.103229",
    "created_by": "user",
    "ai_confidence": 1.0
  }
]
```

#### 3.2 创建事件

```http
POST /api/v1/events
Content-Type: application/json
Authorization: Bearer <token>

{
  "title": "开会",
  "description": "团队周会",
  "start_time": "2026-01-25T10:00:00Z",
  "duration": 60,
  "event_type": "schedule",
  "category": "WORK"
}
```

**字段说明**：
- `event_type`: `schedule`, `deadline`, `floating`, `habit`, `reminder`
- `category`: `STUDY`, `WORK`, `SOCIAL`, `LIFE`, `HEALTH`
- `energy_required`: `HIGH`, `MEDIUM`, `LOW`
- `urgency`: 1-5 (紧急程度)
- `importance`: 1-5 (重要程度)

#### 3.3 更新事件

```http
PUT /api/v1/events/{event_id}
Content-Type: application/json
Authorization: Bearer <token>

{
  "title": "新标题",
  "start_time": "2026-01-25T14:00:00Z"
}
```

#### 3.4 删除事件

```http
DELETE /api/v1/events/{event_id}
Authorization: Bearer <token>
```

响应：`204 No Content`

---

### 4. 对话 (Chat)

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/chat` | 发送消息 |
| POST | `/api/v1/chat/feedback` | 反馈 |
| GET | `/api/v1/conversations` | 对话列表 |
| POST | `/api/v1/conversations` | 创建对话 |
| GET | `/api/v1/conversations/{id}` | 对话详情 |
| GET | `/api/v1/conversations/{id}/messages` | 消息列表 |
| DELETE | `/api/v1/conversations/{id}` | 删除对话 |
| PUT | `/api/v1/conversations/{id}/title` | 更新标题 |

#### 4.1 发送消息

```http
POST /api/v1/chat
Content-Type: application/json
Authorization: Bearer <token>

{
  "user_id": "string",
  "message": "明天下午3点开会",
  "conversation_id": "uuid (可选)"
}
```

**响应**：
```json
{
  "reply": "已为你安排明天下午3点的会议，约1小时",
  "actions": [
    {
      "type": "create_event",
      "event_id": "uuid",
      "event": { /* 完整事件对象 */ }
    }
  ],
  "suggestions": [
    {
      "label": "明天上午10点",
      "value": "2026-01-25T02:00:00Z",
      "description": "2小时"
    }
  ],
  "conversation_id": "uuid",
  "snapshot_id": "uuid"
}
```

**Swift 示例**：
```swift
struct ChatMessage: Codable {
    let role: String  // "user" or "assistant"
    let content: String
    let timestamp: Date
}

struct ChatResponse: Codable {
    let reply: String
    let actions: [ChatAction]
    let suggestions: [Suggestion]
    let conversation_id: String
}

struct ChatAction: Codable {
    let type: String  // "create_event", "update_event", "delete_event"
    let event_id: String
    let event: Event?
}

func sendMessage(_ text: String, conversationId: String? = nil) async throws -> ChatResponse {
    let request: [String: Any] = [
        "user_id": userId,
        "message": text
    ]
    if let cid = conversationId {
        request["conversation_id"] = cid
    }

    let url = URL(string: "\(baseURL)/api/v1/chat")!
    var urlRequest = URLRequest(url: url)
    urlRequest.httpMethod = "POST"
    urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
    urlRequest.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
    urlRequest.httpBody = try JSONSerialization.data(withJSONObject: request)

    let (data, _) = try await URLSession.shared.data(for: urlRequest)
    return try JSONDecoder().decode(ChatResponse.self, from: data)
}
```

---

### 5. 同步 (Sync)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/sync` | 增量同步 |
| GET | `/api/v1/sync/status` | 同步状态 |

#### 5.1 增量同步

```http
GET /api/v1/sync?since=2026-01-24T00:00:00Z
Authorization: Bearer <token>
```

**响应**：
```json
{
  "since": "2026-01-24T00:00:00Z",
  "until": "2026-01-24T14:54:59.399147Z",
  "has_more": false,
  "changes": {
    "events": {
      "created": [/* 事件数组 */],
      "updated": [/* 事件数组 */],
      "deleted": ["event_id", "event_id"]
    },
    "routines": {
      "created": [],
      "updated": [],
      "deleted": []
    }
  }
}
```

---

### 6. 设备管理 (Devices)

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/devices/register` | 注册设备 |
| GET | `/api/v1/devices` | 设备列表 |
| GET | `/api/v1/devices/{id}` | 设备详情 |
| PUT | `/api/v1/devices/{id}` | 更新设备 |
| DELETE | `/api/v1/devices/{id}` | 删除设备 |

#### 6.1 注册设备

```http
POST /api/v1/devices/register
Content-Type: application/json
Authorization: Bearer <token>

{
  "platform": "ios",
  "token": "device_push_token",
  "device_name": "iPhone 14 Pro",
  "device_model": "iPhone15,3",
  "os_version": "17.2",
  "app_version": "1.0.0"
}
```

**响应**：
```json
{
  "id": "device_uuid",
  "user_id": "user_uuid",
  "platform": "ios",
  "token": "device_push_token",
  "device_id": null,
  "device_name": "iPhone 14 Pro",
  "is_active": true,
  "created_at": "2026-01-24T14:52:37.446946"
}
```

---

### 7. 快照 (Snapshots)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/snapshots` | 快照列表 |
| POST | `/api/v1/snapshots/{id}/revert` | 恢复快照 |
| POST | `/api/v1/snapshots/undo` | 撤销最近更改 |

#### 7.1 获取快照列表

```http
GET /api/v1/snapshots?limit=10&include_reverted=false
Authorization: Bearer <token>
```

#### 7.2 恢复快照

```http
POST /api/v1/snapshots/{snapshot_id}/revert
Authorization: Bearer <token>
```

**响应**：
```json
{
  "snapshot_id": "uuid",
  "message": "已撤销上次修改，3 个事件已恢复",
  "reverted_events": ["event_id1", "event_id2", "event_id3"],
  "reverted_at": "2026-01-24T14:55:00.000000"
}
```

---

### 8. 日记 (Diaries)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/diaries` | 日记列表 |
| GET | `/api/v1/diaries/{date}` | 按日期获取 |
| GET | `/api/v1/diaries/stats` | 统计 |
| POST | `/api/v1/diaries/generate` | 手动生成 |
| POST | `/api/v1/diaries/profile/analyze` | 触发分析 |
| GET | `/api/v1/diaries/profile/evolution` | 画像演变 |

---

### 9. 推送通知 (Notifications)

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/notifications/send` | 发送通知 |
| POST | `/api/v1/notifications/send/template/{template_name}` | 发送模板通知 |
| POST | `/api/v1/notifications/events/{id}/remind` | 事件提醒 |
| POST | `/api/v1/notifications/events/{id}/starting` | 事件开始提醒 |
| GET | `/api/v1/notifications/templates` | 模板列表 |
| POST | `/api/v1/notifications/templates` | 创建模板 |
| GET | `/api/v1/notifications/history` | 通知历史 |
| POST | `/api/v1/notifications/test` | 测试通知 |

#### 9.1 发送自定义通知

```http
POST /api/v1/notifications/send
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "会议提醒",
  "body": "团队周会在15分钟后开始",
  "badge": 1,
  "sound": "default",
  "category": "EVENT_REMINDER",
  "data": {
    "event_id": "uuid",
    "action": "view_event"
  }
}
```

**响应**：
```json
{
  "id": "notification_uuid",
  "user_id": "user_uuid",
  "device_id": null,
  "platform": "apns",
  "type": "custom",
  "priority": "normal",
  "payload": {
    "title": "会议提醒",
    "body": "团队周会在15分钟后开始"
  },
  "status": "sent",
  "sent_at": "2026-01-24T14:00:00"
}
```

#### 9.2 发送模板通知

**可用模板**：
- `event_reminder`: 事件提醒 (变量: title, minutes)
- `event_starting`: 事件开始 (变量: title)
- `event_modified`: 事件已修改 (变量: title, new_time)
- `routine_reminder`: 惯例提醒 (变量: routine_name)
- `daily_summary`: 每日总结 (变量: event_count)
- `energy_alert`: 精力提醒 (无变量)

```http
POST /api/v1/notifications/send/template/event_reminder
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "团队周会",
  "minutes": "15"
}
```

#### 9.3 发送事件提醒

```http
POST /api/v1/notifications/events/{event_id}/remind?minutes_before=15
Authorization: Bearer <token>
```

#### 9.4 iOS 推送通知集成

**Swift 端实现**：

```swift
// 1. 注册推送通知
func registerForPushNotifications() {
    let center = UNUserNotificationCenter.current()
    center.requestAuthorization(options: [.alert, .sound, .badge]) { granted, error in
        if granted {
            DispatchQueue.main.async {
                UIApplication.shared.registerForRemoteNotifications()
            }
        }
    }
}

// 2. 获取 Device Token
func application(_ application: UIApplication,
                 didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
    let token = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()

    // 发送到后端
    Task {
        try await UniLifeAPI.shared.registerDevice(
            platform: "ios",
            token: token,
            deviceName: UIDevice.current.name,
            deviceModel: UIDevice.current.model,
            osVersion: UIDevice.current.systemVersion,
            appVersion: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String
        )
    }
}

// 3. 处理收到的通知
func userNotificationCenter(_ center: UNUserNotificationCenter,
                          didReceive response: UNNotificationResponse,
                          withCompletionHandler completionHandler: @escaping () -> Void) {
    let userInfo = response.notification.request.content.userInfo

    // 根据通知类型处理
    if let eventId = userInfo["event_id"] as? String {
        // 跳转到事件详情
        navigateToEvent(eventId)
    }

    completionHandler()
}
```

**UniLifeAPI 扩展**：
```swift
extension UniLifeAPI {

    // 注册设备
    func registerDevice(platform: String, token: String, deviceName: String,
                       deviceModel: String, osVersion: String, appVersion: String) async throws {
        let url = URL(string: "\(baseURL)/api/v1/devices/register")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(accessToken!)", forHTTPHeaderField: "Authorization")

        let body: [String: Any] = [
            "platform": platform,
            "token": token,
            "device_name": deviceName,
            "device_model": deviceModel,
            "os_version": osVersion,
            "app_version": appVersion
        ]

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (_, response) = try await URLSession.shared.data(for: request)
        guard (response as? HTTPURLResponse)?.statusCode == 201 else {
            throw APIError.requestFailed
        }
    }

    // 发送通知
    func sendNotification(title: String, body: String, data: [String: Any] = [:]) async throws {
        let url = URL(string: "\(baseURL)/api/v1/notifications/send")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(accessToken!)", forHTTPHeaderField: "Authorization")

        var payload: [String: Any] = [
            "title": title,
            "body": body
        ]
        payload["data"] = data

        request.httpBody = try JSONSerialization.data(withJSONObject: payload)

        let (_, response) = try await URLSession.shared.data(for: request)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            throw APIError.requestFailed
        }
    }
}
```

---

## 数据模型

### Event（事件）

```swift
struct Event: Codable, Identifiable {
    let id: String
    let user_id: String
    let title: String
    let description: String?
    let start_time: Date?
    let end_time: Date?
    let duration: Int?
    let status: EventStatus
    let event_type: EventType
    let category: Category
    let tags: [String]
    let created_at: Date
    let updated_at: Date

    enum EventStatus: String, Codable {
        case pending = "PENDING"
        case inProgress = "IN_PROGRESS"
        case completed = "COMPLETED"
        case cancelled = "CANCELLED"
    }

    enum EventType: String, Codable {
        case schedule = "schedule"
        case deadline = "deadline"
        case floating = "floating"
        case habit = "habit"
        case reminder = "reminder"
    }

    enum Category: String, Codable {
        case study = "STUDY"
        case work = "WORK"
        case social = "SOCIAL"
        case life = "LIFE"
        case health = "HEALTH"
    }
}
```

### User（用户）

```swift
struct User: Codable {
    let id: String
    let user_id: String?
    let nickname: String
    let timezone: String
    let current_energy: Int
    let energy_profile: EnergyProfile
    let preferences: UserPreferences
    let created_at: Date
    let last_active_at: Date
}

struct EnergyProfile: Codable {
    let hourly_baseline: [Int: Int]
    let task_energy_cost: [String: Int]
    let learned_adjustments: [String: Any]
}
```

---

## 错误处理

### 标准错误响应

```json
{
  "detail": "错误描述"
}
```

### 常见 HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 204 | 成功（无内容） |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 404 | 资源不存在 |
| 500 | 服务器错误 |

---

## Swift 使用示例

### 完整的 API 客户端

```swift
import Foundation

class UniLifeAPI {
    static let shared = UniLifeAPI()
    private let baseURL = "http://localhost:8000"

    private var accessToken: String? {
        get { UserDefaults.standard.string(forKey: "access_token") }
        set { UserDefaults.standard.set(newValue, forKey: "access_token") }
    }

    // MARK: - Authentication

    func login(userId: String) async throws -> LoginResponse {
        let url = URL(string: "\(baseURL)/api/v1/auth/login")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(["user_id": userId])

        let (data, _) = try await URLSession.shared.data(for: request)
        let response = try JSONDecoder().decode(LoginResponse.self, from: data)
        self.accessToken = response.access_token
        return response
    }

    // MARK: - Events

    func getEvents() async throws -> [Event] {
        guard let url = URL(string: "\(baseURL)/api/v1/events") else {
            throw APIError.invalidURL
        }
        var request = URLRequest(url: url)
        request.setValue("Bearer \(accessToken!)", forHTTPHeaderField: "Authorization")

        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONDecoder().decode([Event].self, from: data)
    }

    func createEvent(title: String, startTime: Date, duration: Int) async throws -> Event {
        let url = URL(string: "\(baseURL)/api/v1/events")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(accessToken!)", forHTTPHeaderField: "Authorization")

        let isoDate = ISO8601DateFormatter().string(from: startTime)
        let body: [String: Any] = [
            "title": title,
            "start_time": isoDate,
            "duration": duration
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONDecoder().decode(Event.self, from: data)
    }

    // MARK: - Chat

    func sendMessage(_ message: String, conversationId: String? = nil) async throws -> ChatResponse {
        let url = URL(string: "\(baseURL)/api/v1/chat")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(accessToken!)", forHTTPHeaderField: "Authorization")

        var body: [String: Any] = [
            "user_id": getUserIdFromToken(),
            "message": message
        ]
        if let cid = conversationId {
            body["conversation_id"] = cid
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONDecoder().decode(ChatResponse.self, from: data)
    }

    // MARK: - Helper Methods

    private func getUserIdFromToken() -> String {
        // Decode JWT and extract user_id
        // 简化版本：实际应该解析 JWT
        return UserDefaults.standard.string(forKey: "user_id") ?? ""
    }
}

enum APIError: Error {
    case invalidURL
    case networkError
    case decodingError
    case unauthorized
}
```

---

## 测试用例

### 使用 curl 测试

```bash
# 1. 登录
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user"}' \
  | jq -r '.access_token')

# 2. 获取用户信息
curl -X GET http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN"

# 3. 创建事件
curl -X POST http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "开会",
    "start_time": "2026-01-25T10:00:00Z",
    "duration": 60
  }'

# 4. 获取事件列表
curl -X GET http://localhost:8000/api/v1/events \
  -H "Authorization: Bearer $TOKEN"
```

---

## 注意事项

### 1. 时间格式
- 所有时间字段使用 ISO 8601 格式：`2026-01-25T10:00:00Z`
- Swift 中使用 `ISO8601DateFormatter()` 进行编码/解码

### 2. 分页
- 大多数列表接口支持 `limit` 参数
- 默认 `limit=100`，最大 `limit=500`

### 3. 错误处理
- 建议使用 `do-catch` 捕获网络错误
- 检查 HTTP 状态码
- 处理 401 状态时自动刷新 Token

### 4. Token 刷新
```swift
func refreshToken() async throws {
    let refreshToken = UserDefaults.standard.string(forKey: "refresh_token")!
    let url = URL(string: "\(baseURL)/api/v1/auth/refresh")!
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.httpBody = try JSONEncoder().encode(["refresh_token": refreshToken])

    let (data, _) = try await URLSession.shared.data(for: request)
    let response = try JSONDecoder().decode(RefreshResponse.self, from: data)
    self.accessToken = response.access_token
}
```

---

## 常见问题

### Q: 为什么 Events CRUD 没有直接返回双时间架构的字段？
A: 当前 Events API 返回的是基础字段。双时间架构字段（如 `duration_source`, `duration_confidence`）存在于数据模型中，但不在标准 CRUD 响应中。这些字段主要通过 Chat 接口使用。

### Q: 如何处理离线模式？
A: 建议：
1. 使用 SwiftData/Core Data 本地存储
2. 在线时通过 Chat 同步或 Sync API
3. 定期调用 `/api/v1/sync` 进行增量同步

### Q: 推送通知如何集成？
A:
1. 调用 `/api/v1/devices/register` 注册设备 Token
2. 后端通过 APNs 发送通知
3. 前端处理推送通知并同步数据

---

## 更新日志

### v2.6 (2026-01-24)
- ✅ 新增 Notifications API（推送通知）
- ✅ Event 和 Routine 模型增加完成追踪字段（completed_at, started_at）
- ✅ Routine 模型增加统计字段（skipped_instances, cancelled_instances, current_streak）

### v2.5 (2026-01-24)
- ✅ 新增 Events CRUD API
- ✅ 新增 Users API（用户信息、统计、画像）
- ✅ 新增 Sync API（增量同步）
- ✅ 新增 Devices API（设备管理）
- ✅ 新增 Snapshots API（快照和撤销）

### v2.0
- ✅ Chat 对话系统
- ✅ 对话历史管理
- ✅ 日记功能
