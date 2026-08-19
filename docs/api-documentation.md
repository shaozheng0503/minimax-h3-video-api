# MiniMax H3 视频生成 API 接入文档

## ComfyUI API · 端口 3000（API 调用）+ 端口 8188（可视化界面）

---

## 一、服务概览

### 调用方式

通过 ComfyUI 的 HTTP API 提交工作流 JSON，**一次 `POST /prompt` 请求同步返回结果**——无需轮询、无需 WebSocket，结果直接在 HTTP 响应体中。

### 基础信息

| 项目 | 说明 |
|------|------|
| API 接口地址 | `https://<你的服务地址>:3000` |
| 可视化界面 | `https://<你的服务地址>:8188`（浏览器打开即可查看 ComfyUI 界面） |
| 调用方式 | HTTP REST（同步 + 异步 webhook 两种模式） |
| 认证 | 无需认证，直接 HTTP 调用 |
| CORS | 已启用，浏览器端可直接调用 |
| 交互文档 | API 地址 + `/docs`（Swagger UI，浏览器打开即可在线测试） |
| ComfyUI 版本 | 0.31.0 |
| API 代理版本 | comfyui-api 1.17.1 |

### 30 秒验证

```bash
# 健康检查
curl -s "https://<你的服务地址>:3000/health"
# 返回: {"version":"1.17.1","status":"healthy"}

# 就绪检查
curl -s "https://<你的服务地址>:3000/ready"
# 返回: {"version":"1.17.1","status":"ready"}
```

> 也可以直接在浏览器打开 `https://<你的服务地址>:8188` 查看 ComfyUI 可视化界面。

### 参数速查

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| 分辨率 | 1280×736（720p） | 速度与画质平衡 |
| 帧数 | 124（~5秒） | 训练范围内，质量稳定 |
| 采样步数 | 4 | **turbo 档**（挂加速 LoRA），速度约为 20 步的 5 倍 |
| CFG | 1.0 | turbo 档不使用 CFG 引导 |
| 提示词 | 英文 | Qwen3VL 中英双语，英文更精准 |

> **两档质量任选**：
> - **turbo（默认推荐）**：4 步蒸馏 LoRA 加速，720p/5s 实测约 75 秒（RTX 5090）
> - **standard**：20 步原版无加速，画质上限略高，720p/5s 约 5-7 分钟
> - 使用随附 SDK 时传 `quality="turbo"` / `quality="standard"` 即可切换，LoRA 挂载与参数由 SDK 自动处理

### turbo 加速 LoRA（服务端已部署）

| LoRA 文件 | 适用模型 | 标定分辨率 |
|-----------|---------|-----------|
| `minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors` | fl2va（文生/图生视频） | 768p（短边 768） |
| `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` | ref2va（参考图生视频） | - |

---

## 二、API 端点

| 端点 | 方法 | 用途 | 说明 |
|------|------|------|------|
| `/health` | GET | 健康探针 | 热身完成后返回 200，运行期间持续返回 |
| `/ready` | GET | 就绪探针 | ComfyUI 运行且队列未满时返回 200，否则 503 |
| `/docs` | GET | Swagger 文档 | 浏览器打开可交互测试所有接口 |
| `/models` | GET | 列出可用模型 | 返回各类型模型列表 |
| `/prompt` | POST | **提交工作流** | 核心端点，同步返回结果或异步返回 202 |
| `/download` | POST | 触发模型下载 | 按 URL 下载模型到指定目录 |
| `/interrupt` | POST | 中断任务 | 按 ID 中断正在运行的任务 |

### `/ready` 返回 503 的场景

- ComfyUI 进程崩溃（正在自动重启）
- 队列深度达到 `MAX_QUEUE_DEPTH` 限制（非零值时）

### `/download` 端点

触发模型文件下载到 ComfyUI models 目录。

```bash
curl -s -X POST "https://<你的服务地址>:3000/download" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://huggingface.co/model.safetensors",
    "model_type": "checkpoints",
    "filename": "my-model.safetensors",
    "wait": false,
    "auth": {
      "type": "bearer",
      "token": "hf_xxxxxxxxxxxxx"
    }
  }'
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `url` | 是 | 模型下载 URL |
| `model_type` | 是 | 模型类型（checkpoints、loras、vae 等，对应 models 子目录） |
| `filename` | 否 | 覆盖文件名，默认取 URL basename |
| `wait` | 否 | `false`（默认）立即返回 202；`true` 等待完成返回 200 |
| `auth` | 否 | 访问受保护 URL 的认证凭据 |

**异步响应（`wait: false`）→ 202**：
```json
{"url": "...", "model_type": "checkpoints", "filename": "my-model.safetensors", "status": "started"}
```

**同步响应（`wait: true`）→ 200**：
```json
{"url": "...", "model_type": "checkpoints", "filename": "my-model.safetensors", "status": "completed", "size": 6938281472, "duration": 45.23}
```

---

## 三、可用模型

### 扩散模型（UNETLoader）

| 模型文件 | 用途 |
|----------|------|
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | 文生视频（FL2VA） |
| `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | 参考图生视频（Ref2VA） |

### CLIP 文本编码器（CLIPLoader）

| 模型文件 | 加载类型 |
|----------|---------|
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | `minimax` |

> Qwen3VL 32B，NVFP4 量化，用于文本理解与条件编码。

### VAE（VAELoader）

| 模型文件 | 用途 |
|----------|------|
| `minimax_h3_video_vae_fp16.safetensors` | 视频 VAE（FP16） |
| `minimax_h3_audio_vae_fp32.safetensors` | 音频 VAE（FP32） |

---

## 四、调用流程

```
客户端                                    服务端
  |                                         |
  |  POST /prompt (工作流 JSON)              |
  |  --------------------------->           |  (执行生成，约 1-10 分钟)
  |  <--- 200 {filenames, images, stats} -- |
  |                                         |
  |  结果直接在响应体中，无需轮询             |
  |                                         |
```

**一步到位**：构建工作流 JSON → `POST /prompt` → 解析响应拿结果。

### 同步 vs 异步（webhook）两种模式

| 模式 | 请求方式 | 响应 | 适用场景 |
|------|---------|------|---------|
| **同步** | `POST /prompt`（不带 `webhook_v2`） | HTTP 200，响应体直接包含结果 | 测试、客户端能长等待 |
| **异步（webhook）** | `POST /prompt`（带 `webhook_v2` URL） | HTTP 202，立即返回任务 ID，完成后回调 | **生产推荐**、避免超时、批量任务 |

