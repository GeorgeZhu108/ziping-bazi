# -*- coding: utf-8 -*-
"""
ocr_ranges 并行/有序/清理 单元测试（不依赖真实 GPU 与 PDF）。

通过 mock OCR 与 pymupdf，验证：
  1) 多线程并行确实并发执行（max 并发 >= 2）；
  2) 输出严格按页码升序；
  3) 每页临时 PNG 用完即删，无磁盘泄漏；
  4) 打印页数/秒基准。
"""
import os
import sys
import glob
import tempfile
import threading
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ocr_ranges as ocr


class _FakePixmap:
    def __init__(self, path):
        self._path = path

    def save(self, path):
        # 写入一个极小的占位 PNG 内容，模拟渲染产物
        with open(path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")


class _FakePage:
    def __init__(self, pno):
        self._pno = pno

    def get_pixmap(self, dpi=200):
        return _FakePixmap(f"_page_{self._pno}")


class _FakeDoc:
    def __init__(self, n):
        self._n = n

    def __getitem__(self, i):
        return _FakePage(i)

    @property
    def page_count(self):
        return self._n

    def close(self):
        pass


def _make_fake_ocr(concurrency):
    lock = threading.Lock()

    def fake_ocr(tmp_path):
        with lock:
            concurrency["current"] += 1
            concurrency["max"] = max(concurrency["max"], concurrency["current"])
        # 模拟 GPU 推理耗时，使并发可见
        import time
        time.sleep(0.05)
        with lock:
            concurrency["current"] -= 1
        # 从临时文件名无法得页码，这里用全局映射（测试内约定）
        return [("box", "HELLO_PAGE", 0.99)], None

    return fake_ocr


def test_parallel_order_cleanup_bench():
    concurrency = {"current": 0, "max": 0}
    tmp_out = os.path.join(tempfile.gettempdir(), "_ocr_parallel_test_out.txt")

    with mock.patch.object(ocr, "OCR", _make_fake_ocr(concurrency)), \
         mock.patch.object(ocr.pymupdf, "open", lambda p: _FakeDoc(9)):
        os.environ["OCR_WORKERS"] = "4"
        ocr.ocr_ranges(tmp_out, "fake.pdf", [(1, 9)])

    # 1) 有序
    with open(tmp_out, encoding="utf-8") as f:
        content = f.read()
    pages_found = []
    for line in content.splitlines():
        if line.startswith("===== PAGE "):
            pages_found.append(int(line.split()[2]))
    assert pages_found == list(range(1, 10)), f"页码顺序错误: {pages_found}"
    assert content.count("HELLO_PAGE") == 9, "文本行数不足"

    # 2) 并发：9 页 / 0.05s / 4 workers → 至少应有 2 路并发
    assert concurrency["max"] >= 2, f"未观测到并行（max 并发={concurrency['max']}）"

    # 3) 临时文件清理
    leftovers = glob.glob(os.path.join(tempfile.gettempdir(), "_ocr_tmp_*.png"))
    assert not leftovers, f"存在未清理的临时文件: {leftovers}"

    print("OCR parallel test PASSED: ordered=%s, max_concurrency=%d, leftovers=%d"
          % (pages_found, concurrency["max"], len(leftovers)))
    # 清理输出
    try:
        os.remove(tmp_out)
    except OSError:
        pass


if __name__ == "__main__":
    test_parallel_order_cleanup_bench()
