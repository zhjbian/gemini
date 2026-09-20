# -*- coding: utf-8 -*-
"""生成 baseline 规格文档（浅色主题 HTML）"""
import json
from pathlib import Path
from datetime import datetime

SKILL = Path("/Users/zhijiebian/.agents/skills/order-flow-deep-analysis")
OUT = Path("/Users/zhijiebian/.gemini/cli-workspace/order-flow-deep-analysis")
spec = json.load(open(SKILL / "scripts" / "baseline_spec_v1.json"))
low = json.load(open('/tmp/base_scan_low.json'))
high = json.load(open('/tmp/base_scan_high.json'))

def pct(v, nd=1):
    return "—" if v is None else ("{:." + str(nd) + "f}%").format(100 * v)

def lift(v):
    return "—" if v is None else ("{:+.1f}pt").format(v)

gen = datetime.now()
fname = "order_flow_baseline_LAR_v1_%s_%s.html" % (gen.strftime('%Y-%m-%d'), gen.strftime('%H%M'))

# ── 表格 ──
layer_rows = []
for lname, items in spec["layers"].items():
    first = True
    for k, v in items.items():
        layer_rows.append("<tr><td style='white-space:nowrap;font-weight:600;color:#0f172a'>%s</td><td>%s</td><td>%s</td><td style='color:#334155;white-space:nowrap'>%s</td></tr>"
                          % (lname if first else "", k, v["测"], v["实测"]))
        first = False
layer_html = "".join(layer_rows)

tier_rows = []
for mode, label in (("low", "LAR-v1 · 低位吸收反转（候选低点 n=184）"), ("high", "HDR-v1 · 高位派发镜像（候选高点 n=175）")):
    m = spec["measured"][mode]
    base = spec["measured"]["base_low"] if mode == "low" else spec["measured"]["base_high"]
    tier_rows.append("<tr><td colspan='5' style='background:#f1f5f9;font-weight:700;color:#0f172a'>%s ｜ 基准成功率 %s</td></tr>" % (label, pct(base)))
    for name in ("HIT", "WATCH", "AVOID-反例", "NEUTRAL", "V1_only", "V1+V2", "P&gt;=2"):
        key = "P>=2" if name == "P&gt;=2" else name
        d = m.get(key)
        if not d:
            continue
        r = d["rate"]
        tier_rows.append("<tr><td style='font-weight:600'>%s</td><td>%d</td><td><b style='color:%s'>%s</b></td><td>%s</td><td>%s</td></tr>"
                         % (name, d["n"], "#047857" if r >= base else "#b91c1c", pct(r),
                            lift(100 * (r - base)), pct(d.get("recall")) if d.get("recall") is not None else "—"))
tier_html = "".join(tier_rows)

def case_rows(items, mode):
    out = []
    for x in items:
        ok = (float(x["mfe_60"]) >= 15 and float(x["mae_60"]) <= 5) if mode == "low" else (float(x["mae_60"]) >= 15 and float(x["mfe_60"]) <= 5)
        out.append("<tr><td>%s %s</td><td style='font-weight:600;color:%s'>%s</td><td>%.2f</td><td>%.2f</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            x["day"], x["t"], "#047857" if x["verdict"] == "HIT" else ("#b45309" if x["verdict"] == "WATCH" else "#b91c1c"),
            x["verdict"], float(x["ext"]), float(x["pos_pct"]),
            "—" if x["zone_net"] is None else ("%+.0f" % float(x["zone_net"])),
            "—" if x["at_net"] is None else ("%+.0f" % float(x["at_net"])),
            "—" if x["at_big_max_buy"] is None else ("%.0f" % float(x["at_big_max_buy"])),
            "—" if x["mid_net"] is None else ("%+.0f" % float(x["mid_net"])),
            "%.1f" % float(x["maxrev_45"]),
            ("%s (mfe60 %+.1f / mae60 %+.1f)" % ("✓" if ok else "✗", float(x["mfe_60"]), float(x["mae_60"])))))
    return "".join(out)

anchor = [x for x in low if x["day"] in ("2026-09-14",) and x["t"] in ("07:40", "07:54")] + \
         [x for x in low if x["day"] in ("2026-09-15",) and x["t"] in ("07:50", "10:15")]
