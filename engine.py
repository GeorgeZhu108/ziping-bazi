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
    ELEMENT_TO_STEMS, YONGSHEN_PRIORITY
)

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
        final_xi = qiongtong_xi or "、".join(ELEMENT_TO_STEMS.get(e, []) for e in fuyi_elements if e)
        final_ji = qiongtong_ji
    elif qiongtong_yong and qiongtong_aligned:
        final_advice = f"调候用神{qiongtong_yong}与扶抑方向一致，可优先考虑；格局用神{pattern_yong}作为辅助。"
        final_yong = qiongtong_yong
        final_xi = qiongtong_xi or "、".join(ELEMENT_TO_STEMS.get(e, []) for e in fuyi_elements if e)
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
        final_yong = "、".join(ELEMENT_TO_STEMS.get(e, []) for e in fuyi_elements if e) or "需人工细断"
        final_xi = "、".join(ELEMENT_TO_STEMS.get(e, []) for e in fuyi_elements if e) or "需人工细断"
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

def step12_report(pillars: Dict, dayun: Dict, tenshen: Dict, relations: Dict,
                  shensha: Dict, wuxing: Dict, pattern: Dict, yongshen: Dict,
                  liunian: Dict) -> Dict:
    """
    综合各步结果，生成结构化报告。
    """
    day_gan, day_zhi = parse_pillar(pillars["day"])
    month_gan, month_zhi = parse_pillar(pillars["month"])

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
    s12 = step12_report(s2["pillars"], s3, s4, s6, s7, s8, s9, s10, s11)

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
