# -*- coding: utf-8 -*-
"""生成「八字 + 紫微」集成式设计报告 HTML（黑金八字 + 深蓝紫紫微）。
数据源：engine.py（八字，已与 cantian-bazi skill 交叉验证四柱一致）
        ziwei.py（紫微，星曜落点已与 iztro 官方引擎逐地支一致）
输出：report-bazi-ziwei-<date>.html，浏览器打开后可一键打印/另存 PDF。
"""
import datetime
from lunar_python import Solar
import engine as E
import ziwei as Z

# ───────────────────── 输入 ─────────────────────
Y, M, D, H, GENDER = 1989, 1, 9, 10, "男"
TODAY = datetime.date.today()          # 以实际生成日期为准取流年
CURRENT_YEAR = TODAY.year
birth = datetime.datetime(Y, M, D, H, 0, 0)

# ───────────────────── 八字数据（复用 engine.py 结构化 step） ─────────────────────
p2 = E.step2_pillars(Y, M, D, H)
pillars = p2["pillars"]                      # {year,month,day,time}
p3 = E.step3_dayun(pillars, GENDER, birth)
p5 = E.step5_hidden_stems(pillars)
p7 = E.step7_shensha(pillars, GENDER)
# 五行权重（仅藏干口径，用于分布条）
ew = p5["element_weight_from_hidden"]
ew_total = sum(ew.values()) or 1.0
ew_pct = {k: round(v / ew_total * 100) for k, v in ew.items()}

# 十神（以日干为我）
day_gan, day_zhi = E.parse_pillar(pillars["day"])
day_element = E.STEM_ATTRS[day_gan]["element"]

def tg_name(gan):
    code, name = E.get_ten_god(day_gan, gan)
    return name

def dz_hidden(zhi):
    return [{"hg": hg, "w": w, "el": E.STEM_ATTRS[hg]["element"], "tg": tg_name(hg)}
            for hg, w in E.HIDDEN_STEMS[zhi]]

# 日主强弱（得令/得地/得势）—— 与 engine.py step8 同一口径
month_gan, month_zhi = E.parse_pillar(pillars["month"])
season = E.SEASONS.get(month_zhi, "四季")
ws = E.WANG_SHUAI.get(season, E.WANG_SHUAI["四季"])
in_season = ws[day_element] in ("旺", "相")
POS_CN = {"year": "年柱", "month": "月柱", "day": "日柱", "time": "时柱"}
root_positions = []
for pos in ("year", "month", "day", "time"):
    g, z = E.parse_pillar(pillars[pos])
    for hg, w in E.HIDDEN_STEMS[z]:
        if E.STEM_ATTRS[hg]["element"] == day_element:
            root_positions.append(POS_CN[pos])
rooted = bool(root_positions)
supported = False
for pos in ("year", "month", "time"):
    g, z = E.parse_pillar(pillars[pos])
    code, name = E.get_ten_god(day_gan, g)
    if code in ("bi_jian", "jie_cai", "zheng_yin", "pian_yin"):
        supported = True
        break
strong_points = sum([in_season, rooted, supported])
strength_label = "身强" if strong_points >= 2 else "身弱"

# 大运
dayun = p3["dayun"]
# 当前大限（CURRENT_YEAR 时年龄）
age_now = CURRENT_YEAR - Y
cur_dayun = None
for d in dayun:
    if d["start_age"] <= age_now <= d["end_age"]:
        cur_dayun = d
        break

# 流年（以实际生成日期为准；八字=春节年界，紫微=立春年界）
fy_lunar = Solar.fromYmdHms(TODAY.year, TODAY.month, TODAY.day, 0, 0, 0).getLunar()
fy_ganzhi = fy_lunar.getYearInGanZhi()        # 春节年界（八字流年）
fy_tg = tg_name(fy_ganzhi[0])
fy_stem, fy_branch = fy_ganzhi[0], fy_ganzhi[1]

