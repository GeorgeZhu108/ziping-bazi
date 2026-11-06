# -*- coding: utf-8 -*-
"""Regenerate web rendering fixtures by hitting the LIVE /api/calculate.

We deliberately call the running Flask server (default http://127.0.0.1:5001)
instead of importing engine.py directly, because the dev Python here lacks
lunar_python while the server's interpreter has it. This guarantees fixtures
match exactly what the app serves.

longitude is set to 116.4 (北京) so the 历法校正 card (which renders
晚子时口径) is actually exercised by tests/test_web_render.js — that path was
previously skipped because all fixtures had longitude=null, which is how the
`current-day` English leak slipped through testing.

Usage:  python tests/regen_fixtures.py
"""
import json
import os
import sys
import urllib.request

BASE = os.environ.get("FIXTURE_API", "http://127.0.0.1:5001/api/calculate")

# (filename, year, month, day, hour, minute, gender)
CASES = [
    ("in1",               1989, 1,  9,  10, 0, "男"),
    ("in2",               1995, 11, 11, 23, 0, "男"),
    ("in3",               2000, 2,  29, 14, 0, "女"),
    ("male_1989",         1989, 1,  9,  10, 0, "男"),
    ("male_1995_latezi",  1995, 11, 11, 23, 0, "男"),
    ("female_2000_leap",  2000, 2,  29, 14, 0, "女"),
]

LONGITUDE = 116.4  # 北京经度，确保 历法校正 / 真太阳时 卡片渲染


def fetch(year, month, day, hour, minute, gender):
    body = {
        "year": year, "month": month, "day": day, "hour": hour,
        "minute": minute, "gender": gender, "current_year": 2026,
        "longitude": LONGITUDE, "late_zishi_rule": "current-day",
    }
    req = urllib.request.Request(
        BASE, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, "fixtures", "web")
    os.makedirs(out_dir, exist_ok=True)
    for name, y, m, d, hh, mm, gender in CASES:
        payload = fetch(y, m, d, hh, mm, gender)
        data = payload["data"]
        data["input"]["longitude"] = LONGITUDE
        path = os.path.join(out_dir, name + ".json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print("wrote", name + ".json")
    print("done; fixtures regenerated against", BASE)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        sys.stderr.write("regen failed: " + str(e) + "\n")
        sys.exit(1)
