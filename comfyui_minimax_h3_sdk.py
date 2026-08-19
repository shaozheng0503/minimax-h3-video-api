#!/usr/bin/env python3
"""
MiniMax H3 ComfyUI API SDK

依赖: Python 3.8+ (仅使用标准库，无需安装第三方包)

支持两种调用模式:
  1. 同步模式（默认）: POST /prompt 直接等结果返回，2-10 分钟
  2. 异步模式（webhook）: POST /prompt 带 webhook，立即返回任务 ID，完成后回调

使用示例 — 同步模式:
    from comfyui_minimax_h3_sdk import generate_video
    files = generate_video("A cat playing piano", base_url="https://your-service:3000")

使用示例 — 异步模式（生产推荐）:
    from comfyui_minimax_h3_sdk import ComfyUI, build_t2v_workflow
    client = ComfyUI("https://your-service:3000")
    workflow = build_t2v_workflow(prompt_text="A cat playing piano")
    result = client.async_submit(workflow, webhook_url="https://your-server.com/callback")
    print("任务已提交:", result["id"])
    # ...完成后服务端回调 webhook_v2，格式:
    #   成功: {"type": "prompt.complete", "id": ..., "images": [...], "filenames": [...], "stats": {...}}
    #   失败: {"type": "prompt.failed", "id": ..., "error": "..."}
"""

import json
import time
import random
import urllib.request
import urllib.parse
import urllib.error
import os
import base64


