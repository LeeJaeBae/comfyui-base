COMFYUI_DIR="/runpod-volume/runpod-slim/ComfyUI"
VENV_DIR="$COMFYUI_DIR/.venv-cu128"

# venv 있으면 활성화
if [ -d "$VENV_DIR" ]; then
  source "$VENV_DIR/bin/activate"
fi

cd "$COMFYUI_DIR"

# ComfyUI 실행 (8188)
python -u main.py --listen 0.0.0.0 --port 8188 --disable-auto-launch --disable-metadata --log-stdout &

# handler 실행 (포그라운드)
exec python -u /handler.py
