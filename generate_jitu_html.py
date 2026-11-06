# -*- coding: utf-8 -*-
"""生成 1989-01-09 男（己土·杂气格·用户引用案例）八字命盘黑金风 HTML 报告，
并重点呈现「重写后的大白话解读」十一节。"""
import sys, json
sys.path.insert(0, '.')
from engine import calculate_bazi
from data import HIDDEN_STEMS, STEM_ATTRS

BIRTH = (1989, 1, 9, 10, 0, '男')
res = calculate_bazi(*BIRTH[:5], gender=BIRTH[5], current_year=2026)

s1 = res['steps'][0]
s2 = res['steps'][1]
s4 = res['steps'][3]
s8 = res['steps'][7]
s9 = res['steps'][8]
s10 = res['steps'][9]
s11 = res['steps'][10]
s12 = res['steps'][11]

pillars = s2['pillars']
P = ['年', '月', '日', '时']
order = ['year', 'month', 'day', 'time']
nayin = s2['nayin'].split()

ELEM_COLOR = {'木': '#6fae6a', '火': '#d4543f', '土': '#d4af6e', '金': '#e8e2d2', '水': '#5f9fb5'}

def hidden_html(zhi):
    items = []
    for g, w in HIDDEN_STEMS[zhi]:
        el = STEM_ATTRS[g]['element']
        c = ELEM_COLOR.get(el, '#d4af6e')
        items.append(f"<span style='color:{c}'>{g}</span><span class='w'>{w}</span>")
    return ' '.join(items)

pillar_cards = ""
for i, pos in enumerate(order):
    g, z = pillars[pos][0], pillars[pos][1]
    tg = s4['details'][pos]['十神']
    nay = nayin[i] if i < len(nayin) else ''
    pillar_cards += f"""
    <div class="pillar">
      <div class="p-label">{P[i]}柱</div>
      <div class="p-gan">{g}<span class="tg-god">{tg}</span></div>
      <div class="p-zhi">{z}</div>
      <div class="p-hidden">藏：{hidden_html(z)}</div>
      <div class="p-nayin">{nay}</div>
    </div>"""

wuxing_bars = ""
for e in ['木', '火', '土', '金', '水']:
    sc = s8['scores'].get(e, 0)
    c = ELEM_COLOR[e]
    w = s8['raw_weight'].get(e, 0)
    cls = ' day-emph' if e == s8['day_element'] else ''
    wuxing_bars += f"""
    <div class="wx-row{cls}">
      <span class="wx-name">{e}</span>
      <div class="wx-bar-bg"><div class="wx-bar" style="width:{max(sc,2)}%;background:{c}"></div></div>
      <span class="wx-val">{w}（{sc}%）</span>
    </div>"""

s3 = res['steps'][2]
dayun_axis = ""
for d in s3['dayun']:
    cur = (d['number'] == s11['current_dayun']['number'])
    dayun_axis += f"""<div class="dyun{' cur' if cur else ''}">
      <div class="dy-ganzhi">{d['ganzhi']}</div>
      <div class="dy-age">{d['start_age']}-{d['end_age']}岁</div>
    </div>"""

# —— 大白话报告（重写后十一节）——
pl = s12['plain_language']
report_html = ""
for i, sec in enumerate(pl['sections']):
    term = sec.get('term', '')
    plain = sec.get('plain', '')
    src = sec.get('source', '')
    report_html += f"""
    <div class="rep-sec">
      <h3>{i+1}. {term}</h3>
      <div class="rep-body">{plain}</div>
      {f'<div class="src">出处：{src}</div>' if src else ''}
    </div>"""

# 称骨
cg = s12['chengu']
chengu_html = f"""
    <div class="card">
      <h3>袁天罡称骨 · {cg['total_str']}（{cg['total_qian']}钱）</h3>
      <div class="kv">年柱 {cg['year_w']}钱　月柱 {cg['month_w']}钱　日柱 {cg['day_w']}钱　时柱 {cg['hour_w']}钱</div>
      <div class="kv">歌诀：{cg['song']}</div>
      <div class="note">{cg['source']}</div>
    </div>"""