# ============================================================
# ComfyUI HTTP API 客户端
# ============================================================
class ComfyUI:
    """ComfyUI HTTP API 客户端，支持端口 8188（异步）和端口 3000（同步）"""

    def __init__(self, base_url):
        self.url = base_url.rstrip("/")

    # ----------------------------------------------------------
    # 内部 HTTP 工具
    # ----------------------------------------------------------
    def _get(self, path, timeout=20, retries=5):
        for attempt in range(retries):
            try:
                req = urllib.request.Request(self.url + path)
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                if e.code == 503 and attempt < retries - 1:
                    time.sleep(2)
                    continue
                raise
            except Exception:
                if attempt < retries - 1:
                    time.sleep(2)
                else:
                    raise

    def _post(self, path, data, timeout=30, retries=5):
        body = json.dumps(data).encode("utf-8")
        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    self.url + path,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                if e.code == 503 and attempt < retries - 1:
                    time.sleep(2)
                    continue
                raise
            except Exception:
                if attempt < retries - 1:
                    time.sleep(2)
                else:
                    raise

    def _post_raw(self, path, data, timeout=600, retries=8):
        """POST 请求，返回 (status_code, body_dict)，用于同步模式"""
        body = json.dumps(data).encode("utf-8")
        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    self.url + path,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    raw = r.read()
                    return r.status, json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                raw = b""
                try:
                    raw = e.read()
                except Exception:
                    pass
                if e.code == 503 and attempt < retries - 1:
                    time.sleep(3)
                    continue
                if e.code == 202:
                    # 异步模式返回 202
                    try:
                        return 202, json.loads(raw) if raw else {}
                    except Exception:
                        return 202, {}
                raise
            except Exception:
                if attempt < retries - 1:
                    time.sleep(3)
                else:
                    raise

    # ----------------------------------------------------------
    # 端口 3000 专用方法（同步模式）
    # ----------------------------------------------------------
    def health(self):
        """
        健康探针（端口 3000 专用）
        返回: {"version": "1.17.1", "status": "healthy"}
        """
        return self._get("/health", timeout=10)

    def ready(self):
        """
        就绪探针（端口 3000 专用）
        返回: {"version": "1.17.1", "status": "ready"}
        队列满时返回 503
        """
        return self._get("/ready", timeout=10)

    def get_models(self):
        """
        列出可用模型（端口 3000 / 8188 均可）
        """
        return self._get("/models", timeout=15)

    def sync_generate(self, workflow, convert_output=None,
                      timeout=600, credentials=None,
                      s3=None, azure_blob_upload=None, hf_upload=None):
        """
        同步生成 — 一次请求拿到结果，无需轮询

        参数:
            workflow:           工作流 JSON 对象
            convert_output:     {"format": "jpeg"/"webp", "options": {...}}
                                省略则默认 PNG
            timeout:            HTTP 超时秒数（视频生成通常需要 2-10 分钟）
            credentials:        认证凭据列表 [{"url_pattern": ..., "auth": {...}}]
            s3:                 S3 上传配置 {"bucket": ..., "prefix": ..., "async": false}
            azure_blob_upload:  Azure Blob 上传配置
            hf_upload:          HuggingFace 上传配置

        返回:
            dict，包含以下字段:
              - id:         任务 ID
              - status:     "ok"
              - filenames:  生成的文件名列表
              - images:     图片/视频数据列表（base64 或存储 URL）
              - stats:      执行统计

        异常:
            TimeoutError:    超时
            RuntimeError:    服务端错误
        """
        payload = {"prompt": workflow}
        if convert_output:
            payload["convert_output"] = convert_output
        if credentials:
            payload["credentials"] = credentials
        if s3:
            payload["s3"] = s3
        if azure_blob_upload:
            payload["azure_blob_upload"] = azure_blob_upload
        if hf_upload:
            payload["hf_upload"] = hf_upload

        status, body = self._post_raw("/prompt", payload, timeout=timeout)

        if status == 202:
            raise RuntimeError(
                "服务返回 202（异步模式）。如需同步调用，请勿设置 webhook 参数。"
                "异步任务 ID: %s" % body.get("id", "")
            )
        if status != 200:
            raise RuntimeError("服务返回错误 %d: %s" % (status, body))

        return body

    def async_submit(self, workflow, webhook_url, task_id=None,
                     convert_output=None, credentials=None,
                     s3=None, azure_blob_upload=None, hf_upload=None):
        """
        异步提交 — 立即返回任务 ID，结果完成后回调 webhook_v2

        参数:
            workflow:           工作流 JSON 对象
            webhook_url:        你的回调 URL，任务完成后服务端会 POST 通知
            task_id:            可选，自定义任务 ID（UUID 格式）
            convert_output:     {"format": "jpeg"/"webp", "options": {...}}
            credentials:        认证凭据列表
            s3:                 S3 上传配置
            azure_blob_upload:  Azure Blob 上传配置
            hf_upload:          HuggingFace 上传配置

        返回:
            dict，包含:
              - id:         任务 ID
              - webhook_v2: 回调 URL
              - prompt:     工作流回显

        回调格式:
            成功: {"type": "prompt.complete", "id": ..., "images": [...], "filenames": [...], "stats": {...}}
            失败: {"type": "prompt.failed", "id": ..., "error": "..."}

        Webhook 签名:
            如服务端配置了 WEBHOOK_SECRET，回调头会包含:
              webhook-id, webhook-timestamp, webhook-signature
            可用 svix 库验证:
              from svix import Webhook
              Webhook(secret).verify(body_bytes, dict(headers))
        """
        payload = {"prompt": workflow, "webhook_v2": webhook_url}
        if task_id:
            payload["id"] = task_id
        if convert_output:
            payload["convert_output"] = convert_output
        if credentials:
            payload["credentials"] = credentials
        if s3:
            payload["s3"] = s3
        if azure_blob_upload:
            payload["azure_blob_upload"] = azure_blob_upload
        if hf_upload:
            payload["hf_upload"] = hf_upload

        status, body = self._post_raw("/prompt", payload, timeout=30)

        if status == 200:
            # 服务端直接同步返回了（任务很快完成）
            return body
        if status == 202:
            return body
        if status != 200 and status != 202:
            raise RuntimeError("服务返回错误 %d: %s" % (status, body))

        return body

    def interrupt(self, task_id):
        """
        中断正在运行的任务（端口 3000 专用）

        参数:
            task_id: 要中断的任务 ID

        返回:
            {"id": "...", "interrupted": "success" 或 "failed"}
        """
        return self._post("/interrupt", {"id": task_id}, timeout=15)

    def download_model(self, url, model_type, filename=None,
                       wait=False, auth=None):
        """
        触发模型文件下载到 ComfyUI models 目录（端口 3000 专用）

        参数:
            url:        模型下载 URL
            model_type: 模型类型（checkpoints, loras, vae 等）
            filename:   覆盖文件名（可选）
            wait:       True 等待完成返回 200，False 立即返回 202
            auth:       认证凭据 dict（如 {"type": "bearer", "token": "..."}）

        返回:
            dict，包含 status, filename, url 等字段
        """
        payload = {"url": url, "model_type": model_type, "wait": wait}
        if filename:
            payload["filename"] = filename
        if auth:
            payload["auth"] = auth

        return self._post("/download", payload, timeout=600 if wait else 30)

    def save_sync_outputs(self, sync_result, save_dir="./output"):
        """
        从同步调用结果中提取并保存输出文件

        支持三种输出格式:
          1. base64 编码数据（默认 PNG，或 convert_output 指定的 JPEG/WebP）
          2. S3 URL（如 s3://bucket/prefix/file.png）
          3. Azure Blob URL（如 https://account.blob.core.windows.net/...）
          4. HuggingFace URL

        参数:
            sync_result: sync_generate() 返回的 dict
            save_dir:    本地保存目录

        返回:
            下载的文件列表 [{"path": ..., "type": ..., "size_mb": ...}]
        """
        os.makedirs(save_dir, exist_ok=True)
        downloaded = []

        # 1. filenames 字段 — 服务器端文件名
        for fname in sync_result.get("filenames", []):
            if isinstance(fname, str) and len(fname) > 500:
                try:
                    raw = base64.b64decode(fname)
                    safe_name = "output_%d.bin" % len(downloaded)
                    path = os.path.join(save_dir, safe_name)
                    with open(path, "wb") as f:
                        f.write(raw)
                    downloaded.append({
                        "path": path,
                        "type": "binary",
                        "size_mb": round(len(raw) / 1024 / 1024, 2),
                    })
                    continue
                except Exception:
                    pass

        # 2. images 字段 — base64 / S3 URL / Azure URL
        for i, img in enumerate(sync_result.get("images", [])):
            if isinstance(img, str):
                if img.startswith("s3://") or img.startswith("https://"):
                    # 存储后端 URL，记录引用（不下载）
                    downloaded.append({
                        "path": img,
                        "type": "url",
                        "size_mb": 0,
                    })
                    continue

                if len(img) > 100:
                    # base64 编码的图片/视频数据
                    try:
                        raw = base64.b64decode(img)
                        if raw[:4] == b'\x89PNG':
                            ext = "png"
                        elif raw[:3] == b'\xff\xd8\xff':
                            ext = "jpg"
                        elif raw[:4] == b'fLaC':
                            ext = "flac"
                        elif raw[:4] == b'RIFF':
                            ext = "webp"
                        elif raw[4:8] == b'ftyp':
                            ext = "mp4"
                        else:
                            ext = "bin"
                        fname = "output_%03d.%s" % (i, ext)
                        path = os.path.join(save_dir, fname)
                        with open(path, "wb") as f:
                            f.write(raw)
                        downloaded.append({
                            "path": path,
                            "type": ext,
                            "size_mb": round(len(raw) / 1024 / 1024, 2),
                        })
                    except Exception as e:
                        print("保存 image[%d] 失败: %s" % (i, e))
            elif isinstance(img, dict):
                fname = img.get("filename", "output_%03d.bin" % i)
                path = os.path.join(save_dir, fname)
                if "data" in img:
                    try:
                        raw = base64.b64decode(img["data"])
                        with open(path, "wb") as f:
                            f.write(raw)
                        downloaded.append({
                            "path": path,
                            "type": img.get("format", "binary"),
                            "size_mb": round(len(raw) / 1024 / 1024, 2),
                        })
                    except Exception as e:
                        print("保存 image[%d] 失败: %s" % (i, e))

        return downloaded

    # ----------------------------------------------------------
    # 端口 8188 专用方法（异步模式）
    # ----------------------------------------------------------

    def system_stats(self):
        """获取系统状态（GPU、内存、版本信息）"""
        return self._get("/system_stats")

    def get_queue(self):
        """获取当前队列状态"""
        return self._get("/queue")

    def get_history(self, prompt_id):
        """获取指定任务的执行历史"""
        return self._get("/history/" + prompt_id)

    def queue_prompt(self, workflow):
        """
        提交工作流到队列

        参数:
            workflow: 工作流 JSON 对象

        返回:
            prompt_id 字符串
        """
        resp = self._post("/prompt", {"prompt": workflow})
        return resp["prompt_id"]

    def wait(self, prompt_id, poll=3.0, timeout=600):
        """
        轮询等待任务完成

        参数:
            prompt_id: queue_prompt 返回的 ID
            poll: 轮询间隔（秒）
            timeout: 超时时间（秒）

        返回:
            history entry（包含 outputs 和 status）

        异常:
            TimeoutError: 超时
            RuntimeError: 执行失败
        """
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                hist = self.get_history(prompt_id)
                if prompt_id in hist:
                    status = hist[prompt_id].get("status", {})
                    if status.get("completed"):
                        return hist[prompt_id]
                    if status.get("status_str") == "error":
                        msg = status.get("messages", [])
                        raise RuntimeError("执行失败: " + json.dumps(msg, ensure_ascii=False))
            except RuntimeError:
                raise
            except Exception:
                pass
            time.sleep(poll)
        raise TimeoutError("超时 %ds" % timeout)

    def download(self, filename, subfolder="", save_dir="."):
        """
        下载输出文件

        参数:
            filename: 文件名
            subfolder: 子目录
            save_dir: 本地保存目录

        返回:
            本地文件路径
        """
        params = urllib.parse.urlencode({
            "filename": filename,
            "type": "output",
            "subfolder": subfolder,
        })
        url = self.url + "/view?" + params
        os.makedirs(save_dir, exist_ok=True)
        path = os.path.join(save_dir, filename)
        with urllib.request.urlopen(url, timeout=120) as r:
            with open(path, "wb") as f:
                f.write(r.read())
        return path

    def upload_image(self, file_path):
        """
        上传图片到 ComfyUI input 目录

        参数:
            file_path: 本地图片路径

        返回:
            服务器端文件名
        """
        filename = os.path.basename(file_path)
        boundary = "----FormBoundary7MA4YWxkTrZu0gW"
        with open(file_path, "rb") as f:
            file_data = f.read()
        body = (
            "--%s\r\n" % boundary +
            'Content-Disposition: form-data; name="image"; filename="%s"\r\n' % filename +
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + file_data + ("\r\n--%s--\r\n" % boundary).encode()
        req = urllib.request.Request(
            self.url + "/upload/image",
            data=body,
            headers={"Content-Type": "multipart/form-data; boundary=%s" % boundary},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read())
        return result.get("name", filename)

    def download_outputs(self, history_entry, save_dir="."):
        """
        从 history 结果中提取并下载所有输出文件

        参数:
            history_entry: wait() 返回的 history entry
            save_dir: 本地保存目录

        返回:
            下载的文件列表 [{"path": ..., "type": ..., "size": ...}]
        """
        outputs = self.extract_outputs(history_entry)
        downloaded = []
        for out in outputs:
            try:
                path = self.download(
                    out["filename"],
                    subfolder=out.get("subfolder", ""),
                    save_dir=save_dir,
                )
                size = os.path.getsize(path)
                downloaded.append({
                    "path": path,
                    "type": out["type"],
                    "size": size,
                    "size_mb": round(size / 1024 / 1024, 2),
                })
            except Exception as e:
                print("下载失败 %s: %s" % (out["filename"], e))
        return downloaded

    @staticmethod
    def extract_outputs(history_entry):
        """
        从 history entry 中提取输出文件信息

        SaveVideo 输出可能出现在 gifs 或 images 字段，需同时检查
        """
        results = []
        for node_id, node_data in history_entry.get("outputs", {}).items():
            for key in ["gifs", "images", "audio"]:
                if key in node_data:
                    for item in node_data[key]:
                        ftype = "audio" if key == "audio" else "video"
                        results.append({
                            "type": ftype,
                            "filename": item.get("filename", ""),
                            "subfolder": item.get("subfolder", ""),
                        })
        return results


# ============================================================
# 工作流构建函数
# ============================================================
def build_t2v_workflow(
    prompt_text,
    width=1280,
    height=736,
    length=124,
    seed=None,
    steps=20,
    cfg=7.0,
    sampler_name="euler",
    scheduler="simple",
    shift_video=12.0,
    shift_audio=3.0,
    filename_prefix="minimax_t2v",
):
    """
    构建 MiniMax H3 文生视频工作流（含音频）

    参数:
        prompt_text:   提示词（推荐英文）
        width:          视频宽度（必须为 32 的倍数，默认 1280 = 720p）
        height:         视频高度（必须为 32 的倍数，默认 736 = 720p）
        length:         帧数（24fps，124帧 ≈ 5秒，步进 17）
        seed:           随机种子（None 则随机生成）
        steps:          采样步数（默认 20）
        cfg:            CFG 引导强度（默认 7.0）
        sampler_name:   采样器（默认 euler）
        scheduler:      调度器（默认 simple）
        shift_video:    视频 sigma shift（默认 12.0）
        shift_audio:    音频 sigma shift（默认 3.0）
        filename_prefix: 输出文件名前缀

    返回:
        工作流 JSON 对象

    推荐分辨率:
        720p:  width=1280, height=736
        1080p: width=1920, height=1088
        480p:  width=864,  height=480
    """
    if seed is None:
        seed = random.randint(0, 2**32 - 1)

    return {
        # 模型加载
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
                "type": "minimax",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"},
        },
        "4": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"},
        },
        # Sigma Shift
        "5": {
            "class_type": "MiniMaxH3SigmaShift",
            "inputs": {
                "model": ["1", 0],
                "shift_video": shift_video,
                "shift_audio": shift_audio,
            },
        },
        # 条件 + Latent
        "6": {
            "class_type": "MiniMaxH3ImageToVideo",
            "inputs": {
                "clip": ["2", 0],
                "vae": ["3", 0],
                "prompt": prompt_text,
                "width": width,
                "height": height,
                "length": length,
            },
        },
        "7": {
            "class_type": "ConditioningZeroOut",
            "inputs": {"conditioning": ["6", 0]},
        },
        # 采样
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["5", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["6", 1],
                "denoise": 1.0,
            },
        },
        # VAE 解码
        "9": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["8", 0], "vae": ["3", 0]},
        },
        "10": {
            "class_type": "VAEDecodeAudio",
            "inputs": {"samples": ["8", 0], "vae": ["4", 0]},
        },
        # CreateVideo: IMAGE + AUDIO -> VIDEO
        "13": {
            "class_type": "CreateVideo",
            "inputs": {
                "images": ["9", 0],
                "fps": 24.0,
                "audio": ["10", 0],
            },
        },
        # 保存
        "11": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["13", 0],
                "filename_prefix": filename_prefix,
                "format": "auto",
                "codec": "auto",
            },
        },
        "12": {
            "class_type": "SaveAudio",
            "inputs": {
                "audio": ["10", 0],
                "filename_prefix": filename_prefix,
            },
        },
    }


