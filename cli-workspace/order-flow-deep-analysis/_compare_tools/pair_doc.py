# -*- coding: utf-8 -*-
"""生成 PAIR v1.1 对照模板 baseline 文档（浅色主题）"""
import json, sys
from pathlib import Path
from datetime import datetime

SKILL = Path("/Users/zhijiebian/.agents/skills/order-flow-deep-analysis/scripts")
OUT = Path("/Users/zhijiebian/.gemini/cli-workspace/order-flow-deep-analysis")
sys.path.insert(0, str(SKILL))
import baseline as B
import baseline_pair as P

tpl = P.build()
A, Bt = tpl["A"], tpl["B"]
A2, B2 = tpl.get("A_alt") or {}, tpl.get("B_alt") or {}


def fm(key, r):
    v = r.get(key)
    if key == "vwap_reclaim":
        return "未收复" if v is None else "%d 秒" % int(float(v))
    if v is None:
        return "—"
    v = float(v)
    return ("%+.0f" % v) if abs(v) >= 100 else ("%+.2f" % v)


dec_rows = []
for key, name, unit, note in P.DECISIVE:
    dec_rows.append("<tr><td style='font-weight:600'>%s</td><td style='color:#475569'>%s</td>"
                    "<td style='text-align:right;color:#047857'><b>%s</b></td>"
                    "<td style='text-align:right;color:#b45309'><b>%s</b></td>"
                    "<td style='color:#94a3b8'>%s ／ %s</td><td style='color:#475569'>%s</td></tr>"
                    % (name, unit, fm(key, A), fm(key, Bt), fm(key, A2), fm(key, B2), note))

non_rows = []
for key, name, note in P.NON_DECISIVE:
    non_rows.append("<tr><td style='font-weight:600'>%s</td><td style='text-align:right'>%s</td>"
                    "<td style='text-align:right'>%s</td><td style='color:#475569'>%s</td></tr>"
                    % (name, fm(key, A), fm(key, Bt), note))


def rank_rows(day, highlight):
    rows = B.load_ticks(day)
    out = []
    for t_sec, ext in B.candidates(rows, 'low'):
        x = P.vector(day, B.hms(t_sec), ext)
        s, n, verdict, votes, gate_ok = P.judge(x, tpl)
        out.append((s, B.hms(t_sec), ext, verdict, x, gate_ok))
    out.sort(key=lambda r: -r[0])
    html = []
    for s, hm, ext, verdict, x, gate_ok in out:
        cls = "#047857" if verdict.startswith("A 型") else ("#b45309" if verdict.startswith("不可判") else "#b91c1c")
        tag = " ← 锚定案例" if hm == highlight else ""
        html.append("<tr><td>%s</td><td>%.2f</td><td style='color:%s;font-weight:600'>%s</td>"
                    "<td style='text-align:center'>%+d/9</td><td style='text-align:center'>%s</td>"
                    "<td style='text-align:center'>%s</td><td style='text-align:center'>%s</td>"
                    "<td style='text-align:center'>%s</td><td style='text-align:center'>%s</td>"
                    "<td style='text-align:center'>%s</td><td style='text-align:center'>%s</td></tr>"
                    % (hm, ext, cls, verdict, s, "PASS" if gate_ok else "BLOCK",
                       ("%+.1f" % float(x["mfe60"])) if x.get("mfe60") is not None else "—",
                       ("%+.1f" % float(x["mae60"])) if x.get("mae60") is not None else "—",
                       ("%+.1f" % float(x["mfe120"])) if x.get("mfe120") is not None else "—",
                       ("%.1f" % float(x["maxrev45"])) if x.get("maxrev45") is not None else "—",
                       ("%.0f" % float(x["cvd_delta_30m"])) if x.get("cvd_delta_30m") is not None else "—",
                       ("%.1f" % float(x["zone_span"])) if x.get("zone_span") is not None else "—") + tag)
    return "".join(html)


gen = datetime.now()
fname = "order_flow_baseline_PAIR_v1.1_%s_%s.html" % (gen.strftime('%Y-%m-%d'), gen.strftime('%H%M'))

