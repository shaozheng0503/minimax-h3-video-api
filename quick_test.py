#!/usr/bin/env python3
"""
MiniMax H3 API 快速验证脚本
零依赖，Python 3.8+ 直接运行

用法:
    python quick_test.py https://your-service:3000
"""

import json
import sys
import time
import urllib.request
import urllib.error

PROMPT = "A ginger cat stretches lazily on a windowsill, sunlight filtering through white sheer curtains onto its fur, macro close-up, shallow depth of field, warm and cozy"


def build_workflow():
    return {
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
        "11": {"class_type": "SaveVideo", "inputs": {"video": ["13", 0], "filename_prefix": "quicktest", "format": "auto", "codec": "auto"}},
        "12": {"class_type": "SaveAudio", "inputs": {"audio": ["10", 0], "filename_prefix": "quicktest"}},
    }


def main(base_url):
    base_url = base_url.rstrip("/")
    print("=" * 60)
    print("  MiniMax H3 API 快速验证")
    print("  地址: %s" % base_url)
    print("=" * 60)

    # 1. 健康检查
    print("\n[1/3] 健康检查...")
    try:
        resp = urllib.request.urlopen(base_url + "/health", timeout=10)
        data = json.loads(resp.read())
        print("  /health: %s" % data)
    except Exception as e:
        print("  健康检查失败: %s" % e)
        print("  请确认服务地址正确且服务已启动")
        sys.exit(1)

    # 2. 就绪检查
    print("\n[2/3] 就绪检查...")
    try:
        resp = urllib.request.urlopen(base_url + "/ready", timeout=10)
        data = json.loads(resp.read())
        print("  /ready: %s" % data)
    except urllib.error.HTTPError as e:
        print("  就绪检查返回 %d（队列可能已满）" % e.code)
    except Exception as e:
        print("  就绪检查失败: %s" % e)

    # 3. 提交工作流
    print("\n[3/3] 提交工作流（同步模式，预计 2-10 分钟）...")
    workflow = build_workflow()
    body = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(
        base_url + "/prompt",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            result = json.loads(r.read())
        elapsed = time.time() - t0
        print("  生成完成！耗时: %.1fs" % elapsed)
        print("  状态: %s" % result.get("status"))
        print("  文件: %s" % result.get("filenames"))
        stats = result.get("stats", {})
        if stats:
            print("  推理耗时: %.1fs" % stats.get("comfy_execution", {}).get("duration", 0))
            print("  总耗时: %.1fs" % stats.get("total_time", 0))
    except urllib.error.HTTPError as e:
        elapsed = time.time() - t0
        print("  HTTP %d (耗时 %.1fs)" % (e.code, elapsed))
        try:
            err_body = e.read().decode()
            print("  响应: %s" % err_body[:500])
        except Exception:
            pass
        if e.code == 503:
            print("  提示: 服务正在扩缩容，请等待几秒后重试")
    except Exception as e:
        elapsed = time.time() - t0
        print("  错误 (耗时 %.1fs): %s" % (elapsed, e))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python quick_test.py <base_url>")
        print("示例: python quick_test.py https://your-service:3000")
        sys.exit(1)
    main(sys.argv[1])