def build_i2v_workflow(
    prompt_text,
    first_frame=None,
    last_frame=None,
    width=1280,
    height=736,
    length=124,
    seed=None,
    steps=20,
    cfg=7.0,
    filename_prefix="minimax_i2v",
):
    """
    构建 MiniMax H3 图生视频工作流（支持首帧/尾帧）

    参数:
        prompt_text:  提示词
        first_frame:  首帧图片（本地路径或已上传的服务器文件名）
        last_frame:   尾帧图片（本地路径或已上传的服务器文件名）
        其余参数同 build_t2v_workflow
    """
    if seed is None:
        seed = random.randint(0, 2**32 - 1)

    workflow = build_t2v_workflow(
        prompt_text, width, height, length, seed, steps, cfg,
        filename_prefix=filename_prefix,
    )

    next_id = 14
    if first_frame:
        workflow[str(next_id)] = {
            "class_type": "LoadImage",
            "inputs": {"image": first_frame, "upload": "image"},
        }
        workflow["6"]["inputs"]["first_frame"] = [str(next_id), 0]
        next_id += 1

    if last_frame:
        workflow[str(next_id)] = {
            "class_type": "LoadImage",
            "inputs": {"image": last_frame, "upload": "image"},
        }
        workflow["6"]["inputs"]["last_frame"] = [str(next_id), 0]

    return workflow


