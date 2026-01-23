# UniLife 长期记忆功能实现状态对比

> **目的**：对比原始规范期望与当前实现，识别差距
> **更新时间**：2026-01-23

---

## 1. 核心功能对比矩阵

| 功能模块 | 规范期望 | 当前实现 | 状态 |
|---------|---------|---------|------|
| **人格画像存储** | User_Personality_Profile 表 | `user_profiles` 表（模型存在，表缺失） | ⚠️ 部分实现 |
| **决策偏好存储** | User_Decision_Profile 表 | ✅ `user_decision_profiles` 表已创建 | ✅ 完全实现 |
| **对话持久化** | 完整对话历史 | ✅ `conversations` + `messages` 表 | ✅ 完全实现 |
| **行为学习** | Observer 提取模式 | ✅ `observer.py` 已实现 | ✅ 完全实现 |
| **规则进化** | 置信度动态更新 | ⚠️ 逻辑存在，但未持久化到 DB | ⚠️ 部分实现 |
| **社交关系管理** | ContactInfo + 关系图谱 | ✅ `UserMemory` 模型定义 | ⚠️ 无数据库表 |
| **行为统计** | 长期行为统计 | ✅ `UserMemory.behavior_stats` | ⚠️ 无数据库表 |
| **跨对话上下文** | 长期记忆查询 | ❌ 未实现 | ❌ 未实现 |

---

## 2. 当前数据库表状态

### ✅ 已创建的表

| 表名 | 用途 | 状态 |
|------|------|------|
| `conversations` | 对话会话 | ✅ 使用中 |
| `messages` | 对话消息 | ✅ 使用中 |
| `user_decision_profiles` | 决策偏好 | ✅ 已创建，可使用 |
| `events` | 事件数据 | ✅ 使用中 |
| `routine_templates` | 长期日程模板 | ✅ 使用中 |
| `routine_instances` | 长期日程实例 | ✅ 使用中 |
| `routine_memories` | 长期日程记忆 | ✅ 使用中 |
| `profile_analysis_logs` | 画像分析日志 | ✅ 使用中 |
| `snapshot_changes` | 快照变更记录 | ✅ 使用中 |

### ⚠️ 模型存在但表缺失

| 模型 | 文件 | 状态 |
|------|------|------|
| `UserProfile` | `user_profile.py` | ❌ 表未创建 |
| `UserMemory` | `memory.py` | ❌ 表未创建 |

---

## 3. 规范期望 vs 当前实现差距

### 3.1 用户人格画像（User_Personality_Profile）

**规范期望**：
```json
{
  "basic_info": {
    "role": "大学生",
    "major": "通信工程"
  },
  "emotional_state": {
    "current_vibe": "anxious",
    "stress_level": "high"
  },
  "communication_style": {
    "preferred_tone": "轻松幽默"
  }
}
```

**当前实现**：
- ✅ `UserProfile` 模型已定义（`app/models/user_profile.py`）
- ❌ `user_profiles` 数据库表**未创建**
- ✅ Observer 可以分析并更新模型
- ⚠️ 更新后的数据**无法持久化到数据库

**影响**：
- Persona Agent 无法读取用户的长期人格状态
- 用户画像无法跨会话保持
- 每次对话都是"冷启动"

---

### 3.2 自我进化闭环

**规范期望的完整流程**：

```
用户交互 → Observer 分析
    ↓
提取模式 → 更新 UserProfile
    ↓
存储到数据库
    ↓
下次对话时读取并注入到 Persona
```

**当前实现的流程**：

```
✅ 用户交互 → ✅ Observer 分析
    ↓
✅ 提取模式 → ⚠️ 更新 UserProfile（仅内存）
    ↓
❌ 存储到数据库（user_profiles 表不存在）
    ↓
❌ 下次对话时无法读取
```

**问题分析**：
1. Observer 的 `analyze_period()` 方法存在但效果有限
2. `profile_service.save_profile()` 会尝试保存但失败
3. 下次对话时 `get_profile()` 返回空，创建新实例
4. **学习无法累积**

---

### 3.3 决策偏好学习

**规范期望**：
```json
{
  "scenario_preferences": [
    {
      "scenario_type": "time_conflict",
      "preferred_action": "merge",
      "confidence": 0.75,
      "sample_count": 12
    }
  ]
}
```

**当前实现**：
- ✅ `User_DecisionProfile` 模型完整
- ✅ 数据库表已创建
- ❌ **Observer 没有更新决策偏好**
- ❌ **Executor 没有读取决策偏好**

**代码验证**：
```python
# executor.py 中有读取逻辑
if context.user_decision_profile:
    # 注入到系统提示
    ...

# 但 observer.py 中没有更新逻辑
def _apply_updates(...):
    # 只更新了 UserProfile
    profile_service.save_profile(user_id, profile)
    # 没有更新 User_DecisionProfile！
```

---

### 3.4 长期记忆查询

**规范期望**：
- "用户上周说了什么？"
- "我上个月是怎么安排的？"
- 跨对话的信息检索

**当前实现**：
- ❌ 完全缺失
- ✅ 单个对话内的历史存在
- ❌ 跨对话的语义检索不存在

---

## 4. 功能完整性评估

### 4.1 已实现 ✅

| 功能 | 说明 |
|------|------|
| 对话持久化 | `conversations` + `messages` 表 |
| 意图识别路由 | Router Agent 正常工作 |
| 工具调用执行 | Executor Agent 正常调用 26 个工具 |
| 拟人化回复 | Persona Agent 生成回复 |
| 异步分析触发 | Observer.on_conversation_end() 正常触发 |
| 决策偏好模型 | User_DecisionProfile 表已创建 |
| 日记生成 | Observer.generate_daily_diary() 正常工作 |

