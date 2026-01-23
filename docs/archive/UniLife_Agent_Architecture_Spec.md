# **UniLife 架构重构规范：自进化多智能体系统 (Self-Evolving MAS)**

## **1\. 核心目标 (Project Goal)**

将 UniLife 从基于“负面约束”（禁止做什么）的工具型 Chatbot，重构为基于“正面人设”和“长期记忆”的**拟人化智能助理**。  
新架构需实现以下核心能力：

1. **人格与逻辑分离：** 说话好听（Persona）与办事靠谱（Executor）由不同 Agent 负责。  
2. **动态上下文注入：** 摒弃写死的 Prompt，通过数据库动态读取用户画像注入 Prompt。  
3. **自我进化闭环：** 通过后台观察者（Observer）分析用户行为，自动更新用户偏好和决策逻辑，无需人工调整 Prompt。

## **2\. 总体架构设计 (System Architecture)**

系统采用 **双循环 \+ 三层级** 架构。

* **同步循环 (Synchronous Loop):** 毫秒级响应，负责实时对话和任务执行。  
* **异步循环 (Asynchronous Loop):** 分钟级/天级响应，负责反思、总结和更新记忆库。

### **2.1 智能体清单 (Agent Roster)**

| Agent 名称 | 角色定义 | 模型建议 | 职责 |
| :---- | :---- | :---- | :---- |
| **A1. Router** | 调度官 | DeepSeek-V3.2 | 意图识别，分流请求。 |
| **A2. Executor** | 执行官 | DeepSeek-V3.2 | **理性大脑**。处理日程逻辑、API调用、冲突检测。**无感情**。 |
| **A3. Persona** | 陪伴者 | DeepSeek-V3.2 | **感性嘴巴**。负责拟人化回复、情感抚慰。不直接操作数据库。 |
| **A4. Observer** | 观察者 | DeepSeek-V3.2 | **潜意识/灵魂**。后台运行。分析日志，提取画像，生成决策规则。 |

## **3\. 数据结构规范 (Data Structures)**

为了支持“进化”，必须将用户记忆结构化。

### **3.1 用户画像 (User\_Personality\_Profile)**

*用途：注入给 A3. Persona，用于控制语气和聊天内容。*  
{  
  "basic\_info": {  
    "role": "大学生",  
    "major": "通信工程",  
    "hobbies": \["街舞", "摄影"\]  
  },  
  "emotional\_state": {  
    "current\_vibe": "anxious", // 由 Observer 更新  
    "stress\_level": "high",  
    "recent\_events": "临近期末，连续熬夜"  
  },  
  "communication\_style": {  
    "preferred\_tone": "毒舌但靠谱的朋友",  
    "language\_style": "口语化，多用短句"  
  }  
}

### **3.2 用户决策偏好 (User\_Decision\_Profile)**

*用途：注入给 A2. Executor，作为日程安排的“隐性规则”。*  
{  
  "scheduling\_habits": {  
    "start\_of\_day": "09:00", // 早于此时间的任务权重极低  
    "deep\_work\_window": \["14:00", "17:00"\],  
    "meeting\_preference": "stacked" // 会议连着开  
  },  
  "energy\_map": {  
    "Monday": "low", // 周一不排高难度任务  
    "Friday": "high"  
  },  
  "explicit\_rules": \[  
    "周五晚上19:00后锁定为娱乐时间",  
    "健身后必须留30分钟洗澡时间"  
  \]  
}

## **4\. 详细 Agent 设计与 Prompt 策略**

### **Agent 1: Router (调度层)**

* **Input:** 用户当前 query \+ 简短上下文。  
* **Output:** JSON 分类结果。  
* **Logic:**  
  * 涉及日程增删改查 \-\> 路由给 **Executor**。  
  * 纯闲聊、情绪宣泄 \-\> 路由给 **Persona**。  
  * 混合意图 \-\> 先路由给 Executor 获取数据，再传给 Persona 润色。

### **Agent 2: Executor (执行层 \- 理性)**

* **System Prompt 核心:**你是逻辑执行引擎。不要闲聊。只输出 JSON 或 Tool Calls。  
  **必须严格遵守以下用户决策偏好：**  
  {{User\_Decision\_Profile}} (动态注入)  
