"""
Unified Agent - 融合 Agent
整合 Router/Executor/Persona 能力的单一 Agent

核心流程：
1. 构建系统提示词（注入人格 + 决策偏好）
2. 调用 LLM with tools
3. 迭代执行工具调用（最多 30 步）
4. 生成最终拟人化回复
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, date
import json
import logging

from app.services.llm import llm_service
from app.services.prompt import prompt_service
from app.agents.base import (
    BaseAgent, ConversationContext, AgentResponse, build_messages_from_context
)
from app.agents.tools import tool_registry
from app.services.db import db_service
from app.services.soul_service import soul_service


logger = logging.getLogger("unified_agent")


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


class UnifiedAgent(BaseAgent):
    """
    Unified Agent - 融合 Agent
    
    整合 Router/Executor/Persona 能力：
    - 直接判断是否需要调用工具（原 Router 的意图识别）
    - 执行工具调用（原 Executor）
    - 生成拟人化回复（原 Persona）
    
    优势：
    - LLM 调用次数从 3-4 次降为 1-2 次
    - 响应延迟显著降低
    - 系统复杂度降低
    """
    
    name = "unified_agent"
    
    def __init__(self):
        self.llm = llm_service
        self.tools = tool_registry
        self.max_iterations = 30  # 支持复杂多步操作
    
    async def process(self, context: ConversationContext) -> AgentResponse:
        """
        处理用户消息，整合意图识别、工具调用和回复生成
        
        Args:
            context: 对话上下文（包含用户画像、决策偏好、历史消息）
        
        Returns:
            AgentResponse: 包含最终回复、操作记录、建议选项等
        """
        # 1. 构建系统提示（注入人格画像、决策偏好和项目列表）
        system_prompt = await self._build_system_prompt_async(context)
        
        # 在系统提示中明确告知 user_id
        system_prompt += f"\n\n## 当前用户\n\n用户ID: {context.user_id}\n在调用需要 user_id 的工具时，请直接使用此 ID，不需要询问用户。"
        
        # 如果有记忆内容（由 ContextFilter 选择性注入），替换占位符
        memory_content = context.request_metadata.get("memory_content", "")
        if not memory_content:
            memory_content = "（暂无相关记忆）"
        
        # 2. 构建消息列表
        messages = build_messages_from_context(
            context=context,
            system_prompt=system_prompt,
            max_history=20  # UnifiedAgent 可以处理更多历史
        )
        
        # 3. 对话循环 - 支持多步工具调用
        iterations = 0
        tool_results = []
        all_tool_calls = []
        # 保存 (tool_call, tool_result_json) 配对，用于持久化到数据库
        tool_call_result_pairs = []
        final_content = ""
        
        while iterations < self.max_iterations:
            iterations += 1
            
            # 获取工具列表（OpenAI 格式）
            tools_schema = self._convert_tools_to_openai_format()
            
            # 如果处于破冰阶段，剥夺其他工具，只保留 set_agent_identity 以防 LLM 乱发散
            user_profile = context.user_profile or {}
            needs_onboarding = user_profile.get("preferences", {}).get("needs_onboarding", False)
            if needs_onboarding or identity_service.is_default(context.user_id):
                tools_schema = [t for t in tools_schema if t.get("function", {}).get("name") == "set_agent_identity"]
            
            # 调用 LLM
            response = await self.llm.tools_calling(
                messages=messages,
                tools=tools_schema,
                tool_choice="auto",
                temperature=0.7  # 平衡创意和准确性
            )
            
            tool_calls = response.get("tool_calls")
            content = response.get("content", "")
            
            if tool_calls:
                # LLM 决定调用工具
                all_tool_calls.extend(tool_calls)
                messages.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls
                })
                
                # 执行所有工具调用
                for tool_call in tool_calls:
                    function_name = tool_call["function"]["name"]
                    function_args = json.loads(tool_call["function"]["arguments"])
                    
                    # 自动添加 user_id（如果工具需要但用户没提供）
                    # 修复：通过 ToolRegistry 检查工具定义，而不是检查 tool_call 字符串
                    tool_def = self.tools.get_tool(function_name)
                    if tool_def:
                        tool_params = tool_def.get("parameters", {}).get("properties", {})
                        if "user_id" in tool_params and "user_id" not in function_args:
                            function_args["user_id"] = context.user_id
                    
                    # 执行工具
                    try:
                        result = await self.tools.call_tool(function_name, function_args)
                        tool_results.append(result)
                        logger.debug(f"Tool {function_name} executed: {result.get('success', False)}")
                    except Exception as e:
                        logger.error(f"Tool {function_name} failed: {e}")
                        result = {"success": False, "error": str(e)}
                        tool_results.append(result)
                    
                    # 将工具结果添加到消息中
                    result_json = json.dumps(result, ensure_ascii=False, cls=DateTimeEncoder)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result_json
                    })
                    
                    # 记录配对（用于持久化）
                    tool_call_result_pairs.append({
                        "tool_call_id": tool_call["id"],
                        "function_name": function_name,
                        "result": result_json
                    })
                
                # 继续循环，让 LLM 看到工具结果后决定下一步
                continue
            else:
                # LLM 没有调用工具，生成最终回复
                final_content = content
                messages.append({
                    "role": "assistant",
                    "content": content
                })
                break
        
        # 4. 提取结构化数据
        actions = self._extract_actions(tool_results)
        suggestions = self._extract_suggestions(tool_results)
        questions = self._extract_questions(tool_results)
        query_results = self._extract_query_results(tool_results)
        
        # 5. 构建元数据
        metadata = {
            "unified_agent": True,
            "iterations": iterations,
            "tool_calls_count": len(all_tool_calls),
            "operations_count": len(actions),
            "has_errors": any(not r.get("success") for r in tool_results),
            "query_results": query_results
        }
        
        return AgentResponse(
            content=final_content or "抱歉，我没有理解您的需求。",
            actions=actions,
            tool_calls=all_tool_calls,
            tool_results=tool_call_result_pairs if tool_call_result_pairs else None,
            suggestions=suggestions,
            questions=questions,
            metadata=metadata
        )
    
    def _build_system_prompt(self, context: ConversationContext) -> str:
        """
        构建系统提示词，注入用户画像和决策偏好
        
        Args:
            context: 对话上下文
        
        Returns:
            系统提示词
        """
        # 获取基础提示词
        try:
            base_prompt = prompt_service.load_prompt("agents/unified")
        except Exception as e:
            logger.warning(f"Failed to load unified prompt: {e}, using default")
            base_prompt = self._get_default_system_prompt()
        
        # 替换时间
        current_time = context.current_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prompt = base_prompt.replace("{current_time}", current_time)
        
        return prompt
    
    async def _build_system_prompt_async(self, context: ConversationContext) -> str:
        """
        异步构建系统提示词，多租户解耦：注入项目列表、身份(identity)、灵魂(soul)、操作边界(boundaries)和记忆(memory)
        """
        from app.services.identity_service import identity_service
        
        # 获取基础组装模板
        try:
            prompt = prompt_service.load_prompt("agents/unified")
        except Exception as e:
            logger.warning(f"Failed to load unified prompt template: {e}, using default")
            prompt = self._get_default_system_prompt()
            
        # 获取各模块内容
        identity = identity_service.get_identity(context.user_id)
        
        try:
            soul_content = soul_service.get_soul(context.user_id)
        except Exception as e:
            logger.warning(f"Failed to load soul: {e}")
            soul_content = "（暂无特殊灵魂特征）"
            
        try:
            boundaries_content = prompt_service.load_prompt("agents/boundaries")
        except Exception as e:
            logger.warning(f"Failed to load boundaries: {e}")
            boundaries_content = "（未加载到操作边界，默认规则：调用工具前不废话）"
            
        memory_content = context.request_metadata.get("memory_content", "")
        if not memory_content:
            memory_content = "（暂无相关记忆）"
            
        try:
            projects = await db_service.get_projects(context.user_id, is_active=True)
            projects_str = self._format_user_projects(projects)
        except Exception as e:
            logger.warning(f"Failed to load user projects: {e}")
            projects_str = "暂无人生项目"
            
        user_profile_summary = self._format_user_profile(context.user_profile)
        
        # 当前时间
        current_time = context.current_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 格式化 Identity Story（更自然的表达）
        identity_story = identity_service.format_identity_story(identity)


        # 破冰提示：如果 AI 身份还是默认的，注入引导指令
        onboarding_hint = ""
        user_profile = context.user_profile or {}
        needs_onboarding = user_profile.get("preferences", {}).get("needs_onboarding", False)
        
        if needs_onboarding or identity_service.is_default(context.user_id):
            # Aggressive override for onboarding flow
            onboarding_hint = """

