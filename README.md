# MiniMax H3 Video Generation API

基于 ComfyUI 的 MiniMax H3 视频生成服务封装与基准测试。提供零依赖 Python SDK（文生视频 / 图生视频 / 参考图生视频，同步 + 异步双模式），以及在 RTX 5090 上 27 个用例的完整实测数据与生成视频。

> 测试环境：共绩算力弹性 GPU 实例 · ComfyUI 0.31.0 · PyTorch 2.13.0 + CUDA 13.0 · comfyui-api 代理 v1.17.1

## ✨ 特性

- **零依赖 Python SDK** — 纯标准库实现，无需 `pip install` 任何第三方包
- **双档质量** — `turbo`（4 步蒸馏 LoRA，默认，约快 5 倍）与 `standard`（20 步原版）
- **三种生成模式** — 文生视频（T2V）、图生视频（I2V，首/尾帧）、参考图生视频（Ref2V）
- **同步 + 异步** — 同步直接返回结果；异步通过 webhook_v2 回调，适合生产环境
- **带音频输出** — MiniMax H3 原生音频轨（VAEDecodeAudio），输出 MP4 自带声音
- **存储后端** — 支持 S3 / Azure Blob / HuggingFace 输出直传
- **27 例实测基准** — 480p/720p/1080p × 5s/10s/15s × 多提示词，原始数据与生成视频全部入库

## 🚀 快速开始

```bash
git clone https://github.com/shaozheng0503/minimax-h3-video-api.git
cd minimax-h3-video-api/sdks/python
```

### 一行代码生成视频（turbo 档）

```python
from comfyui_minimax_h3_sdk import generate_video

# turbo 档：4 步加速 LoRA，720p/5s 约 75 秒出片
files = generate_video(
    "A ginger cat stretches lazily on a windowsill, sunlight filtering through curtains",
    base_url="https://<你的服务地址>:3000",
)
```

### 高画质档（standard，20 步）

```python
files = generate_video(
    "A ginger cat stretches lazily on a windowsill",
    base_url="https://<你的服务地址>:3000",
    quality="standard",   # 20 步原版，约 5-7 分钟，画质上限略高
)
```

### 异步模式（生产推荐）

```python
from comfyui_minimax_h3_sdk import ComfyUI, build_t2v_workflow

client = ComfyUI("https://<你的服务地址>:3000")
workflow = build_t2v_workflow(prompt_text="A cat playing piano")

result = client.async_submit(
    workflow,
    webhook_url="https://your-server.com/callback",
    task_id="my-task-001",
)
print("任务已提交:", result["id"])
# 完成后服务端回调 webhook_v2，带签名验证
```

## 📊 性能基准（RTX 5090 + turbo 档）

完整报告见 [`docs/benchmark-dual-5090.md`](docs/benchmark-dual-5090.md)（双卡 18 例）与 [`docs/benchmark-single-5090.md`](docs/benchmark-single-5090.md)（单卡 9 例）。

生成耗时（热启动中位数）：

| 分辨率 | 5s | 10s | 15s |
|--------|-----|------|------|
| 480p | ~38s | ~65s | ~117s |
| 720p | ~75s | ~168s | ~375s |
| 1080p | ~228s | ~584s | ~1472s |

> standard 档（20 步无加速）耗时约为 turbo 的 5 倍。
> 1080p 长时长档建议用异步模式并限制并发；不适合实时场景。

**关键结论**：双卡 5090 对单任务**无加速**（ComfyUI 单任务跑单卡），价值在于并发吞吐 ×2（双实例 + 负载均衡）。详见报告第五章「双卡利用情况」。

## 📁 仓库结构

```
├── README.md                        # 本文件
├── sdks/python/                     # Python SDK（零依赖）
│   ├── comfyui_minimax_h3_sdk.py    # SDK 主文件
│   ├── test_sdk_e2e.py              # 端到端测试脚本
│   └── README.md                    # SDK 使用说明
├── docs/
│   ├── api-documentation.md         # 完整 API 接入文档（curl/Python/JS 示例）
│   ├── benchmark-dual-5090.md       # 双卡 5090 基准报告（18 例）
│   ├── benchmark-single-5090.md     # 单卡 5090 基准报告（9 例）
│   ├── benchmark_dual_results.json  # 18 例原始数据
│   ├── benchmark_results.json       # 9 例原始数据
│   ├── benchmark_dual5090.py        # 双卡基准脚本（可复跑）
│   ├── benchmark_minimax_h3.py      # 单卡基准脚本（可复跑）
│   └── minimax_h3_turbo_api.json    # 工作流模板（API 格式）
└── outputs/                         # 27 个生成视频（MP4，含音频）
    ├── dual_*.mp4                   # 双卡基准 18 例
    └── bench_*.mp4                   # 单卡基准 9 例
```

## 🧩 工作流结构（turbo 档）

```
UNETLoader(fl2va int8) → LoraLoaderModelOnly(turbo_4step) → MiniMaxH3SigmaShift(12/3)
CLIPLoader(Qwen3VL, minimax) ┐
VAELoader(video_fp16)        ┴→ MiniMaxH3ImageToVideo(prompt, W, H, length)
                                  ↓ [0]=CONDITIONING, [1]=LATENT
RandomNoise(seed) → BasicGuider ← conditioning
BasicScheduler(simple, 4步) → SamplerCustomAdvanced ← latent
VAEDecode(video) + VAEDecodeAudio(audio) → CreateVideo(24fps) → SaveVideo
```

## 📐 关键约束：H3 帧数网格（17k+5）

MiniMax H3 的输出帧数必须落在 17k+5 网格上，宽高需对齐 32 倍数：

```python
def frames_from_seconds(s):
    base = max(5, round(s * 24))
    return base + (5 - (base % 17)) % 17

# 5s  → 124 帧（实际 5.2s @ 24fps）
# 10s → 243 帧（实际 10.1s）
# 15s → 362 帧（实际 15.1s）
```

分辨率档位（宽×高均为 32 倍数）：

| 档位 | 16:9 | 9:16 | 4:3 |
|------|------|------|-----|
| 480p | 864×480 | 480×864 | 640×480 |
| 720p | 1280×720 | 720×1280 | 960×720 |
| 1080p | 1920×1080 | 1080×1920 | 1440×1080 |

## 📈 成本参考

共绩算力 RTX 5090 按卡时计费：

| 计费项 | 数值 |
|--------|------|
| 按需价格 | 3.25 元/卡时 |
| SPOT 实例 | 约 40% 价格 |
| 计费粒度 | 秒级 |
| 并发模型 | 1 实例 = 1 GPU = 1 并发任务 |

## 📹 测试视频

27 个生成视频（共约 90MB，MP4 含音频轨）直接存放在 [`outputs/`](outputs/) 目录：

- `dual_*.mp4` — 双卡基准 18 例（6 提示词 × 3 分辨率），文件名格式 `dual_{分辨率}_{用例}_{模型}`
- `bench_*.mp4` — 单卡基准 9 例

每个视频对应的提示词、参数、耗时见 `docs/benchmark_dual_results.json` 与两份基准报告。

## 📄 License

MIT