hit_cases = [x for x in low if x["verdict"] == "HIT"][:14]
avoid_cases = [x for x in low if x["verdict"] == "AVOID-反例"][:8]
use_rows = "".join("<tr><td><code>%s</code></td><td>%s</td></tr>" % r for r in [
    ("python3 baseline.py --date 2026-09-14 --at 07:54 --px 7664.00",
     "对指定候选低点出 P/V/C/反例四层判定 + 后验（后验列仅用于回看校验）"),
    ("python3 baseline.py --date 2026-09-15 --list",
     "列出当日 06:45–10:30 全部因果候选低点及其判定（用于盘后复盘）"),
    ("python3 baseline.py --scan --mode low --emit-json scan_low.json",
     "全样本事件研究：基准成功率 / 各判据提升 / 各档位精确率与召回率（重新标定用）"),
    ("python3 baseline.py --scan --mode high",
     "镜像（高位派发）验证：同一套逻辑取反，独立跑一遍，防止单边过拟合"),
    ("python3 baseline.py --emit-spec scripts/baseline_spec_v1.json",
     "导出本规格 JSON（版本化、可 diff）"),
])

TPL = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>Order Flow Baseline v1.0 · LAR 低位吸收反转 / HDR 镜像</title>
<style>
 body{background:#f8fafc;color:#0f172a;font-family:-apple-system,"PingFang SC","Helvetica Neue",Arial,sans-serif;margin:0;padding:22px;line-height:1.62}
 .wrap{max-width:1180px;margin:0 auto}
 h1{font-size:1.3rem;margin:0 0 4px}
 h2{font-size:1.03rem;margin:24px 0 8px;padding-left:9px;border-left:4px solid #1d4ed8}
 h3{font-size:0.94rem;margin:14px 0 6px;color:#1e293b}
 .sub{color:#64748b;font-size:0.82rem;margin-bottom:14px}
 .card{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;margin:10px 0}
 table{width:100%;border-collapse:collapse;font-size:0.8rem;margin:6px 0}
 th{background:#eef2f7;color:#334155;text-align:left;padding:7px 9px;border:1px solid #e2e8f0;font-weight:600}
 td{padding:6px 9px;border:1px solid #e9eef4;vertical-align:top}
 tr:nth-child(even) td{background:#fbfdff}
 code{background:#f1f5f9;padding:1px 5px;border-radius:4px;font-size:0.78rem}
 ul{margin:6px 0 6px 20px;padding:0}li{margin:3px 0}
 .foot{color:#94a3b8;font-size:0.74rem;margin-top:18px}
 .tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:0.72rem;border:1px solid #cbd5e1;color:#475569;background:#f8fafc}
 .warn{background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:10px 12px;font-size:0.82rem;color:#78350f}
</style></head><body><div class="wrap">
<h1>Order Flow Baseline v1.0 —— LAR（低位吸收反转） / HDR（镜像高位派发）</h1>
<div class="sub">锚定案例 2026-09-14 07:54 低点（真反转）｜ 负对照 2026-09-15 07:50 低点（假反弹）｜ 样本 27 个交易日（2026-08-16 ~ 09-15）· 候选低点 184 / 高点 175 ｜ 无前视 ✓ · 浅色主题 ✓ · 仅分析参考，不接入自动下单 ✓</div>

<h2>0. 这个 baseline 是什么 / 不是什么</h2>
<div class="card">
<ul>
<li><b>是</b>：把「2026-09-14 低点真反转」的 order flow 特征拆成 <b>可机检的三个时点层（P 预判 t+15 / V 验证 t+45 / C 确认 t+60）</b>，每条判据都给出样本内实测提升，并配 <b>反例形态</b>（负对照）与 <b>镜像空头版</b>。可用 <code>baseline.py</code> 对任意候选低点/高点一键判定。</li>
<li><b>不是</b>：不是「6 个条件全中才反转」的清单。样本证明：<b>单条判据都不足以定性</b>，最强的一条（V1 低点未被有效跌破）也仅 40% 成功率；组合后的 HIT 档为 <b>57.7%</b>（基准 18.5%），仍有 42% 失败。</li>
<li><b>案例式推断被数据推翻的两条</b>（重要）：①「越跌越买（低点前 30 分钟净买）」样本内为<b>负提升</b>（13.0% vs 基准 18.5%）⇒ 已从判据降为 context；②「低点区成交量大」同样为负提升（≥15k 手 → 9.8%）⇒ <b>放量不是承接证据，符号（方向）才是</b>。</li>
</ul>
</div>

<h2>1. 触发条件（因果、无前视）</h2>
<div class="card">
<p style="margin:0 0 6px"><span class="tag">候选低点</span> 1 分钟低点创 30 分钟新低 且 自 30 分钟高点回撤 ≥ 8 点；窗口 06:45–10:30；同一波段去重（间隔 ≥25 分钟，或出现更深的低点且间隔 ≥5 分钟）。<br>
<span class="tag">候选高点（镜像）</span> 同一逻辑取反。</p>
<p style="margin:6px 0 0;font-size:0.82rem;color:#475569">实测：样本内平均每个交易日产生 <b>6.8 个</b>候选低点（184/27）——触发本身不构成信号，只负责把「可能的极值点」摆到台面上。</p>
</div>

<h2>2. 三层判据与实测提升</h2>
<div class="card">
<table><tr><th style="width:17%">层（可判定时刻）</th><th style="width:9%">编号</th><th style="width:40%">测什么</th><th style="width:34%">样本内实测（n / 成功率 / 提升）</th></tr>
%(layer)s
</table>
<p style="font-size:0.8rem;color:#475569;margin:8px 0 0">
<b>判定规则</b>：<span class="tag">HIT</span> P≥2 且 V1 且 V2 ｜ <span class="tag">WATCH</span> V1 且（V2 或 P≥2）｜ <span class="tag">AVOID-反例</span> 低点区净卖 且 低点后净卖 且 15–45 分钟净卖（三条全中）｜ 其余 NEUTRAL。
反例形态优先于 WATCH（样本内反例 0–7.7% 成功率）。
</p>
</div>

<h2>3. 档位表现（同一样本，可复算）</h2>
<div class="card">
<table><tr><th style="width:16%">档位</th><th style="width:10%">n</th><th style="width:16%">成功率</th><th style="width:20%">相对基准</th><th style="width:16%">召回率</th></tr>
%(tier)s
</table>
<p style="font-size:0.8rem;color:#475569;margin:8px 0 0">成功定义：自低点起 60 分钟内 <b>最大上行 ≥15 点 且 最大逆向 ≤5 点</b>（高点镜像对称）。召回率 = 该档位覆盖了全部「真反转」样本的比例。<br>
读法：<b>HIT 档用 44% 的召回换到 3.1 倍于基准的精确率</b>；AVOID-反例与 NEUTRAL 两档合计覆盖 69% 的候选点，成功率仅 4–8%，即「大部分候选低点不值得参与」。</p>
</div>

<h2>4. 两案例对照（baseline 的实际输出）</h2>
<div class="card">
<table>
<tr><th style="width:22%">案例</th><th style="width:12%">判定</th><th>证据（P / V / C / 反例）</th><th style="width:22%">后验结果（仅回看）</th></tr>
<tr><td><b>2026-09-14 07:54</b> @7664.00</td><td style="color:#047857;font-weight:700">HIT</td>
<td>P2✓ atNet +1,420 ｜ P3✓ 机构单 <b>257 手</b> ｜ P4✓ pos 0.08 ｜ P1✗ zoneNet +13（临界）<br>
V1✓ maxrev 1.8 ｜ V2✓ midNet +2,992 ｜ V3✓ ≥50 手净 +494<br>
C1✓ 12 分钟收复 VWAP ｜ C2✓ DOM 贴价卖墙 <b>0 分钟</b> ｜ C3✓ 买墙 3 分钟 ｜ C4✓ 全盘比 max 1.47<br>
反例：三条全 ✗</td>
<td>mfe60 <b>+42.5</b> / mae60 +1.8 ｜ mfe120 +55.8</td></tr>
<tr><td><b>2026-09-15 07:50</b> @7648.50</td><td style="color:#b91c1c;font-weight:700">AVOID-反例</td>
<td>P1✗ zoneNet <b>−1,439</b> ｜ P2✗ atNet <b>−593</b> ｜ P3✓ 机构单 300 手（单笔，无后续） ｜ P4✓ pos 0.09<br>
V1✓ maxrev 5.0（临界） ｜ V2✗ midNet <b>−509</b> ｜ V3✗ ≥50 手净 −220<br>
C1✗ 未收复 VWAP ｜ C2✗ DOM 卖墙 <b>6 分钟 @7656.25</b> ｜ C3✗ 买墙 0 分钟 ｜ C4✗ 全盘比 max 0.98<br>
<b>反例：三条全 ✓</b></td>
<td>mfe60 +11.2 / mae60 +5.0 ｜ mfe120 +12.5</td></tr>
</table>
<p style="font-size:0.8rem;color:#475569;margin:8px 0 0">两案例的差别被 baseline 完整还原：<b>B 唯一「达标」的 P3（300 手主动买）是孤立脉冲</b>——baseline 要求 P≥2 且 V1&V2，该点 V2/V3 为负、C 层全灭、反例三条全中，因此不升级为 HIT。这正是 2026-09-15「反弹但不反转」的可机检表达。</p>
</div>

<h2>5. 通过 baseline 的历史 HIT 案例（前 14 例，用于人工复核）</h2>
<div class="card" style="overflow-x:auto">
<table style="font-size:0.76rem">
<tr><th>案例</th><th>判定</th><th>极值</th><th>pos</th><th>zoneNet</th><th>atNet</th><th>机构单</th><th>midNet</th><th>maxrev45</th><th>结果(mfe60/mae60)</th></tr>
%(hit)s
</table>
<p style="font-size:0.78rem;color:#64748b;margin:6px 0 0">注意：HIT 档是「值得参与」而非「必然反转」——同日 <b>2026-09-15 10:15</b> 的低点也判为 HIT，但 60 分钟只走 +10 点（未达 15 点门槛）；尽管如此，其风险特征（mae60 4.0）仍优于同日 07:50 的低点（mae60 5.0 且全程被 7656.25 卖墙压制）。</p>
</div>

<h2>6. AVOID-反例 档（前 8 例）</h2>
<div class="card" style="overflow-x:auto">
<table style="font-size:0.76rem">
<tr><th>案例</th><th>判定</th><th>极值</th><th>pos</th><th>zoneNet</th><th>atNet</th><th>机构单</th><th>midNet</th><th>maxrev45</th><th>结果(mfe60/mae60)</th></tr>
%(avoid)s
</table>
<p style="font-size:0.78rem;color:#64748b;margin:6px 0 0">该档位样本内成功率 7.7%（52 例），是本 baseline 的「不做多」过滤器。</p>
</div>

<h2>7. 使用方式</h2>
<div class="card">
<table><tr><th style="width:52%">命令</th><th>用途</th></tr>%(use)s</table>
<p style="font-size:0.8rem;color:#475569;margin:8px 0 0">规格文件：<code>~/.agents/skills/order-flow-deep-analysis/scripts/baseline_spec_v1.json</code>（版本化，可 diff）；实现：同目录 <code>baseline.py</code>；DOM 分钟画像缓存：<code>.../cache/dom_minutes/</code>（可用 <code>--scan</code> 自动补建）。</p>
</div>

<h2>8. 局限与使用纪律</h2>
<div class="card">
<div class="warn">
<b>必读</b>
<ul>
<li>样本仅 27 个交易日、单市场状态：真反转样本 34 例（低点）/ 40 例（高点）。<b>HIT 档 n=26 的 57.7% 置信区间很宽（约 ±19pt）</b>，阈值属初值；建议每周 <code>--scan</code> 重跑并记录版本差异。</li>
<li>V1（maxrev45≤5）是最强判据但时间上最晚（t+45）：<b>P 层只用于「提前关注」，不可单独入场</b>；真正可执行的是 V 层之后（t+45），右侧确认在 C 层（t+60）。</li>
<li>DOM 层（C2 贴价卖墙 / C3 贴价买墙 / C4 全盘比）只在 6 个交易日有完整 06:30–11:00 覆盖（n=52 候选）：提升幅度（+13~18pt）方向明确但样本更小；DOM 不可用时 C2–C4 记为 n/a，判定降级为「不含盘口的 HIT」。</li>
<li>案例中的教训已固化：<b>孤立大单（≥100 手）不等于机构建仓</b>——B 的 300 手主动买出现后 15 分钟净 Delta 转负，baseline 用 V2/V3 拦住了它。</li>
<li>本 baseline 只做「低点是否被吸收」的结构判定，不含仓位/止损/目标（那是下单层的事）；不接入自动下单。</li>
</ul>
</div>
<div class="foot">生成 %(gen)s · 规格 %(ver)s · 报告目录 /Users/zhijiebian/.gemini/cli-workspace/order-flow-deep-analysis/</div>
</div>
</div></body></html>"""

import re as _re
H = _re.sub(r'%(?!\()', '%%', TPL) % {
    'layer': layer_html, 'tier': tier_html, 'hit': case_rows(hit_cases, 'low'),
    'avoid': case_rows(avoid_cases, 'low'), 'use': use_rows,
    'gen': gen.strftime('%Y-%m-%d %H:%M'), 'ver': spec['version']}

OUT.mkdir(parents=True, exist_ok=True)
(OUT / fname).write_text(H)
print("WROTE", OUT / fname)
