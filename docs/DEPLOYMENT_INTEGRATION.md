# UniLife 部署和集成文档

## 概述

本文档描述 UniLife 后端的部署流程、环境配置，以及与微信机器人和 iOS 应用的集成指南。

---

## 1. 环境配置

### 1.1 环境变量

**文件**：`.env`

```bash
# ============== LLM 配置 ==============
DEEPSEEK_API_KEY=sk-***
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# ============== 数据库配置 ==============
DB_TYPE=sqlite                    # sqlite | postgresql
SQLITE_PATH=unilife.db            # SQLite 文件路径
# POSTGRESQL_URL=postgresql+asyncpg://user:pass@localhost/unilife

# ============== JWT 认证 ==============
JWT_SECRET_KEY=change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080           # 7 天

# ============== 服务器配置 ==============
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false

# ============== 微信接入（可选）=============
WECHAT_WEBHOOK_URL=https://your-server.com/wechat
WECHAT_SECRET_KEY=***

# ============== iOS 推送（可选）=============
APNS_KEY_ID=***
APNS_TEAM_ID=***
APNS_BUNDLE_ID=com.unilife.app
APNS_PRIVATE_KEY_PATH=/path/to/key.pem
```

### 1.2 必需配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | 无 |
| `JWT_SECRET_KEY` | JWT 签名密钥 | `dev_secret_123` |
| `DB_TYPE` | 数据库类型 | `sqlite` |

---

## 2. 开发环境搭建

### 2.1 前置要求

- Python 3.10+
- pip 或 poetry

### 2.2 安装步骤

```bash
# 1. 克隆项目
git clone <repo-url>
cd unilife-backend

# 2. 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填写必需配置

# 5. 初始化数据库
python init_db.py

# 6. 启动服务
python -m app.main
# 或
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2.3 验证安装

```bash
# 检查健康状态
curl http://localhost:8000/health

# 访问 API 文档
open http://localhost:8000/docs
```

---

## 3. 数据库迁移

### 3.1 迁移脚本

按顺序运行迁移脚本：

```bash
# 1. 决策偏好表
python migrations/migrate_add_decision_profile.py

# 2. Routine 系统迁移
python migrate_routine_to_new_arch.py

# 3. 双时间字段
python migrate_dual_time_fields.py

# 4. 关系状态字段
python migrate_relationship_status.py

# 5. 日记表
python migrate_add_diary_tables.py
```

### 3.2 备份建议

运行迁移前务必备份数据库：

```bash
# SQLite
cp unilife.db unilife.db.backup

# PostgreSQL
pg_dump unilife > backup.sql
```

---

## 4. chatgpt-on-wechat 集成

### 4.1 部署 chatgpt-on-wechat

```bash
# 1. 克隆项目
git clone https://github.com/zhayk/chatgpt-on-wechat
cd chatgpt-on-wechat

# 2. 配置 .env
cat > .env << EOF
# UniLife 后端配置
UNILIFE_API_URL=http://localhost:8000/api/v1/chat
UNILIFE_API_KEY=optional-api-key

# 微信配置
CHANNEL_TYPE=wx
PROXY=*
OPEN_AI_API_KEY=your-api-key
MODEL=deepseek-chat
EOF

# 3. 启动
docker compose up -d
```

### 4.2 配置 Webhook

**UniLife 后端添加 Webhook 端点**（可选）：

```python
# app/api/wechat.py
from fastapi import APIRouter, Request

router = APIRouter()

@router.post("/webhook")
async def wechat_webhook(request: Request):
    data = await request.json()

    # 构造 chat 请求
    chat_request = {
        "user_id": data["user_id"],
        "message": data["content"],
        "context": {
            "channel": "wechat",
            "message_type": data.get("message_type", "text")
        }
    }

    # 调用 chat 端点
    result = await process_chat(chat_request)

    return {"reply": result["reply"]}