> **重要**：实测同步请求 **193 秒**未被网关切断（720p/10s 档实测通过），但网关确有超时上限，而 1080p/15s 生成最高可达 25 分钟。同步模式仅建议用于 720p 以下、约 3 分钟内能完成的任务；**长任务生产环境必须用异步 webhook 模式**，避免连接被切后拿不到结果。

### 请求参数

```json
{
  "prompt": { ... },                          // 必填，工作流 JSON
  "id": "your-task-id",                      // 可选，自定义任务 ID（UUID 格式）
  "webhook_v2": "https://your-callback/url", // 可选，传入则走异步模式
  "convert_output": {                        // 可选，输出格式转换
    "format": "jpeg",                        // jpeg | jpg | webp（省略则默认 PNG）
    "options": { "quality": 80 }
  },
  "credentials": [ ... ],                    // 可选，访问受保护 URL 的凭据
  "s3": { ... },                             // 可选，输出上传到 S3
  "azure_blob_upload": { ... },              // 可选，输出上传到 Azure Blob
  "hf_upload": { ... }                       // 可选，输出上传到 HuggingFace
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `prompt` | object | 是 | ComfyUI 工作流 JSON（API 格式） |
| `id` | string | 否 | 自定义任务 ID（UUID 格式），不传则自动生成 |
| `webhook_v2` | string | 否 | 传入则切换为异步模式，返回 HTTP 202 |
| `convert_output` | object | 否 | 将输出转换为 JPEG/WebP 格式（省略则默认 PNG） |
| `credentials` | array | 否 | 访问受保护模型/资源 URL 的凭据列表 |
| `s3` | object | 否 | 输出上传到 S3 存储后端 |
| `azure_blob_upload` | object | 否 | 输出上传到 Azure Blob 存储 |
| `hf_upload` | object | 否 | 输出上传到 HuggingFace 仓库 |

> **注意**：使用 `webhook_v2`（推荐），不要用 `webhook`（旧版已弃用，行为不同——每个输出单独发一个请求且未签名）。

### convert_output 输出格式转换

省略 `convert_output` 时默认返回 **PNG** 格式（无损，质量最好，但体积最大）。

#### JPEG 选项

```json
"convert_output": {
  "format": "jpeg",
  "options": {
    "quality": 80,
    "progressive": false,
    "chromaSubsampling": "4:2:0",
    "optimizeCoding": true,
    "mozjpeg": false,
    "trellisQuantisation": false,
    "overshootDeringing": false,
    "optimizeScans": false
  }
}
```

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `quality` | number | 80 | 1-100，压缩质量 |
| `progressive` | boolean | false | 渐进式扫描 |
| `chromaSubsampling` | string | "4:2:0" | 设为 "4:4:4" 防止色度子采样 |
| `optimizeCoding` | boolean | true | 优化 Huffman 编码表 |
| `mozjpeg` | boolean | - | 使用 mozjpeg 默认值（更高压缩率） |
| `trellisQuantisation` | boolean | false | 网格量化 |
| `overshootDeringing` | boolean | false | 过冲去振铃 |
| `optimizeScans` | boolean | false | 优化扫描顺序 |

#### WebP 选项

```json
"convert_output": {
  "format": "webp",
  "options": {
    "quality": 80,
    "lossless": false,
    "nearLossless": false,
    "effort": 4,
    "preset": "default"
  }
}
```

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `quality` | number | 80 | 1-100 |
| `alphaQuality` | number | 100 | 0-100，透明度质量 |
| `lossless` | boolean | false | 无损压缩 |
| `nearLossless` | boolean | false | 近无损压缩 |
| `smartSubsample` | boolean | false | 智能子采样 |
| `preset` | string | "default" | default/picture/photo/drawing/icon/text |
| `effort` | number | 4 | 0(最快)-6(最慢) |

### credentials 凭据配置

`credentials` 是一个数组，每个条目通过 `url_pattern` 匹配 URL，并附加对应的认证信息。按数组顺序匹配，第一个匹配的 pattern 生效。

#### URL Pattern 通配符

- `*` — 匹配除 `/` 外的任何字符
- `**` — 匹配包括 `/` 在内的任何字符
- `?` — 匹配单个字符

示例：`https://huggingface.co/**` 匹配所有 HuggingFace URL

#### 5 种认证类型

**Bearer Token**（如 HuggingFace gated models）：
```json
{
  "url_pattern": "https://huggingface.co/**",
  "auth": {
    "type": "bearer",
    "token": "hf_xxxxxxxxxxxxx"
  }
}
```

**Basic Auth**：
```json
{
  "url_pattern": "https://*.example.com/**",
  "auth": {
    "type": "basic",
    "username": "user",
    "password": "pass"
  }
}
```

**Custom Header**（如 API keys）：
```json
{
  "url_pattern": "https://api.example.com/**",
  "auth": {
    "type": "header",
    "header_name": "X-API-Key",
    "header_value": "your-api-key"
  }
}
```

**Query Parameter**（如 Azure SAS tokens）：
```json
{
  "url_pattern": "https://*.blob.core.windows.net/**",
  "auth": {
    "type": "query",
    "query_param": "sig",
    "query_value": "your-sas-token"
  }
}
```

**S3 Credentials**（私有 S3 bucket）：
```json
{
  "url_pattern": "s3://my-bucket/**",
  "auth": {
    "type": "s3",
    "access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "session_token": "optional-sts-token",
    "region": "us-east-1",
    "endpoint": "https://s3.custom-endpoint.com"
  }
}
```

> `session_token`、`region`、`endpoint` 为可选字段。

### 存储后端上传（可选）

工作流完成后可将输出直接上传到外部存储，而非在响应中返回 base64。三个存储后端可选：

**S3 上传**：
```json
{
  "s3": {
    "bucket": "my-bucket",
    "prefix": "outputs/",
    "async": false
  }
}
```
配置后 `images` 字段返回 `s3://my-bucket/outputs/xxx.png` 而非 base64。

**Azure Blob 上传**：
```json
{
  "azure_blob_upload": {
    "container": "my-container",
    "blob_prefix": "outputs/",
    "async": false
  }
}
```
配置后 `images` 字段返回 `https://<account>.blob.core.windows.net/my-container/outputs/xxx.png`。

**HuggingFace 上传**：
```json
{
  "hf_upload": {
    "repo": "username/repo",
    "repo_type": "model",
    "revision": "main",
    "directory": "test-source-images",
    "async": false
  }
}
```

### 响应格式

#### 同步模式（HTTP 200）

> **实测验证**：以下响应格式已通过实际调用验证。