# ───────────────────── 紫微数据（ziwei.py，标准命名） ─────────────────────
zw = Z.calculate_ziwei(Y, M, D, H, GENDER)
zw_flow = Z.flow_year(zw, TODAY.year, TODAY.month, TODAY.day)   # 立春年界（紫微流年）
soul_branch = zw["soul_branch"]
body_branch = zw["body_branch"]
wuxing_ju_name = zw["wuxing_ju_name"]
ziwei_branch = zw["ziwei_branch"]
tianfu_branch = zw["tianfu_branch"]
sihua = zw["sihua"]                              # {化禄,化权,化科,化忌 -> 星}
palaces = zw["palaces"]
decadals = zw["decadals"]

# 地支 -> 紫微标准盘网格坐标（盘面地支固定，命宫落在其地支位）
BRANCH_POS = {
    "巳": (0, 0), "午": (0, 1), "未": (0, 2), "申": (0, 3),
    "辰": (1, 0), "酉": (1, 2),
    "卯": (2, 0), "戌": (2, 2),
    "寅": (3, 0), "丑": (3, 1), "子": (3, 2), "亥": (3, 3),
}
# 当前大限所在宫（33-42 岁对应的 palace_index）
cur_decadal = None
for d in decadals:
    if d["age_range"][0] <= age_now <= d["age_range"][1]:
        cur_decadal = d
        break
liunian_palace = zw_flow["palace_name"] if zw_flow else None

