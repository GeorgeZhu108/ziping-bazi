# 八字引擎 · 工程与考据经验沉淀（LEARNINGS）

> 仅记录经实测验证、可复用的结论与坑点。所有命理结论须有古籍出处 + 多源交叉验证，禁止臆想。

## 一、报告撰写铁律（用户强约束）
- **大白话解读必须「数据驱动、逐句拆解」，禁止苍白空话。** 用户原话批评：「解释太过苍白 不详细」。
- 每节须做到：① 引用古诀原文 → ② 逐句/逐词解释 → ③ 绑定本盘真实数值（raw_weight / scores / 得令得地得势）→ ④ 落到具体人生维度（财富/事业/健康/感情/人际/学业）。
- 术语出现即解释：如「杂气格」必须 step-by-step 推（月支∈四库→藏干→透干→八格不清）；「用神丙/甲/癸」必须点明其十神角色（正印/正官/偏财）与本义。
- 已落地：engine.build_plain_language 重写，11 节；data.py 新增 DITIANSUI_XINGXIANG_NOTE（十干古诀逐句白话）。

## 二、气候判定 bug 与修复（关键）
- **错误做法**：用 raw_weight(水) vs raw_weight(火) 大小直接判「偏寒/偏燥」。曾把「己土·丑月（三冬）」误判为「偏暖燥」，与调候用丙暖局自相矛盾。
- **正确做法**：气候状态应由「调候用神五行」反推——调候用神为火 → 本局偏寒需暖；为水 → 偏燥需润；无明确调候 → 寒暖尚匀。见 engine.build_plain_language 中【调候用神 与 扶抑用神】段。

## 三、年界双轨制（必须透明标注，非 bug）
- **八字年柱 / 月柱 / 日柱 / 时柱** 全部取自 lunar-python `getBaZi()`，即**立春年界**（业界绝大多数在线排盘网站同源）。
- **称骨** 单独取 `getYearInGanZhi()`（春节年界）+ `leap_aware_month`（闰月十五分界），属古籍/袁天罡流派口径。
- 两者在「立春↔春节」窗口内会**故意不一致**（例：1988-02-05 立春年界=戊辰，春节年界=丁卯）。测试须显式列出此分歧，不得当作偏差。
- 验证：tests/test_external_crosscheck.py 用 10 组参数，月/日/时/称骨与「lunar 原生」+「手写独立算法」零偏差；仅窗口案例出现设计性年界分歧。

## 四、称骨进制澄清（用户曾质疑「16进制/半斤八两」）
- 袁天罡称骨是**十进制**：1 两 = 10 钱，非斤↔两的十六进制。参见 chengu._fmt_liang 使用 `divmod(qian, 10)`。
- 权重表已与在线主流共识版（xuenb/buyiju/wnl8/yourchineseastrology 一致，zhouyi.cc 实例交叉验证）逐条比对，**零偏差**（tests/test_chengu_online_diff.py）。

## 五、晚子时（23:00–23:59）口径
- lunar-python 对 23:00–23:59 的**时柱**取「次日日干」起遁（如 戊日 23:30 → 时柱甲子，因次日己日 子时=甲子），而日柱仍属当日。
- 引擎 `late_zishi_rule`：'current-day'（默认，与 lunar 一致，不跨日）/ 'next-day'（整日进位）。两者均经测试正确，非 bug。
- 手写独立时柱算法须复刻此规则：hour==23 时用 (y,m,d)+1 日的日干起五鼠遁。

## 六、外部资源交叉验证方法论（回答「有没有多参数比对其他资源」）
- **不依赖一次性网页抓取**（易被反爬/JS 渲染干扰、不可复现）。采用两层稳定 oracle：
  1. **链路 A（业界标准库）**：lunar-python `getBaZi()` —— 在线排盘站底层同源，作为基准。
  2. **链路 B（手写独立算法，零依赖 lunar）**：日柱=儒略日 JDN 公式（锚定 1949-10-01 开国大典=甲子 校准）；时柱=五鼠遁；月柱=节气定月支 + 五虎遁；称骨=复算 chengu。
