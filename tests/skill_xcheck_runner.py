# -*- coding: utf-8 -*-
"""逐个测试已安装命理技能，与自研引擎做 7 案例四柱对比。

客观证据：每个技能每个案例的原始 stdout 存到
    corpus/skill_xcheck/<skill>/<case>.txt
汇总结果存到 corpus/skill_xcheck/results.json

规则：
  - 只有带确定性脚本的技能才参与数值比对；
  - 纯 LLM 指令 / 文档框架型技能登记为 NO_DETERMINISTIC_SCRIPT，不臆造结果；
  - 技能不支持的参数（如 bazi-personality 无经度）如实标注，不假装等价。

运行：<bundled python> tests/skill_xcheck_runner.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import calculate_bazi  # noqa: E402

PY = r"C:\Users\zzh10\.workbuddy\binaries\python\versions\3.14.3\python.exe"
SKILLS = os.path.join(os.path.expanduser("~"), ".workbuddy", "skills")
EVIDENCE = os.path.join(ROOT, "corpus", "skill_xcheck")

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"

CASES = [
    ("C1", 1990, 10, 8, 9, 30, "男", None),
    ("C2", 2003, 6, 15, 14, 30, "男", None),
    ("C3", 1990, 2, 4, 10, 0, "男", None),
    ("C4", 1990, 7, 1, 23, 30, "男", None),
    ("C5", 1985, 9, 15, 23, 40, "女", None),
    ("C6", 2000, 2, 29, 12, 0, "男", None),
    ("C7", 1990, 5, 15, 14, 30, "男", 114.17),
]

# 技能 -> (脚本相对路径, 是否支持经度参数, 说明, 该技能声明的晚子时口径)
# nextscm: --sect 2 = 子正换日派（23 点归当日）-> 对齐我方 current-day
# bazi-personality: SKILL.md 明确「23:00-23:59 日柱进位到次日（子时换日派）」
#                   -> 对齐我方 next-day（口径对齐后才可比，不能拿不同口径硬比）
SCRIPTED = {
    "nextscm-mingli-analysis": ("scripts/bazi_paipan.py", True, "Meeus 节气 + 加权量化", "current-day"),
    "bazi-personality": ("scripts/bazi_convert.py", False, "纯标准库天文节气，无经度参数", "next-day"),
}
# 无确定性脚本的技能（实测目录内无 .py/.js/.ts/.sh）
UNSCRIPTED = ["zhouyi-sizhu-bazi", "bazi-diviner", "ziqidonglai-bazi-reading"]

# GitHub 开源独立引擎（纯 Python from-scratch，不依赖 lunar_python）
# tianji: Zijian-Ni/tianji —— 自带历法/五虎遁/五鼠遁/节气实现，与本项目 lunar_python 后端完全独立
# 声明口径：date-only 节气（无时分精度）、无真太阳时校正、晚子时不做时干移位
# 注意：Windows 下 /tmp 不被 Python 识别，统一用 tempfile.gettempdir() 定位克隆目录
_TIANJI_SRC = os.path.join(tempfile.gettempdir(), "tianji", "src")
GITHUB = {
    "tianji": (_TIANJI_SRC, "纯 Python from-scratch，无 lunar_python 依赖"),
}
GITHUB_EVIDENCE = os.path.join(ROOT, "corpus", "github_xcheck")


def ours(case, rule="current-day"):
    cid, y, m, d, h, mi, gender, lon = case
    kw = {} if lon is None else {"longitude": lon}
    r = calculate_bazi(y, m, d, h, mi, gender=gender, late_zishi_rule=rule, **kw)
    p = r["pillars"]
    return " ".join([p["year"], p["month"], p["day"], p["time"]])


def save(skill, cid, text):
    d = os.path.join(EVIDENCE, skill)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, cid + ".txt"), "w", encoding="utf-8") as f:
        f.write(text)


def save_github(skill, cid, text):
    d = os.path.join(GITHUB_EVIDENCE, skill)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, cid + ".txt"), "w", encoding="utf-8") as f:
        f.write(text)


def run_tianji(src_dir, case):
    """用 GitHub 开源纯 Python 引擎 tianji 计算四柱，作为第三条独立交叉验证。

    重要口径差异（必须如实标注，不能拿不同口径硬比）：
      - tianji 节气按「日期」切分，无时分精度（寒露/立春只看日期，不看几点几分）；
      - tianji 无真太阳时校正、不接收经度；
      - tianji 晚子时（23 点）日柱不换、时干用「当日」日干（不做时干移位）。
    因此对齐本项目 current-day 基准（日柱不换），晚子时差异为流派口径，非缺陷。
    """
    cid, y, m, d, h, mi, gender, lon = case
    code = (
        "import sys\n"
        "sys.path.insert(0, {src!r})\n"
        "from tianji.bazi.chart import create_chart\n"
        "c = create_chart({y}, {m}, {d}, {h}, {g!r})\n"
        "print('TIANJI_PILLARS=' + ' '.join(str(p) for p in c.pillars))\n"
    ).format(src=src_dir, y=y, m=m, d=d, h=h, g=("male" if gender == "男" else "female"))
    env = dict(os.environ)
    env["PYTHONPATH"] = src_dir
    p = subprocess.run([PY, "-c", code], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    out = (p.stdout or "") + (("\n[STDERR]\n" + p.stderr) if p.stderr else "")
    save_github("tianji", cid, out)
    mobj = re.search(r"TIANJI_PILLARS=(.+)", out)
    if mobj:
        return mobj.group(1).strip(), p.returncode
    return "PARSE_FAILED", p.returncode


def run_nextscm(script, case):
    cid, y, m, d, h, mi, gender, lon = case
    cmd = [PY, script, "--solar", f"{y:04d}-{m:02d}-{d:02d}",
           "--time", f"{h:02d}:{mi:02d}",
           "--gender", "male" if gender == "男" else "female",
           "--sect", "2"]
    note = "sect=2(子正换日/23点归当日)"
    if lon is not None:
        cmd += ["--lon", str(lon)]
        note += ", 真太阳时 --lon=114.17"
    else:
        note += ", 未传经度"
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (("\n[STDERR]\n" + p.stderr) if p.stderr else "")
    save("nextscm-mingli-analysis", cid, out)
    # 只取【四 柱 盘】区块内的第一组 4 柱；报告后面的「天干：…合」「地支：…刑」
    # 是关系描述行，不能被误当成四柱表覆盖（v1 解析器的 bug）。
    stems = branches = None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("天干") and not s.startswith(("天干十神", "天干五行")):
            v = [c for c in s if c in STEMS]
            if len(v) >= 4:
                stems = v[:4]
        elif s.startswith("地支") and not s.startswith("地支五行"):
            v = [c for c in s if c in BRANCHES]
            if len(v) >= 4:
                branches = v[:4]
        if stems and branches:
            break
    if stems and branches:
        return " ".join(stems[i] + branches[i] for i in range(4)), note, p.returncode
    return "PARSE_FAILED", note, p.returncode


def run_personality(script, case):
    cid, y, m, d, h, mi, gender, lon = case
    cmd = [PY, script, "--year", str(y), "--month", str(m), "--day", str(d),
           "--hour", str(h), "--minute", str(mi)]
    note = "无经度参数" + ("（C7 本技能无法做真太阳时校正，用原始钟表时间）" if lon else "")
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (("\n[STDERR]\n" + p.stderr) if p.stderr else "")
    save("bazi-personality", cid, out)
    try:
        data = json.loads(p.stdout)
        pl = data["pillars"]
        return " ".join(pl[k]["stem"] + pl[k]["branch"] for k in ("年柱", "月柱", "日柱", "时柱")), note, p.returncode
    except Exception as e:
        return "PARSE_FAILED:" + str(e), note, p.returncode


def main():
    os.makedirs(EVIDENCE, exist_ok=True)
    results = {"ours": {}, "ours_next_day": {}, "skills": {}, "unscripted": {}, "github": {}}

    for c in CASES:
        results["ours"][c[0]] = ours(c)
        results["ours_next_day"][c[0]] = ours(c, rule="next-day")

    for name, (rel, has_lon, desc, rule) in SCRIPTED.items():
        script = os.path.join(SKILLS, name, rel)
        if not os.path.exists(script):
            results["skills"][name] = {"status": "SCRIPT_MISSING", "desc": desc}
            continue
        entry = {"status": "ran", "desc": desc, "late_zishi_rule": rule, "cases": {}}
        base = results["ours_next_day"] if rule == "next-day" else results["ours"]
        for c in CASES:
            if name == "nextscm-mingli-analysis":
                got, note, rc = run_nextscm(script, c)
            else:
                got, note, rc = run_personality(script, c)
            expected = base[c[0]]
            entry["cases"][c[0]] = {
                "skill_pillars": got, "our_pillars": expected,
                "match": got == expected, "note": note, "returncode": rc,
            }
        results["skills"][name] = entry

    for name in UNSCRIPTED:
        d = os.path.join(SKILLS, name)
        files = []
        if os.path.isdir(d):
            for root, _, fs in os.walk(d):
                for f in fs:
                    if f.endswith((".py", ".js", ".ts", ".sh")):
                        files.append(os.path.relpath(os.path.join(root, f), d))
        results["unscripted"][name] = {
            "installed": os.path.isdir(d),
            "deterministic_scripts": files,
            "status": "NO_DETERMINISTIC_SCRIPT" if not files else "HAS_SCRIPTS",
        }

    with open(os.path.join(EVIDENCE, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("=== 自研引擎双口径基准（current-day / next-day）===")
    for cid in results["ours"]:
        a, b = results["ours"][cid], results["ours_next_day"][cid]
        print(f"  {cid}: current={a} | next-day={b}" + ("  (相同)" if a == b else "  ← 晚子时用例"))
    print("\n=== 带确定性脚本技能：按各技能声明的口径逐案例比对 ===")
    for name, entry in results["skills"].items():
        if entry.get("status") != "ran":
            print(f"  {name}: {entry.get('status')}")
            continue
        ok = sum(1 for c in entry["cases"].values() if c["match"])
        print(f"  {name}: {ok}/7 一致 | {entry['desc']} | 口径={entry['late_zishi_rule']}")
        for cid, c in entry["cases"].items():
            flag = "OK  " if c["match"] else "DIFF"
            print(f"    {flag} {cid} skill={c['skill_pillars']} ours={c['our_pillars']} | {c['note']}")
    print("\n=== 无确定性脚本技能（如实登记，不臆造结果）===")
    for name, e in results["unscripted"].items():
        print(f"  {name}: installed={e['installed']} status={e['status']} scripts={e['deterministic_scripts']}")

    # GitHub 开源独立引擎（tianji）交叉验证
    for name, (src_dir, desc) in GITHUB.items():
        if not os.path.isdir(src_dir):
            results["github"][name] = {"status": "SRC_MISSING", "desc": desc}
            continue
        entry = {
            "status": "ran", "desc": desc,
            "conventions": "date-only 节气(无时分精度), 无真太阳时, 晚子时不做时干移位",
            "aligned_to": "current-day", "cases": {},
        }
        base = results["ours"]
        for c in CASES:
            got, rc = run_tianji(src_dir, c)
            expected = base[c[0]]
            entry["cases"][c[0]] = {
                "tianji_pillars": got, "our_pillars": expected,
                "match": got == expected, "returncode": rc,
            }
        results["github"][name] = entry

    print("\n=== GitHub 开源引擎 tianji 交叉验证（对齐 current-day 基准）===")
    for name, entry in results["github"].items():
        if entry.get("status") != "ran":
            print(f"  {name}: {entry.get('status')}")
            continue
        ok = sum(1 for c in entry["cases"].values() if c["match"])
        print(f"  {name}: {ok}/7 一致 | {entry['desc']} | 口径={entry['conventions']}")
        for cid, c in entry["cases"].items():
            flag = "OK  " if c["match"] else "DIFF"
            diff_reason = ""
            if not c["match"]:
                if cid in ("C1", "C3"):
                    diff_reason = " ← 节气时分精度差异(tianji 按日期切,无时分)"
                elif cid in ("C4", "C5"):
                    diff_reason = " ← 晚子时口径差异(tianji 时干用当日日干)"
                else:
                    diff_reason = " ← 需核查"
            print(f"    {flag} {cid} tianji={c['tianji_pillars']} ours={c['our_pillars']}{diff_reason}")
    print(f"\n证据目录: {EVIDENCE}\nGitHub 证据: {GITHUB_EVIDENCE}")


if __name__ == "__main__":
    main()
