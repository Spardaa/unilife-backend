# UniLife 记忆系统改进方案

> 日期：2026-03-01
> 作者：Yuki（基于 Natsu 的需求）
> 目标：改进记忆注入逻辑，让 AI 更「记得」用户

---

## 📊 一、现状分析

### 1.1 记忆存储结构（memory.md）

```markdown
# UniLife Memory

## UniLife 眼中的用户
_（最后更新：YYYY-MM-DD）_
（AI 对用户的长期认识）

## Weekly Summary
（压缩的旧记忆）

## Recent Diary
### 2026-03-01
（今天的日记）
```

### 1.2 记忆注入流程

```
用户消息
    ↓
ContextFilterAgent（判断是否需要注入记忆）
    ↓
├─ 需要注入 → get_relevant_memory(query) / get_recent_diary()
│              ↓
│              context.request_metadata["memory_content"] = 记忆内容
│
└─ 不需要注入 → memory_content = ""
    ↓
UnifiedAgent 构建提示词
    ↓
替换 {memory_content}
```

### 1.3 调用链路

| 文件 | 职责 |
|------|------|
| `context_filter_agent.py` | 判断是否需要注入记忆，选择记忆片段 |
| `memory_service.py` | 提供记忆读取方法 |
| `unified_agent.py` | 构建提示词时注入记忆 |
| `observer.py` | 每日写日记，更新用户认知 |

---

## ❌ 二、问题诊断

### 2.1 长期记忆从未被注入

**问题位置：** `memory_service.py` → `get_relevant_memory()`

```python
# 只搜索 ## Recent Diary 部分
diary_match = re.search(r"## Recent Diary\s*\n(.*)", full, re.DOTALL)
```

**影响：**
- `## UniLife 眼中的用户` 从来没被注入到提示词
- AI 只知道「最近发生了什么」，不知道「用户是谁」
- 长期积累的用户画像完全浪费

**严重程度：** 🔴 高

---

### 2.2 关键词匹配太弱

**问题位置：** `memory_service.py` → `get_relevant_memory()`

```python
# 简单的关键词重叠评分
query_words = set(query.lower().split())
entry_words = set(re.sub(r"[^\w\s]", "", entry.lower()).split())
overlap = len(query_words & entry_words)
```

**问题：**
- 太粗糙，容易漏掉相关记忆
- 例：query = 「用户喜欢什么」，日记 = 「他偏好简洁风格」→ 匹配不上
- 中文分词问题：简单的空格分割对中文效果差

**严重程度：** 🟡 中

---

### 2.3 ContextFilter 降级时不注入记忆

**问题位置：** `context_filter_agent.py` → `process()`

```python
# fallback 时
return AgentResponse(
    metadata={
        "inject_memory": False,
        "memory_content": ""
    }
)
```

**影响：**
- LLM 调用失败时，直接不注入记忆
- AI 完全「失忆」，不知道用户是谁

**严重程度：** 🟡 中

---

### 2.4 记忆分层不清晰

**问题位置：** 整体架构

| 区块 | 现状 | 应该 |
|------|------|------|
| `## UniLife 眼中的用户` | ❌ 从不注入 | ✅ **每次都注入**（长期记忆） |
| `## Weekly Summary` | ❌ 从不注入 | ⚠️ 可选注入（历史摘要） |
| `## Recent Diary` | ✅ 选择性注入 | ✅ 选择性注入（短期记忆） |

**影响：**
- 记忆层次混乱
- 长期记忆（用户画像）和短期记忆（日记）权重一样

**严重程度：** 🔴 高

---

### 2.5 memory.md 格式不够自然

**问题位置：** `memory_service.py` → `_INITIAL_MEMORY`

```markdown
## UniLife 眼中的用户

_（暂无记录）_
```

**问题：**
- 区块名字像数据库字段，不够人性化
- 应该更像「AI 对用户的认识」，而不是「系统记录」

**严重程度：** 🟢 低

---

## ✅ 三、改进方案

### 3.1 核心原则

1. **长期记忆优先** — 用户画像每次都注入
2. **分层清晰** — 长期记忆 vs 短期记忆分离
3. **降级友好** — LLM 失败时也要有基本记忆
4. **格式自然** — 用人话描述，不是配置列表

---

### 3.2 改进 memory.md 格式

**Before:**
```markdown
# UniLife Memory

## UniLife 眼中的用户

_（暂无记录）_

## Weekly Summary


## Recent Diary
```

