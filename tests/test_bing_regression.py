"""回归测试：丙火穷通宝鉴规则 + 1990-10-08 案例（酉月丙火）。

验证目标：
1) data.py 中丙火 12 个月规则的 yong/xi/ji 与 OCR 核校后的穷通宝鉴原文一致。
2) calculate_bazi 对丙火各月排盘后，step10 调候用神读取正确，无回归。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import QIONGTONG_RULES
from engine import calculate_bazi

# —— 1) 期望规则（据 OCR 原文校正）——
EXPECTED = {
    1:  ("壬", "庚", "戊"),
    2:  ("壬", "庚", "戊"),
    3:  ("壬", "甲", "戊"),
    4:  ("壬", "庚", "戊"),
    5:  ("壬", "庚", "戊"),
    6:  ("壬", "庚", "戊"),
    7:  ("壬", "庚", "戊"),
    8:  ("壬", "甲", "戊"),
    9:  ("甲", "壬", "戊"),
    10: ("甲", "壬", "戊"),
    11: ("壬", "戊", "己"),
    12: ("壬", "戊", "己"),
}

bing = QIONGTONG_RULES["丙"]
print("=== 丙火规则核验 ===")
ok = True
for m, (y, x, j) in EXPECTED.items():
    r = bing[m]
    got = (r["yong"], r["xi"], r["ji"])
    flag = "OK " if got == (y, x, j) else "ERR"
    if got != (y, x, j):
        ok = False
    print(f"  {flag} 丙日{m:02d}月: 期望({y},{x},{j}) 实际({got[0]},{got[1]},{got[2]})  source={r['source']}")

# —— 2) 直接调用 step10 验证 丙日 十二个月令 调候用神读取（绕过日期/日干匹配）——
from engine import MONTH_ZHI_TO_SOLAR_MONTH, step10_yongshen
# 月支 -> 农历月序（与 QIONGTONG_RULES 键对应）
zhi_by_month = {v: k for k, v in MONTH_ZHI_TO_SOLAR_MONTH.items()}
print("\n=== step10 丙日 十二月令 调候用神读取 ===")
all_ok = ok
for m in range(1, 13):
    zhi = zhi_by_month.get(m)
    # 构造最小化 wuxing / pattern（仅影响扶抑/格局分支，不影响力穷通读取）
    wuxing = {"day_element": "火", "strength": "中和偏旺"}
    pattern = {"pattern": "正财格", "source": "三命通会·论正财格"}
    s10 = step10_yongshen("丙", zhi, wuxing, pattern)
    comp = s10.get("components", {}).get("穷通宝鉴", {})
    got = (comp.get("用神"), comp.get("喜神"), comp.get("忌神"))
    exp = EXPECTED[m]
    flag = "OK " if got == exp else "ERR"
    if got != exp:
        all_ok = False
    print(f"  {flag} 丙日{m:02d}月(月支{zhi}): 期望{exp} 实际{got}")

# —— 3) 真实案例集成（1990-10-08 丙午日 酉月）——
print("\n=== 真实案例集成：1990-10-08 男（丙午日·酉月） ===")
res = calculate_bazi(1990, 10, 8, 9, 30, gender="男", longitude=116.41)
err = res.get("error")
if err:
    print(f"  ERROR -> {err}")
else:
    s10 = next((s for s in res["steps"] if s.get("step") == 10), None)
    comp = s10.get("components", {}).get("穷通宝鉴", {})
    print(f"  日柱={res['pillars']['day']} 月支={res['pillars']['month'][1]}"
          f" 穷通用={comp.get('用神')} 喜={comp.get('喜神')} 忌={comp.get('忌神')}"
          f" 出处={comp.get('出处')}")
    # 与旧 JSON 对比：旧版 final_yong 也应为 壬（用神未变），仅喜/忌精细化
    print(f"  综合建议: {s10.get('final_advice','')}")

print("\n最终结果:", "全部通过" if all_ok else "存在偏差")
