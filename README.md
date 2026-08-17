# MiniMax H3 视频生成 API

基于 ComfyUI 的 MiniMax H3 文生视频 / 图生视频 API 接入方案，部署于共绩算力弹性服务。

## 文件说明

| 文件 | 说明 |
|------|------|
| `MiniMax_H3_API_Doc.md` | 完整 API 接入文档（1391 行），客户直接参考 |
| `comfyui_minimax_h3_sdk.py` | Python SDK（零依赖，仅标准库） |
| `test_sdk_e2e.py` | 端到端测试脚本（720p） |
| `test_768p_15s.py` | 768p / 15秒 生成速度测试脚本 |
| `test_768p_benchmark.py` | 768p 多轮连续基准测试脚本 |

## 快速开始

### 1. 健康检查

```bash
curl -s "https://<你的服务地址>:3000/health"
# {"version":"1.17.1","status":"healthy"}
```

### 2. 用 SDK 一行生成视频

```python
from comfyui_minimax_h3_sdk import generate_video

files = generate_video(
    "A ginger cat stretches lazily on a windowsill",
    base_url="https://<你的服务地址>:3000",
)
```

### 3. 异步模式（生产推荐）

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
# 完成后服务端回调 webhook_v2
```

## 核心特性

- **文生视频（T2V）**：文本生成含音频的 MP4 视频（720p / 5秒 / 24fps）
- **图生视频（I2V）**：首帧 / 尾帧引导视频生成
- **参考图生视频（Ref2V）**：多参考图 / 视频 / 音频引导
- **同步 + 异步双模式**：同步直接返回结果，异步通过 webhook_v2 回调
- **零依赖 SDK**：Python 标准库实现，无需 pip install
- **存储后端支持**：S3 / Azure Blob / HuggingFace 输出上传

## 技术栈

- **模型**：MiniMax H3（FL2VA / Ref2VA，int8 量化）
- **CLIP**：Qwen3VL 32B（NVFP4 量化）
- **API 代理**：[comfyui-api](https://github.com/SaladTechnologies/comfyui-api) v1.17.1
- **运行时**：ComfyUI 0.31.0
- **GPU**：RTX 5090 32GB（PyTorch 2.13.0 + CUDA 13.0）
- **部署**：共绩算力弹性服务

## 实测性能

### 720p（1280×736，5 秒视频）

| 指标 | 数值 |
|------|------|
| 分辨率 | 1280×736（720p） |
| 帧数 | 124 帧（~5.2s @ 24fps） |
| 首次生成（含冷启动） | ~330 秒 |
| 缓存命中 | ~2.8 秒 |
| 输出文件 | MP4（~0.8–1.5MB）+ FLAC（~0.2MB） |
| 响应体大小 | ~2.3MB |

### 768p（1344×768，15 秒视频）

| 指标 | 数值 |
|------|------|
| 分辨率 | 1344×768（768p） |
| 帧数 | 362 帧（~15s @ 24fps） |
| 首次生成 | ~50 分钟 |
| GPU | RTX 5090 32GB |
| PyTorch | 2.13.0 + CUDA 13.0 |

> **注意**：由于共绩算力容器网关有 100 秒超时限制，768p/15s 必须使用异步模式（8188 端口提交 + 轮询 `/history`，或 3000 端口 + `webhook_v2` 回调）。同步调用会在 100 秒后断开连接，但 ComfyUI 仍会继续在后台执行。

## GPU 规格

| 指标 | 数值 |
|------|------|
| GPU | RTX 5090 32GB |
| PyTorch | 2.13.0 |
| CUDA | 13.0 |
| ComfyUI | 0.31.0 |
| API 代理 | comfyui-api v1.17.1 |

## 计费参考

共绩算力按 **GPU × 时长** 计费（精确到秒），弹性扩缩容：

| 计费项 | 说明 |
|------|------|
| 按卡时 | RTX 5090: 3.25 元/卡时 |
| 计费粒度 | 秒级 |
| SPOT 实例 | 约为按需价格的 40%（6 折优惠） |
| 并发模型 | 1 实例 = 1 GPU = 1 并发任务，弹性扩缩 |

## 文档目录

完整文档见 `MiniMax_H3_API_Doc.md`，包含：

1. 服务概览与端点列表
2. 工作流 JSON 定义（12 节点拓扑）
3. 全部请求参数（prompt / webhook_v2 / convert_output / credentials / S3 等）
4. 同步 + 异步调用示例（curl / Python / JavaScript）
5. Webhook 回调格式与签名验证
6. 图生视频 / 参考图生视频
7. 错误处理与注意事项
8. 提示词建议
9. Python SDK 使用说明

## License

MIT