### 4.2 部分实现 ⚠️

| 功能 | 当前状态 | 缺少什么 |
|------|---------|---------|
| **人格画像学习** | 模型存在，Observer 可分析 | ❌ 数据无法持久化（表缺失） |
| **决策偏好学习** | 模型存在 | ❌ Observer 不更新，Executor 不读取 |
| **置信度追踪** | 逻辑存在 | ❌ 无法累积（需要持久化） |

### 4.3 未实现 ❌

| 功能 | 原因 | 优先级 |
|------|------|-------|--------|
| **跨对话上下文** | 架构未设计 | 低 |
| **长期记忆检索** | 需要向量数据库 | 低 |
| **社交关系管理** | 模型存在但无表 | 中 |
| **行为统计累积** | 模型存在但无表 | 中 |

---

## 5. 关键问题分析

### 问题 1：数据无法累积

**现象**：
```
对话 1: Observer 分析 → 更新 UserProfile → 保存失败（表不存在）
对话 2: Observer 分析 → 读取 UserProfile → 空 → 创建新实例
对话 3: Observer 分析 → 读取 UserProfile → 空 → 创建新实例
```

**原因**：
- `user_profiles` 表未创建
- 迁移脚本 `migrate_enhanced_features.py` 未运行

**解决方案**：
```bash
python migrate_enhanced_features.py
```

---

### 问题 2：Executor 不读取决策偏好

**现象**：
```
# orchestrator.py
context.user_decision_profile = None  # 始终为空！
```

**原因**：
1. `User_DecisionProfile` 表是空的（无数据）
2. Orchestrator 没有调用 `decision_profile_service` 来读取
3. **不存在 `decision_profile_service` 服务**

**解决方案**：
1. 创建 `app/services/decision_profile_service.py`
2. 在 Orchestrator 中加载决策偏好
3. Observer 更新决策偏好

---

### 问题 3：Observer 不更新决策偏好

**现象**：
```python
# observer.py 的 _apply_updates()
def _apply_updates(...):
    profile = profile_service.get_or_create_profile(user_id)
    # 只更新 UserProfile，不更新 User_DecisionProfile！
```

**原因**：
- 规范中期望 Observer 同时更新两种画像
- 当前实现只更新了 UserProfile

---

## 6. 与原始规范的主要差距

### 差距 1：画像更新不完整

**规范期望**：
```
Observer 分析后：
1. 更新 UserProfile（人格）
2. 更新 User_DecisionProfile（决策）
```

**当前实现**：
```
Observer 分析后：
1. ✅ 更新 UserProfile（人格）
2. ❌ 不更新 User_DecisionProfile
```

---

### 差距 2：画像读取不完整

**规范期望**：
```
Executor 启动时：
1. 读取 User_Decision_Profile
2. 读取 UserProfile
3. 注入到系统提示
```

**当前实现**：
```
Executor 启动时：
1. ❌ 不读取 User_Decision_Profile
2. ❌ 不读取 UserProfile
3. ✅ 注入 user_id（基本）
```

---

### 差距 3：进化闭环不完整

**规范期望**：
```
用户行为 → Observer 学习 → 更新画像
                ↓
        下次对话时读取并应用
```

**当前实现**：
```
用户行为 → Observer 学习 → 更新 UserProfile（内存）
                ↓
        下次对话时：UserProfile 是空的（未持久化）
```

---

## 7. 建议的修复优先级

### P0（修复核心问题）

1. **创建 user_profiles 表**
   ```bash
   python migrate_enhanced_features.py
   ```
   - 立即修复人格画像持久化

2. **创建 Decision Profile Service**
   - 创建 `app/services/decision_profile_service.py`
   - 实现读取/更新逻辑

3. **在 Orchestrator 中加载画像**
   - 启动时读取 UserProfile 和 User_Decision_Profile
   - 注入到 Executor 和 Persona

---

### P1（完善进化闭环）

4. **Observer 更新决策偏好**
   - 在 `observer.py` 中添加 `User_DecisionProfile` 更新逻辑
   - 实现置信度累积算法

5. **实现置信度持久化**
   - 确保 Observer 的学习可以被保存

---

### P2（长期记忆）

6. **跨对话上下文**
   - 实现长期记忆检索
   - 支持用户查询历史对话

---

## 8. 总结

### 当前状态评估

| 维度 | 完成度 | 评价 |
|------|--------|------|
| **架构设计** | 95% | 四层智能体架构完整 |
| **代码实现** | 80% | 核心逻辑正确，数据持久化不完整 |
| **规范符合度** | 70% | 架构符合规范，但数据流不完整 |
| **自我进化** | 40% | 有逻辑无数据，无法累积学习 |

### 核心问题

> **"有大脑，但记不住"**
> - 架构设计完整，Agent 职责清晰
> - 但 Observer 的学习结果无法持久化
> - 下次对话时又是"冷启动"

### 快速修复路径

```bash
# 1. 创建缺失的表
python migrate_enhanced_features.py

# 2. 代码修改（需要实现）
# - 创建 decision_profile_service.py
# - orchestrator 加载决策偏好
# - observer 更新决策偏好
```

### 预期修复后

| 功能 | 修复后状态 |
|------|----------|
| 人格画像持久化 | ✅ 完全可用 |
| 决策偏好学习 | ✅ 开始累积 |
| 跨对话记忆 | ✅ 基础可用 |
| 自我进化闭环 | ✅ 完整实现 |

---

*文档版本: 1.0*
*完成时间: 2026-01-23*