```json
{
  "id": "7c532124-fcfe-48c2-8eab-a92a671e5ae1",
  "prompt": { ... },
  "filenames": [
    "7c532124-_test_api2_00001.flac",
    "7c532124-_test_api2_00002_.mp4"
  ],
  "images": ["<base64编码数据>"],
  "stats": {
    "comfy_execution": {
      "start": 1786702508796,
      "end": 1786702933362,
      "duration": 424566,
      "nodes": {
        "8": {"start": 1786702508797},
        "9": {"start": 1786702918199}
      }
    },
    "preprocess_time": 0,
    "comfy_round_trip_time": 424585,
    "postprocess_time": 0,
    "upload_time": 0,
    "total_time": 424585
  }
}
```

> **注意**：
> - 同步响应**没有** `status` 字段（HTTP 200 即表示成功）
> - `stats` 中所有时间单位均为**毫秒**（`duration: 424566` = 424.6 秒 ≈ 7 分钟）
> - `comfy_execution.start/end` 为毫秒级 Unix 时间戳
> - `filenames` 会自动加上任务 ID 前缀（如 `7c532124-`）
> - `images` 为 base64 编码的文件数据（视频 + 音频各一个）

#### 异步模式提交响应（HTTP 202）

```json
{
  "id": "generated-uuid",
  "webhook_v2": "https://your-callback/url",
  "prompt": { ... }
}
```

#### 异步模式回调（服务端 POST 你的 webhook_v2 URL）

**成功回调（`prompt.complete`）**：

```json
{
  "type": "prompt.complete",
  "timestamp": "2026-08-14T09:50:00Z",
  "id": "task-xxx",
  "images": ["<base64编码数据>"],
  "filenames": ["output_00001_.mp4", "output_00001.flac"],
  "prompt": {},
  "stats": {
    "comfy_execution": {
      "total": { "start": 1234567890000, "end": 1234567977000, "duration": 87000 }
    },
    "preprocess_time": 1200,
    "total_time": 92300
  }
}
```

**失败回调（`prompt.failed`）**：

```json
{
  "type": "prompt.failed",
  "timestamp": "2026-08-14T09:50:00Z",
  "error": "error-message",
  "id": "task-xxx",
  "prompt": {}
}
```

