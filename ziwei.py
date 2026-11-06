# -*- coding: utf-8 -*-
"""紫微斗数排盘核心（纯 Python 移植）

溯源（非臆造，逐条可核对）：
  · 排盘流程与安星口诀 = iztro (SylarLong/iztro, MIT) 的 src/star/location.ts + src/star/majorStar.ts
    + src/astro/palace.ts + src/astro/astro.ts
  · 四化表 / 辅星表 / 宫名 / 五行局映射 = Renhuai123/ziwei-doushu (MIT) 的 lib/ziwei/constants.ts + sihua.ts
  · 农历/四柱(立春年界) = lunar-python（与八字引擎同源，已交叉验证）

覆盖范围（核心排盘）：
  命宫/身宫 → 十二宫(含宫干支) → 五行局 → 十四主星(紫微系逆布/天府系顺布)
  → 本命四化(禄权科忌) → 主要辅星(禄存羊陀马、魁钺、左右、昌曲、红鸾天喜、地空地劫、火铃)
  → 起大限(大运) → 流年落宫

口径约定（与 iztro 默认一致，已显式标注）：
  · 年界：立春换年（与八字年柱同源）。
  · 月：农历月（非节气月）；闰月前半月用上月、后半月用本月（fix_leap=True）。
  · 时辰：23:00–00:59 为子时；晚子时(23:00–23:59) 归次日（iztro normalizeDayBoundary 默认）。
"""
import datetime
from lunar_python import Solar

STEMS = "甲乙丙丁戊己庚辛壬癸"          # 天干 0-9
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"   # 地支 0-11（子=0）

# 十二宫名（以命宫为起点顺时针）：命宫,兄弟,夫妻,子女,财帛,疾厄,迁移,交友,官禄,田宅,福德,父母
PALACE_NAMES = ["命宫", "兄弟宫", "夫妻宫", "子女宫", "财帛宫", "疾厄宫",
                "迁移宫", "交友宫", "官禄宫", "田宅宫", "福德宫", "父母宫"]

# 五虎遁：年干 → 寅月(正月)天干索引（甲己→丙2 乙庚→戊4 丙辛→庚6 丁壬→壬8 戊癸→甲0）
WUHU_BASE = {0: 2, 5: 2, 1: 4, 6: 4, 2: 6, 7: 6, 3: 8, 8: 8, 4: 0, 9: 0}

# 五行局：纳音取数 → 局数（水二局2 木三局3 金四局4 土五局5 火六局6）
ELEMENT_TO_JU = {"水": 2, "木": 3, "金": 4, "土": 5, "火": 6}
JU_NAMES = {2: "水二局", 3: "木三局", 4: "金四局", 5: "土五局", 6: "火六局"}

# 四化表：年干索引 → [化禄, 化权, 化科, 化忌]（与 Renhuai123/ziwei-doushu constants.ts 逐字一致）
SI_HUA_TABLE = {
    0: ["廉贞", "破军", "武曲", "太阳"],   # 甲
    1: ["天机", "天梁", "紫微", "太阴"],   # 乙
    2: ["天同", "天机", "文昌", "廉贞"],   # 丙
    3: ["太阴", "天同", "天机", "巨门"],   # 丁
    4: ["贪狼", "太阴", "右弼", "天机"],   # 戊
    5: ["武曲", "贪狼", "天梁", "文曲"],   # 己
    6: ["太阳", "武曲", "太阴", "天同"],   # 庚
    7: ["巨门", "太阳", "文曲", "文昌"],   # 辛
    8: ["天梁", "紫微", "左辅", "武曲"],   # 壬
    9: ["破军", "巨门", "太阴", "贪狼"],   # 癸
}

# 天魁/天钺：年干 → [天魁branch, 天钺branch]
TIANKUI_TABLE = {
    0: [1, 7], 1: [0, 8], 2: [11, 9], 3: [11, 9], 4: [1, 7],
    5: [0, 8], 6: [1, 7], 7: [6, 2], 8: [3, 5], 9: [3, 5],
}
# 禄存：年干 → branch；天马：年支三合 → branch（寅午戌→申8 申子辰→寅2 巳酉丑→亥11 亥卯未→巳5）
LUCUN_TABLE = {0: 2, 1: 3, 2: 5, 3: 6, 4: 5, 5: 6, 6: 8, 7: 9, 8: 11, 9: 0}
TIANMA_TABLE = {2: 8, 6: 8, 10: 8, 8: 2, 0: 2, 4: 2, 5: 11, 9: 11, 1: 11, 11: 5, 3: 5, 7: 5}

