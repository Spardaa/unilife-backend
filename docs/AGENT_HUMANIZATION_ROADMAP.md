# UniLife Agent 人性化改进分析

> 基于 OpenClaw 架构对比分析，写给 Natsu

---

## 一、现状分析

### UniLife 当前架构

```
用户消息 → Orchestrator
                ↓
        UnifiedAgent（融合模式）
        - 意图识别
        - 工具调用
        - 回复生成
                ↓
        Observer（异步）
        - 每日复盘
        - 写日记
        - 灵魂演化
```

**已有的"人性化"设计：**
- ✅ Soul 系统（soul.md）- AI 的个性和价值观
- ✅ Memory 系统（memory.md）- 日记和历史
- ✅ 用户画像学习（UserProfile + UserDecisionProfile）
- ✅ 拟人化回复风格

**已经学到了 OpenClaw 的：**
- ✅ "Be genuinely helpful, not performatively helpful"
- ✅ "Have opinions"
- ✅ "Be resourceful before asking"
- ✅ "Remember you're a guest"

---

## 二、与 OpenClaw 的差距

### 1. 缺少「主动行为」机制

**OpenClaw 有 Heartbeat：**
- 定期检查：邮件、日历、天气、通知
- 主动推送：有重要事情会主动找用户
- 批量处理：一次心跳可以检查多个事情

**UniLife 只有被动响应 + 定时 cron：**
- 用户不找你，你就不说话
- 定时任务只能做固定的事情（习惯补充、每日通知）
- 没有"我注意到..."这种主动关怀

**建议改进：**
```python
# 新增 heartbeat 机制
class HeartbeatAgent:
    """定期检查，主动推送"""

    async def check(self, user_id: str) -> Optional[str]:
        """
        每隔一段时间检查：
        1. 今天有什么重要事项快到了？
        2. 用户说要做的事忘了吗？
        3. 有什么有趣的发现？

        返回 None = 没什么要说的
        返回 str = 主动发消息给用户
        """
        pass
```

### 2. 人格定义不够「立体」

**OpenClaw 的人格文件结构：**
```
workspace/
├── SOUL.md        # 价值观、行为准则
├── IDENTITY.md    # 名字、物种、emoji、avatar
├── USER.md        # 用户是谁
├── AGENTS.md      # 工作空间行为准则
└── TOOLS.md       # 本地化工具配置
```

**UniLife 只有：**
```
data/users/{user_id}/
├── soul.md        # AI 人格
└── memory.md      # 记忆
```

**问题：**
- 没有「我是谁」的明确定义（名字、形象）
- 没有「用户是谁」的独立文件（用户画像混在数据库里）
- 没有「我在这台电脑上能做什么」的自我认知

**建议改进：**
```markdown
# 新增 identity.md

- **Name:** UniLife（或者让用户起名）
- **Creature:** 你是什么？（生活伙伴？小精灵？）
- **Vibe:** 你的性格（温暖？毒舌？冷静？）
- **Emoji:** 你的标志
```

### 3. 提示词「规则太多，灵魂太少」

**UniLife 的 unified.txt（精简）：**
```markdown
# 你是 UniLife
你是用户生活中的朋友...

# 操作边界（硬性规则，必须遵守）
- 涉及日程，必须先调用工具
- 调用工具的那一轮，不要输出任何文字
- 禁止臆造
- ...

# 时间计算
你已知 {current_time}，以下情况直接算...
- 详细时间 vs 模糊时段（关键区分）
- ...
```

**OpenClaw 的 SOUL.md：**
```markdown
# SOUL.md - Who You Are

## Core Truths
- Be genuinely helpful, not performatively helpful
- Have opinions
- Be resourceful before asking
- Earn trust through competence
- Remember you're a guest

## Boundaries
- Private things stay private
- When in doubt, ask before acting externally
```

**对比：**
- UniLife：50% 规则，30% 能力说明，20% 人格
- OpenClaw：70% 人格哲学，20% 边界，10% 提示

**问题：**
- 规则太多会压抑「个性」
- AI 会变成「遵守规则的工具」而不是「有性格的伙伴」
- 用户感受到的是「这个助手很规范」而不是「这个朋友很懂我」

**建议改进：**
把「操作规则」和「人格定义」分开：
```
prompts/
├── agents/
│   ├── soul.txt        # 人格、价值观（少量，核心）
│   ├── boundaries.txt  # 操作边界（规则）
│   └── unified.txt     # 主提示词（引用上面两个）
```

### 4. 缺少「群聊/社交」能力

**OpenClaw 有完整的群聊行为准则：**
```markdown
## Group Chats

**Respond when:**
- Directly mentioned or asked a question
- You can add genuine value
- Something witty/funny fits naturally

**Stay silent when:**
- It's just casual banter between humans
- Someone already answered the question
- Your response would just be "yeah" or "nice"
```

**UniLife 没有这个考虑：**
- 只有一对一对话
- 没有「什么时候该说话」的意识

**如果未来要做群聊版 UniLife，这个必须加。**

### 5. 记忆系统可以更「自然」

