# -*- coding: utf-8 -*-
"""生成 1990-10-08 男 八字命盘黑金风 HTML 报告（八字·运势分析师专用）"""
import sys, json
sys.path.insert(0, '.')
from engine import calculate_bazi
from data import HIDDEN_STEMS, STEM_ATTRS, BRANCH_ATTRS, TEN_GOD_CODE_TO_NAME

BIRTH = (1990, 10, 8, 9, 30, '男')
res = calculate_bazi(*BIRTH[:5], gender=BIRTH[5], current_year=2026)

s1 = res['steps'][0]   # 历法
s2 = res['steps'][1]   # 四柱
s4 = res['steps'][3]   # 十神
s6 = res['steps'][5]   # 刑冲合害
s7 = res['steps'][6]   # 神煞
s8 = res['steps'][7]   # 五行
s9 = res['steps'][8]   # 格局
s10 = res['steps'][9]  # 用神
s11 = res['steps'][10] # 大运流年
s12 = res['steps'][11] # 综合

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

# 四柱卡片
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

# 五行条形
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
      <span class="wx-val">{sc}%</span>
    </div>"""

# 大运时间轴
s3 = res['steps'][2]
dayun_axis = ""
for d in s3['dayun']:
    cur = (d['number'] == s11['current_dayun']['number'])
    dayun_axis += f"""<div class="dyun{' cur' if cur else ''}">
      <div class="dy-ganzhi">{d['ganzhi']}</div>
      <div class="dy-age">{d['start_age']}-{d['end_age']}岁</div>
    </div>"""

# 关系
rels = ""
for r in s6['relations']:
    if r['type'] == '刑':
        txt = f"{r['type']}·{r['xing_name']}：{'、'.join(r['branches'])} — {r['meaning']}"
    elif r['type'] == '半合':
        txt = f"{r['type']}·{r['name']}：{'、'.join(r['branches'])} — {r['meaning']}"
    elif r['type'] == '天干五合':
        txt = f"天干五合：{'、'.join(r['stems'])}（化{r['化合五行']}）— {r['meaning']}"
    else:
        txt = r.get('meaning', '')
    rels += f"<li>{txt}<span class='src'>{r.get('source','')}</span></li>"

# 神煞
sh = ""
for x in s7['shensha']:
    sh += f"<span class='sha'>{x['name']}<i>{'、'.join(x['matched'])}</i></span>"

# 用神三源
qk = s10['components']['穷通宝鉴']
ft = s10['components']['滴天髓扶抑']
gj = s10['components']['格局用神']
syn = s10['synthesis']

html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>八字命盘 · 1990-10-08 男</title>
<style>
:root{{--bg:#0e0b08;--gold:#d4af6e;--gold-bright:#f3d99c;--ink:#ece4d3;--red:#c44a3c;--green:#6b9a5c;}}
*{{box-sizing:border-box;}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:"PingFang SC","Hiragino Sans GB","STSong",serif;line-height:1.7;}}
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
.wx-val{{width:48px;text-align:right;color:#b9ad94;font-size:12px;}}
.day-emph .wx-name{{color:var(--gold-bright);}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:18px;}}
.card{{background:#15110a;border:1px solid rgba(212,175,110,.25);border-radius:10px;padding:16px 18px;}}
.card h3{{color:var(--gold);margin:0 0 10px;font-size:16px;letter-spacing:1px;}}
.tag{{display:inline-block;background:rgba(212,175,110,.15);color:var(--gold-bright);padding:2px 10px;border-radius:20px;font-size:13px;margin:2px 4px 2px 0;border:1px solid rgba(212,175,110,.3);}}
.kv{{font-size:14px;margin:6px 0;}}
.kv b{{color:var(--gold-bright);}}
.dayun-axis{{display:flex;flex-wrap:wrap;gap:10px;}}
.dyun{{background:#15110a;border:1px solid rgba(212,175,110,.25);border-radius:8px;padding:10px 12px;min-width:78px;text-align:center;}}
.dyun.cur{{border-color:var(--gold);background:rgba(212,175,110,.12);box-shadow:0 0 12px rgba(212,175,110,.35);}}
.dy-ganzhi{{color:var(--gold-bright);font-size:18px;font-weight:bold;}}
.dy-age{{font-size:12px;color:#a89c84;}}
ul.clean{{list-style:none;padding-left:0;}}
ul.clean li{{margin:8px 0;font-size:14px;}}
.src{{display:block;font-size:11px;color:#7d7363;margin-top:2px;}}
.sha{{display:inline-block;background:rgba(196,74,60,.12);border:1px solid rgba(196,74,60,.35);color:#e8b9b0;padding:4px 10px;border-radius:6px;font-size:13px;margin:4px 6px 0 0;}}
.sha i{{display:block;font-style:normal;font-size:10px;color:#a89c84;}}
.summary{{background:linear-gradient(160deg,#1a140b,#100b06);border:1px solid var(--gold);border-radius:12px;padding:20px;margin-top:10px;}}
.summary p{{font-size:15px;color:var(--gold-bright);margin:10px 0;}}
.disclaimer{{margin-top:34px;border:1px dashed var(--red);border-radius:10px;padding:14px 16px;color:#c9a59c;font-size:12px;background:rgba(196,74,60,.05);}}
.note{{font-size:12px;color:#8a7e68;margin-top:8px;}}
@media(max-width:720px){{.pillars,.grid2{{grid-template-columns:1fr;}}.p-gan{{font-size:34px;}}}}
</style></head>
<body><div class="wrap">

<header>
  <h1>八 字 命 盘</h1>
  <div class="sub">BAZI FOUR PILLARS CHART · 子平推演</div>
  <div class="meta">公历 1990-10-08 09:30 · 男 · 生肖马 · 农历 一九九〇年八月二十<br>
  节气：寒露（1990-10-08 21:13，出生在寒露之前 → 酉月乙酉）</div>
</header>

<h2>一、四柱排盘</h2>
<div class="pillars">{pillar_cards}</div>
<div class="note">月柱按「节气精确时刻」划分：寒露 10-08 21:13 之前属酉月（乙酉），之后属戌月（丙戌）。本命生于 09:30，故为乙酉。</div>

<h2>二、五行强弱</h2>
<div class="card">
  <div class="kv">日主：<b>丙火</b>　判定：<b>{s8['strength']}</b></div>
  <div class="kv">判定依据：{s8['strength_reason']}</div>
  <div class="kv">生助日主 {s8['support_vs_consume']['生助日主']}%　｜　克泄耗日主 {s8['support_vs_consume']['克泄耗日主']}%</div>
  {wuxing_bars}
  <div class="note">丙火生于酉月（仲秋金旺火囚，失令）；但日坐午火羊刃、年时双午、时支巳火禄，地支火根极厚（得地）；月干乙木正印透出生扶（得势）。故虽失令，仍作中和偏旺论。</div>
</div>

<h2>三、十神与格局</h2>
<div class="grid2">
  <div class="card">
    <h3>十神分布</h3>
    <div class="kv">年干 <b>庚</b> · 偏财</div>
    <div class="kv">月干 <b>乙</b> · 正印</div>
    <div class="kv">日干 <b>丙</b> · 日主</div>
    <div class="kv">时干 <b>癸</b> · 正官</div>
    <div class="note">年干庚（偏财）与月干乙（正印）天干五合化金 —— 财星合住印星，印星受制，生身之力被羁绊。</div>
  </div>
  <div class="card">
    <h3>格局判定</h3>
    <div class="kv">格局：<b>{s9['pattern']}</b></div>
    <div class="kv">说明：{s9['description']}</div>
    <div class="kv">依据：月支 {s9['reason'].get('月支')} 本气 {s9['reason'].get('月支本气藏干')}（{s9['reason'].get('月支本气十神')}）当令为格。</div>
  </div>
</div>

<h2>四、用神三源合参</h2>
<div class="grid2">
  <div class="card">
    <h3>穷通宝鉴 · 调候</h3>
    <div class="kv">调候用神：<b>{qk['用神']}（{qk['用神五行']}）</b></div>
    <div class="kv">喜神：{qk['喜神']}　忌神：{qk['忌神']}</div>
    <div class="kv">说明：{qk['说明']}</div>
  </div>
  <div class="card">
    <h3>滴天髓 · 扶抑</h3>
    <div class="kv">日主：{ft['日主强弱']}</div>
    <div class="kv">扶抑方向：{ft['扶抑方向']}</div>
    <div class="kv">喜用五行：{'、'.join(ft['喜用五行'])}</div>
  </div>
</div>
<div class="card" style="margin-top:14px;">
  <h3>三命通会 · 格局用神 + 综合</h3>
  <div class="kv">格局用神：<b>{gj['格局用神']}</b>　{gj['说明']}</div>
  <div class="kv">综合建议：{syn['综合建议']}</div>
  <div class="kv">最终用神 <b>{s10['final_yong']}</b>　喜神 <b>{s10['final_xi']}</b>　忌神 <b>{s10['final_ji']}</b></div>
</div>

<h2>五、大运与流年（2026）</h2>
<div class="card">
  <h3>大运时间轴</h3>
  <div class="dayun-axis">{dayun_axis}</div>
  <div class="kv" style="margin-top:12px;">当前大运：<b>{s11['current_dayun']['ganzhi']}</b>（{s11['current_dayun']['start_age']}-{s11['current_dayun']['end_age']}岁）　判定：<b>{s11['dayun_judgment']}</b></div>
  <div class="kv">{s11['dayun_comment']}</div>
  <div class="kv" style="margin-top:8px;">2026 流年：<b>{s11['liunian']['ganzhi']}</b>（本命年·值太岁）　判定：<b>{s11['liunian_judgment']}</b></div>
  <div class="kv">关系：{'、'.join(s11['liunian_relations'])}；流年与日柱丙午相同 → 伏吟。</div>
  <div class="kv">{s11['liunian_comment']}</div>
  <div class="kv">综合：{s11['overall_judgment']} —— {s11['comment']}</div>
</div>

<h2>六、神煞与刑冲合害</h2>
<div class="card">
  <h3>神煞</h3>
  <div>{sh}</div>
  <h3 style="margin-top:16px;">刑冲合害</h3>
  <ul class="clean">{rels}</ul>
  <div class="note">羊刃（日干丙见午，年日双见）→ 性格刚烈、有魄力亦需防冲动；将星主领导才能；亡神主谋略；午午自刑主内心矛盾是非。</div>
</div>

<div class="summary">
  <h3 style="color:var(--gold-bright);margin:0 0 10px;">三句话总结</h3>
  <p>① 丙火日主坐羊刃、双午带禄，火根极厚，虽生酉月失令，仍以中和偏旺论，个性鲜明、有担当、不喜受人管束。</p>
  <p>② 月令酉金正财当令，年干庚金偏财透出，巳酉半合金局助财，财星旺盛；月干乙木正印被庚财合走（庚乙合化金），学业/贵人助力易受现实利益牵绊。</p>
  <p>③ 2026 丙午为本命年（值太岁）+ 流年与日柱伏吟 + 午午自刑，宜守不宜攻，注意情绪、是非与决策反复，正是沉淀内修之年。</p>
</div>

<div class="disclaimer">
  ⚠️ 以上为玄学体系的传统解读与象征推演，仅供参考。本回复由 AI 生成，不构成医疗、法律、财务或投资建议；命理是参考，不是定数。涉及健康、法律、重大财务决策请咨询相应专业人士。
</div>

</div></body></html>"""

out = 'D:/Study/Claw University/八字-1990-10-08-男.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print('WROTE', out)
