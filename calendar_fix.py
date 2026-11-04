# -*- coding: utf-8 -*-
"""
基础历法预处理层（真太阳时 / 中国夏令时 / 晚子时口径 / 日期合法性）

来源与许可：
    本模块核心算法移植自开源项目 ziwei-doushu（作者：王多鱼AI，
    GitHub: https://github.com/Renhuai123/ziwei-doushu，代码采用 MIT License）。
    - 真太阳时公式、NOAA 均时差近似、晚子时四口径：对应其 lib/ziwei/true-solar-time.ts
    - 中国夏令时判定表 XLS_CN：对应其 lib/ziwei/dst-cn.ts
    移植目的：补全我方八字引擎此前缺失的「钟表时间 → 标准时 → 真太阳时」
    预处理步骤（此前直接用钟表时间喂 lunar-python 的 getBaZi，西部出生或时辰
    边界附近会排错盘）。命理运算逻辑（十神/格局/用神等）仍由 engine.py 负责，
    本层只做历法，不做命理（参照对方 lunar-solar.ts「只做历法不做命理」原则）。

设计原则（沿用对方铁律）：
    - 中国夏令时「只判定、不自动减 1 小时」：我们无法知道用户报的是夏令时读数
      还是已换算的标准时，默默扣除会把存量命盘悄悄改掉，故仅提示。
    - 绝不静默滚动不存在的日期（如 2 月 30 日）：直接判非法，交由上层拒绝排盘。
"""

import math
from datetime import datetime, timedelta

# 受理年份区间（lunar-python / lunar-javascript 在极端年份不可靠，参照对方 LUNAR_YEAR_MIN/MAX 思路）
SOLAR_YEAR_MIN = 1900
SOLAR_YEAR_MAX = 2100

MINUTES_PER_DAY = 1440
SECONDS_PER_DAY = 86400
_MOD = (lambda v, b: ((v % b) + b) % b)


# ============================================================
# 1. 日期合法性
# ============================================================

def is_valid_gregorian_date(year: int, month: int, day: int) -> bool:
    """公历日期是否真实存在（拒绝 2 月 30 日、非闰年 2 月 29 日等）。"""
    if not (isinstance(year, int) and isinstance(month, int) and isinstance(day, int)):
        return False
    if year < SOLAR_YEAR_MIN or year > SOLAR_YEAR_MAX:
        return False
    try:
        d = datetime(year, month, day)
    except ValueError:
        return False
    return d.year == year and d.month == month and d.day == day


def shift_gregorian_date(year: int, month: int, day: int, day_offset: int):
    """在公历日期上偏移若干天，返回 (year, month, day)。"""
    d = datetime(year, month, day) + timedelta(days=day_offset)
    return d.year, d.month, d.day


# ============================================================
# 2. 真太阳时（移植自 true-solar-time.ts）
# ============================================================

def equation_of_time_minutes(year: int, month: int, day: int,
                             clock_hour: int = 12, clock_minute: int = 0) -> float:
    """
    NOAA 均时差近似值，返回分钟；正值表示真太阳时快于平太阳时。
    参考：https://gml.noaa.gov/grad/solcalc/solareqns.PDF
    公式：229.18 × (0.000075 + 0.001868 cosγ − 0.032077 sinγ
                    − 0.014615 cos2γ − 0.040849 sin2γ)
    其中 γ = 2π/年天数 × (年内第几天 − 1 + (钟表小时−12)/24)
    """
    if not is_valid_gregorian_date(year, month, day):
        return 0.0
    is_leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
    days_in_year = 366 if is_leap else 365
    fractional_hour = clock_hour + clock_minute / 60.0
    day_of_year = (datetime(year, month, day) - datetime(year, 1, 1)).days + 1
    gamma = (2 * math.pi / days_in_year) * (day_of_year - 1 + (fractional_hour - 12) / 24)
    return 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )


def branch_from_solar_minutes(normalized_minutes: float) -> int:
    """由当日分钟数(0-1440)求时辰序号 0-11（子=0…亥=11）。"""
    if normalized_minutes >= 1380 or normalized_minutes < 60:
        return 0  # 子时 23:00-01:00
    return int((normalized_minutes - 60) // 120) + 1


# 晚子时口径（与 ziwei-doushu 一致）
LateZishiRule = str  # 'next-day' | 'current-day' | 'all-current' | 'day-cur-time-next'


def resolve_late_zishi(day_offset: int, normalized_minutes: float, branch: int,
                       rule: str = "current-day") -> int:
    """
    把真太阳日的跨日偏移与晚子时口径合并，得到相对输入日的「最终排盘日偏移」。
    - next-day     : 23:00-23:59 归次日（传统晚子时派）
    - current-day  : 23:00-23:59 归本日（lunar-python 默认口径，向后兼容）
    - all-current  : 全天归本日（不分早晚子）
    - day-cur-time-next : 改时柱口径不改主盘日（紫微专用，八字不用）
    """
    next_day_rule = (rule == "next-day")
    is_late_zishi = (branch == 0 and normalized_minutes >= 1380)

    if rule == "all-current":
        return day_offset  # 不做晚子换日
    if day_offset < 0 and is_late_zishi:
        return day_offset + 1 if next_day_rule else day_offset
    if day_offset != 0:
        return day_offset
    if is_late_zishi:
        return 1 if next_day_rule else 0
    return 0


# ============================================================
# 3. 中国夏令时判定（移植自 dst-cn.ts，XLS_CN 全表，逐字对齐通行口径）
# ============================================================
# [年, 起月, 起日, 止月, 止日]，起止日均含。
XLS_CN: list = [
    [1935, 5, 1, 9, 30], [1936, 5, 1, 9, 30], [1937, 5, 1, 9, 30], [1938, 5, 1, 9, 30],
    [1939, 5, 1, 9, 30], [1940, 5, 1, 9, 30], [1941, 5, 1, 9, 30], [1942, 5, 1, 9, 30],
    [1943, 5, 1, 9, 30], [1944, 5, 1, 9, 30], [1945, 5, 1, 9, 30], [1946, 5, 1, 9, 30],
    [1947, 5, 1, 9, 30], [1948, 5, 1, 9, 30], [1949, 5, 1, 9, 30], [1950, 5, 1, 9, 30],
    [1951, 5, 1, 9, 30], [1952, 3, 1, 10, 31], [1953, 4, 1, 10, 31], [1954, 4, 1, 10, 31],
    [1955, 5, 1, 9, 30], [1956, 5, 1, 9, 30], [1957, 4, 1, 9, 30], [1958, 4, 1, 9, 30],
    [1959, 4, 1, 9, 30], [1960, 6, 1, 9, 30], [1961, 6, 1, 9, 30], [1974, 4, 1, 10, 31],
    [1975, 4, 1, 10, 31], [1979, 7, 1, 9, 30], [1986, 5, 4, 9, 14], [1987, 4, 12, 9, 13],
    [1988, 4, 10, 9, 11], [1989, 4, 16, 9, 17], [1990, 4, 15, 9, 16], [1991, 4, 14, 9, 15],
]


def is_china_dst(year: int, month: int, day: int) -> bool:
    """该公历日期是否处于中国大陆夏令时期间（纯按日期，不看小时）。"""
    for (y, m1, d1, m2, d2) in XLS_CN:
        if year != y:
            continue
        if month > m1 and month < m2:
            return True
        if month == m1 and day >= d1:
            return True
        elif month == m2 and day <= d2:
            return True
    return False


def china_dst_range(year: int):
    """该年夏令时起止（用于文案）；不在表内返回 None。"""
    for (y, m1, d1, m2, d2) in XLS_CN:
        if y == year:
            return {"start": f"{m1} 月 {d1} 日", "end": f"{m2} 月 {d2} 日"}
    return None


def china_dst_years() -> list:
    return [row[0] for row in XLS_CN]


# ============================================================
# 4. 统一预处理入口
# ============================================================

def preprocess_birth_time(year: int, month: int, day: int, hour: int, minute: int = 0,
                          longitude: float = None, utc_offset_minutes: int = 480,
                          late_zishi_rule: str = "current-day") -> dict:
    """
    将「钟表时间」预处理为「排盘用的真太阳时」，并给出日期偏移与提示。

    参数：
        longitude          : 出生地经度（度，东正西负）。不传则不做真太阳时校正。
        utc_offset_minutes : 钟表时间所在时区标准偏移（分钟，东正西负）。默认 480（北京时间/东八区）。
                             海外出生地传当地时区固定偏移（如 UTC+9 → 540），与主流排盘口径一致。
        late_zishi_rule    : 晚子时(23:00-23:59)口径，默认 'current-day' 与 lunar-python 一致。

    返回：
        {
          "valid": bool, "error": str|None,
          "corrected": (y,m,d,h,mi),        # 喂 getBaZi 的修正后时间
          "branch": int,                    # 时辰序号 0-11
          "corrected_flag": bool,           # 是否做了真太阳时校正
          "longitude_correction_minutes": float,
          "equation_of_time_minutes": float,
          "total_correction_minutes": float,
          "day_shift": int,                 # 相对输入日的偏移
          "dst": {"is_dst": bool, "range": str|None},   # 夏令时提示（只判定不扣）
          "rule": str,
        }
    """
    result = {
        "valid": True, "error": None,
        "corrected": (year, month, day, hour, minute),
        "branch": branch_from_solar_minutes(hour * 60 + minute),
        "corrected_flag": False,
        "longitude_correction_minutes": 0.0,
        "equation_of_time_minutes": 0.0,
        "total_correction_minutes": 0.0,
        "day_shift": 0,
        "dst": {"is_dst": False, "range": None},
        "rule": late_zishi_rule,
    }

    # 1) 日期合法性
    if not is_valid_gregorian_date(year, month, day):
        result["valid"] = False
        result["error"] = f"公历日期 {year}-{month:02d}-{day:02d} 不存在或超出受理范围（{SOLAR_YEAR_MIN}–{SOLAR_YEAR_MAX}）"
        return result

    # 2) 夏令时判定（只提示，不自动减）
    if is_china_dst(year, month, day):
        rng = china_dst_range(year)
        result["dst"] = {"is_dst": True, "range": (rng["start"] + " 至 " + rng["end"]) if rng else None}

    # 3) 真太阳时校正（仅当提供经度）
    if longitude is not None and isinstance(longitude, (int, float)):
        meridian = (utc_offset_minutes / 4.0) if utc_offset_minutes is not None else 120.0
        lon_corr = (longitude - meridian) * 4.0  # 经度修正（分钟）
        eot = equation_of_time_minutes(year, month, day, hour, minute)
        total_corr = lon_corr + eot

        raw_minutes = hour * 60 + minute + total_corr
        rounded_seconds = int(round(raw_minutes * 60))
        day_offset = rounded_seconds // SECONDS_PER_DAY
        second_of_day = rounded_seconds % SECONDS_PER_DAY
        h2 = second_of_day // 3600
        m2 = (second_of_day % 3600) // 60
        normalized_minutes = second_of_day / 60.0

        result["longitude_correction_minutes"] = round(lon_corr, 2)
        result["equation_of_time_minutes"] = round(eot, 2)
        result["total_correction_minutes"] = round(total_corr, 2)
        result["corrected_flag"] = True
        result["branch"] = branch_from_solar_minutes(normalized_minutes)
    else:
        # 无经度：仅按钟表时间求时辰与跨日
        raw_minutes = hour * 60 + minute
        rounded_seconds = int(round(raw_minutes * 60))
        day_offset = rounded_seconds // SECONDS_PER_DAY
        second_of_day = rounded_seconds % SECONDS_PER_DAY
        h2 = second_of_day // 3600
        m2 = (second_of_day % 3600) // 60
        normalized_minutes = second_of_day / 60.0

    # 4) 晚子时口径合并跨日偏移
    is_late_zishi = (result["branch"] == 0 and normalized_minutes >= 1380)
    day_shift = resolve_late_zishi(day_offset, normalized_minutes, result["branch"], late_zishi_rule)
    result["day_shift"] = day_shift

    cy, cm, cd = shift_gregorian_date(year, month, day, day_shift)
    # 子时换日派（next-day）必修：日期进位后，晚子时 23:xx 必须归一为次日 00:xx
    # （早子时）再喂 getBaZi()。否则会把「次日 23:xx」再套一次晚子时规则，
    # 时柱由正确的壬子错成甲子。客观基准：
    #   lunar-python 1990-07-01 23:30 -> 庚午 壬午 丁卯 壬子
    #   lunar-python 1990-07-02 00:30 -> 庚午 壬午 戊辰 壬子  ← 子时换日派应得
    #   lunar-python 1990-07-02 23:30 -> 庚午 壬午 戊辰 甲子  ← 修复前的错误输入
    if late_zishi_rule == "next-day" and is_late_zishi:
        h2 = 0
    result["corrected"] = (cy, cm, cd, h2, m2)
    return result


if __name__ == "__main__":
    # 自测：北京(116.4°) 1990-10-08 09:30（应基本无偏，因北京接近120°）
    print("北京 1990-10-08 09:30:", preprocess_birth_time(1990, 10, 8, 9, 30, longitude=116.4))
    # 乌鲁木齐(87.6°) 同日 23:30（经度修正约 -130 分钟，会跨日并换时辰）
    print("乌鲁木齐 1990-10-08 23:30:", preprocess_birth_time(1990, 10, 8, 23, 30, longitude=87.6))
    # 夏令时年份
    print("1990-07-01 是否夏令时:", is_china_dst(1990, 7, 1))
    # 非法日期
    print("1990-02-30:", preprocess_birth_time(1990, 2, 30, 9, 30))
