# -*- coding: utf-8 -*-
"""
本地 OCR 批处理（rapidocr-onnxruntime，零 API Key）。
用法:
    python ocr_ranges.py <out_file> <pdf_path> <start1> <end1> [<start2> <end2> ...]
将多个页码区间逐页渲染并 OCR，写入 out_file。每页一行带 PAGE 标记。

GPU 策略（算力资源优化）：启动即探测 onnxruntime ExecutionProvider。
  - 检测到 CUDAExecutionProvider（需 onnxruntime-gpu + 匹配 cuDNN）→ 启用 CUDA。
  - 检测到 DmlExecutionProvider（onnxruntime-directml，Windows 任意 DX12 GPU，
    无需 CUDA/cuDNN）→ 运行时 patch rapidocr 硬编码的 CUDA EP 为 DML，启用 DirectML。
  - 均无 → CPU；可设 OCR_FORCE_CPU=1 强制 CPU。
"""
import os
import re
import sys
import inspect
import tempfile
import pymupdf
from rapidocr_onnxruntime import RapidOCR


def _available_eps():
    try:
        import onnxruntime as ort
        return ort.get_available_providers()
    except Exception:
        return []


_dml_patched = False


def _enable_dml():
    """运行时把 rapidocr 硬编码的 CUDA EP 重定向为 DmlExecutionProvider（不改动 site-packages）。

    事实依据：rapidocr_onnxruntime 1.2.3 的 OrtInferSession.__init__ 把
    cuda_ep 硬编码为 'CUDAExecutionProvider' 且需 get_device()=='GPU'；
    而本机装的是 onnxruntime-directml（提供 DmlExecutionProvider），
    onnxruntime.get_device() 在无 torch 时返回 'CPU'。两者都需 patch 才能走 DML。
    幂等：已 patch 则直接返回 True，避免对 exec 定义的方法二次 getsource 失败。
    """
    global _dml_patched
    import textwrap
    import rapidocr_onnxruntime.utils as U
    import onnxruntime as ort
    if "DmlExecutionProvider" not in ort.get_available_providers():
        return False
    if getattr(U.OrtInferSession.__init__, "_dml_patched", False):
        return True
    try:
        src = inspect.getsource(U.OrtInferSession.__init__)
        src = textwrap.dedent(src)
        src = re.sub(r"cuda_ep\s*=\s*'CUDAExecutionProvider'", "cuda_ep = 'DmlExecutionProvider'", src)
        src = src.replace("'cudnn_conv_algo_search': 'EXHAUSTIVE',", "")
        src = src.replace("'do_copy_in_default_stream': True", "'device_id': 0")
        # 强制所有模型（DET/REC/CLS）走 GPU：把 rapidocr 的 use_cuda/get_device 条件
        # 替换为「cuda_ep 在可用 EP 中」（cuda_ep 已被改为 DmlExecutionProvider）。
        # 这样不依赖 config['use_cuda'] 与 onnxruntime.get_device()（本机无 torch 时返回 CPU）。
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

    if os.environ.get("OCR_FORCE_CPU") == "1":
        print("[OCR] OCR_FORCE_CPU=1，强制 CPU", flush=True)
        return RapidOCR()

    gpu_eps = [e for e in eps if e in ("CUDAExecutionProvider", "DmlExecutionProvider")]
    if not gpu_eps:
        print("[OCR] 未检测到 GPU EP -> CPU 推理。启用 GPU："
              "pip install onnxruntime-gpu (CUDA/cuDNN) 或 onnxruntime-directml (Windows D3D12)",
              flush=True)
        return RapidOCR()

    # 1) CUDA 优先（需 onnxruntime-gpu + 匹配 cuDNN）
    if "CUDAExecutionProvider" in eps:
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
            print("[OCR] 已启用 CUDAExecutionProvider (GPU)", flush=True)
            return ocr
        except Exception as exc:
            print(f"[OCR] CUDA 初始化失败，尝试 DML：{exc}", flush=True)

    # 2) DML（DirectML，Windows 任意 DX12 GPU，无需 CUDA/cuDNN）
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
            print(f"[OCR] 已启用 DmlExecutionProvider (GPU/DirectML)；实际 EP={_rapid_eps_used(ocr)}",
                  flush=True)
            return ocr
    except Exception as exc:
        print(f"[OCR] DML 初始化失败，回退 CPU：{exc}", flush=True)

    print("[OCR] 回退 CPU（不影响结果，仅速度）", flush=True)
    return RapidOCR()


OCR = _build_ocr()


def ocr_ranges(out_file, pdf_path, ranges, dpi=200):
    doc = pymupdf.open(pdf_path)
    n = doc.page_count
    done = set()
    with open(out_file, "w", encoding="utf-8") as f:
        for (s, e) in ranges:
            for pno in range(max(0, s - 1), min(n, e)):
                if pno in done:
                    continue
                done.add(pno)
                pix = doc[pno].get_pixmap(dpi=dpi)
                tmp = os.path.join(tempfile.gettempdir(), f"_ocr_tmp_{pno}.png")
                pix.save(tmp)
                result, _ = OCR(tmp)
                lines = [txt for _, txt, _ in result] if result else []
                f.write(f"\n===== PAGE {pno + 1} =====\n")
                f.write(" ".join(lines) + "\n")
                f.flush()
    print(f"DONE {out_file}: {len(done)} pages")


if __name__ == "__main__":
    out_file = sys.argv[1]
    pdf_path = sys.argv[2]
    nums = [int(x) for x in sys.argv[3:]]
    ranges = [(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]
    ocr_ranges(out_file, pdf_path, ranges)
