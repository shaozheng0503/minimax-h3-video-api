#!/usr/bin/env python3
"""768p / 15秒 生成速度测试"""
import json, urllib.request, time, base64, os, sys

BASE = "https://deployment-452-mofsmnkz-3000.550w.link"

workflow = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
    "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax"}},
    "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
    "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
    "5": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": 12.0, "shift_audio": 3.0}},
    "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
        "clip": ["2", 0], "vae": ["3", 0],
        "prompt": "A cinematic aerial shot of a misty mountain range at dawn, golden sunlight breaking through clouds, lush green valleys, rivers winding through the landscape",
        "width": 1344, "height": 768, "length": 362
    }},
    "7": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["6", 0]}},
    "8": {"class_type": "KSampler", "inputs": {
        "model": ["5", 0], "seed": 8888, "steps": 20, "cfg": 7.0,
        "sampler_name": "euler", "scheduler": "simple",
        "positive": ["6", 0], "negative": ["7", 0],
        "latent_image": ["6", 1], "denoise": 1.0
    }},
    "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
    "10": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["8", 0], "vae": ["4", 0]}},
    "13": {"class_type": "CreateVideo", "inputs": {"images": ["9", 0], "fps": 24.0, "audio": ["10", 0]}},
    "11": {"class_type": "SaveVideo", "inputs": {"video": ["13", 0], "filename_prefix": "768p_15s", "format": "auto", "codec": "auto"}},
    "12": {"class_type": "SaveAudio", "inputs": {"audio": ["10", 0], "filename_prefix": "768p_15s"}},
}

print("=== 768p / 362帧 (~15秒) 生成测试 ===", flush=True)
print("分辨率: 1344x768 (768p)", flush=True)
print("帧数: 362 (~15.1s @ 24fps)", flush=True)
print("开始: %s" % time.strftime("%H:%M:%S"), flush=True)
print("提交中...", flush=True)

payload = json.dumps({"prompt": workflow}).encode("utf-8")
t0 = time.time()

for attempt in range(5):
    try:
        req = urllib.request.Request(
            BASE + "/prompt", data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1800) as r:
            raw = r.read()
            j = json.loads(raw)
            elapsed = time.time() - t0
            stats = j.get("stats", {})
            dur_ms = stats.get("comfy_execution", {}).get("duration", 0)
            total_ms = stats.get("total_time", 0)

            print("", flush=True)
            print("完成: %s" % time.strftime("%H:%M:%S"), flush=True)
            print("------------------------------", flush=True)
            print("Wall clock:   %.1f 秒 (%.1f 分钟)" % (elapsed, elapsed / 60), flush=True)
            print("推理耗时:     %.1f 秒 (%.1f 分钟)" % (dur_ms / 1000, dur_ms / 1000 / 60), flush=True)
            print("总耗时:       %.1f 秒 (%.1f 分钟)" % (total_ms / 1000, total_ms / 1000 / 60), flush=True)
            print("filenames:   %s" % j.get("filenames", []), flush=True)

            images = j.get("images", [])
            print("images: %d 个" % len(images), flush=True)
            os.makedirs("output", exist_ok=True)
            for i, img in enumerate(images):
                if isinstance(img, str) and len(img) > 100:
                    raw_data = base64.b64decode(img)
                    mb = len(raw_data) / 1024 / 1024
                    if raw_data[:4] == b"fLaC":
                        ext, ft = "flac", "FLAC"
                    elif raw_data[4:8] == b"ftyp":
                        ext, ft = "mp4", "MP4"
                    else:
                        ext, ft = "bin", raw_data[:4].hex()
                    path = os.path.join("output", "768p_15s_%d.%s" % (i, ext))
                    with open(path, "wb") as f:
                        f.write(raw_data)
                    print("  images[%d]: %.2f MB [%s] -> %s" % (i, mb, ft, path), flush=True)
            print("", flush=True)
            print("=== 测试完成 ===", flush=True)
            sys.exit(0)
    except urllib.error.HTTPError as e:
        if e.code == 503:
            print("503, retry %d/5..." % (attempt + 1), flush=True)
            time.sleep(5)
            continue
        print("HTTP %d: %s" % (e.code, e.read().decode("utf-8", errors="replace")[:300]), flush=True)
        sys.exit(1)
    except Exception as e:
        print("ERROR: %s" % e, flush=True)
        if attempt < 4:
            time.sleep(5)
            continue
        sys.exit(1)

print("All retries exhausted", flush=True)