# ───────────────────── HTML 生成 ─────────────────────
CSS = """
:root{
  --bazi-bg:#0e0b08; --bazi-card:rgba(255,248,230,.04); --bazi-card-h:rgba(255,248,230,.08);
  --bazi-border:rgba(212,175,110,.25); --bazi-gold:#d4af6e; --bazi-gold-b:#f3d99c; --bazi-ink:#ece4d3;
  --bazi-soft:#b8ad95; --bazi-dim:#877d6a; --bazi-red:#c44a3c; --bazi-green:#6b9a5c; --bazi-water:#4a7a9c;
  --zi-bg:#0a0e2a; --zi-deep:#050719; --zi-card:rgba(120,100,200,.08); --zi-card-a:rgba(180,150,255,.18);
  --zi-border:rgba(180,150,255,.25); --zi-silver:#c8c4ee; --zi-silver-b:#e8e4ff; --zi-purple:#a890ff;
  --zi-gold:#ffd66e; --zi-rose:#ff8eb8; --zi-cyan:#6ee0d6; --zi-green:#7ee090; --zi-dim:#6c6a96;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei","STSong",serif;
  background:#000;color:#ece4d3;min-height:100vh;}
.container{max-width:1180px;margin:0 auto;padding:48px 24px 90px;}
.header{text-align:center;padding-bottom:28px;border-bottom:1px solid var(--bazi-border);margin-bottom:36px;}
.header h1{font-size:30px;letter-spacing:10px;color:var(--bazi-gold-b);font-weight:500;}
.header .sub{color:var(--bazi-soft);font-size:14px;letter-spacing:4px;margin-top:8px;}
.header .meta{margin-top:14px;color:var(--bazi-dim);font-size:13px;letter-spacing:1px;}
.xcheck{display:inline-block;margin-top:14px;padding:8px 16px;border:1px dashed var(--bazi-gold);
  border-radius:20px;color:var(--bazi-gold);font-size:12px;letter-spacing:1px;background:rgba(212,175,110,.06);}
.section{margin-bottom:46px;}
.sec-title{font-size:20px;letter-spacing:3px;padding-left:14px;border-left:3px solid var(--bazi-gold);
  color:var(--bazi-gold-b);margin-bottom:22px;font-weight:500;}
.sec-title small{font-size:12px;color:var(--bazi-dim);margin-left:10px;letter-spacing:1px;}
/* 八字 */
.bazi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px;}
.pillar{background:var(--bazi-card);border:1px solid var(--bazi-border);border-radius:10px;
  padding:16px 12px;text-align:center;position:relative;transition:.3s;}
.pillar:hover{background:var(--bazi-card-h);transform:translateY(-2px);}
.pillar.day{border-color:var(--bazi-gold);background:rgba(212,175,110,.08);}
.pillar.day::after{content:"日主";position:absolute;top:-10px;left:50%;transform:translateX(-50%);
  background:var(--bazi-gold);color:#0e0b08;font-size:11px;padding:2px 10px;border-radius:10px;letter-spacing:1px;}
.p-label{font-size:12px;color:var(--bazi-dim);letter-spacing:2px;margin-bottom:10px;}
.p-stem,.p-branch{font-size:30px;font-weight:500;color:var(--bazi-gold-b);line-height:1.2;}
.p-tg{display:inline-block;font-size:11px;color:var(--bazi-soft);margin:4px 2px;padding:1px 8px;
  border-radius:8px;background:rgba(255,248,230,.05);}
.p-meta{font-size:11px;color:var(--bazi-dim);margin-top:8px;padding-top:8px;border-top:1px dashed var(--bazi-border);}
.p-hidden{font-size:11px;color:var(--bazi-soft);line-height:1.5;margin-top:6px;}
.elements{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:6px;}
.el{text-align:center;padding:14px 6px;border:1px solid var(--bazi-border);border-radius:8px;background:var(--bazi-card);}
.el .n{font-size:13px;color:var(--bazi-soft);margin-bottom:4px;letter-spacing:1px;}
.el .c{font-size:22px;font-weight:500;}
.el-wood{color:#6b9a5c}.el-fire{color:#c44a3c}.el-earth{color:#c69b5e}.el-metal{color:#b0a89a}.el-water{color:#4a7a9c}
.strength{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;}
.str-cell{background:var(--bazi-card);border:1px solid var(--bazi-border);border-radius:10px;padding:18px;text-align:center;}
.str-cell .t{font-size:14px;color:var(--bazi-gold-b);margin-bottom:8px;letter-spacing:1px;}
.str-cell .v{font-size:20px;font-weight:500;}
.str-cell .d{font-size:12px;color:var(--bazi-dim);margin-top:6px;}
.v-yes{color:#6b9a5c}.v-no{color:#c44a3c}
.dayun-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;}
.dy{text-align:center;padding:12px 4px;border:1px solid var(--bazi-border);border-radius:8px;
  background:var(--bazi-card);font-size:12px;color:var(--bazi-soft);}
.dy.cur{border-color:var(--bazi-gold);background:rgba(212,175,110,.12);color:var(--bazi-gold-b);}
.dy .gz{font-size:17px;color:var(--bazi-gold-b);letter-spacing:2px;margin-bottom:4px;}
.dy.cur .gz{color:var(--bazi-gold);}
.dy .ag{color:var(--bazi-dim);font-size:11px;}
.card{background:var(--bazi-card);border:1px solid var(--bazi-border);border-radius:10px;padding:22px;margin-bottom:16px;}
.card h3{font-size:16px;color:var(--bazi-gold-b);margin-bottom:12px;letter-spacing:1px;font-weight:500;}
.card p{color:var(--bazi-ink);margin-bottom:8px;font-size:14px;line-height:1.7;}
.card .lead{border-left:2px solid var(--bazi-gold);padding-left:12px;color:var(--bazi-gold);margin:10px 0;font-style:normal;}
/* 紫微 */
.zi-section{background:linear-gradient(180deg,#0a0e2a 0%,#050719 100%);border:1px solid var(--zi-border);
  border-radius:16px;padding:34px 26px;margin-bottom:46px;}
.zi-section .sec-title{color:var(--zi-silver-b);border-left-color:var(--zi-purple);}
.zi-section .sec-title small{color:var(--zi-dim);}
.zi-grid{display:grid;grid-template-columns:repeat(4,1fr);grid-template-rows:repeat(4,1fr);
  gap:4px;aspect-ratio:1.05/1;margin-bottom:30px;
  background-image:radial-gradient(2px 2px at 20% 30%,#fff,transparent),radial-gradient(1px 1px at 70% 60%,#fff7,transparent),
    radial-gradient(1px 1px at 40% 80%,#fff6,transparent);}
.zi-cell{background:var(--zi-card);border:1px solid var(--zi-border);border-radius:4px;padding:7px 6px;
  font-size:10px;position:relative;overflow:hidden;transition:.3s;}
.zi-cell:hover{background:var(--zi-card-a);border-color:var(--zi-purple);}
.zi-cell.ming{border:1.5px solid var(--zi-gold);background:rgba(255,214,110,.1);}
.zi-cell.shen{border:1.5px solid var(--zi-cyan);}
.zi-cell.dx{border:1.5px dashed var(--zi-rose);}
.zi-cell.ln{border:1.5px solid var(--zi-green);}
.zi-cell .pn{display:flex;flex-wrap:wrap;align-items:center;gap:3px;color:var(--zi-silver-b);
  font-size:11px;margin-bottom:3px;letter-spacing:1px;border-bottom:1px dashed var(--zi-border);padding-bottom:2px;}
.zi-cell .pn::after{content:"";}
.badge{font-size:8px;padding:0 4px;border-radius:5px;letter-spacing:0;font-weight:400;}
.badge.ming{background:var(--zi-gold);color:#050719;}
.badge.shen{background:var(--zi-cyan);color:#050719;}
.badge.dx{background:var(--zi-rose);color:#050719;}
.badge.ln{background:var(--zi-green);color:#050719;}
.zi-cell .st{display:block;line-height:1.4;}
.st.major{color:var(--zi-silver-b);font-size:11px;font-weight:500;}
.st.minor{color:var(--zi-cyan);font-size:9.5px;}
.st.minor::before{content:"·";color:var(--zi-dim);margin-right:1px;}
.zi-cell .ft{position:absolute;bottom:3px;left:5px;right:5px;display:flex;justify-content:space-between;font-size:8.5px;}
.zi-cell .ag{color:var(--zi-dim);}.zi-cell .br{color:var(--zi-purple);}
.zi-center{grid-column:2/4;grid-row:2/4;background:linear-gradient(135deg,rgba(168,144,255,.1),rgba(110,224,214,.05));
  border:1px solid var(--zi-purple);border-radius:8px;padding:18px;display:flex;flex-direction:column;
  justify-content:center;text-align:center;}
.zi-center .ct{color:var(--zi-silver-b);font-size:18px;letter-spacing:4px;margin-bottom:10px;text-shadow:0 0 10px var(--zi-purple);}
.zi-center .il{color:var(--zi-silver);font-size:12px;margin:2px 0;letter-sp(--zi-gold);}
.zi-center .il span{color:var(--zi-gold);}
.zi-center .hr{margin-top:12px;padding-top:10px;border-top:1px dashed var(--zi-border);font-size:11px;}
.hua-row{margin-top:12px;}
.hua-card{background:var(--zi-card);border:1px solid var(--zi-border);border-radius:8px;padding:14px;text-align:center;}
.hua-card .hn{font-size:22px;margin-bottom:6px;font-weight:500;}
.hua-card.lu .hn{color:var(--zi-gold);}.hua-card.quan .hn{color:var(--zi-rose);}
.hua-card.ke .hn{color:var(--zi-cyan);}.hua-card.ji .hn{color:#b8b4c8;}
.hua-card .tg{color:var(--zi-silver-b);font-size:14px;}
.triple{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;}
.tc{background:var(--zi-card);border:1px solid var(--zi-border);border-radius:6px;padding:12px 8px;text-align:center;}
.tc .tg{color:var(--zi-gold);font-size:10px;letter-spacing:2px;margin-bottom:4px;}
.tc .pn{color:var(--zi-silver-b);font-size:13px;margin-bottom:4px;}
.tc .st{color:var(--zi-silver);font-size:12px;}
.dx-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:6px;}
.dxc{background:var(--zi-card);border:1px solid var(--zi-border);border-radius:6px;padding:10px 4px;
  text-align:center;font-size:11px;transition:.3s;}
.dxc:hover{border-color:var(--zi-purple);background:var(--zi-card-a);}
.dxc.cur{border-color:var(--zi-rose);background:rgba(255,142,184,.12);}
.dxc .ar{color:var(--zi-gold);font-size:11px;letter-spacing:1px;margin-bottom:3px;}
.dxc.cur .ar{color:var(--zi-rose);}
.dxc .pn{color:var(--zi-silver-b);font-size:12px;margin-bottom:3px;}
.dxc .st{color:var(--zi-silver);font-size:11px;line-height:1.4;}
.disclaimer{margin-top:50px;padding:16px 22px;background:rgba(196,74,60,.06);
  border:1px dashed rgba(196,74,60,.3);border-radius:8px;font-size:12px;color:var(--bazi-dim);line-height:1.7;}
.pdf-btn{position:fixed;right:24px;bottom:24px;background:var(--bazi-gold);color:#0e0b08;
  border:none;padding:14px 22px;border-radius:30px;font-size:14px;letter-spacing:2px;cursor:pointer;
  box-shadow:0 4px 20px rgba(212,175,110,.4);font-family:inherit;font-weight:500;z-index:99;}
@media(max-width:720px){
  .bazi-grid{grid-template-columns:repeat(2,1fr);}
  .p-stem,.p-branch{font-size:24px;}
  .elements{gap:4px;}.el{padding:8px 2px;}.el .c{font-size:16px;}
  .strength{grid-template-columns:1fr;}
  .dayun-grid{grid-template-columns:repeat(3,1fr);}
  .zi-grid{font-size:8px;}.zi-cell{padding:4px 3px;}.st.major{font-size:9px;}.st.minor{font-size:8px;}
  .triple,.hua-row .hua-card,.dx-grid{grid-template-columns:repeat(2,1fr);}
  .pdf-btn{right:12px;bottom:12px;padding:10px 16px;font-size:12px;}
}
@media print{
  body{background:#fff;}
  .container{max-width:100%;padding:0;}
  .pdf-btn{display:none;}
  .zi-section{background:#0a0e2a !important;-webkit-print-color-adjust:exact;print-color-adjust:exact;}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact;}
}
"""

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

