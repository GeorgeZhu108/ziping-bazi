# -*- coding: utf-8 -*-
"""
Regression test: 引擎输出的「面向用户」文案（大白话 overview / sections / glossary）
不得夹带英文（含此前出现的 "month柱透出" 类 bug）。

内部字段名（如 十神代码 zheng_guan、late_zishi_rule=current-day）不计入——
它们不直接展示给用户。

运行：python tests/test_no_english.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import engine as E
import ziwei as Z

# 测试用真实出生数据（覆盖闰日、晚子时、男女、不同月令）
INPUTS = [
    (1989, 1, 9, 10, "男"), (1990, 7, 15, 10, "男"), (1995, 11, 11, 23, "男"),
    (1988, 12, 31, 0, "男"), (2000, 2, 29, 14, "女"), (1976, 5, 20, 15, "女"),
    (1985, 8, 8, 8, "男"), (1992, 3, 3, 20, "女"), (1995, 9, 9, 9, "男"),
    (1977, 4, 4, 4, "女"),
]

# 命理体系内部枚举码 / 配置键（不应出现在用户文案，但属数据结构，非文案泄漏）
_INTERNAL_OK = {"current-day", "next-day", "all-current", "day-cur-time-next"}

_ENG = re.compile(r"[A-Za-z]{2,}")


def _user_texts(result):
    """抽取所有面向用户的纯文本（大白话 overview / sections[].plain / glossary[].term&plain）。"""
    out = []
    pl = result["steps"][-1].get("plain_language", {}) or {}
    if isinstance(pl.get("overview"), str):
        out.append(pl["overview"])
    for s in pl.get("sections", []) or []:
        if isinstance(s, dict):
            if isinstance(s.get("plain"), str):
                out.append(s["plain"])
        elif isinstance(s, str):
            out.append(s)
    for g in pl.get("glossary", []) or []:
        if isinstance(g, dict):
            if isinstance(g.get("term"), str):
                out.append(g["term"])
            if isinstance(g.get("plain"), str):
                out.append(g["plain"])
        elif isinstance(g, str):
            out.append(g)
    return out


def test_no_english_in_user_text():
    leaks = []
    for (y, m, d, h, g) in INPUTS:
        r = E.calculate_bazi(y, m, d, h, 0, gender=g)
        for t in _user_texts(r):
            for w in _ENG.findall(t):
                if w not in _INTERNAL_OK:
                    leaks.append((y, m, d, h, g, w, t[:40]))
    assert not leaks, f"用户文案发现英文泄漏: {leaks[:10]}"


def test_touchu_position_is_chinese():
    """透出天干的位置字段必须是中文 年/月/日/时，不能是英文 year/month/day/time。"""
    bad = []
    for (y, m, d, h, g) in INPUTS:
        r = E.calculate_bazi(y, m, d, h, 0, gender=g)
        s9 = next(s for s in r["steps"] if s["step"] == 9)
        for t in s9["reason"].get("透出天干", []):
            if t.get("位置") in ("year", "month", "day", "time"):
                bad.append((y, m, d, h, g, t))
    assert not bad, f"透出天干位置仍为英文: {bad[:5]}"


def test_no_english_in_ziwei_summary():
    """紫微斗数·人生总体总评（life_summary）面向用户文案不得夹带英文。"""
    leaks = []
    for (y, m, d, h, g) in INPUTS:
        r = Z.calculate_ziwei(y, m, d, h, g)
        ls = r["interpretation"]["life_summary"]
        for sec in ls:
            for key in ("term", "plain", "source"):
                for w in _ENG.findall(sec.get(key, "")):
                    leaks.append((y, m, d, h, g, w, sec.get(key, "")[:40]))
    assert not leaks, f"紫微总体总评发现英文泄漏: {leaks[:10]}"


if __name__ == "__main__":
    try:
        test_no_english_in_user_text()
        print("[OK] test_no_english_in_user_text")
    except AssertionError as e:
        print("[FAIL] test_no_english_in_user_text:", e)
        raise
    try:
        test_touchu_position_is_chinese()
        print("[OK] test_touchu_position_is_chinese")
    except AssertionError as e:
        print("[FAIL] test_touchu_position_is_chinese:", e)
        raise
    try:
        test_no_english_in_ziwei_summary()
        print("[OK] test_no_english_in_ziwei_summary")
    except AssertionError as e:
        print("[FAIL] test_no_english_in_ziwei_summary:", e)
        raise
    print("PASS: 引擎用户文案无英文泄漏（八字+紫微），透出位置均为中文")
