#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax-H3 (turbo LoRA 4步) 视频生成基准测试
=============================================
9 个用例: 480p / 720p / 1080p × 5s / 10s / 15s
工作流: minimax_h3_turbo_api.json (fl2v_turbo_4step_v1.0_768p LoRA, 4步, euler, shift 12/3, 带音频)

用法:
  python benchmark_minimax_h3.py            # 跑全部 9 个
  python benchmark_minimax_h3.py 480p 5s    # 只跑指定用例
输出:
  outputs/           视频
  benchmark_results.json  原始数据
"""

import json, time, sys, os, uuid, urllib.request, urllib.parse, urllib.error

BASE = "https://deployment-452-mofsmnkz-8188.550w.link"
WF_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "minimax_h3_turbo_api.json")
OUT_DIR = "outputs"
RESULT_FILE = "benchmark_results.json"

# H3 帧数网格: 17k+5
def frames_from_seconds(s: float) -> int:
    base = max(5, round(s * 24))
    return base + (5 - (base % 17)) % 17

# 分辨率档位 (宽高均 32 倍数, 16:9≈1.777, 9:16≈0.5625)
RES = {
    "480p":  {"16:9": (864, 480),  "9:16": (480, 864)},
    "720p":  {"16:9": (1280, 720), "9:16": (720, 1280)},
    "1080p": {"16:9": (1920, 1080),"9:16": (1080, 1920)},
}

# 各时长规格定义: (时长秒, 宽高比, 提示词)
SPECS = {
    "5s": {
        "seconds": 5, "aspect": "16:9",
        "prompt": ("5秒、16:9。一只橘猫从窗台跳下，落地瞬间扭头看向镜头，胡须微微抖动。"
                   "午后阳光从百叶窗缝隙射入，在地面形成条纹光影。自然猫叫声，一次轻柔的落地声。"
                   "不要文字，不要其他人物。"),
    },
    "10s": {
        "seconds": 10, "aspect": "9:16",
        "prompt": ("10秒、9:16竖屏。一位女生在明亮家居工作室中面对镜头微笑，拿起桌上的护肤精华瓶，"
                   "旋开瓶盖，滴一滴在手背，轻轻拍开。柔和自然光，浅色背景。"
                   "声音：瓶盖旋转声，一次轻快的背景钢琴音符。不要对白，不要品牌标识。"),
    },
    "15s": {
        "seconds": 15, "aspect": "16:9",
        "prompt": ("16:9分层剪纸动画。每个元素都看得出是从有纹理的卡纸上剪下来的，层与层之间有柔和的投影。"
                   "一个孩子攥着风筝线，风一起就把他带着跑了起来。他跑过一道道叠起来的纸山坡。"
                   "前景的草以更快的速度往后掠，后面的山慢一些。风筝翻了一下，又稳住，在坡顶把他拽得踮起脚。"
                   "配色是暮色的玫瑰红、赭石和深靛蓝。声音：用纸的摩挲声当风声，弦乐一路推上去，"
                   "腾空那一下有一次屏住的呼吸。不要对白，不要写实材质。"),
    },
}


def api(method, path, data=None, timeout=120, retries=3):
    body = json.dumps(data).encode() if isinstance(data, (dict, list)) else data
    headers = {"Content-Type": "application/json"} if body else {}
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                return json.loads(raw.decode()) if raw else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:400]
            raise RuntimeError(f"HTTP {e.code} {path}: {detail}")
        except Exception as e:
            last = e
            time.sleep(4 * (i + 1))
    raise RuntimeError(f"request failed {path}: {last}")


def submit(wf):
    resp = api("POST", "/prompt", {"prompt": wf, "client_id": uuid.uuid4().hex})
    pid = resp.get("prompt_id")
    if not pid:
        raise RuntimeError(f"提交失败: {resp}")
    return pid


def wait_and_download(pid, timeout=1800):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            h = api("GET", f"/history/{pid}")
        except Exception:
            time.sleep(5); continue
        if pid in h:
            st = h[pid].get("status", {})
            outs = h[pid].get("outputs", {})
            if not outs:
                raise RuntimeError(f"无输出(执行失败): {json.dumps(st)[:300]}")
            files = []
            for nid, o in outs.items():
                for key in ("videos", "gifs", "images"):
                    for v in (o.get(key) or []):
                        fn = v.get("filename")
                        if not fn: continue
                        qs = urllib.parse.urlencode({"filename": fn, "subfolder": v.get("subfolder",""), "type": v.get("type","output")})
                        req = urllib.request.Request(BASE + f"/view?{qs}")
                        with urllib.request.urlopen(req, timeout=600) as r:
                            data = r.read()
                        out = os.path.join(OUT_DIR, f"bench_{case_id}_" + os.path.basename(fn))
                        open(out, "wb").write(data)
                        files.append({"local": out, "size_mb": round(len(data)/1e6, 2), "remote": fn})
            msgs = [m for m in st.get("messages", []) if m[0] in ("execution_start", "execution_success", "execution_error")]
            return files, msgs
        time.sleep(6)
    raise TimeoutError(f"等待 {pid} 超时")


def load_results():
    if os.path.exists(RESULT_FILE):
        return json.load(open(RESULT_FILE, encoding="utf-8"))
    return {}


def save_results(r):
    json.dump(r, open(RESULT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    filters = sys.argv[1:]
    results = load_results()
    cases = [(res, dur) for res in ("480p", "720p", "1080p") for dur in ("5s", "10s", "15s")]
    if filters:
        cases = [c for c in cases if any(f in (c[0]+c[1]) for f in filters)]

    print(f"待跑用例: {len(cases)} 个（已完成跳过: {len(results)} 条记录）\n")
    for res, dur in cases:
        case_id = f"{res}_{dur}"
        if case_id in results and results[case_id].get("ok"):
            print(f"[skip] {case_id} 已完成"); continue
        w, hh = RES[res][SPECS[dur]["aspect"]]
        length = frames_from_seconds(SPECS[dur]["seconds"])
        wf = json.load(open(WF_FILE, encoding="utf-8"))
        wf["16"]["inputs"].update({"prompt": SPECS[dur]["prompt"], "width": w, "height": hh, "length": length})
        wf["20"]["inputs"]["noise_seed"] = 20260818

        print(f"[run ] {case_id}: {w}x{hh} {SPECS[dur]['aspect']} {length}帧 (~{length/24:.1f}s) ...", flush=True)
        rec = {"res": res, "dur": dur, "width": w, "height": hh, "aspect": SPECS[dur]["aspect"],
               "frames": length, "seconds": SPECS[dur]["seconds"], "seed": 20260818,
               "lora": "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16", "steps": 4, "sampler": "euler",
               "shift": [12.0, 3.0], "unet": "minimax_h3_fl2va_pruned_int8_convrot"}
        t_submit = time.time()
        try:
            pid = submit(wf)
            rec["prompt_id"] = pid
            files, msgs = wait_and_download(pid)
            t_done = time.time()
            rec.update({"ok": True,
                        "t_submit": time.strftime("%H:%M:%S", time.localtime(t_submit)),
                        "t_done": time.strftime("%H:%M:%S", time.localtime(t_done)),
                        "wall_s": round(t_done - t_submit, 1), "files": files})
            print(f"[done] {case_id}: {rec['wall_s']}s, files={[f['local'] for f in files]}", flush=True)
        except Exception as e:
            rec.update({"ok": False, "error": str(e)[:400]})
            print(f"[FAIL] {case_id}: {e}", flush=True)
        results[case_id] = rec
        save_results(results)
        time.sleep(3)

    ok = sum(1 for r in results.values() if r.get("ok"))
    print(f"\n===== 汇总: {ok}/{len(results)} 成功 =====")
    for cid in sorted(results):
        r = results[cid]
        print(f"  {cid:10} {'OK ' if r.get('ok') else 'FAIL'} {r.get('wall_s','?'):>7}s  {r.get('width')}x{r.get('height')} {r.get('frames')}帧")
