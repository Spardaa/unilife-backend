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
│   ├── models/              # 数据模型
│   │   ├── event.py         # 事件、精力等级、类别枚举
│   │   └── preference.py    # 用户偏好模型
│   ├── agents/              # AI Agents
│   │   ├── jarvis.py        # Jarvis Agent (LLM + Tools 架构)
│   │   ├── scheduler.py     # 日程管理
│   │   ├── energy.py        # 精力管理
│   │   └── tools.py         # 工具注册 (18个工具)
│   ├── services/            # 业务服务
│   │   ├── db.py            # 数据库服务 (SQLAlchemy)
│   │   ├── llm.py           # LLM 服务 (DeepSeek + 重试机制)
│   │   └── snapshot.py     # 快照服务
│   ├── api/                 # API 路由
│   │   ├── chat.py          # 对话式接口
│   │   ├── events.py        # 事件 CRUD
│   │   ├── users.py         # 用户管理
│   │   ├── snapshots.py     # 快照管理
│   │   └── stats.py         # 统计数据
│   ├── schemas/             # Pydantic 请求/响应模型
│   └── utils/               # 工具函数
├── prompts/                 # AI 提示词
│   └── jarvis_system.txt    # Jarvis 系统提示词
├── tests/                   # 测试
├── docs/                    # 文档
├── client.py                # 终端客户端
├── init_db.py              # 数据库初始化脚本
├── migrate_db.py           # 数据库迁移脚本
├── test_deepseek_connection.py  # 连接测试工具
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
- 数据库表（users, events, snapshots, user_memory, user_preferences）
- 一个示例用户账号

### 4. 数据库迁移（重要！）

如果您从旧版本升级，需要运行数据库迁移脚本：

```bash
python migrate_db.py
```

这会：
- 自动备份数据库（`unilife.db.backup`）
- 添加 6 个新字段支持 Routine/Habit 管理
- 更新表结构

### 5. 启动开发服务器

```bash
python -m app.main
```

或使用 uvicorn：

```bash
uvicorn app.main:app --reload
```

API 文档访问：http://localhost:8000/docs

### 6. 使用终端客户端（可选）

提供了交互式终端客户端用于测试：

```bash
python client.py
```

功能：
- 用户登录（ID 持久化存储）
- 交互式对话
- 自动处理选项和概率显示
- 彩色输出

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

### 创建长期日程/习惯

```json
POST /api/v1/chat
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "我想每周一三四五健身"
}
```

AI 会询问：
- 时间是否灵活（每天再定 / 固定时间）
- 偏好时间段
- 补课策略（如果某天没时间）

### 查看今天的长期日程

```json
POST /api/v1/chat
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "今天有什么习惯待完成？"
}
```

### 完成习惯并查看统计

```json
POST /api/v1/chat
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "我完成了今天的健身，坚持得怎么样？"
}
```

## AI Agent 架构

### Jarvis Agent (核心智能体)

采用 **LLM + Tools** 架构（类似 Cursor Agent），不再使用意图路由器。

**核心特性：**
- 使用 DeepSeek API 进行自然语言理解和推理
- 通过函数调用（Function Calling）访问 18 个工具
- 自动进行多步推理和工具链式调用
- 最多 30 次迭代，支持复杂任务规划

**工具分类（18个工具）：**

1. **事件管理（6个）**
   - create_event, query_events, delete_event
   - update_event, complete_event, check_time_conflicts

2. **精力管理（2个）**
   - get_user_energy, get_schedule_overview

3. **快照系统（2个）**
   - get_snapshots, revert_snapshot

4. **用户偏好学习（2个）**
   - analyze_preferences - 分析历史偏好，预测用户选择
   - record_preference - 记录用户决策

5. **交互式建议（1个）**
   - provide_suggestions - 提供预设选项，降低用户输入难度
   - 支持概率显示（根据历史偏好+当前上下文动态计算）

6. **长期日程管理（5个）**
   - create_routine - 创建长期习惯（如每周一三四五健身）
   - get_routines - 获取所有长期日程
   - get_active_routines_for_today - 获取今天待完成的习惯
   - mark_routine_completed - 标记完成
   - get_routine_stats - 查看完成率统计

**智能特性：**
- **动态权重决策**：历史偏好（0-100%）+ 当前上下文（0-100%）
- **上下文感知**：综合时间、能量、日程密度等因素
- **概率预测**：为选项添加 AI 预测的用户选择概率
- **灵活时间**：支持"每天再定时间"的 Routine
- **补课机制**：智能建议如何补上未完成的习惯

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
- **events** - 日程事件（包含 6 个 Routine 相关字段）
- **snapshots** - 快照记录
- **user_memory** - 用户记忆与学习数据
- **user_preferences** - 用户偏好学习记录
  - scenario_type - 场景类型（如 time_conflict, event_cancellation）
  - decision - 用户决策
  - context - 上下文信息
  - weight - 权重（默认 1.0）

**Events 表新增字段（支持 Routine）：**
- repeat_rule - 重复规则（daily/weekly/custom）
- is_flexible - 时间是否灵活
- preferred_time_slots - 偏好时间段
- makeup_strategy - 补课策略
- parent_routine_id - 父 routine ID
- routine_completed_dates - 完成日期列表

## 开发计划

### Phase 1: 核心后端 (P0) - ✅ 完成
- [x] 项目初始化
- [x] 数据模型定义
- [x] Jarvis Agent 实现（LLM + Tools 架构）
- [x] 18 个工具实现
- [x] 快照系统
- [x] 精力系统
- [x] 聊天 API 集成
- [x] SQLite 数据库支持
- [x] 数据库迁移脚本

### Phase 2: 智能增强 (P1) - ✅ 核心完成
- [x] 用户偏好学习系统
- [x] 交互式建议（带概率显示）
- [x] 动态权重决策
- [x] 上下文感知分析
- [x] Routine/Habit 管理系统
  - [x] 灵活时间安排
  - [x] 补课机制
  - [x] 完成追踪统计
- [ ] Routine 智能提醒（主动推送）- 待实现
- [ ] chatgpt-on-wechat 集成
- [ ] 智能时间解析增强

### Phase 3: 生活控制台 (P2)
- [ ] 统计 API
- [ ] 精力热力图数据
- [ ] 效率报告
- [ ] 习惯打卡日历视图

### Phase 4: A2A 社交 (P3) - 待定
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
