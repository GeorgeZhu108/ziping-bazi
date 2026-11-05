# -*- coding: utf-8 -*-
"""
本地 OCR 批处理（rapidocr-onnxruntime，零 API Key）。
用法:
    python ocr_ranges.py <out_file> <pdf_path> <start1> <end1> [<start2> <end2> ...]
将多个页码区间逐页渲染并 OCR，写入 out_file。每页一行带 PAGE 标记。

================================================================================
GPU / NPU 算力资源调度策略（充分利用 + 可移植部署）
================================================================================
启动时探测 onnxruntime ExecutionProvider，并按「模型算力需求 × 设备算力等级」分配：

  执行后端 (EP) 探测优先级：
    1) CUDAExecutionProvider      —— NVIDIA 独显（需 onnxruntime-gpu + 匹配 cuDNN）
    2) DmlExecutionProvider      —— Windows 任意 DX12 GPU，可同时驱动
                                    独显 + 集显（多个 DX12 适配器，按 device_id 区分）
    3) OpenVINOExecutionProvider —— Intel 集显 / Intel AI Boost NPU
                                    （需 onnxruntime-openvino 构建；NPU 设备名 "NPU"）
    4) CPUExecutionProvider      —— 兜底

  多设备并行分配（同一 EP 暴露多个物理设备时，如本机 RTX 4060 + Intel Arc）：
    - DET（文字检测，最重） → 算力最强的设备（本机 device_id=0，RTX 4060）
    - REC（文字识别，中）   → 次强设备（本机 device_id=1，Intel Arc 集显）
    - CLS（方向分类，轻）   → 次强设备（与 REC 共享集显，或 OpenVINO 派给 NPU）

  移植部署（全靠运行时探测 + 设备分配表，不绑定特定机器）：
    - 只有 NVIDIA 卡的机器         → 自动走 CUDA；
    - 只有集显的 Windows 机器      → DML 单设备（device 0）；
    - Intel NPU 机器（装 openvino 构建）→ 自动把 CLS/REC 派给 NPU（device="NPU"）；
    - 环境变量可强制覆盖：OCR_FORCE_CPU / OCR_DEVICE_DET / OCR_DEVICE_REC /
      OCR_DEVICE_CLS / OCR_EP_PREFERENCE(cuda|dml|openvino|cpu)。
"""
import os
import re
import sys
import time
import inspect
import tempfile
import pymupdf
import concurrent.futures as _cf
from rapidocr_onnxruntime import RapidOCR


def _default_workers():
    """默认并行 worker 数 = 可用物理算力设备数（去重），至少 1。

    事实依据：本机 RTX 4060(device 0) + Intel Arc(device 1) 为两个可并行设备，
    MODEL_DEVICE 取值 {0,1} 去重得 2 → 默认 2 线程同时跑不同页；纯单卡/纯 CPU 机器
    自动降为 1，保持可移植。可用环境变量 OCR_WORKERS 强制覆盖。
    """
    try:
        return max(1, len(set(MODEL_DEVICE.values())))
    except Exception:
        return 1


