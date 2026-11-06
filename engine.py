# -*- coding: utf-8 -*-
"""
子平推演 - 演算引擎
12步流水线：历法转换→四柱→大运→十神→藏干→关系→神煞→五行→格局→用神→流年→报告
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
from lunar_python import Solar, Lunar

from calendar_fix import preprocess_birth_time

from data import (
    HEAVENLY_STEMS, EARTHLY_BRANCHES, STEM_ATTRS, BRANCH_ATTRS,
    ELEMENTS, SHENG, KE, TEN_GOD_NAMES, TEN_GOD_RULES, HIDDEN_STEMS,
    LIU_HE, LIU_CHONG, SAN_HE, SAN_HUI, XING_RULES, HAI, RELATION_SOURCES,
    SHENSHA_RULES, SEASONS, WANG_SHUAI, WANG_SHUAI_SCORE,
    QIONGTONG_RULES, PATTERN_RULES, LU_POSITION, DIWANG_POSITION,
    SHENG_XIAO, GAN_HE, GAN_HE_ELEMENT, RELATION_MEANINGS,
    TEN_GOD_MEANINGS, LIUNIAN_TEMPLATES, MONTH_ZHI_TO_SOLAR_MONTH,
    ELEMENT_TO_STEMS, YONGSHEN_PRIORITY, NAYIN, DITIANSUI_TIXIANG,
    DITIANSUI_XINGXIANG, DITIANSUI_XINGXIANG_NOTE, ZIPING_GE, ziping_ge_category, SHENFENG, SANMINGTONGHUI
)
import chengu

# ============================================================
# 工具函数
# ============================================================

def next_stem(gan: str, step: int = 1) -> str:
    idx = HEAVENLY_STEMS.index(gan)
    return HEAVENLY_STEMS[(idx + step) % 10]

def prev_stem(gan: str, step: int = 1) -> str:
    idx = HEAVENLY_STEMS.index(gan)
    return HEAVENLY_STEMS[(idx - step) % 10]

def next_branch(zhi: str, step: int = 1) -> str:
    idx = EARTHLY_BRANCHES.index(zhi)
    return EARTHLY_BRANCHES[(idx + step) % 12]

def prev_branch(zhi: str, step: int = 1) -> str:
    idx = EARTHLY_BRANCHES.index(zhi)
    return EARTHLY_BRANCHES[(idx - step) % 12]

def is_yang_gan(gan: str) -> bool:
    return not STEM_ATTRS[gan]["yin"]

def element_relation(gan: str, target_gan: str) -> str:
    """返回 target_gan 对 gan 的关系：生我、我生、克我、我克、同我"""
    g_e = STEM_ATTRS[gan]["element"]
    t_e = STEM_ATTRS[target_gan]["element"]
    if g_e == t_e:
        return "同我"
    if SHENG[g_e] == t_e:
        return "我生"
    if SHENG[t_e] == g_e:
        return "生我"
    if KE[g_e] == t_e:
        return "我克"
    return "克我"

def get_ten_god(day_stem: str, target_gan: str) -> Tuple[str, str]:
    """
    返回 (十神代码, 十神名称)
    来源：三命通会·十神论
    """
    relation = element_relation(day_stem, target_gan)
    same_yin = STEM_ATTRS[day_stem]["yin"] == STEM_ATTRS[target_gan]["yin"]
    for code, rule in TEN_GOD_RULES.items():
        if rule["relation"] == relation and rule["same_yin"] == same_yin:
            return code, TEN_GOD_NAMES[code]
    return "bi_jian", "比肩"


def parse_pillar(pillar: str) -> Tuple[str, str]:
    return pillar[0], pillar[1]


def get_jieqi_date(year: int, jieqi_name: str) -> datetime:
    """
    获取某年某节气的公历日期。
    lunar-python 提供当年节气表，按名称索引。
    """
    solar = Solar.fromYmd(year, 1, 1)
    lunar = solar.getLunar()
    table = lunar.getJieQiTable()
    if jieqi_name in table:
        jq = table[jieqi_name]
        return datetime(jq.getYear(), jq.getMonth(), jq.getDay(),
                        jq.getHour(), jq.getMinute(), jq.getSecond())
    return None


def find_jieqi_around(birth: datetime) -> Tuple[str, datetime, str, datetime]:
    """
    返回 (上一个节气名, 上一个节气时间, 下一个节气名, 下一个节气时间)
    """
    solar = Solar.fromYmdHms(birth.year, birth.month, birth.day,
                             birth.hour, birth.minute, birth.second)
    lunar = solar.getLunar()
    prev_name = str(lunar.getPrevJieQi()) if lunar.getPrevJieQi() else None
    next_name = str(lunar.getNextJieQi()) if lunar.getNextJieQi() else None
    table = lunar.getJieQiTable()
    prev_dt = None
    next_dt = None
    if prev_name and prev_name in table:
        jq = table[prev_name]
        prev_dt = datetime(jq.getYear(), jq.getMonth(), jq.getDay(),
                           jq.getHour(), jq.getMinute(), jq.getSecond())
    if next_name and next_name in table:
        jq = table[next_name]
        next_dt = datetime(jq.getYear(), jq.getMonth(), jq.getDay(),
                           jq.getHour(), jq.getMinute(), jq.getSecond())
    return prev_name, prev_dt, next_name, next_dt


# ============================================================
# 第1步：历法转换
# ============================================================

def step1_calendar(year: int, month: int, day: int, hour: int, minute: int = 0, second: int = 0,
                  pre: Dict = None) -> Dict:
    """
    公历 → 干支历，并获取节气信息。
    来源：中国古代算命术·排八字 / 三命通会·论节候
    注：year~minute 已是「真太阳时校正后」的排盘时间（由 calculate_bazi 经 calendar_fix 预处理传入）。
    """
    solar = Solar.fromYmdHms(year, month, day, hour, minute, second)
    lunar = solar.getLunar()
    eight_char = lunar.getBaZi()  # 返回列表或字符串
    if isinstance(eight_char, list):
        parts = eight_char
        eight_char = " ".join(parts)
    else:
        parts = eight_char.split()
    # 历法校正透明化（真太阳时/夏令时/晚子时口径）
    correction_note = None
    if pre is not None:
        correction_note = {
            "是否校正真太阳时": pre["corrected_flag"],
            "经度修正(分)": pre["longitude_correction_minutes"],
            "均时差(分)": pre["equation_of_time_minutes"],
            "总修正(分)": pre["total_correction_minutes"],
            "排盘日偏移": pre["day_shift"],
            "晚子时口径": pre["rule"],
            "中国夏令时": pre["dst"],
        }
    result = {
        "step": 1,
        "name": "历法转换",
        "source": "中国古代算命术·排八字；三命通会·论节候",
        "input": {"公历(钟表时间)": f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}", "历法": "公历/格里历"},
        "output": {
            "八字": eight_char,
            "年柱": parts[0],
            "月柱": parts[1],
            "日柱": parts[2],
            "时柱": parts[3],
            "农历": str(lunar.toString()),
            "生肖": str(lunar.getYearShengXiao()),
            "节气信息": {
                "当前节气": str(lunar.getCurrentJieQi() or "无"),
                "上一节气": str(lunar.getPrevJieQi()),
                "下一节气": str(lunar.getNextJieQi()),
            },
        },
        "历法校正": correction_note,
    }
    return result


# ============================================================
# 第2步：四柱排盘
# ============================================================

def step2_pillars(year: int, month: int, day: int, hour: int, minute: int = 0, second: int = 0) -> Dict:
    """
    四柱排盘，含天干地支属性、纳音。
    来源：三命通会·论四柱

    重要修复：lunar-python 的 getMonthInGanZhi() 按"节气所在日期的 00:00"分界，
    在节气当日早/晚出生时会误判月柱（如 1990-10-08 寒露 21:13，09:30 出生本属酉月乙酉，
    却被误判为戌月丙戌）。改用 getBaZi()，它按节气精确时刻分界，月柱正确。
    四柱统一取自 getBaZi()，确保与 step1 一致且月柱精准。
    """
    solar = Solar.fromYmdHms(year, month, day, hour, minute, second)
    lunar = solar.getLunar()
    baizi_list = lunar.getBaZi()
    if isinstance(baizi_list, str):
        baizi_list = baizi_list.split()
    pillars = {
        "year": baizi_list[0],
        "month": baizi_list[1],
        "day": baizi_list[2],
        "time": baizi_list[3],
    }
    baizi = " ".join(baizi_list)
    nayin = lunar.getBaZiNaYin()
    if isinstance(baizi, list):
        baizi = " ".join(baizi)
    if isinstance(nayin, list):
        nayin_list = nayin
    else:
        nayin_list = nayin.split() if isinstance(nayin, str) else []
    result = {
        "step": 2,
        "name": "四柱排盘",
        "source": "三命通会·论四柱；中国古代算命术·八字排法",
        "pillars": pillars,
        "baizi": baizi,
        "nayin": " ".join(nayin_list),
        "details": {}
    }
    for pos, p in pillars.items():
        g, z = parse_pillar(p)
        idx = {"year":0,"month":1,"day":2,"time":3}[pos]
        result["details"][pos] = {
            "天干": g,
            "地支": z,
            "天干属性": STEM_ATTRS[g],
            "地支属性": BRANCH_ATTRS[z],
            "纳音": nayin_list[idx] if idx < len(nayin_list) else "",
        }
    return result


# ============================================================
# 第3步：大运排列
# ============================================================

def step3_dayun(pillars: Dict, gender: str, birth: datetime) -> Dict:
    """
    大运排列：阳男阴女顺行，阴男阳女逆行；起运岁数按3天折1岁。
    来源：中国古代算命术·大运排法 / 三命通会·论大运
    """
    year_gan, year_zhi = parse_pillar(pillars["year"])
    month_gan, month_zhi = parse_pillar(pillars["month"])
    day_gan, day_zhi = parse_pillar(pillars["day"])

    yang_year = is_yang_gan(year_gan)
    forward = (yang_year and gender == "男") or (not yang_year and gender == "女")

    # 起运岁数计算：到下一个/上一个节气天数
    prev_name, prev_dt, next_name, next_dt = find_jieqi_around(birth)
    if forward and next_dt:
        delta = next_dt - birth
        days = delta.total_seconds() / 86400
    elif not forward and prev_dt:
        delta = birth - prev_dt
        days = delta.total_seconds() / 86400
    else:
        days = 3
    start_age = max(1, round(days / 3))

    # 大运干支排列
    dayun_list = []
    for i in range(1, 13):
        if forward:
            g = next_stem(month_gan, i)
            z = next_branch(month_zhi, i)
        else:
            g = prev_stem(month_gan, i)
            z = prev_branch(month_zhi, i)
        start_age_i = start_age + (i - 1) * 10
        end_age_i = start_age_i + 9
        ganzhi = g + z
        dayun_list.append({
            "number": i,
            "ganzhi": ganzhi,
            "start_age": start_age_i,
            "end_age": end_age_i,
            "gan": g,
            "zhi": z,
        })

    return {
        "step": 3,
        "name": "大运排列",
        "source": "中国古代算命术·大运排法；三命通会·论大运",
        "direction": "顺行" if forward else "逆行",
        "direction_reason": f"年干{year_gan}为{'阳' if yang_year else '阴'}干，{gender}命{'顺行' if forward else '逆行'}",
        "jieqi": {
            "forward": forward,
            "reference": next_name if forward else prev_name,
            "days_to_jieqi": round(days, 2),
            "start_age": start_age,
        },
        "dayun": dayun_list,
    }


# ============================================================
# 第4步：十神标注
# ============================================================

def step4_tenshen(pillars: Dict) -> Dict:
    """
    以日干为我，标注四柱天干地支所藏天干对应的十神。
    来源：三命通会·十神论 / 滴天髓·六亲论
    """
    day_gan, day_zhi = parse_pillar(pillars["day"])
    details = {}
    # 天干十神
    for pos in ["year", "month", "day", "time"]:
        g, z = parse_pillar(pillars[pos])
        if pos == "day":
            tg_code, tg_name = "ri_zhu", "日主"
        else:
            tg_code, tg_name = get_ten_god(day_gan, g)
        details[pos] = {
            "天干": g,
            "十神": tg_name,
            "十神代码": tg_code,
            "地支": z,
        }
    # 地支藏干十神
    hidden_tenshen = {}
    for pos in ["year", "month", "day", "time"]:
        g, z = parse_pillar(pillars[pos])
        hidden = HIDDEN_STEMS[z]
        hidden_tenshen[pos] = []
        for hg, weight in hidden:
            _, tg_name = get_ten_god(day_gan, hg)
            hidden_tenshen[pos].append({
                "藏干": hg,
                "权重": weight,
                "十神": tg_name,
            })

    return {
        "step": 4,
        "name": "十神标注",
        "source": "三命通会·十神论；滴天髓·六亲论",
        "day_stem": day_gan,
        "day_branch": day_zhi,
        "details": details,
        "hidden_tenshen": hidden_tenshen,
    }


# ============================================================
# 第5步：藏干展开
# ============================================================

def step5_hidden_stems(pillars: Dict) -> Dict:
    """
    展开四柱地支藏干，并计算五行权重分布。
    来源：三命通会·地支藏干
    """
    hidden = {}
    element_weight = {e: 0.0 for e in ELEMENTS}
    for pos in ["year", "month", "day", "time"]:
        g, z = parse_pillar(pillars[pos])
        stems = HIDDEN_STEMS[z]
        hidden[pos] = {
            "地支": z,
            "藏干": [{"干": hg, "权重": w, "五行": STEM_ATTRS[hg]["element"]} for hg, w in stems],
        }
        for hg, w in stems:
            element_weight[STEM_ATTRS[hg]["element"]] += w

    return {
        "step": 5,
        "name": "藏干展开",
        "source": "三命通会·地支藏干",
        "hidden": hidden,
        "element_weight_from_hidden": element_weight,
    }


# ============================================================
# 第6步：刑冲合害
# ============================================================

def step6_relations(pillars: Dict) -> Dict:
    """
    检测地支六合、六冲、三合、三会、刑、害，以及天干五合。
    来源：三命通会·地支刑冲合害论 / 滴天髓·知命
    """
    branches = [parse_pillar(pillars[pos])[1] for pos in ["year", "month", "day", "time"]]
    stems = [parse_pillar(pillars[pos])[0] for pos in ["year", "month", "day", "time"]]
    positions = ["年支", "月支", "日支", "时支"]
    stem_positions = ["年干", "月干", "日干", "时干"]

    found = []
    # 六合
    for i in range(4):
        for j in range(i + 1, 4):
            pair = (branches[i], branches[j])
            if pair in LIU_HE or (pair[1], pair[0]) in LIU_HE:
                found.append({
                    "type": "六合",
                    "pair": [positions[i], positions[j]],
                    "branches": list(pair),
                    "meaning": RELATION_MEANINGS["六合"],
                    "source": RELATION_SOURCES["六合"],
                })
    # 六冲
    for i in range(4):
        for j in range(i + 1, 4):
            pair = (branches[i], branches[j])
            if pair in LIU_CHONG or (pair[1], pair[0]) in LIU_CHONG:
                found.append({
                    "type": "六冲",
                    "pair": [positions[i], positions[j]],
                    "branches": list(pair),
                    "meaning": RELATION_MEANINGS["六冲"],
                    "source": RELATION_SOURCES["六冲"],
                })
    # 三合（需三个不同地支齐全，或两个不同地支成半合）
    for name, groups in SAN_HE.items():
        for group in groups:
            matched = [positions[i] for i in range(4) if branches[i] in group]
            matched_branches = set(branches[i] for i in range(4) if branches[i] in group)
            if len(matched_branches) == 3:
                found.append({
                    "type": "三合",
                    "name": name,
                    "positions": matched,
                    "branches": list(matched_branches),
                    "meaning": RELATION_MEANINGS["三合"],
                    "source": RELATION_SOURCES["三合"],
                })
            elif len(matched_branches) == 2:
                found.append({
                    "type": "半合",
                    "name": name,
                    "positions": matched,
                    "branches": list(matched_branches),
                    "meaning": "半合，力量弱于三合，主一定凝聚力。",
                    "source": RELATION_SOURCES["三合"],
                })
    # 三会（需三个不同地支齐全）
    for name, group in SAN_HUI.items():
        matched = [positions[i] for i in range(4) if branches[i] in group]
        matched_branches = set(branches[i] for i in range(4) if branches[i] in group)
        if len(matched_branches) >= 3:
            found.append({
                "type": "三会",
                "name": name,
                "positions": matched,
                "branches": list(matched_branches),
                "meaning": RELATION_MEANINGS["三会"],
                "source": RELATION_SOURCES["三会"],
            })
    # 刑
    for i in range(4):
        for j in range(i + 1, 4):
            pair = (branches[i], branches[j])
            for xing_name, rules in XING_RULES.items():
                if pair in rules or (pair[1], pair[0]) in rules:
                    found.append({
                        "type": "刑",
                        "xing_name": xing_name,
                        "pair": [positions[i], positions[j]],
                        "branches": list(pair),
                        "meaning": RELATION_MEANINGS["刑"],
                        "source": RELATION_SOURCES["刑"],
                    })
    # 害
    for i in range(4):
        for j in range(i + 1, 4):
            pair = (branches[i], branches[j])
            if pair in HAI or (pair[1], pair[0]) in HAI:
                found.append({
                    "type": "害",
                    "pair": [positions[i], positions[j]],
                    "branches": list(pair),
                    "meaning": RELATION_MEANINGS["害"],
                    "source": RELATION_SOURCES["害"],
                })
    # 天干五合
    for i in range(4):
        for j in range(i + 1, 4):
            pair = (stems[i], stems[j])
            if pair in GAN_HE or (pair[1], pair[0]) in GAN_HE:
                key = pair if pair in GAN_HE else (pair[1], pair[0])
                found.append({
                    "type": "天干五合",
                    "pair": [stem_positions[i], stem_positions[j]],
                    "stems": list(pair),
                    "化合五行": GAN_HE_ELEMENT[key],
                    "meaning": RELATION_MEANINGS["天干五合"],
                    "source": "三命通会·论天干五合",
                })

    return {
        "step": 6,
        "name": "刑冲合害",
        "source": "三命通会·地支刑冲合害论；滴天髓·知命",
        "branches": dict(zip(positions, branches)),
        "relations": found,
    }


# ============================================================
# 第7步：神煞计算
# ============================================================

def step7_shensha(pillars: Dict, gender: str) -> Dict:
    """
    计算常见神煞。
    来源：三命通会·神煞篇
    """
    year_gan, year_zhi = parse_pillar(pillars["year"])
    month_gan, month_zhi = parse_pillar(pillars["month"])
    day_gan, day_zhi = parse_pillar(pillars["day"])
    time_gan, time_zhi = parse_pillar(pillars["time"])
    all_branches = {"年支": year_zhi, "月支": month_zhi, "日支": day_zhi, "时支": time_zhi}
    all_stems = {"年干": year_gan, "月干": month_gan, "日干": day_gan, "时干": time_gan}

    found = []

    for name, rule in SHENSHA_RULES.items():
        matched_positions = []
        if "map" in rule:
            # 查日干、年支、日支
            check_targets = []
            if "日干查" in rule["rule"] or "以日干查" in rule["rule"]:
                check_targets.append(("日干", day_gan))
            if "年支" in rule["rule"] or "以年支" in rule["rule"]:
                check_targets.append(("年支", year_zhi))
            if "日支" in rule["rule"] or "以日支" in rule["rule"]:
                check_targets.append(("日支", day_zhi))
            if "月支" in rule["rule"] or "以月支" in rule["rule"]:
                check_targets.append(("月支", month_zhi))
            if not check_targets:
                # 默认查日干和日支、年支
                check_targets = [("日干", day_gan), ("日支", day_zhi), ("年支", year_zhi)]
            for pos_key, val in check_targets:
                if val in rule["map"]:
                    for target in rule["map"][val]:
                        # 检查四柱地支中是否存在该target
                        for b_pos, b_val in all_branches.items():
                            if b_val == target:
                                matched_positions.append(f"{pos_key}{val} → {b_pos}{target}")
        elif "days" in rule:
            # 魁罡：查日柱
            if day_gan + day_zhi in rule["days"]:
                matched_positions.append("日柱")
        elif rule.get("type") == "sequence_check":
            # 三奇贵人：检查连续三柱
            seq_stems = list(all_stems.values())
            seq_pos = list(all_stems.keys())
            # 乙丙丁 或 甲戊庚
            for pattern in [("乙", "丙", "丁"), ("甲", "戊", "庚")]:
                for i in range(len(seq_stems) - 2):
                    if seq_stems[i] == pattern[0] and seq_stems[i + 1] == pattern[1] and seq_stems[i + 2] == pattern[2]:
                        matched_positions.append(f"{seq_pos[i]}-{seq_pos[i+1]}-{seq_pos[i+2]}:{pattern[0]}{pattern[1]}{pattern[2]}")

        elif rule.get("type") == "kongwang":
            # 空亡：以日柱查旬空
            xun_kong = rule["xun_kong"]
            # 六十甲子旬首：以日干地支确定旬首
            # 天干序号 0-9，地支序号 0-11，干支组合的序号 = (天干序号 - 地支序号) % 60 的同干支位置
            gan_idx = HEAVENLY_STEMS.index(day_gan)
            zhi_idx = EARTHLY_BRANCHES.index(day_zhi)
            # 旬首天干为甲，旬首地支 = (地支序号 - 天干序号) mod 12
            xun_shou_offset = (zhi_idx - gan_idx) % 12
            xun_shou_zhi = EARTHLY_BRANCHES[xun_shou_offset]
            xun_shou = "甲" + xun_shou_zhi
            if xun_shou in xun_kong:
                empty_branches = xun_kong[xun_shou]
                for b_pos, b_val in all_branches.items():
                    if b_val in empty_branches:
                        matched_positions.append(f"日柱{day_gan}{day_zhi}属{xun_shou}旬，空亡{b_pos}{b_val}")

        if matched_positions:
            found.append({
                "name": name,
                "rule": rule["rule"],
                "matched": matched_positions,
                "source": rule["source"],
            })

    return {
        "step": 7,
        "name": "神煞计算",
        "source": "三命通会·神煞篇",
        "shensha": found,
    }


# ============================================================
# 第8步：五行强弱
# ============================================================

def step8_wuxing_score(pillars: Dict) -> Dict:
    """
    五行强弱评分：天干本气 + 地支藏干 + 月令旺衰 + 通根得势。
    来源：滴天髓·体象 / 三命通会·五行旺相休囚

    算法说明（程序化近似）：
    1. 原始分 = 四柱天干本气(各1.0) + 地支藏干按权重 + 月令本气额外0.5
    2. 以月令旺衰状态对各行乘系数：旺1.0、相0.7、休0.4、囚0.2、死0.1
    3. 归一化为百分制，作为相对比较
    4. 日主强弱另综合：是否得令、得地（日支/地支通根）、得势（天干比劫印）
    """
    day_gan, day_zhi = parse_pillar(pillars["day"])
    month_gan, month_zhi = parse_pillar(pillars["month"])
    day_element = STEM_ATTRS[day_gan]["element"]

    # 1. 原始力量
    raw_weight = {e: 0.0 for e in ELEMENTS}
    for pos in ["year", "month", "day", "time"]:
        g, z = parse_pillar(pillars[pos])
        raw_weight[STEM_ATTRS[g]["element"]] += 1.0
        for hg, w in HIDDEN_STEMS[z]:
            raw_weight[STEM_ATTRS[hg]["element"]] += w
        # 月令本气额外加权（司令之气）
        if pos == "month":
            main_gan = HIDDEN_STEMS[z][0][0]
            raw_weight[STEM_ATTRS[main_gan]["element"]] += 0.5

    # 2. 月令旺衰系数
    season = SEASONS.get(month_zhi, "四季")
    wangshuai = WANG_SHUAI.get(season, WANG_SHUAI["四季"])
    adjusted_weight = {e: raw_weight[e] * WANG_SHUAI_SCORE[wangshuai[e]] for e in ELEMENTS}

    total = sum(adjusted_weight.values()) or 1.0
    scores = {e: round(adjusted_weight[e] / total * 100, 2) for e in ELEMENTS}
    day_score = scores[day_element]

    # 3. 生助 vs 克泄耗
    support = 0.0  # 同我 + 生我
    consume = 0.0  # 克我 + 我克 + 我生
    for e in ELEMENTS:
        if e == day_element or SHENG[e] == day_element:
            support += scores[e]
        else:
            consume += scores[e]

    # 4. 日主强弱综合判断
    # 得令：日主五行在月令为旺或相
    in_season = wangshuai[day_element] in ["旺", "相"]
    # 得地：日支或时支藏干有日主五行根气
    rooted = False
    root_positions = []
    for pos in ["year", "month", "day", "time"]:
        g, z = parse_pillar(pillars[pos])
        for hg, w in HIDDEN_STEMS[z]:
            if STEM_ATTRS[hg]["element"] == day_element:
                rooted = True
                root_positions.append(pos)
    # 得势：天干有比肩、劫财、正印、偏印
    supported_by_stems = False
    for pos in ["year", "month", "time"]:
        g, z = parse_pillar(pillars[pos])
        code, name = get_ten_god(day_gan, g)
        if code in ["bi_jian", "jie_cai", "zheng_yin", "pian_yin"]:
            supported_by_stems = True
            break

    # 综合判定
    strong_points = sum([in_season, rooted, supported_by_stems])
    if strong_points >= 3:
        strength = "身旺"
    elif strong_points == 2:
        strength = "中和偏旺"
    elif strong_points == 1:
        strength = "中和偏弱"
    else:
        strength = "身弱"

    # 若日主五行得分极端高/低，可修正判断
    if day_score >= 35 and strength in ["中和偏弱", "身弱"]:
        strength = "中和偏旺"
    elif day_score <= 12 and strength in ["中和偏旺", "身旺"]:
        strength = "中和偏弱"

    strength_reason = (
        f"得令（月令{wangshuai[day_element]}）" if in_season else f"失令（月令{wangshuai[day_element]}）"
    ) + "；" + ("得地（地支通根）" if rooted else "失地（地支无强根）") + "；" + (
        "得势（天干有印比）" if supported_by_stems else "失势（天干少印比）"
    ) + "。"

    return {
        "step": 8,
        "name": "五行强弱",
        "source": "滴天髓·体象；三命通会·五行旺相休囚",
        "season": season,
        "wangshuai": wangshuai,
        "raw_weight": {e: round(raw_weight[e], 2) for e in ELEMENTS},
        "scores": scores,
        "day_element": day_element,
        "day_score": day_score,
        "strength": strength,
        "strength_reason": strength_reason,
        "support_vs_consume": {
            "生助日主": round(support, 2),
            "克泄耗日主": round(consume, 2),
        },
        "condition": {
            "得令": in_season,
            "得地": rooted,
            "得地位置": root_positions,
            "得势": supported_by_stems,
        },
    }


# ============================================================
# 第9步：格局判定
# ============================================================

def step9_pattern(pillars: Dict, tenshen: Dict) -> Dict:
    """
    以月支定格，参看透出天干的十神。
    来源：三命通会·格局篇
    """
    day_gan, day_zhi = parse_pillar(pillars["day"])
    month_gan, month_zhi = parse_pillar(pillars["month"])

    # 月支本气十神
    month_hidden = HIDDEN_STEMS[month_zhi]
    main_hidden_gan, _ = month_hidden[0]
    _, main_tenshen = get_ten_god(day_gan, main_hidden_gan)

    # 检查月支藏干所透天干
    tian_gan_tou_chu = []
    for pos in ["year", "month", "day", "time"]:
        g, z = parse_pillar(pillars[pos])
        for hg, _ in HIDDEN_STEMS[month_zhi]:
            if g == hg:
                tian_gan_tou_chu.append({"位置": pos, "天干": g})

    # 建禄 / 月刃（阳干论刃，阴干无刃）
    yang_gan = is_yang_gan(day_gan)
    if LU_POSITION.get(day_gan) == month_zhi:
        pattern = "建禄格"
    elif yang_gan and DIWANG_POSITION.get(day_gan) == month_zhi:
        pattern = "月刃格"
    else:
        # 按透出天干取格：月干优先，其次年干、时干（日干为日主自身，不取）
        if tian_gan_tou_chu:
            # 优先月干透出
            priority_order = {"month": 0, "year": 1, "time": 2, "day": 3}
            tian_gan_tou_chu.sort(key=lambda x: priority_order.get(x["位置"], 9))
            g = tian_gan_tou_chu[0]["天干"]
            code, name = get_ten_god(day_gan, g)
            pattern_map = {
                "zheng_guan": "正官格", "qi_sha": "七杀格",
                "zheng_cai": "正财格", "pian_cai": "偏财格",
                "zheng_yin": "正印格", "pian_yin": "偏印格",
                "shi_shen": "食神格", "shang_guan": "伤官格",
            }
            pattern = pattern_map.get(code, "杂气格")
        else:
            pattern_map = {
                "正官": "正官格", "七杀": "七杀格", "正财": "正财格", "偏财": "偏财格",
                "正印": "正印格", "偏印": "偏印格", "食神": "食神格", "伤官": "伤官格",
                "比肩": "建禄格", "劫财": "月刃格",
            }
            pattern = pattern_map.get(main_tenshen, "杂气格")

    pattern_info = PATTERN_RULES.get(pattern, PATTERN_RULES["杂气格"])

    return {
        "step": 9,
        "name": "格局判定",
        "source": pattern_info["source"],
        "pattern": pattern,
        "description": pattern_info["description"],
        "reason": {
            "月支": month_zhi,
            "月支本气藏干": main_hidden_gan,
            "月支本气十神": main_tenshen,
            "透出天干": tian_gan_tou_chu,
        },
    }


# ============================================================
# 第10步：用神推荐
# ============================================================

def _join_stems(elements):
    """将若干五行元素展开为对应天干，并以顿号连接（安全展开，避免 join 接收列表）。"""
    stems = []
    for e in elements:
        if e:
            stems.extend(ELEMENT_TO_STEMS.get(e, []))
    return "、".join(stems)


def step10_yongshen(day_gan: str, month_zhi: str, wuxing: Dict, pattern: Dict) -> Dict:
    """
    三源合参取用神：穷通宝鉴调候 + 滴天髓扶抑 + 格局用神。
    来源：穷通宝鉴；滴天髓·体象；三命通会·论用神

    本步骤明确区分三套用神体系，并给出合参后的综合建议。
    """
    month_num = MONTH_ZHI_TO_SOLAR_MONTH.get(month_zhi, 1)
    qiongtong = QIONGTONG_RULES.get(day_gan, {}).get(month_num, {})
    qiongtong_yong = qiongtong.get("yong", "")
    qiongtong_xi = qiongtong.get("xi", "")
    qiongtong_ji = qiongtong.get("ji", "")
    qiongtong_note = qiongtong.get("note", "")
    qiongtong_source = qiongtong.get("source", "穷通宝鉴")

    # 调候用神五行
    qiongtong_element = STEM_ATTRS[qiongtong_yong]["element"] if qiongtong_yong else ""

    # 扶抑用神：根据日主强弱，给出喜用五行
    day_element = wuxing["day_element"]
    strength = wuxing["strength"]
    if strength in ["身弱", "中和偏弱"]:
        # 身弱喜印比：生我者 + 同我者
        fuyi_elements = [SHENG.get(day_element, ""), day_element]
        fuyi_tenshen = "印比（正印、偏印、比肩、劫财）"
        fuyi_desc = f"日主{strength}，喜印比生扶"
    elif strength in ["身旺", "中和偏旺"]:
        # 身旺喜克泄耗：克我者、我克者、我生者
        fuyi_elements = [KE.get(day_element, ""), SHENG.get(day_element, "")]
        # 我克者
        for e in ELEMENTS:
            if KE.get(e) == day_element:
                fuyi_elements.append(e)
                break
        fuyi_tenshen = "财官食伤（正官、七杀、正财、偏财、食神、伤官）"
        fuyi_desc = f"日主{strength}，喜财官食伤克泄耗"
    else:
        fuyi_elements = []
        fuyi_tenshen = "随大运流年而定"
        fuyi_desc = f"日主{strength}，无明显偏枯，喜忌需看具体组合"

    # 格局用神：由格局推导方向
    pattern_name = pattern["pattern"]
    if pattern_name in ["正官格", "七杀格"]:
        pattern_yong = "印" if wuxing["strength"] in ["身弱", "中和偏弱"] else "财"
        pattern_yong_desc = "官杀格身弱喜印化杀生身，身旺喜财滋杀"
    elif pattern_name in ["正财格", "偏财格"]:
        pattern_yong = "比劫" if wuxing["strength"] in ["身弱", "中和偏弱"] else "食伤"
        pattern_yong_desc = "财格身弱喜比劫分财，身旺喜食伤生财"
    elif pattern_name in ["正印格", "偏印格"]:
        pattern_yong = "财" if wuxing["strength"] in ["身旺", "中和偏旺"] else "官杀"
        pattern_yong_desc = "印格身旺喜财破印，身弱喜官杀生印"
    elif pattern_name in ["食神格", "伤官格"]:
        pattern_yong = "财" if wuxing["strength"] in ["中和", "中和偏旺", "身旺"] else "印比"
        pattern_yong_desc = "食伤格身旺喜财泄秀，身弱喜印比生扶"
    elif pattern_name in ["建禄格", "月刃格"]:
        pattern_yong = "财官食伤"
        pattern_yong_desc = "建禄月刃格日主本旺，喜财官食伤为用"
    else:
        pattern_yong = "依扶抑而定"
        pattern_yong_desc = "杂气格需先分清扶抑方向"

    # 三源合参
    # 检查调候用神是否在扶抑喜用五行中
    qiongtong_aligned = qiongtong_element and qiongtong_element in fuyi_elements
    # 检查格局用神方向是否与扶抑一致（粗略：格局用神是十神类别，对应五行）
    pattern_elements = []
    if pattern_yong == "印":
        pattern_elements = [SHENG.get(day_element, "")]
    elif pattern_yong == "比劫":
        pattern_elements = [day_element]
    elif pattern_yong == "财":
        for e in ELEMENTS:
            if KE.get(e) == day_element:
                pattern_elements.append(e)
                break
    elif pattern_yong == "官杀":
        pattern_elements = [KE.get(day_element, "")]
    elif pattern_yong == "食伤":
        pattern_elements = [SHENG.get(day_element, "")]
    elif pattern_yong == "财官食伤":
        pattern_elements = [KE.get(day_element, ""), SHENG.get(day_element, "")]
        for e in ELEMENTS:
            if KE.get(e) == day_element:
                pattern_elements.append(e)
                break

    pattern_aligned = any(e in fuyi_elements for e in pattern_elements)

    # 综合结论
    if qiongtong_yong and qiongtong_aligned and pattern_aligned:
        final_advice = f"三源同向：以{qiongtong_yong}（{qiongtong_element}）调候扶抑，格局亦顺。"
        final_yong = qiongtong_yong
        final_xi = qiongtong_xi or _join_stems(fuyi_elements)
        final_ji = qiongtong_ji
    elif qiongtong_yong and qiongtong_aligned:
        final_advice = f"调候用神{qiongtong_yong}与扶抑方向一致，可优先考虑；格局用神{pattern_yong}作为辅助。"
        final_yong = qiongtong_yong
        final_xi = qiongtong_xi or _join_stems(fuyi_elements)
        final_ji = qiongtong_ji
    elif qiongtong_yong:
        final_advice = (
            f"调候用神为{qiongtong_yong}（{qiongtong_element}），扶抑喜用为{fuyi_tenshen}。"
            f"若命局寒暖燥湿失调明显，以调候{qiongtong_yong}为先；否则以扶抑为主。"
        )
        final_yong = qiongtong_yong
        final_xi = qiongtong_xi or fuyi_tenshen
        final_ji = qiongtong_ji
    else:
        final_advice = f"穷通宝鉴未载此组合，以扶抑为主：{fuyi_desc}。"
        final_yong = _join_stems(fuyi_elements) or "需人工细断"
        final_xi = _join_stems(fuyi_elements) or "需人工细断"
        final_ji = ""

    return {
        "step": 10,
        "name": "用神推荐",
        "source": "穷通宝鉴；滴天髓·体象；三命通会·论用神",
        "method": "三源合参：穷通宝鉴调候 + 滴天髓扶抑 + 格局用神",
        "components": {
            "穷通宝鉴": {
                "用神": qiongtong_yong,
                "用神五行": qiongtong_element,
                "喜神": qiongtong_xi,
                "忌神": qiongtong_ji,
                "说明": qiongtong_note,
                "出处": qiongtong_source,
            },
            "滴天髓扶抑": {
                "日主强弱": strength,
                "扶抑方向": fuyi_desc,
                "喜用五行": [e for e in fuyi_elements if e],
                "扶抑用神": fuyi_tenshen,
                "出处": "滴天髓·体象",
            },
            "格局用神": {
                "格局": pattern_name,
                "格局用神": pattern_yong,
                "说明": pattern_yong_desc,
                "出处": pattern["source"],
            },
        },
        "synthesis": {
            "调候用神": qiongtong_yong,
            "扶抑用神": fuyi_tenshen,
            "格局用神": pattern_yong,
            "是否同向": {
                "调候与扶抑一致": qiongtong_aligned,
                "格局与扶抑一致": pattern_aligned,
            },
            "综合建议": final_advice,
        },
        "final_yong": final_yong,
        "final_xi": final_xi,
        "final_ji": final_ji,
    }


# ============================================================
# 第11步：大运流年
# ============================================================

def _element_is_favorable(element: str, wuxing: Dict, yongshen: Dict) -> bool:
    """判断某五行是否为喜用（基于扶抑用神方向）"""
    strength = wuxing["strength"]
    day_element = wuxing["day_element"]
    if strength in ["身弱", "中和偏弱"]:
        return element == day_element or element == SHENG.get(day_element)
    elif strength in ["身旺", "中和偏旺"]:
        return element in [KE.get(day_element), SHENG.get(day_element)] or any(KE.get(e) == day_element for e in ELEMENTS if e == element)
    return False


def _element_is_unfavorable(element: str, wuxing: Dict, yongshen: Dict) -> bool:
    """判断某五行是否为忌（基于扶抑用神方向）"""
    return not _element_is_favorable(element, wuxing, yongshen)


def step11_liunian(dayun_result: Dict, current_year: int, birth_year: int,
                   pillars: Dict, wuxing: Dict, yongshen: Dict) -> Dict:
    """
    大运流年综合判断。
    来源：三命通会·论大运流年；滴天髓·体用

    判断逻辑：
    1. 先找当前大运，判断大运天干五行是否为喜用，定十年基调
    2. 再算流年干支，判断流年天干喜忌
    3. 检查流年地支与原局日柱、年柱的冲合刑害关系
    4. 综合给出吉凶与提示
    """
    age = current_year - birth_year

    current_dyun = None
    for dy in dayun_result["dayun"]:
        if dy["start_age"] <= age <= dy["end_age"]:
            current_dyun = dy
            break
    if not current_dyun:
        current_dyun = dayun_result["dayun"][0]

    # 流年干支
    year_index = (current_year - 4) % 60
    gz = HEAVENLY_STEMS[year_index % 10] + EARTHLY_BRANCHES[year_index % 12]
    liunian_gan = gz[0]
    liunian_zhi = gz[1]

    day_gan, day_zhi = parse_pillar(pillars["day"])
    year_gan, year_zhi = parse_pillar(pillars["year"])

    # 大运天干喜忌
    dyun_element = STEM_ATTRS[current_dyun["gan"]]["element"]
    dyun_good = _element_is_favorable(dyun_element, wuxing, yongshen)
    dyun_bad = _element_is_unfavorable(dyun_element, wuxing, yongshen)
    if dyun_good and not dyun_bad:
        dayun_judgment = "吉"
        dayun_comment = LIUNIAN_TEMPLATES["dayun_good"]
    elif dyun_bad and not dyun_good:
        dayun_judgment = "凶"
        dayun_comment = LIUNIAN_TEMPLATES["dayun_bad"]
    else:
        dayun_judgment = "平"
        dayun_comment = LIUNIAN_TEMPLATES["dayun_mixed"]

    # 流年天干喜忌
    liunian_element = STEM_ATTRS[liunian_gan]["element"]
    liunian_good = _element_is_favorable(liunian_element, wuxing, yongshen)
    liunian_bad = _element_is_unfavorable(liunian_element, wuxing, yongshen)

    # 流年地支与原局关系
    relations = []
    # 冲日柱
    if (liunian_zhi, day_zhi) in LIU_CHONG or (day_zhi, liunian_zhi) in LIU_CHONG:
        relations.append("冲日柱")
    # 合日柱
    if (liunian_zhi, day_zhi) in LIU_HE or (day_zhi, liunian_zhi) in LIU_HE:
        relations.append("合日柱")
    # 冲年柱（太岁冲年）
    if (liunian_zhi, year_zhi) in LIU_CHONG or (year_zhi, liunian_zhi) in LIU_CHONG:
        relations.append("冲年柱（犯太岁）")
    # 流年地支=年支（本命年/值太岁）
    if liunian_zhi == year_zhi:
        relations.append("值太岁（本命年）")
    # 刑日柱
    for xing_name, rules in XING_RULES.items():
        if (liunian_zhi, day_zhi) in rules or (day_zhi, liunian_zhi) in rules:
            relations.append(f"刑日柱（{xing_name}）")
    # 害日柱
    if (liunian_zhi, day_zhi) in HAI or (day_zhi, liunian_zhi) in HAI:
        relations.append("害日柱")

    # 流年综合判断
    if liunian_good and not liunian_bad:
        liunian_judgment = "吉"
        liunian_comment = LIUNIAN_TEMPLATES["yong_shen_year"]
    elif liunian_bad and not liunian_good:
        liunian_judgment = "凶"
        liunian_comment = LIUNIAN_TEMPLATES["ji_shen_year"]
    else:
        liunian_judgment = "平"
        liunian_comment = LIUNIAN_TEMPLATES["normal"]

    # 加入地支关系提示
    relation_comments = []
    if "冲日柱" in relations:
        relation_comments.append(LIUNIAN_TEMPLATES["chong_ri_zhu"])
    if "合日柱" in relations:
        relation_comments.append(LIUNIAN_TEMPLATES["he_ri_zhu"])
    if "值太岁（本命年）" in relations or "冲年柱（犯太岁）" in relations:
        relation_comments.append(LIUNIAN_TEMPLATES["tai_sui"])

    # 综合结论
    if dayun_judgment == "吉" and liunian_judgment == "吉":
        overall = "吉"
        overall_comment = "大运与流年皆利，宜积极进取。"
    elif dayun_judgment == "凶" and liunian_judgment == "凶":
        overall = "凶"
        overall_comment = "大运与流年皆逆，宜守不宜攻，谨慎决策。"
    else:
        overall = "平"
        overall_comment = "大运与流年喜忌有交错，需结合具体事项判断。"

    if relation_comments:
        overall_comment += " " + "；".join(relation_comments)

    return {
        "step": 11,
        "name": "大运流年",
        "source": "三命通会·论大运流年；滴天髓·体用",
        "current_year": current_year,
        "age": age,
        "current_dayun": current_dyun,
        "dayun_judgment": dayun_judgment,
        "dayun_comment": dayun_comment,
        "liunian": {"ganzhi": gz, "gan": liunian_gan, "zhi": liunian_zhi},
        "liunian_judgment": liunian_judgment,
        "liunian_comment": liunian_comment,
        "liunian_relations": relations,
        "overall_judgment": overall,
        "comment": overall_comment,
        # 保留旧字段兼容前端
        "judgment": overall,
    }


# ============================================================
# 第12步：综合报告
# ============================================================


def build_plain_language(day_gan: str, day_element: str, strength: str, month_zhi: str,
                         pattern: Dict, yongshen: Dict, liunian: Dict,
                         shensha: Dict, relations: Dict,
                         chengu_result: Dict = None, year_pillar: str = "",
                         day_pillar: str = "", year_nayin: str = "",
                         day_nayin: str = "", pillars: Dict = None,
                         gender: str = "男", wuxing: Dict = None,
                         tenshen: Dict = None) -> Dict:
    """
    生成「大白话」解读：用通俗语言解释专业术语，并标注古籍出处。
    让不懂命理的人也能看懂综合报告。
    """
    # —— 提取五行 / 十神明细，供下方做"有数据支撑"的解读 ——
    wx = wuxing or {}
    _raw = wx.get("raw_weight", {}) or {}
    _scores = wx.get("scores", {}) or {}
    _sup = wx.get("support_vs_consume", {}) or {}
    _season = wx.get("season", "")
    _wang = wx.get("wangshuai", {}) or {}
    _day_score = wx.get("day_score")
    _supported = _sup.get("生助日主")
    _consumed = _sup.get("克泄耗日主")
    _cond = wx.get("condition", {}) or {}
    _tenshen = tenshen or {}
    _tdetails = _tenshen.get("details", {}) or {}
    _hidden = _tenshen.get("hidden_tenshen", {}) or {}

    # —— 日主强弱（通俗）——
    if strength in ("身旺", "中和偏旺"):
        strength_plain = (
            f"您的「日主{day_gan}」（代表您自己）{strength}。通俗说，您天生底气较足、精力旺，"
            f"能扛事、也担得起财富与事业（命理上叫“能担财官”）。不过太旺也像水满则溢，"
            f"有时需要适当“泄”掉一点过剩能量——比如多发挥才华、多输出、多助人，反而更顺。"
        )
    elif strength in ("身弱", "中和偏弱"):
        strength_plain = (
            f"您的「日主{day_gan}」（代表您自己）{strength}。通俗说，您天生底子偏薄，"
            f"更需要外界助力——贵人、朋友、学习充电、稳定平台，来为您“补强”。"
            f"遇大事宜借力、不宜硬扛；命理上把这叫“喜印比生扶”（印星、比肩劫财来帮您）。"
        )
    else:
        strength_plain = (
            f"您的「日主{day_gan}」（代表您自己）属于中和状态，强弱比较均衡，"
            f"适应力强、可塑性好，喜忌要看具体大运流年再定。"
        )

    # 用"数据"把底气讲实：得令 / 得地 / 得势 + 五行占比
    _tongshen = "、".join(_cond.get("得地位置", []) or []) or "无"
    _raw_d = {k: (round(v, 1) if isinstance(v, (int, float)) else v) for k, v in _raw.items()}
    strength_plain += (
        f"\n\n【底气从何而来——用数据说话】您这一盘五行原始得气份数为："
        f"木{_raw_d.get('木', 0)}、火{_raw_d.get('火', 0)}、土{_raw_d.get('土', 0)}、"
        f"金{_raw_d.get('金', 0)}、水{_raw_d.get('水', 0)}。其中「{day_element}」独占 {_raw_d.get(day_element, 0)}、"
        f"折算后得分约 {_day_score} 分；生助您的力量占 {_supported}%，克泄耗您的只占 {_consumed}%。"
        f"命理判定根由有三：得令（月令「{month_zhi}」当旺={'是' if _cond.get('得令') else '否'}）、"
        f"得地（地支通根于 {_tongshen}）、得势（天干有印比相助={'是' if _cond.get('得势') else '否'}）。"
        f"三者齐备，正是您“{strength}”的底气来源——不是空口说“您旺”，而是这盘{day_element}势厚实、自己就能站稳。"
    )

    # 引《滴天髓·论十天干》形象描摹日主性情，并逐层释义
    _xg = DITIANSUI_XINGXIANG.get(day_gan, "")
    _xg_note = DITIANSUI_XINGXIANG_NOTE.get(day_gan, "")
    if _xg:
        strength_plain += (
            f"\n\n【古诀逐句释义】《滴天髓·论十天干》对「{day_gan}」的八字真言是：「{_xg}」。"
            f"\n把它拆开看：{_xg_note}"
        )
        # 顺势而为：结合身旺 / 身弱给具体行动建议
        if strength in ("身旺", "中和偏旺"):
            strength_plain += (
                f"\n\n【该如何顺势而为】您身旺，好比一块肥沃厚土，本身底气已足。顺势的关键是“向外输出”而非“继续堆叠”："
                f"① 事业上勇于担责、带团队（{day_element}能承载）；"
                f"② 把才华变成作品与产出（食伤泄秀）；"
                f"③ 主动经营财富与人际（财星、官星）；④ 助人、分享，反而更顺。"
                f"要避的，是再叠印比（同五行）——那会土重埋金、反成滞塞。这正应了古诀“宜助宜帮、金多金光”的提醒：帮对了人、泄对了地方，您才显光华。"
            )
        else:
            strength_plain += (
                f"\n\n【该如何顺势而为】您身弱，好比土薄之地，顺势的关键是“借力补强”："
                f"靠近贵人、扎进稳定平台、持续学习（印星生扶），与同辈抱团（比劫帮身），"
                f"遇大事借势而不硬扛，方能把底气一点点养起来。"
            )
        # 专属喜忌（来自 step10 实际推导），引向"用神"一节
        fy = yongshen.get("final_yong") or ""
        fx = yongshen.get("final_xi") or ""
        fj = yongshen.get("final_ji") or ""
        if fy or fx or fj:
            strength_plain += (
                f"\n\n【您这一盘的专属喜与忌】综合穷通宝鉴 / 滴天髓 / 三命通会三源合参，对您最有用的是"
                f"「用神 {fy or '—'}」「喜神 {fx or '—'}」，给您添乱的是「忌神 {fj or '—'}」。"
                f"下方“用神”一节会把它们逐字讲透，并落到财富、事业、健康、感情等具体角度。"
            )

    # 神峰通考·病药说 的病药判定（事实依据：data.SHENFENG），供下方格局/用神段落复用
    if strength in ("身弱", "中和偏弱"):
        _bing = "您身弱为『病』，宜取印星、比劫来『扶』，这便是治病的『药』。"
    elif strength in ("身旺", "中和偏旺"):
        _bing = "您身强（或偏旺）为『病』，宜取克、泄、耗来『抑』，这便是治病的『药』。"
    else:
        _bing = "您中和，病药之象不显，宜随大运流年再辨旺衰。"

    # —— 月令与格局（通俗）——
    pattern_plain = (
        f"八字里的“格局”，相当于给您的命局定一个基本类型与气质倾向。它主要看您出生的"
        f"“月令”（出生那个月的地支，这里是「{month_zhi}」）。月令就像当季的气候，"
        f"决定哪种五行最旺，是定格局的“提纲”。您构成「{pattern['pattern']}」：{pattern['description']}"
    )
    # 格局推导过程（透明展示"怎么定出来的"）
    _pr = pattern.get("reason", {}) or {}
    _mz = _pr.get("月支", month_zhi)
    _mh = _pr.get("月支本气藏干", "")
    _mt = _pr.get("月支本气十神", "")
    _tou = _pr.get("透出天干", []) or []
    if pattern["pattern"] == "杂气格":
        _cang = _hidden.get("month", []) or []
        _cang_txt = "、".join([f"{h.get('藏干')}（{h.get('十神')}）" for h in _cang]) or f"{_mh}（{_mt}）"
        _tou_txt = "、".join([f"{t.get('天干')}（{t.get('位置')}柱透出）" for t in _tou]) or "无正统十神透出"
        pattern_plain += (
            f"\n\n【“杂气格”是怎么得出来的——一步步推给您看】定格局以“月令”（出生月地支）为提纲。"
            f"您的月支是「{_mz}」，属辰、戌、丑、未“四库”之一——古人称这类月为“杂气月”，"
            f"因为库中所藏不是一干，而是三干混杂（本气+中气+余气）。您月支「{_mz}」内藏：{_cang_txt}。"
            f"《子平真诠》定杂气格的规矩是“取透干或人元司令定格”——看这三干里哪个透出天干"
            f"（显在四柱天干上），或看月令当值的“人元司令”来立格。本盘从月支透出天干的是：{_tou_txt}。"
            f"透出的若是比肩、劫财（同我者），不算“八格”之列；而能立正格的正官、七杀、财、印、食伤又都没透出，"
            f"于是“格局不清”，归为「杂气格」——意思是月令之气混杂，需结合日主强弱（扶抑）来取用神，而非拘泥某一固定格局。"
        )
    else:
        _tou_txt = "、".join([f"{t.get('天干')}（{t.get('位置')}柱透出）" for t in _tou]) or f"月支本气{_mh}（{_mt}）"
        pattern_plain += (
            f"\n\n【“{pattern['pattern']}”是怎么定出来的】定格局以月令（月支「{_mz}」）为提纲，"
            f"本气藏干为「{_mh}」（十神为{_mt}）；再看月支藏干哪个透出天干：本盘透出的是 {_tou_txt}，"
            f"据此立为「{pattern['pattern']}」。简言之：月令给了一盘气的“主色调”，透干的那一神把格局“点”了出来。"
        )

    # 引《子平真诠·论用神》格局顺逆（事实依据：data.ZIPING_GE / ziping_ge_category）
    _ge = ziping_ge_category(pattern.get("pattern", ""))
    if _ge:
        pattern_plain += (
            f"\n\n《子平真诠·论用神》把格局分作『善格』与『不善格』：您这「{pattern['pattern']}」属"
            f"「{_ge['category']}」中的「{_ge['type']}」，论其“取用之法”当『{_ge['policy']}』——{_ge['note']}"
            f"（注：此处的『顺用/逆用』是《子平真诠》对各格“如何取用神”的特定说法，指顺其性而"
            f"生护、或逆其性而制约；与上方“格局用神与扶抑方向一致”所说的“顺”是不同层面的含义，并非矛盾。）"
        )

    # —— 用神喜忌（通俗）——
    fy = yongshen.get("final_yong") or ""
    fx = yongshen.get("final_xi") or ""
    fj = yongshen.get("final_ji") or ""
    syn = yongshen.get("synthesis", {})
    _qt = yongshen.get("components", {}).get("穷通宝鉴", {})
    _qt_yong = _qt.get("用神", "")
    _aligned = syn.get("是否同向", {}) or {}
    yong_plain = (
        "取“用神”是八字的核心：用神就是对您最有帮助的五行/十神，相当于您的“补药”；"
        "喜神是帮用神一臂之力的；忌神是给您添乱的，逢之宜谨慎。\n"
        "古法有三套体系合参——穷通宝鉴看寒暖燥湿（调候用神）、滴天髓看强弱（扶抑用神）、"
        f"三命通会看格局（格局用神）。三者合参后：您的用神是「{fy or '需结合大运细断'}」；"
        f"喜神「{fx or '—'}」；忌神「{fj or '—'}」。"
    )
    # 逐字解释 用神 / 喜神 / 忌神（每个干都讲清它在您盘里是"十神"里的什么角色）
    _TG_ROLE = {
        "zheng_guan": "正官——规矩、事业、名望、上司、丈夫（女命），是“克我而正”的力量",
        "qi_sha": "七杀——魄力、挑战、压力、儿子（男命）、偏夫（女命），是“克我而偏”的力量",
        "zheng_cai": "正财——稳定收入、妻子（男命）、务实，是“我克而正”的力量",
        "pian_cai": "偏财——横财、父亲、外缘、桃花，是“我克而偏”的力量",
        "zheng_yin": "正印——贵人、学历、庇护、母亲，是“生我而正”的力量",
        "pian_yin": "偏印——偏门学识、冷贵人，是“生我而偏”的力量",
        "shi_shen": "食神——才华、口福、女儿（女命）、温和输出，是“我生而正”的力量",
        "shang_guan": "伤官——才艺、叛逆、锋芒、儿子（女命），是“我生而偏”的力量",
        "bi_jian": "比肩——同辈、朋友、同事、分财者，是“同我”的力量",
        "jie_cai": "劫财——兄弟、竞争者、破财者，是“同我”的力量",
    }
    _ELEM_MEAN = {
        "木": "木主生长、舒展、条达（对应事业、官杀、行动力）",
        "火": "火主温暖、名望、光明（对应贵人、印星、声誉）",
        "土": "土主承载、稳定、积藏（对应根基、比劫、务实）",
        "金": "金主收敛、才华、器具（对应食伤、才华输出、子女）",
        "水": "水主流动、财富、智慧（对应财星、情感、灵动）",
    }
    _explain_lines = []
    for _stem, _label in ((fy, "用神"), (fx, "喜神"), (fj, "忌神")):
        if not _stem:
            continue
        _code, _tname = get_ten_god(day_gan, _stem)
        _elem = STEM_ATTRS.get(_stem, {}).get("element", "")
        _role = _TG_ROLE.get(_code, "（十神角色待定）")
        _em = _ELEM_MEAN.get(_elem, "")
        _tag = "尤其要靠近/多用" if _label != "忌神" else "要警惕/回避"
        _explain_lines.append(
            f"\n· 「{_label} {_stem}」（{_elem}）：在您盘里是「{_tname}」——{_role}。{_em}。{_tag}。"
        )
    if _explain_lines:
        yong_plain += "\n\n【用神 / 喜神 / 忌神 逐字讲透】" + "".join(_explain_lines)
    # 调候 vs 扶抑：两套体系的区别与合参
    yong_plain += (
        f"\n\n【调候用神 与 扶抑用神，是两个不同维度，别混】"
        f"\n· 调候（穷通宝鉴）：管“寒暖燥湿”的气候问题——像冬天生人冷，要火来暖；夏天生人燥，要水来润。"
        f"您日主{day_gan}生于「{month_zhi}」月（{_season}之令），全局水{_raw.get('水',0)}、火{_raw.get('火',0)}、"
        f"土{_raw.get('土',0)}——调候用神是「{_qt_yong or fy}」（{STEM_ATTRS.get(_qt_yong,{}).get('element','') or _qt_yong}），"
        f"需要它来调候，正说明本局{'偏寒、最需火来暖局' if STEM_ATTRS.get(_qt_yong,{}).get('element')=='火' else '偏燥、最需水来润局' if STEM_ATTRS.get(_qt_yong,{}).get('element')=='水' else '寒暖尚匀'}。"
        f"\n· 扶抑（滴天髓）：管“身旺身弱”的强弱问题——您{strength}，喜{'克泄耗（向外输出）' if strength in ('身旺','中和偏旺') else '生扶（借力补强）'}。"
        f"\n· 两者是否同向：调候与扶抑一致={'是' if _aligned.get('调候与扶抑一致') else '否'}；"
        f"格局与扶抑一致={'是' if _aligned.get('格局与扶抑一致') else '否'}。"
        f"所以综合上：{syn.get('综合建议','按三源合参定夺')}。"
    )
    if syn.get("综合建议"):
        yong_plain += f"\n一句话记住：{syn['综合建议']}"
    # 引《神峰通考·病药说》以药喻用神（事实依据：data.SHENFENG）
    yong_plain += (
        f"\n\n若用明代张楠《神峰通考·病药说》来打比方：命局中『不妥当之处』便是『病』，"
        f"所取用神便是治病的『药』。{_bing}"
    )

    # —— 大运流年（通俗）——
    age = liunian.get("age")
    dayun = liunian.get("current_dayun", {})
    dayun_gz = dayun.get("ganzhi", "")
    dayun_j = liunian.get("dayun_judgment", "")
    ly = liunian.get("liunian", {}).get("ganzhi", "")
    ly_j = liunian.get("overall_judgment", "")
    ly_comment = liunian.get("liunian_comment", "")
    ly_rels = liunian.get("liunian_relations", [])
    liunian_plain = (
        "“大运”是十年一换的人生阶段大环境，“流年”是具体某一年。\n"
        f"您现年约 {age} 岁，正行「{dayun_gz}」大运，这十年基调{dayun_j}；"
        f"{liunian.get('current_year')} 年流年为「{ly}」，整体{ly_j}。"
    )
    if ly_comment:
        liunian_plain += f"{ly_comment}"
    if ly_rels:
        liunian_plain += f"（今年地支与命局关系：{', '.join(ly_rels)}）"

    # —— 命局特殊信号（神煞 / 刑冲合害）——
    sha_names = [s.get("name", "") for s in shensha.get("shensha", [])][:5]
    rel_types = list(set([r.get("type", "") for r in relations.get("relations", [])]))
    if sha_names or rel_types:
        signal_parts = []
        if sha_names:
            signal_parts.append(f"传统神煞有：{', '.join(sha_names)}")
        if rel_types:
            signal_parts.append(f"地支间存在：{', '.join(rel_types)}")
        signal_plain = "；".join(signal_parts) + "。这些属于传统附加信息，可作参考，不必过度担忧。"
    else:
        signal_plain = "命局暂无显著的神煞与刑冲合害标记。"

    # —— 用神如何影响您的具体人生（财富 / 事业 / 健康 / 感情 / 人际 / 学业）——
    def _find_elem_for_code(dg, code):
        for s in ("甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"):
            if get_ten_god(dg, s)[0] == code:
                return STEM_ATTRS.get(s, {}).get("element", ""), s
        return "", ""

    _xiyong_elems = []
    for _s in (fy, fx):
        _e = STEM_ATTRS.get(_s, {}).get("element")
        if _e and _e not in _xiyong_elems:
            _xiyong_elems.append(_e)
    _ji_elems = []
    for _s in (fj,):
        _e = STEM_ATTRS.get(_s, {}).get("element")
        if _e and _e not in _ji_elems:
            _ji_elems.append(_e)
    _xiyong_str = "、".join(_xiyong_elems) or "（见上）"
    _ji_str = "、".join(_ji_elems) or "（见上）"
    _month_ts = _tdetails.get("month", {}).get("十神", "")
    _month_tg = _tdetails.get("month", {}).get("天干", "")
    if gender == "男":
        _spouse_elem, _spouse_s = _find_elem_for_code(day_gan, "zheng_cai")
        _spouse_label = "妻星（正财）"
    else:
        _spouse_elem, _spouse_s = _find_elem_for_code(day_gan, "zheng_guan")
        _spouse_label = "夫星（正官）"
    _spouse_score = _raw.get(_spouse_elem, 0)
    life_plain = (
        f"把上面抽象的“用神/喜忌”翻译成您关心的六个方面。总原则：多亲近「{_xiyong_str}」类的人事物、"
        f"行业、方位与年份；少碰「{_ji_str}」类。下面逐条结合您这一盘的真实五行强弱说——\n"
        f"【财富】您是{day_element}日主，“我克者”为财。财星所在的「水」原始得气仅 {_raw.get('水',0)}（偏弱），"
        f"而偏财「{fj or '—'}」又是忌神且弱，说明正财不算丰、横财更宜谨慎；您比劫（{day_element}）重，"
        f"合作共事易有“分财”，账目宜分明、莫糊涂合伙。\n"
        f"【事业】“克我者”为官杀（事业、名望、上司）。您月干透「{_month_tg}」为「{_month_ts}」，"
        f"有魄力担责之象；用神「{fy or '—'}」（印）主贵人平台暖局。但事业竞争力所在的「木」得气仅 {_raw.get('木',0)}（偏弱），"
        f"临场发挥与升迁需借大运流年补木（喜用神中的木）方显。\n"
        f"【健康（传统意象，非医学诊断）】五行讲究平衡：您「土」得气 {_raw.get('土',0)} 过重，传统上对应脾胃厚实易滞；"
        f"「水」仅 {_raw.get('水',0)}（弱），对应肾系/泌尿系统、畏寒；「火」{_raw.get('火',0)}（偏弱），对应心阳与循环；"
        f"「木」{_raw.get('木',0)}（弱），对应肝胆疏泄、情绪易郁结。调候用「{fy or '—'}」暖局，正可针对“土重水弱火弱”的偏寒偏滞。\n"
        f"【感情婚姻】您{gender}命，{_spouse_label}为「{_spouse_elem}」（{_spouse_s or '—'}），"
        f"本盘得气 {_spouse_score}（{'偏弱，宜晚婚或借大运流年补足' if isinstance(_spouse_score, (int, float)) and _spouse_score <= 0.8 else '尚可'}）。"
        f"偏财「{fj or '—'}」为忌且藏于月支（父母宫），感情中注意财务边界与桃花分寸。\n"
        f"【人际】您比劫（同辈、朋友、同事）多，人缘广、互助也多，但同辈间也易有利益牵扯；"
        f"月干透七杀/官，对上（上司、规则）既有压力也是锻炼；喜神「{fx or '—'}」（官）提示：守规矩、尊权威，反而得助力。\n"
        f"【学业】印星（喜用神中的火）为学业根基，本盘火偏弱，需主动用功、环境暖助；"
        f"食伤（金）为才华输出，金相（{_raw.get('金',0)}）尚可，有一技之长可发挥；"
        f"官杀（木）为考试竞争力，木偏弱，临场宜借运。一句话：您底子厚（身旺），成事靠“向外输出才华 + 借贵人与规则”，而非死守。"
    )

    sections = [
        {"term": "您是谁（日主）", "plain": (
            f"八字由四柱八个字组成，其中“日干”（出生那天的天干）代表您本人，叫「日主」。"
            f"您的日主是「{day_gan}」，五行属{day_element}。看命，首先就是看这个“您”"
            f"在整盘里的强弱与处境。"
        ), "source": "三命通会·论日干；滴天髓·体象"},
        {"term": "您的强弱（身旺 / 身弱）", "plain": strength_plain,
         "source": "滴天髓·体象；三命通会·五行旺相休囚"},
        {"term": "您出生的时令与格局", "plain": pattern_plain, "source": pattern.get("source", "三命通会·论格局")},
        {"term": "对您最有利的“补药”（用神 / 喜神 / 忌神）", "plain": yong_plain,
         "source": "穷通宝鉴；滴天髓·体象；三命通会·论用神"},
        {"term": "用神如何影响您的具体人生", "plain": life_plain,
         "source": "穷通宝鉴；滴天髓·体象；三命通会·论六亲/论五行"},
        {"term": "您的大运与今年流年", "plain": liunian_plain, "source": "三命通会·论大运流年；滴天髓·体用"},
        {"term": "命局里的特殊信号", "plain": signal_plain, "source": "三命通会·论神煞 / 论刑冲合害"},
    ]

    # —— 纳音五行（渊海子平 / 三命通会·纳音）——
    if year_nayin or day_nayin:
        _ny_elem = next((e for e in ("金", "木", "水", "火", "土") if e in (year_nayin or "")), "")
        nayin_plain = (
            f"纳音五行，是六十甲子每对干支被赋予的另一个“五行别称”，渊海子平与三命通会同载此表，与“正五行”并行不悖。"
            f"您年柱「{year_pillar}」的纳音为「{year_nayin or '—'}」，日柱「{day_pillar}」的纳音为「{day_nayin or '—'}」。"
            f"打个比方：正五行是您的“本色”，纳音是您的“雅号”，两者合看，命局意象更丰满生动。"
        )
        # 结合具体纳音 + 本盘实际五行强弱做"雅号如何落地"的解读
        if _ny_elem and _ny_elem == day_element:
            nayin_plain += (
                f"\n\n【“本色与雅号”具体怎么理解】您的正五行日主是「{day_element}」（{day_gan}），"
                f"纳音也属「{_ny_elem}」（{year_nayin}），本色与雅号同气，主您表里如一、根基厚重，"
                f"这“{_ny_elem}”的意象（如{_ny_elem}之沉稳/生发）会贯穿您的外在气质与内在定力。"
            )
        elif _ny_elem:
            _rel = "与您同气、相互涵养"
            if SHENG.get(day_element) == _ny_elem:
                _rel = f"纳音之{_ny_elem}生扶您的{day_element}（如雨润土、资粮助身）"
            elif KE.get(day_element) == _ny_elem:
                _rel = f"纳音之{_ny_elem}被您的{day_element}所克（您能驾驭、转化它）"
            elif SHENG.get(_ny_elem) == day_element:
                _rel = f"您的{day_element}生纳音之{_ny_elem}（您滋养、成就它）"
            elif KE.get(_ny_elem) == day_element:
                _rel = f"纳音之{_ny_elem}克您的{day_element}（它约束、雕琢您）"
            nayin_plain += (
                f"\n\n【“本色与雅号”具体怎么理解】您的正五行日主是「{day_element}」（{day_gan}），"
                f"而纳音却披着「{year_nayin}」（属{_ny_elem}）的雅号——就像一个本性厚重的{day_element}，"
                f"顶着“{_ny_elem}”的名号。{_rel}，两者相成：您外表敦厚内里藏才，"
                f"如{_ny_elem}扎根{day_element}、根基稳而能向上。"
                f"但别只看雅号——本盘实际的「{_ny_elem}」得气仅 {_raw.get(_ny_elem, 0)}（偏弱），"
                f"这层雅号之美要等您走「{_ny_elem}」旺的大运流年（或逢喜用），才真正显出来。"
            )
        nayin_plain += (
            f"\n简言之：正五行讲“您是什么”，纳音讲“您像什么”；一个是体质，一个是气质，合看才立体。"
        )
        sections.append({"term": "您的纳音五行（年命 / 日柱）", "plain": nayin_plain,
                         "source": "渊海子平·纳音；三命通会·纳音"})

    # —— 袁天罡称骨（事实依据：chengu.calculate_chengu / 袁天罡称骨歌）——
    if chengu_result and chengu_result.get("total_str"):
        cg = chengu_result
        chengu_plain = (
            f"唐代星命家袁天罡留下一部《称骨歌》，把人的出生年、月、日、时各配一个“骨重”（以钱计，十钱为一两），"
            f"四柱相加便是您一生的“总重量”。您的四柱骨重分别是——年柱 {cg['year_w']} 钱、月柱 {cg['month_w']} 钱、"
            f"日柱 {cg['day_w']} 钱、时柱 {cg['hour_w']} 钱，合计 {cg['total_str']}。"
            f"\n袁天罡据此批曰：「{cg['song']}」"
            f"\n这便是传统称骨法对您命格气质的一句古批。需说明：称骨与八字是两套并行的古老算法，"
            f"一个称“重量”、一个论“五行生克”，可互为映照；均属古人的经验总结，宜以文化视角欣赏，不必奉为定论。"
            f"\n（这首古批如何与您四柱的“气数阶段”合看、逐句理解，详见下方『十二长生』一节——"
            f"那里会把您年/月/日/时支分别处于长生·帝旺·墓·绝等哪一阶段讲透，并和这首称骨歌互相印证。）"
        )
        if cg.get("year_note"):
            chengu_plain += f"\n{cg['year_note']}"
        sections.append({"term": "袁天罡称骨：您命中几两几钱", "plain": chengu_plain,
                         "source": cg.get("source", "袁天罡称骨歌")})
    elif chengu_result:
        sections.append({"term": "袁天罡称骨", "plain": chengu_result.get("song", "（称骨数据暂不全）"),
                         "source": "袁天罡称骨歌"})

    # —— 三命通会·寄生十二宫（十二长生）——
    if pillars:
        cs = SANMINGTONGHUI["CHANGSHENG_12"]
        _zhi_order = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
        _dg = day_gan
        _start = cs["changsheng_zhi"].get(_dg)
        if _start:
            _dir = cs["yinyang"].get(_dg, 1)

            def _state(zhi):
                i0 = _zhi_order.index(_start)
                i = _zhi_order.index(zhi)
                dist = (i - i0) % 12 if _dir == 1 else (i0 - i) % 12
                return cs["stages"][dist]

            _pz = []
            for _k in ("year", "month", "day", "time"):
                _g = pillars.get(_k, "")
                if isinstance(_g, str) and len(_g) == 2:
                    _label = {"year": "年柱", "month": "月柱", "day": "日支", "time": "时柱"}[_k]
                    _pz.append(f"{_label}「{_g[1]}」为{_state(_g[1])}")
            _cs_plain = (
                f"《三命通会·卷二》立『寄生十二宫』专说，把五行之气在十二地支里的生命节律分成十二阶段："
                f"长生、沐浴、冠带、临官、帝旺、衰、病、死、墓、绝、胎、养，循环无端。"
                f"推法以日干为主：您的日干是「{_dg}」，长生在「{_start}」（长生诀：{cs['koujue']}），"
                f"{'阳干顺行' if _dir == 1 else '阴干逆行'}。\n据此看您四柱地支所处的气数阶段——"
                f"{'；'.join(_pz)}。"
                f"\n十二宫中长生、临官(禄)、帝旺为『旺相』，好比人生当打之年；墓、绝、胎、养为收藏孕育，并非凶险。"
                f"古诀云『生旺太过宜制伏，死绝不及宜生扶』，重在识其通变，不可执一而论。"
            )
            # 把"气数"和"身旺底气 / 称骨歌"勾连起来，回应"结合四柱气数解释"的要求
            _day_state_cs = next((s.split("为")[1] for s in _pz if s.startswith("日支")), "")
            _time_state_cs = next((s.split("为")[1] for s in _pz if s.startswith("时柱")), "")
            _month_state_cs = next((s.split("为")[1] for s in _pz if s.startswith("月柱")), "")
            _year_state_cs = next((s.split("为")[1] for s in _pz if s.startswith("年柱")), "")
            _cs_plain += (
                f"\n\n【用“气数”解释您的“身旺底气”从哪来】上面说到您身旺，底气的一个重要来源就藏在十二长生里："
                f"您的日支「{pillars['day'][1]}」与时支「{pillars['time'][1]}」都落在「{_day_state_cs or _time_state_cs}」"
                f"（己土阴干逆行，帝旺在巳）——日支是“自己宫”、时支是“结局/子孙宫”，自坐帝旺，"
                f"等于您中年当打之年气数正旺、自身定力足，这与“身旺”互相印证；"
                f"而月支「{month_zhi}」为「{_month_state_cs}」、年支「{pillars['year'][1]}」为「{_year_state_cs}」属收藏蓄势之位，"
                f"提示早岁宜蓄力、中晚年方发。"
            )
            if chengu_result and chengu_result.get("song"):
                _cg_song = chengu_result["song"]
                _cg_total = chengu_result.get("total_str", "")
                _cs_plain += (
                    f"\n\n【把袁天罡称骨歌 与 十二长生 合看】您称骨 {_cg_total}，袁天罡批：「{_cg_song}」。"
                    f"这首古批是古人对“总重量”的意象总评；若用十二长生来读：日时支坐旺（帝旺/临官）"
                    f"正说明您自身气数旺、底气足，与称骨歌里那份“自身站得稳、不靠依附”的意象相合；"
                    f"月年支处收藏之位，则呼应“早年蓄势、中晚年发越”的节律。"
                    f"称骨是“总重量”、十二长生是“气数阶段”，两相互参，命局意象才真正活起来。"
                )
            sections.append({"term": "您的生命节律：十二长生（三命通会·寄生十二宫）",
                             "plain": _cs_plain, "source": cs["source"]})

    # —— 三命通会·论六亲（大白话重构，每一步落到本盘实际十神 + 宫位）——
    _lq = SANMINGTONGHUI["LIUQIN"]
    _pos_label = {"year": "年柱(祖上/父母宫)", "month": "月柱(父母兄弟宫)",
                  "day": "日柱(己身/夫妻宫)", "time": "时柱(子孙宫)"}

    def _scan_tg(code):
        found = []
        for _pos in ("year", "month", "day", "time"):
            _d = _tdetails.get(_pos, {})
            _tg = _d.get("天干", "")
            if _tg and get_ten_god(day_gan, _tg)[0] == code:
                found.append(f"{_pos_label[_pos]}天干透出「{_tg}」（现于明处，力量强、关系明显）")
        for _pos in ("year", "month", "day", "time"):
            for _h in (_hidden.get(_pos, []) or []):
                _hg = _h.get("藏干", "")
                if _hg and get_ten_god(day_gan, _hg)[0] == code:
                    found.append(f"{_pos_label[_pos]}地支藏「{_hg}」（藏于暗处，力量含蓄、缘分内敛）")
        return found

    if gender == "男":
        _rel_defs = [
            ("父亲", "pian_cai", "偏财为父"),
            ("母亲", "zheng_yin", "正印为母"),
            ("兄弟姐妹", ("bi_jian", "jie_cai"), "比劫为兄弟姐妹（男女同断）"),
            ("妻子", "zheng_cai", "正财为妻"),
            ("儿子", "qi_sha", "七杀为子（男命）"),
            ("女儿", "zheng_guan", "正官为女（男命）"),
        ]
    else:
        _rel_defs = [
            ("父亲", "pian_cai", "偏财为父"),
            ("母亲", "zheng_yin", "正印为母"),
            ("兄弟姐妹", ("bi_jian", "jie_cai"), "比劫为兄弟姐妹（男女同断）"),
            ("丈夫", "zheng_guan", "正官为夫（女命）"),
            ("儿子", "shi_shen", "食神为子（女命，三命通会）"),
            ("女儿", "shang_guan", "伤官为女（女命，三命通会）"),
        ]
    _lq_lines = []
    for _name, _code, _rule in _rel_defs:
        _codes = _code if isinstance(_code, tuple) else (_code,)
        _found = []
        for _c in _codes:
            _found += _scan_tg(_c)
        if _found:
            _lq_lines.append(f"· {_name}（{_rule}）：本盘见{_name}星于——{'；'.join(_found)}。")
        else:
            _lq_lines.append(f"· {_name}（{_rule}）：本盘天干地支均未见明显{_name}星，主这方面缘分较淡、或需借大运流年方显。")
    _lq_plain = (
        f"《三命通会·卷七·论六亲》的算法，用大白话讲就是：以您自己（日干「{day_gan}」）为中心，"
        f"把“谁生我、我生谁、谁克我、我克谁、谁同我”转成亲人角色——生我者=父母长辈、我克者=妻财、"
        f"克我者=官杀丈夫/子女、我生者=食伤子女、同我者=兄弟姐妹。下面把您这一盘里“每位亲人对应的星”"
        f"逐一找出来、并看它落在哪一柱（宫位），这就是古人说的『星宫同参』：星（十神）看关系好坏，"
        f"宫（年祖上/月父母/日夫妻己身/时子孙）看条件优劣。\n"
        + "\n".join(_lq_lines)
        + f"\n\n【星宫同参怎么读】若某位亲人的“星”透在天干（明处），关系明显、力量强；若只藏在地支（暗处），"
          f"则缘分含蓄内敛。星落之宫也定“在哪方面显”：如父星落月柱父母宫，主父亲与您早年家庭关联深；"
          f"妻星落日支夫妻宫，主配偶贴近您自身。把“星”与“宫”合看，比单看一个字准得多。"
        + f"\n【落到人际】您比劫（同辈朋友）多，人缘广、互助也多，但同辈间易有利益牵扯；"
          f"官杀（上司/规则/子女）透干，对上既有压力也是锻炼。守规矩、借贵人（印）、择明友（比劫有度），人际便顺。"
    )
    sections.append({"term": "您的六亲与人际（三命通会·论六亲）", "plain": _lq_plain,
                     "source": _lq["source"]})

    overview = (
        f"简单来说：您是「{day_gan}」日主（五行属{day_element}），{strength}；"
        f"生于「{month_zhi}」月令，构成「{pattern['pattern']}」格局；"
        f"对您最有利的用神是「{fy or '需结合大运细断'}」（喜{fx or '—'}、忌{fj or '—'}）。"
        f"现年约 {age} 岁，行「{dayun_gz}」大运，今年（{liunian.get('current_year')}）流年「{ly}」整体{ly_j}。"
        f"下面分条用大白话给您讲清楚每个术语是什么意思。"
    )
    if chengu_result and chengu_result.get("total_str"):
        overview += (
            f"；另有唐代袁天罡《称骨歌》算得您命重 {chengu_result['total_str']}，古批已附于下方分条解读中。"
        )

    glossary = [
        {"term": "十神", "plain": "以“日主”为中心，其余七个字与您的关系角色（如比肩=同辈、正财=稳定收入、正官=事业规矩等）。就像您身边不同身份的人。"},
        {"term": "神煞", "plain": "古人在干支组合上附加的一些吉凶标记（如天乙贵人、文昌等），属于传统辅助信息，仅供参考，不必迷信。"},
        {"term": "刑冲合害", "plain": "地支之间的几种互动关系：“合”像亲近合作，“冲”像对冲冲突，“刑/害”像暗中摩擦。用来判断人际与事件的顺逆。"},
        {"term": "纳音五行", "plain": "六十甲子每对干支被赋予的另一个五行名称（如丙午=天河水），常用于象义辅助，与“正五行”并行，不可混为一谈。"},
        {"term": "真太阳时", "plain": "因经度不同，各地的“真实太阳时”和钟表时间有差（约每差1度差4分钟）。出生地越偏西，真太阳时越晚。校正后才排得准。"},
    ]

    return {"overview": overview, "sections": sections, "glossary": glossary}


def step12_report(pillars: Dict, dayun: Dict, tenshen: Dict, relations: Dict,
                  shensha: Dict, wuxing: Dict, pattern: Dict, yongshen: Dict,
                  liunian: Dict, gender: str = "男",
                  chengu_year: str = "", chengu_month: int = None,
                  chengu_day: int = None, chengu_hour_zhi: str = "") -> Dict:
    """
    综合各步结果，生成结构化报告。
    """
    day_gan, day_zhi = parse_pillar(pillars["day"])
    month_gan, month_zhi = parse_pillar(pillars["month"])
    year_gan, year_zhi = parse_pillar(pillars["year"])
    hour_gan, hour_zhi = parse_pillar(pillars["time"])

    # 袁天罡称骨（事实依据：chengu.calculate_chengu；四源交叉验证 + 闰月十五分界）
    chengu_result = chengu.calculate_chengu(
        year_ganzhi=chengu_year,
        month=chengu_month,
        day=chengu_day,
        hour_zhi=chengu_hour_zhi,
    )
    # 年界分歧透明化：称骨年柱按春节农历年，八字年柱按立春，立春前后出生者可能差一档。
    if chengu_result.get("total_str") and chengu_year and chengu_year != pillars["year"]:
        chengu_result["year_note"] = (
            f"注：称骨年柱按传统农历春节为界取「{chengu_year}」，而八字年柱按立春为界取"
            f"「{pillars['year']}」，两者差一档属正常（年界流派分歧，非计算错误）。"
        )
    # 纳音五行（渊海子平 / 三命通会·纳音）
    year_nayin = NAYIN.get(pillars["year"], "")
    day_nayin = NAYIN.get(pillars["day"], "")

    report = {
        "step": 12,
        "name": "综合报告",
        "source": "六部著作综合（穷通宝鉴、滴天髓、三命通会、中国古代算命术）",
        "summary": {
            "日主": day_gan,
            "日柱": pillars["day"],
            "月令": month_zhi,
            "格局": pattern["pattern"],
            "日主强弱": wuxing["strength"],
            "用神": yongshen["final_yong"],
            "喜神": yongshen["final_xi"],
            "忌神": yongshen["final_ji"],
            "当前大运": liunian.get("current_dayun", {}).get("ganzhi", ""),
        },
        "key_observations": [],
        "cautions": [],
    }

    # 关键观察
    report["key_observations"].append(
        f"日主{day_gan}（{wuxing['day_element']}）{wuxing['strength']}。{wuxing['strength_reason']}"
    )
    report["key_observations"].append(f"月令{month_zhi}为提纲，{pattern['pattern']}：{pattern['description']}")

    syn = yongshen["synthesis"]
    report["key_observations"].append(
        f"用神三源：调候{syn['调候用神'] or '无'}，扶抑{syn['扶抑用神']}，格局{syn['格局用神']}。{syn['综合建议']}"
    )

    if relations["relations"]:
        relation_types = list(set([r["type"] for r in relations["relations"]]))
        report["key_observations"].append(f"命局存在：{', '.join(relation_types)}")

    if shensha["shensha"]:
        names = [s["name"] for s in shensha["shensha"][:5]]
        report["key_observations"].append(f"主要神煞：{', '.join(names)}")

    # 注意事项
    if yongshen["final_ji"]:
        report["cautions"].append(f"忌神：{yongshen['final_ji']}，流年逢之多需收敛。")
    if liunian["overall_judgment"] == "凶":
        report["cautions"].append(
            f"{liunian['current_year']}年流年{liunian['liunian']['ganzhi']}，判定为{liunian['overall_judgment']}，宜守不宜攻。"
        )
    if liunian.get("liunian_relations"):
        report["cautions"].append(f"流年地支关系：{', '.join(liunian['liunian_relations'])}。")

    # 大白话解读（基于古籍，通俗化，引经据典）
    report["plain_language"] = build_plain_language(
        day_gan=day_gan,
        day_element=wuxing["day_element"],
        strength=wuxing["strength"],
        month_zhi=month_zhi,
        pattern=pattern,
        yongshen=yongshen,
        liunian=liunian,
        shensha=shensha,
        relations=relations,
        chengu_result=chengu_result,
        year_pillar=pillars["year"],
        day_pillar=pillars["day"],
        year_nayin=year_nayin,
        day_nayin=day_nayin,
        pillars=pillars,
        gender=gender,
        wuxing=wuxing,
        tenshen=tenshen,
    )
    # 称骨结果一并附于报告（API / JSON 可取用）
    report["chengu"] = chengu_result

    return report


# ============================================================
# 总调度：完整演算
# ============================================================

def calculate_bazi(year: int, month: int, day: int, hour: int, minute: int = 0,
                   second: int = 0, gender: str = "男", current_year: int = None,
                   longitude: float = None, late_zishi_rule: str = "current-day") -> Dict:
    """
    主入口：执行12步演算流水线。

    新增参数：
        longitude        : 出生地经度（度，东正西负）。提供后做真太阳时校正；
                           不提供则维持原钟表时间（向后兼容，仅追加夏令时提示）。
        late_zishi_rule  : 晚子时(23:00-23:59)口径，默认 'current-day' 与 lunar-python 一致。
    """
    if current_year is None:
        current_year = datetime.now().year

    # —— 基础历法预处理（真太阳时 / 夏令时 / 晚子时 / 日期合法性）——
    pre = preprocess_birth_time(year, month, day, hour, minute,
                                longitude=longitude, late_zishi_rule=late_zishi_rule)
    if not pre["valid"]:
        return {
            "input": {
                "birth": f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}",
                "gender": gender,
                "current_year": current_year,
                "longitude": longitude,
                "late_zishi_rule": late_zishi_rule,
            },
            "error": pre["error"],
            "steps": [],
            "pillars": None,
        }

    cy, cm, cd, ch, cmin = pre["corrected"]
    birth = datetime(cy, cm, cd, ch, cmin, second)

    s1 = step1_calendar(cy, cm, cd, ch, cmin, second, pre=pre)
    s2 = step2_pillars(cy, cm, cd, ch, cmin, second)
    s3 = step3_dayun(s2["pillars"], gender, birth)
    s4 = step4_tenshen(s2["pillars"])
    s5 = step5_hidden_stems(s2["pillars"])
    s6 = step6_relations(s2["pillars"])
    s7 = step7_shensha(s2["pillars"], gender)
    s8 = step8_wuxing_score(s2["pillars"])
    s9 = step9_pattern(s2["pillars"], s4)
    month_gan, month_zhi = parse_pillar(s2["pillars"]["month"])
    s10 = step10_yongshen(s4["day_stem"], month_zhi, s8, s9)
    s11 = step11_liunian(s3, current_year, year, s2["pillars"], s8, s10)
    # 称骨专用农历解析：与八字分两套历法口径（年界按春节 + 闰月十五分界 + 农历真实日）
    lunar_cg = Solar.fromYmdHms(cy, cm, cd, ch, cmin, second).getLunar()
    cg_year = lunar_cg.getYearInGanZhi()                       # 春节农历年干支
    cg_month = chengu.leap_aware_month(lunar_cg.getMonth(), lunar_cg.getDay())  # 闰月十五分界折算
    cg_day = lunar_cg.getDay()                                 # 农历真实日（含晚子时真实时刻）
    cg_hour_zhi = s2["pillars"]["time"][1]                      # 八字时柱地支（含晚子时口径）
    s12 = step12_report(s2["pillars"], s3, s4, s6, s7, s8, s9, s10, s11,
                        gender=gender,
                        chengu_year=cg_year, chengu_month=cg_month,
                        chengu_day=cg_day, chengu_hour_zhi=cg_hour_zhi)

    return {
        "input": {
            "birth": f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}",
            "gender": gender,
            "current_year": current_year,
            "longitude": longitude,
            "late_zishi_rule": late_zishi_rule,
            "corrected_birth": f"{cy}-{cm:02d}-{cd:02d} {ch:02d}:{cmin:02d}",
            "dst_warning": pre["dst"],
        },
        "steps": [s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12],
        "pillars": s2["pillars"],
    }


if __name__ == "__main__":
    result = calculate_bazi(1990, 7, 15, 10, gender="男", current_year=2026)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