- 覆盖维度须刻意制造差异：不同日主/性别/东经西经本初子午线/闰年/年末年初/晚子时/年界窗口。
- 用神/格局另以古典文本 golden 值校验（tests/test_full_regression.py，梁湘润穷通宝鉴 120 条 + 子平真诠格局表）。

## 七、测试清单（CI 基线）
- test_regression.py（10/10）、test_full_regression.py（120 条 + 溯源）、test_late_zishi_regression.py、
  test_chengu_online_diff.py（在线共识零偏差）、test_chengu_lunar.py、test_ocr_parallel.py（OCR 多线程）、
  **test_external_crosscheck.py（多参数×多源四柱/称骨零偏差，本文件第六节所述）**。
- 提交前须全绿；任一偏差须先定位是「引擎 bug」还是「独立 oracle 实现错」，禁止静默放过。

## 八、CI 固化（多参数×多源交叉验证进流水线）
- 交付物：`.github/workflows/ci.yml`（push/PR 触发，Python 3.11/3.13 矩阵）+ `requirements.txt`（flask + lunar-python）+ `run_ci.sh`（本地一键跑全套确定性测试，无需 GitHub 也可验）。
- **CI 只跑确定性、可离线套件**：test_regression / test_full_regression / test_late_zishi_regression / test_chengu_online_diff / test_chengu_lunar / test_external_crosscheck / test_ziwei。
- **显式排除** test_ocr_parallel（需 rapidocr + GPU/CPU 重负载）、test_bing_regression / test_skill_crosscheck（需网络/外部技能）：这些非确定性、不可离线复现，不适合 CI。
- 当前仓库无远程、本会话 GitHub MCP 不可用 → 工作流文件先就位，用户建 GitHub 仓库推送即自动生效。

## 九、紫微斗数集成（Renhuai123/ziwei-doushu 纯 Python 移植核心）
- **溯源（非臆造，逐条可核对）**：上游 `algorithm.ts` 实为 iztro（SylarLong/iztro, MIT）的薄封装；真排盘数学在 iztro。故 `ziwei.py` 直接移植：
  - 命宫/身宫/五行局/宫干/十二宫/大限 = iztro `src/astro/palace.ts` + `astro.ts`；
  - 十四主星安星诀、禄存羊陀马/魁钺/左右/昌曲/红鸾天喜/地空地劫/火铃 = iztro `src/star/location.ts` + `majorStar.ts`；
  - 四化表 / 辅星表 / 宫名 / 五行局映射 = Renhuai123 `lib/ziwei/constants.ts` + `sihua.ts`。
- **关键口径（与 iztro 默认对齐，已显式标注）**：
  - 年界：**立春换年**（与八字年柱同源，用 `getBaZi()[0]`）；故立春前出生年干取上一年（例 1989-01-09 → 戊辰，年干戊）。
  - 月：**农历月**（非节气月）；闰月前半月用上月、后半月用本月（fix_leap）。
  - 时辰：23:00–00:59 为子时；**晚子时 23:00–23:59 归次日**（iztro normalizeDayBoundary 默认），农历日随之取次日。
  - 五行局：以**命宫干支**纳音取数（干 甲乙1丙丁2戊己3庚辛4壬癸5；支 子午丑未1 寅申卯酉2 辰戌巳亥3；>5 减5 → 1木2金3水4火5土 → 局数 木3金4水2火6土5）。
  - 紫微起星诀：局数除日数至整除，商%12−1，奇偶偏移定紫微；天府=12−紫微（对待宫）。
- **验证（iztro 自身注释金标准示例，非自造）**：
  - 起紫微：27日木三局→戌 / 13日火六局→亥 / 6日土五局→未（tests/test_ziwei.py 逐字断言）。
  - 五行局：丙子→水二局 / 辛未→土五局 / 庚申→木三局。
  - 四化表、命宫公式（农历五月子时→命宫午）、紫微铁律（紫微≠天府同宫、十四主星各唯一宫）全绿；当前 5/5。
- 辅星已实现：禄存/擎羊/陀罗/天马/天魁/天钺/左辅/右弼/文昌/文曲/红鸾/天喜/地空/地劫/火星/铃星。宫干按五虎遁绕地支序（寅宫=年干五虎遁寅月干，顺行）。