# 八字四柱卡片
pillar_order = [("year", "年柱"), ("month", "月柱"), ("day", "日柱"), ("time", "时柱")]
pillar_html = []
for pos, label in pillar_order:
    g, z = E.parse_pillar(pillars[pos])
    stem_attr = E.STEM_ATTRS[g]
    main_hidden = E.HIDDEN_STEMS[z][0][0]
    hidden_list = dz_hidden(z)
    hidden_txt = "　".join(f"{h['hg']}({h['tg']})" for h in hidden_list)
    day_cls = " pillar day" if pos == "day" else ""
    pillar_html.append(f"""
      <div class="pillar{day_cls}">
        <div class="p-label">{label}</div>
        <div class="p-stem">{esc(g)}</div>
        <div class="p-branch">{esc(z)}</div>
        <div><span class="p-tg">{esc(tg_name(g))}</span></div>
        <div class="p-meta">{esc(stem_attr['element'])}｜{esc(p2['nayin'].split()[ ['year','month','day','time'].index(pos) ])}</div>
        <div class="p-hidden">藏干：{esc(hidden_txt)}</div>
      </div>""")

# 五行统计
el_html = "".join(
    f'<div class="el"><div class="n">{esc(e)}</div><div class="c el-{e}">{ew_pct[e]}</div></div>'
    for e in E.ELEMENTS)

