"""
LLM Service - Integration with DeepSeek API (OpenAI Compatible)
支持最新的 Tools API (OpenAI 格式)
"""
from typing import List, Dict, Any, Optional
import httpx
import asyncio
import time
import logging
from app.config import settings

# 确保 httpx 异常类型可用
# httpx.ConnectError, RemoteProtocolError, ReadTimeout, WriteTimeout, NetworkError, HTTPStatusError

# 获取日志记录器
_retry_logger = None

def get_retry_logger():
    global _retry_logger
    if _retry_logger is None:
        _retry_logger = logging.getLogger("llm.retry")
    return _retry_logger


class LLMService:
    """Service for interacting with LLM (DeepSeek - OpenAI Compatible)"""

    def __init__(self):
        self.api_key = settings.glm_api_key
        self.base_url = settings.glm_base_url
        self.model = settings.glm_model
        self.max_retries = 3
        self.retry_delay = 1.0

        # 创建支持重试的 HTTP 客户端
        limits = httpx.Limits(
            max_keepalive_connections=5,
            max_connections=10,
            keepalive_expiry=30.0
        )

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=httpx.Timeout(600.0, connect=30.0),  # 10分钟总超时，30秒连接超时
            limits=limits,
            verify=True  # SSL 证书验证
        )

        # 导入日志记录器（延迟导入，避免循环依赖）
        self._llm_logger = None

    @property
    def llm_logger(self):
        """延迟导入日志记录器"""
        if self._llm_logger is None:
            from app.utils.logger import llm_logger
            self._llm_logger = llm_logger
        return self._llm_logger

    async def _make_request_with_retry(
        self,
        endpoint: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        发送带重试机制的请求

        Args:
            endpoint: API 端点
            payload: 请求负载

        Returns:
            响应数据
        """
        last_error = None
        retry_logger = get_retry_logger()

        for attempt in range(self.max_retries):
            try:
                self.llm_logger.log_request(
                    endpoint=endpoint,
                    messages=payload.get("messages", []),
                    temperature=payload.get("temperature", 0.7),
                    tools=payload.get("tools"),
                    max_tokens=payload.get("max_tokens")
                )

                start_time = time.time()
                response = await self.client.post(endpoint, json=payload)
                duration = time.time() - start_time

                response.raise_for_status()

                data = response.json()

                self.llm_logger.log_response(
                    request_id=self.llm_logger.request_count,
                    response={
                        "content": data.get("choices", [{}])[0].get("message", {}).get("content"),
                        "tool_calls": data.get("choices", [{}])[0].get("message", {}).get("tool_calls"),
                        "usage": data.get("usage", {}),
                    },
                    duration=duration,
                    success=True
                )

                return data

            except httpx.ConnectError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    retry_logger.warning(f"连接错误，{delay}秒后重试 ({attempt + 1}/{self.max_retries})...")
                    await asyncio.sleep(delay)
                else:
                    self.llm_logger.log_error(self.llm_logger.request_count, e)
                    raise Exception(f"Connection failed after {self.max_retries} attempts: {e}")

            except httpx.RemoteProtocolError as e:
                # 服务器断开连接（可能是临时网络问题）
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    retry_logger.warning(f"服务器断开连接，{delay}秒后重试 ({attempt + 1}/{self.max_retries})...")
                    await asyncio.sleep(delay)
                else:
                    self.llm_logger.log_error(self.llm_logger.request_count, e)
                    raise Exception(f"Server disconnected after {self.max_retries} attempts: {e}")

            except httpx.ReadTimeout as e:
                # 读取超时
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    retry_logger.warning(f"读取超时，{delay}秒后重试 ({attempt + 1}/{self.max_retries})...")
                    await asyncio.sleep(delay)
                else:
                    self.llm_logger.log_error(self.llm_logger.request_count, e)
                    raise Exception(f"Read timeout after {self.max_retries} attempts: {e}")

            except httpx.WriteTimeout as e:
                # 写入超时
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    retry_logger.warning(f"写入超时，{delay}秒后重试 ({attempt + 1}/{self.max_retries})...")
                    await asyncio.sleep(delay)
                else:
                    self.llm_logger.log_error(self.llm_logger.request_count, e)
                    raise Exception(f"Write timeout after {self.max_retries} attempts: {e}")

            except httpx.HTTPStatusError as e:
                last_error = e

                # 4xx 错误不重试
                if 400 <= e.response.status_code < 500:
                    self.llm_logger.log_error(self.llm_logger.request_count, e)
                    raise

                # 5xx 错误重试
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    retry_logger.warning(f"服务器错误 {e.response.status_code}，{delay}秒后重试 ({attempt + 1}/{self.max_retries})...")
                    await asyncio.sleep(delay)
                else:
                    self.llm_logger.log_error(self.llm_logger.request_count, e)
                    raise Exception(f"HTTP {e.response.status_code} after {self.max_retries} attempts: {e}")

            except httpx.NetworkError as e:
                # 其他网络错误
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    retry_logger.warning(f"网络错误，{delay}秒后重试 ({attempt + 1}/{self.max_retries})...")
                    await asyncio.sleep(delay)
                else:
                    self.llm_logger.log_error(self.llm_logger.request_count, e)
                    raise Exception(f"Network error after {self.max_retries} attempts: {e}")

            except Exception as e:
                last_error = e
                self.llm_logger.log_error(self.llm_logger.request_count, e)
                raise

        # 所有重试都失败
        raise Exception(f"Failed to connect to LLM API after {self.max_retries} attempts. Last error: {last_error}")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send chat completion request to LLM

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate

        Returns:
            Response dictionary with 'content' and other fields
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        data = await self._make_request_with_retry("/chat/completions", payload)
        return {
            "content": data["choices"][0]["message"]["content"],
            "usage": data.get("usage", {}),
            "model": data.get("model"),
        }

    async def tools_calling(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        tool_choice: str = "auto",
        temperature: float = 0.3
    ) -> Dict[str, Any]:
        """
        Send tools calling request to LLM (OpenAI Format)

        Args:
            messages: List of message dictionaries (can include tool_call_id and tool_calls)
            tools: List of available tools with type, function (name, description, parameters)
            tool_choice: "auto", "none", "required", or {"type": "function", "name": "tool_name"}
            temperature: Sampling temperature

        Returns:
            Response with tool_calls or content
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
            "temperature": temperature,
        }

        data = await self._make_request_with_retry("/chat/completions", payload)
        message = data["choices"][0]["message"]

        return {
            "tool_calls": message.get("tool_calls"),
            "content": message.get("content"),
            "usage": data.get("usage", {}),
            "role": message.get("role", "assistant"),
        }

    async def function_calling(
        self,
        messages: List[Dict[str, str]],
        functions: List[Dict[str, Any]],
        function_call: str = "auto"
    ) -> Dict[str, Any]:
        """
        Send function calling request to LLM (Legacy Format)

        Args:
            messages: List of message dictionaries
            functions: List of available functions with name, description, parameters
            function_call: "auto", "none", or {"name": "function_name"}

        Returns:
            Response with function call or content
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "functions": functions,
            "function_call": function_call,
            "temperature": 0.3,  # Lower temperature for function calling
        }

        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()

        data = response.json()
        message = data["choices"][0]["message"]

        return {
            "function_call": message.get("function_call"),
            "content": message.get("content"),
            "usage": data.get("usage", {}),
        }

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


# Global LLM service instance
llm_service = LLMService()
