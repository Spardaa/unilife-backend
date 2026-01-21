"""
测试 DeepSeek API 连接
用于诊断网络连接问题
"""
import asyncio
import httpx
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings


async def test_connection():
    """测试 DeepSeek API 连接"""

    print("=" * 60)
    print("DeepSeek API 连接测试")
    print("=" * 60)
    print()

    # 显示配置
    print(f"API Base URL: {settings.deepseek_base_url}")
    print(f"API Model: {settings.deepseek_model}")
    print(f"API Key: {settings.deepseek_api_key[:10]}...{settings.deepseek_api_key[-4:]}")
    print()

    # 测试 1: 简单的 GET 请求（如果 API 支持）
    print("测试 1: 检查网络连接...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://api.deepseek.com")
            print(f"✓ 服务器可访问，状态码: {response.status_code}")
    except Exception as e:
        print(f"✗ 无法访问 DeepSeek API: {e}")
        print()
        print("可能的原因：")
        print("1. 网络连接问题")
        print("2. 防火墙阻止了连接")
        print("3. 需要配置代理")
        print()
        return False

    print()

    # 测试 2: API 调用
    print("测试 2: 发送测试请求到 DeepSeek API...")
    try:
        async with httpx.AsyncClient(
            base_url=settings.deepseek_base_url,
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            timeout=httpx.Timeout(30.0, connect=10.0),
            verify=True
        ) as client:
            payload = {
                "model": settings.deepseek_model,
                "messages": [
                    {"role": "user", "content": "你好，请用一句话介绍你自己。"}
                ],
                "temperature": 0.7,
                "max_tokens": 100
            }

            print("发送请求...")
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()

            data = response.json()
            reply = data["choices"][0]["message"]["content"]

            print(f"✓ API 调用成功！")
            print(f"回复: {reply}")
            print()
            print("=" * 60)
            print("所有测试通过！DeepSeek API 连接正常。")
            print("=" * 60)
            return True

    except httpx.ConnectError as e:
        print(f"✗ 连接错误: {e}")
        print()
        print("可能的原因：")
        print("1. SSL/TLS 证书验证失败")
        print("2. 代理设置问题")
        print("3. 防火墙阻止 HTTPS 连接")
        print()
        print("建议解决方案：")
        print("1. 检查是否需要配置代理（设置 HTTP_PROXY/HTTPS_PROXY 环境变量）")
        print("2. 尝试使用 VPN")
        print("3. 检查防火墙设置")
        print()

    except httpx.HTTPStatusError as e:
        print(f"✗ HTTP 错误: {e.response.status_code}")
        print(f"响应内容: {e.response.text}")
        print()
        if e.response.status_code == 401:
            print("API Key 无效，请检查 .env 文件中的 DEEPSEEK_API_KEY")
        elif e.response.status_code == 429:
            print("请求过于频繁，请稍后再试")
        elif e.response.status_code >= 500:
            print("DeepSeek API 服务器错误，请稍后再试")
        print()

    except Exception as e:
        print(f"✗ 未知错误: {type(e).__name__}: {e}")
        print()

    print("=" * 60)
    print("测试失败，请检查网络连接和 API 配置。")
    print("=" * 60)
    return False


if __name__ == "__main__":
    asyncio.run(test_connection())
