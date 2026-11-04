# -*- coding: utf-8 -*-
"""晚子时（23:00-23:59）换日口径回归。

BUG 背景（由 SkillHub 技能交叉验证发现，2026-11-04）：
  bazi-personality/scripts/bazi_convert.py 采用「子时换日派」，C4 给
  「庚午 壬午 戊辰 壬子」；我方 late_zishi_rule='next-day' 却给
  「庚午 壬午 戊辰 甲子」。
  根因：preprocess_birth_time 把 day_shift 加到日期后仍保留 23:xx，
  再交给 lunar-python getBaZi() 等于二次套用晚子时，时柱错成甲子。
  修复：next-day 且晚子时，把 corrected 时刻归一为次日 00:xx。

客观基准（lunar-python getBaZi() 实测）：
  1990-07-01 23:30 -> 庚午 壬午 丁卯 壬子
  1990-07-02 00:30 -> 庚午 壬午 戊辰 壬子   ← 子时换日派应得
  1990-07-02 23:30 -> 庚午 壬午 戊辰 甲子   ← 修复前的错误输入
  1985-09-15 23:40 -> 乙丑 乙酉 丁巳 壬子
  1985-09-16 00:40 -> 乙丑 乙酉 戊午 壬子

运行：<bundled python> tests/test_late_zishi_regression.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calendar_fix import preprocess_birth_time  # noqa: E402
from engine import calculate_bazi  # noqa: E402
from lunar_python import Solar  # noqa: E402

CASES = [("C4", 1990, 7, 1, 23, 30, "男"), ("C5", 1985, 9, 15, 23, 40, "女")]
EXPECT = {
    "current-day": {"C4": "庚午 壬午 丁卯 壬子", "C5": "乙丑 乙酉 丁巳 壬子"},
    "next-day": {"C4": "庚午 壬午 戊辰 壬子", "C5": "乙丑 乙酉 戊午 壬子"},
}

ok = True


def pillars_str(r):
    p = r["pillars"]
    return " ".join([p["year"], p["month"], p["day"], p["time"]])


print("=== 1) 默认口径（current-day）零回归 ===")
for cid, y, m, d, h, mi, g in CASES:
    got = pillars_str(calculate_bazi(y, m, d, h, mi, gender=g))
    exp = EXPECT["current-day"][cid]
    if got != exp:
        ok = False
        print(f"  [FAIL] {cid}: {got} != {exp}")
    else:
        print(f"  [OK] {cid}: {got}")

print("\n=== 2) next-day 口径与 lunar-python 次日早子时一致 ===")
for cid, y, m, d, h, mi, g in CASES:
    got = pillars_str(calculate_bazi(y, m, d, h, mi, gender=g, late_zishi_rule="next-day"))
    exp = EXPECT["next-day"][cid]
    # 独立基准：用次日 00:xx 直接问 lunar-python
    import datetime
    nd = datetime.date(y, m, d) + datetime.timedelta(days=1)
    lb = " ".join(Solar.fromYmdHms(nd.year, nd.month, nd.day, 0, mi, 0).getLunar().getBaZi())
    good = got == exp == lb
    if not good:
        ok = False
        print(f"  [FAIL] {cid}: engine={got} expect={exp} lunar_next_morning={lb}")
    else:
        print(f"  [OK] {cid}: {got} (与次日 00:{mi:02d} 的 getBaZi 一致)")

print("\n=== 3) next-day 的 corrected 时刻必须归一到 00:xx ===")
for cid, y, m, d, h, mi, g in CASES:
    pre = preprocess_birth_time(y, m, d, h, mi, late_zishi_rule="next-day")
    corr = pre["corrected"]
    if corr[3] != 0 or corr[4] != mi:
        ok = False
        print(f"  [FAIL] {cid}: corrected={corr}，期望小时=0 分钟={mi}")
    else:
        print(f"  [OK] {cid}: corrected={corr} day_shift={pre['day_shift']}")

print("\n=== 4) 四种口径均不抛异常 ===")
for rule in ["current-day", "next-day", "all-current", "day-cur-time-next"]:
    try:
        r = calculate_bazi(1990, 7, 1, 23, 30, gender="男", late_zishi_rule=rule)
        print(f"  [OK] {rule}: {pillars_str(r)}")
    except Exception as e:
        ok = False
        print(f"  [FAIL] {rule}: {e}")

print("\n=== 结果 ===", "全部通过 ✅" if ok else "存在偏差 ❌")
sys.exit(0 if ok else 1)
