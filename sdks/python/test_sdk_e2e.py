#!/usr/bin/env python3
"""
SDK 端到端测试 — 用 comfyui_minimax_h3_sdk.py 实际生成视频并保存到本地。
默认 turbo 加速档（约 1-2 分钟）；加 --standard 参数测 20 步原版档。

用法:
    python test_sdk_e2e.py https://<你的服务地址>:3000
    python test_sdk_e2e.py https://<你的服务地址>:3000 --standard

也可用环境变量:
    MINIMAX_BASE_URL="https://<你的服务地址>:3000" python test_sdk_e2e.py
"""

import sys
import os

# 确保能 import 同目录的 SDK
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comfyui_minimax_h3_sdk import ComfyUI, build_t2v_workflow

# 服务地址：优先取命令行参数，其次环境变量，最后用占位符提示
BASE_URL = None
for arg in sys.argv[1:]:
    if arg.startswith("http"):
        BASE_URL = arg.rstrip("/")
if not BASE_URL:
    BASE_URL = os.environ.get("MINIMAX_BASE_URL", "").rstrip("/")

QUALITY = "standard" if "--standard" in sys.argv else "turbo"

if not BASE_URL:
    print("用法: python test_sdk_e2e.py https://<你的服务地址>:3000 [--standard]")
    print("或:   设置环境变量 MINIMAX_BASE_URL")
    sys.exit(1)

SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

print("=" * 60)
print("MiniMax H3 SDK 端到端测试")
print("服务地址:", BASE_URL)
print("=" * 60)

# --- Step 1: 健康检查 ---
print("\n[1/4] 健康检查...")
client = ComfyUI(BASE_URL)
try:
    h = client.health()
    print("  health:", h)
except Exception as e:
    print("  health 失败:", e)
    print("  服务可能未就绪，退出")
    sys.exit(1)

# --- Step 2: 构建工作流 ---
print("\n[2/4] 构建工作流（quality=%s）..." % QUALITY)
workflow = build_t2v_workflow(
    prompt_text="A ginger cat stretches lazily on a windowsill, sunlight filtering through white sheer curtains onto its fur, macro close-up, shallow depth of field, warm and cozy",
    width=1280,
    height=736,
    length=124,
    seed=42,
    quality=QUALITY,
)
preset_steps = workflow["8"]["inputs"]["steps"]
preset_cfg = workflow["8"]["inputs"]["cfg"]
has_lora = "15" in workflow
print("  节点数:", len(workflow))
print("  分辨率: 1280x736 (720p)")
print("  帧数: 124 (~5.2s @ 24fps)")
print("  steps: %s | cfg: %s | turbo LoRA: %s" % (preset_steps, preset_cfg, "是" if has_lora else "否"))
print("  seed: 42")

# --- Step 3: 同步生成 ---
est = "1-2 分钟" if QUALITY == "turbo" else "5-8 分钟"
print("\n[3/4] 提交工作流（同步模式，预计 %s）..." % est)
print("  开始时间:", __import__("datetime").datetime.now().strftime("%H:%M:%S"))

try:
    result = client.sync_generate(workflow, timeout=600)
    print("  HTTP 200 成功!")
    print("  任务 ID:", result.get("id", "N/A"))

    # stats
    stats = result.get("stats", {})
    duration_ms = stats.get("comfy_execution", {}).get("duration", 0)
    total_ms = stats.get("total_time", 0)
    if duration_ms:
        print("  推理耗时: %.1fs" % (duration_ms / 1000))
    if total_ms:
        print("  总耗时: %.1fs" % (total_ms / 1000))

    # filenames
    filenames = result.get("filenames", [])
    print("  输出文件:", filenames)

    # images count
    images = result.get("images", [])
    print("  images 数量:", len(images))
    for i, img in enumerate(images):
        if isinstance(img, str):
            print("    images[%d]: %d chars (base64)" % (i, len(img)))

except Exception as e:
    print("  生成失败:", e)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# --- Step 4: 保存输出 ---
print("\n[4/4] 保存输出文件到 %s ..." % SAVE_DIR)
files = client.save_sync_outputs(result, save_dir=SAVE_DIR)

if files:
    print("  保存成功!")
    for f in files:
        size_str = "%.2f MB" % f.get("size_mb", 0) if f.get("size_mb") else "N/A"
        print("    [%s] %s (%s)" % (f.get("type", "?"), os.path.basename(f.get("path", "")), size_str))
else:
    print("  没有保存任何文件")

print("\n" + "=" * 60)
print("测试完成!")
print("=" * 60)
