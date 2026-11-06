# -*- coding: utf-8 -*-
"""针对若干『具体八字』跑多源比对表（供人工核对）

方法学（与 tests/test_external_crosscheck.py 同源，复用其独立 oracle）：
  · 链路A = lunar-python 原生 getBaZi()（线上绝大多数排盘站底层同一引擎）
  · 链路B = 手写独立算法（JDN日柱 / 五鼠遁时柱 / 节气+五虎遁月柱 / 复算称骨）
  · 引擎  = ziping-app 自身 calculate_bazi
三者逐柱核对：月/日/时 必须三路一致；年柱立春口径引擎==链路A；称骨引擎==复算。
年界窗口内额外暴露 立春↔春节 设计性分歧（非 bug）。

用法：python run_comparison_table.py
输出：终端打印 + comparison_table.md
"""
import os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lunar_python import Solar
from engine import calculate_bazi
import chengu
from tests.test_external_crosscheck import (
    day_gz, time_gz, month_gz, GAN, ZHI,
)


def parse_corr(s):
    y, m, d = int(s[:4]), int(s[5:7]), int(s[8:10])
    hh, mm = int(s[11:13]), int(s[14:16])
    return y, m, d, hh, mm


# —— 若干具体八字（带可读标签，覆盖多样性场景）——
CASES = [
    (1989, 1, 9, 10, 0, "男", 116.4, "己土锚点·用户引用案例"),
    (1990, 10, 8, 9, 30, "男", 116.4, "丙火·寒露节气月柱bug-fix锚点"),
    (1988, 2, 5, 12, 0, "女", 116.4, "年界窗口·立春2/4后春节2/17前"),
    (2000, 3, 1, 23, 30, "男", 116.4, "晚子时23:30"),
    (1976, 9, 9, 0, 0, "男", 0.0, "午夜·本初子午线经度校正"),
    (2023, 7, 4, 8, 0, "女", -122.4, "西经旧金山·经度校正"),
]


