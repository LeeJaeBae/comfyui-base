#!/usr/bin/env bash
# set -e 제거 (에러가 나도 로그는 찍고 죽게 하기 위함)

echo "=== CONTAINER STARTED ==="
echo "Date: $(date)"

# 1. ComfyUI 경로 확인 (가장 많이 틀리는 곳)
COMFYUI_DIR="/workspace/runpod-slim/ComfyUI"

if [ ! -d "$COMFYUI_DIR" ]; then
    echo "🚨 ERROR: ComfyUI directory NOT found at: $COMFYUI_DIR"
    echo "⚠️  Current directory structure:"
    ls -R /workspace || echo "Volume not mounted?"
    
    # 디버깅을 위해 10분간 대기 (바로 죽으면 로그 못 봄)
    echo "Sleeping 600 seconds for debugging..."
    sleep 600
    exit 1
fi

echo "✅ ComfyUI found at $COMFYUI_DIR"
cd "$COMFYUI_DIR"

# 2. 가상환경 활성화 시도
if [ -f ".venv-cu128/bin/activate" ]; then
    source .venv-cu128/bin/activate
else
    echo "⚠️  VENV not found, using system python"
fi

# 3. ComfyUI 실행
echo "🚀 Starting ComfyUI..."
python main.py --listen 0.0.0.0 --port 8188 --disable-auto-launch &

# 4. ComfyUI 로딩 대기
echo "Waiting 5 seconds..."
sleep 5

# 5. 핸들러 실행 (rp_handler.py가 맞는지 꼭 확인!)
echo "🚀 Starting RunPod Handler..."
if [ -f "/rp_handler.py" ]; then
    python -u /rp_handler.py
else
    echo "🚨 ERROR: /rp_handler.py file missing!"
    ls -la /
    sleep 600
fi