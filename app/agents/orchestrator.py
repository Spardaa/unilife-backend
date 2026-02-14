"""
Agent Orchestrator - 多智能体编排器
支持两种模式：
- 3+1 模式: Router → Executor → Persona + Observer (经典架构)
- 1+1 模式: UnifiedAgent + Observer (融合架构，更快响应)
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
import json
import time
import os

from app.agents.base import (
    ConversationContext, AgentResponse,
    Intent, RoutingDecision
)
from app.agents.router import router_agent
from app.agents.executor import executor_agent
from app.agents.persona import persona_agent
from app.agents.observer import observer_agent
from app.agents.observer_tracker import observer_trigger_tracker
from app.services.profile_service import profile_service
from app.services.conversation_service import conversation_service

# 环境变量控制是否使用 Unified 模式
# 设置 UNIFIED_AGENT_MODE=true 启用 1+1 架构
UNIFIED_MODE = os.environ.get("UNIFIED_AGENT_MODE", "true").lower() == "true"


class AgentOrchestrator:
    """
    智能体编排器 - 协调多 Agent 协作

    支持两种架构模式：
    
    3+1 模式 (经典架构):
    1. Router → 识别意图，决定路由
    2. Executor → 执行工具调用（如果需要）
    3. Persona → 生成拟人化回复
    4. Observer → 异步分析，更新画像
    
    1+1 模式 (融合架构, unified_mode=True):
    1. UnifiedAgent → 意图识别 + 工具调用 + 拟人化回复
    2. Observer → 异步分析，更新画像
    
    通过设置环境变量 UNIFIED_AGENT_MODE=true 或构造参数 unified_mode=True 切换模式
    """

    def __init__(self, unified_mode: Optional[bool] = None):
        # 决定使用哪种模式：参数优先，否则使用环境变量
        self.unified_mode = unified_mode if unified_mode is not None else UNIFIED_MODE
        
        # 3+1 模式的 Agents
        self.router = router_agent
        self.executor = executor_agent
        self.persona = persona_agent
        
        # 共用的 Agents
        self.observer = observer_agent
        self.observer_tracker = observer_trigger_tracker
        self._background_task: Optional[asyncio.Task] = None
        
        # 1+1 模式的 UnifiedAgent（延迟导入，避免循环依赖）
        self._unified_agent = None
        if self.unified_mode:
            self._init_unified_agent()
    
    def _init_unified_agent(self):
        """初始化 UnifiedAgent 和 ContextFilterAgent（延迟导入）"""
        try:
            from app.agents.unified_agent import unified_agent
            from app.agents.context_filter_agent import context_filter_agent
            self._unified_agent = unified_agent
            self._context_filter = context_filter_agent
            import logging
            logging.getLogger("orchestrator").info("Unified mode enabled (1+1 architecture with context filter)")
        except ImportError as e:
            import logging
            logging.getLogger("orchestrator").error(f"Failed to import unified_agent or context_filter: {e}")
            self.unified_mode = False
            self._context_filter = None

    def _get_conversation_logger(self):
        """延迟导入对话日志记录器"""
        from app.utils.logger import conversation_logger
        return conversation_logger

    def _get_logger(self):
        """获取标准日志记录器"""
        import logging
        return logging.getLogger("orchestrator")

    async def process_message(
        self,
        user_message: str,
        user_id: str,
        conversation_id: str,
        current_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        处理用户消息的主入口

        Args:
            user_message: 用户消息
            user_id: 用户ID
            conversation_id: 对话ID
            current_time: 当前时间（可选，用于测试）

        Returns:
            {
                "reply": "自然语言回复",
                "actions": [...],
                "tool_calls": [...],
                "conversation_history": [...],
                "suggestions": [...],
                "routing_metadata": {...}
            }
        """
        start_time = time.time()
        conv_logger = self._get_conversation_logger()
        logger = self._get_logger()

        # 记录对话开始
        conv_logger.log_start(user_id, conversation_id, user_message)

        try:
            # 1. 构建上下文
            context = await self._build_context(
                user_id=user_id,
                conversation_id=conversation_id,
                user_message=user_message,
                current_time=current_time
            )
            
            # 分支：Unified 模式使用单一 Agent 处理
            if self.unified_mode and self._unified_agent:
                return await self._process_unified(
                    context=context,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    start_time=start_time,
                    conv_logger=conv_logger,
                    logger=logger
                )

            # 2. Router 路由
            router_start = time.time()
            router_response = await self.router.process(context)
            router_duration = time.time() - router_start
            logger.debug(f"Router completed in {router_duration:.2f}s")

            # 保存路由结果
            context.router_result = router_response.metadata
            context.current_intent = Intent.from_string(
                router_response.metadata.get("intent", Intent.UNKNOWN)
            )

            # 使用 Router 筛选后的上下文（替换原始上下文）
            if router_response.filtered_context is not None:
                context.conversation_history = router_response.filtered_context
                logger.debug(f"Context filtered: {router_response.metadata.get('original_context_count', 0)} → {len(router_response.filtered_context)} messages")

            # 记录路由决策
            routing_decision = router_response.should_route_to or RoutingDecision.PERSONA
            conv_logger.log_routing(
                routing_decision=routing_decision.value,
                confidence=router_response.metadata.get("confidence", 0.0),
                reasoning=router_response.metadata.get("reasoning", "")
            )

            # 3. 根据 Router 决策执行
            executor_response = None
            executor_duration = 0

            if routing_decision in [RoutingDecision.EXECUTOR, RoutingDecision.BOTH]:
                # 需要 Executor 执行
                executor_start = time.time()
                executor_response = await self.executor.process(context)
                executor_duration = time.time() - executor_start
                logger.debug(f"Executor completed in {executor_duration:.2f}s")

                context.executor_result = executor_response.metadata
                context.suggestions = executor_response.suggestions  # 设置 suggestions

                # 提取操作和建议
                actions = executor_response.actions
                suggestions = executor_response.suggestions  # 修复：从 AgentResponse 属性获取
                tool_calls = executor_response.tool_calls

                # 记录执行的操作
                conv_logger.log_actions(actions)

            elif routing_decision == RoutingDecision.PERSONA:
                # 只需要 Persona
                actions = []
                suggestions = None
                tool_calls = []

            # 4. Persona 生成最终回复
            persona_start = time.time()
            persona_response = await self.persona.process(context)
            persona_duration = time.time() - persona_start
            logger.debug(f"Persona completed in {persona_duration:.2f}s")

            final_reply = persona_response.content

            # 5. 构建返回结果
            # 提取 query_results（从 Executor 的 metadata 中）
            query_results = None
            if executor_response and executor_response.metadata:
                query_results = executor_response.metadata.get("query_results", [])

            result = {
                "reply": final_reply,
                "actions": actions if routing_decision != RoutingDecision.PERSONA else [],
                "tool_calls": tool_calls if routing_decision != RoutingDecision.PERSONA else [],
                "suggestions": suggestions,
                "query_results": query_results,  # 新增：结构化查询结果
                "routing_metadata": {
                    "intent": router_response.metadata.get("intent"),
                    "routing": routing_decision.value,
                    "confidence": router_response.metadata.get("confidence"),
                    "reasoning": router_response.metadata.get("reasoning")
                },
                "timing": {
                    "router": router_duration,
                    "executor": executor_duration,
                    "persona": persona_duration,
                    "total": time.time() - start_time
                }
            }

            # 记录最终回复
            conv_logger.log_reply(final_reply)

            # 6. 添加到 Observer 追踪器（延迟触发或阈值触发）
            logger.debug("Adding conversation to Observer tracker...")

            # 获取原始完整上下文（用于 Observer 分析）
            # 从 conversation_service 获取未筛选的完整历史
            from app.services.conversation_service import conversation_service
            full_context = await conversation_service.get_recent_context(
                user_id=user_id,
                conversation_id=conversation_id,
                hours=72,
                max_messages=100  # Observer 获取更多历史
            )

            # 添加到追踪器
            trigger_info = self.observer_tracker.add_message(
                conversation_id=conversation_id,
                user_id=user_id,
                conversation_context=full_context
            )

            # 如果达到阈值，立即触发分析
            if trigger_info:
                logger.info(f"Observer threshold triggered: {trigger_info['trigger_type']}, messages: {trigger_info['message_count']}")
                asyncio.create_task(
                    self.observer.analyze_conversation_batch(
                        conversation_id=conversation_id,
                        user_id=user_id,
                        full_context=trigger_info['full_context']
                    )
                )

            # 启动后台任务检查延迟触发（如果还没启动）
            if self._background_task is None or self._background_task.done():
                self._background_task = asyncio.create_task(
                    self._observer_background_loop()
                )

            # 记录对话结束
            conv_logger.log_end()

            total_duration = time.time() - start_time
            logger.info(f"Total processing time: {total_duration:.2f}s")

            return result

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            raise
    
    async def _process_unified(
        self,
        context: ConversationContext,
        user_id: str,
        conversation_id: str,
        start_time: float,
        conv_logger,
        logger
    ) -> Dict[str, Any]:
        """
        使用 UnifiedAgent 处理请求 (1+1 模式)
        
        流程：
        1. ContextFilterAgent 筛选上下文（可选）
        2. UnifiedAgent 处理请求
        3. Observer 异步分析
        
        Args:
            context: 对话上下文
            user_id: 用户ID
            conversation_id: 对话ID
            start_time: 请求开始时间
            conv_logger: 对话日志记录器
            logger: 标准日志记录器
        
        Returns:
            处理结果字典
        """
        filter_duration = 0
        original_history_count = len(context.conversation_history)
        
        # 1. 先使用 ContextFilterAgent 筛选上下文
        if self._context_filter and len(context.conversation_history) > 3:
            filter_start = time.time()
            filter_response = await self._context_filter.process(context)
            filter_duration = time.time() - filter_start
            
            # 使用筛选后的上下文
            if filter_response.filtered_context is not None:
                context.conversation_history = filter_response.filtered_context
                logger.debug(f"Context filtered: {original_history_count} → {len(context.conversation_history)} messages in {filter_duration:.2f}s")
        
        # 2. 调用 UnifiedAgent 处理
        unified_start = time.time()
        unified_response = await self._unified_agent.process(context)
        unified_duration = time.time() - unified_start
        logger.debug(f"UnifiedAgent completed in {unified_duration:.2f}s")
        
        # 记录路由信息
        conv_logger.log_routing(
            routing_decision="unified",
            confidence=1.0,
            reasoning=f"Unified mode with context filter ({original_history_count}→{len(context.conversation_history)})"
        )
        
        # 记录执行的操作
        if unified_response.actions:
            conv_logger.log_actions(unified_response.actions)
        
        # 3. 构建返回结果
        result = {
            "reply": unified_response.content,
            "actions": unified_response.actions or [],
            "tool_calls": unified_response.tool_calls or [],
            "suggestions": unified_response.suggestions,
            "query_results": unified_response.metadata.get("query_results", []) if unified_response.metadata else [],
            "routing_metadata": {
                "mode": "unified",
                "context_filter": {
                    "original": original_history_count,
                    "filtered": len(context.conversation_history)
                },
                "iterations": unified_response.metadata.get("iterations", 1) if unified_response.metadata else 1,
                "tool_calls_count": unified_response.metadata.get("tool_calls_count", 0) if unified_response.metadata else 0
            },
            "timing": {
                "context_filter": filter_duration,
                "unified": unified_duration,
                "total": time.time() - start_time
            }
        }
        
        # 记录最终回复
        conv_logger.log_reply(unified_response.content)
        
        # 3. 添加到 Observer 追踪器（与 3+1 模式相同）
        logger.debug("Adding conversation to Observer tracker...")
        
        full_context = await conversation_service.get_recent_context(
            user_id=user_id,
            conversation_id=conversation_id,
            hours=72,
            max_messages=100
        )
        
        trigger_info = self.observer_tracker.add_message(
            conversation_id=conversation_id,
            user_id=user_id,
            conversation_context=full_context
        )
        
        if trigger_info:
            logger.info(f"Observer threshold triggered: {trigger_info['trigger_type']}, messages: {trigger_info['message_count']}")
            asyncio.create_task(
                self.observer.analyze_conversation_batch(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    full_context=trigger_info['full_context']
                )
            )
        
        # 启动后台任务检查延迟触发
        if self._background_task is None or self._background_task.done():
            self._background_task = asyncio.create_task(
                self._observer_background_loop()
            )
        
        # 记录对话结束
        conv_logger.log_end()
        
        total_duration = time.time() - start_time
        logger.info(f"[Unified Mode] Total processing time: {total_duration:.2f}s (UnifiedAgent: {unified_duration:.2f}s)")
        
        return result

    async def _build_context(
        self,
        user_id: str,
        conversation_id: str,
        user_message: str,
        current_time: Optional[str]
    ) -> ConversationContext:
        """
        构建对话上下文

        Args:
            user_id: 用户ID
            conversation_id: 对话ID
            user_message: 用户消息
            current_time: 当前时间

        Returns:
            ConversationContext
        """
        # 获取近72小时的对话历史（带时间戳）
        context_messages = await conversation_service.get_recent_context(
            user_id=user_id,
            conversation_id=conversation_id,
            hours=72,
            max_messages=30
        )

        # 获取用户画像
        user_profile = None
        user_decision_profile = None

        try:
            profile = profile_service.get_or_create_profile(user_id)
            if profile:
                user_profile = profile.model_dump() if hasattr(profile, 'model_dump') else profile
        except:
            pass

        # 获取用户决策偏好
        try:
            from app.services.decision_profile_service import decision_profile_service

            decision_profile = decision_profile_service.get_or_create_profile(user_id)
            user_decision_profile = decision_profile.model_dump() if hasattr(decision_profile, 'model_dump') else decision_profile
        except:
            user_decision_profile = None

        # 构建上下文
        # 获取当前时间（用户本地时间，默认使用Asia/Shanghai时区）
        import pytz
        user_tz = pytz.timezone("Asia/Shanghai")  # TODO: 从用户profile获取时区
        now = datetime.now(user_tz)
        current_hour = now.hour

        # 判断当前时段
        time_period = ""
        if 0 <= current_hour < 5:
            time_period = "凌晨"
        elif 5 <= current_hour < 9:
            time_period = "早上"
        elif 9 <= current_hour < 12:
            time_period = "上午"
        elif 12 <= current_hour < 14:
            time_period = "中午"
        elif 14 <= current_hour < 18:
            time_period = "下午"
        elif 18 <= current_hour < 23:
            time_period = "晚上"
        else:  # 23-24
            time_period = "深夜"

        # 星期映射
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday_name = weekday_names[now.weekday()]

        # 构建带时段和星期信息的时间字符串（使用本地时间）
        current_time_str = current_time or now.strftime("%Y-%m-%d %H:%M:%S")
        current_time_with_period = f"{current_time_str} ({weekday_name}, {time_period}, {current_hour}点)"

        context = ConversationContext(
            user_id=user_id,
            conversation_id=conversation_id,
            user_message=user_message,
            conversation_history=context_messages,
            user_profile=user_profile,
            user_decision_profile=user_decision_profile,
            current_time=current_time_with_period  # 传入带时段信息的时间
        )

        return context

    async def analyze_user_period(
        self,
        user_id: str,
        period_start: str,
        period_end: str,
        job_type: str = "daily"
    ) -> Dict[str, Any]:
        """
        分析用户行为（定时任务）

        Args:
            user_id: 用户ID
            period_start: 开始日期 (YYYY-MM-DD)
            period_end: 结束日期 (YYYY-MM-DD)
            job_type: 任务类型 (daily/weekly)

        Returns:
            分析结果
        """
        from datetime import datetime

        start_date = datetime.strptime(period_start, "%Y-%m-%d").date()
        end_date = datetime.strptime(period_end, "%Y-%m-%d").date()

        return await self.observer.analyze_period(
            user_id=user_id,
            period_start=start_date,
            period_end=end_date,
            job_type=job_type
        )

    async def _observer_background_loop(self):
        """
        Observer 后台循环，定期检查延迟触发

        每 5 分钟检查一次是否有超过 30 分钟无新消息的对话
        """
        import logging
        bg_logger = logging.getLogger("observer.background")

        while True:
            try:
                # 等待 5 分钟
                await asyncio.sleep(300)

                # 检查延迟触发
                triggered = self.observer_tracker.check_delayed_triggers()

                if triggered:
                    bg_logger.info(f"Observer delayed trigger: {len(triggered)} conversations")

                    for trigger_info in triggered:
                        try:
                            await self.observer.analyze_conversation_batch(
                                conversation_id=trigger_info['conversation_id'],
                                user_id=trigger_info['user_id'],
                                full_context=trigger_info['full_context']
                            )
                            bg_logger.info(f"Observer analyzed: {trigger_info['conversation_id']}, trigger: {trigger_info['trigger_type']}")
                        except Exception as e:
                            bg_logger.error(f"Observer analysis failed for {trigger_info['conversation_id']}: {e}")

            except asyncio.CancelledError:
                bg_logger.info("Observer background loop cancelled")
                break
            except Exception as e:
                bg_logger.error(f"Observer background loop error: {e}")

    def get_observer_tracker_status(self) -> Dict[str, Any]:
        """
        获取 Observer 追踪器状态（用于监控）

        Returns:
            追踪器状态信息
        """
        pending = self.observer_tracker.get_pending_info()

        return {
            "pending_count": len(pending),
            "pending_conversations": pending[:10]  # 最多返回 10 个
        }

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            各 Agent 的状态
        """
        result = {
            "orchestrator": "ok",
            "mode": "unified (1+1)" if self.unified_mode else "classic (3+1)",
            "agents": {
                "observer": self.observer.name
            }
        }
        
        if self.unified_mode:
            result["agents"]["unified"] = self._unified_agent.name if self._unified_agent else "not loaded"
            result["agents"]["context_filter"] = self._context_filter.name if self._context_filter else "not loaded"
        else:
            result["agents"]["router"] = self.router.name
            result["agents"]["executor"] = self.executor.name
            result["agents"]["persona"] = self.persona.name
        
        return result


# 全局 Orchestrator 实例
agent_orchestrator = AgentOrchestrator()
