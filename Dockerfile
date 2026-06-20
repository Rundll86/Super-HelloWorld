# ============================================================
# Super-HelloWorld — 多阶段 Docker 构建
# ============================================================
# 阶段 1: Builder — 编译依赖 & 安全检查
# 阶段 2: Production — 最小化运行时镜像
# ============================================================

# ---- Stage 1: Builder ----
FROM python:3.12-slim AS builder

LABEL maintainer="Enterprise Architecture Team"
LABEL org.opencontainers.image.title="Super-HelloWorld"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.description="Enterprise-grade Hello World printing infrastructure"

# 安全: 非 root 构建
RUN groupadd --system --gid 1001 helloworld && \
    useradd --system --uid 1001 --gid 1001 helloworld

WORKDIR /build

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Stage 2: Production ----
FROM python:3.12-slim AS production

# 安全加固
RUN groupadd --system --gid 1001 helloworld && \
    useradd --system --uid 1001 --gid 1001 helloworld && \
    apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        tini \
    && rm -rf /var/lib/apt/lists/*

# 复制 Python 包
COPY --from=builder /root/.local /home/helloworld/.local
ENV PATH=/home/helloworld/.local/bin:$PATH
ENV PYTHONPATH=/app

# 复制应用代码
WORKDIR /app
COPY --chown=helloworld:helloworld src/ ./src/
COPY --chown=helloworld:helloworld requirements.txt .

# 安全: 切换到非 root 用户
USER helloworld

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "from src.main import HelloWorldEngine; e = HelloWorldEngine(); print('OK')" || exit 1

# Expose metrics port (Prometheus)
EXPOSE 9090

# 使用 tini 作为 init 进程
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "src.main"]
