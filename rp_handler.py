import os
import json
import time
import base64
import traceback
import uuid
from typing import Dict, Any, List, Tuple, Optional

import requests
import websocket
import runpod


# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
COMFY_HOST = os.getenv("COMFY_HOST", "127.0.0.1")
COMFY_PORT = int(os.getenv("COMFY_PORT", "8188"))
COMFY_HTTP = f"http://{COMFY_HOST}:{COMFY_PORT}"
COMFY_WS = f"ws://{COMFY_HOST}:{COMFY_PORT}/ws"

# RunPod: refresh worker after each job (clean state)
REFRESH_WORKER = os.environ.get("REFRESH_WORKER", "false").lower() == "true"

# How long to wait for ComfyUI to be reachable at startup (handler side)
CONNECT_RETRIES = int(os.getenv("COMFY_CONNECT_RETRIES", "500"))
CONNECT_SLEEP_SEC = float(os.getenv("COMFY_CONNECT_SLEEP_SEC", "0.2"))

# Websocket receive timeout (seconds)
WS_RECV_TIMEOUT_SEC = float(os.getenv("WS_RECV_TIMEOUT_SEC", "10"))

# If websocket is silent this many times in a row, assume execution is done and go fetch history
WS_SILENT_MAX = int(os.getenv("WS_SILENT_MAX", "8"))

# Default job timeout (seconds) if job input doesn't specify
DEFAULT_JOB_TIMEOUT_SEC = int(os.getenv("DEFAULT_JOB_TIMEOUT_SEC", "600"))


# -----------------------------------------------------------------------------
# HTTP Helpers
# -----------------------------------------------------------------------------
def _get_json(path: str) -> Dict[str, Any]:
    r = requests.get(f"{COMFY_HTTP}{path}", timeout=60)
    r.raise_for_status()
    return r.json()