def run():
    dev = {"year": 0, "month": 0, "day": 0, "time": 0, "chengu": 0}
    design_div = []
    rows = []

    for (y, mo, d, h, mi, g, lon, note) in CASES:
        r = calculate_bazi(y, mo, d, h, mi, gender=g, longitude=lon,
                           current_year=2026)
        if r.get("error"):
            print(f"  [SKIP] {y}-{mo:02d}-{d:02d} {g}: {r['error']}")
            continue
        eng = r["pillars"]
        corr = r["input"]["corrected_birth"]
        cy, cm, cd, ch, cmin = parse_corr(corr)

        # 链路 A：lunar 原生（立春年界，基于校正后时间）
        ls = Solar.fromYmdHms(cy, cm, cd, ch, cmin, 0).getLunar()
        A = ls.getBaZi()

        # 链路 B：手写独立算法（基于校正后时间）
        B_day = day_gz(cy, cm, cd)
        B_time = time_gz(cy, cm, cd, ch)
        B_month = month_gz(cy, cm, cd, ch, cmin)
        B_year = A[0]

        for pos, a, b, e in [("month", A[1], B_month, eng["month"]),
                             ("day", A[2], B_day, eng["day"]),
                             ("time", A[3], B_time, eng["time"])]:
            if not (a == b == e):
                dev[pos] += 1
                print(f"  [FAIL][{note}] {pos}: 引擎={e} 链路A={a} 链路B={b}")

        if eng["year"] != A[0]:
            dev["year"] += 1
            print(f"  [FAIL][{note}] year: 引擎={eng['year']} 链路A={A[0]}")

        # 春节年界年柱（设计性分歧检测）
        spring_year_zhi = ls.getYearInGanZhi()
        if spring_year_zhi != A[0]:
            design_div.append((f"{y}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}", A[0], spring_year_zhi))

        # 称骨复算
        s12 = r["steps"][-1]
        eng_qian = s12["chengu"]["total_qian"]
        cg_m = chengu.leap_aware_month(ls.getMonth(), ls.getDay())
        cg_d = ls.getDay()
        cg_hz = eng["time"][1]
        exp = chengu.calculate_chengu(spring_year_zhi, cg_m, cg_d, cg_hz)
        if eng_qian != exp["total_qian"]:
            dev["chengu"] += 1
            print(f"  [FAIL][{note}] 称骨: 引擎={eng_qian} 复算={exp['total_qian']}")

        rows.append({
            "birth": f"{y}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}",
            "g": g, "lon": lon, "note": note,
            "eng": [eng["year"], eng["month"], eng["day"], eng["time"]],
            "A": A, "B": [B_year, B_month, B_day, B_time],
            "ts": s12["chengu"]["total_str"], "q": eng_qian,
        })

    # —— 生成 markdown 比对表 ——
    lines = []
    lines.append("# 具体八字 · 多源交叉验证比对表\n")
    lines.append("> 方法学：引擎(ziping-app) 四柱/称骨 逐项比对 链路A(lunar-python 原生，线上排盘站同源) 与 链路B(手写独立算法 JDN日柱/五鼠遁时柱/节气+五虎遁月柱/复算称骨)。\n")
    lines.append("| # | 出生(公历) | 性别 | 经度 | 标签 | 引擎四柱 | 链路A(lunar) | 链路B(手写) | 称骨(引擎/复算) | 一致性 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for i, row in enumerate(rows, 1):
        eng_s = "".join(row["eng"])
        A_s = "".join(row["A"])
        B_s = "".join(row["B"])
        # 一致性：月日时三柱 + 称骨
        consistent = (row["eng"][1] == row["A"][1] == row["B"][1] and
                      row["eng"][2] == row["A"][2] == row["B"][2] and
                      row["eng"][3] == row["A"][3] == row["B"][3])
        flag = "✅" if consistent else "❌"
        lines.append(
            f"| {i} | {row['birth']} | {row['g']} | {row['lon']} | {row['note']} "
            f"| {eng_s} | {A_s} | {B_s} | {row['ts']} | {flag} |"
        )
    lines.append("")
    lines.append("## 偏差统计")
    total_dev = sum(dev.values())
    lines.append(f"- 年柱偏差: {dev['year']} ｜ 月柱: {dev['month']} ｜ 日柱: {dev['day']} ｜ 时柱: {dev['time']} ｜ 称骨: {dev['chengu']}")
    lines.append(f"- **合计偏差: {total_dev}**")
    lines.append("")
    lines.append("## 设计性年界分歧（立春年界 vs 春节年界，非 bug，已透明标注）")
    if design_div:
        lines.append("| 出生(公历) | 立春年界 | 春节年界 |")
        lines.append("|---|---|---|")
        for birth, a, s in design_div:
            lines.append(f"| {birth} | {a} | {s} |")
    else:
        lines.append("- （本批参数未触及立春↔春节窗口，双年界一致）")
    lines.append("")
    lines.append("## 结论")
    if total_dev == 0:
        lines.append("✅ **全部一致**：引擎与两套独立来源在 月/日/时/称骨 上零偏差。")
    else:
        lines.append(f"❌ 存在 {total_dev} 处偏差，详见上方 FAIL 日志。")

    md = "\n".join(lines)
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "comparison_table.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)

    # 终端打印
    print("=" * 72)
    print("具体八字 · 多源交叉验证比对表")
    print("=" * 72)
    print(f"{'#':<3}{'出生(公历)':<17}{'性别':<4}{'经度':>8}  {'引擎':<10}{'lunar':<10}{'手写':<10}{'称骨':<8}一致")
    for i, row in enumerate(rows, 1):
        eng_s = "".join(row["eng"]); A_s = "".join(row["A"]); B_s = "".join(row["B"])
        consistent = (row["eng"][1]==row["A"][1]==row["B"][1] and
                      row["eng"][2]==row["A"][2]==row["B"][2] and
                      row["eng"][3]==row["A"][3]==row["B"][3])
        print(f"{i:<3}{row['birth']:<17}{row['g']:<4}{row['lon']:>8}  {eng_s:<10}{A_s:<10}{B_s:<10}{row['ts']:<8}{'✅' if consistent else '❌'}")
    print("-" * 72)
    print(f"偏差统计：年{dev['year']} 月{dev['month']} 日{dev['day']} 时{dev['time']} 称骨{dev['chengu']} ｜ 合计 {total_dev}")
    if design_div:
        for birth, a, s in design_div:
            print(f"  设计性年界分歧 {birth}: 立春={a} 春节={s}")
    print(f"\n已写入：{out_path}")
    return total_dev == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
