#!/bin/bash
# UniLife Backend - Serverless 部署打包脚本
#
# 使用方法：
#   chmod +x deploy_serverless.sh
#   ./deploy_serverless.sh

set -e  # 遇到错误立即退出

echo "=========================================="
echo "UniLife Backend - Serverless 打包脚本"
echo "=========================================="
echo ""

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 Python 版本
echo "检查 Python 版本..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "当前 Python 版本: $PYTHON_VERSION"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
    echo "错误: 需要 Python 3.8 或更高版本"
    exit 1
fi

# 清理旧的打包文件
echo ""
echo "清理旧文件..."
rm -rf package
rm -f unilife_backend.zip

# 创建打包目录
echo "创建打包目录..."
mkdir -p package

# 安装依赖
echo ""
echo "安装 Serverless 依赖..."
echo "这可能需要几分钟..."

pip3 install -r requirements_serverless.txt --target ./package --upgrade

if [ $? -ne 0 ]; then
    echo ""
    echo "依赖安装失败，尝试使用国内镜像源..."
    pip3 install -r requirements_serverless.txt --target ./package --upgrade -i https://pypi.tuna.tsinghua.edu.cn/simple
fi

echo "${GREEN}依赖安装完成${NC}"

# 复制项目代码
echo ""
echo "复制项目代码..."

# 复制应用代码
cp -r app ./package/

# 复制 Serverless 入口文件
cp serverless.py ./package/
cp serverless_cron.py ./package/

# 复制提示词模板（如果存在）
if [ -d "prompts" ]; then
    cp -r prompts ./package/
    echo "已复制 prompts 目录"
fi

# 复制配置文件（可选）
if [ -f ".env.example" ]; then
    cp .env.example ./package/
    echo "已复制 .env.example"
fi

# 打包
echo ""
echo "正在打包..."
cd package
zip -r ../unilife_backend.zip . -q
cd ..

# 获取文件大小
FILE_SIZE=$(du -h unilife_backend.zip | cut -f1)

echo ""
echo "${GREEN}打包完成！${NC}"
echo ""
echo "打包文件信息："
echo "  文件名: unilife_backend.zip"
echo "  文件大小: $FILE_SIZE"
echo "  位置: $(pwd)/unilife_backend.zip"
echo ""
echo "=========================================="
echo "下一步："
echo "=========================================="
echo ""
echo "1. 登录腾讯云控制台: https://console.cloud.tencent.com/scf"
echo "2. 创建新函数"
echo "3. 上传 unilife_backend.zip"
echo "4. 配置环境变量（参考 docs/SERVERLESS_DEPLOYMENT_GUIDE.md）"
echo "5. 配置 API 网关触发器"
echo ""
echo "定时任务函数："
echo "  - 上传同一 zip 文件"
echo "  - 入口文件: serverless_cron.daily_diary_generator"
echo "  - 配置定时触发器"
echo ""
echo "详细部署指南: docs/SERVERLESS_DEPLOYMENT_GUIDE.md"
echo ""
