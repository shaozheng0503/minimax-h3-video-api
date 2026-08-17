#!/usr/bin/env python3
"""实际提交工作流验证"""
import json, time, urllib.request, urllib.error

BASE = "https://deployment-452-isgikjrp-3000.550w.link"
PROMPT = "A ginger cat stretches lazily on a windowsill, sunlight filtering through white sheer curtains onto its fur, macro close-up, shallow depth of field, warm and cozy"

workflow = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
    "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax"}},
    "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
    "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
    "5": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": 12.0, "shift_audio": 3.0}},
    "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"clip": ["2", 0], "vae": ["3", 0], "prompt": PROMPT, "width": 1280, "height": 736, "length": 124}},
    "7": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["6", 0]}},
    "8": {"class_type": "KSampler", "inputs": {"model": ["5", 0], "seed": 0, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "simple", "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["6", 1], "denoise": 1.0}},
    "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
    "10": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["8", 0], "vae": ["4", 0]}},
    "13": {"class_type": "CreateVideo", "inputs": {"images": ["9", 0], "fps": 24.0, "audio": ["10", 0]}},
    "11": {"class_type": "SaveVideo", "inputs": {"video": ["13", 0], "filename_prefix": "apitest", "format": "auto", "codec": "auto"}},
    "12": {"class_type": "SaveAudio", "inputs": {"audio": ["10", 0], "filename_prefix": "apitest"}},
}

print("提交工作流到端口 3000...")
print("提示词: %s" % PROMPT[:50])
print("分辨率: 1280x736 (720p), 帧数: 124 (~5s)")
print()

body = json.dumps({"prompt": workflow}).encode("utf-8")
req = urllib.request.Request(
    BASE + "/prompt",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)

t0 = time.time()
try:
    print("等待生成中（同步模式，预计 2-10 分钟）...")
    with urllib.request.urlopen(req, timeout=600) as r:
        result = json.loads(r.read())
    elapsed = time.time() - t0

    print()
    print("=" * 50)
    print("生成完成！耗时: %.1fs" % elapsed)
    print("=" * 50)
    print("状态: %s" % result.get("status"))
    print("任务ID: %s" % result.get("id", "N/A"))
    print("文件: %s" % result.get("filenames"))

    stats = result.get("stats", {})
    if stats:
        print("推理耗时: %.1fs" % stats.get("comfy_execution", {}).get("duration", 0))
        print("总耗时: %.1fs" % stats.get("total_time", 0))

    images = result.get("images", [])
    print("输出数据块数: %d" % len(images))
    if images:
        for i, img in enumerate(images):
            if isinstance(img, str):
                print("  images[%d]: %d chars (base64)" % (i, len(img)))
            elif isinstance(img, dict):
                print("  images[%d]: %s" % (i, list(img.keys())))

except urllib.error.HTTPError as e:
    elapsed = time.time() - t0
    print()
    print("HTTP %d (耗时 %.1fs)" % (e.code, elapsed))
    try:
        err = e.read().decode()
        # 截取前 500 字符
        print(err[:500])
    except Exception:
        pass
except Exception as e:
    elapsed = time.time() - t0
    print()
    print("错误 (耗时 %.1fs): %s" % (elapsed, e))
