"""
Serverless 入口文件 - 腾讯云 SCF / 阿里云 FC 适配器

使用 Mangum 将 FastAPI 应用适配到云函数的 API 网关
"""
from app.main import app
from mangum import Mangum

# 创建 Serverless 适配器
# lifespan="off" 禁用 FastAPI 的 lifespan 事件，避免与云函数启动冲突
lambda_handler = Mangum(
    app,
    lifespan="off",
    api_gateway_base_path="/api/v1"
)


# 为了兼容不同云平台，提供多种入口
def handler(event, context):
    """
    腾讯云 SCF / 阿里云 FC 标准入山

    Args:
        event: API 网关事件
        context: 函数上下文

    Returns:
        符合 API 网关规范的响应
    """
    return lambda_handler(event, context)


# AWS Lambda 兼容
def lambda_handler_name(event, context):
    """AWS Lambda 标准入山"""
    return lambda_handler(event, context)


if __name__ == "__main__":
    # 本地测试
    print("Serverless handler loaded successfully")
    print("App:", app.title)
