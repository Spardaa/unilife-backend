"""
UniLife Logging System - 统一日志系统

提供详细的日志追踪，方便调试 LLM 行为
"""
import logging
import sys
import json
import time
from typing import Any, Dict, Optional, List
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

from app.config import settings


# 日志颜色
class LogColors:
    """终端日志颜色"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @staticmethod
    def blue(msg: str) -> str:
        return f"{LogColors.OKBLUE}{msg}{LogColors.ENDC}"

    @staticmethod
    def green(msg: str) -> str:
        return f"{LogColors.OKGREEN}{msg}{LogColors.ENDC}"

    @staticmethod
    def yellow(msg: str) -> str:
        return f"{LogColors.WARNING}{msg}{LogColors.ENDC}"

    @staticmethod
    def red(msg: str) -> str:
        return f"{LogColors.FAIL}{msg}{LogColors.ENDC}"

    @staticmethod
    def bold(msg: str) -> str:
        return f"{LogColors.BOLD}{msg}{LogColors.ENDC}"


class UniLifeFormatter(logging.Formatter):
    """自定义日志格式化器"""

    # 不同级别的颜色映射
    LEVEL_COLORS = {
        logging.DEBUG: LogColors.OKBLUE,
        logging.INFO: LogColors.OKGREEN,
        logging.WARNING: LogColors.WARNING,
        logging.ERROR: LogColors.FAIL,
        logging.CRITICAL: LogColors.FAIL,
    }

    def __init__(self, use_color: bool = True, show_detail: bool = True):
        super().__init__()
        self.use_color = use_color
        self.show_detail = show_detail

    def format(self, record: logging.LogRecord) -> str:
        # 基础信息
        level_name = record.levelname
        logger_name = record.name

        # 颜色处理
        if self.use_color:
            color = self.LEVEL_COLORS.get(record.levelno, "")
            level_name = f"{color}{level_name}{LogColors.ENDC}"
            logger_name = f"{LogColors.OKCYAN}{logger_name}{LogColors.ENDC}"

        # 时间戳
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")

        # 格式化
        if self.show_detail:
            # 详细模式：显示文件名和行号
            base_msg = f"{LogColors.BOLD}[{timestamp}]{LogColors.ENDC} {level_name:8} {logger_name:20} | {record.getMessage()}"
        else:
            # 简洁模式
            base_msg = f"[{timestamp}] {level_name:8} | {record.getMessage()}"

        # 异常信息
        if record.exc_info:
            base_msg += f"\n{self.formatException(record.exc_info)}"

        return base_msg


class LLMRequestLogger:
    """LLM 请求/响应日志记录器"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.request_count = 0

    def log_request(
        self,
        endpoint: str,
        messages: List[Dict[str, Any]],
        temperature: float,
        tools: Optional[List[Dict]] = None,
        max_tokens: Optional[int] = None
    ):
        """记录 LLM 请求"""
        self.request_count += 1
        request_id = self.request_count

        self.logger.info(f"{'='*60}")
        self.logger.info(f"{LogColors.bold('LLM Request')} #{request_id} → {endpoint}")
        self.logger.debug(f"  Model: {settings.deepseek_model}")
        self.logger.debug(f"  Temperature: {temperature}")
        if max_tokens:
            self.logger.debug(f"  Max Tokens: {max_tokens}")
        if tools:
            self.logger.debug(f"  Tools: {len(tools)} tools available")
            for tool in tools:
                self.logger.debug(f"    - {tool.get('function', {}).get('name', 'unknown')}")

        # 记录消息（DEBUG 级别）
        self.logger.debug(f"  Messages ({len(messages)}):")
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            # 截断长内容
            if len(content) > 200:
                content = content[:200] + "..."
            self.logger.debug(f"    [{i}] {role}: {content}")

            # 记录 tool_calls
            if msg.get("tool_calls"):
                self.logger.debug(f"       → tool_calls: {len(msg['tool_calls'])} calls")
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    self.logger.debug(f"          - {fn.get('name')}({fn.get('arguments', '')[:50]}...)")

        return request_id

    def log_response(
        self,
        request_id: int,
        response: Dict[str, Any],
        duration: float,
        success: bool = True
    ):
        """记录 LLM 响应"""
        status = LogColors.green("SUCCESS") if success else LogColors.red("FAILED")
        self.logger.info(f"{status} | Duration: {duration:.2f}s | Request #{request_id}")

        if success:
            # Usage 信息
            usage = response.get("usage", {})
            if usage:
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)
                self.logger.debug(f"  Tokens: {prompt_tokens} + {completion_tokens} = {total_tokens}")

            # Content
            content = response.get("content", "")
            if content:
                content_preview = content[:200] + "..." if len(content) > 200 else content
                self.logger.debug(f"  Content: {content_preview}")

            # Tool calls
            tool_calls = response.get("tool_calls")
            if tool_calls:
                self.logger.debug(f"  Tool Calls: {len(tool_calls)}")
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    args = fn.get("arguments", "")
                    args_preview = args[:100] + "..." if len(args) > 100 else args
                    self.logger.debug(f"    - {fn.get('name')}({args_preview})")

        self.logger.info(f"{'='*60}")

    def log_error(self, request_id: int, error: Exception):
        """记录 LLM 错误"""
        self.logger.error(f"Request #{request_id} failed: {error}")


