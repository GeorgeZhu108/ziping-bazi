# -*- coding: utf-8 -*-
"""Web 前端渲染回归测试（Node 驱动）。

复用 tests/test_web_render.js：在 Node 中真实回放 templates/index.html 的
客户端渲染管线，对 fixtures/web 下的真实 API 返回做断言——可见输出中不得出现
英文泄漏（undefined / null）。折叠的 <pre class="hidden"> 原始数据块被排除，
因为它本就镜像原始 API JSON（含 null）。

运行：python tests/test_web_render.py
依赖：node 在 PATH 中。
"""
import os
import subprocess
import sys


def test_web_render_no_undefined():
    here = os.path.dirname(os.path.abspath(__file__))
    js = os.path.join(here, "test_web_render.js")
    r = subprocess.run(["node", js], cwd=os.path.dirname(here))
    assert r.returncode == 0, "Web 渲染出现 undefined/null 英文泄漏（见上方输出）"


if __name__ == "__main__":
    test_web_render_no_undefined()
    print("OK: web render regression passed")