def _post_json(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(f"{COMFY_HTTP}{path}", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def _wait_for_comfy():
    """Block until ComfyUI is reachable (or raise)."""
    last_err = None
    for _ in range(CONNECT_RETRIES):
        try:
            # system_stats exists on recent ComfyUI; if not, fallback to object_info
            try:
                _get_json("/system_stats")
            except Exception:
                _get_json("/object_info")
            return
        except Exception as e:
            last_err = e
            time.sleep(CONNECT_SLEEP_SEC)
    raise RuntimeError(f"Failed to connect to ComfyUI at {COMFY_HTTP} after {CONNECT_RETRIES} attempts: {last_err}")


# -----------------------------------------------------------------------------
# Image Upload + Workflow Injection
# -----------------------------------------------------------------------------
def _parse_data_url_image(data_url: str) -> bytes:
    """
    Accepts:
      - "data:image/png;base64,AAA..."
      - or raw base64 "AAA..."
    Returns bytes.
    """
    if data_url.startswith("data:"):
        # data:[<mediatype>][;base64],<data>
        try:
            header, b64 = data_url.split(",", 1)
        except ValueError:
            raise ValueError("Invalid data URL format")
        return base64.b64decode(b64)
    return base64.b64decode(data_url)


def upload_image_to_comfy(image_bytes: bytes, name: str) -> str:
    """
    Upload image to ComfyUI /upload/image.
    Returns uploaded filename (ComfyUI-side).
    """
    files = {"image": (name, image_bytes)}
    r = requests.post(f"{COMFY_HTTP}/upload/image", files=files, timeout=120)
    r.raise_for_status()
    data = r.json()
    # Usually: {"name":"...","subfolder":"","type":"input"}
    return data["name"]


def inject_uploaded_images(workflow: Dict[str, Any], name_map: Dict[str, str]) -> Dict[str, Any]:
    """
    Replace any string input value that matches original image name with uploaded filename.
    Example: if node.inputs.image == "test.png" then replace with "test_123.png" returned by ComfyUI.
    """
    for node_id, node in workflow.items():
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue

        for k, v in list(inputs.items()):
            if isinstance(v, str) and v in name_map:
                inputs[k] = name_map[v]

    return workflow


# -----------------------------------------------------------------------------
# Queue + Wait
# -----------------------------------------------------------------------------
def queue_workflow(workflow: Dict[str, Any], client_id: str) -> str:
    resp = _post_json("/prompt", {"prompt": workflow, "client_id": client_id})
    prompt_id = resp.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI /prompt did not return prompt_id: {resp}")
    return prompt_id


def wait_until_done(prompt_id: str, client_id: str, timeout_sec: int) -> Tuple[bool, List[str]]:
    """
    Wait for completion via websocket. Robust to missing 'node=None' final signal.
    Returns: (done, errors)
    """
    errors: List[str] = []
    ws = None
    start = time.time()
    silent_count = 0
    done = False

    try:
        ws = websocket.WebSocket()
        ws.settimeout(WS_RECV_TIMEOUT_SEC)
        ws.connect(f"{COMFY_WS}?clientId={client_id}")

        while True:
            # Hard timeout
            if time.time() - start > timeout_sec:
                errors.append(f"timeout waiting for prompt_id={prompt_id}")
                break

            try:
                raw = ws.recv()
                silent_count = 0  # got something

                if not raw:
                    continue

                msg = json.loads(raw)
                mtype = msg.get("type")

                # Error signal
                if mtype == "execution_error":
                    errors.append(json.dumps(msg))
                    break

                # Most reliable "done" signal when present
                if mtype == "executing":
                    data = msg.get("data", {})
                    if data.get("prompt_id") == prompt_id:
                        # When node is None, many builds use that as "graph finished"
                        if data.get("node") is None:
                            done = True
                            break

                # Some builds emit "executed" per node; not strictly needed
                # if mtype == "executed": ...

            except websocket.WebSocketTimeoutException:
                silent_count += 1
                # If websocket goes silent for a while, assume it's done and fetch history.
                # This fixes the "hang forever" problem.
                if silent_count >= WS_SILENT_MAX:
                    done = True
                    break
            except websocket.WebSocketConnectionClosedException:
                # If ws closed, best effort: assume done and fetch history.
                done = True
                break

    finally:
        try:
            if ws:
                ws.close()
        except Exception:
            pass

    return done, errors


# -----------------------------------------------------------------------------
# Output Fetching
# -----------------------------------------------------------------------------
def fetch_history(prompt_id: str) -> Dict[str, Any]:
    hist = _get_json(f"/history/{prompt_id}")
    item = hist.get(prompt_id)
    if not item:
        # Sometimes history is delayed; small retry
        for _ in range(10):
            time.sleep(0.2)
            hist = _get_json(f"/history/{prompt_id}")
            item = hist.get(prompt_id)
            if item:
                break
    if not item:
        raise RuntimeError(f"No history item for prompt_id={prompt_id}")
    return item


def _download_view_file(filename: str, folder_type: str = "output", subfolder: str = "") -> bytes:
    params = {
        "filename": filename,
        "type": folder_type,
    }
    if subfolder:
        params["subfolder"] = subfolder

    # build query safely
    q = "&".join([f"{k}={requests.utils.quote(str(v))}" for k, v in params.items()])
    url = f"{COMFY_HTTP}/view?{q}"

    r = requests.get(url, timeout=120)
    r.raise_for_status()
    return r.content


def collect_outputs_as_data_urls(history_item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Return outputs as list of:
      { kind, filename, data_url, subfolder, type }
    """
    results: List[Dict[str, Any]] = []
    outputs = history_item.get("outputs", {}) or {}

    for _, out in outputs.items():
        # Images
        for img in (out.get("images") or []):
            filename = img.get("filename")
            if not filename:
                continue
            folder_type = img.get("type", "output")
            subfolder = img.get("subfolder", "")

            blob = _download_view_file(filename, folder_type=folder_type, subfolder=subfolder)
            # Try infer mime (ComfyUI typically outputs png/webp)
            mime = "image/png"
            if filename.lower().endswith(".webp"):
                mime = "image/webp"
            elif filename.lower().endswith(".jpg") or filename.lower().endswith(".jpeg"):
                mime = "image/jpeg"

            b64 = base64.b64encode(blob).decode("utf-8")
            results.append({
                "kind": "image",
                "filename": filename,
                "subfolder": subfolder,
                "type": folder_type,
                "data_url": f"data:{mime};base64,{b64}",
            })

        # Videos (some nodes output "videos")
        for vid in (out.get("videos") or []):
            filename = vid.get("filename")
            if not filename:
                continue
            folder_type = vid.get("type", "output")
            subfolder = vid.get("subfolder", "")

            blob = _download_view_file(filename, folder_type=folder_type, subfolder=subfolder)
            mime = "video/mp4"
            if filename.lower().endswith(".webm"):
                mime = "video/webm"
            b64 = base64.b64encode(blob).decode("utf-8")
            results.append({
                "kind": "video",
                "filename": filename,
                "subfolder": subfolder,
                "type": folder_type,
                "data_url": f"data:{mime};base64,{b64}",
            })

        # GIFs (some nodes output "gifs")
        for gif in (out.get("gifs") or []):
            filename = gif.get("filename")
            if not filename:
                continue
            folder_type = gif.get("type", "output")
            subfolder = gif.get("subfolder", "")

            blob = _download_view_file(filename, folder_type=folder_type, subfolder=subfolder)
            mime = "image/gif"
            b64 = base64.b64encode(blob).decode("utf-8")
            results.append({
                "kind": "gif",
                "filename": filename,
                "subfolder": subfolder,
                "type": folder_type,
                "data_url": f"data:{mime};base64,{b64}",
            })

    return results


# -----------------------------------------------------------------------------
# Handler
# -----------------------------------------------------------------------------
def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Expected input format (your test matches this):
    {
      "images": [{"name":"test.png","image":"data:image/png;base64,..."}],
      "workflow": {...}
    }
    """

    print("HANDLER START", flush=True)
    print("QUEUE WORKFLOW", flush=True)
    print("PROMPT ID:", prompt_id, flush=True)
    print("WAIT WS...", flush=True)
    print("WS DONE OR TIMEOUT", flush=True)
    print("FETCH HISTORY", flush=True)
    print("RETURN OUTPUTS", flush=True)



    try:
        _wait_for_comfy()

        inp = job.get("input", {}) or {}
        workflow = inp.get("workflow")
        if not isinstance(workflow, dict):
            return {"error": "input.workflow (dict) is required"}

        # Optional job timeout override (milliseconds in your test sometimes)
        timeout_ms = job.get("timeout") or inp.get("timeout")
        timeout_sec = DEFAULT_JOB_TIMEOUT_SEC
        if isinstance(timeout_ms, (int, float)) and timeout_ms > 1000:
            timeout_sec = int(timeout_ms / 1000)

        client_id = inp.get("client_id") or uuid.uuid4().hex

        # Upload images if provided and inject into workflow by filename match
        images = inp.get("images") or []
        name_map: Dict[str, str] = {}
        if isinstance(images, list) and images:
            for im in images:
                if not isinstance(im, dict):
                    continue
                orig_name = im.get("name") or f"input_{uuid.uuid4().hex}.png"
                data = im.get("image")
                if not data:
                    continue
                img_bytes = _parse_data_url_image(data)
                uploaded_name = upload_image_to_comfy(img_bytes, orig_name)
                name_map[orig_name] = uploaded_name

            if name_map:
                workflow = inject_uploaded_images(workflow, name_map)

        # Queue workflow
        prompt_id = queue_workflow(workflow, client_id)

        # Wait
        done, ws_errors = wait_until_done(prompt_id, client_id, timeout_sec=timeout_sec)

        # Fetch outputs regardless (best effort)
        hist_item = fetch_history(prompt_id)
        outputs = collect_outputs_as_data_urls(hist_item)

        resp: Dict[str, Any] = {
            "prompt_id": prompt_id,
            "done": bool(done),
            "ws_errors": ws_errors,
            "uploaded_images": name_map,   # original -> uploaded
            "outputs": outputs,            # data URLs
        }

        # RunPod additional controls
        if REFRESH_WORKER:
            resp["refresh_worker"] = True

        return resp

    except Exception as e:
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "refresh_worker": True if REFRESH_WORKER else False
        }


# Start the Serverless function when the script is run
if __name__ == '__main__':
    runpod.serverless.start({'handler': handler })