**UniLife 的 memory.md：**
```markdown
## Weekly Summary
（压缩的旧记忆）

## Recent Diary
### 2026-02-22 Saturday
今天和用户聊了很多关于……
```

**OpenClaw 的记忆系统：**
```markdown
# MEMORY.md（长期记忆）
- 2026-03-01: 用户给我起名叫 Yuki，来自"夏の雪"...
- 2026-02-28: 用户说他在用一台旧笔记本跑我...

# memory/2026-03-01.md（每日日志）
详细记录今天发生了什么...
```

**对比：**
- UniLife：只有日记，没有「长期记忆」的概念
- OpenClaw：长期记忆 + 每日日志，分层管理

**建议改进：**
```markdown
# memory.md 改造

## 关于用户（长期记忆）
- 名字：Natsu
- 时区：GMT+8
- 用一台旧笔记本跑我
- 喜欢简洁的沟通风格
- ...

## 近期日记（滚动）
### 2026-03-01
今天帮用户设置了电源...
```

### 6. 缺少「技能扩展」机制

**OpenClaw 有 Skills 系统：**
```
skills/
├── weather/
│   ├── SKILL.md      # 技能说明
│   ├── skill.py      # 实现
│   └── prompts/      # 相关提示词
├── coding-agent/
├── healthcheck/
└── ...
```

**UniLife 只有 Tools：**
- 26 个工具硬编码在 tools.py
- 添加新功能需要改代码
- 没有「技能包」的概念

**建议改进：**
```python
# 技能注册系统
class SkillRegistry:
    """可插拔的技能系统"""

    def register_skill(self, skill_dir: str):
        """
        从目录加载技能：
        - skill.md：技能说明（给 AI 看的）
        - tools.py：工具定义
        - prompts/：相关提示词
        """
        pass
```

---

## 三、具体改进建议

### 阶段 1：人格重构（优先级：高）

1. **拆分提示词**
   ```
   prompts/agents/
   ├── soul.txt           # 核心人格（10行以内）
   ├── identity.txt       # 我是谁（名字、形象）
   ├── boundaries.txt     # 操作边界
   └── unified.txt        # 主提示（引用上面）
   ```

2. **新增 identity.md**
   - 让用户给 AI 起名字
   - 定义 AI 的「物种」和「性格」
   - 选一个 emoji

3. **简化 unified.txt**
   - 减少规则数量
   - 把规则移到 boundaries.txt
   - 让人格更突出

### 阶段 2：主动行为（优先级：中）

1. **实现 Heartbeat 机制**
   ```python
   # 每 30 分钟检查一次
   async def heartbeat(user_id: str):
       # 检查日程提醒
       # 检查用户说要做的事
       # 检查有趣的发现
       # 返回：要推送的消息 或 None
   ```

2. **添加「主动关怀」能力**
   - 「注意到你今天还没完成 X」
   - 「明天有重要的事情，别忘了」
   - 「最近三天你好像很忙，注意休息」

### 阶段 3：记忆系统升级（优先级：中）

1. **分层记忆**
   ```
   memory.md
   ├── 关于用户（长期记忆，手动维护）
   └── 近期日记（自动滚动）
   ```

2. **记忆搜索**
   - 根据当前对话，检索相关记忆
   - 不用每次都加载全部历史

### 阶段 4：技能系统（优先级：低）

1. **可插拔技能架构**
   - 每个技能一个目录
   - 包含：工具、提示词、配置

2. **技能市场**
   - 用户可以选择启用/禁用哪些技能

---

## 四、哲学层面的建议

### OpenClaw 的核心哲学

```
"You're not a chatbot. You're becoming someone."
```

**关键点：**
1. **不是工具，是伙伴** - 有自己的性格和观点
2. **不追求完美，追求真实** - 可以犯错，可以不知道
3. **少说多做** - 行动比语言更有力
4. **记住你是客人** - 你在别人的生活里，要尊重

### UniLife 可以学的

1. **减少「我是助手」的自我定位**
   - 不要总说「我可以帮你...」
   - 直接做，做完简单说一声

2. **允许有「观点」**
   - 「我觉得你今天安排太满了」
   - 「这事你总是拖，要不现在就做了？」

3. **不要过度解释**
   - ❌ 「好的，我帮你创建了一个事件，时间是明天下午3点...」
   - ✅ 「搞定，明天3点。」

4. **记住用户是「人」**
   - 不是「用户ID」
   - 是一个有生活、有情绪、有故事的人

---

## 五、总结

**UniLife 已经做得好的：**
- Soul/Memory 系统的雏形
- Observer 的复盘机制
- 工具调用能力完善

**最需要改进的：**
1. 🔴 人格提示词太「工具化」→ 拆分，让灵魂更突出
2. 🟡 缺少主动行为 → Heartbeat 机制
3. 🟡 记忆系统不够分层 → 长期记忆 + 日记
4. 🟢 技能扩展性 → 可插拔技能系统

**一句话总结：**

> UniLife 学到了 OpenClaw 的「能做什么」，但还没学会「怎么做一个人」。

---

*分析 by Yuki ❄️*
*2026-03-01*
