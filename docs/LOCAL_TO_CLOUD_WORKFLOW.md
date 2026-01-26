# iOS App 与后端联通指南

## 推荐的工作流程

```
┌─────────────────────────────────────────────────────┐
│  阶段 1: 本地联通（必须先做）                         │
│  时间：1-2 小时                                      │
│  目的：确保功能正常，无基础问题                       │
├─────────────────────────────────────────────────────┤
│  阶段 2: 部署后端到云端                              │
│  时间：2-3 小时                                      │
│  目的：让 iOS App 能从外网访问                       │
├─────────────────────────────────────────────────────┤
│  阶段 3: 切换 iOS 配置到云端                         │
│  时间：5 分钟                                        │
│  目的：iOS 访问云端后端                              │
├─────────────────────────────────────────────────────┤
│  阶段 4: 真机测试                                    │
│  时间：30 分钟                                       │
│  目的：确保真实环境正常工作                          │
└─────────────────────────────────────────────────────┘
```

---

## 阶段 1: 本地联通（现在做）

### 为什么要先本地联通？

```
❌ 不推荐的直接部署：
1. 部署到云端 → 发现 API 设计有问题 → 修改 → 重新部署
2. 部署到云端 → 发现数据库字段不对 → 修改 → 重新部署
3. 部署到云端 → 调试不方便（每次修改都要上传）
4. 浪费时间，浪费云服务器费用

✅ 推荐的本地联通：
1. 本地运行后端
2. iOS 模拟器连接本地后端
3. 调通所有接口
4. 修复所有问题
5. 确认无误后部署到云端
```

### 具体步骤

#### 1.1 启动本地后端

```bash
# 在后端项目目录
cd /Users/natsu/Desktop/unilife/unilife-backend

# 启动开发服务器
python -m app.main

# 或使用 uvicorn（支持热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 1.2 确认后端正常运行

```bash
# 测试健康检查接口
curl http://localhost:8000/health

# 应该返回：
# {"status": "healthy"}

# 测试聊天接口
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_001",
    "message": "你好"
  }'
```

#### 1.3 配置 iOS App 连接本地后端

```swift
// Config.swift - 开发环境配置
struct APIConfig {
    #if DEBUG
    // 开发环境：连接本地后端
    static let baseURL = "http://localhost:8000"
    #else
    // 生产环境：连接云端后端（稍后配置）
    static let baseURL = "https://your-backend-domain.com"
    #endif

    static let timeout: TimeInterval = 30.0
}

// APIService.swift
class APIService {
    static let shared = APIService()

    private let baseURL: String
    private let session: URLSession

    init() {
        self.baseURL = APIConfig.baseURL

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = APIConfig.timeout
        self.session = URLSession(configuration: config)
    }

    func chat(userId: String, message: String) async throws -> ChatResponse {
        let url = URL(string: "\(baseURL)/api/v1/chat")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "user_id": userId,
            "message": message
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.requestFailed
        }

        let chatResponse = try JSONDecoder().decode(ChatResponse.self, from: data)
        return chatResponse
    }
}

// Models.swift
struct ChatResponse: Codable {
    let reply: String
    let user_id: String
    let message_id: String
    // 根据实际返回结构调整
}
```

#### 1.4 在 iOS 模拟器测试

```swift
// ContentView.swift 或某个测试界面
struct TestView: View {
    @State private var messages: [String] = []

    var body: some View {
        VStack {
            List(messages, id: \.self) { msg in
                Text(msg)
            }

            Button("测试后端连接") {
                Task {
                    do {
                        let response = try await APIService.shared.chat(
                            userId: "test_ios_user",
                            message: "你好，这是来自 iOS 的消息"
                        )
                        messages.append("AI: \(response.reply)")
                    } catch {
                        messages.append("错误: \(error.localizedDescription)")
                    }
                }
            }
        }
    }
}
```

#### 1.5 本地调试技巧

```bash
# 后端查看日志
# 修改 app/main.py，添加请求日志：
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"📥 {request.method} {request.url.path}")
    print(f"📋 Headers: {dict(request.headers)}")

    response = await call_next(request)

    print(f"📤 Status: {response.status_code}")
    return response
```

#### 1.6 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 连接拒绝 | 后端没启动 | `python -m app.main` |
| 超时 | 防火墙/端口占用 | 检查 8000 端口是否被占用 |
| 404 错误 | 路径错误 | 确认是 `/api/v1/chat` 不是 `/chat` |
| CORS 错误 | 浏览器限制 | iOS 不受 CORS 限制，可忽略 |

---

## 阶段 2: 部署后端到云端（本地联通后）

### 2.1 选择云服务器

```
推荐配置：
- 腾讯云轻量应用服务器
- 2核4GB
- 按量付费（约 ¥0.08/小时）
- 系统：Ubuntu 22.04

费用：首次购买通常有优惠（¥50-100/年）
```

### 2.2 一键部署脚本（我可以帮你准备）

```bash
# deploy.sh - 自动部署到云服务器
#!/bin/bash