TPL = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>Order Flow Baseline PAIR v1.1 · 只用 09-14 / 09-15 的对照模板</title>
<style>
 body{background:#f8fafc;color:#0f172a;font-family:-apple-system,"PingFang SC","Helvetica Neue",Arial,sans-serif;margin:0;padding:22px;line-height:1.62}
 .wrap{max-width:1200px;margin:0 auto}
 h1{font-size:1.3rem;margin:0 0 4px}
 h2{font-size:1.03rem;margin:24px 0 8px;padding-left:9px;border-left:4px solid #1d4ed8}
 h3{font-size:0.94rem;margin:14px 0 6px;color:#1e293b}
 .sub{color:#64748b;font-size:0.82rem;margin-bottom:14px}
 .card{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;margin:10px 0;overflow-x:auto}
 table{width:100%;border-collapse:collapse;font-size:0.8rem;margin:6px 0}
 th{background:#eef2f7;color:#334155;text-align:left;padding:7px 9px;border:1px solid #e2e8f0;font-weight:600}
 td{padding:6px 9px;border:1px solid #e9eef4;vertical-align:top}
 tr:nth-child(even) td{background:#fbfdff}
 code{background:#f1f5f9;padding:1px 5px;border-radius:4px;font-size:0.78rem}
 ul{margin:6px 0 6px 20px;padding:0}li{margin:3px 0}
 .foot{color:#94a3b8;font-size:0.74rem;margin-top:18px}
 .tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:0.72rem;border:1px solid #cbd5e1;color:#475569;background:#f8fafc}
 .warn{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:10px 12px;font-size:0.82rem;color:#78350f}
 .mono{font-variant-numeric:tabular-nums}
</style></head><body><div class="wrap">
<h1>Order Flow Baseline PAIR v1.1 —— 只用 2026-09-14 / 09-15 两个相反案例的对照模板</h1>
<div class="sub">锚点 A：09-14 07:54 @7664.00（真反转，后验 mfe60 +42.5 / mae60 +1.8） ｜ 锚点 B：09-15 07:53 @7643.50（假反弹，后验 mfe60 +16.3 / mae60 0.0）｜ 全部阈值与判据只来自这两天 · 无前视 ✓ · 浅色主题 ✓ · 仅分析参考，不接入自动下单 ✓</div>

<h2>0. 方法：为什么改成「对照模板」而不是大样本标定</h2>
<div class="card">
<ul>
<li>样本外数据（8/16–9/13）与这两天<b>不是同一组对照</b>：前者没有「同一形态、相反结局」的配对，用它标定会把与反转无关的市场状态差异（趋势/区间、波动率）混进阈值。</li>
<li>因此改为：把两个案例各算一条特征向量（<b>A 模板 / B 模板</b>），对一个新候选低点<b>逐维比较它更像谁</b>（不设人为阈值，只比较距离），再叠加一条两案例完全分开的<b>硬门槛</b>。</li>
<li>局限已在第 5 节写明：<b>n=1 正例 + n=1 反例，无法估计误报率</b>；本模板是「结构判据清单 + 用法」，不是统计模型。它的验证只能做两件事：①两个锚点彼此可分（已通过：A +9/9、B −9/9）；②<b>在这两天内部</b>对全部候选低点做排序是否合理（第 4 节）。</li>
</ul>
</div>

<h2>1. 两个锚点的特征向量（决定性维度）</h2>
<div class="card">
<table>
<tr><th style="width:20%">维度</th><th style="width:8%">单位</th><th style="width:11%;text-align:right">A 07:54</th><th style="width:11%;text-align:right">B 07:53</th><th style="width:16%">引擎口径复核 A 07:55 ／ B 08:00</th><th style="width:34%">含义</th></tr>
%(dec)s
</table>
<p style="font-size:0.8rem;color:#475569;margin:8px 0 0"><b>稳健性</b>：换用引擎时间戳锚点（A 07:55 / B 08:00），9 个维度的分离方向与量级完全一致 ⇒ 模板不依赖「低点取哪一分钟」。</p>
</div>

<h2>2. 判定规则：1 条硬门槛 + 9 维投票</h2>
<div class="card">
<ul>
<li><b>硬门槛（必须过）</b>：低点 ±15 分钟累计 Delta &gt; 0。两案例在此维完全分开（A +2,326 / +2,257，B −2,566 / −1,510）。<b>不过门槛 = 不参与</b>。</li>
<li><b>投票</b>：其余 8 维 + 门槛维共 9 维，逐维判断「候选值离 A 更近还是离 B 更近」，像 A 记 +1、像 B 记 −1。</li>
<li><b>判定</b>：门槛过 且 得分 ≥ +6 → <span class="tag">A 型（低点吸收）</span>；得分 ≤ −6 → <span class="tag">B 型（假反弹）</span>；其余 <span class="tag">不可判</span>。</li>
</ul>
<p style="font-size:0.8rem;color:#475569;margin:6px 0 0">为什么门槛必须单独拿出：09-14 的 07:19 与 07:24 在两个失败低点上<b>投票得分也是 +7</b>（结构像 A），但它们的 ±15 分钟累计 Delta 为 −546 / −416（净流反向），随后分别逆向 18.8 点与 9.0 点。只靠投票会误判，加上门槛后被正确拦下。</p>
</div>

<h2>3. 无区分度维度（同样重要的结论：这些<b>不能</b>当判据）</h2>
<div class="card">
<table><tr><th style="width:24%">维度</th><th style="width:12%;text-align:right">A 07:54</th><th style="width:12%;text-align:right">B 07:53</th><th>为什么不算判据</th></tr>
%(non)s
</table>
<p style="font-size:0.8rem;color:#475569;margin:8px 0 0">其中三条直接修正了上一轮基于单案例叙述的判据：<b>①「低点后出现 ≥100 手主动买单」无区分度</b>（B 的 300 手比 A 的 257 手更大）；<b>②「低点后 15 分钟净买」无区分度</b>（B 甚至更大 +1,602 vs +1,355）；<b>③「低点未被有效跌破」不能证明反转</b>——B 的低点根本没被跌破，却是全天无反转。</p>
</div>

<h2>4. 在两日内验证（全部候选低点排序）</h2>
<h3>4.1 2026-09-14（真反转日，5 个候选低点）</h3>
<div class="card"><table class="mono">
<tr><th>时刻</th><th>极值</th><th>判定</th><th>得分</th><th>净流门槛</th><th>mfe60</th><th>mae60</th><th>mfe120</th><th>maxrev45</th><th>CVD±15m</th><th>低点区停留</th></tr>
%(rankA)s
</table>
<p style="font-size:0.8rem;color:#475569;margin:6px 0 0">结果：判定 <b>A 型 2 个，均成功</b>（07:54 → +42.5/+1.8；07:40 → +31.5/+2.5）；两个「结构像 A 但净流反向」的失败低点（07:19、07:24）被硬门槛拦下；10:16 判为不可判（+8.0/+1.8，属区间反弹）。</p>
</div>
<h3>4.2 2026-09-15（假反弹日，11 个候选低点）</h3>
<div class="card"><table class="mono">
<tr><th>时刻</th><th>极值</th><th>判定</th><th>得分</th><th>净流门槛</th><th>mfe60</th><th>mae60</th><th>mfe120</th><th>maxrev45</th><th>CVD±15m</th><th>低点区停留</th></tr>
%(rankB)s
</table>
<p style="font-size:0.8rem;color:#475569;margin:6px 0 0">结果：<b>全天没有任何候选低点通过硬门槛</b>（11/11 BLOCK），即模板在这天不给出 A 型信号。当日前向最好的低点 10:22（+13.0/+1.0）也只是「不可判」——它是可做的区间反弹，但不是反转。</p>
</div>

<h2>5. 局限与使用纪律（必读）</h2>
<div class="card">
<div class="warn">
<ul>
<li><b>n=1 正例 + n=1 反例</b>：本模板只能证明「两个案例可分」与「在这两日内排序合理」，<b>无法给出误报率</b>。任何新增判据都必须等新的「同形态相反结局」配对出现后再校准。</li>
<li>9 维投票的「近 A 记 +1」是无权重设计：维度间量纲不同，只做同维内的距离比较，不做跨维加权（避免用 2 个样本硬凑权重）。</li>
<li>门槛用的是「±15 分钟累计 Delta &gt; 0」这一条：若把它换成「低点前 30 分钟净 Delta &gt; 0」，09-14 的 <b>07:40（后验 +31.5）会被误杀</b>；故门槛只保留 CVD 这一条，前段流向作为投票维度之一。</li>
<li>低点区「停留时长」在本对案例中是重要维度（A 24–39 分钟 vs B 0.4–9 分钟），但它与「低点区成交量」一样对取点口径敏感：必须用与模板一致的因果口径（1 分钟极值 + 30 分钟新低回撤 ≥8 点）来取候选。</li>
<li>模板只回答「这个低点是否具备吸收结构」，不含仓位、止损、目标（下单层）；不接入自动下单。</li>
</ul>
</div>
<div class="foot">生成 %(gen)s · 模板文件 scripts/baseline_templates_v1.json · 实现 scripts/baseline_pair.py · 报告目录 /Users/zhijiebian/.gemini/cli-workspace/order-flow-deep-analysis/</div>
</div>
</div></body></html>"""

import re as _re
H = _re.sub(r'%(?!\()', '%%', TPL) % {
    'dec': "".join(dec_rows), 'non': "".join(non_rows),
    'rankA': rank_rows('2026-09-14', '07:54'), 'rankB': rank_rows('2026-09-15', '07:53'),
    'gen': gen.strftime('%Y-%m-%d %H:%M')}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / fname).write_text(H)
print("WROTE", OUT / fname)