def build_ref2v_workflow(
    prompt_text,
    ref_images,
    width=1280,
    height=736,
    length=124,
    seed=None,
    steps=20,
    cfg=7.0,
    ref_image_size="match",
    filename_prefix="minimax_ref2v",
):
    """
    构建 MiniMax H3 参考图生视频工作流

    参数:
        prompt_text:    提示词，使用 <Picture 1> 引用参考图
        ref_images:     参考图片路径列表（最多9张）
        ref_image_size: "match" 或 "max"
    """
    if seed is None:
        seed = random.randint(0, 2**32 - 1)

    workflow = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
        "5": {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["1", 0], "shift_video": 12.0, "shift_audio": 3.0}},
        "6": {
            "class_type": "MiniMaxH3ReferenceToVideo",
            "inputs": {
                "clip": ["2", 0], "vae": ["3", 0], "audio_vae": ["4", 0],
                "prompt": prompt_text, "width": width, "height": height,
                "length": length, "ref_image_size": ref_image_size,
                "ref_images": {},
            },
        },
        "7": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["6", 0]}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["5", 0], "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": "euler", "scheduler": "simple", "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["6", 1], "denoise": 1.0}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["8", 0], "vae": ["4", 0]}},
        "13": {"class_type": "CreateVideo", "inputs": {"images": ["9", 0], "fps": 24.0, "audio": ["10", 0]}},
        "11": {"class_type": "SaveVideo", "inputs": {"video": ["13", 0], "filename_prefix": filename_prefix, "format": "auto", "codec": "auto"}},
        "12": {"class_type": "SaveAudio", "inputs": {"audio": ["10", 0], "filename_prefix": filename_prefix}},
    }

    # 添加参考图片节点
    next_id = 20
    ref_map = {}
    for i, img_path in enumerate(ref_images[:9], 1):
        workflow[str(next_id)] = {
            "class_type": "LoadImage",
            "inputs": {"image": img_path, "upload": "image"},
        }
        ref_map["ref_image_%d" % i] = [str(next_id), 0]
        next_id += 1
    workflow["6"]["inputs"]["ref_images"] = ref_map

    return workflow