# 使用方法：
# ./deploy.sh root@your-server-ip

SERVER=$1

echo "开始部署到 $SERVER ..."

# 上传代码
rsync -avz --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.git' \
  . $SERVER:/opt/unilife-backend/

# 安装依赖
ssh $SERVER "cd /opt/unilife-backend && pip3 install -r requirements.txt"

# 启动服务
ssh $SERVER "cd /opt/unilife-backend && ./start.sh"

echo "部署完成！"
```

### 2.3 配置 Nginx 反向代理

```nginx
# /etc/nginx/sites-available/unilife
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2.4 配置 HTTPS（免费）

```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx

# 自动配置 HTTPS
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

---

## 阶段 3: 切换 iOS 配置到云端

### 3.1 更新 iOS 配置

```swift
// Config.swift
struct APIConfig {
    #if DEBUG
    // 如果想在调试环境也用云端：
    static let baseURL = "https://your-backend-domain.com"

    // 或保持本地：
    // static let baseURL = "http://localhost:8000"
    #else
    // 生产环境：云端
    static let baseURL = "https://your-backend-domain.com"
    #endif
}
```

### 3.2 添加环境切换开关（可选）

```swift
// SettingsView.swift - 让用户可以选择环境
struct SettingsView: View {
    @AppStorage("apiEnvironment") private var environment: String = "production"

    var body: some View {
        Form {
            Picker("API 环境", selection: $environment) {
                Text("云端").tag("production")
                Text("本地").tag("development")
            }
        }
    }
}

// APIService.swift
class APIService {
    static let shared = APIService()

    private var baseURL: String {
        let env = UserDefaults.standard.string(forKey: "apiEnvironment") ?? "production"
        return env == "development" ? "http://localhost:8000" : "https://your-backend-domain.com"
    }

    // ...
}
```

---

## 阶段 4: 真机测试

### 4.1 注意事项

```
⚠️ 真机无法访问 localhost
- iOS 真机上的 localhost 是手机本身，不是 Mac
- 需要让真机和 Mac 在同一 WiFi
- 使用 Mac 的 IP 地址（如 192.168.1.100）
```

### 4.2 真机连接本地后端（调试用）

```swift
// Config.swift
struct APIConfig {
    #if targetEnvironment(simulator)
    // 模拟器：使用 localhost
    static let baseURL = "http://localhost:8000"
    #else
    // 真机：使用 Mac 的 IP（确保在同一 WiFi）
    // 先在 Mac 上运行：ifconfig | grep inet
    static let baseURL = "http://192.168.1.100:8000"
    #endif
}
```

### 4.3 真机连接云端后端

```swift
// 直接配置云端地址
struct APIConfig {
    static let baseURL = "https://your-backend-domain.com"
}
```

---

## 完整时间线

```
Day 1 - 本地开发与联通
  ├─ 1 小时：启动后端，测试 API
  ├─ 1 小时：iOS 集成 API
  └─ 1 小时：本地调试，确保功能正常

Day 2 - 部署后端（可选，也可以几天后再做）
  ├─ 30 分钟：购买云服务器
  ├─ 1 小时：部署后端代码
  ├─ 30 分钟：配置域名和 HTTPS
  └─ 30 分钟：iOS 切换到云端，测试

总计：约 4-6 小时（分两天完成更好）
```

---

## 常见问题

### Q1: 本地测试时，iOS 模拟器连不上后端？

```bash
# 检查后端是否在监听所有接口（不只是 127.0.0.1）
# 修改启动命令：
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Q2: 部署到云端后，iOS 连不上？

```bash
# 检查清单：
1. 云服务器防火墙是否开放 80/443 端口
2. 后端服务是否正在运行
3. Nginx 配置是否正确
4. 域名 DNS 是否解析正确
5. HTTPS 证书是否有效
```

### Q3: 如何在开发环境快速切换本地/云端？

```swift
// 使用编译条件 + 运行时开关
struct APIConfig {
    // 开发时可以在 App 内切换，发布后固定云端
    @AppStorage("useLocalBackend") private var useLocal: Bool = false

    static var baseURL: String {
        if useLocal {
            return "http://192.168.1.100:8000" // 你的 Mac IP
        } else {
            return "https://your-backend-domain.com"
        }
    }
}
```

---

## 总结

### 推荐顺序

```
✅ 1. 本地联通（必须先做）
   - 确保功能正常
   - 节省调试时间
   - 避免反复部署

✅ 2. 本地测试充分
   - 各种场景测试
   - 边界情况验证
   - 修复所有 bug

✅ 3. 部署到云端
   - 一键部署脚本
   - 配置 HTTPS
   - 生产环境测试

✅ 4. 发布 App
   - 提交 App Store
   - 等待审核
   - 正式上线
```

### 关键提醒

```
不要跳过本地联通步骤！

原因：
1. 云端调试比本地慢 10 倍
2. 每次修改都要上传代码
3. 无法使用断点调试
4. 浪费云服务器费用

先本地做好，再部署云端。
```