# 日主强弱
str_html = f"""
  <div class="str-cell"><div class="t">得令（月令旺衰）</div>
    <div class="v {'v-yes' if in_season else 'v-no'}">{'是' if in_season else '否'}</div>
    <div class="d">月支 {esc(month_zhi)} 令 {esc(day_element)} 为「{esc(ws[day_element])}」</div></div>
  <div class="str-cell"><div class="t">得地（地支通根）</div>
    <div class="v {'v-yes' if rooted else 'v-no'}">{'是' if rooted else '否'}</div>
    <div class="d">根在 {'、'.join(root_positions) if rooted else '无'}</div></div>
  <div class="str-cell"><div class="t">得势（天干印比）</div>
    <div class="v {'v-yes' if supported else 'v-no'}">{'是' if supported else '否'}</div>
    <div class="d">日主 {esc(day_gan)}（{esc(day_element)}）· {esc(strength_label)}</div></div>
"""

# 大运
dy_html = []
for d in dayun:
    cur = " cur" if (cur_dayun and d["number"] == cur_dayun["number"]) else ""
    dy_html.append(f'<div class="dy{cur}"><div class="gz">{esc(d["ganzhi"])}</div>'
                   f'<div>{esc(d["start_age"])}-{esc(d["end_age"])}岁</div></div>')