# ============================================================
# Webhook 验证工具（可选，需安装 svix: pip install svix）
# ============================================================
def verify_webhook(body_bytes, headers, secret):
    """
    验证 Standard Webhooks 签名（需安装 svix 库）

    参数:
        body_bytes: 原始请求体字节
        headers:    请求头 dict（需包含 webhook-id, webhook-timestamp, webhook-signature）
        secret:     WEBHOOK_SECRET 密钥

    返回:
        验证通过返回解析后的 JSON payload，失败抛出异常

    示例:
        from comfyui_minimax_h3_sdk import verify_webhook

        @app.route("/callback", methods=["POST"])
        def callback():
            payload = verify_webhook(request.data, dict(request.headers), SECRET)
            if payload["type"] == "prompt.complete":
                # 处理成功回调
                pass
    """
    from svix import Webhook
    wh = Webhook(secret)
    return wh.verify(body_bytes, dict(headers))


# ============================================================
# 快速调用入口
# ============================================================
def generate_video(
    prompt_text,
    base_url,
    width=1280,
    height=736,
    length=124,
    steps=20,
    cfg=7.0,
    seed=None,
    save_dir="./output",
    timeout=600,
):
    """
    一行代码生成视频（同步模式，端口 3000）

    参数:
        prompt_text: 提示词
        base_url:    ComfyUI 服务地址（含端口 3000），如 "https://your-service:3000"
        width:       视频宽度（32 的倍数，默认 1280 = 720p）
        height:      视频高度（32 的倍数，默认 736 = 720p）
        length:      帧数（24fps，124帧≈5秒）
        steps:       采样步数（默认 20）
        cfg:         CFG 引导强度（默认 7.0）
        seed:        随机种子（None 则随机）
        save_dir:    输出保存目录
        timeout:     HTTP 超时秒数（默认 600）

    示例:
        from comfyui_minimax_h3_sdk import generate_video
        files = generate_video(
            "A cat playing piano",
            base_url="https://your-service:3000",
        )
    """
    client = ComfyUI(base_url)

    workflow = build_t2v_workflow(
        prompt_text, width, height, length,
        seed=seed, steps=steps, cfg=cfg,
    )

    print("调用中（预计 1-10 分钟）...")
    result = client.sync_generate(workflow, timeout=timeout)

    stats = result.get("stats", {})
    # 注意：stats 中时间单位为毫秒，需除以 1000 转换为秒
    duration_ms = stats.get("comfy_execution", {}).get("duration", 0)
    if duration_ms:
        print("  生成耗时: %.1fs" % (duration_ms / 1000))
    total_ms = stats.get("total_time", 0)
    if total_ms:
        print("  总耗时: %.1fs" % (total_ms / 1000))

    files = client.save_sync_outputs(result, save_dir=save_dir)

    for f in files:
        print("  [%s] %s (%.2f MB)" % (f["type"], os.path.basename(f["path"]), f["size_mb"]))

    return files


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python comfyui_minimax_h3_sdk.py <base_url>")
        print("示例: python comfyui_minimax_h3_sdk.py https://your-service:3000")
        sys.exit(1)

    generate_video(
        prompt_text="A ginger cat stretches lazily on a windowsill, sunlight filtering through white sheer curtains onto its fur, macro close-up, shallow depth of field, warm and cozy",
        base_url=sys.argv[1],
        width=1280,
        height=736,
        length=124,
        save_dir="./output",
    )
