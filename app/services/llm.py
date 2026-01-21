"""
LLM Service - Integration with DeepSeek API (OpenAI Compatible)
支持最新的 Tools API (OpenAI 格式)
"""
from typing import List, Dict, Any, Optional
import httpx
import asyncio
from app.config import settings


class LLMService:
    """Service for interacting with LLM (DeepSeek - OpenAI Compatible)"""

    def __init__(self):
        self.api_key = settings.deepseek_api_key
        self.base_url = settings.deepseek_base_url
        self.model = settings.deepseek_model
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

        for attempt in range(self.max_retries):
            try:
                print(f"[LLM] Attempt {attempt + 1}/{self.max_retries}: {endpoint}")

                response = await self.client.post(endpoint, json=payload)
                response.raise_for_status()

                data = response.json()
                print(f"[LLM] Success: {endpoint}")
                return data

            except httpx.ConnectError as e:
                last_error = e
                print(f"[LLM] Connection error (attempt {attempt + 1}): {e}")

                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)  # 指数退避
                    print(f"[LLM] Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    print(f"[LLM] All retry attempts failed for {endpoint}")

            except httpx.HTTPStatusError as e:
                last_error = e
                print(f"[LLM] HTTP error {e.response.status_code}: {e.response.text}")

                # 4xx 错误不重试
                if 400 <= e.response.status_code < 500:
                    break

                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    print(f"[LLM] Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)

            except Exception as e:
                last_error = e
                print(f"[LLM] Unexpected error (attempt {attempt + 1}): {e}")
                break

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