html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>八字命盘 · 1989-01-09 男（己土·杂气格）</title>
<style>
:root{{--bg:#0e0b08;--gold:#d4af6e;--gold-bright:#f3d99c;--ink:#ece4d3;--red:#c44a3c;--green:#6b9a5c;}}
*{{box-sizing:border-box;}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:"PingFang SC","Hiragino Sans GB","STSong",serif;line-height:1.75;}}
.wrap{{max-width:980px;margin:0 auto;padding:32px 20px 60px;}}
header{{text-align:center;border-bottom:1px solid rgba(212,175,110,.35);padding-bottom:18px;margin-bottom:26px;}}
header h1{{color:var(--gold-bright);font-size:30px;letter-spacing:4px;margin:0 0 6px;}}
header .sub{{color:var(--gold);letter-spacing:2px;font-size:13px;}}
header .meta{{margin-top:10px;color:#b9ad94;font-size:13px;}}
h2{{color:var(--gold-bright);border-left:4px solid var(--gold);padding-left:12px;margin:34px 0 16px;font-size:20px;letter-spacing:2px;}}
.pillars{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;}}
.pillar{{background:linear-gradient(160deg,#17120b,#0f0b06);border:1px solid rgba(212,175,110,.3);border-radius:10px;padding:16px 10px;text-align:center;}}
.p-label{{color:var(--gold);font-size:13px;letter-spacing:2px;}}
.p-gan{{font-size:40px;color:var(--gold-bright);font-weight:bold;margin:6px 0;position:relative;}}
.tg-god{{position:absolute;top:-6px;right:-2px;font-size:12px;color:var(--red);background:#1a0e0c;padding:1px 5px;border-radius:4px;border:1px solid rgba(196,74,60,.5);}}
.p-zhi{{font-size:34px;color:var(--ink);}}
.p-hidden{{font-size:13px;color:#a89c84;margin-top:6px;}}
.p-hidden .w{{font-size:10px;color:#7d7363;margin-left:1px;}}
.p-nayin{{font-size:12px;color:var(--gold);margin-top:6px;opacity:.85;}}
.wx-row{{display:flex;align-items:center;margin:8px 0;font-size:14px;}}
.wx-name{{width:28px;font-weight:bold;}}
.wx-bar-bg{{flex:1;height:14px;background:#1c160d;border-radius:7px;overflow:hidden;margin:0 10px;}}
.wx-bar{{height:100%;border-radius:7px;}}
.wx-val{{width:78px;text-align:right;color:#b9ad94;font-size:12px;}}
.day-emph .wx-name{{color:var(--gold-bright);}}
.card{{background:#15110a;border:1px solid rgba(212,175,110,.25);border-radius:10px;padding:16px 18px;margin-top:14px;}}
.card h3{{color:var(--gold);margin:0 0 10px;font-size:16px;letter-spacing:1px;}}
.kv{{font-size:14px;margin:6px 0;}}
.kv b{{color:var(--gold-bright);}}
.dayun-axis{{display:flex;flex-wrap:wrap;gap:10px;}}
.dyun{{background:#15110a;border:1px solid rgba(212,175,110,.25);border-radius:8px;padding:10px 12px;min-width:78px;text-align:center;}}
.dyun.cur{{border-color:var(--gold);background:rgba(212,175,110,.12);box-shadow:0 0 12px rgba(212,175,110,.35);}}
.dy-ganzhi{{color:var(--gold-bright);font-size:18px;font-weight:bold;}}
.dy-age{{font-size:12px;color:#a89c84;}}
.src{{display:block;font-size:11px;color:#7d7363;margin-top:4px;}}
.note{{font-size:12px;color:#8a7e68;margin-top:8px;}}
.rep-sec{{background:#15110a;border:1px solid rgba(212,175,110,.22);border-radius:10px;padding:16px 18px;margin:14px 0;}}
.rep-sec h3{{color:var(--gold-bright);margin:0 0 10px;font-size:17px;letter-spacing:1px;border-bottom:1px dashed rgba(212,175,110,.3);padding-bottom:8px;}}
.rep-body{{font-size:14.5px;color:var(--ink);white-space:pre-wrap;}}
.disclaimer{{margin-top:34px;border:1px dashed var(--red);border-radius:10px;padding:14px 16px;color:#c9a59c;font-size:12px;background:rgba(196,74,60,.05);}}
@media(max-width:720px){{.pillars{{grid-template-columns:1fr 1fr;}}.p-gan{{font-size:34px;}}}}
</style></head>
<body><div class="wrap">

<header>
  <h1>八 字 命 盘</h1>
  <div class="sub">BAZI · 己土日主 · 杂气格 · 子平推演</div>
  <div class="meta">公历 1989-01-09 10:00 · 男 · 生肖龙<br>
  四柱：{pillars['year']} {pillars['month']} {pillars['day']} {pillars['time']}</div>
</header>

<h2>一、四柱排盘</h2>
<div class="pillars">{pillar_cards}</div>

<h2>二、五行强弱（原始得气）</h2>
<div class="card">
  <div class="kv">日主：<b>己土</b>　判定：<b>{s8['strength']}</b></div>
  <div class="kv">生助日主 {s8['support_vs_consume']['生助日主']}%　｜　克泄耗日主 {s8['support_vs_consume']['克泄耗日主']}%</div>
  {wuxing_bars}
</div>

<h2>三、格局与用神三源合参</h2>
<div class="card">
  <h3>格局</h3>
  <div class="kv">格局：<b>{s9['pattern']}</b>　说明：{s9['description']}</div>
  <h3 style="margin-top:14px;">用神综合</h3>
  <div class="kv">最终用神 <b>{s10['final_yong']}</b>　喜神 <b>{s10['final_xi']}</b>　忌神 <b>{s10['final_ji']}</b></div>
  <div class="kv">综合建议：{s10['synthesis']['综合建议']}</div>
</div>

<h2>四、大运与流年（2026）</h2>
<div class="card">
  <h3>大运时间轴</h3>
  <div class="dayun-axis">{dayun_axis}</div>
  <div class="kv" style="margin-top:12px;">当前大运：<b>{s11['current_dayun']['ganzhi']}</b>（{s11['current_dayun']['start_age']}-{s11['current_dayun']['end_age']}岁）　判定：<b>{s11['dayun_judgment']}</b></div>
  <div class="kv">2026 流年：<b>{s11['liunian']['ganzhi']}</b>　判定：<b>{s11['liunian_judgment']}</b></div>
  <div class="kv">综合：{s11['overall_judgment']}</div>
</div>

<h2>五、袁天罡称骨</h2>
{chengu_html}

<h2>六、大白话解读（重写版·逐节详解）</h2>
<div class="note">以下为重写后、面向非命理读者的通俗解读，每一节均结合本盘真实数据，逐句解释古诀与术语，拒绝苍白空话。</div>
{report_html}

<div class="disclaimer">
  ⚠️ 以上为玄学体系的传统解读与象征推演，仅供参考。本回复由 AI 生成，不构成医疗、法律、财务或投资建议；命理是参考，不是定数。涉及健康、法律、重大财务决策请咨询相应专业人士。
</div>

</div></body></html>"""

out = '八字-1989-01-09-男-己土.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print('WROTE', out, '| sections:', len(pl['sections']))