```

### 4.3 测试集成

```bash
# 发送测试消息
curl -X POST http://localhost:8000/api/v1/wechat/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "content": "明天下午3点开会",
    "message_type": "text"
  }'
```

---

## 5. iOS 应用接入

### 5.1 接入流程

```
1. 注册/登录 → 获取 Access Token
2. 增量同步 → 获取初始数据
3. 注册设备 → 启用推送
4. 对话交互 → 调用 /api/v1/chat
```

### 5.2 Swift 代码示例

#### 登录

```swift
import Foundation

struct UnilifeAPI {
    let baseURL = "http://localhost:8000"
    let tokenKey = "unilife_token"

    // 登录
    func login(userId: String) async throws -> LoginResponse {
        let url = URL(string: "\(baseURL)/api/v1/auth/login")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["user_id": userId]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, _) = try await URLSession.shared.data(for: url)
        let response = try JSONDecoder().decode(LoginResponse.self, from: data)

        // 存储 Token
        UserDefaults.standard.set(response.accessToken, forKey: tokenKey)

        return response
    }

    // 获取 Token
    func getAccessToken() -> String? {
        return UserDefaults.standard.string(forKey: tokenKey)
    }
}

struct LoginResponse: Codable {
    let user_id: String
    let access_token: String
    let refresh_token: String
    let expires_in: Int
}
```

#### 增量同步

```swift
extension UnilifeAPI {
    // 首次同步（获取全量数据）
    func syncInitial() async throws -> SyncResponse {
        let since = ISO8601DateFormatter().string(from: Date(timeIntervalSince1970: 0))
        return try await sync(since: since)
    }

    // 增量同步
    func sync(since: String) async throws -> SyncResponse {
        guard let token = getAccessToken() else {
            throw UnilifeError.notAuthenticated
        }

        var components = URLComponents(string: "\(baseURL)/api/v1/sync")!
        components.queryItems = [
            URLQueryItem(name: "since", value: since),
            URLQueryItem(name: "include", value: "events,routines")
        ]

        var request = URLRequest(url: components.url!)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONDecoder().decode(SyncResponse.self, from: data)
    }
}

struct SyncResponse: Codable {
    let since: String
    let until: String
    let has_more: Bool
    let changes: Changes
}

struct Changes: Codable {
    let events: ChangeSet
    let routines: ChangeSet
}

struct ChangeSet: Codable {
    let created: [Event]
    let updated: [Event]
    let deleted: [String]
}
```

#### 对话

```swift
extension UnilifeAPI {
    // 发送消息
    func chat(message: String) async throws -> ChatResponse {
        guard let token = getAccessToken() else {
            throw UnilifeError.notAuthenticated
        }

        let url = URL(string: "\(baseURL)/api/v1/chat")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let body = [
            "user_id": getUserId(),
            "message": message
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, _) = try await URLSession.shared.data(for: url)
        return try JSONDecoder().decode(ChatResponse.self, from: data)
    }
}

struct ChatResponse: Codable {
    let reply: String
    let actions: [Action]
    let suggestions: [Suggestion]
    let conversation_id: String
    let snapshot_id: String?
}

struct Action: Codable {
    let type: String
    let event_id: String
    let event: Event?
}

struct Suggestion: Codable {
    let label: String
    let value: String?
    let description: String?
    let probability: Int?
}

enum UnilifeError: Error {
    case notAuthenticated
}
```

### 5.3 推送集成

#### 注册设备

```swift
import UserNotifications

class PushManager {
    let api = UnilifeAPI()

