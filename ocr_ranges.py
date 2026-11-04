# -*- coding: utf-8 -*-
"""
本地 OCR 批处理（rapidocr-onnxruntime，零 API Key）。
用法:
    python ocr_ranges.py <out_file> <pdf_path> <start1> <end1> [<start2> <end2> ...]
将多个页码区间逐页渲染并 OCR，写入 out_file。每页一行带 PAGE 标记。
"""
import sys
import pymupdf
from rapidocr_onnxruntime import RapidOCR

OCR = RapidOCR()


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