* **Workflow:**  
  1. 接收任务 ("帮我排这周的复习")。  
  2. 读取日历 API 获取空闲时间。  
  3. **关键步骤：** 将空闲时间与 User\_Decision\_Profile 进行加权匹配（例如：避开周一早上，优先选下午）。  
  4. 输出：具体的日程安排 Plan (JSON)。

### **Agent 3: Persona (交互层 \- 感性)**

* **System Prompt 核心:**你是 UniLife，用户的贴身死党。  
  **当前用户状态：** {{User\_Personality\_Profile.emotional\_state}}  
  **参考语气样本 (Few-Shot):**  
  User: "不想动。" \-\> You: "又来？赶紧的，弄完这波请你喝奶茶。"  
  **任务：** 接收 Executor 的执行结果（或用户的闲聊），用符合人设的语气回复。  
* **约束：** 只有人设描写，**无**“禁止使用XX词汇”等负面约束。

### **Agent 4: Observer (进化层 \- 异步后台)**

* **触发机制：** 定时任务 (Cron Job) 或 会话结束信号。  
* **Input:** 过去 N 小时的完整交互日志 (Raw Logs)。  
* **Output:** 结构化更新指令 (Update Actions)。  
* **Prompt 逻辑:**  
  1. **Fact Extraction:** 发生了什么？（用户推迟了会议）。  
  2. **Insight Generation:** 为什么？（推测：用户早起困难，或对该类任务有抵触）。  
  3. **Rule Formation:** 生成/更新 User\_Decision\_Profile 或 User\_Personality\_Profile。  
* **示例输出:**  
  {  
    "type": "update\_preference",  
    "target": "scheduling\_habits.start\_of\_day",  
    "value": "10:00",  
    "reason": "观察到用户连续3次推迟09:00的任务"  
  }

## **5\. 交互工作流 (Workflows)**

### **场景 A：智能决策 (The Smart Scheduling Flow)**

1. **用户:** "帮我安排三次健身。"  
2. **Router:** 识别为 Task\_Scheduling \-\> 转发给 **Executor**。  
3. **Executor:**  
   * 读取 User\_Decision\_Profile (发现规则: "gym\_time": "20:00")。  
   * 生成方案：周一、三、五 20:00。  
   * 返回结果 JSON。  
4. **Persona:** 接收 JSON。  
   * 读取 User\_Personality\_Profile (状态: "stress\_high")。  
   * 生成回复: "帮你排在晚8点了。最近压力大，去出出汗挺好的。记得带水。"  
5. **用户:** "好。"

### **场景 B：自我进化 (The Evolution Flow \- 后台)**

1. **Observer:** 读取上述日志。  
2. **分析:** Executor 依据规则排了晚8点，用户接受了。  
3. **行动:** 增加 gym\_time: 20:00 规则的 **置信度 (Confidence Score)**。  
4. **数据库:** 更新 User\_Decision\_Profile。

## **6\. 开发实施路线图 (Implementation Steps)**

1. **Phase 1: 解耦 (Decoupling)**  
   * 拆分现有的庞大 Prompt。  
   * 实现 Router \+ Persona \+ Executor 的基本链路。  
   * *此时暂无记忆，仅实现职能分离。*  
2. **Phase 2: 记忆库搭建 (Memory Setup)**  
   * 建立简单的 JSON 存储（File Based 或 NoSQL）。  
   * 定义 Personality 和 Decision 的 JSON Schema。  
   * 在 Executor 和 Persona 启动时实现数据加载 (Load) 和注入 (Inject)。  
3. **Phase 3: 观察者接入 (Observer Integration)**  
   * 编写 Observer 的 Prompt（专注于分析行为与修正规则）。  
   * 建立异步任务队列，处理日志并写回数据库。

## **7\. 给 AI Coding Assistant 的特别指令**

* **Refactoring Pattern:** 请使用 **Strategy Pattern (策略模式)** 来处理不同 Agent 的调用。  
* **Prompt Management:** 请将所有 System Prompts 存放在独立的文件或数据库表中，支持模板变量替换 (Template Strings)。  
* **State Management:** 在会话过程中，请维护一个 ConversationContext 对象，包含 user\_id, current\_intent, last\_tool\_output 等信息。