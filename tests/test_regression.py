# -*- coding: utf-8 -*-
"""
八字引擎回归测试集
覆盖：黄金案例、真太阳时跨时辰、立春年柱边界、晚子时口径、夏令时提示、日期合法性。
运行：pytest tests/test_regression.py  -v
      或  python tests/test_regression.py   （无 pytest 时自跑）
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import calculate_bazi


def _p(r):
    return r["pillars"]


# 1) 黄金案例：1990-10-08 09:30 男（此前已逐字段核对正确）
def test_golden_1990_10_08_no_longitude():
    r = calculate_bazi(1990, 10, 8, 9, 30, gender="男", current_year=2026)
    assert _p(r) == {"year": "庚午", "month": "乙酉", "day": "丙午", "time": "癸巳"}
    # 月柱必须精确按寒露 21:13 分界（酉月），不应是戌月丙戌
    assert _p(r)["month"] == "乙酉"


# 2) 北京(116.4°) 经度修正几乎为零，结果与无经度一致（向后兼容）
def test_beijing_longitude_no_regression():
    r0 = calculate_bazi(1990, 10, 8, 9, 30, gender="男", current_year=2026)
    r1 = calculate_bazi(1990, 10, 8, 9, 30, gender="男", longitude=116.4, current_year=2026)
    assert _p(r0) == _p(r1)
    assert r1["input"]["corrected_birth"] == "1990-10-08 09:28"  # -1.79 分


# 3) 真太阳时跨时辰：乌鲁木齐(87.6°) 1990-10-08 23:30 钟表时→真太阳时 21:33 亥时
#    证明缺真太阳时会把亥时误判为子时，且月柱由酉变戌（已过寒露 21:13）
def test_true_solar_changes_branch_urumqi():
    r = calculate_bazi(1990, 10, 8, 23, 30, gender="男", longitude=87.6, current_year=2026)
    assert r["input"]["corrected_birth"] == "1990-10-08 21:33"
    assert _p(r)["time"] == "己亥"   # 亥时，非子时庚子
    assert _p(r)["month"] == "丙戌"  # 真太阳时已过寒露 → 戌月


# 4) 立春年柱边界：1990 立春 = 02-04 10:14
#    立春前 05:00 → 上年己巳；立春后 16:00 → 当年庚午
def test_lichun_boundary():
    before = calculate_bazi(1990, 2, 4, 5, 0, gender="男", current_year=2026)
    after = calculate_bazi(1990, 2, 4, 16, 0, gender="男", current_year=2026)
    assert before["pillars"]["year"] == "己巳"
    assert after["pillars"]["year"] == "庚午"
    assert before["pillars"]["year"] != after["pillars"]["year"]


# 5) 晚子时默认口径(current-day)：23:00-23:59 归本日（与 lunar-python 一致）
def test_zishi_current_day():
    r = calculate_bazi(1990, 10, 8, 23, 30, gender="男", current_year=2026)
    assert r["pillars"]["day"] == "丙午"   # 当日
    assert r["pillars"]["time"] == "庚子"  # 子时


# 6) 晚子时 next-day 口径：23:00-23:59 归次日（日柱顺移到次日丁未）
#    注：时柱由 lunar-python 晚子时口径决定（23:xx 的时柱按次日日干遁），不在此约束
def test_zishi_next_day_rule():
    r = calculate_bazi(1990, 10, 8, 23, 30, gender="男", late_zishi_rule="next-day", current_year=2026)
    assert r["input"]["corrected_birth"] == "1990-10-09 23:30"
    assert r["pillars"]["day"] == "丁未"   # 次日
    assert r["steps"][0]["历法校正"]["排盘日偏移"] == 1


# 7) 中国夏令时提示（只判定不自动减）：1990-07-01 在 1986-1991 夏令时区间内
def test_dst_warning_1990_07_01():
    r = calculate_bazi(1990, 7, 1, 12, 0, gender="男", longitude=116.4, current_year=2026)
    assert r["input"]["dst_warning"]["is_dst"] is True
    assert "4 月 15 日" in r["input"]["dst_warning"]["range"]


# 8) 非法日期：2 月 30 日必须被拒绝（杜绝静默滚动）
def test_invalid_date_2_30():
    r = calculate_bazi(1990, 2, 30, 9, 30, gender="男")
    assert r.get("error") is not None
    assert r["steps"] == []


# 9) 闰年 2 月 29 日合法（2000 为闰年）
def test_leap_year_2_29_valid_2000():
    r = calculate_bazi(2000, 2, 29, 12, 0, gender="男", current_year=2026)
    assert r.get("error") is None
    assert _p(r)["year"] in ("庚辰",)  # 2000 立春后为庚辰年


# 10) 非闰年 2 月 29 日非法（1990 非闰年）
def test_leap_year_2_29_invalid_1990():
    r = calculate_bazi(1990, 2, 29, 12, 0, gender="男")
    assert r.get("error") is not None


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:
            print(f"ERR   {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
