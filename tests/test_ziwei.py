# -*- coding: utf-8 -*-
"""紫微斗数核心排盘 · 单元测试（与 iztro / Renhuai123/ziwei-doushu 对齐）

验证策略（避免臆造，全部可核对）：
  1) 起紫微星诀：iztro location.ts 注释给出的 3 个金标准示例逐字断言
     （27日木三局→戌 / 13日火六局→亥 / 6日土五局→未）
  2) 五行局：iztro palace.ts 注释给出的 3 个示例（丙子→水二局 / 辛未→土五局 / 庚申→木三局）
  3) 四化表：与 upstream constants.ts SI_HUA_TABLE 逐字一致（甲/乙/壬/癸 抽样 + 全表等长）
  4) 命宫公式：农历五月子时 → 命宫在午（标准安命身宫诀手算）
  5) 内部紫微铁律：紫微≠天府同宫；十四主星各落唯一宫；紫微天府=(12-ziwei)
  6) 端到端：1989-01-09 10:00 男 排盘不报错且结构完整
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ziwei import (
    get_ziwei_tianfu, get_five_elements_class, SI_HUA_TABLE,
    calculate_ziwei, get_soul_body, BRANCHES, STEMS, JU_NAMES,
)


def test_ziwei_placement_examples():
    # iztro location.ts 注释原文示例：局数除日数后紫微落宫
    # 例一：27日 木三局(3) → 紫微在戌（宫索引 8，地支 (2+8)%12=10=戌）
    z, t = get_ziwei_tianfu(27, 3)
    assert BRANCHES[(z + 2) % 12] == "戌", f"例一 紫微应落戌，实得 {BRANCHES[(z+2)%12]}"
    # 例二：13日 火六局(6) → 紫微在亥（宫索引 9，地支 (2+9)%12=11=亥）
    z, t = get_ziwei_tianfu(13, 6)
    assert BRANCHES[(z + 2) % 12] == "亥", f"例二 紫微应落亥，实得 {BRANCHES[(z+2)%12]}"
    # 例三：6日 土五局(5) → 紫微在未（宫索引 5，地支 (2+5)%12=7=未）
    z, t = get_ziwei_tianfu(6, 5)
    assert BRANCHES[(z + 2) % 12] == "未", f"例三 紫微应落未，实得 {BRANCHES[(z+2)%12]}"
    # 天府必与紫微相对（fixIndex(12-ziwei)）
    z, t = get_ziwei_tianfu(27, 3)
    assert t == (12 - z) % 12


def test_wuxing_ju_examples():
    # iztro palace.ts 注释：丙子→水二局(2)；辛未→土五局(5)；庚申→木三局(3)
    assert get_five_elements_class(STEMS.index("丙"), BRANCHES.index("子")) == 2
    assert get_five_elements_class(STEMS.index("辛"), BRANCHES.index("未")) == 5
    assert get_five_elements_class(STEMS.index("庚"), BRANCHES.index("申")) == 3
    # 局数→局名映射闭环
    for v, name in JU_NAMES.items():
        assert name in ("水二局", "木三局", "金四局", "土五局", "火六局")


def test_sihua_table():
    # 与 Renhuai123/ziwei-doushu constants.ts SI_HUA_TABLE 逐字一致
    assert SI_HUA_TABLE[0] == ["廉贞", "破军", "武曲", "太阳"]   # 甲
    assert SI_HUA_TABLE[1] == ["天机", "天梁", "紫微", "太阴"]   # 乙
    assert SI_HUA_TABLE[8] == ["天梁", "紫微", "左辅", "武曲"]   # 壬
    assert SI_HUA_TABLE[9] == ["破军", "巨门", "太阴", "贪狼"]   # 癸
    assert len(SI_HUA_TABLE) == 10
    for v in SI_HUA_TABLE.values():
        assert len(v) == 4


def test_soul_body():
    # 农历五月(寅月=0 → month0=4) 子时(time_branch=0)：命宫=午，身宫=午（子时命身同宫）
    soul, body = get_soul_body(4, 0)
    assert BRANCHES[(soul + 2) % 12] == "午"
    assert BRANCHES[(body + 2) % 12] == "午"
    # 农历五月 午时(time_branch=6)：命宫逆数→子，身宫顺数→子（午时命身同宫在子）
    soul, body = get_soul_body(4, 6)
    assert BRANCHES[(soul + 2) % 12] == "子"
    assert BRANCHES[(body + 2) % 12] == "子"


def test_full_chart_invariants():
    c = calculate_ziwei(1989, 1, 9, 10, "男")
    # 紫微 ≠ 天府 同宫
    assert c["ziwei_index"] != c["tianfu_index"]
    # 十四主星各落唯一宫（紫微系6 + 天府系8 = 14颗，全部落盘）
    placed = []
    for p in c["palaces"]:
        for s in p["stars"]:
            if s["type"] == "major":
                placed.append(s["name"])
    assert len(placed) == 14, f"主星数应为14，实得 {len(placed)}"
    assert len(set(placed)) == 14, f"主星应互不重复，实得 {placed}"
    # 十二宫结构完整
    assert len(c["palaces"]) == 12
    assert sum(1 for p in c["palaces"] if p["is_ming"]) == 1
    assert sum(1 for p in c["palaces"] if p["is_shen"]) == 1
    # 大限 12 柱完整
    assert len(c["decadals"]) == 12
    # 四化与年干一致（1989-01-09 在立春前 → 立春年界为戊辰，年干戊=index4）
    ys = STEMS.index(c["lunar"]["year_stem"])
    assert c["sihua"] == dict(zip(["化禄", "化权", "化科", "化忌"], SI_HUA_TABLE[ys]))
    # 流年落宫可查
    fy = __import__("ziwei").flow_year(c, 2026)
    assert fy is not None and "palace_name" in fy


def test_interpret_ziwei():
    c = calculate_ziwei(1989, 1, 9, 10, "男")
    it = c["interpretation"]
    # 命宫主星释义：至少一条，且字段齐全
    assert it["ming_stars"], "命宫主星释义不应为空"
    for m in it["ming_stars"]:
        assert all(k in m for k in ("name", "nature", "meaning", "source")), f"释义字段缺失: {m}"
        assert m["meaning"], f"释义内容不应为空: {m['name']}"
    # 四化释义：4 条，且能定位到落宫（非空）
    assert len(it["sihua"]) == 4
    for s in it["sihua"]:
        assert s["hua"] in ("化禄", "化权", "化科", "化忌")
        assert s["palace"] != "—", f"四化 {s['hua']}{s['star']} 应定位到落宫"
        assert s["meaning"]
    # 身宫释义非空
    assert it["shen_meaning"]
    # 整体可 JSON 序列化（供 Web API 透传）
    import json
    json.dumps(it)
    # 例：1989-01-09 命宫申，主星天同+天梁 → 应识别「机月同梁」格
    names = {p["name"]: [s["name"] for s in p["stars"] if s["type"] == "major"]
             for p in c["palaces"]}
    triple = set(names.get("命宫", [])) | set(names.get("财帛宫", [])) | \
             set(names.get("官禄宫", [])) | set(names.get("迁移宫", []))
    if {"天机", "太阴", "天同", "天梁"} & triple:
        assert any(p["name"] == "机月同梁" for p in it["patterns"]), "三方四正含机月同梁应被识别"


if __name__ == "__main__":
    n = 0
    for fn in (test_ziwei_placement_examples, test_wuxing_ju_examples,
               test_sihua_table, test_soul_body, test_full_chart_invariants,
               test_interpret_ziwei):
        fn(); n += 1; print(f"  [OK] {fn.__name__}")
    print(f"紫微核心测试 {n}/6 全部通过 ✅")
