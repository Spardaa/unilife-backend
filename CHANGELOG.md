# 更新日志

所有重要的项目变更都将记录在此文件中。

## [1.2.0] - 2026-01-22

### 新增功能 ⭐

#### 1. 精力评估系统
- **双维度评估**：体力（Physical）+ 精神（Mental）
- **Energy Evaluator Agent**：自动评估事件精力消耗
  - 评估标准：Low (0-3), Medium (4-6), High (7-10)
  - 输出：level + score + description + factors
- **Smart Scheduler Agent**：智能日程分析
  - 检测连续高强度活动
  - 发现单一维度过度集中
  - 提供优化建议
- **2 个新工具**：
  - `evaluate_energy_consumption` - 评估事件精力消耗
  - `analyze_schedule` - 分析日程合理性

#### 2. 用户画像系统
- **Context Extractor Agent**：观察式用户画像学习
  - 不主动询问，通过事件学习
  - 四维度画像：关系、身份、喜好、习惯
  - 置信度评分和证据追踪
- **用户画像服务**：
  - 自动聚合画像点
  - 持久化存储
  - 支持增量学习
- **Events 表新增字段**：
  - `ai_description` - AI 生成的活动描述
  - `extracted_points` - 提取的用户画像点

#### 3. 对话记录持久化
- **对话记录表**（conversations）
  - 存储完整的对话历史
  - 支持上下文传递
  - 多轮对话支持
- **对话服务**：
  - 保存对话记录
  - 查询对话历史
  - 清除历史记录

#### 4. 增量数据库快照系统
- **快照数据模型**：
  - 只存储变更的行（不是完整表）
  - 支持多表快照
  - before/after 状态记录
- **database_snapshots 表**：
  - 表级快照
  - 变更类型追踪（insert/update/delete）
  - 到期时间管理

### 技术改进

#### 数据模型
- `app/models/user_profile.py` - 用户画像模型
- `app/models/database_snapshot.py` - 快照数据模型
- `app/models/conversation.py` - 对话记录模型
- `app/models/routine.py` - 习惯管理模型
- `app/models/event.py` - 新增增强字段

#### 新增 Agent
- `app/agents/energy_evaluator.py` - 精力评估专家
- `app/agents/smart_scheduler.py` - 智能调度助手
- `app/agents/context_extractor.py` - 用户画像推测专家

#### 新增服务
- `app/services/profile_service.py` - 用户画像服务
- `app/services/routine_service.py` - 习惯管理服务
- `app/services/conversation_service.py` - 对话记录服务

#### 数据库迁移
- `migrate_enhanced_features.py` - 增强功能迁移脚本
- `migrate_routine.py` - Routine 功能迁移脚本
- `migrate_conversations.py` - 对话记录迁移脚本

#### 测试文件
- `test_enhanced_features.py` - 增强功能测试
- `test_routine.py` - Routine 功能测试
- `test_conversation.py` - 对话记录测试

### Bug 修复
- 修复 SQLAlchemy 2.0 兼容性问题
  - 添加 `text()` 包装原生 SQL
  - 修改参数传递方式（tuple → dict）
- 修复 `user_profile.py` 中 `relationship` 单复数不一致问题
- 修复 LLM 服务导入错误（`llm_client` → `llm_service`）

### 工具总数
- 从 18 个工具增加到 **20 个工具**

### 文档更新
- 更新 README.md
  - 项目结构
  - 数据库表说明
  - AI Agent 架构
  - 对话示例
  - 开发计划进度

## [1.1.0] - 2026-01-20

### 新增功能
- Routine/Habit 管理系统
- 智能时间解析
- 用户偏好学习系统
- 交互式建议（带概率显示）

## [1.0.0] - 2026-01-15

### 初始版本
- Jarvis Agent（LLM + Tools 架构）
- 基础事件管理
- 精力系统
- 快照系统
- 对话 API