**After:**
```markdown
# UniLife 记忆

## 关于用户（长期记忆）

_（AI 对用户的认识，每次对话都会带上这部分）_

- 时区：GMT+8
- 作息：夜猫子，睡够 6 小时优先
- 最近在忙：UniLife 项目、机器人舞蹈研究
- 偏好：简洁的沟通风格，不喜欢废话
- 关注：AI Agent（to C）、机器人表演
- （其他重要的事...）

---

## 本周观察

_（Observer 定期更新，记录模式和行为变化）_

用户这周好像很忙，经常熬夜...

---

## 近期日记

### 2026-03-01
今天第一次和用户正式聊天，帮他设置了电源、聊了 UniLife 的改进方向...

### 2026-02-28
（昨天的日记）
```

**关键改进：**
- 区块名字更人性化
- 「关于用户」明确标注为长期记忆
- 结构更清晰（用 `---` 分隔）

---

### 3.3 新增方法：获取长期记忆

**文件：** `app/services/memory_service.py`

```python
def get_user_profile(self, user_id: str) -> str:
    """
    获取「关于用户」的长期记忆（每次都注入）
    
    Returns:
        用户画像文本，如无则返回空字符串
    """
    full = self.get_memory(user_id)
    
    # 匹配新格式：## 关于用户（长期记忆）
    match = re.search(r"## 关于用户.*?\n(.*?)(?=\n---|\n## |$)", full, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # 兼容旧格式：## UniLife 眼中的用户
    match = re.search(r"## UniLife 眼中的用户\s*\n(.*?)(?=\n## |$)", full, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    return ""
```

---

### 3.4 改进 UnifiedAgent 记忆注入逻辑

**文件：** `app/agents/unified_agent.py`

**Before:**
```python
memory_content = context.request_metadata.get("memory_content", "")
if not memory_content:
    memory_content = "（暂无相关记忆）"
```

**After:**
```python
# 1. 长期记忆（每次都注入）
user_profile = memory_service.get_user_profile(context.user_id)

# 2. 短期记忆（ContextFilter 选择性注入）
recent_memory = context.request_metadata.get("memory_content", "")

# 3. 合并
if user_profile or recent_memory:
    memory_content = ""
    if user_profile:
        memory_content += f"## 关于用户\n\n{user_profile}\n\n---\n\n"
    if recent_memory:
        memory_content += f"## 近期记忆\n\n{recent_memory}"
else:
    memory_content = "（暂无相关记忆）"
```

---

### 3.5 简化 ContextFilter 记忆判断

**文件：** `app/agents/context_filter_agent.py`

**改进点：**

1. **降级时也注入基本记忆**

```python
# fallback 时
recent_memory = memory_service.get_recent_diary(context.user_id, days=3)
return AgentResponse(
    metadata={
        "inject_memory": True,  # 改为 True
        "memory_content": recent_memory  # 注入近 3 天日记
    }
)
```

2. **简化判断逻辑**（可选）

```python
# 不再复杂判断，默认都注入近 3 天日记
# 长期记忆由 UnifiedAgent 负责注入
should_inject_memory = True  # 默认注入
memory_query = ""  # 不再精确查询，直接取近 3 天
```

---

### 3.6 改进 Observer 写日记逻辑

**文件：** `app/agents/observer.py` + `prompts/agents/observer.txt`

**改进点：**

1. **更新用户画像更积极**

```python
# 每日复盘时，除了写日记，也更新「关于用户」
if result.get("user_profile_update"):
    memory_service.update_user_profile(user_id, result["user_profile_update"])
```

2. **Observer prompt 增加用户画像更新任务**

```markdown
# 深夜复盘任务

### 1. 写日记 (diary_entry)
...

### 2. 更新用户画像 (user_profile_update)
- **可选。** 如果今天你对用户有了新的认识，更新「关于用户」区块。
- 比如：发现用户偏好、习惯、最近关注的事。
- 如果没有新的认识，返回 `null`。

### 3. 灵魂演化 (soul_update)
...
```

---

### 3.7 改进记忆检索（可选，Phase 2）

**如果后续想改进关键词匹配：**

```python
def get_relevant_memory(self, user_id: str, query: str, days: int = 14) -> str:
    """
    改进版：更智能的记忆检索
    """
    full = self.get_memory(user_id)
    
    # 1. 提取所有日记条目
    diary_match = re.search(r"## (近期日记|Recent Diary)\s*\n(.*)", full, re.DOTALL)
    if not diary_match:
        return ""
    
    diary_body = diary_match.group(2)
    entries = re.split(r"(?=### \d{4}-\d{2}-\d{2})", diary_body)
    
    # 2. 关键词扩展（简单版）
    query_keywords = self._expand_keywords(query)
    
    # 3. 评分
    scored = []
    for entry in entries:
        if not entry.strip():
            continue
        score = self._score_entry(entry, query_keywords)
        scored.append((score, entry))
    
    # 4. 返回最相关的 1-3 条
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [e for s, e in scored[:3] if s > 0]
    
    return "\n\n".join(top) if top else self.get_recent_diary(user_id, days=3)

def _expand_keywords(self, query: str) -> Set[str]:
    """关键词扩展（同义词、相关词）"""
    # 简单实现：分词 + 常见同义词
    keywords = set(jieba.cut(query)) if 'jieba' in sys.modules else set(query.split())
    
    # 同义词映射（可扩展）
    synonyms = {
        "喜欢": ["偏好", "爱", "倾向"],
        "不喜欢": ["讨厌", "反感", "避免"],
        "忙": ["忙碌", "没时间", "紧张"],
        # ...
    }
    
    for word in list(keywords):
        if word in synonyms:
            keywords.update(synonyms[word])
    
    return keywords
```