class AgentLogger:
    """Agent 执行日志记录器"""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = logging.getLogger(f"agent.{agent_name}")

    def log_start(self, context: Any):
        """记录 Agent 开始执行"""
        self.logger.info(f"{LogColors.bold(f'[{self.agent_name}]')} Starting...")
        self.logger.debug(f"  User ID: {context.user_id}")
        self.logger.debug(f"  Conversation ID: {context.conversation_id}")

        # 记录用户消息
        user_msg = context.user_message
        msg_preview = user_msg[:100] + "..." if len(user_msg) > 100 else user_msg
        self.logger.debug(f"  User Message: {msg_preview}")

        # 记录上下文
        if context.user_profile:
            self.logger.debug(f"  Has User Profile: Yes")
        if context.user_decision_profile:
            self.logger.debug(f"  Has Decision Profile: Yes")

    def log_end(self, result: Any, duration: float):
        """记录 Agent 执行结束"""
        self.logger.info(f"{LogColors.bold(f'[{self.agent_name}]')} Completed in {duration:.2f}s")

        # 记录结果摘要
        if hasattr(result, 'content'):
            content = result.content[:100] + "..." if len(result.content) > 100 else result.content
            self.logger.debug(f"  Response: {content}")

        if hasattr(result, 'actions') and result.actions:
            self.logger.debug(f"  Actions: {len(result.actions)} actions performed")

        if hasattr(result, 'tool_calls') and result.tool_calls:
            self.logger.debug(f"  Tool Calls: {len(result.tool_calls)} calls")

    def log_error(self, error: Exception):
        """记录 Agent 错误"""
        self.logger.error(f"{LogColors.bold(f'[{self.agent_name}]')} Error: {error}")


class ToolCallLogger:
    """工具调用日志记录器"""

    def __init__(self):
        self.logger = logging.getLogger("tools")
        self.call_count = 0

    def log_call(self, tool_name: str, arguments: Dict[str, Any]) -> int:
        """记录工具调用"""
        self.call_count += 1
        call_id = self.call_count

        self.logger.debug(f"{LogColors.OKCYAN}[TOOL #{call_id}]{LogColors.ENDC} Calling: {LogColors.bold(tool_name)}")

        # 记录参数（DEBUG）
        args_str = json.dumps(arguments, ensure_ascii=False, indent=2)
        if len(args_str) > 300:
            args_str = args_str[:300] + "\n... (truncated)"
        self.logger.debug(f"  Arguments: {args_str}")

        return call_id

    def log_result(self, call_id: int, tool_name: str, result: Any, duration: float):
        """记录工具调用结果"""
        result_str = str(result)
        result_preview = result_str[:200] + "..." if len(result_str) > 200 else result_str
        self.logger.debug(f"[TOOL #{call_id}] Result ({duration:.2f}s): {result_preview}")

    def log_error(self, call_id: int, tool_name: str, error: Exception):
        """记录工具调用错误"""
        self.logger.error(f"[TOOL #{call_id}] {LogColors.red('ERROR')}: {error}")