> **Webhook 签名验证**：如果服务端配置了 `WEBHOOK_SECRET` 环境变量，回调请求会使用 [Standard Webhooks](https://www.standardwebhooks.com/) 规范签名。客户端可通过请求头 `webhook-id`、`webhook-timestamp`、`webhook-signature` 验证。未配置则无需验证。

#### Python 验证 Webhook 签名

SDK 已内置纯标准库实现（无需安装任何依赖）：

```python
from comfyui_minimax_h3_sdk import verify_webhook

payload = verify_webhook(body_bytes, dict(headers), SECRET)
# 验证通过返回解析后的 JSON；失败抛 ValueError（签名不符/时间戳过期）
```

等价的纯手写实现（HMAC-SHA256，Standard Webhooks 规范）：

```python
import base64, hashlib, hmac, json

def verify_webhook(body_bytes, headers, secret):
    to_sign = "{id}.{ts}.{body}".format(
        id=headers["webhook-id"],
        ts=headers["webhook-timestamp"],
        body=body_bytes.decode("utf-8"),
    )
    key = secret.removeprefix("whsec_").encode()
    expected = base64.b64encode(
        hmac.new(key, to_sign.encode(), hashlib.sha256).digest()
    ).decode()
    for sig in headers["webhook-signature"].split():
        if sig.startswith("v1,") and hmac.compare_digest(sig[3:], expected):
            return json.loads(body_bytes)
    raise ValueError("signature verification failed")
```

#### Node.js 验证 Webhook 签名

```javascript
const { Webhook } = require('svix');

function verifyWebhook(req, secret) {
  const webhook = new Webhook(secret);
  return webhook.verify(req.rawBody, req.headers); // 验证通过返回 payload
}
```

> `WEBHOOK_SECRET` 需在服务端环境变量中配置。未配置时回调不携带签名头，客户端无需验证。

#### stats 字段详解

同步响应和 `prompt.complete` 回调中的 `stats` 字段结构一致：

```json
"stats": {
  "comfy_execution": {
    "total": {
      "start": 1700000000000,   // 毫秒时间戳
      "end": 1700000005000,
      "duration": 5000           // 毫秒
    },
    "nodes": {
      "1": {"start": 1700000000000},
      "8": {"start": 1700000001000}
    }
  },
  "preprocess_time": 1500,    // 预处理耗时（毫秒）
  "upload_time": 1,           // 上传耗时（毫秒）
  "total_time": 6576          // 总耗时（毫秒）
}
```

> **时间单位**：`stats` 中所有时间均为**毫秒**（非秒）。`comfy_execution.total.start/end` 为毫秒级 Unix 时间戳。

---

## 五、工作流定义

### 文生视频工作流（T2V + 音频，turbo 加速档）

生成含音频的 MP4 视频，同步输出独立 FLAC 音频。默认走 **turbo 档**（4 步 + 加速 LoRA）。

#### 工作流 JSON（turbo，推荐）

```json
{
  "1": {
    "class_type": "UNETLoader",
    "inputs": {
      "unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
      "weight_dtype": "default"
    }
  },
  "15": {
    "class_type": "LoraLoaderModelOnly",
    "inputs": {
      "model": ["1", 0],
      "lora_name": "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors",
      "strength_model": 1.0
    }
  },
  "2": {
    "class_type": "CLIPLoader",
    "inputs": {
      "clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
      "type": "minimax"
    }
  },
  "3": {
    "class_type": "VAELoader",
    "inputs": {
      "vae_name": "minimax_h3_video_vae_fp16.safetensors"
    }
  },
  "4": {
    "class_type": "VAELoader",
    "inputs": {
      "vae_name": "minimax_h3_audio_vae_fp32.safetensors"
    }
  },
  "5": {
    "class_type": "MiniMaxH3SigmaShift",
    "inputs": {
      "model": ["15", 0],
      "shift_video": 12.0,
      "shift_audio": 3.0
    }
  },
  "6": {
    "class_type": "MiniMaxH3ImageToVideo",
    "inputs": {
      "clip": ["2", 0],
      "vae": ["3", 0],
      "prompt": "A ginger cat stretches lazily on a windowsill, sunlight filtering through white sheer curtains onto its fur, macro close-up, shallow depth of field, warm and cozy",
      "width": 1280,
      "height": 736,
      "length": 124
    }
  },
  "7": {
    "class_type": "ConditioningZeroOut",
    "inputs": {
      "conditioning": ["6", 0]
    }
  },
  "8": {
    "class_type": "KSampler",
    "inputs": {
      "model": ["5", 0],
      "seed": 0,
      "steps": 4,
      "cfg": 1.0,
      "sampler_name": "euler",
      "scheduler": "simple",
      "positive": ["6", 0],
      "negative": ["7", 0],
      "latent_image": ["6", 1],
      "denoise": 1.0
    }
  },
  "9": {
    "class_type": "VAEDecode",
    "inputs": {
      "samples": ["8", 0],
      "vae": ["3", 0]
    }
  },
  "10": {
    "class_type": "VAEDecodeAudio",
    "inputs": {
      "samples": ["8", 0],
      "vae": ["4", 0]
    }
  },
  "13": {
    "class_type": "CreateVideo",
    "inputs": {
      "images": ["9", 0],
      "fps": 24.0,
      "audio": ["10", 0]
    }
  },
  "11": {
    "class_type": "SaveVideo",
    "inputs": {
      "video": ["13", 0],
      "filename_prefix": "minimax_t2v",
      "format": "auto",
      "codec": "auto"
    }
  },
  "12": {
    "class_type": "SaveAudio",
    "inputs": {
      "audio": ["10", 0],
      "filename_prefix": "minimax_t2v"
    }
  }
}
```

> **与 standard 档的差异**只有三处：① 增加节点 15（LoraLoaderModelOnly 挂 turbo LoRA）；② 节点 5 的 model 改接 `["15", 0]`；③ 节点 8 的 `steps` 改 4、`cfg` 改 1.0。要切回 standard：删掉节点 15、节点 5 接回 `["1", 0]`、steps=20、cfg=7.0。

#### 节点说明

| 节点ID | class_type | 作用 |
|--------|-----------|------|
| 1 | UNETLoader | 加载 MiniMax H3 扩散模型 |
| 15 | LoraLoaderModelOnly | 挂载 4 步蒸馏加速 LoRA（turbo 档） |
| 2 | CLIPLoader | 加载 Qwen3VL 文本编码器 |
| 3 | VAELoader | 加载视频 VAE |
| 4 | VAELoader | 加载音频 VAE |
| 5 | MiniMaxH3SigmaShift | 设置视频/音频流的 sigma shift |
| 6 | MiniMaxH3ImageToVideo | 文本编码 + 生成空 Latent |
| 7 | ConditioningZeroOut | 生成负面条件（置零） |
| 8 | KSampler | 执行扩散采样（turbo: 4步/cfg=1.0；standard: 20步/cfg=7.0） |
| 9 | VAEDecode | 解码视频 Latent → IMAGE |
| 10 | VAEDecodeAudio | 解码音频 Latent → AUDIO |
| 13 | CreateVideo | IMAGE + AUDIO → VIDEO（关键中间节点） |
| 11 | SaveVideo | 保存 MP4 视频 |
| 12 | SaveAudio | 保存 FLAC 音频 |

> **重要**：`VAEDecode` 输出的是 `IMAGE` 类型，不能直接接 `SaveVideo`（需要 `VIDEO` 类型）。必须通过 `CreateVideo` 节点将 `IMAGE` + `AUDIO` 合成为 `VIDEO`。

#### 节点拓扑（turbo 档）

```
UNETLoader → LoraLoaderModelOnly(turbo) → MiniMaxH3SigmaShift → KSampler
CLIPLoader ──→ MiniMaxH3ImageToVideo ───┘ (positive + latent)
                    ↑
         VAELoader(video)
                    │
ConditioningZeroOut ─→ (negative)
                                        ↓
               KSampler ──→ VAEDecode ──→ CreateVideo ──→ SaveVideo (MP4)
                            │                ↑
                            └──→ VAEDecodeAudio ─┘
                                    ↑
                         VAELoader(audio)
                                    ↓
                              SaveAudio (FLAC)
```

---

## 六、参数说明

### 视频尺寸

宽高必须为 **32 的倍数**（模型约束）。

#### 推荐分辨率

| 分辨率等级 | 宽 × 高 | 像素数 | 说明 |
|-----------|---------|--------|------|
| 480p | 864 × 480 | 0.4M | 低画质，速度最快 |
| 720p | 1280 × 736 | 0.94M | 推荐日常使用 |
| 1080p | 1920 × 1088 | 2.09M | 高画质，耗时较长 |
| 原始默认 | 1344 × 768 | 1.03M | 模型默认分辨率 |

### 帧数与时长

帧数按 `17k+5` 网格对齐（模型内部约束），24 fps。

| length（帧数） | 时长 | 说明 |
|---------------|------|------|
| 124 | ~5.2s | 默认值，训练范围内（推荐） |
| 141 | ~5.9s | |
| 158 | ~6.6s | |
| 175 | ~7.3s | |
| 362 | ~15.1s | 训练范围上限 |

> 超过 362 帧为模型未训练范围，质量不保证。

### 采样参数

| 参数 | turbo 档（默认） | standard 档 | 说明 |
|------|----------------|------------|------|
| steps | 4 | 20 | 采样步数。turbo 靠蒸馏 LoRA 在 4 步内逼近 20 步质量 |
| cfg | 1.0 | 7.0 | CFG 引导强度。蒸馏模型不使用 CFG |
| lora | fl2v_turbo_4step_v1.0_768p | 无 | turbo 需挂载对应加速 LoRA（见第五节工作流） |
| sampler_name | euler | euler | 采样器，两档一致 |
| scheduler | simple | simple | 调度器，两档一致 |
| seed | 随机 | 随机 | 0 ~ 2^32-1 |
| denoise | 1.0 | 1.0 | 去噪强度，文生视频固定 1.0 |

> **实测耗时对比**（RTX 5090，720p / 124 帧）：
> - turbo：约 75 秒
> - standard：约 5-7 分钟（约 5 倍耗时）

### Sigma Shift 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| shift_video | 12.0 | 视频流噪声调度偏移 |
| shift_audio | 3.0 | 音频流噪声调度偏移 |

> 使用默认值即可，通常不需要调整。

---

## 七、快速开始

### 7.1 curl 调用

```bash
# 1. 健康检查
curl -s "https://<你的服务地址>:3000/health"
# 返回: {"version":"1.17.1","status":"healthy"}

# 2. 就绪检查
curl -s "https://<你的服务地址>:3000/ready"
# 返回: {"version":"1.17.1","status":"ready"}

# 3. 同步提交工作流（一次请求拿到结果，turbo 档 720p 约 1-2 分钟）
curl -s -X POST "https://<你的服务地址>:3000/prompt" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": {
      "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
      "15": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors", "strength_model": 1.0}},
      "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax"}},
      "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
      "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
      "5": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["15", 0], "shift_video": 12.0, "shift_audio": 3.0}},
      "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"clip": ["2", 0], "vae": ["3", 0], "prompt": "A cat playing piano", "width": 1280, "height": 736, "length": 124}},
      "7": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["6", 0]}},
      "8": {"class_type": "KSampler", "inputs": {"model": ["5", 0], "seed": 0, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["6", 1], "denoise": 1.0}},
      "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
      "10": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["8", 0], "vae": ["4", 0]}},
      "13": {"class_type": "CreateVideo", "inputs": {"images": ["9", 0], "fps": 24.0, "audio": ["10", 0]}},
      "11": {"class_type": "SaveVideo", "inputs": {"video": ["13", 0], "filename_prefix": "output", "format": "auto", "codec": "auto"}},
      "12": {"class_type": "SaveAudio", "inputs": {"audio": ["10", 0], "filename_prefix": "output"}}
    }
  }' --max-time 600
```

#### 响应格式（HTTP 200）

```json
{
  "id": "7c532124-fcfe-48c2-8eab-a92a671e5ae1",
  "filenames": ["xxx_test_api_00001.flac", "xxx_test_api_00002_.mp4"],
  "images": ["<base64编码数据>"],
  "stats": {
    "comfy_execution": {
      "start": 1786702508796,
      "end": 1786702933362,
      "duration": 424566
    },
    "total_time": 424585
  }
}
```

| 字段 | 说明 |
|------|------|
| `id` | 任务 ID（UUID 格式） |
| `filenames` | 生成的文件名列表（自动加任务 ID 前缀） |
| `images` | base64 编码的输出数据列表（视频 + 音频） |
| `stats.comfy_execution.duration` | 模型推理耗时（**毫秒**） |
| `stats.total_time` | 总耗时（**毫秒**） |

> **时间单位**：`stats` 中所有时间均为毫秒。如 `duration: 424566` = 424.6 秒 ≈ 7 分钟。

### 7.2 Python 调用

```python
import json, base64, os, urllib.request

BASE_URL = "https://<你的服务地址>:3000"

# 1. 构建工作流（turbo 加速档）
workflow = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
    "15": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors", "strength_model": 1.0}},
    "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax"}},
    "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
    "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
    "5": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["15", 0], "shift_video": 12.0, "shift_audio": 3.0}},
    "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"clip": ["2", 0], "vae": ["3", 0], "prompt": "A cat playing piano", "width": 1280, "height": 736, "length": 124}},
    "7": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["6", 0]}},
    "8": {"class_type": "KSampler", "inputs": {"model": ["5", 0], "seed": 0, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["6", 1], "denoise": 1.0}},
    "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
    "10": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["8", 0], "vae": ["4", 0]}},
    "13": {"class_type": "CreateVideo", "inputs": {"images": ["9", 0], "fps": 24.0, "audio": ["10", 0]}},
    "11": {"class_type": "SaveVideo", "inputs": {"video": ["13", 0], "filename_prefix": "output", "format": "auto", "codec": "auto"}},
    "12": {"class_type": "SaveAudio", "inputs": {"audio": ["10", 0], "filename_prefix": "output"}},
}

# 2. 同步调用 — 一次请求直接拿到结果
data = json.dumps({"prompt": workflow}).encode("utf-8")
req = urllib.request.Request(
    BASE_URL + "/prompt",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=600) as r:
    result = json.loads(r.read())

print("状态: %s" % result.get("status", "ok"))  # 同步模式可能没有 status 字段
print("文件: %s" % result.get("filenames"))
stats = result.get("stats", {})
# 注意：stats 中时间单位为毫秒，需除以 1000 转换为秒
duration_ms = stats.get("comfy_execution", {}).get("duration", 0)
total_ms = stats.get("total_time", 0)
print("生成耗时: %.1fs" % (duration_ms / 1000))
print("总耗时: %.1fs" % (total_ms / 1000))

# 3. 保存输出文件（images 字段为 base64 编码）
os.makedirs("./output", exist_ok=True)
for i, img_data in enumerate(result.get("images", [])):
    if isinstance(img_data, str) and len(img_data) > 100:
        raw = base64.b64decode(img_data)
        # 根据文件头判断格式
        if raw[:4] == b'\x89PNG':
            ext = "png"
        elif raw[:3] == b'\xff\xd8\xff':
            ext = "jpg"
        elif raw[:4] == b'fLaC':
            ext = "flac"
        elif raw[4:8] == b'ftyp':
            ext = "mp4"
        else:
            ext = "bin"
        path = "./output/output_%03d.%s" % (i, ext)
        with open(path, "wb") as f:
            f.write(raw)
        print("已保存: %s (%.2f MB)" % (path, len(raw) / 1024 / 1024))
```

### 7.3 JavaScript / 浏览器调用

```javascript
const BASE_URL = "https://<你的服务地址>:3000";

const workflow = {
  "1": { class_type: "UNETLoader", inputs: { unet_name: "minimax_h3_fl2va_pruned_int8_convrot.safetensors", weight_dtype: "default" } },
  "15": { class_type: "LoraLoaderModelOnly", inputs: { model: ["1", 0], lora_name: "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors", strength_model: 1.0 } },
  "2": { class_type: "CLIPLoader", inputs: { clip_name: "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", type: "minimax" } },
  "3": { class_type: "VAELoader", inputs: { vae_name: "minimax_h3_video_vae_fp16.safetensors" } },
  "4": { class_type: "VAELoader", inputs: { vae_name: "minimax_h3_audio_vae_fp32.safetensors" } },
  "5": { class_type: "MiniMaxH3SigmaShift", inputs: { model: ["15", 0], shift_video: 12.0, shift_audio: 3.0 } },
  "6": { class_type: "MiniMaxH3ImageToVideo", inputs: { clip: ["2", 0], vae: ["3", 0], prompt: "A cat playing piano", width: 1280, height: 736, length: 124 } },
  "7": { class_type: "ConditioningZeroOut", inputs: { conditioning: ["6", 0] } },
  "8": { class_type: "KSampler", inputs: { model: ["5", 0], seed: 0, steps: 4, cfg: 1.0, sampler_name: "euler", scheduler: "simple", positive: ["6", 0], negative: ["7", 0], latent_image: ["6", 1], denoise: 1.0 } },
  "9": { class_type: "VAEDecode", inputs: { samples: ["8", 0], vae: ["3", 0] } },
  "10": { class_type: "VAEDecodeAudio", inputs: { samples: ["8", 0], vae: ["4", 0] } },
  "13": { class_type: "CreateVideo", inputs: { images: ["9", 0], fps: 24.0, audio: ["10", 0] } },
  "11": { class_type: "SaveVideo", inputs: { video: ["13", 0], filename_prefix: "output", format: "auto", codec: "auto" } },
  "12": { class_type: "SaveAudio", inputs: { audio: ["10", 0], filename_prefix: "output" } },
};

// 同步调用 — 一次请求拿到结果
const resp = await fetch(`${BASE_URL}/prompt`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ prompt: workflow }),
});
const result = await resp.json();

console.log("状态:", result.status || "ok");
console.log("文件:", result.filenames);
// 注意：stats 中时间单位为毫秒
console.log("推理耗时:", (result.stats?.comfy_execution?.duration || 0) / 1000, "s");

// 保存输出（base64 → Blob → 下载）
result.images?.forEach((base64Data, i) => {
  if (typeof base64Data === "string" && base64Data.length > 100) {
    const byteChars = atob(base64Data);
    const bytes = new Uint8Array(byteChars.length);
    for (let j = 0; j < byteChars.length; j++) bytes[j] = byteChars.charCodeAt(j);
    const blob = new Blob([bytes]);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `output_${i}.mp4`;
    a.click();
  }
});
```

### 7.4 异步模式（Webhook 回调 — 生产推荐）

网关确有超时上限（实测 193 秒内同步可用），而 1080p/15s 视频生成最高可达 25 分钟，同步连接无法覆盖全部档位。**生产环境推荐异步 webhook 模式**：提交后立即返回（HTTP 202），结果完成后服务端回调你的接口。

#### 调用流程

```
客户端                                        服务端
  |                                           |
  |  POST /prompt {prompt, webhook_v2: URL}   |
  |  ---------------------------->           |
  |  <--- 202 {id, webhook_v2} --------------|  (立即返回，不等执行)
  |                                           |
  |    ... 客户端可以去做别的事 ...             |  (服务端执行生成，2-10 分钟)
  |                                           |
  |  <--- POST your-webhook_v2-url ----------|  (生成完成，回调通知)
  |       {type: "prompt.complete", id, images, filenames, stats}
  |                                           |
  |  或：                                      |
  |  <--- POST your-webhook_v2-url ----------|  (生成失败，回调通知)
  |       {type: "prompt.failed", id, error}
  |                                           |
```

#### 提交异步任务（Python）

```python
import json, urllib.request

BASE_URL = "https://<你的服务地址>:3000"
CALLBACK_URL = "https://your-server.com/api/minimax/callback"

workflow = {
    # ... 完整工作流 JSON（同第五节）
}

payload = {
    "prompt": workflow,
    "webhook_v2": CALLBACK_URL,   # 注意：用 webhook_v2，不是 webhook
    "id": "my-task-001",          # 可选，自定义任务 ID
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    BASE_URL + "/prompt",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as r:
    result = json.loads(r.read())

# 立即返回 202
print("状态码: %d" % r.status)      # 202
print("任务ID: %s" % result.get("id"))
print("webhook: %s" % result.get("webhook_v2"))
# 此时任务已提交，等回调通知
```

#### 接收回调（Python Flask 示例）

```python
from flask import Flask, request, jsonify
import base64, os

app = Flask(__name__)

@app.route("/api/minimax/callback", methods=["POST"])
def handle_callback():
    data = request.get_json()

    # 根据 type 字段判断回调类型
    callback_type = data.get("type")
    task_id = data.get("id")

    if callback_type == "prompt.complete":
        # 生成成功
        filenames = data.get("filenames", [])
        images = data.get("images", [])
        stats = data.get("stats", {})
        # stats 中时间单位为毫秒
        duration_ms = stats.get("comfy_execution", {}).get("total", {}).get("duration", 0)

        print(f"任务 {task_id} 生成成功")
        print(f"文件: {filenames}")
        print(f"推理耗时: {duration_ms / 1000:.1f}s")

        # 保存输出文件（images 为 base64 编码）
        os.makedirs("./output", exist_ok=True)
        for i, img_data in enumerate(images):
            if isinstance(img_data, str) and len(img_data) > 100:
                raw = base64.b64decode(img_data)
                # 根据文件头判断格式
                if raw[:4] == b'\x89PNG':
                    ext = "png"
                elif raw[:3] == b'\xff\xd8\xff':
                    ext = "jpg"
                elif raw[:4] == b'fLaC':
                    ext = "flac"
                elif raw[4:8] == b'ftyp':
                    ext = "mp4"
                else:
                    ext = "bin"
                path = f"./output/{task_id}_{i}.{ext}"
                with open(path, "wb") as f:
                    f.write(raw)
                print(f"已保存: {path}")

    elif callback_type == "prompt.failed":
        # 生成失败
        error = data.get("error")
        print(f"任务 {task_id} 生成失败: {error}")

    return jsonify({"received": True}), 200
```

#### 提交异步任务（curl）

```bash
curl -s -X POST "https://<你的服务地址>:3000/prompt" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": { ... },
    "webhook_v2": "https://your-server.com/api/minimax/callback",
    "id": "my-task-001"
  }'
# 返回 (HTTP 202): {"id":"my-task-001","webhook_v2":"https://...","prompt":{...}}
```

### 7.5 同步超时降级策略

如果不想搭 webhook 服务端，又担心同步连接超时，可以用这个策略：

```python
import json, time, urllib.request, urllib.error

BASE_URL = "https://<你的服务地址>:3000"

def generate_with_fallback(workflow, timeout=600, retries=3):
    """
    同步调用，超时/503 自动重试
    """
    payload = {"prompt": workflow}
    body = json.dumps(payload).encode("utf-8")

    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                BASE_URL + "/prompt",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 503 and attempt < retries - 1:
                print("503，服务扩缩容中，10 秒后重试...")
                time.sleep(10)
                continue
            raise
        except Exception as e:
            if attempt < retries - 1:
                print("超时/错误，10 秒后重试: %s" % e)
                time.sleep(10)
                continue
            raise
```

> **注意**：同步模式下如果连接超时，任务可能还在服务端执行，但客户端拿不到结果。如果超时频繁发生，请切换为异步 webhook 模式。

---

## 八、图生视频（I2V）

支持首帧（first_frame）和尾帧（last_frame）输入。

> 图生视频需要先上传图片到 ComfyUI 输入目录（使用 8188 端口的 `/upload/image` 接口），然后在工作流中引用。

### 工作流修改

在节点 6（MiniMaxH3ImageToVideo）中添加可选输入：

```json
"6": {
  "class_type": "MiniMaxH3ImageToVideo",
  "inputs": {
    "clip": ["2", 0],
    "vae": ["3", 0],
    "prompt": "Camera slowly zooms in",
    "width": 1280,
    "height": 736,
    "length": 124,
    "first_frame": ["14", 0]
  }
},
"14": {
  "class_type": "LoadImage",
  "inputs": {
    "image": "image.jpg",
    "upload": "image"
  }
}
```

> 注意：使用图生视频时，节点编号需重新编排避免冲突。

---

## 九、参考图生视频（Ref2V）

使用 `minimax_h3_ref2va_pruned_int8_convrot.safetensors` 模型 + `MiniMaxH3ReferenceToVideo` 节点。

| 特性 | 说明 |
|------|------|
| 参考图片 | 最多 9 张 |
| 参考视频 | 最多 3 段（24fps，2-15s） |
| 参考音频 | 最多 3 段 |
| ref_image_size | `match`（匹配输出分辨率）或 `max`（2048px 短边，精度更高但更慢） |

在 prompt 中使用 `<Picture 1>` / `<Video 1>` / `<Audio 1>` 标签引用对应的参考素材。

---

## 十、注意事项

### 10.1 冷启动与执行缓存

首次请求（或服务重启后）需要将模型加载到 GPU 显存：
- UNET（int8 量化）：约 10-15 GB
- CLIP（Qwen3VL 32B NVFP4）：约 16 GB
- 视频 VAE + 音频 VAE：约 2 GB
- **总计约 28-33 GB**

冷启动耗时约 1-5 分钟（turbo 档首次提交会多一步 LoRA 加载，开销可忽略），之后单次生成视分辨率而定：
- **turbo 档**：720p/5s 约 75 秒；480p/5s 约 38 秒；1080p/15s 约 25 分钟
- **standard 档**：约为 turbo 的 5 倍耗时

**执行缓存（Execution Cache）**：ComfyUI 会自动缓存已执行节点的结果。如果连续提交相同参数的工作流（相同 seed、prompt、尺寸），后续请求可能直接命中缓存，返回时间可降至 **2-3 秒**。

> 实测：首次提交 720p/124帧 turbo 工作流耗时约 75-90 秒（含冷启动），后续相同参数提交仅 1-3 秒（缓存命中）。更换 seed 或 prompt 后恢复正常推理耗时。

如需避免缓存影响（每次都重新生成），请在每次请求中使用不同的 `seed` 值。

### 10.2 503 错误处理

弹性服务在扩缩容时可能返回 HTTP 503。客户端应实现自动重试：

```python
import time, urllib.request

def request_with_retry(url, data, max_retries=5, delay=3):
    for i in range(max_retries):
        try:
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            return urllib.request.urlopen(req, timeout=600).read()
        except Exception:
            if i < max_retries - 1:
                time.sleep(delay)
            else:
                raise
```

### 10.3 宽高对齐

`width` 和 `height` 必须是 32 的倍数。如果传入非对齐值，ComfyUI 会自动向上取整。

### 10.4 超时设置

网关同步连接实测 **193 秒内可用**（720p/10s 档实测通过），1080p 长任务最高可达 25 分钟。

| 模式 | 超时行为 | 建议 |
|------|---------|------|
| 异步 webhook 模式 | 提交只需几秒，不受影响 | **生产必选** |
| 同步模式 | 长任务可能被网关切断 | 用于 ≤720p/10s 或测试；更长任务走异步 |

> **同步模式超时是必然的**——不是因为生成慢，而是网关限制。生产环境请用异步 webhook_v2 模式（见 7.4 节）。

### 10.5 并发限制

每个服务实例同一时间只处理 1 个任务。提交多个任务时会排队。如需并发，请部署多个实例或使用负载均衡。

队列深度由 `MAX_QUEUE_DEPTH` 环境变量控制（默认 0 = 无限制）。达到限制时 `/ready` 返回 503。

### 10.6 请求体大小限制

默认最大请求体 100 MB（`MAX_BODY_SIZE_MB` 环境变量）。如果工作流包含大量 base64 编码的输入图片，注意不要超过此限制。

### 10.7 Webhook 重试机制

异步模式的 webhook 回调失败时（非 2xx 响应），服务端会自动重试，最多 3 次（`PROMPT_WEBHOOK_RETRIES` 环境变量，默认 3）。客户端的回调端点应做到幂等——即多次收到同一回调不会产生副作用。

### 10.8 中断任务

如果需要中断正在运行的任务：

```bash
curl -s -X POST "https://<你的服务地址>:3000/interrupt" \
  -H "Content-Type: application/json" \
  -d '{"id": "<任务ID>"}'
```

### 10.9 系统事件监听（可选）

除了任务级别的 `prompt.complete` / `prompt.failed` 回调，服务端还支持**系统事件 webhook**（需配置 `SYSTEM_WEBHOOK_URL` 和 `SYSTEM_WEBHOOK_EVENTS` 环境变量）。系统事件可用于进度监控、执行追踪等场景。

| 事件名 | 说明 |
|--------|------|
| `status` | ComfyUI 状态 |
| `progress` | 进度更新（value/max/node） |
| `progress_state` | 前端聚合进度（v1.14.0+） |
| `executing` | 节点执行中 |
| `execution_start` | 执行开始 |
| `execution_cached` | 缓存命中 |
| `executed` | 节点执行完成 |
| `execution_success` | 执行成功 |
| `execution_interrupted` | 执行被中断 |
| `execution_error` | 执行错误（含 traceback） |
| `file_downloaded` | 文件下载完成 |
| `file_uploaded` | 文件上传完成 |
| `file_deleted` | 文件删除 |

系统事件格式统一为：

```json
{
  "type": "progress",
  "data": {
    "value": 45,
    "max": 100,
    "prompt_id": "task-xxx",
    "node": "8"
  },
  "sid": "session-id"
}
```

**执行错误事件（`execution_error`）**包含详细错误信息：

```json
{
  "type": "execution_error",
  "data": {
    "prompt_id": "task-xxx",
    "node_id": "8",
    "node_type": "KSampler",
    "executed": [],
    "exception_message": "CUDA out of memory. Tried to allocate 2.20 GiB",
    "exception_type": "RuntimeError",
    "traceback": "Traceback (most recent call last):\n  ...",
    "current_inputs": {"seed": 42, "steps": 20, "cfg": 7.0},
    "current_outputs": []
  },
  "sid": "session-id"
}
```

> 通过 `execution_error` 系统事件可获取完整的 traceback 和出错节点的输入参数，便于调试。

---

## 十一、提示词建议

### 推荐提示词结构

```
[主体描述] + [动作/运动] + [镜头语言] + [光线/氛围] + [画质关键词]
```

### 示例提示词

| 场景 | 提示词 |
|------|--------|
| 动物特写 | A ginger cat stretches lazily on a windowsill, sunlight filtering through white sheer curtains onto its fur, macro close-up, shallow depth of field, warm and cozy |
| 科幻都市 | Futuristic city with busy aerial traffic, flying cars weaving between skyscrapers, holographic ads flickering in the air, fast lateral camera movement, cyberpunk style, futuristic |
| 美食饮品 | Milk being poured into a cup of hot coffee, foam forming a slow swirling vortex, slow motion close-up, warm lighting, commercial advertising quality, ultra HD |
| 人物情感 | A girl runs through a golden wheat field, wind blowing her hair and white dress, backlit by sunset, slow motion, dreamy cinematic feel |

### 提示词技巧

1. **英文效果更好**：MiniMax H3 的 CLIP 基于 Qwen3VL，中英双语但英文理解更精准
2. **明确镜头运动**：slow motion, close-up, aerial shot, lateral movement
3. **指定氛围**：cinematic, warm lighting, dreamy, cozy
4. **控制时长**：5 秒短视频描述一个完整动作即可，不要过于复杂

---

## 十二、Python SDK

随附文件 `comfyui_minimax_h3_sdk.py` 提供封装好的 SDK，零依赖（仅标准库）。

### 使用方法

```python
from comfyui_minimax_h3_sdk import generate_video

# 一行代码生成视频（默认 turbo 加速档，720p/5s 约 1-2 分钟）
files = generate_video(
    "A cat playing piano in a jazz club",
    base_url="https://<你的服务地址>:3000",
    width=1280,
    height=736,
    length=124,
    save_dir="./output",
)

# 高画质档（20 步原版，约 5-7 分钟）
files = generate_video(
    "A cat playing piano in a jazz club",
    base_url="https://<你的服务地址>:3000",
    quality="standard",
)
```

### 高级用法

```python
from comfyui_minimax_h3_sdk import ComfyUI, build_t2v_workflow

client = ComfyUI("https://<你的服务地址>:3000")

# 健康检查
print(client.health())

# 构建工作流（quality 可选 "turbo" / "standard"，默认 turbo）
workflow = build_t2v_workflow(
    prompt_text="A cat playing piano in a jazz club",
    width=1280,
    height=736,
    length=124,
    quality="turbo",      # turbo: 4步+LoRA加速 / standard: 20步原版
    # steps=4, cfg=1.0,   # 可显式覆盖，默认按 quality 档自动
    seed=42,
)

# === 同步模式 ===
result = client.sync_generate(workflow, timeout=600)
print("任务ID:", result.get("id"))
print("文件:", result.get("filenames"))
# stats 时间单位为毫秒，需除以 1000 转秒
stats = result.get("stats", {})
dur_ms = stats.get("comfy_execution", {}).get("duration", 0)
print("推理耗时: %.1fs" % (dur_ms / 1000))
files = client.save_sync_outputs(result, save_dir="./output")

# === 异步模式（webhook_v2，生产推荐）===
result = client.async_submit(
    workflow,
    webhook_url="https://your-server.com/api/callback",
    task_id="my-task-001",
)
print("任务已提交:", result["id"])
# 完成后服务端回调 webhook_v2 URL，格式:
#   成功: {"type": "prompt.complete", "id": ..., "images": [...], "filenames": [...], "stats": {...}}
#   失败: {"type": "prompt.failed", "id": ..., "error": "..."}
```

---

## 附录：API 响应格式

### POST /prompt 成功响应（实测验证）

```json
{
  "id": "7c532124-fcfe-48c2-8eab-a92a671e5ae1",
  "filenames": ["7c532124-_test_api_00001.flac", "7c532124-_test_api_00002_.mp4"],
  "images": ["<base64编码数据>"],
  "stats": {
    "comfy_execution": {
      "start": 1786702508796,
      "end": 1786702933362,
      "duration": 424566,
      "nodes": {"8": {"start": 1786702508797}}
    },
    "preprocess_time": 0,
    "comfy_round_trip_time": 424585,
    "postprocess_time": 0,
    "upload_time": 0,
    "total_time": 424585
  }
}
```

> 实测数据（turbo 档）：720p / 124 帧 / 4 steps，推理耗时约 75 秒；standard 档（20 steps）约 424 秒（7 分钟）。响应体约 2.3MB。

### 错误响应

| HTTP 状态码 | 含义 | 处理方式 |
|-------------|------|---------|
| 400 | 工作流格式错误 | 检查 JSON 结构和节点 class_type |
| 413 | 请求体超过 `MAX_BODY_SIZE_MB`（默认 100MB） | 减少输入数据体积 |
| 422 | 节点参数校验失败 | 检查节点 inputs，查看响应中的错误详情 |
| 500 | 服务内部错误 | 查看响应 message 字段，联系运维 |
| 503 | 服务扩缩容中 / 队列满 | 等待 3 秒后重试（见 10.2） |

### ComfyUI 官方 API v2 参考

本服务使用的是 [comfyui-api](https://github.com/SaladTechnologies/comfyui-api)（端口 3000 的同步/异步代理层），**不是** ComfyUI 官方 API v2。如需了解 ComfyUI 官方云端 API v2（用于 ComfyUI Cloud），其差异如下：

| 特性 | comfyui-api（本服务） | ComfyUI API v2（官方云） |
|------|----------------------|------------------------|
| 端口 | 3000 | HTTPS API |
| 认证 | 无需认证 / HTTP 头 | Bearer Token |
| 提交方式 | `POST /prompt` | `POST /jobs` |
| 幂等性 | 自定义 `id` | `Idempotency-Key`（单次使用，24h 过期） |
| 任务状态 | 同步返回或 webhook 回调 | queued → running → succeeded/failed/expired |
| 进度监控 | 系统事件 webhook（可选） | SSE 流式 + 轮询 GET |
| 资产引用 | 工作流内 base64 / 文件名 | content-addressed assets |

> 本文档仅适用于 comfyui-api（端口 3000）。ComfyUI API v2 的完整文档见 [docs.comfy.org](https://docs.comfy.org/api-reference/v2/jobs/submit-a-workflow-for-execution)。
