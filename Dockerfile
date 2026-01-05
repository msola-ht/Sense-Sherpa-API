# ================= 阶段 1: 准备环境 =================
FROM python:3.11-slim AS builder

# 声明构建参数，支持多架构
ARG TARGETARCH

WORKDIR /build

# 1. 换源并安装 wget 和 xz-utils
RUN apt-get update && \
    apt-get install -y wget xz-utils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. 根据架构下载 FFmpeg 静态包
# 支持的架构: amd64, arm64
RUN case ${TARGETARCH} in \
    amd64) \
    wget -O ffmpeg.tar.xz https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz ;; \
    arm64) \
    wget -O ffmpeg.tar.xz https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz ;; \
    *) \
    echo "Unsupported architecture: ${TARGETARCH}" && exit 1 ;; \
    esac && \
    tar -xf ffmpeg.tar.xz && \
    mv ffmpeg-* ffmpeg

# 3. 准备 Python 虚拟环境
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/http:/https:/g' /etc/apt/sources.list.d/debian.sources

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 3. 安装依赖 (sherpa-onnx, fastapi 等)
RUN pip install --no-cache-dir --default-timeout=100 \
    "fastapi>=0.104.0" \
    "uvicorn[standard]>=0.24.0" \
    "sherpa-onnx>=1.10.0" \
    "numpy>=1.24.0" \
    "python-multipart>=0.0.6"

# ================= 阶段 2: 最终运行镜像 =================
FROM python:3.11-slim

ARG TARGETARCH

WORKDIR /app

# 1. 从 builder 阶段拷贝 FFmpeg 二进制文件
COPY --from=builder /build/ffmpeg/ffmpeg /usr/local/bin/
COPY --from=builder /build/ffmpeg/ffprobe /usr/local/bin/

# 2. 确保 ffmpeg 有执行权限
RUN chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe

# 3. 从 builder 拷贝 Python 环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# 4. 复制业务代码
COPY main_api.py .

EXPOSE 8000
ENTRYPOINT ["python", "main_api.py"]