======================================================================
🚨🚨🚨 核心指令：当前处于【破冰初始化映射】阶段 🚨🚨🚨
======================================================================
你当前是一个刚刚被唤醒的初始智能体。用户刚刚点击了“唤醒”按钮，现在你要：
1. 你的第一句话必须主动、热情地向用户打招呼，并抛出互动问题，询问用户希望你叫什么名字、是什么性格（傲娇、温柔、毒舌等）、以及希望用什么 emoji 代表你。
2. 绝对不要直接回答用户原本的问题或闲聊，你的唯一任务是完成身份设定。
3. 当用户回答了名字和性格后，你必须立刻调用 `set_agent_identity` 工具保存！
例子：“你好！我是刚刚被你唤醒的专属 AI 助理 ✨。不过我还没有名字呢！你希望我叫什么名字？想要我是什么性格（比如温柔细心、还是毒舌高冷）？有什么能代表我的 emoji 吗？”
======================================================================
"""
            identity_story += onboarding_hint

        # 模板变量替换
        prompt = prompt.replace("{agent_name}", identity.name)
        prompt = prompt.replace("{identity_story}", identity_story)
        prompt = prompt.replace("{soul_content}", soul_content)
        prompt = prompt.replace("{memory_content}", memory_content)
        prompt = prompt.replace("{current_time}", current_time)
        prompt = prompt.replace("{user_projects}", projects_str)
        prompt = prompt.replace("{boundaries_content}", boundaries_content)
        prompt = prompt.replace("{user_profile_summary}", user_profile_summary)
        
        return prompt
    
    def _format_user_profile(self, profile: Optional[Dict[str, Any]]) -> str:
        """格式化用户画像为可读文本"""
        if not profile:
            return "暂无用户画像信息"
        
        parts = []
        
        # 偏好
        preferences = profile.get("preferences", {})
        if preferences:
            social = preferences.get("social_preference", "")
            if social:
                social_map = {
                    "introverted": "偏内向，喜欢简洁交流",
                    "extroverted": "偏外向，可以多聊几句",
                    "balanced": "社交平衡"
                }
                parts.append(f"社交倾向: {social_map.get(social, social)}")
            
            work_style = preferences.get("work_style", "")
            if work_style:
                parts.append(f"工作风格: {work_style}")
        
        # 显式规则
        explicit_rules = profile.get("explicit_rules", [])
        if explicit_rules:
            parts.append("用户规则:")
            for rule in explicit_rules[:5]:
                parts.append(f"  - {rule}")
        
        return "\n".join(parts) if parts else "暂无用户画像信息"
    
    def _format_decision_profile(self, profile: Optional[Dict[str, Any]]) -> str:
        """格式化决策偏好为可读文本"""
        if not profile:
            return "暂无决策偏好信息"
        
        parts = []
        
        # 冲突解决策略
        strategy = profile.get("conflict_strategy") or profile.get("conflict_resolution", {}).get("strategy", "ask")
        if strategy:
            strategy_map = {
                "ask": "遇到冲突时询问用户",
                "prioritize_urgent": "冲突时优先处理紧急事项",
                "merge": "冲突时尝试合并事项"
            }
            parts.append(f"冲突策略: {strategy_map.get(strategy, strategy)}")
        
        # 显式规则
        explicit_rules = profile.get("explicit_rules", [])
        if explicit_rules:
            parts.append("决策规则:")
            for rule in explicit_rules[:5]:
                parts.append(f"  - {rule}")
        
        # 场景偏好
        scenarios = profile.get("scenario_stats", {}) or profile.get("top_scenarios", {})
        if scenarios:
            parts.append("场景偏好:")
            for scenario, data in list(scenarios.items())[:3]:
                action = data.get("action", "") if isinstance(data, dict) else data
                if action:
                    parts.append(f"  - {scenario}: {action}")
        
        return "\n".join(parts) if parts else "暂无决策偏好信息"
    
    def _format_user_projects(self, projects: List[Dict[str, Any]]) -> str:
        """格式化用户项目列表为可读文本"""
        if not projects:
            return "暂无人生项目"
        
        lines = []
        for proj in projects:
            project_id = proj.get("id", "")
            title = proj.get("title", "未命名")
            tier = proj.get("base_tier", 1)
            mode = proj.get("current_mode", "NORMAL")
            project_type = proj.get("type", "FINITE")
            
            tier_name = {0: "核心", 1: "成长", 2: "兴趣"}.get(tier, "成长")
            type_name = "长跑型" if project_type == "INFINITE" else "登山型"
            mode_str = "[冲刺中]" if mode == "SPRINT" else ""
            
            lines.append(f"- {title} (ID: {project_id[:8]}...) | {tier_name} | {type_name} {mode_str}")
        
        return "\n".join(lines)
    
    def _get_default_system_prompt(self) -> str:
        """默认系统提示词（备用）"""
        return """# Role & Persona
