# -*- coding: utf-8 -*-
"""
扫描版古籍 OCR 工具（本地引擎 rapidocr-onnxruntime，无需任何 API Key）。

用法:
    python ocr_book.py <pdf_path> <start_page> <end_page> [dpi]
将逐页渲染为图片并 OCR，输出每页识别文字。
"""
import sys
import pymupdf
from rapidocr_onnxruntime import RapidOCR

OCR = RapidOCR()


def ocr_range(pdf_path, start, end, dpi=200):
    doc = pymupdf.open(pdf_path)
    n = doc.page_count
    for pno in range(max(0, start - 1), min(n, end)):
        pix = doc[pno].get_pixmap(dpi=dpi)
        # 存临时 png 再读，避免色彩空间问题
        tmp = f"_ocr_tmp_{pno}.png"
        pix.save(tmp)
        result, _ = OCR(tmp)
        text_lines = []
        if result:
            for box, txt, score in result:
                text_lines.append(txt)
        full = " ".join(text_lines)
        print(f"\n===== PAGE {pno + 1} (score lines={len(text_lines)}) =====")
        print(full)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: ocr_book.py <pdf> <start> <end> [dpi]")
        sys.exit(1)
    ocr_range(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]),
              int(sys.argv[4]) if len(sys.argv) > 4 else 200)