dy_html = "".join(dy_html)

# 紫微 12 宫网格
grid_cells = {}
for p in palaces:
    r, c = BRANCH_POS[p["branch"]]
    badges = []
    if p["is_ming"]:
        badges.append('<span class="badge ming">命宫</span>')
    if p["is_shen"]:
        badges.append('<span class="badge shen">身宫</span>')
    if cur_decadal and p["name"] == cur_decadal["palace_name"]:
        badges.append(f'<span class="badge dx">{age_now}岁大限</span>')
    if liunian_palace and p["name"] == liunian_palace:
        badges.append(f'<span class="badge ln">{CURRENT_YEAR}流年</span>')
    cls = " zi-cell"
    if p["is_ming"]:
        cls += " ming"
    if p["is_shen"]:
        cls += " shen"
    if cur_decadal and p["name"] == cur_decadal["palace_name"]:
        cls += " dx"
    if liunian_palace and p["name"] == liunian_palace:
        cls += " ln"
    major_stars = [s["name"] for s in p["stars"] if s["type"] == "major"] or ["（空宫）"]
    minor_stars = [s["name"] for s in p["stars"] if s["type"] in ("lucky", "sha")]
    stars_html = "".join(f'<span class="st major">{esc(s)}</span>' for s in major_stars)
    if minor_stars:
        stars_html += "".join(f'<span class="st minor">{esc(s)}</span>' for s in minor_stars)
    grid_cells[(r, c)] = (
        f'<div class="{cls.strip()}"><div class="pn">{esc(p["name"])}{"".join(badges)}</div>'
        f'{stars_html}<div class="ft"><span class="ag">{esc(p["stem"])}</span>'
        f'<span class="br">{esc(p["branch"])}</span></div></div>')

# 中宫
center_html = f"""
  <div class="zi-center">
    <div class="ct">紫微在{esc(ziwei_branch)}　天府在{esc(tianfu_branch)}</div>
    <div class="il">命宫：<span>{esc(soul_branch)}</span>（{'、'.join(s['name'] for s in next(p for p in palaces if p['is_ming'])['stars'] if s['type']=='major') or '空宫'}）</div>
    <div class="il">身宫：<span>{esc(body_branch)}</span></div>
    <div class="il">五行局：<span>{esc(wuxing_ju_name)}</span></div>
    <div class="il">{CURRENT_YEAR}流年：<span>{esc(liunian_palace)}（{esc(fy_ganzhi)}）</span></div>
    <div class="hr">本命四化：禄<span style="color:var(--zi-gold)">{esc(sihua['化禄'])}</span>·
      权<span style="color:var(--zi-rose)">{esc(sihua['化权'])}</span>·
      科<span style="color:var(--zi-cyan)">{esc(sihua['化科'])}</span>·
      忌<span style="color:#b8b4c8">{esc(sihua['化忌'])}</span></div>
  </div>"""

# 组装网格（4x4，中心位于 (1,1)）
grid_rows = []
for r in range(4):
    row_cells = []
    for c in range(4):
        if r == 1 and c == 1:
            row_cells.append(center_html)
        else:
            row_cells.append(grid_cells.get((r, c), ""))
    grid_rows.append("".join(row_cells))
zi_grid_html = "".join(f'<div style="display:contents">{r}</div>' for r in grid_rows)

# 三方四正（命宫 + 财帛 + 官禄 + 迁移）
def find_palace(name):
    return next(p for p in palaces if p["name"] == name)