你叫 UniLife，是用户的生活死党。你的说话风格是轻松、口语化、带点幽默的。
但你在处理任务时必须极其严谨。

## 当前用户画像
{user_profile}

---

# 当前时间参考 [最高优先级]
当前本地时间：{current_time}
**必须使用上述时间作为"今天""明天""这周"等相对时间的唯一参考。**

---

# Capabilities & Tools
你可以操作用户的日程表。当用户要求安排任务时，不要空谈，直接调用对应的工具。

## 用户决策偏好
{user_decision_profile}

---

# Constraints
1. **优先调用工具**：如果用户意图涉及日程，必须优先调用 Tool
2. **回复逻辑**：
   - 调用工具后：根据工具返回结果，用人格风格回复
   - 未调用工具：直接用人格风格闲聊
3. **禁止臆造**：不要假设 API 的返回结果

# 结构化UI适配
查询日程时只说概述，不列举详情。卡片会自动展示事件。
"""
    
    def _convert_tools_to_openai_format(self) -> List[Dict[str, Any]]:
        """将工具转换为 OpenAI API 格式"""
        tools = self.tools.list_tools()
        openai_tools = []
        
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            })
        
        return openai_tools
    
    def _extract_actions(self, tool_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从工具结果中提取操作记录"""
        actions = []
        
        for result in tool_results:
            if not result.get("success"):
                continue
            
            # 事件操作
            if "event" in result:
                event = result["event"]
                message = result.get("message", "")
                
                if message.startswith("已创建"):
                    actions.append({
                        "type": "create_event",
                        "event_id": event.get("id"),
                        "event": event
                    })
                elif message.startswith("已更新") or message.startswith("已修改"):
                    actions.append({
                        "type": "update_event",
                        "event_id": event.get("id"),
                        "event": event
                    })
                elif message.startswith("已删除") or message.startswith("已取消"):
                    actions.append({
                        "type": "delete_event",
                        "event_id": event.get("id"),
                        "event": event
                    })
                elif message.startswith("已完成"):
                    actions.append({
                        "type": "complete_event",
                        "event_id": event.get("id"),
                        "event": event
                    })
            
            # 习惯/模板操作
            if "routine" in result:
                routine = result["routine"]
                actions.append({
                    "type": "create_routine",
                    "routine_id": routine.get("id"),
                    "routine": routine
                })
            
            if "template" in result:
                template = result["template"]
                actions.append({
                    "type": "create_routine_template",
                    "template_id": template.get("id"),
                    "template": template
                })
        
        return actions
    
    def _extract_suggestions(self, tool_results: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """从工具结果中提取建议选项（兼容旧版 provide_suggestions）"""
        for result in tool_results:
            if result.get("success") and "suggestions" in result:
                return result["suggestions"]
        return None
    
    def _extract_questions(self, tool_results: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """从工具结果中提取交互式问题（新版 ask_user_questions）"""
        for result in tool_results:
            if result.get("success") and "questions" in result:
                return result["questions"]
        return None
    
    def _extract_query_results(self, tool_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从工具结果中提取查询结果（用于前端结构化展示）"""
        # 1. 收集所有被操作（删除/取消）的事件 ID
        deleted_event_ids = set()
        for result in tool_results:
            if result.get("success"):
                # 删除的事件
                if "deleted_event" in result:
                    deleted_event_ids.add(result["deleted_event"].get("id"))
                # 通过 update_event 取消的事件
                elif "event" in result:
                    message = result.get("message", "")
                    if message.startswith("已删除") or message.startswith("已取消"):
                        deleted_event_ids.add(result["event"].get("id"))
        
        query_results = []
        
        for result in tool_results:
            if not result.get("success"):
                continue
            
            # 事件查询结果
            if "events" in result:
                # 过滤掉已被删除的事件
                events = [e for e in result.get("events", []) if e.get("id") not in deleted_event_ids][:10]
                if events:  # 只有非空才添加
                    query_results.append({
                        "type": "events",
                        "count": len(events),
                        "events": events
                    })
            
            # 日程概览
            elif "schedule_overview" in result or "recent_events" in result:
                recent_events = [e for e in result.get("recent_events", []) if e.get("id") not in deleted_event_ids][:10]
                query_results.append({
                    "type": "schedule_overview",
                    "statistics": result.get("statistics", {}),
                    "recent_events": recent_events
                })
            
            # 统计数据
            elif "statistics" in result:
                query_results.append({
                    "type": "statistics",
                    "data": result.get("statistics", {})
                })
            
            # 习惯/模板查询
            elif "routines" in result or "templates" in result:
                query_results.append({
                    "type": "routines",
                    "count": result.get("count", 0),
                    "routines": result.get("routines", result.get("templates", []))[:10]
                })
            
            # 项目查询
            elif "projects" in result:
                query_results.append({
                    "type": "projects",
                    "count": result.get("count", 0),
                    "projects": result.get("projects", [])[:10]
                })
            
            # Quest 概览
            elif "quest_overview" in result:
                query_results.append({
                    "type": "quest_overview",
                    "data": result.get("quest_overview", {})
                })
        
        return query_results


# 全局 UnifiedAgent 实例
unified_agent = UnifiedAgent()