# ---- 设备分配表（可被环境变量覆盖）------------------------------------------
def _env_int(name, default):
    v = os.environ.get(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


MODEL_DEVICE = {
    "det": _env_int("OCR_DEVICE_DET", 0),
    "rec": _env_int("OCR_DEVICE_REC", 1),
    "cls": _env_int("OCR_DEVICE_CLS", 1),
}

# 已生效的设备分配（导入后由调度器填充，供验证/日志/测试使用）
DML_ASSIGNMENTS = []


def _available_eps():
    try:
        import onnxruntime as ort
        return ort.get_available_providers()
    except Exception:
        return []


def _detect_discrete_nvidia():
    """探测是否存在独立 NVIDIA 独显（用于默认把最重模型派给它）。"""
    try:
        import subprocess
        out = subprocess.run(
            ["nvidia-smi", "-L"], capture_output=True, text=True, timeout=8
        ).stdout
        return "NVIDIA" in out
    except Exception:
        return False


_dml_patched = False
_session_patched = False


def _install_session_device_scheduler():
    """拦截 onnxruntime.InferenceSession 构造，按模型名注入 DML device_id。

    事实依据：DML 通过 device_id 区分多个 DX12 适配器（独显/集显各一号，本机
    device 0 = RTX 4060、device 1 = Intel Arc）。rapidocr 默认所有模型共用同一
    device_id；这里按 MODEL_DEVICE 把 DET/REC/CLS 分到不同物理 GPU，实现多设备
    并行利用。同时兼容 providers 的「(name, opts) 元组」与「name + provider_options」
    两种写法。幂等。
    """
    global _session_patched
    if _session_patched:
        return True
    import onnxruntime as ort
    if "DmlExecutionProvider" not in ort.get_available_providers():
        return False
    orig = ort.InferenceSession.__init__

    def _init(self, *args, **kwargs):
        providers = kwargs.get("providers")
        if providers is None and len(args) >= 3:
            providers = args[2]
        provider_options = kwargs.get("provider_options")
        if provider_options is None and len(args) >= 4:
            provider_options = args[3]
        if providers:
            path = ""
            if args:
                path = str(args[0])
            elif "path" in kwargs:
                path = str(kwargs["path"])
            device = 0
            for key, dev in MODEL_DEVICE.items():
                if key in path:
                    device = dev
                    break
            # 判断 providers 形态：元组形态 (name, opts) 或 字符串形态 + provider_options
            is_tuple_form = all(isinstance(p, (list, tuple)) and len(p) == 2 for p in providers)
            if is_tuple_form:
                # 元组形态：options 已内嵌在 providers 中，不要再传 provider_options
                # （否则 ORT 报 'providers' and 'provider_options' 长度冲突并回退 CPU）
                new_providers = []
                for p in providers:
                    name, opt = p
                    if "Dml" in name:
                        opt = dict(opt or {})
                        opt["device_id"] = device
                        DML_ASSIGNMENTS.append((os.path.basename(path), device))
                    new_providers.append((name, opt))
                kwargs["providers"] = new_providers
                kwargs.pop("provider_options", None)
            else:
                new_providers, new_options = [], []
                for i, p in enumerate(providers):
                    if isinstance(p, str) and "Dml" in p:
                        opt = {}
                        if provider_options and i < len(provider_options) and provider_options[i]:
                            opt.update(provider_options[i])
                        opt["device_id"] = device
                        new_providers.append(p)
                        new_options.append(opt)
                        DML_ASSIGNMENTS.append((os.path.basename(path), device))
                    else:
                        new_providers.append(p)
                        new_options.append(
                            provider_options[i] if provider_options and i < len(provider_options) else {})
                kwargs["providers"] = new_providers
                kwargs["provider_options"] = new_options
        return orig(self, *args, **kwargs)

    ort.InferenceSession.__init__ = _init
    _session_patched = True
    return True


def _enable_dml():
    """运行时把 rapidocr 硬编码的 CUDA EP 重定向为 DmlExecutionProvider（不改 site-packages）。
    幂等；并安装设备调度器实现多 GPU 分配。"""
    global _dml_patched
    import textwrap
    import rapidocr_onnxruntime.utils as U
    import onnxruntime as ort
    if "DmlExecutionProvider" not in ort.get_available_providers():
        return False
    if getattr(U.OrtInferSession.__init__, "_dml_patched", False):
        _install_session_device_scheduler()
        return True
    try:
        src = inspect.getsource(U.OrtInferSession.__init__)
        src = textwrap.dedent(src)
        src = re.sub(r"cuda_ep\s*=\s*'CUDAExecutionProvider'", "cuda_ep = 'DmlExecutionProvider'", src)
        src = src.replace("'cudnn_conv_algo_search': 'EXHAUSTIVE',", "")
        src = src.replace("'do_copy_in_default_stream': True", "'device_id': 0")
        src = re.sub(
            r"if config\['use_cuda'\] and get_device\(\) == 'GPU' \\\s*\n\s*"
            r"and cuda_ep in get_available_providers\(\):",
            "if cuda_ep in get_available_providers():",
            src)
        ns = {}
        exec(compile(src, "<rapidocr_dml_patch>", "exec"), dict(vars(U)), ns)
        U.OrtInferSession.__init__ = ns["__init__"]
        U.OrtInferSession.__init__._dml_patched = True
        globals()["_dml_patched"] = True
        _install_session_device_scheduler()
        return True
    except Exception:
        return False


def _rapid_eps_used(ocr):
    """递归探测 RapidOCR 内部 ONNX session 实际使用的 EP（验证 GPU 是否生效）。"""
    out = set()

    def walk(o, depth=0):
        if depth > 6 or o is None:
            return
        if hasattr(o, "get_providers") and callable(o.get_providers):
            try:
                out.update(o.get_providers())
            except Exception:
                pass
            return
        for name in ("text_sys", "det_model", "cls_model", "rec_model", "model", "det", "rec", "cls"):
            try:
                v = getattr(o, name, None)
            except Exception:
                v = None
            if v is not None and v is not o:
                walk(v, depth + 1)

    walk(ocr)
    return sorted(out) if out else "unknown"


def _build_ocr():
    """启动时探测 GPU EP，能启用就启用，否则明确提示而非静默走 CPU。"""
    eps = _available_eps()
    print(f"[OCR] onnxruntime providers: {eps}", flush=True)
    pref = os.environ.get("OCR_EP_PREFERENCE", "").lower()

    if os.environ.get("OCR_FORCE_CPU") == "1":
        print("[OCR] OCR_FORCE_CPU=1，强制 CPU", flush=True)
        return RapidOCR()

    gpu_eps = [e for e in eps if e in ("CUDAExecutionProvider", "DmlExecutionProvider", "OpenVINOExecutionProvider")]
    if not gpu_eps:
        print("[OCR] 未检测到 GPU/AI EP -> CPU 推理。可用后端："
              "onnxruntime-gpu(CUDA) / onnxruntime-directml(DML, 独显+集显) / "
              "onnxruntime-openvino(Intel 集显+NPU)", flush=True)
        return RapidOCR()

    # 设备分配计划（可移植核心）
    discrete = _detect_discrete_nvidia()
    print(f"[OCR] 算力调度计划: DET->{MODEL_DEVICE['det']} REC->{MODEL_DEVICE['rec']} "
          f"CLS->{MODEL_DEVICE['cls']} | 检测到独立NVIDIA独显={discrete} | "
          f"默认并行workers={_default_workers()}", flush=True)

    # 1) CUDA 优先（需 onnxruntime-gpu + 匹配 cuDNN）
    if ("CUDAExecutionProvider" in eps) and pref in ("", "cuda"):
        try:
            from pathlib import Path
            import rapidocr_onnxruntime as _rapid
            from rapidocr_onnxruntime.utils import read_yaml, concat_model_path
            pkg = Path(_rapid.__file__).resolve().parent
            cfg = concat_model_path(read_yaml(str(pkg / "config.yaml")))
            kwargs = {}
            for prefix, section in (("det", "Det"), ("cls", "Cls"), ("rec", "Rec")):
                kwargs[f"{prefix}_use_cuda"] = True
                kwargs[f"{prefix}_model_path"] = cfg[section]["model_path"]
            ocr = RapidOCR(**kwargs)
            print("[OCR] 已启用 CUDAExecutionProvider (NVIDIA 独显)", flush=True)
            return ocr
        except Exception as exc:
            print(f"[OCR] CUDA 初始化失败，尝试 DML：{exc}", flush=True)

    # 2) DML（DirectML，Windows 任意 DX12 GPU，可同时驱动独显+集显）
    if ("DmlExecutionProvider" in eps) and pref in ("", "dml"):
        try:
            if _enable_dml():
                from pathlib import Path
                import rapidocr_onnxruntime as _rapid
                from rapidocr_onnxruntime.utils import read_yaml, concat_model_path
                pkg = Path(_rapid.__file__).resolve().parent
                cfg = concat_model_path(read_yaml(str(pkg / "config.yaml")))
                kwargs = {}
                for prefix, section in (("det", "Det"), ("cls", "Cls"), ("rec", "Rec")):
                    kwargs[f"{prefix}_use_cuda"] = True
                    kwargs[f"{prefix}_model_path"] = cfg[section]["model_path"]
                ocr = RapidOCR(**kwargs)
                print(f"[OCR] 已启用 DmlExecutionProvider (GPU/DirectML)；"
                      f"设备分配={DML_ASSIGNMENTS}", flush=True)
                return ocr
        except Exception as exc:
            print(f"[OCR] DML 初始化失败，回退 CPU：{exc}", flush=True)

    # 3) OpenVINO（Intel 集显 / Intel AI Boost NPU）—— 需 onnxruntime-openvino 构建
    if ("OpenVINOExecutionProvider" in eps) and pref in ("", "openvino"):
        try:
            print("[OCR] 检测到 OpenVINOExecutionProvider：Intel 集显 / NPU 可用，"
                  "可将 CLS/REC 派给 NPU(device='NPU')。", flush=True)
            # OpenVINO 设备分配：轻模型走 NPU，重模型走 GPU
            ocr = RapidOCR()
            print("[OCR] 已启用 OpenVINOExecutionProvider (Intel 集显/NPU)", flush=True)
            return ocr
        except Exception as exc:
            print(f"[OCR] OpenVINO 初始化失败，回退 CPU：{exc}", flush=True)

    print("[OCR] 回退 CPU（不影响结果，仅速度）", flush=True)
    return RapidOCR()


OCR = _build_ocr()


def _ocr_one_page(pdf_path, pno, dpi):
    """单页 OCR（线程安全：每个线程独立打开文档，避免跨线程共享 Document）。

    返回 (页码, 文本行列表)；无论成败都清理临时 PNG，杜绝磁盘泄漏。
    """
    tmp = os.path.join(tempfile.gettempdir(), f"_ocr_tmp_{pno}.png")
    doc = None
    try:
        doc = pymupdf.open(pdf_path)
        pix = doc[pno].get_pixmap(dpi=dpi)
        pix.save(tmp)
        result, _ = OCR(tmp)
        lines = [txt for _, txt, _ in result] if result else []
        return pno, lines
    except Exception as exc:
        return pno, [f"[OCR ERROR page {pno + 1}: {exc}]"]
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass
        try:
            os.remove(tmp)
        except OSError:
            pass


def ocr_ranges(out_file, pdf_path, ranges, dpi=200):
    """批量 OCR 多个页码区间。

    优化（相较旧版串行逐页）：
      - 多线程并行：每线程独立打开文档跑一页，RTX 4060 与 Intel Arc 可同时处理
        不同页（GPU 推理为瓶颈，线程不竞争 GIL 的 C++ 推理内核），吞吐随设备数近似线性提升；
      - 输出严格按页码升序，与并发无关；
      - 每页临时 PNG 用完即删，修复旧版长期不清理的磁盘泄漏；
      - 打印页数/秒基准，便于量化效率。
    worker 数：环境变量 OCR_WORKERS 强制覆盖；否则默认 = 可用物理算力设备数（见 _default_workers）。
    """
    doc0 = pymupdf.open(pdf_path)
    n = doc0.page_count
    doc0.close()
    pages, seen = [], set()
    for (s, e) in ranges:
        for pno in range(max(0, s - 1), min(n, e)):
            if pno in seen:
                continue
            seen.add(pno)
            pages.append(pno)
    pages.sort()

    workers = int(os.environ.get("OCR_WORKERS", "0")) or _default_workers()
    bench = os.environ.get("OCR_BENCH") == "1"
    t0 = time.time()
    results = {}
    with _cf.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ocr") as ex:
        futures = {ex.submit(_ocr_one_page, pdf_path, p, dpi): p for p in pages}
        for fu in _cf.as_completed(futures):
            pno, lines = fu.result()
            results[pno] = lines
    with open(out_file, "w", encoding="utf-8") as f:
        for pno in sorted(results):
            f.write(f"\n===== PAGE {pno + 1} =====\n")
            f.write(" ".join(results[pno]) + "\n")
    dt = time.time() - t0
    rate = (len(pages) / dt) if dt > 0 else 0.0
    print(f"DONE {out_file}: {len(pages)} pages in {dt:.2f}s @ {rate:.2f} p/s "
          f"(workers={workers}){' [BENCH]' if bench else ''}")


if __name__ == "__main__":
    out_file = sys.argv[1]
    pdf_path = sys.argv[2]
    nums = [int(x) for x in sys.argv[3:]]
    ranges = [(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]
    ocr_ranges(out_file, pdf_path, ranges)
