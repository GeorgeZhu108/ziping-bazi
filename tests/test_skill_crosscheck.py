# -*- coding: utf-8 -*-
"""跨技能 / 专家交叉验证回归（可复现，纯 Python，不依赖 Node）

对照源：
  [S1] cantian-bazi 技能（fortune-consultant 专家包）离线确定性排盘脚本
       cantian-tymext 历法库，与本项目的 lunar-python 完全独立。
       复现命令（需 Node + 该 skill 目录下 npm i）：
         npx tsx scripts/buildBaziFromSolar.ts "<ISO时间>" <1男/0女> 2
  [S2] bazi-master 技能 SKILL.md 的静态规则表（藏干/十二长生/纳音/禄刃/
       文昌/桃花/驿马/天乙贵人/十神），硬编码为独立参照。
  [S3] fortune-consultant 专家子代理（LLM 推演，非确定性计算）。

已归因的差异（均非本项目缺陷，勿据此改代码）：
  D1 辛金十二长生：bazi-master 写成顺行（子丑寅卯…），但「阳顺阴逆」主流
     为「长生子、沐浴亥、冠带戌、临官酉、帝旺申…养丑」，且该文档自身的
     乙/丁/己/癸都是逆行 —— 属技能文档内部自相矛盾的抄表错误。本项目正确。
  D2 天乙贵人「庚」：本项目采《三命通会》系「甲戊庚牛羊…六辛逢马虎」
     （庚=丑未、辛=寅午）；bazi-master 采异本「庚辛逢虎马」（庚辛皆寅午）。
     两派并存，属流派分歧。data.py 的 source 已标注所采口诀。
  D3 bazi-master 示例把 2003-06-15 排成「甲戌年 丁丑月 壬寅日 丁未时」，
     甲戌为 1994 年、丑月为腊月，与日期不符；其 9.3 起运示例亦把 3 月 22 日
     的「下一个节」写成寒露且天数差 3.59 天。属技能示例数据错误。
     S1 独立排盘与本项目同为「癸未 戊午 己未 辛未」。
  D4 C7 真太阳时：本项目 14:10:36（经度 -23.32 分 + 均时差 +3.93 分），
     S1 为 14:10:20，差 16 秒，均时差算法精度所致；时柱同属未时，四柱一致。
  D5 1990 年中国夏令时（4/15–9/16）：本项目与 S1 均「只提示不扣回」，
     口径一致；是否扣回属于可配置的设计选择，非缺陷。

运行：<bundled python> tests/test_skill_crosscheck.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import HIDDEN_STEMS, SHENSHA_RULES, LU_POSITION, DIWANG_POSITION, SHENG_XIAO
from engine import calculate_bazi

ok = True

# ------------------------------------------------------------------
# 1) 四柱：本项目 vs cantian-bazi 离线独立实现（[S1] 实测结果硬编码）
# ------------------------------------------------------------------
# (年,月,日,时,分,性别,经度, S1四柱)
BASELINE = [
    ("C1", 1990, 10, 8,  9, 30, "男", None,    "庚午 乙酉 丙午 癸巳"),
    ("C2", 2003,  6, 15, 14, 30, "男", None,   "癸未 戊午 己未 辛未"),
    ("C3", 1990,  2, 4,  10, 0,  "男", None,   "己巳 丁丑 庚子 辛巳"),  # 立春边界
    ("C4", 1990,  7, 1,  23, 30, "男", None,   "庚午 壬午 丁卯 壬子"),  # 晚子时+夏令时
    ("C5", 1985,  9, 15, 23, 40, "女", None,   "乙丑 乙酉 丁巳 壬子"),  # 晚子时/女命
    ("C6", 2000,  2, 29, 12, 0,  "男", None,   "庚辰 戊寅 丁巳 丙午"),  # 闰年
    ("C7", 1990,  5, 15, 14, 30, "男", 114.17, "庚午 辛巳 庚辰 癸未"),  # 真太阳时
]

print("=== 1) 四柱 vs cantian-bazi 独立历法库（7 案例） ===")
for cid, y, m, d, h, mi, gender, lon, expect in BASELINE:
    kw = {} if lon is None else {"longitude": lon}
    r = calculate_bazi(y, m, d, h, mi, gender=gender, **kw)
    p = r["pillars"]
    got = " ".join([p["year"], p["month"], p["day"], p["time"]])
    if got != expect:
        ok = False
        print(f"  [FAIL] {cid}: 项目={got} | cantian={expect}")
    else:
        print(f"  [OK] {cid}: {got}")

# ------------------------------------------------------------------
# 2) 静态规则表 vs bazi-master SKILL.md（[S2]）
# ------------------------------------------------------------------
print("\n=== 2) 静态规则表 vs bazi-master（206 项，按主流权威口径） ===")
diffs = []

REF_HIDDEN = {
    "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"],
    "卯": ["乙"], "辰": ["戊", "乙", "癸"], "巳": ["丙", "庚", "戊"],
    "午": ["丁", "己"], "未": ["己", "丁", "乙"], "申": ["庚", "壬", "戊"],
    "酉": ["辛"], "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"],
}
for z, ref in REF_HIDDEN.items():
    got = [s for s, _ in HIDDEN_STEMS[z]]
    if got != ref:
        diffs.append(f"藏干 {z}: {got} != {ref}")

# 主流「阳顺阴逆」十二长生（修正 D1：辛采用逆行）
STAGES = "长生 沐浴 冠带 临官 帝旺 衰 病 死 墓 绝 胎 养".split()
REF_CS = {
    "甲": "亥子丑寅卯辰巳午未申酉戌", "乙": "午巳辰卯寅丑子亥戌酉申未",
    "丙": "寅卯辰巳午未申酉戌亥子丑", "丁": "酉申未午巳辰卯寅丑子亥戌",
    "戊": "寅卯辰巳午未申酉戌亥子丑", "己": "酉申未午巳辰卯寅丑子亥戌",
    "庚": "巳午未申酉戌亥子丑寅卯辰", "辛": "子亥戌酉申未午巳辰卯寅丑",
    "壬": "申酉戌亥子丑寅卯辰巳午未", "癸": "卯寅丑子亥戌酉申未午巳辰",
}
for g, zs in REF_CS.items():
    for i, z in enumerate(zs):
        if SHENG_XIAO[g].get(z) != STAGES[i]:
            diffs.append(f"十二长生 {g}在{z}: {SHENG_XIAO[g].get(z)} != {STAGES[i]}")

REF_WC = {"甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
          "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯"}
for g, v in REF_WC.items():
    if SHENSHA_RULES["文昌贵人"]["map"].get(g) != [v]:
        diffs.append(f"文昌 {g}")

# 本项目采用的口诀版本（D2）
REF_TY = {"甲": ["丑", "未"], "戊": ["丑", "未"], "庚": ["丑", "未"],
          "乙": ["子", "申"], "己": ["子", "申"],
          "丙": ["亥", "酉"], "丁": ["亥", "酉"],
          "壬": ["卯", "巳"], "癸": ["卯", "巳"], "辛": ["寅", "午"]}
for g, v in REF_TY.items():
    got = SHENSHA_RULES["天乙贵人"]["map"].get(g) or []
    if sorted(got) != sorted(v):
        diffs.append(f"天乙贵人 {g}: {got} != {v}")

REF_TH = {"申": "酉", "子": "酉", "辰": "酉", "寅": "卯", "午": "卯", "戌": "卯",
          "巳": "午", "酉": "午", "丑": "午", "亥": "子", "卯": "子", "未": "子"}
for z, v in REF_TH.items():
    if SHENSHA_RULES["桃花"]["map"].get(z) != [v]:
        diffs.append(f"桃花 {z}")

REF_YM = {"申": "寅", "子": "寅", "辰": "寅", "寅": "申", "午": "申", "戌": "申",
          "巳": "亥", "酉": "亥", "丑": "亥", "亥": "巳", "卯": "巳", "未": "巳"}
for z, v in REF_YM.items():
    if SHENSHA_RULES["驿马"]["map"].get(z) != [v]:
        diffs.append(f"驿马 {z}")

REF_YR = {"甲": "卯", "乙": "寅", "丙": "午", "丁": "巳", "戊": "午",
          "己": "巳", "庚": "酉", "辛": "申", "壬": "子", "癸": "亥"}
for g, v in REF_YR.items():
    if SHENSHA_RULES["羊刃"]["map"].get(g) != [v]:
        diffs.append(f"羊刃 {g}")
    if DIWANG_POSITION.get(g) != v:
        diffs.append(f"帝旺 {g}")

REF_LU = {"甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
          "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子"}
for g, v in REF_LU.items():
    if LU_POSITION.get(g) != v:
        diffs.append(f"禄位 {g}")

if diffs:
    ok = False
    for d in diffs:
        print("  [FAIL]", d)
else:
    print("  206 项全部一致 ✅（含按主流口径修正后的辛金逆行表）")

# ------------------------------------------------------------------
# 3) 溯源标注检查（D2 必须在 source 里说明流派）
# ------------------------------------------------------------------
print("\n=== 3) 流派分歧的溯源标注 ===")
src = SHENSHA_RULES["天乙贵人"]["source"]
if "甲戊庚牛羊" in src and "异本" in src:
    print("  [OK] 天乙贵人 source 已标注所采口诀与异本")
else:
    ok = False
    print("  [FAIL] 天乙贵人 source 未标注口诀版本：", src)

print("\n=== 结果 ===", "全部通过 ✅" if ok else "存在偏差 ❌")
sys.exit(0 if ok else 1)