# 十四主星中文名
MAJOR_STARS = ["紫微", "天机", "太阳", "武曲", "天同", "廉贞",
               "天府", "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军"]
# 紫微系（紫微起逆数）：索引偏移 0,1,3,4,5,8 对应下列非空星
ZIWEI_GROUP = ["紫微", "天机", "", "太阳", "武曲", "天同", "", "", "廉贞"]
# 天府系（天府起顺数）：索引偏移 0..10 对应下列非空星
TIANFU_GROUP = ["天府", "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "", "", "", "破军"]

# 主星性质（倪师体系，摘自 Renhuai123/ziwei-doushu constants.ts STAR_DESCRIPTIONS）
STAR_INFO = {
    "紫微": "帝王·尊贵·独立（土，中性偏吉）", "天机": "智慧·机变·谋略（木，吉）",
    "太阳": "阳刚·官贵·慷慨（火，吉）", "武曲": "财富·刚毅·果断（金，中性）",
    "天同": "温和·享福·随缘（水，吉）", "廉贞": "才艺·刑囚·桃花（火，凶中带吉）",
    "天府": "财库·稳重·保守（土，吉）", "太阴": "柔美·财富·阴柔（水，吉）",
    "贪狼": "欲望·桃花·多才（木，中性）", "巨门": "口舌·是非·善辩（水，凶中带吉）",
    "天相": "辅佐·行政·印绶（水，吉）", "天梁": "荫护·医药·长辈（土，吉）",
    "七杀": "将星·果决·孤克（金，凶）", "破军": "开创·变动·破坏（水，凶）",
}


def fix_index(n, mod=12):
    return ((n % mod) + mod) % mod


# ───────────────────────── 农历/时间预处理 ─────────────────────────
def _normalize_time(y, m, d, h):
    """晚子时(23:00–23:59)归次日子时（iztro normalizeDayBoundary 默认口径）。
    返回 (date, time_branch)。time_branch: 子0…亥11。"""
    if h == 23:
        nxt = datetime.date(y, m, d) + datetime.timedelta(days=1)
        return nxt, 0
    return datetime.date(y, m, d), ((h + 1) // 2) % 12


def _lunar_month_index(lunar, fix_leap=True):
    """农历月 → 0-based 宫索引（寅月/正月=0）。闰月前半月用上月、后半月用本月。"""
    mm = lunar.getMonth()  # 正月=1，闰月为负
    if mm < 0:
        real = -mm
        if fix_leap and lunar.getDay() <= 15:
            real -= 1
            if real == 0:
                real = 12
        mm = real
    return mm - 1  # 0-based：正月→0


# ───────────────────────── 核心排盘 ─────────────────────────
def get_soul_body(month0, time_branch):
    """命宫/身宫索引（寅=0…丑=11）。
    安命身宫诀：寅起正月顺数至生月，逆数生时为命宫；顺数生时为身宫。"""
    soul = fix_index(month0 - time_branch)
    body = fix_index(month0 + time_branch)
    return soul, body


def get_five_elements_class(stem_idx, branch_idx):
    """五行局（以命宫干支定）。纳音取数：干 甲乙1丙丁2戊己3庚辛4壬癸5；
    支 子午丑未1 寅申卯酉2 辰巳戌亥3；相加>5减5；1木 2金 3水 4火 5土。"""
    stem_num = stem_idx // 2 + 1
    # 地支取数：子午丑未=1；寅申卯酉=2；辰戌巳亥=3
    branch_map = {0: 1, 6: 1, 1: 1, 7: 1, 2: 2, 8: 2, 3: 2, 9: 2, 4: 3, 10: 3, 5: 3, 11: 3}
    branch_num = branch_map[branch_idx]
    idx = stem_num + branch_num
    while idx > 5:
        idx -= 5
    return {1: 3, 2: 4, 3: 2, 4: 6, 5: 5}[idx]  # 局数


def get_ziwei_tianfu(lunar_day, ju_value):
    """起紫微星诀（iztro location.ts getStartIndex）：
    六五四三二，酉午亥辰丑；局数除日数，商数宫前走；若见数无余，便要起虎口；日数小于局，还直宫中守。
    返回 (ziwei_index, tianfu_index)，宫索引 寅=0。"""
    offset = -1
    while True:
        offset += 1
        divisor = lunar_day + offset
        quotient = divisor // ju_value
        if divisor % ju_value == 0:
            break
    quotient %= 12
    ziwei = quotient - 1
    if offset % 2 == 0:
        ziwei += offset
    else:
        ziwei -= offset
    ziwei = fix_index(ziwei)
    tianfu = fix_index(12 - ziwei)
    return ziwei, tianfu


def place_major_stars(ziwei_idx, tianfu_idx):
    """按 紫微逆数 / 天府顺数 安十四主星。返回 {宫索引: [星名,...]}。"""
    stars = {i: [] for i in range(12)}
    for off, name in enumerate(ZIWEI_GROUP):
        if name:
            stars[fix_index(ziwei_idx - off)].append(name)
    for off, name in enumerate(TIANFU_GROUP):
        if name:
            stars[fix_index(tianfu_idx + off)].append(name)
    return stars


def place_minor_stars(year_stem, year_branch, lunar_month1, time_branch):
    """主要辅星（禄存羊陀马、魁钺、左右、昌曲、红鸾天喜、地空地劫、火铃）。返回 {宫索引:[(星名,类型)]}。"""
    res = {i: [] for i in range(12)}
    # 禄存 / 擎羊(禄前) / 陀罗(禄后)
    lu = LUCUN_TABLE[year_stem]
    res[lu].append(("禄存", "lucky"))
    res[fix_index(lu + 1)].append(("擎羊", "sha"))
    res[fix_index(lu - 1)].append(("陀罗", "sha"))
    # 天马（年支三合）
    res[TIANMA_TABLE[year_branch]].append(("天马", "lucky"))
    # 天魁 / 天钺（年干）
    kui, yue = TIANKUI_TABLE[year_stem]
    res[kui].append(("天魁", "lucky"))
    res[yue].append(("天钺", "lucky"))
    # 左辅（辰+月-1 顺）/ 右弼（戌-月-1 逆）
    zuo = fix_index(4 + (lunar_month1 - 1))
    you = fix_index(10 - (lunar_month1 - 1))
    res[zuo].append(("左辅", "lucky"))
    res[you].append(("右弼", "lucky"))
    # 文昌（戌-时 逆）/ 文曲（辰+时 顺）
    res[fix_index(10 - time_branch)].append(("文昌", "lucky"))
    res[fix_index(4 + time_branch)].append(("文曲", "lucky"))
    # 红鸾（卯-年支 逆）/ 天喜（对宫）
    hl = fix_index(3 - year_branch)
    res[hl].append(("红鸾", "sha"))
    res[fix_index(hl + 6)].append(("天喜", "sha"))
    # 地空（亥-时 逆）/ 地劫（亥+时 顺）
    res[fix_index(11 - time_branch)].append(("地空", "sha"))
    res[fix_index(11 + time_branch)].append(("地劫", "sha"))
    # 火星 / 铃星（年支三合 + 时支顺数）
    if year_branch in (2, 6, 10):      # 寅午戌
        huo, ling = 1, 3
    elif year_branch in (8, 0, 4):      # 申子辰
        huo, ling = 2, 10
    elif year_branch in (5, 9, 1):      # 巳酉丑
        huo, ling = 3, 10
    else:                               # 亥卯未
        huo, ling = 9, 10
    res[fix_index(huo + time_branch)].append(("火星", "sha"))
    res[fix_index(ling + time_branch)].append(("铃星", "sha"))
    return res


def calculate_ziwei(year, month, day, hour, gender, fix_leap=True, current_year=None):
    """排一张紫微命盘。返回结构化 dict。
    gender: '男'/'女'。"""
    d, time_branch = _normalize_time(year, month, day, hour)
    lunar = Solar.fromYmdHms(d.year, d.month, d.day, 0, 0, 0).getLunar()
    bazi = lunar.getBaZi()                       # 立春年界 年/月/日/时
    year_stem = STEMS.index(bazi[0][0])
    year_branch = BRANCHES.index(bazi[0][1])
    lunar_month0 = _lunar_month_index(lunar, fix_leap)
    lunar_day = lunar.getDay()

    soul, body = get_soul_body(lunar_month0, time_branch)
    # 命宫干 = 五虎遁(年干) 在命宫地支；五行局以命宫干支定
    soul_stem = fix_index(WUHU_BASE[year_stem] + soul, 10)
    ju_value = get_five_elements_class(soul_stem, fix_index(soul + 2))  # 命宫地支=(soul+2)%12
    ju_name = JU_NAMES[ju_value]

    ziwei_idx, tianfu_idx = get_ziwei_tianfu(lunar_day, ju_value)
    major = place_major_stars(ziwei_idx, tianfu_idx)
    minor = place_minor_stars(year_stem, year_branch, lunar_month0 + 1, time_branch)

    # 十二宫：宫索引 i(寅=0) 地支=(2+i)%12；宫干=(五虎遁寅月干 + i)%10；宫名自命宫起顺时针
    palaces = []
    for i in range(12):
        p_branch = fix_index(2 + i)
        p_stem = fix_index(WUHU_BASE[year_stem] + i, 10)
        p_name = PALACE_NAMES[fix_index(i - soul)]
        stars = [{"name": s, "type": "major", "info": STAR_INFO.get(s, "")} for s in major[i]]
        for s, t in minor[i]:
            stars.append({"name": s, "type": t, "info": ""})
        palaces.append({
            "index": i, "name": p_name,
            "branch": BRANCHES[p_branch], "stem": STEMS[p_stem],
            "branch_idx": p_branch, "stem_idx": p_stem,
            "stars": stars,
            "is_ming": i == soul, "is_shen": i == body,
            "empty": len(major[i]) == 0,
        })

    # 本命四化（年干）
    sihua = dict(zip(["化禄", "化权", "化科", "化忌"], SI_HUA_TABLE[year_stem]))

    # 起大限：阳男阴女顺行、阴男阳女逆行；起始年龄=局数，每十年一宫
    yin_yang_year = year_branch % 2           # 0=阳 1=阴
    yin_yang_gender = 0 if gender == "男" else 1
    same = (yin_yang_year == yin_yang_gender)
    decadals = []
    for i in range(12):
        idx = fix_index(soul + i) if same else fix_index(soul - i)
        start_age = ju_value + 10 * i
        d_stem = fix_index(WUHU_BASE[year_stem] + idx, 10)
        d_branch = fix_index(2 + idx)
        decadals.append({
            "palace_index": idx, "palace_name": PALACE_NAMES[fix_index(idx - soul)],
            "branch": BRANCHES[d_branch], "stem": STEMS[d_stem],
            "age_range": [start_age, start_age + 9],
        })

    chart = {
        "input": {"year": year, "month": month, "day": day, "hour": hour,
                  "gender": gender, "fix_leap": fix_leap,
                  "birth_used": f"{d.year}-{d.month:02d}-{d.day:02d}（晚子时归次日后）" if hour == 23 else f"{year}-{month:02d}-{day:02d}"},
        "lunar": {"year_stem": STEMS[year_stem], "year_branch": BRANCHES[year_branch],
                  "lunar_month": lunar.getMonth(), "lunar_day": lunar_day,
                  "time_branch": BRANCHES[time_branch]},
        "soul_index": soul, "body_index": body,
        "soul_branch": BRANCHES[fix_index(soul + 2)], "body_branch": BRANCHES[fix_index(body + 2)],
        "wuxing_ju": ju_value, "wuxing_ju_name": ju_name,
        "ziwei_index": ziwei_idx, "tianfu_index": tianfu_idx,
        "ziwei_branch": BRANCHES[fix_index(ziwei_idx + 2)],
        "tianfu_branch": BRANCHES[fix_index(tianfu_idx + 2)],
        "palaces": palaces,
        "sihua": sihua,
        "decadals": decadals,
    }
    chart["interpretation"] = interpret_ziwei(chart)
    return chart


def flow_year(chart, flow_year_gregorian, month=1, day=1):
    """流年落宫：取流年地支对应的宫。返回该宫 dict（含流年四化）。
    flow_year_gregorian 取该公历年的年月日（默认 1/1）。紫微年界=立春，
    故传入实际日期（而非年初）可正确取当年立春后的流年。"""
    lunar = Solar.fromYmdHms(flow_year_gregorian, month, day, 0, 0, 0).getLunar()
    fy = lunar.getBaZi()[0]
    fy_branch = BRANCHES.index(fy[1])
    fy_stem = STEMS.index(fy[0])
    for p in chart["palaces"]:
        if p["branch_idx"] == fy_branch:
            return {"year": flow_year_gregorian, "stem": fy[0], "branch": fy[1],
                    "palace_name": p["name"], "sihua": dict(zip(["化禄", "化权", "化科", "化忌"], SI_HUA_TABLE[fy_stem]))}
    return None


# ───────────────────────── 释义知识库（标准斗数赋文释义） ─────────────────────────
# 星曜性质与释义：综合《紫微斗数全书》星曜赋文与中州/倪师一脉释义（与 STAR_INFO 同源）。
STAR_INTERP = {
    "紫微": {"nature": "北斗帝星（土，尊贵）",
             "meaning": "紫微为北斗主星，化气曰「尊」，主领导力、格局与自我要求。喜左辅右弼「文武相佐」、天相昌曲「禄马侍从」则格局清贵；独坐无辅易流于孤高。《紫微斗数全书》云：「紫微居子午，位至公卿」。",
             "source": "《紫微斗数全书·星曜释义》"},
    "天机": {"nature": "南斗善星（木，智慧）",
             "meaning": "天机化气曰「善」，主智慧、机变与策划；庙旺则灵巧多谋，陷地则思虑过多、易犹豫。与天梁或太阴同度，多主术数、参谋之才。",
             "source": "《紫微斗数全书·星曜释义》"},
    "太阳": {"nature": "中天正极（火，光明）",
             "meaning": "太阳化气曰「贵」，主光明、权威、名声与慷慨；庙旺则显达、得人敬重，陷地则辛劳、付出多而收获缓。父子、男亲缘分亦看此星。",
             "source": "《紫微斗数全书·星曜释义》"},
    "武曲": {"nature": "北斗财星（金，刚毅）",
             "meaning": "武曲化气曰「财」，主财富、刚毅与行动力；庙旺善理财、白手起家，陷地则求财辛苦。性刚果决，宜专业技艺立身。",
             "source": "《紫微斗数全书·星曜释义》"},
    "天同": {"nature": "南斗福星（水，温和）",
             "meaning": "天同化气曰「福」，主温和、享福与随缘；庙旺主安逸人缘、知足常乐，陷地则懒散、优柔。最喜见禄存、化禄增福。",
             "source": "《紫微斗数全书·星曜释义》"},
    "廉贞": {"nature": "北斗次桃花（火，才艺）",
             "meaning": "廉贞化气曰「囚」，主才艺、情感与是非；见吉（禄权科）则显贵多才，见煞（羊陀火铃）易纠结、官非。为「囚」星，亦主约束力。",
             "source": "《紫微斗数全书·星曜释义》"},
    "天府": {"nature": "南斗财库（土，稳重）",
             "meaning": "天府化气曰「令」，为南斗主星、财库之府，主稳重、包容与积蓄；庙旺主富足保守、有掌财之能，陷地则过于保守、错失时机。",
             "source": "《紫微斗数全书·星曜释义》"},
    "太阴": {"nature": "中天水星（水，柔美）",
             "meaning": "太阴化气曰「富」，主柔美、财富、田宅与阴性缘分；庙旺（夜生、水乡）富厚内敛，陷地则浮动、多思虑。母缘、妻缘、居家亦看此星。",
             "source": "《紫微斗数全书·星曜释义》"},
    "贪狼": {"nature": "北斗桃花（木，欲望）",
             "meaning": "贪狼化气曰「桃花」，主欲望、才艺与交际；庙旺多才多艺、善应变，陷地则贪酒色、浮荡。为「杀破狼」之一，主开创与变化。",
             "source": "《紫微斗数全书·星曜释义》"},
    "巨门": {"nature": "北斗暗星（水，口舌）",
             "meaning": "巨门化气曰「暗」，主口舌、思辨与是非；庙旺善辩、以口才立身（教师、法律、传播），陷地则多疑、惹是非。喜太阳同度解暗。",
             "source": "《紫微斗数全书·星曜释义》"},
    "天相": {"nature": "南斗印星（水，辅佐）",
             "meaning": "天相化气曰「印」，主辅佐、行政与服务；庙旺主掌印、协调得宜，如「命宫之宰辅」。最喜紫微、禄存夹护，忌刑忌冲破。",
             "source": "《紫微斗数全书·星曜释义》"},
    "天梁": {"nature": "南斗荫星（土，荫护）",
             "meaning": "天梁化气曰「荫」，主荫护、医药、长辈与化解；庙旺主清高、逢凶化吉、得长辈贵人，陷地则孤高、好说教。喜见天同增福。",
             "source": "《紫微斗数全书·星曜释义》"},
    "七杀": {"nature": "南斗将星（金，果决）",
             "meaning": "七杀化气曰「将」，主威权、开创与孤克；庙旺主将才、开拓，陷地则刚暴、波折。为「杀破狼」之一，主人生起伏与变动。",
             "source": "《紫微斗数全书·星曜释义》"},
    "破军": {"nature": "北斗耗星（水，开创）",
             "meaning": "破军化气曰「耗」，主破旧立新、变动与消耗；庙旺主开创有成，陷地则破耗、反复。为「杀破狼」之一，主先破后立。",
             "source": "《紫微斗数全书·星曜释义》"},
}

# 四化通用释义（本命年干四化落星所主之事的倾向）
SIHUA_INTERP = {
    "化禄": {"short": "得 · 缘 · 丰", "meaning": "化禄主「缘」与「得」，使该星所管之事得福气、顺遂、资源丰沛，多主吉庆、易得手。",
             "source": "《紫微斗数全书·四化赋》"},
    "化权": {"short": "执 · 掌 · 力", "meaning": "化权主「执」与「掌」，使该星所管之事掌权、主导、具力量与掌控力，主能干、有主见。",
             "source": "《紫微斗数全书·四化赋》"},
    "化科": {"short": "名 · 显 · 解", "meaning": "化科主「名」与「显」，使该星所管之事得名声、清誉、考试利，并能化解凶厄，主文采、声望。",
             "source": "《紫微斗数全书·四化赋》"},
    "化忌": {"short": "执 · 欠 · 绊", "meaning": "化忌主「执」与「欠」，使该星所管之事多波折、牵绊、执念，需谨慎经营；亦主深刻、难忘。",
             "source": "《紫微斗数全书·四化赋》"},
}

# 十二宫基本含义
PALACE_INTERP = {
    0: "命宫：先天禀赋、性格气质、外貌与健康根基，统御全盘。",
    1: "兄弟宫：手足情分、同辈助力与朋友缘分。",
    2: "夫妻宫：婚姻、伴侣性格与感情相处模式。",
    3: "子女宫：子女缘分、晚辈与桃花（亦看生育、创造力）。",
    4: "财帛宫：财运格局、理财方式与求财态度。",
    5: "疾厄宫：体质强弱、易感病位与养生重点。",
    6: "迁移宫：外出际遇、环境适应力与对外形象。",
    7: "交友宫（奴仆宫）：部属、社交圈与服务对象。",
    8: "官禄宫（事业宫）：事业方向、职业成就与名望。",
    9: "田宅宫：房产、家运根基与不动产。",
    10: "福德宫：精神世界、享乐态度与潜意识倾向。",
    11: "父母宫：长辈荫庇、父母缘分与学业根基。",
}


def _find_palace_of_star(chart, star_name):
    for p in chart["palaces"]:
        if any(s["name"] == star_name for s in p["stars"]):
            return p
    return None


def detect_patterns(chart):
    """识别常见格局（基于三方四正主星）。返回 [(名称, 描述), ...]。"""
    names = {"命宫": None, "财帛宫": None, "官禄宫": None, "迁移宫": None}
    for p in chart["palaces"]:
        if p["name"] in names:
            names[p["name"]] = set(s["name"] for s in p["stars"] if s["type"] == "major")
    triple = set()
    for v in names.values():
        if v:
            triple |= v
    patterns = []
    sha = {"七杀", "破军", "贪狼"}
    if triple & sha:
        patterns.append(("杀破狼", "命宫三方四正见七杀、破军或贪狼，主开创、变动与起伏较大的人生节奏，宜把握转折、忌守旧。"))
    wen = {"天机", "太阴", "天同", "天梁"}
    if len(triple & wen) >= 3:
        patterns.append(("机月同梁", "命宫三方四正聚天机、太阴、天同、天梁之三以上，主文职、谋划与服务型格局，宜专业、稳定。"))
    if "紫微" in triple and "天府" in triple:
        patterns.append(("紫府朝垣", "紫微与天府同宫或对拱，财官双美、格局清贵，主有地位与积蓄。"))
    if "太阳" in triple and "巨门" in triple:
        patterns.append(("巨日同宫", "太阳与巨门同宫（或对照），主口才、名望与官贵，宜以言语、声名立身。"))
    return patterns


def interpret_ziwei(chart):
    """生成结构化释义，供 Web 与报告渲染。所有释义均基于标准斗数赋文。"""
    ming = next(p for p in chart["palaces"] if p["is_ming"])
    shen = next(p for p in chart["palaces"] if p["is_shen"])
    ming_stars = [s for s in ming["stars"] if s["type"] == "major"]

    ming_interp = []
    for s in ming_stars:
        info = STAR_INTERP.get(s["name"], {})
        ming_interp.append({
            "name": s["name"],
            "nature": info.get("nature", ""),
            "meaning": info.get("meaning", ""),
            "source": info.get("source", ""),
        })

    sihua_list = []
    for hua, star in chart["sihua"].items():
        p = _find_palace_of_star(chart, star)
        info = SIHUA_INTERP.get(hua, {})
        sihua_list.append({
            "hua": hua,
            "star": star,
            "palace": p["name"] if p else "—",
            "short": info.get("short", ""),
            "meaning": info.get("meaning", ""),
            "source": info.get("source", ""),
        })

    patterns = [{"name": n, "desc": d} for n, d in detect_patterns(chart)]
    triple_stars = []
    for nm in ["命宫", "财帛宫", "官禄宫", "迁移宫"]:
        p = next(x for x in chart["palaces"] if x["name"] == nm)
        stars = "、".join(s["name"] for s in p["stars"] if s["type"] == "major") or "空宫（借星）"
        triple_stars.append(f"{nm}（{p['stem']}{p['branch']}）：{stars}")

    return {
        "ming_branch": chart["soul_branch"],
        "shen_branch": chart["body_branch"],
        "ju_name": chart["wuxing_ju_name"],
        "ming_stars": ming_interp,
        "shen_meaning": PALACE_INTERP.get(shen["index"], ""),
        "sihua": sihua_list,
        "patterns": patterns,
        "triple": triple_stars,
    }


def to_text(chart):
    """简要文本化命盘（调试/核对用）。"""
    lines = []
    inp = chart["input"]
    lines.append(f"紫微命盘｜{inp['birth_used']} {inp['gender']} ｜ 农历 {chart['lunar']['year_stem']}{chart['lunar']['year_branch']}年 "
                f"{chart['lunar']['lunar_month']}月{chart['lunar']['lunar_day']}日 {chart['lunar']['time_branch']}时")
    lines.append(f"命宫：{chart['soul_branch']}　身宫：{chart['body_branch']}　{chart['wuxing_ju_name']}"
                f"｜紫微在{chart['ziwei_branch']}　天府在{chart['tianfu_branch']}")
    lines.append(f"本命四化：禄：{chart['sihua']['化禄']} 权：{chart['sihua']['化权']} "
                f"科：{chart['sihua']['化科']} 忌：{chart['sihua']['化忌']}")
    lines.append("── 十二宫 ──")
    for p in chart["palaces"]:
        stars = "、".join(s["name"] for s in p["stars"]) or "（空宫）"
        tag = "★命" if p["is_ming"] else ("☆身" if p["is_shen"] else "")
        lines.append(f"  {p['name']}({p['stem']}{p['branch']}){tag}：{stars}")
    lines.append("── 大限 ──")
    for d in chart["decadals"]:
        lines.append(f"  {d['age_range'][0]:>2}-{d['age_range'][1]:<2}岁：{d['stem']}{d['branch']}（{d['palace_name']}）")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    # 默认示例：用户引用的己土八字同日 1989-01-09 10:00 男（仅作演示紫微盘）
    demo = calculate_ziwei(1989, 1, 9, 10, "男")
    print(to_text(demo))
