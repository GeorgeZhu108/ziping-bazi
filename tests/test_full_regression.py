# -*- coding: utf-8 -*-
"""全量回归：穷通宝鉴调候规则（10日干×12月）

基准来源：梁湘润评注本《穷通宝鉴·栏江网》本地 OCR 逐字核验
（corpus/ocr_jia_yi.txt / ocr_ding_wu.txt / ocr_ji_geng.txt / ocr_gui.txt
 及 _ocr_bing*.txt，含各干「调候用神提要表」）。

GOLDEN 中每项为 "用神喜神忌神" 三字串，"-" 表示忌神留空
（守「诚实溯源」原则：原文未明言病/忌则不臆造忌神）。

运行：<bundled python> tests/test_full_regression.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import QIONGTONG_RULES, HEAVENLY_STEMS
from engine import calculate_bazi, MONTH_ZHI_TO_SOLAR_MONTH

# 120 条全量锁定：正月→十二月（月序 1..12）
GOLDEN = {
    "甲": ["丙癸-", "庚丁-", "庚壬-", "癸丁-", "癸庚-", "癸庚-", "丁庚-", "丁丙-", "丁壬-", "庚丁-", "丁庚-", "丁庚-"],
    "乙": ["丙癸戊", "丙癸庚", "癸丙庚", "癸丙-", "癸丙戊", "癸丙己", "丙癸庚", "癸丙-", "癸丙-", "丙戊癸", "丙戊癸", "丙戊癸"],
    "丙": ["壬庚戊", "壬庚戊", "壬甲戊", "壬庚戊", "壬庚戊", "壬庚戊", "壬庚戊", "壬甲戊", "甲壬戊", "甲壬戊", "壬戊己", "壬戊己"],
    "丁": ["甲庚癸", "甲庚癸", "甲庚癸", "甲庚癸", "壬庚丙", "甲壬癸", "甲庚-", "甲丙-", "甲庚戊", "甲庚癸", "甲庚癸", "甲庚癸"],
    "戊": ["丙甲-", "丙甲-", "甲丙-", "甲丙-", "壬甲丁", "癸丙丁", "丙癸壬", "丙癸辛", "甲丙-", "甲丙-", "丙甲-", "丙甲-"],
    "己": ["丙癸壬", "甲癸-", "丙癸庚", "癸丙戊", "癸丙戊", "癸丙戊", "癸丙庚", "癸丙-", "甲丙-", "丙甲癸", "丙甲癸", "丙甲癸"],
    "庚": ["丙甲癸", "丁甲癸", "甲丁癸", "壬戊-", "壬癸戊", "丁甲癸", "丁甲壬", "丁甲壬", "甲壬己", "丁丙癸", "丁甲癸", "丙丁癸"],
    "辛": ["己壬丙", "壬丙戊", "壬甲戊", "壬庚戊", "壬己戊", "壬庚戊", "壬庚戊", "壬甲戊", "壬甲戊", "壬丙-", "丙壬癸", "丙壬癸"],
    "壬": ["庚丙-", "戊辛-", "甲庚戊", "壬庚-", "癸庚-", "辛甲-", "戊丁-", "甲庚戊", "甲丙戊", "戊丙-", "戊丙-", "丙甲-"],
    "癸": ["辛丙-", "庚辛丁", "丙辛-", "辛庚丁", "庚辛丁", "庚辛丁", "丁甲癸", "辛丙-", "辛甲戊", "庚辛丁", "丙辛癸", "丙辛癸"],
}

# 原文溯源抽查：校正必须带梁氏评注本依据，而非只改三元组
TRACE_CHECKS = [
    ("乙", 11, "去癸水之病"),       # 乙木冬月喜戊之据
    ("丁", 4, "最忌癸水"),          # 丁火四月忌癸之据
    ("戊", 1, "癸為喜神"),          # 戊土清空误填忌神癸之据
    ("己", 10, "不可用癸"),         # 己土冬月忌癸之据
    ("庚", 1, "丙甲為上"),          # 庚金正月用丙之据
    ("庚", 9, "忌見己土濁壬"),      # 庚金九月喜壬忌己之据
    ("癸", 8, "辛金為用"),          # 癸水八月用辛之据
    ("癸", 9, "戊己皆忌"),          # 癸水九月忌戊之据
]

ok = True

print("=== 1) 结构完整性（10干 × 12月 = 120条） ===")
for gan in HEAVENLY_STEMS:
    block = QIONGTONG_RULES.get(gan, {})
    if len(block) != 12:
        print(f"  [FAIL] {gan} 月份数={len(block)} != 12")
        ok = False
        continue
    for m in range(1, 13):
        e = block.get(m)
        if not e or set(e.keys()) != {"yong", "xi", "ji", "note", "source"}:
            print(f"  [FAIL] {gan} 月{m} 键异常")
            ok = False
            continue
        if not e["yong"] or not e["xi"]:
            print(f"  [FAIL] {gan} 月{m} 用/喜神为空")
            ok = False
        if "梁湘润" not in e["source"]:
            print(f"  [FAIL] {gan} 月{m} source 未标注梁氏评注页码")
            ok = False
        if len(e["note"]) < 20:
            print(f"  [FAIL] {gan} 月{m} note 未记录原文依据")
            ok = False
print("  结构检查完毕（键集合 / 用喜神 / 梁氏出处 / 原文依据）。")

print("\n=== 2) 全量 120 条用喜忌基准比对 ===")
diff = 0
for gan, row in GOLDEN.items():
    for m, gold in enumerate(row, start=1):
        e = QIONGTONG_RULES[gan][m]
        actual = e["yong"] + e["xi"] + (e["ji"] or "-")
        if actual != gold:
            print(f"  [FAIL] {gan}月{m}: 基准={gold} | 实际={actual}")
            ok = False
            diff += 1
print(f"  比对 120 条，偏差 {diff} 条。" if diff else "  120 条全部一致 ✅")

print("\n=== 3) 原文溯源抽查 ===")
for gan, m, phrase in TRACE_CHECKS:
    note = QIONGTONG_RULES[gan][m]["note"]
    if phrase not in note:
        print(f"  [FAIL] {gan}月{m} note 缺原文关键句「{phrase}」")
        ok = False
    else:
        print(f"  [OK] {gan}月{m} 含「{phrase}」")

print("\n=== 4) 端到端冒烟：每个日干找一个真实日期，验证引擎读取校正后规则 ===")
def find_date_for_gan(target_gan):
    import datetime
    d = datetime.date(1990, 1, 1)
    end = datetime.date(2010, 1, 1)
    while d < end:
        res = calculate_bazi(d.year, d.month, d.day, 9, 30, gender="男")
        if res.get("error"):
            d += datetime.timedelta(days=1)
            continue
        if res["pillars"]["day"][0] == target_gan:
            return d, res
        d += datetime.timedelta(days=1)
    return None, None

for gan in HEAVENLY_STEMS:
    d, res = find_date_for_gan(gan)
    if not d:
        print(f"  [FAIL] 未找到 {gan} 日干日期")
        ok = False
        continue
    s10 = next((s for s in res["steps"] if s.get("step") == 10), None)
    if not s10 or "穷通宝鉴" not in s10.get("components", {}):
        print(f"  [FAIL] {gan} 日期{d} step10 缺穷通宝鉴分量")
        ok = False
        continue
    qt = s10["components"]["穷通宝鉴"]
    month_zhi = res["pillars"]["month"][1]
    mnum = MONTH_ZHI_TO_SOLAR_MONTH.get(month_zhi, 1)
    rule = QIONGTONG_RULES[gan][mnum]
    if qt["用神"] != rule["yong"] or qt["喜神"] != rule["xi"]:
        print(f"  [FAIL] {gan} 日期{d} 月支{month_zhi}(月{mnum}) "
              f"引擎=({qt['用神']},{qt['喜神']}) != 规则=({rule['yong']},{rule['xi']})")
        ok = False
    else:
        print(f"  [OK] {gan} 日期{d} 月{mnum} 用={qt['用神']} 喜={qt['喜神'] or '-'} 忌={qt['忌神'] or '-'}")

print("\n=== 结果 ===", "全部通过 ✅" if ok else "存在偏差 ❌")
sys.exit(0 if ok else 1)
