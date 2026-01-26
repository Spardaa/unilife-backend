# UniLife 安全防护指南

## 潜在安全威胁分析

### 1. DDoS 攻击 🟡 中风险

**威胁**：恶意用户发送大量请求，导致服务器瘫痪

**影响**：
- 服务不可用
- 产生高额流量费用
- 正常用户无法访问

**防护措施**：
```nginx
# Nginx 配置限流
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

location /api/v1/chat {
    limit_req zone=api_limit burst=20 nodelay;
    # 每个 IP 每秒最多 10 次请求，突发 20 次
}
```

```python
# 应用层限流
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.post("/api/v1/chat")
@limiter.limit("60/minute")  # 每分钟最多 60 次
async def chat_endpoint():
    ...
```

**推荐方案**：
- 免费方案：Cloudflare CDN（自动防护 DDoS）
- 付费方案：腾讯云 DDoS 防护

---

### 2. API 滥用 🟠 高风险

**威胁**：恶意用户疯狂调用 DeepSeek API，导致你的费用爆炸

**影响**：
- DeepSeek API 费用可能达到数千元/天
- 服务被拖垮

**实际案例**：
```python
# 如果没有防护，攻击者可以写个脚本：
for i in range(100000):
    await call_chat_api()  # 疯狂调用，你的账单爆炸
```

**防护措施**：

#### A. 用户级别的限流
```python
# app/api/chat.py
from collections import defaultdict
from datetime import datetime, timedelta

# 简单内存限流（生产环境建议用 Redis）
user_request_count = defaultdict(list)

async def check_rate_limit(user_id: str, max_requests: int = 100, window: int = 86400):
    """检查用户是否超过配额"""
    now = datetime.now()
    day_ago = now - timedelta(seconds=window)

    # 清理过期记录
    user_request_count[user_id] = [
        t for t in user_request_count[user_id] if t > day_ago
    ]

    # 检查是否超限
    if len(user_request_count[user_id]) >= max_requests:
        return False

    user_request_count[user_id].append(now)
    return True

@app.post("/api/v1/chat")
async def chat(request: ChatRequest):
    # 限额检查
    if not await check_rate_limit(request.user_id, max_requests=100):
        raise HTTPException(
            status_code=429,
            detail="今日对话次数已达上限，请明天再试"
        )
    ...
```

#### B. 总体限流
```python
# 全局限流，防止总费用失控
GLOBAL_REQUEST_LIMIT = 1000  # 每天最多 1000 次请求
global_daily_count = 0

async def check_global_limit():
    global global_daily_count

    # 每天重置
    if datetime.now().hour == 0:
        global_daily_count = 0

    if global_daily_count >= GLOBAL_REQUEST_LIMIT:
        raise HTTPException(
            status_code=503,
            detail="服务今日已达到最大负载，请明天再试"
        )

    global_daily_count += 1
```

#### C. 成本监控告警
```python
# app/services/llm.py
import os

# 设置每日最大成本（单位：元）
MAX_DAILY_COST = float(os.getenv("MAX_DAILY_COST", "50"))

daily_cost = 0

async def call_deepseek_with_cost_check(messages):
    global daily_cost

    # 估算这次请求的成本（DeepSeek 约 ¥0.001/1K tokens）
    estimated_tokens = sum(len(m["content"]) for m in messages)
    estimated_cost = estimated_tokens / 1000 * 0.001

    if daily_cost + estimated_cost > MAX_DAILY_COST:
        raise Exception("今日 API 成本已达上限，服务暂停")

    # 调用 API
    response = await call_deepseek(messages)

    # 更新成本
    daily_cost += estimated_cost

    return response
```

---

### 3. SQL 注入攻击 🟢 低风险

**威胁**：通过恶意输入操作数据库

**当前状态**：
```python
# 你的项目使用了 SQLAlchemy ORM，天然防护了 SQL 注入
async def create_event(self, event_data: Dict[str, Any]):
    event = EventModel(**event_data)  # ✅ 安全，ORM 自动转义
    session.add(event)
```

**风险点**：
```python
# 如果有原生 SQL 查询，需要注意：
query = f"SELECT * FROM users WHERE id = '{user_id}'"  # ❌ 危险！

# 正确做法：
query = "SELECT * FROM users WHERE id = :user_id"
result = conn.execute(query, {"user_id": user_id})  # ✅ 安全
```

**检查你的代码**：
```bash
# 搜索可能的原生 SQL
grep -r "SELECT.*FROM" app/
grep -r "f\"SELECT" app/
```

---

### 4. XSS 跨站脚本攻击 🟢 低风险

**威胁**：恶意用户输入 JavaScript 代码，窃取其他用户信息

**当前状态**：
- 你的项目是后端 API，不直接渲染 HTML
- 风险主要在前端（iOS/Android 客户端）

**前端需要注意**：
```swift
// ❌ 危险：直接显示用户输入
textView.text = userMessage

// ✅ 安全：转义后再显示
textView.text = sanitizeHTML(userMessage)
```

---

### 5. 认证绕过 🟡 中风险

**威胁**：未登录用户访问付费功能

**当前代码检查**：
```python
# app/middleware/auth.py
# 你的项目已经有 JWT 认证中间件

# 需要确保所有敏感接口都加了认证：
@app.post("/api/v1/events")
# ✅ 有 @require_user_login 装饰器

@app.get("/api/v1/stats/{user_id}")
# ❓ 检查是否有认证
```

