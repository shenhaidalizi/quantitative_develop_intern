FROM hub.zoyutech.com/library/python:3.12


WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    ON_SERVER=true \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn,nexus.trader.com

RUN if [ -f /etc/apt/sources.list ]; then \
    cp /etc/apt/sources.list /etc/apt/sources.list.bak.$(date +%F); \
    sed -i 's|http://deb.debian.org/debian|http://mirrors.tuna.tsinghua.edu.cn/debian|g' /etc/apt/sources.list; \
    sed -i 's|http://security.debian.org/debian-security|http://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list; \
fi && \
if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
    cp /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list.d/debian.sources.bak.$(date +%F); \
    sed -i 's|http://deb.debian.org/debian|http://mirrors.tuna.tsinghua.edu.cn/debian|g' /etc/apt/sources.list.d/debian.sources; \
    sed -i 's|http://security.debian.org/debian-security|http://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
fi

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
COPY --chmod=0755 scripts/bootstrap.sh /app/scripts/bootstrap.sh
# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 1) 安装 cron，并加载计划任务
RUN apt-get update && apt-get install -y --no-install-recommends cron tzdata && rm -rf /var/lib/apt/lists/*

COPY core/ ./core/
COPY scripts/ ./scripts/
COPY tests/ ./tests/
COPY benchmarks/ ./benchmarks/
COPY __init__.py .

# 2) 安装定时任务（使用 /etc/cron.d 方式）
COPY scripts/preprocess.cron /etc/cron.d/preprocess
RUN chmod 0644 /etc/cron.d/preprocess && crontab /etc/cron.d/preprocess

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# 默认启动命令
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh
CMD ["/app/run.sh"]

# 修改文件: services/analyzer/Dockerfile（让容器内能直接 import minio_api）
# 在 ENV 段增加或追加一行：
ENV PYTHONPATH=/app/core:$PYTHONPATH