class ConversationLogger:
    """对话流程日志记录器"""

    def __init__(self):
        self.logger = logging.getLogger("conversation")

    def log_start(self, user_id: str, conversation_id: str, user_message: str):
        """记录对话开始"""
        msg_preview = user_message[:100] + "..." if len(user_message) > 100 else user_message
        self.logger.info(f"{LogColors.bold('CONVERSATION START')}")
        self.logger.info(f"  User: {user_id}")
        self.logger.info(f"  Conversation: {conversation_id}")
        self.logger.info(f"  Message: {msg_preview}")
        self.logger.info(f"{'─'*60}")

    def log_routing(self, routing_decision: str, confidence: float, reasoning: str = ""):
        """记录路由决策"""
        self.logger.info(f"  Router: {LogColors.bold(routing_decision)} (confidence: {confidence:.2f})")
        if reasoning:
            self.logger.debug(f"    Reasoning: {reasoning}")

    def log_actions(self, actions: List[Any]):
        """记录执行的操作"""
        if actions:
            self.logger.info(f"  Actions: {len(actions)} actions performed")
            for action in actions:
                self.logger.debug(f"    - {action}")

    def log_reply(self, reply: str):
        """记录最终回复"""
        reply_preview = reply[:150] + "..." if len(reply) > 150 else reply
        self.logger.info(f"  Reply: {LogColors.green(reply_preview)}")

    def log_end(self):
        """记录对话结束"""
        self.logger.info(f"{'─'*60}")
        self.logger.info(f"{LogColors.bold('CONVERSATION END')}\n")


# 全局日志记录器实例
llm_logger = LLMRequestLogger(logging.getLogger("llm"))
tool_logger = ToolCallLogger()
conversation_logger = ConversationLogger()


def get_agent_logger(agent_name: str) -> AgentLogger:
    """获取 Agent 日志记录器"""
    return AgentLogger(agent_name)


@contextmanager
def log_duration(logger: logging.Logger, operation: str):
    """上下文管理器：记录操作耗时"""
    start_time = time.time()
    logger.debug(f"{operation}...")
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.debug(f"{operation} completed in {duration:.2f}s")


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    show_detail: bool = True
):
    """
    设置全局日志配置

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        log_file: 日志文件路径（可选）
        show_detail: 是否显示详细信息（文件名、行号）
    """
    # 转换日志级别
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # 清除现有处理器
    root_logger.handlers.clear()

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(UniLifeFormatter(use_color=True, show_detail=show_detail))
    root_logger.addHandler(console_handler)

    # 文件处理器（可选）
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
        file_handler.setFormatter(UniLifeFormatter(use_color=False, show_detail=True))
        root_logger.addHandler(file_handler)

    # 设置第三方库的日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    # 记录初始化
    root_logger.info(f"{LogColors.bold('UniLife Logging System Initialized')}")
    root_logger.info(f"  Level: {level}")
    if log_file:
        root_logger.info(f"  Log File: {log_file}")


# 初始化日志系统
def init_logging():
    """根据配置初始化日志"""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # 开发模式：使用 INFO，生产模式：使用 WARNING
    level = "DEBUG" if settings.debug else settings.log_level.upper()

    # 日志文件路径
    log_file = None
    if not settings.debug:
        # 生产模式写入日志文件
        log_file = "logs/unilife.log"

    setup_logging(level=level, log_file=log_file, show_detail=settings.debug)


# 启动时初始化
# init_logging()  # 延迟初始化，在 main.py 中调用
