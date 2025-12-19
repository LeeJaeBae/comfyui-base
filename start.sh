#!/bin/bash
echo "### STARTING SERVERLESS WORKER ###"

# 1. 에러가 나도 죽지 않도록 설정 (디버깅용)
set +e 

# 2. 환경 변수 및 경로 설정
COMFYUI_DIR="/workspace/runpod-slim/ComfyUI"
VENV_DIR="$COMFYUI_DIR/.venv-cu128"

# 3. 가상환경 활성화 (매우 중요)
# 도커 빌드 단계에서 생성된 venv가 있다면 사용, 없으면 시스템 파이썬 사용
if [ -d "$VENV_DIR" ]; then
    echo "Activating VENV: $VENV_DIR"
    source "$VENV_DIR/bin/activate"
else
    echo "VENV not found, using system python..."
fi

# 4. ComfyUI 실행 (백그라운드 &)
echo "Starting ComfyUI..."
cd "$COMFYUI_DIR" || echo "ComfyUI dir not found, trying /ComfyUI"

# (혹시 경로가 다를 경우를 대비해 루트 경로도 체크)
if [ ! -d "$COMFYUI_DIR" ]; then
    cd /
    if [ -d "ComfyUI" ]; then
        cd ComfyUI
    else
        # 최악의 경우: ComfyUI가 없음 -> 그래도 핸들러는 켜야 에러 로그라도 봄
        echo "WARNING: ComfyUI not found!"
    fi
fi

# ComfyUI 서버 시작
python3 main.py --listen 0.0.0.0 --port 8188 --disable-auto-launch &

# 5. ComfyUI가 켜질 때까지 잠시 대기
echo "Waiting 10s for ComfyUI to boot..."
sleep 10

# 6. [핵심] RunPod 핸들러 실행
# 기존 스크립트에는 이 부분이 없어서 망했던 겁니다.
echo "Starting RunPod Handler..."

if [ -f "/rp_handler.py" ]; then
    python3 -u /rp_handler.py
else
    echo "CRITICAL ERROR: /rp_handler.py not found!"
    # 파일이 없으면 좀비 모드로 전환해서 터미널 접속이라도 가능하게 함
    sleep infinity
fi