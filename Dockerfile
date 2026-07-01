"""
Dockerfile - 容器化部署
"""
# 基础镜像
FROM python:3.11-slim

# 环境
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NODE_VERSION=20

# 安装 Node.js 20 (binance-cli 需要)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 工作目录
WORKDIR /app

# 1. Python 依赖(先复制以利用缓存)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. binance-cli
RUN npm install -g @binance/binance-cli

# 3. 复制项目
COPY . .

# binance-cli 全局路径
ENV PATH="/usr/local/bin:${PATH}"

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, '/app'); from src.utils.health import HealthMonitor; print(HealthMonitor.get().is_healthy())" \
    || exit 1

# 默认启动:启动后台调度器
CMD ["python", "src/main.py", "--scheduler"]
