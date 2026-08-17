#!/usr/bin/env python3
"""
768p / 15秒 连续多轮测试 — 排除冷启动影响
通过 8188 端口提交，轮询 history 等待完成，记录每轮耗时
"""
import json, urllib.request, urllib.parse, time, sys

BASE_8188 = "https://deployment-452-mofsmnkz-8188.550w.link"

SEEDS = [1001, 2002, 3003]
PROMPT = "A cinematic aerial shot of a misty mountain range at dawn, golden sunlight breaking through clouds, lush green valleys, rivers winding through the landscape"
WIDTH = 1344
HEIGHT = 768
LENGTH = 362

def build_workflow(seed):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "5": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0],
            "prompt": PROMPT, "width": WIDTH, "height": HEIGHT, "length": LENGTH
        }},
        "7": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["6", 0]}},
        "8": {"class_type": "KSampler", "inputs": {
            "model": ["5", 0], "seed": seed, "steps": 20, "cfg": 7.0,
            "sampler_name": "euler", "scheduler": "simple",
            "positive": ["6", 0], "negative": ["7", 0],
            "latent_image": ["6", 1], "denoise": 1.0
        }},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["8", 0], "vae": ["4", 0]}},
        "13": {"class_type": "CreateVideo", "inputs": {"images": ["9", 0], "fps": 24.0, "audio": ["10", 0]}},
        "11": {"class_type": "SaveVideo", "inputs": {"video": ["13", 0], "filename_prefix": "768p_bench", "format": "auto", "codec": "auto"}},
        "12": {"class_type": "SaveAudio", "inputs": {"audio": ["10", 0], "filename_prefix": "768p_bench"}},
    }

def submit(workflow):
    """提交到 8188 队列，返回 prompt_id"""
    payload = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(
        BASE_8188 + "/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())
    return resp.get("prompt_id")

def poll(prompt_id, timeout=3600):
    """轮询 history 等待完成"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            url = BASE_8188 + "/history/" + prompt_id
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            if prompt_id in data:
                entry = data[prompt_id]
                status = entry.get("status", {})
                if status.get("completed"):
                    return entry
                if status.get("status_str") == "error":
                    msgs = status.get("messages", [])
                    return {"error": "execution failed", "messages": msgs}
        except Exception:
            pass
        time.sleep(15)
    return None

def get_outputs(entry):
    """从 history entry 提取输出文件名"""
    results = []
    outputs = entry.get("outputs", {})
    for nid, out in outputs.items():
        for key in ["gifs", "images", "audio"]:
            if key in out:
                for item in out[key]:
                    fn = item.get("filename", "")
                    results.append({"node": nid, "type": key, "filename": fn})
    return results

print("=" * 60, flush=True)
print("768p / 15秒 连续多轮基准测试", flush=True)
print("分辨率: %dx%d | 帧数: %d (~%.1fs @ 24fps)" % (WIDTH, HEIGHT, LENGTH, LENGTH / 24), flush=True)
print("seeds: %s" % SEEDS, flush=True)
print("=" * 60, flush=True)

results = []

for i, seed in enumerate(SEEDS):
    print("", flush=True)
    print("[Round %d/%d] seed=%d" % (i + 1, len(SEEDS), seed), flush=True)
    print("  提交时间: %s" % time.strftime("%H:%M:%S"), flush=True)

    wf = build_workflow(seed)
    try:
        prompt_id = submit(wf)
        print("  prompt_id: %s" % prompt_id, flush=True)
    except Exception as e:
        print("  提交失败: %s" % e, flush=True)
        results.append({"seed": seed, "error": str(e)})
        continue

    print("  轮询等待中...", flush=True)
    t0 = time.time()
    entry = poll(prompt_id, timeout=3600)
    elapsed = time.time() - t0

    if entry is None:
        print("  超时!", flush=True)
        results.append({"seed": seed, "prompt_id": prompt_id, "timeout": True, "elapsed": elapsed})
        continue

    if "error" in entry:
        print("  执行失败!", flush=True)
        results.append({"seed": seed, "prompt_id": prompt_id, "error": entry["error"], "elapsed": elapsed})
        continue

    outputs = get_outputs(entry)
    print("  完成: %s" % time.strftime("%H:%M:%S"), flush=True)
    print("  耗时: %.1f 秒 (%.1f 分钟)" % (elapsed, elapsed / 60), flush=True)
    print("  输出:", flush=True)
    for o in outputs:
        print("    [%s] %s" % (o["type"], o["filename"]), flush=True)

    results.append({
        "seed": seed,
        "prompt_id": prompt_id,
        "elapsed_sec": round(elapsed, 1),
        "elapsed_min": round(elapsed / 60, 1),
        "outputs": outputs,
    })

print("", flush=True)
print("=" * 60, flush=True)
print("测试汇总", flush=True)
print("=" * 60, flush=True)
for r in results:
    if "elapsed_sec" in r:
        print("seed=%d: %.1f 秒 (%.1f 分钟)" % (r["seed"], r["elapsed_sec"], r["elapsed_min"]), flush=True)
    elif "error" in r:
        print("seed=%d: 失败 (%s)" % (r["seed"], r.get("error", "?")), flush=True)
    elif "timeout" in r:
        print("seed=%d: 超时" % r["seed"], flush=True)

valid = [r for r in results if "elapsed_sec" in r]
if len(valid) >= 2:
    # 去掉第一次（可能含冷启动），取后面的平均
    warm = valid[1:]
    avg = sum(r["elapsed_sec"] for r in warm) / len(warm)
    print("", flush=True)
    print("去掉首次(预热)后平均: %.1f 秒 (%.1f 分钟)" % (avg, avg / 60), flush=True)