**建议检查**：
```bash
# 搜索所有 API 端点，确认敏感接口都有认证
grep -r "@app\." app/api/ | grep -E "(post|delete|put)"
```

---

### 6. 数据泄露 🟡 中风险

**威胁**：数据库被入侵，用户对话记录泄露

**当前状态**：
```python
# app/models/conversation.py
# 你的项目存储了完整的用户对话
messages = Column(JSON, nullable=False)
```

**防护措施**：

#### A. 敏感信息脱敏
```python
# 在保存前自动脱敏
import re

def sanitize_message(content: str) -> str:
    """移除敏感信息"""
    # 移除手机号
    content = re.sub(r'1[3-9]\d{9}', '[手机号]', content)
    # 移除身份证
    content = re.sub(r'\d{17}[\dXx]', '[身份证]', content)
    # 移除邮箱
    content = re.sub(r'\w+@\w+\.\w+', '[邮箱]', content)
    return content

# 保存时使用
sanitized_content = sanitize_message(user_message)
```

#### B. 数据库加密
```python
# 敏感字段加密存储
from cryptography.fernet import Fernet

key = os.getenv("ENCRYPTION_KEY")
cipher = Fernet(key)

encrypted_data = cipher.encrypt(data.encode())
```

#### C. 访问控制
```python
# 确保用户只能访问自己的数据
@app.get("/api/v1/conversations")
async def get_conversations(user_id: str, current_user: User):
    # ✅ 检查 user_id 是否是当前用户
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
```

---

### 7. 暴力破解 🟢 低风险

**威胁**：尝试大量密码组合

**当前状态**：
- 你的项目使用 JWT 认证，不存储密码
- 主要风险是 API Key 被破解

**防护措施**：
```python
# 限制失败尝试次数
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/v1/auth/login")
@limiter.limit("5/minute")  # 每分钟最多 5 次登录尝试
async def login():
    ...
```

---

## 快速安全检查清单

### 部署前必做（5 分钟）

```bash
✅ 1. 修改默认密钥
   JWT_SECRET_KEY=...  # 改为随机字符串
   DEEPSEEK_API_KEY=...  # 不要提交到 Git

✅ 2. 检查 .env 文件
   .env 已加入 .gitignore

✅ 3. 配置防火墙
   只开放 22, 80, 443 端口

✅ 4. 启用 HTTPS
   使用 Let's Encrypt 免费证书

✅ 5. 关闭 DEBUG 模式
   DEBUG=false
```

### 代码审查（30 分钟）

```bash
# 1. 搜索可能的 SQL 注入
grep -rn "f\"SELECT\|f'SELECT" app/

# 2. 检查所有文件操作
grep -rn "open(" app/ | grep -v ".pyc"

# 3. 确认敏感接口有认证
grep -rn "@app.post\|@app.delete\|@app.put" app/api/

# 4. 检查是否有 eval/exec（危险函数）
grep -rn "eval(\|exec(" app/
```

---

## 推荐的安全工具

```bash
# 1. 依赖漏洞扫描
pip install safety
safety check

# 2. 代码安全扫描
pip install bandit
bandit -r app/

# 3. 自动化 HTTPS
# 使用 certbot 获取免费 SSL 证书
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

## 监控和告警

### 基础监控指标

```python
# app/utils/monitoring.py
from prometheus_client import Counter, Histogram

# 请求计数
request_count = Counter('http_requests_total', 'Total requests')

# API 调用成本
api_cost = Counter('api_cost_total', 'Total API cost')

# 响应时间
response_time = Histogram('http_response_time_seconds', 'Response time')

# 异常计数
error_count = Counter('errors_total', 'Total errors')
```

### 告警规则

```yaml
# 当出现以下情况时发送告警：
alerts:
  - name: HighErrorRate
    condition: error_rate > 10%  # 错误率超过 10%
    action: 发送邮件/短信

  - name: HighCost
    condition: daily_cost > 100元  # 每日成本超过 100 元
    action: 发送紧急通知，暂停服务

  - name: HighLatency
    condition: avg_response_time > 10秒  # 平均响应时间超过 10 秒
    action: 发送警告
```

---

## 总结

### 风险等级总结

| 威胁 | 风险等级 | 优先级 | 防护难度 |
|------|----------|--------|----------|
| API 滥用 | 🟠 高 | P0 | 简单 |
| DDoS 攻击 | 🟡 中 | P1 | 简单 |
| 认证绕过 | 🟡 中 | P1 | 简单 |
| 数据泄露 | 🟡 中 | P2 | 中等 |
| SQL 注入 | 🟢 低 | P2 | 简单 |
| XSS 攻击 | 🟢 低 | P3 | 简单 |
| 暴力破解 | 🟢 低 | P3 | 简单 |

### 立即要做的（P0）

```bash
1. 添加 API 限流（防止费用爆炸）
2. 修改 JWT_SECRET_KEY（防止认证被破解）
3. 配置防火墙（只开放必要端口）
```

### 尽快做的（P1）

```bash
4. 启用 HTTPS（防止数据被窃听）
5. 添加成本监控（异常自动告警）
6. 代码安全扫描（bandit）
```

### 可以稍后（P2-P3）

```bash
7. 数据库加密
8. 敏感信息脱敏
9. 更完善的监控体系
```

---

**最重要的一点**：

```
安全是一个持续的过程，不是一次性的事情。

建议：
✅ 先做好基础防护（P0-P1）
✅ 快速上线验证产品
✅ 根据实际情况逐步加强

不要过度设计，但要避免低级错误。
```
