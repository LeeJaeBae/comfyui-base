FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-pip \
    git \
    curl \
    ca-certificates \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
 && ln -sf /usr/bin/python3 /usr/bin/python \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir runpod requests websocket-client

WORKDIR /
COPY start.sh /start.sh
COPY handler.py /handler.py
RUN chmod +x /start.sh

EXPOSE 8188
ENTRYPOINT ["/start.sh"]
