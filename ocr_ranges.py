# -*- coding: utf-8 -*-
"""
本地 OCR 批处理（rapidocr-onnxruntime，零 API Key）。
用法:
    python ocr_ranges.py <out_file> <pdf_path> <start1> <end1> [<start2> <end2> ...]
将多个页码区间逐页渲染并 OCR，写入 out_file。每页一行带 PAGE 标记。
"""
import os
import sys
import pymupdf
from rapidocr_onnxruntime import RapidOCR


def _available_eps():
    try:
        import onnxruntime as ort
        return ort.get_available_providers()
    except Exception:
        return []


def _build_ocr():
    """启动时探测 GPU ExecutionProvider，能启用就启用，否则明确提示而非静默走 CPU。

    事实依据（本机实测）：
      - 主环境 onnxruntime 1.27.0 (CPU wheel) -> ['AzureExecutionProvider', 'CPUExecutionProvider']
      - 隔离环境 onnxruntime-directml 1.24.4 -> ['DmlExecutionProvider', 'CPUExecutionProvider']
      - rapidocr-onnxruntime 1.2.3 的 OrtInferSession 硬编码只认 'CUDAExecutionProvider'，
        且 config.yaml 里 Det/Cls/Rec 的 use_cuda 全为 false，故默认必然走 CPU。
      - UpdateParameters 用 det_/cls_/rec_ 前缀覆盖配置；只传 *_use_cuda 会因缺
        *_model_path 触发 KeyError，必须成对传入。
    """
    eps = _available_eps()
    gpu_eps = [e for e in eps if e in ("CUDAExecutionProvider", "DmlExecutionProvider")]
    print(f"[OCR] onnxruntime providers: {eps}", flush=True)

    if os.environ.get("OCR_FORCE_CPU") == "1":
        print("[OCR] OCR_FORCE_CPU=1，强制 CPU", flush=True)
        return RapidOCR()

    if not gpu_eps:
        print("[OCR] 未检测到 GPU EP -> CPU 推理。启用 GPU："
              "pip install onnxruntime-gpu (CUDA/cuDNN) 或 onnxruntime-directml (Windows D3D12)",
              flush=True)
        return RapidOCR()

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
            print(f"[OCR] GPU 初始化失败，回退 CPU：{exc}", flush=True)
            return RapidOCR()

    print("[OCR] 检测到 DmlExecutionProvider，但 rapidocr-onnxruntime 1.2.3 仅识别 "
          "CUDAExecutionProvider；DirectML 需改装 onnxruntime-gpu 或 patch utils.py 的 cuda_ep。",
          flush=True)
    print("[OCR] 当前回退 CPU（不影响结果，仅速度）", flush=True)
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
                tmp = f"/tmp/_ocr_tmp_{pno}.png"
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
