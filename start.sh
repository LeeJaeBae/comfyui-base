#!/usr/bin/env bash
set -euxo pipefail

COMFYUI_DIR="/runpod-volume/runpod-slim/ComfyUI"
VENV_DIR="$COMFYUI_DIR/.venv-cu128"

echo "START.SH BOOTED: $(date)"
echo "COMFYUI_DIR=$COMFYUI_DIR"
ls -la /handler.py || true
ls -la "$COMFYUI_DIR" | head

if [ -d "$VENV_DIR" ]; then
  source "$VENV_DIR/bin/activate" || echo "venv activate failed, using system python"
fi

cd "$COMFYUI_DIR"

# ComfyUI 로그를 컨테이너 stdout으로 강제
python3 -u main.py \
  --listen 0.0.0.0 \
  --port 8188 \
  --disable-auto-launch \
  --disable-metadata \
  --log-stdout 2>&1 | tee /proc/1/fd/1 &

echo "Starting handler..."
exec python3 -u /rp_handler.py