---

## 📋 四、修改清单

### 4.1 必须修改（解决核心问题）

| 优先级 | 文件 | 改动 | 工作量 |
|--------|------|------|--------|
| 🔴 P0 | `memory_service.py` | 新增 `get_user_profile()` 方法 | ⭐ 小 |
| 🔴 P0 | `unified_agent.py` | 改进记忆注入逻辑（长期+短期分离） | ⭐ 小 |
| 🟡 P1 | `context_filter_agent.py` | 降级时也注入记忆 | ⭐ 小 |
| 🟡 P1 | `memory_service.py` | 改进 `_INITIAL_MEMORY` 格式 | ⭐ 小 |

### 4.2 可选改进（提升体验）

| 优先级 | 文件 | 改动 | 工作量 |
|--------|------|------|--------|
| 🟢 P2 | `observer.py` | 增加用户画像更新任务 | ⭐⭐ 中 |
| 🟢 P2 | `prompts/agents/observer.txt` | 更新 prompt 模板 | ⭐ 小 |
| 🟢 P2 | `memory_service.py` | 改进关键词匹配（加同义词） | ⭐⭐ 中 |

---

## 🧪 五、测试验证

### 5.1 单元测试

```python
# test_memory_upgrade.py

def test_get_user_profile():
    """测试获取用户画像"""
    # 准备测试数据
    memory_content = """# UniLife 记忆

## 关于用户（长期记忆）

- 时区：GMT+8
- 作息：夜猫子
- 偏好：简洁

---

## 近期日记

### 2026-03-01
今天聊了很多...
"""
    
    # 写入测试文件
    user_data_service.write_file(test_user_id, "memory.md", memory_content)
    
    # 测试
    profile = memory_service.get_user_profile(test_user_id)
    
    assert "时区：GMT+8" in profile
    assert "夜猫子" in profile
    print("✓ get_user_profile() works")


def test_unified_agent_memory_injection():
    """测试 UnifiedAgent 记忆注入"""
    # 模拟 context
    context = ConversationContext(
        user_id=test_user_id,
        user_message="你好",
        request_metadata={
            "memory_content": "今天聊了很多..."
        }
    )
    
    # 构建提示词
    agent = UnifiedAgent()
    prompt = agent._build_prompt(context, identity, soul_content)
    
    # 验证
    assert "关于用户" in prompt or "UniLife 眼中的用户" in prompt
    assert "近期记忆" in prompt or "今天聊了很多" in prompt
    print("✓ Memory injection works")
```

### 5.2 集成测试

```bash
# 1. 启动服务
python -m uvicorn app.main:app --reload

# 2. 发送消息，观察日志
# 检查 memory_content 是否包含「关于用户」

# 3. 查看 memory.md
# 验证格式是否正确
```

---

## 📌 六、注意事项

### 6.1 向后兼容

- `get_user_profile()` 需要兼容旧格式 `## UniLife 眼中的用户`
- 新格式 `## 关于用户（长期记忆）` 和旧格式都要支持

### 6.2 性能考虑

- `get_user_profile()` 每次对话都调用，需要高效
- 考虑加缓存（可选）

### 6.3 Token 消耗

- 长期记忆 + 短期记忆会增加 token
- 建议限制长度：
  - 用户画像：< 500 字符
  - 近期日记：< 1000 字符

---

## 🎯 七、预期效果

### Before

```
用户：你好
AI：（不知道用户是谁，每次都像第一次见面）
```

### After

```
用户：你好
AI：（知道用户是 Natsu，夜猫子，偏好简洁）
    「嘿 Natsu，今天这么早起来了？」
```

---

## 📅 八、实施计划

| 阶段 | 内容 | 时间 |
|------|------|------|
| **Phase 1** | 核心修复（P0 + P1） | 1-2 小时 |
| **Phase 2** | 体验优化（P2） | 2-3 小时 |
| **Phase 3** | 智能检索（向量搜索） | 后续 |

---

**文档完成。需要我开始实施 Phase 1 吗？**
