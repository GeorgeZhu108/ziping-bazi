# -*- coding: utf-8 -*-
"""袁天罡称骨：农历月/日（含闰月十五分界、春节年界）端到端验证。

验证目标：
  1. leap_aware_month 闰月十五分界 + 闰正月/闰腊月特例正确；
  2. engine 称骨改用农历后，1990-07-15 公历=农历闰五月廿三 → 折算六月 → 49 钱（4两9钱），
     修正此前公历月日直算（44 钱）的偏差；
  3. 春节/立春年界分歧预警（year_note）在立春前出生者正确触发。
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import calculate_bazi
import chengu


def test_leap_aware_month():
    # 闰五月（getMonth() = -5）
    assert chengu.leap_aware_month(-5, 10) == 5   # 前半月算本月
    assert chengu.leap_aware_month(-5, 15) == 5   # 十五仍算本月
    assert chengu.leap_aware_month(-5, 16) == 6   # 十六起算下月
    assert chengu.leap_aware_month(-5, 23) == 6
    # 特例：闰正月 / 闰腊月不拆分
    assert chengu.leap_aware_month(-1, 20) == 1
    assert chengu.leap_aware_month(-12, 20) == 12
    # 普通月原样返回
    assert chengu.leap_aware_month(6, 23) == 6
    assert chengu.leap_aware_month(3, 1) == 3
    print("[OK] leap_aware_month 闰月十五分界 + 特例")


def test_main_case_lunar():
    # 1990-07-15 10:00 公历 = 农历 庚午年闰五月廿三
    # 农历年庚午=9, 闰五月廿三(后半月)折算六月=16, 农历日23=8, 巳时=16 => 49 钱
    r = calculate_bazi(1990, 7, 15, 10, 0, gender="男", longitude=116.41, current_year=2026)
    cg = r["steps"][11]["chengu"]
    assert cg["year_w"] == 9
    assert cg["month_w"] == 16          # 六月骨重（非公历七月9钱）
    assert cg["day_w"] == 8             # 农历廿三（非公历15日10钱）
    assert cg["hour_w"] == 16
    assert cg["total_qian"] == 49
    assert cg["total_str"] == "4两9钱"
    assert cg["song"].startswith("此命推来福不轻")
    print("[OK] 主算例农历折算 -> 4两9钱（修正公历直算44钱偏差）")


def test_spring_festival_vs_lichun_note():
    # 1990-02-01：春节(1/27)后、立春(2/4)前
    # 八字年柱按立春=己巳；称骨年按春节=庚午 -> 触发 year_note
    r = calculate_bazi(1990, 2, 1, 10, 0, gender="男", longitude=116.41, current_year=2026)
    cg = r["steps"][11]["chengu"]
    assert r["pillars"]["year"] == "己巳"
    assert cg["year_w"] == 9            # 庚午
    assert "year_note" in cg
    assert "己巳" in cg["year_note"] and "庚午" in cg["year_note"]
    print("[OK] 春节/立春年界分歧预警触发")


def test_plain_language_shows_chengu():
    r = calculate_bazi(1990, 7, 15, 10, 0, gender="男", longitude=116.41, current_year=2026)
    pl = r["steps"][11]["plain_language"]
    terms = [s["term"] for s in pl["sections"]]
    assert any("称骨" in t for t in terms)
    cg_sec = [s for s in pl["sections"] if "称骨" in s["term"]][0]
    assert "4两9钱" in cg_sec["plain"]
    print("[OK] 综合报告称骨分条显示农历结果 4两9钱")


if __name__ == "__main__":
    test_leap_aware_month()
    test_main_case_lunar()
    test_spring_festival_vs_lichun_note()
    test_plain_language_shows_chengu()
    print("\n全部通过 ✅")
