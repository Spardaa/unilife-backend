# UniLife Backend Serverless 部署指南

本文档提供将 UniLife Backend 部署到 Serverless 云函数平台的完整指南。

## 目录

- [平台选择](#平台选择)
- [架构调整](#架构调整)
- [数据库配置](#数据库配置)
- [部署步骤](#部署步骤)
- [常见问题](#常见问题)

---

## 平台选择

### 推荐平台

根据中文用户的使用习惯，推荐以下平台：

| 平台 | 优点 | 缺点 | 推荐指数 |
|------|------|------|----------|
| **腾讯云 SCF** | 文档完善、免费额度高、与微信生态集成 | 需要实名认证 | ⭐⭐⭐⭐⭐ |
| **阿里云 FC** | 稳定性好、产品成熟 | 价格稍高 | ⭐⭐⭐⭐ |
| **华为云 FG** | 性能强 | 文档较少 | ⭐⭐⭐ |

本指南以**腾讯云 SCF** 为例进行讲解。

---

## 架构调整

### 调整前 vs 调整后

| 组件 | 调整前 | 调整后 |
|------|--------|--------|
| Web 服务器 | Uvicorn 持续运行 | API 网关 + 云函数 |
| 数据库 | SQLite 本地文件 | 云数据库 PostgreSQL |
| 后台任务 | APScheduler 定时调度 | 云函数定时触发器 |
| 生命周期 | 长期运行 | 按需启动 |

### 核心变化

1. **移除 Uvicorn 依赖** - 云函数直接处理 HTTP 请求
2. **移除 APScheduler** - 使用云平台定时触发器
3. **数据库改为 PostgreSQL** - 使用云数据库
4. **添加 Serverless 适配器** - 连接 API 网关和 FastAPI

---

## 数据库配置

### 方案一：腾讯云 PostgreSQL

1. **创建数据库实例**
   - 登录腾讯云控制台
   - 搜索「PostgreSQL」
   - 点击「新建实例」
   - 选择「单节点」(最便宜)
   - 规格：1核1GB 足够
   - 地域：选择离你最近的

2. **获取连接信息**
   ```
   主机地址：postgres.xxx.tencentcloudapi.com
   端口：5432
   数据库名：unilife
   用户名：unilife_user
   密码：你的密码
   ```

3. **格式化连接字符串**
   ```
   postgresql+asyncpg://unilife_user:密码@postgres.xxx.tencentcloudapi.com:5432/unilife
   ```

### 方案二：Supabase（推荐新手）

Supabase 提供免费的 PostgreSQL 数据库，非常适合测试和小规模使用。

1. **注册 Supabase**
   - 访问 https://supabase.com
   - 使用 GitHub 账号登录
   - 创建新项目

2. **获取连接信息**
   - 进入项目设置 → Database
   - 找到 Connection string
   - 选择 URI 格式
   - 示例：
   ```
   postgresql+asyncpg://postgres:密码@db.xxx.supabase.co:5432/postgres
   ```

---

## 部署步骤

### 步骤 1: 准备代码

#### 1.1 创建 Serverless 入口文件

创建 `serverless.py` 文件（已为你准备好）：

```python
from app.main import app
from mangum import Mangum

# 创建 Serverless 适配器
lambda_handler = Mangum(app, lifespan="off")
```

#### 1.2 更新依赖

创建 `requirements_serverless.txt`：

```
# 核心框架
fastapi==0.115.0
pydantic==2.9.2
pydantic-settings==2.6.0

# Serverless 适配
mangum==0.17.0

# 数据库
sqlalchemy==2.0.35
asyncpg==0.30.0

# LLM
openai==1.54.0
httpx==0.27.2

# 认证
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.12

# 工具
python-dateutil==2.9.0
pytz==2024.2
requests==2.32.5
```

#### 1.3 禁用后台任务调度器

修改 `app/main.py`，在 Serverless 环境下禁用调度器：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_logging()
    logger = logging.getLogger("main")
    logger.info(f"{LogColors.bold('🚀 UniLife Backend starting...')}")

    # Serverless 环境下不启动后台调度器
    if not os.getenv("SERVERLESS"):
        task_scheduler.start()

    yield

    if not os.getenv("SERVERLESS"):
        task_scheduler.stop()
```

### 步骤 2: 配置环境变量

在云函数配置中设置以下环境变量：

```bash
# Serverless 标识
SERVERLESS=true

# 数据库配置（使用你的实际连接字符串）
DB_TYPE=postgresql
POSTGRESQL_URL=postgresql+asyncpg://user:pass@host:5432/unilife

# LLM 配置
DEEPSEEK_API_KEY=你的API密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# JWT 配置（生产环境务必使用强密钥）
JWT_SECRET_KEY=生产环境请生成随机字符串
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080

# 其他配置
DEBUG=false
LOG_LEVEL=INFO
```

### 步骤 3: 初始化数据库

首次部署后需要初始化数据库表结构：

1. **方式一：本地初始化**
   ```bash
   # 设置环境变量
   export POSTGRESQL_URL=postgresql+asyncpg://user:pass@host:5432/unilife

   # 运行初始化脚本
   python init_db.py
   ```

2. **方式二：创建初始化函数**
   - 创建一个专门的云函数用于数据库初始化
   - 执行一次后删除

### 步骤 4: 创建定时任务函数

将后台任务改为独立的云函数，使用定时触发器：

创建 `serverless_cron.py`：

```python
"""
定时任务云函数
"""
import os
import json
from datetime import date

# 设置环境变量
os.environ["SERVERLESS"] = "true"

from app.scheduler.background_tasks import task_scheduler


def generate_daily_diaries(event, context):
    """每日日记生成（定时触发：每日 3:00）"""
    import asyncio

    target_date = date.today()
    result = asyncio.run(task_scheduler._generate_daily_diaries())
    return {"statusCode": 200, "body": json.dumps(result)}


def analyze_daily_profiles(event, context):
    """每日画像分析（定时触发：每日 3:15）"""
    import asyncio

    result = asyncio.run(task_scheduler._analyze_daily_profiles())
    return {"statusCode": 200, "body": json.dumps(result)}


def analyze_weekly_profiles(event, context):
    """每周画像深度分析（定时触发：每周日 4:00）"""
    import asyncio

    result = asyncio.run(task_scheduler._analyze_weekly_profiles())
    return {"statusCode": 200, "body": json.dumps(result)}
```

### 步骤 5: 打包部署

#### 5.1 安装依赖

```bash
# 安装 Serverless 依赖到本地
pip install -r requirements_serverless.txt --target ./package

# 复制项目代码
cp -r app ./package/
cp serverless.py ./package/

# 打包为 zip
cd package
zip -r ../unilife_backend.zip .
cd ..
```

#### 5.2 上传到腾讯云

1. 登录腾讯云控制台 → 云函数
2. 点击「新建」
3. 函数名称：`unilife-backend`
4. 运行环境：Python 3.10/3.11
5. 函数代码：选择「本地上传」
6. 上传 `unilife_backend.zip`
7. 入口文件：`serverless.lambda_handler`

#### 5.3 配置 API 网关

1. 在云函数详情页，点击「触发管理」
2. 点击「创建触发器」
3. 触发器类型：API 网关触发器
4. 鉴权类型：选择「免认证」或「API 网关鉴权」
5. 路径配置：`/api/v1/*`

#### 5.4 配置定时触发器

为后台任务创建定时触发器：

| 任务 | 触发器类型 | Cron 表达式 |
|------|-----------|-------------|
| 每日日记生成 | 定时触发 | `0 0 3 * * * *` |
| 每日画像分析 | 定时触发 | `0 15 3 * * * *` |
| 每周画像分析 | 定时触发 | `0 0 4 ? * 1 *` |

### 步骤 6: 测试验证

1. **测试 API**
   ```bash
   # 获取你的 API 网关地址
   curl https://你的API网关地址/api/v1/health
   ```

2. **测试聊天接口**
   ```bash
   curl -X POST https://你的API网关地址/api/v1/chat \
     -H "Content-Type: application/json" \
     -d '{"user_id": "test", "message": "你好"}'
   ```

---

## 常见问题

### 1. 冷启动慢怎么办？

- 使用预置并发
- 精简依赖包
- 使用腾讯云的「云函数同版本流量灰度」

### 2. 如何调试？

```python
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# 在代码中添加日志
logger.info("调试信息")
```

日志会输出到云平台日志服务。

### 3. 数据库连接池问题？

Serverless 环境下，每个函数实例都有自己的连接池：

```python
# 在 app/config.py 中调整
# 添加连接池配置
SQLALCHEMY_ENGINE_OPTIONS={
    "pool_size": 2,
    "max_overflow": 5,
    "pool_pre_ping": True
}
```

### 4. 成本估算？

腾讯云 SCF 免费额度：
- 调用次数：100 万次/月
- CU 资源量：40 万 CUs/月

个人使用完全免费。

### 5. 如何回滚？

在云函数控制台：
1. 找到「版本管理」
2. 选择历史版本
3. 点击「发布」

---

## 下一步

部署完成后，你可能还需要：

1. 配置自定义域名（通过 CDN）
2. 设置监控告警（云监控）
3. 配置日志采集（CLS）
4. 设置 CI/CD 自动部署

如有问题，请查看各云平台官方文档或提 Issue。
