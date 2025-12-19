![ComfyUI Worker Banner](https://cpjrphpz3t5wbwfe.public.blob.vercel-storage.com/worker-comfyui_banner-CDZ6JIEByEePozCT1ZrmeVOsN5NX3U.jpeg)

---

Run [ComfyUI](https://github.com/comfyanonymous/ComfyUI) workflows as a serverless endpoint.

---

[![RunPod](https://api.runpod.io/badge/runpod-workers/worker-comfyui)](https://www.runpod.io/console/hub/runpod-workers/worker-comfyui)

---

## Usage

The worker accepts the following input parameters:

| Parameter  | Type     | Default | Required | Description                                                                                                                                                                                                                                    |
| :--------- | :------- | :------ | :------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `workflow` | `object` | `None`  | **Yes**  | The entire ComfyUI workflow in the API JSON format. See the main project [README.md](https://github.com/runpod-workers/worker-comfyui#how-to-get-the-workflow-from-comfyui) for instructions on how to export this from the ComfyUI interface. |
| `images`   | `array`  | `[]`    | No       | An optional array of input images. Each image object should contain `name` (string, required, filename to reference in the workflow) and `image` (string, required, base64-encoded image data).                                                |

> [!NOTE]
> The `input.images` array has specific size constraints based on RunPod API limits (10MB for `/run`, 20MB for `/runsync`). See the main [README.md](https://github.com/runpod-workers/worker-comfyui#inputimages) for details.

### Example Request

This example uses a simplified workflow (replace with your actual workflow JSON).

```json
{
  "input": {
    "workflow": {
      "3": {
        "inputs": {
          "seed": 1337,
          "steps": 20,
          "cfg": 8,
          "sampler_name": "euler",
          "scheduler": "normal",
          "denoise": 1,
          "model": ["4", 0],
          "positive": ["6", 0],
          "negative": ["7", 0],
          "latent_image": ["5", 0]
        },
        "class_type": "KSampler"
      },
      "4": {
        "inputs": {
          "ckpt_name": "sd_xl_base_1.0.safetensors"
        },
        "class_type": "CheckpointLoaderSimple"
      },
      "5": {
        "inputs": {
          "width": 512,
          "height": 512,
          "batch_size": 1
        },
        "class_type": "EmptyLatentImage"
      },
      "6": {
        "inputs": {
          "text": "beautiful scenery nature glass bottle landscape, purple galaxy bottle,",
          "clip": ["4", 1]
        },
        "class_type": "CLIPTextEncode"
      },
      "7": {
        "inputs": {
          "text": "text, watermark",
          "clip": ["4", 1]
        },
        "class_type": "CLIPTextEncode"
      },
      "8": {
        "inputs": {
          "samples": ["3", 0],
          "vae": ["4", 2]
        },
        "class_type": "VAEDecode"
      },
      "9": {
        "inputs": {
          "filename_prefix": "ComfyUI",
          "images": ["8", 0]
        },
        "class_type": "SaveImage"
      }
    },
    "images": [
      {
        "name": "input_image_1.png",
        "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
      }
    ]
  }
}
```

### Example Response

```json
{
  "delayTime": 2188,
  "executionTime": 2297,
  "id": "sync-c0cd1eb2-068f-4ecf-a99a-55770fc77391-e1",
  "output": {
    "message": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAABAAAAAQACAIAAADwf7zU...",
    "status": "success"
  },
  "status": "COMPLETED"
}
```
