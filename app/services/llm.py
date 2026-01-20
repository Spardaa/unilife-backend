"""
LLM Service - Integration with DeepSeek API
"""
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings


class LLMService:
    """Service for interacting with LLM (DeepSeek)"""

    def __init__(self):
        self.api_key = settings.deepseek_api_key
        self.base_url = settings.deepseek_base_url
        self.model = settings.deepseek_model
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60.0
        )

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

        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()

        data = response.json()
        return {
            "content": data["choices"][0]["message"]["content"],
            "usage": data.get("usage", {}),
            "model": data.get("model"),
        }

    async def function_calling(
        self,
        messages: List[Dict[str, str]],
        functions: List[Dict[str, Any]],
        function_call: str = "auto"
    ) -> Dict[str, Any]:
        """
        Send function calling request to LLM

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