    // 注册设备
    func registerDevice() async throws {
        // 获取 Device Token
        let deviceToken = await getDeviceToken()

        guard let token = api.getAccessToken() else {
            throw UnilifeError.notAuthenticated
        }

        let url = URL(string: "\(api.baseURL)/api/v1/devices/register")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let body: [String: Any] = [
            "platform": "ios",
            "token": deviceToken,
            "metadata": [
                "model": UIDevice.current.model,
                "os_version": UIDevice.current.systemVersion
            ]
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (_, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw UnilifeError.registrationFailed
        }
    }

    // 获取 Device Token
    func getDeviceToken() async -> String {
        // 实现获取 APNs Device Token
        // 参考：https://developer.apple.com/documentation/usernotifications/registering-your-app-with-apns
        return "mock_device_token"
    }
}
```

---

## 6. 生产环境部署

### 6.1 Docker 部署

**Dockerfile**：

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "app.main"]
```

**docker-compose.yml**：

```yaml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - DB_TYPE=postgresql
      - POSTGRESQL_URL=postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@db:5432/unilife
    depends_on:
      - db

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=unilife
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### 6.2 启动服务

```bash
# 构建并启动
docker compose up -d

# 查看日志
docker compose logs -f backend

# 停止服务
docker compose down
```

### 6.3 Railway 部署

```bash
# 安装 Railway CLI
npm install -g @railway/cli

# 登录
railway login

# 初始化项目
railway init

# 配置环境变量
railway variables set DEEPSEEK_API_KEY=sk-***

# 部署
railway up
```

---

## 7. API 测试

### 7.1 使用 curl

```bash
# 登录
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test123"}'

# 同步
curl -X GET "http://localhost:8000/api/v1/sync?since=2026-01-24T00:00:00Z" \
  -H "Authorization: Bearer {token}"

# 对话
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{"user_id": "test", "message": "今天有什么安排？"}'
```

### 7.2 使用 Postman

1. 导入环境变量
   - `base_url`: `http://localhost:8000`
   - `token`: `{access_token}`

2. 导入 Collection（需创建）

3. 运行测试集合

### 7.3 测试脚本

**文件**：`scripts/test_api.sh`

```bash
#!/bin/bash

BASE_URL="http://localhost:8000"

# 登录
echo "=== 登录 ==="
LOGIN_RESPONSE=$(curl -s -X POST $BASE_URL/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user_123"}')

TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')
echo "Token: $TOKEN"

# 同步
echo -e "\n=== 增量同步 ==="
curl -s -X GET "$BASE_URL/api/v1/sync?since=2026-01-01T00:00:00Z" \
  -H "Authorization: Bearer $TOKEN" | jq

# 对话
echo -e "\n=== 对话 ==="
curl -s -X POST $BASE_URL/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"user_id": "test_user_123", "message": "明天下午3点开会"}' | jq
```

---

## 8. 故障排查

### 8.1 常见问题

| 问题 | 解决方案 |
|------|----------|
| 端口已被占用 | 修改 `API_PORT` 或终止占用进程 |
| 数据库连接失败 | 检查 `POSTGRESQL_URL` 或 SQLite 文件路径 |
| Token 无效 | 重新登录获取新 Token |
| LLM 调用失败 | 检查 `DEEPSEEK_API_KEY` 是否有效 |

### 8.2 日志查看

```bash
# Docker 环境
docker compose logs -f backend

# 本地环境
# 日志输出到 stdout
```

### 8.3 调试模式

```bash
# .env
DEBUG=true

# 启动服务
python -m app.main
```

---

## 9. 安全建议

### 9.1 生产环境

- [ ] 更改 `JWT_SECRET_KEY`
- [ ] 使用 `POSTGRESQL` 替代 `SQLite`
- [ ] 启用 HTTPS
- [ ] 配置 CORS 白名单
- [ ] 实现速率限制

### 9.2 API 密钥管理

```bash
# 不要将密钥提交到 Git
echo ".env" >> .gitignore
echo "unilife.db" >> .gitignore
```

---

## 10. 参考资源

| 资源 | 链接 |
|------|------|
| FastAPI 文档 | https://fastapi.tiangolo.com/ |
| SQLAlchemy | https://docs.sqlalchemy.org/ |
| DeepSeek API | https://platform.deepseek.com/api-docs/ |
| chatgpt-on-wechat | https://github.com/zhayk/chatgpt-on-wechat |
| APNs | https://developer.apple.com/documentation/usernotifications |
