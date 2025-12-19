#!/usr/bin/env bash
set -euxo pipefail

# 1. 경로 설정
COMFYUI_DIR="/runpod-volume/runpod-slim/ComfyUI"
VENV_DIR="$COMFYUI_DIR/.venv"

echo "START.SH BOOTED: $(date)"

# 2. 볼륨 마운트 확인 (로그가 안 뜨는 원인 차단)
if [ ! -d "$COMFYUI_DIR" ]; then
    echo "ERROR: ComfyUI directory not found at $COMFYUI_DIR"
    echo "Check your Network Volume mount path!"
    sleep 10 # 로그 볼 시간 벌기
    exit 1
fi

# 3. 가상환경 활성화
if [ -d "$VENV_DIR" ]; then
    echo "Activating VENV: $VENV_DIR"
    source "$VENV_DIR/bin/activate" || echo "venv activate failed"
else
    echo "WARNING: VENV not found at $VENV_DIR, using system python"
fi

cd "$COMFYUI_DIR"

# 4. ComfyUI 실행
# --log-stdout과 tee 조합은 가끔 버퍼링 문제를 일으키니 단순화합니다.
echo "Starting ComfyUI Server..."
python3 -u main.py \
  --listen 0.0.0.0 \
  --port 8188 \
  --disable-auto-launch \
  --disable-metadata &

# 5. ComfyUI가 뜰 때까지 잠깐 대기 (안정성)
sleep 5

# 6. RunPod 핸들러 실행 (rp_handler.py 인지 꼭 확인하세요!)
echo "Starting RunPod Handler..."
if [ -f "/rp_handler.py" ]; then
    exec python3 -u /rp_handler.py
else
    echo "ERROR: /rp_handler.py not found!"
    ls -la /
    sleep 10
    exit 1
fi