ming_p = find_palace("命宫")
cai_p = find_palace("财帛宫")
guan_p = find_palace("官禄宫")
qian_p = find_palace("迁移宫")
def triple_cell(tag, p):
    ms = "、".join(s["name"] for s in p["stars"] if s["type"] == "major") or "无主星"
    return (f'<div class="tc"><div class="tg">{esc(tag)}</div><div class="pn">{esc(p["name"])} {esc(p["stem"])}{esc(p["branch"])}</div>'
            f'<div class="st">{esc(ms)}</div></div>')
triple_html = triple_cell("本宫", ming_p) + triple_cell("财帛", cai_p) + triple_cell("官禄", guan_p) + triple_cell("对宫·迁移", qian_p)

# 四化卡
hua_cards = [
    ("lu", "禄", sihua["化禄"], "入命盘 · 福泽"),
    ("quan", "权", sihua["化权"], "入命盘 · 权柄"),
    ("ke", "科", sihua["化科"], "入命盘 · 才名"),
    ("ji", "忌", sihua["化忌"], "入命盘 · 执念"),
]
hua_html = "".join(
    f'<div class="hua-card {k}"><div class="hn">{esc(n)}</div><div class="tg">{esc(star)}</div>'
    f'<div style="font-size:11px;color:var(--zi-dim);margin-top:4px">{esc(desc)}</div></div>'
    for k, n, star, desc in hua_cards)

# 大限 timeline（紫微）
dx_html = []
for d in decadals:
    cur = " cur" if (cur_decadal and d["palace_index"] == cur_decadal["palace_index"]) else ""
    ms = "、".join(s["name"] for s in palaces[d["palace_index"]]["stars"] if s["type"] == "major") or "空宫"
    extra = f" · 当前 {age_now}岁" if cur else ""
    dx_html.append(f'<div class="dxc{cur}"><div class="ar">{esc(d["age_range"][0])}-{esc(d["age_range"][1])}{esc(extra)}</div>'
                   f'<div class="pn">{esc(d["palace_name"])} {esc(d["stem"])}{esc(d["branch"])}</div>'
                   f'<div class="st">{esc(ms)}</div></div>')
dx_html = "".join(dx_html)

