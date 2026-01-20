# UniLife Backend

AI-powered life scheduling assistant - Backend API

## 项目简介

UniLife 是一个具备自主决策能力的 AI 生活管家，它理解用户的精力状态、任务的急迫程度以及社交关系，核心目标是：**消除"认知摩擦"，让用户从繁琐的日程安排中解放出来，专注于生活本身。**

## 技术栈

- **后端框架**: FastAPI
- **数据库**: SQLite (开发) / PostgreSQL (生产)
- **ORM**: SQLAlchemy
- **LLM**: DeepSeek API
- **部署**: Railway / Render / 国内云服务

## 项目结构

```
unilife-backend/
├── app/
│   ├── main.py              # FastAPI 应用入口
│   ├── config.py            # 配置文件
│   ├── models/              # 数据模型 (Event, User, Snapshot, Memory)
│   ├── agents/              # AI Agents
│   │   ├── router.py        # 意图识别与路由
│   │   ├── scheduler.py     # 日程执行
│   │   ├── energy.py        # 精力管理
│   │   └── intent.py        # 意图枚举
│   ├── services/            # 业务服务
│   │   ├── db.py            # 数据库服务 (SQLAlchemy)
│   │   ├── llm.py           # LLM 服务 (DeepSeek)
│   │   └── snapshot.py     # 快照服务
│   ├── api/                 # API 路由
│   │   ├── chat.py          # 对话式接口
│   │   ├── events.py        # 事件 CRUD
│   │   ├── users.py         # 用户管理
│   │   ├── snapshots.py     # 快照管理
│   │   └── stats.py         # 统计数据
│   ├── schemas/             # Pydantic 请求/响应模型
│   └── utils/               # 工具函数
├── tests/                   # 测试
├── docs/                    # 文档
├── init_db.py              # 数据库初始化脚本
├── requirements.txt         # 依赖包
└── .env.example             # 环境变量示例
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填写以下必需配置：
- `DEEPSEEK_API_KEY`: DeepSeek API key
- `JWT_SECRET_KEY`: JWT 密钥（生产环境必须更改）

数据库默认使用 SQLite，无需额外配置。如需使用 PostgreSQL，请设置：
- `DB_TYPE=postgresql`
- `POSTGRESQL_URL=postgresql+asyncpg://user:password@localhost:5432/unilife`

### 3. 初始化数据库（可选）

运行初始化脚本创建数据库表和示例数据：

```bash
python init_db.py
```

这会创建：
- 数据库表（users, events, snapshots, user_memory）
- 一个示例用户账号

### 4. 启动开发服务器

```bash
python -m app.main
```

或使用 uvicorn：

```bash
uvicorn app.main:app --reload
```

API 文档访问：http://localhost:8000/docs

## API 端点

### 核心接口

- `POST /api/v1/chat` - 对话式接口（主要交互入口）
- `GET /api/v1/chat/history` - 获取对话历史
- `DELETE /api/v1/chat/history` - 清除对话历史
- `POST /api/v1/chat/feedback` - 提供反馈

### 事件管理

- `GET /api/v1/events` - 获取事件列表
- `POST /api/v1/events` - 创建事件
- `GET /api/v1/events/{id}` - 获取单个事件
- `PUT /api/v1/events/{id}` - 更新事件
- `DELETE /api/v1/events/{id}` - 删除事件

### 用户管理

- `POST /api/v1/users/register` - 注册
- `POST /api/v1/users/login` - 登录
- `GET /api/v1/users/me` - 获取当前用户
- `PUT /api/v1/users/me` - 更新用户信息
- `PUT /api/v1/users/me/energy` - 更新精力配置

### 快照系统

- `GET /api/v1/snapshots` - 获取快照列表
- `POST /api/v1/snapshots/{id}/revert` - 回退到快照

### 统计数据

- `GET /api/v1/stats/energy` - 精力统计
- `GET /api/v1/stats/productivity` - 效率统计
- `GET /api/v1/stats/time-saved` - 节省时间统计

## 对话示例

### 创建事件

```json
POST /api/v1/chat
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "帮我安排明天下午3点开会，大概1小时"
}
```

### 查询日程

```json
POST /api/v1/chat
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "我明天有什么安排？"
}
```

### 撤销操作

```json
POST /api/v1/chat
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "撤销刚才的操作"
}
```

### 查看精力状态

```json
POST /api/v1/chat
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "我现在状态怎么样？"
}
```

## Multi-Agent 架构

### RouterAgent
意图识别与路由，决定调用哪个下游 Agent
- 支持多种意图分类（创建事件、查询、更新、删除、撤销等）
- 使用 DeepSeek API 进行自然语言理解
- 包含基于关键词的降级方案

### ScheduleAgent
日程 CRUD 执行、时间冲突处理、智能排程
- 从自然语言解析事件信息
- 检测时间冲突
- 支持多种事件类型（固定日程、DDL 任务、浮动任务）

### EnergyAgent
精力值计算、疲劳检测、排程建议
- 基于 E-U (Energy-Urgency) 模型进行排程
- 疲劳检测与警告
- 精力优化建议

### SnapshotManager
快照创建与回退
- 自动记录所有日程变更
- 支持一键撤销
- 自动清理过期快照

### MemoryAgent（待实现）
用户画像管理、习惯学习、长期记忆

## 数据库

### SQLite (默认 - 开发环境)
- 本地文件数据库，无需外部服务
- 数据文件: `unilife.db`
- 适合快速开发和测试

### PostgreSQL (生产环境)
- 支持高并发和大数据量
- 可配置国内云服务（腾讯云、阿里云等）
- 迁移方式：修改 `.env` 中的 `DB_TYPE` 和 `POSTGRESQL_URL`

### 数据表

- **users** - 用户信息及精力配置
- **events** - 日程事件
- **snapshots** - 快照记录
- **user_memory** - 用户记忆与学习数据

## 开发计划

### Phase 1: 核心后端 (P0) - ✅ 完成
- [x] 项目初始化
- [x] 数据模型定义
- [x] RouterAgent 实现
- [x] ScheduleAgent 实现
- [x] 快照系统
- [x] 精力系统 (EnergyAgent)
- [x] 聊天 API 集成
- [x] SQLite 数据库支持

### Phase 2: 增强功能
- [ ] chatgpt-on-wechat 集成
- [ ] MemoryAgent 实现
- [ ] 智能时间解析增强
- [ ] 更精准的意图识别

### Phase 3: 生活控制台 (P3)
- [ ] 统计 API
- [ ] 精力热力图数据
- [ ] 效率报告

### Phase 4: A2A 社交 (P2) - 待定
- [ ] Agent 代理谈判
- [ ] Agent-Aware 通讯录
- [ ] 社交防火墙

## 测试

运行测试：

```bash
pytest
```

## 文档

详细的产品需求文档请查看 `docs/` 目录：

- `UniLife_PRD_v1.md` - 产品需求文档
- `UniLife_Product_Functional_Spec.md` - 功能详述文档

## License

MIT
