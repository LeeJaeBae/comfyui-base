FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# ---- system deps (최소) ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    python3-pip \
    git \
    curl \
    ca-certificates \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
 && ln -sf /usr/bin/python3.12 /usr/bin/python \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# ---- python runtime deps (handler용) ----
RUN pip install --no-cache-dir runpod requests websocket-client

# ---- working dir ----
WORKDIR /

# ---- start script ----
COPY start.sh /start.sh
RUN chmod +x /start.sh

# ---- expose comfy + handler ----
EXPOSE 8188

# ---- entrypoint ----
ENTRYPOINT ["/start.sh"]
