# Serverless 部署快速开始

这是一个为完全新手准备的 Serverless 部署指南，帮你将 UniLife Backend 部署到腾讯云函数。

## 前置准备

### 1. 你需要准备什么

- [ ] 一个腾讯云账号（需要实名认证）
- [ ] 一个云数据库（PostgreSQL）
  - 推荐：[Supabase](https://supabase.com) 提供免费 PostgreSQL 数据库
  - 或：腾讯云 PostgreSQL（付费）
- [ ] DeepSeek API Key
  - 访问：https://platform.deepseek.com
  - 注册并获取 API Key

### 2. 费用预估

**个人使用完全免费！**

腾讯云云函数免费额度：
- 调用次数：100 万次/月
- CU 资源量：40 万 CUs/月

UniLife 的使用量大约：
- 每次对话：~10 次调用
- 每天 50 次对话 = 1500 次调用/月
- **远远低于免费额度**

---

## 快速开始（3 步部署）

### 步骤 1: 准备云数据库

#### 方案 A：使用 Supabase（推荐新手，免费）

1. 访问 https://supabase.com
2. 点击 "Start your project"
3. 使用 GitHub 登录
4. 创建新项目：
   - 项目名：`unilife`
   - 数据库密码：**记住这个密码**
5. 等待创建完成（约 2 分钟）
6. 进入项目 → Settings → Database
7. 找到 "Connection string" → 选择 "URI" 格式
8. 复制连接字符串，格式类似：
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxx.supabase.co:5432/postgres
   ```
9. 将 `postgresql://` 改为 `postgresql+asyncpg://`（添加 +asyncpg）
10. 保存这个字符串，后面要用

#### 方案 B：使用腾讯云 PostgreSQL（付费）

1. 登录腾讯云控制台
2. 搜索 "PostgreSQL"
3. 点击 "新建实例"
4. 选择最便宜的配置：
   - 单节点
   - 1核1GB
   - 按量计费
5. 创建后获取连接信息

### 步骤 2: 打包代码

在项目根目录执行：

```bash
# 给脚本添加执行权限
chmod +x deploy_serverless.sh

# 运行打包脚本
./deploy_serverless.sh
```

打包完成后会生成 `unilife_backend.zip` 文件。

### 步骤 3: 上传到腾讯云

#### 3.1 创建云函数

1. 访问 https://console.cloud.tencent.com/scf
2. 点击 "新建"
3. 填写基本信息：
   - 函数名称：`unilife-backend`
   - 运行环境：Python 3.10 或 3.11
   - 函数代码：选择 "本地上传"
   - 上传 zip 文件：`unilife_backend.zip`
4. 点击 "完成"

#### 3.2 配置环境变量

在函数详情页：

1. 点击 "函数配置" → "环境变量"
2. 点击 "编辑"
3. 添加以下环境变量（参考 `.env.serverless` 文件）：

```bash
# 必填项
SERVERLESS=true
DB_TYPE=postgresql
POSTGRESQL_URL=postgresql+asyncpg://postgres:你的密码@db.xxx.supabase.co:5432/postgres
DEEPSEEK_API_KEY=sk-你的DeepSeek密钥
JWT_SECRET_KEY=随机生成的32位字符串

# 可选项
DEBUG=false
LOG_LEVEL=INFO
```

4. 点击 "保存"

#### 3.3 配置 API 网关

在函数详情页：

1. 点击 "触发管理"
2. 点击 "创建触发器"
3. 配置：
   - 触发器类型：API 网关触发器
   - 鉴权类型：免认证（或 API 网关鉴权）
   - 请求方法：ANY
   - 路径：`/api/v1`
4. 点击 "提交"

#### 3.4 获取 API 地址

在触发器列表中，点击 "API 网关触发器" 的链接，会跳转到 API 网关详情。

在 "调试" 页面可以看到你的 API 访问地址，类似：
```
https://service-xxx.gz.apigw.tencentcs.com/release
```

---

## 初始化数据库

首次部署需要初始化数据库表结构：

### 方法 1：本地初始化（推荐）

```bash
# 设置环境变量
export POSTGRESQL_URL=postgresql+asyncpg://...

# 运行初始化
python init_db.py
```

### 方法 2：在线初始化

在 Supabase 控制台的 SQL Editor 中执行：

```sql
-- 创建基础表（这里只列出示例，完整 SQL 见 init_db.py）
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR PRIMARY KEY,
    nickname VARCHAR NOT NULL,
    ...
);
```

**推荐使用方法 1**，因为它会自动创建所有表并插入示例数据。

---

## 测试验证

### 1. 健康检查

```bash
curl https://你的API地址/api/v1/health
```

应该返回：
```json
{"status": "healthy"}
```

### 2. 测试聊天接口

```bash
curl -X POST https://你的API地址/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "message": "你好"
  }'
```

---

## 定时任务配置（可选）

如果你需要使用日记生成和画像分析功能，需要创建额外的云函数：

### 1. 创建定时任务函数

重复上述步骤，上传同一个 zip 文件：
- 函数名：`unilife-cron-diary`
- 入口文件：`serverless_cron.daily_diary_generator`

### 2. 配置定时触发器

在函数详情页 → 触发管理 → 创建触发器：

| 任务 | 函数 | Cron 表达式 |
|------|------|-------------|
| 每日日记生成 | daily_diary_generator | `0 0 3 * * * *` |
| 每日画像分析 | daily_profile_analyzer | `0 15 3 * * * *` |
| 每周画像分析 | weekly_profile_analyzer | `0 0 4 ? * 1 *` |

---

## 常见问题

### Q: 提示 "模块不存在"

A: 检查 zip 文件是否包含 `app` 目录和 `serverless.py`

### Q: 数据库连接失败

A: 检查：
1. 连接字符串格式是否正确（注意 +asyncpg）
2. 数据库是否开启了公网访问
3. 防火墙是否允许 0.0.0.0/0（或添加腾讯云 IP）

### Q: API 返回 500 错误

A: 查看云函数日志，控制台 → 日志查询

### Q: 如何更新代码

A:
1. 修改代码后重新打包
2. 在函数详情页 → 函数代码 → 上传新 zip
3. 保存后自动部署

---

## 下一步

部署完成后，你可以：

1. 绑定自定义域名（通过 CDN）
2. 设置监控告警
3. 配置 CI/CD 自动部署

详细配置请参考：[docs/SERVERLESS_DEPLOYMENT_GUIDE.md](docs/SERVERLESS_DEPLOYMENT_GUIDE.md)

---

## 文件清单

部署相关的文件：

```
unilife-backend/
├── serverless.py              # 主函数入口
├── serverless_cron.py         # 定时任务函数
├── deploy_serverless.sh       # 打包脚本
├── requirements_serverless.txt # 精简依赖
├── .env.serverless            # 环境变量示例
└── docs/
    └── SERVERLESS_DEPLOYMENT_GUIDE.md  # 详细部署指南
```

---

**需要帮助？**

- 详细文档：`docs/SERVERLESS_DEPLOYMENT_GUIDE.md`
- 提交 Issue：[GitHub Issues](https://github.com/你的仓库/issues)