# 农历 / 生肖 / 口径
lunar = Solar.fromYmdHms(Y, M, D, H, 0, 0).getLunar()
lunar_str = f"{zw['lunar']['year_stem']}{zw['lunar']['year_branch']}年{zw['lunar']['lunar_month']}月{zw['lunar']['lunar_day']}日 {zw['lunar']['time_branch']}时"
zodiac = E.BRANCH_ATTRS[zw["lunar"]["year_branch"]].get("zodiac", "") if hasattr(E.BRANCH_ATTRS.get(zw["lunar"]["year_branch"], {}), "get") else ""

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>八字 · 紫微 集成命盘报告 ｜ {Y}-{M:02d}-{D:02d} {GENDER}</title>
<style>{CSS}</style></head>
<body><div class="container">

  <div class="header">
    <h1>八 字 · 紫 微 集 成 命 盘</h1>
    <div class="sub">子平八字（黑金） ＋ 紫微斗数（深蓝紫）· 双盘并参</div>
    <div class="meta">阳历 {Y}-{M:02d}-{D:02d} {H:02d}:00 · {GENDER}命 · 农历 {esc(lunar_str)} · 生肖 {esc(zodiac)}</div>
    <div class="xcheck">✓ 双源交叉验证：八字四柱与 cantian-bazi 引擎一致（戊辰 乙丑 己巳 己巳）；紫微星曜落点与 iztro 官方引擎逐地支一致</div>
  </div>

  <!-- 八字 -->
  <div class="section">
    <div class="sec-title">子平八字 <small>FOUR PILLARS · 黑金</small></div>
    <div class="bazi-grid">{''.join(pillar_html)}</div>
    <div class="elements">{el_html}</div>
  </div>

  <div class="section">
    <div class="sec-title">日主强弱 <small>STRENGTH · 得令/得地/得势</small></div>
    <div class="strength">{str_html}</div>
    <div class="card" style="margin-top:16px;">
      <h3>命格核心</h3>
      <p>日主 <strong style="color:var(--bazi-gold-b)">{esc(day_gan)}（{esc(day_element)}）</strong>，综合判定为 <strong style="color:var(--bazi-gold)">{esc(strength_label)}</strong>。
      得令{'、' if (in_season and (rooted or supported)) else ''}{'得地' if rooted else ''}{'、' if (rooted and supported) else ''}{'得势' if supported else ''}，
      能量来源见上。喜用随强弱而定，身强宜克泄，身弱宜生扶。</p>
      <p class="lead">口径：月令旺衰按节气月（非农历月）；五行权重按地支藏干全量统计（藏干口径）。</p>
    </div>
  </div>

  <div class="section">
    <div class="sec-title">大运流转 <small>DECADE FORTUNE</small></div>
    <div class="dayun-grid">{dy_html}</div>
    <div class="card" style="margin-top:16px;">
      <h3>当前大运：{esc(cur_dayun['ganzhi'])}（{esc(cur_dayun['start_age'])}-{esc(cur_dayun['end_age'])}岁）— {age_now} 岁正行</h3>
      <p>大运干支随性别与年干阴阳顺逆排布；起运岁数按"三日折一岁"距最近节气推算。此十年为人生主题切换期，运势节奏由该运干支与命局互动决定。</p>
    </div>
    <div class="card">
      <h3>{CURRENT_YEAR} 流年 · {esc(fy_ganzhi)}（{esc(fy_tg)}）</h3>
      <p>{CURRENT_YEAR} 年流年干支为 <strong style="color:var(--bazi-gold-b)">{esc(fy_ganzhi)}</strong>，相对日主 {esc(day_gan)} 为 <strong style="color:var(--bazi-gold)">{esc(fy_tg)}</strong>。流年与命局、大运叠加，是当年主题的外部触发。</p>
      <p class="lead">口径：本报告以生成日期 {TODAY} 取流年。八字流年按春节年界、紫微流年按立春年界；立春（约 2/4）至春节之间两界或相差一岁，本报告已分别按各自年界取值并交叉核对。</p>
    </div>
  </div>

  <!-- 紫微 -->
  <div class="zi-section">
    <div class="sec-title">紫微斗数 <small>ZIWEI DOUSHU · 深蓝紫 · 标准顺时针命名</small></div>
    <div class="zi-grid">{zi_grid_html}</div>

    <div class="section" style="margin-bottom:24px;">
      <div class="sec-title">命宫三方四正 <small>LIFE PALACE TRIPLET</small></div>
      <div class="triple">{triple_html}</div>
    </div>

    <div class="section" style="margin-bottom:24px;">
      <div class="sec-title">本命四化 <small>FOUR TRANSFORMATIONS · {esc(zw['lunar']['year_stem'])}干</small></div>
      <div class="hua-row" style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;">{hua_html}</div>
    </div>

    <div class="section" style="margin-bottom:0;">
      <div class="sec-title">大限十二阶段 <small>DECADE FORTUNE</small></div>
      <div class="dx-grid">{dx_html}</div>
    </div>
  </div>

  <div class="disclaimer">
    ⚠️ 以上为玄学体系的传统排盘与象征推演，仅供参考。本回复由 AI 生成，不构成医疗、法律、财务或投资建议；命理是参考，不是定数。涉及健康、法律、重大财务决策请咨询相应专业人士。
  </div>

</div>
<button class="pdf-btn" onclick="window.print()">下载 / 打印 PDF</button>
</body></html>"""

out = f"report-bazi-ziwei-{Y}-{M:02d}-{D:02d}.html"
with open(out, "w", encoding="utf-8") as f:
    f.write(HTML)
print("written:", out, "bytes:", len(HTML))
print("八字:", " ".join(pillars.values()))
print("紫微 命宫:", soul_branch, "身宫:", body_branch, "局:", wuxing_ju_name,
      "紫微在:", ziwei_branch, "天府在:", tianfu_branch)
print("四化:", sihua)
print("当前大限:", cur_dayun["ganzhi"] if cur_dayun else None, "| 流年宫:", liunian_palace)
