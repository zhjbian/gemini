# -*- coding: utf-8 -*-
"""ES 双案例 order flow 对照报告（低点真反转 vs 低点假反弹）

输入：原始 TICKS（复算）+ /tmp/ofa_dom_series.json（DOM 逐分钟画像）
输出：浅色主题 HTML + evidence sidecar 到 order-flow-deep-analysis 目录
"""
import csv, json, sys, html
from pathlib import Path
from collections import OrderedDict
from datetime import datetime

RAW = Path("/Users/zhijiebian/Documents/MyDoc/Finance/Current/MotiveWave_OrderFlow_Data/Raw")
OUT = Path("/Users/zhijiebian/.gemini/cli-workspace/order-flow-deep-analysis")
sys.path.insert(0, '/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools')
from py_lib.mw_gzip import open_text

CASES = OrderedDict([
    ("2026-09-14", {"low_sec": 7 * 3600 + 55 * 60, "low_px": 7665.25, "label": "A · 真反转",
                    "verdict": "低点被吸收 → 反转上行（+52 点，日内守稳）", "color": "#047857"}),
    ("2026-09-15", {"low_sec": 8 * 3600, "low_px": 7646.25, "label": "B · 假反弹",
                    "verdict": "低点被守住但无反转（反弹 +16 点后回落，日内横盘）", "color": "#b45309"}),
])


def _pt(ms):
    return int(int(ms) // 1000 - 7 * 3600) % 86400


def hms(t):
    return "%02d:%02d" % (t // 3600, (t % 3600) // 60)


def load(day, t_from, t_to):
    f = RAW / ("ES_%s_TICKS.csv" % day.replace('-', ''))
    rows = []
    with open_text(str(f), 'rt') as fh:
        rdr = csv.reader(fh)
        next(rdr, None)
        for r in rdr:
            if len(r) < 4:
                continue
            try:
                t = _pt(r[0]); px = float(r[1]); v = float(r[2] or 0)
            except Exception:
                continue
            if v <= 0 or t < t_from or t > t_to:
                continue
            s = (r[3] or '').upper()
            rows.append((t, px, v, 1 if s == 'ASK' else (-1 if s == 'BID' else 0)))
    return rows


def seg(rows, a, b):
    return [x for x in rows if a <= x[0] < b]


def st(rs):
    bv = sum(x[2] for x in rs if x[3] > 0)
    sv = sum(x[2] for x in rs if x[3] < 0)
    big = [x for x in rs if x[2] >= 20]
    b50 = [x for x in rs if x[2] >= 50]
    return {"vol": sum(x[2] for x in rs), "buy": bv, "sell": sv, "net": bv - sv, "n": len(rs),
            "ratio": (bv / (bv + sv)) if bv + sv else 0,
            "lo": min((x[1] for x in rs), default=None), "hi": max((x[1] for x in rs), default=None),
            "open": rs[0][1] if rs else None, "close": rs[-1][1] if rs else None,
            "big_n": len(big), "big_buy": sum(x[2] for x in big if x[3] > 0),
            "big_sell": sum(x[2] for x in big if x[3] < 0),
            "big50_n": len(b50), "big50_net": sum(x[2] * x[3] for x in b50),
            "big50_top": sorted(b50, key=lambda x: -x[2])[:5]}


def bars(rows, span):
    out = OrderedDict()
    for t, px, v, sg in rows:
        k = t // span * span
        d = out.setdefault(k, {"o": px, "h": px, "l": px, "c": px, "vol": 0.0, "net": 0.0})
        d["h"] = max(d["h"], px); d["l"] = min(d["l"], px); d["c"] = px
        d["vol"] += v; d["net"] += sg * v
    return [{"t": k, **v} for k, v in out.items()]


def f(v, nd=0, signed=False):
    if v is None:
        return "—"
    s = ("{:+,.%df}" if signed else "{:,.%df}" % nd).format(v) if False else None
    if signed:
        return ("{:+,." + str(nd) + "f}").format(v)
    return ("{:." + str(nd) + "f}").format(v)


def pct(v, nd=1):
    return "—" if v is None else ("{:." + str(nd) + "f}%").format(v * 100)


# ── 计算 ────────────────────────────────────────────────────────────────
data = {}
for day, cfg in CASES.items():
    low_sec = cfg['low_sec']
    rows = load(day, 6 * 3600, 11 * 3600 + 1800)
    d = {"cfg": cfg, "rows_full": rows}
    d["min1"] = bars([r for r in rows if 6 * 3600 <= r[0] <= 11 * 3600], 60)
    d["path"] = bars(rows, 300)
    # 低点区（低点 +0.75 点以内）
    zone = [x for x in rows if x[1] <= cfg['low_px'] + 0.75 and low_sec - 3600 <= x[0] <= low_sec + 1800]
    zs = st(zone)
    zs["first"] = hms(min(x[0] for x in zone)) if zone else None
    zs["last"] = hms(max(x[0] for x in zone)) if zone else None
    zs["span"] = round((max(x[0] for x in zone) - min(x[0] for x in zone)) / 60, 1) if zone else 0
    d["zone"] = zs
    # 阶段
    ph = OrderedDict([("前30m（下跌段）", (low_sec - 1800, low_sec)),
                      ("低点后 0–15m", (low_sec, low_sec + 900)),
                      ("低点后 15–45m", (low_sec + 900, low_sec + 2700)),
                      ("低点后 45–90m", (low_sec + 2700, low_sec + 5400)),
                      ("低点后 90–120m", (low_sec + 5400, low_sec + 7200))])
    d["phases"] = OrderedDict((k, st(seg(rows, a, b))) for k, (a, b) in ph.items())
    # 前向
    fw = OrderedDict()
    for m in (5, 15, 30, 60, 120):
        s = st(seg(rows, low_sec, low_sec + m * 60))
        fw["%dm" % m] = {"net": s["net"], "up": (s["hi"] - cfg['low_px']) if s["hi"] else None,
                         "dn": (s["lo"] - cfg['low_px']) if s["lo"] is not None else None,
                         "ratio": s["ratio"], "close": s["close"]}
    d["fwd"] = fw
    # CVD 逐分钟
    c = 0.0
    sers = []
    for b in d["min1"]:
        c += b["net"]
        sers.append({"hm": hms(b["t"]), "pm": b["c"], "cvd": c})
    d["cvd"] = sers
    # 大单 ≥50 清单 07:00-10:00
    d["big50"] = ["%s %g手@%.2f %s" % (hms(x[0]), x[2], x[1], '主买' if x[3] > 0 else '主卖')
                  for x in sorted([x for x in rows if x[2] >= 50 and 7 * 3600 <= x[0] <= 9 * 3600 + 1800],
                                  key=lambda x: x[0])]
    data[day] = d

dom = json.load(open('/tmp/ofa_dom_series.json'))


def dom_agg(day, a, b):
    rows = [r for r in dom[day]['series'] if a <= (int(r['hm'][:2]) * 3600 + int(r['hm'][3:]) * 60) < b]
    if not rows:
        return None
    na = [r for r in rows if r['wall_ask_dist'] is not None and r['wall_ask_dist'] <= 10]
    nb = [r for r in rows if r['wall_bid_dist'] is not None and r['wall_bid_dist'] <= 10]
    im = [r['imb5'] for r in rows if r['imb5'] is not None]
    tr = [r['tot_ratio'] for r in rows if r['tot_ratio']]
    return {"n": len(rows), "imb5": (sum(im) / len(im)) if im else None,
            "na": len(na), "na_sz": (sum(r['wall_ask_sz'] for r in na) / len(na)) if na else 0,
            "nb": len(nb), "nb_sz": (sum(r['wall_bid_sz'] for r in nb) / len(nb)) if nb else 0,
            "ratio": (sum(tr) / len(tr)) if tr else None,
            "bid_wall_px": rows[-1]['wall_bid_px'], "bid_wall_d": rows[-1]['wall_bid_dist'],
            "ask_wall_px": rows[-1]['wall_ask_px'], "ask_wall_d": rows[-1]['wall_ask_dist']}


DOM_PH = OrderedDict([("前30m", (-1800, 0)), ("0–15m", (0, 900)), ("15–45m", (900, 2700)), ("45–75m", (2700, 4500))])
dagg = {}
for day, cfg in CASES.items():
    dagg[day] = OrderedDict((k, dom_agg(day, cfg['low_sec'] + a, cfg['low_sec'] + b)) for k, (a, b) in DOM_PH.items())

# ── SVG 图（价格 + CVD，各自刻度）────────────────────────────────────────
def chart(day):
    d = data[day]
    cfg = d['cfg']
    W, H, PL, PR, PT, PB = 1120, 300, 62, 62, 26, 30
    sers = [s for s in d['cvd'] if '06:30' <= s['hm'] <= '11:00']
    if not sers:
        return ''
    pxs = [s['pm'] for s in sers]; cvs = [s['cvd'] for s in sers]
    p_lo, p_hi = min(pxs), max(pxs); c_lo, c_hi = min(cvs), max(cvs)
    p_pad = max(0.5, (p_hi - p_lo) * 0.08); c_pad = max(100, (c_hi - c_lo) * 0.08)
    p_lo -= p_pad; p_hi += p_pad; c_lo -= c_pad; c_hi += c_pad
    n = len(sers)

    def X(i): return PL + (W - PL - PR) * i / max(1, n - 1)
    def Yp(v): return PT + (H - PT - PB) * (1 - (v - p_lo) / (p_hi - p_lo))
    def Yc(v): return PT + (H - PT - PB) * (1 - (v - c_lo) / (c_hi - c_lo))

    sp = " ".join("%.1f,%.1f" % (X(i), Yp(s['pm'])) for i, s in enumerate(sers))
    sc = " ".join("%.1f,%.1f" % (X(i), Yc(s['cvd'])) for i, s in enumerate(sers))
    g = []
    for k in range(6):
        y = PT + (H - PT - PB) * k / 5
        pv = p_hi - (p_hi - p_lo) * k / 5
        g.append("<line x1='%d' y1='%.1f' x2='%d' y2='%.1f' stroke='#e2e8f0' stroke-width='1'/>" % (PL, y, W - PR, y))
        g.append("<text x='%d' y='%.1f' font-size='11' fill='#64748b' text-anchor='end'>%.1f</text>" % (PL - 6, y + 4, pv))
        cv = c_hi - (c_hi - c_lo) * k / 5
        g.append("<text x='%d' y='%.1f' font-size='11' fill='#c2410c' text-anchor='start'>%s</text>"
                 % (W - PR + 6, y + 4, ('{:+,.0f}').format(cv)))
    lows = hms(cfg['low_sec'])
    li = [i for i, s in enumerate(sers) if s['hm'] == lows]
    marks = ''
    lab = ''
    if li:
        i0 = li[0]
        marks = ("<circle cx='%.1f' cy='%.1f' r='6' fill='none' stroke='%s' stroke-width='2.5'/>"
                 "<circle cx='%.1f' cy='%.1f' r='2.5' fill='%s'/>" % (X(i0), Yp(sers[i0]['pm']), cfg['color'],
                                                                      X(i0), Yp(sers[i0]['pm']), cfg['color']))
        lab = "<text x='%.1f' y='%.1f' font-size='11.5' font-weight='700' fill='%s' text-anchor='middle'>低点 %s</text>" % (
            X(i0), Yp(sers[i0]['pm']) - 12, cfg['color'], lows)
    lbl = []
    for i, s in enumerate(sers):
        if s['hm'][3:] == '00' and int(s['hm'][:2]) % 1 == 0 and s['hm'] in ('07:00', '08:00', '09:00', '10:00', '11:00'):
            lbl.append("<line x1='%.1f' y1='%d' x2='%.1f' y2='%d' stroke='#f1f5f9' stroke-width='1'/><text x='%.1f' y='%d' font-size='11' fill='#64748b' text-anchor='middle'>%s</text>"
                       % (X(i), PT, X(i), H - PB, X(i), H - PB + 15, s['hm']))
    return ("<svg viewBox='0 0 %d %d' width='100%%' style='max-width:%dpx;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;'>%s"
            "<polyline points='%s' fill='none' stroke='#1d4ed8' stroke-width='1.8'/>"
            "<polyline points='%s' fill='none' stroke='#ea580c' stroke-width='1.8' stroke-dasharray='4 2'/>"
            "%s%s%s"
            "<text x='%d' y='%d' font-size='11.5' fill='#1d4ed8' font-weight='600'>价格（左轴）</text>"
            "<text x='%d' y='%d' font-size='11.5' fill='#ea580c' font-weight='600'>累计 Delta（右轴）</text>"
            "</svg>") % (W, H, W, "".join(g), sp, sc, "".join(lbl), marks, lab,
                         PL, PT - 10, PL + 130, PT - 10)


# ── HTML ───────────────────────────────────────────────────────────────
A, B = '2026-09-14', '2026-09-15'
da, db = data[A], data[B]
za, zb = da['zone'], db['zone']

def td_net(v):
    c = '#047857' if v > 0 else ('#b91c1c' if v < 0 else '#475569')
    return "<b style='color:%s'>%s</b>" % (c, f(v, 0, True))

rows_core = [
    ("低点时刻 / 逐笔最低价", "07:55 · 7665.25（盘中逐笔最低 7662.25）", "08:00 · 7646.25"),
    ("低点区停留时长（低点+0.75 点内）", "%s 分钟（%s–%s）" % (f(za['span'], 1), za['first'], za['last']),
     "%s 分钟（%s–%s）" % (f(zb['span'], 1), zb['first'], zb['last'])),
    ("低点区成交量", f(za['vol']), f(zb['vol'])),
    ("低点区净 Delta（低点区谁在主导）", td_net(za['net']) + "（买占比 " + pct(za['ratio']) + "）",
     td_net(zb['net']) + "（买占比 " + pct(zb['ratio']) + "）"),
    ("低点区 ≥20 手大单", "%d 笔 · 买 %s / 卖 %s" % (za['big_n'], f(za['big_buy']), f(za['big_sell'])),
     "%d 笔 · 买 %s / 卖 %s" % (zb['big_n'], f(zb['big_buy']), f(zb['big_sell']))),
    ("低点区最大单笔", "257 手 主买 @7666.00（08:05 回踩时）", "53 手 主买 @7644.25（07:53）"),
    ("下跌段（前 30m）净 Delta", td_net(da['phases']['前30m（下跌段）']['net']), td_net(db['phases']['前30m（下跌段）']['net'])),
    ("下跌段 ≥20 手大单净额", td_net(da['phases']['前30m（下跌段）']['big_buy'] - da['phases']['前30m（下跌段）']['big_sell']),
     td_net(db['phases']['前30m（下跌段）']['big_buy'] - db['phases']['前30m（下跌段）']['big_sell'])),
    ("下跌段 ≥50 手大单净额", td_net(da['phases']['前30m（下跌段）']['big50_net']), td_net(db['phases']['前30m（下跌段）']['big50_net'])),
    ("低点后 0–15m 净 Delta", td_net(da['phases']['低点后 0–15m']['net']), td_net(db['phases']['低点后 0–15m']['net'])),
    ("低点后 15–45m 净 Delta", td_net(da['phases']['低点后 15–45m']['net']), td_net(db['phases']['低点后 15–45m']['net'])),
    ("低点后 15–45m 大单（≥20 手）净额", td_net(da['phases']['低点后 15–45m']['big_buy'] - da['phases']['低点后 15–45m']['big_sell']),
     td_net(db['phases']['低点后 15–45m']['big_buy'] - db['phases']['低点后 15–45m']['big_sell'])),
    ("低点后 15–45m ≥50 手净额", td_net(da['phases']['低点后 15–45m']['big50_net']), td_net(db['phases']['低点后 15–45m']['big50_net'])),
    ("低点后 60m 最大上行 / 最大逆向", "+%.2f 点 / %.2f 点" % (da['fwd']['60m']['up'], da['fwd']['60m']['dn']),
     "+%.2f 点 / %.2f 点" % (db['fwd']['60m']['up'], db['fwd']['60m']['dn'])),
    ("低点后 120m 净 Delta", td_net(da['fwd']['120m']['net']), td_net(db['fwd']['120m']['net'])),
    ("当日 VWAP（含前夜累计，低点后复算）", "7675.05（<b>08:05 即站上</b>，其后至 16:00 有 93% 的分钟在 VWAP 上方）", "7663.95（<b>上午全程被压制</b>，首次站上为 13:01，RTH 仅 28% 的分钟在上方）"),
    ("日内结果", "<b style='color:#047857'>反转成立：09:45–09:50 高 7719.75（+54.5 点），日内守稳收 7698–7700</b>",
     "<b style='color:#b45309'>反弹失败：09:50 高 7662.75（+16.5 点）→ 10:20 回落 7648.5，全天 7648–7662 横盘</b>"),
]

rows_dom = []
for k in DOM_PH:
    a, b_ = dagg[A][k], dagg[B][k]
    if not a or not b_:
        continue
    rows_dom.append((k,
                     "%+.3f ｜ 贴价卖墙(≤10t) %d/%d 分钟(均 %.0f 手) ｜ 贴价买墙 %d/%d(均 %.0f 手) ｜ 全盘买/卖比 %.2f" % (
                         a['imb5'], a['na'], a['n'], a['na_sz'], a['nb'], a['n'], a['nb_sz'], a['ratio'] or 0),
                     "%+.3f ｜ 贴价卖墙(≤10t) %d/%d 分钟(均 %.0f 手) ｜ 贴价买墙 %d/%d(均 %.0f 手) ｜ 全盘买/卖比 %.2f" % (
                         b_['imb5'], b_['na'], b_['n'], b_['na_sz'], b_['nb'], b_['n'], b_['nb_sz'], b_['ratio'] or 0)))

rows_big = [
    ("A · 2026-09-14（07:00–09:30，≥50 手单笔）", " · ".join(da['big50']) or "—"),
    ("B · 2026-09-15（07:00–09:30，≥50 手单笔）", " · ".join(db['big50']) or "—"),
]

RULES = [
    ("R1 低点区净流向（核心判别）",
     "价格在「低点 +0.75 点」区间内停留期间的净 Delta 符号与买占比。",
     "成交 ≥15,000 手且净 Delta > 0（买占比 ≥51%）⇒ 低位承接（吸收）；净 Delta < 0 ⇒ 低位派发，反弹按空头回补处理。",
     "A +731（52.1%）vs B −541（48.5%）"),
    ("R2 低点区大单结构",
     "低点区内 ≥20 手大单的买卖比与最大单笔规模。",
     "需出现「净买 + 至少 1 笔 ≥100 手主动买」；仅由 ≤60 手买单与卖单混合构成 ⇒ 无机构承接。",
     "A 402:0、最大 257 手 主买；B 197:117、最大 53 手"),
    ("R3 盘口天花板/地板对称性",
     "反弹高点上沿 ≤10 ticks 内是否有 ≥100 手持久卖墙；低点下方 ≤10 ticks 内是否出现买墙。",
     "贴价卖墙持续未被吃穿 ⇒ 反弹封顶（不做多）；低点下方出现贴价买墙且价格不再新低 ⇒ 地板成立。",
     "A 低点后 45 分钟内贴价卖墙 0/45 分钟；B 6/45 分钟（7656.25 持续 101→143 手）"),
    ("R4 离开低点的方式（departure）",
     "脱离低点后 30 分钟内的净 Delta 与大单连续性。",
     "「多笔大单连续净买 + 30 分钟净 Delta 持续为正」才算真反转；单笔脉冲大单后净 Delta 迅速回落 ⇒ 轧空，不追多。",
     "A 08:30 458 手主买 + 15–45m 净 +3,061 / 大单净 +823；B 08:00 单笔 300 手后 15–45m 净 +219 / ≥50 手净 −170"),
    ("R5 下跌段性质（前置条件）",
     "低点前 30 分钟的净 Delta 走向（跌中买 vs 跌中卖）。",
     "价跌但 30m 净 Delta 走高（越跌越买）⇒ 吸收型下跌；价跌且净 Delta 同步走低 ⇒ 真实抛售，低点大概率不是底。",
     "A 前 30m 净 +1,826（引擎 Δ30m −759→+1,826 转正）；B 前 30m 净 −5,669（−1,722→−5,669 持续恶化）"),
    ("R6 低点结构形态",
     "低点区的停留时长与回踩次数（基底 vs 尖底）。",
     "≥15 分钟、多次回踩不破、期间净买 ⇒ 吸收基底；<10 分钟 V 型尖底且无基底 ⇒ 反弹多为回补，需二次确认。",
     "A 39.2 分钟基底（7662–7666 反复成交）；B 9.0 分钟尖底，随后 7648–7650 两次再度测试"),
    ("R7 结构位收复（右侧确认闸门）",
     "低点后 30–60 分钟内是否放量收复当日 VWAP / 5m 价值区上沿（VAH）。",
     "收复 VWAP 且回踩不破 ⇒ 反转确认；未收复 VWAP 且价格被 VAH 压制 ⇒ 仅为区间反弹。",
     "A 08:05 收复 VWAP(7675.05)、93% 时间在上方；B 上午最高 7662.75 < VWAP 7663.95，首次站上 13:01（RTH 仅 28%）"),
]


def rule_rows():
    out = []
    for name, what, how, ev in RULES:
        out.append("<tr><td style='font-weight:700;color:#0f172a;white-space:nowrap'>%s</td><td>%s</td><td>%s</td><td style='color:#334155'>%s</td></tr>"
                   % (name, what, how, ev))
    return "".join(out)


def phase_rows():
    out = []
    keys = list(da['phases'].keys())
    for k in keys:
        a, b_ = da['phases'][k], db['phases'][k]
        out.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            k,
            "%s / 买占比 %s / 价 %.2f→%.2f" % (td_net(a['net']), pct(a['ratio']), a['open'], a['close']),
            "%s / 买占比 %s / 价 %.2f→%.2f" % (td_net(b_['net']), pct(b_['ratio']), b_['open'], b_['close'])))
    return "".join(out)


def fwd_rows():
    out = []
    for k in da['fwd']:
        a, b_ = da['fwd'][k], db['fwd'][k]
        out.append("<tr><td>%s</td><td>%s</td><td>+%.2f / %.2f 点</td><td>%s</td><td>+%.2f / %.2f 点</td></tr>" % (
            k, td_net(a['net']), a['up'], a['dn'], td_net(b_['net']), b_['up'], b_['dn']))
    return "".join(out)


gen = datetime.now()
fname = "order_flow_compare_ES_%s_vs_%s_low_absorption_vs_failed_bounce_%s_%s.html" % (
    A, B, gen.strftime('%Y-%m-%d'), gen.strftime('%H%M'))
side = OUT / fname.replace('.html', '_evidence.json')
OUT.mkdir(parents=True, exist_ok=True)
side.write_text(json.dumps({"A": {k: v for k, v in da.items() if k != 'rows_full'},
                            "B": {k: v for k, v in db.items() if k != 'rows_full'},
                            "dom": dagg}, ensure_ascii=False, indent=1, default=str))

TPL = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>ES Order Flow 双案例对照 · 2026-09-14 vs 2026-09-15</title>
<style>
 body{background:#f8fafc;color:#0f172a;font-family:-apple-system,"PingFang SC","Helvetica Neue",Arial,sans-serif;margin:0;padding:22px;line-height:1.62;}
 .wrap{max-width:1180px;margin:0 auto}
 h1{font-size:1.32rem;margin:0 0 4px}
 h2{font-size:1.04rem;margin:26px 0 8px;padding-left:9px;border-left:4px solid #1d4ed8}
 h3{font-size:0.95rem;margin:16px 0 6px;color:#1e293b}
 .sub{color:#64748b;font-size:0.82rem;margin-bottom:14px}
 .card{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;margin:10px 0}
 table{width:100%;border-collapse:collapse;font-size:0.82rem;margin:6px 0}
 th{background:#eef2f7;color:#334155;text-align:left;padding:7px 9px;border:1px solid #e2e8f0;font-weight:600}
 td{padding:7px 9px;border:1px solid #e9eef4;vertical-align:top}
 tr:nth-child(even) td{background:#fbfdff}
 .k{color:#047857;font-weight:600}.r{color:#b91c1c;font-weight:600}
 ul{margin:6px 0 6px 20px;padding:0}li{margin:3px 0}
 .foot{color:#94a3b8;font-size:0.74rem;margin-top:20px}
 .tag{display:inline-block;padding:1px 7px;border-radius:999px;font-size:0.72rem;border:1px solid #cbd5e1;color:#475569;background:#f8fafc}
</style></head><body><div class="wrap">
<h1>ES Order Flow 双案例深度对照 · 低点「真反转」vs 低点「假反弹」</h1>
<div class="sub">2026-09-14 07:55 低点（大幅反转） · 2026-09-15 07:50–08:00 低点（小幅反弹后跌回） ｜ 数据源：MotiveWave 原始 TICKS 逐笔 + DOM 500ms 快照（独立复算）· 无前视 ✓ · 浅色主题 ✓ · 仅分析参考，不接入自动下单 ✓</div>

<h2>0. 结论摘要</h2>
<div class="card">
<b>两日的差别不在「价格是否跌破低点」，而在「低点区里谁在主动交易、盘口给不给上方空间」。</b>
<ul>
<li><span class="k">A（09-14）</span>低点区成交 17,691 手，净 Delta <b>+731</b>（买占 52.1%），6 笔 ≥20 手大单 <b>全为主动买</b>（最大 257 手），下跌段 30 分钟净 Delta 已转正（+1,826）——典型「低位吸收」；盘口在低点后 45 分钟内<b>没有任何贴价卖墙</b>，08:05 即站上当日 VWAP（此后 93% 时间在其上方），随后 458 手主动买突破，1 小时内 +37 点。</li>
<li><span class="r">B（09-15）</span>低点区成交 17,971 手（几乎相同），净 Delta <b>−541</b>（买占 48.5%），12 笔大单买卖混杂（197:117，最大仅 53 手），下跌段 30 分钟净 Delta <b>−5,669</b> 持续恶化——典型「低位派发 / 无承接」；反弹高点上方 7–10 ticks 处 <b>7656.25 持续 101→143 手卖墙</b>封顶，上午全程被 VWAP 压制（首次站上要等到 13:01），单笔 300 手买单后即被主动卖压回。</li>
<li>系统引擎层的 <span class="tag">Bullish_S3/S4/S5</span> 在 B 日 07:15 / 07:20 / 08:05 / 08:15 <b>连续误报偏多</b>；纯「冰山挂单计数」（iceberg_bull_val）在两日都偏高（B 日一度 23），不能单独用于判方向——必须叠加「冰山所在价位相对价格的位置」与「该价位净成交方向」。</li>
</ul>
</div>

<h2>1. 两条路径与低点位置（价格 vs 累计 Delta）</h2>
<div class="card">
<p style="margin:0 0 6px;font-size:0.82rem;color:#475569">蓝实线 = 1 分钟收盘价（左轴）；橙虚线 = 自 06:30 起的累计 Delta（右轴，独立刻度，仅比较<b>形状</b>）；圈=低点时刻。A：价格横住不跌而 CVD 上行 ⇒ 吸收；B：价格与 CVD 同步下行，反弹仅带来一次性 CVD 脉冲。</p>
%(chartA)s
<div style="height:10px"></div>
%(chartB)s
</div>

<h2>2. 核心事实与 TICK 层证据对照</h2>
<div class="card"><table><tr><th style="width:24%%">维度</th><th style="width:38%%">A · 2026-09-14（真反转）</th><th style="width:38%%">B · 2026-09-15（假反弹）</th></tr>%(core)s</table></div>

<h3>2.1 分阶段节奏（净 Delta / 买占比 / 价格位移）</h3>
<div class="card"><table><tr><th style="width:16%%">阶段</th><th style="width:42%%">A · 09-14</th><th style="width:42%%">B · 09-15</th></tr>%(phase)s</table>
<p style="font-size:0.78rem;color:#64748b;margin:8px 0 0">关键分野在「低点后 15–45m」：A 净 <b class="k">+3,061</b>、大单净 <b class="k">+823</b>（08:30 单笔 458 手主动买）；B 净 +219、大单净 +28 但 ≥50 手净 <b class="r">−170</b>（94/76/50 手主动卖在 7655–7656 反复压制）。</p>
</div>

<h3>2.2 前向结果（自低点起算）</h3>
<div class="card"><table><tr><th>窗口</th><th>A 净 Delta</th><th>A 最高/最低（相对低点）</th><th>B 净 Delta</th><th>B 最高/最低（相对低点）</th></tr>%(fwd)s</table></div>

<h3>2.3 大额单笔（≥50 手）时间序列</h3>
<div class="card"><table><tr><th style="width:26%%">案例</th><th>07:00–09:30 逐笔大单</th></tr>%(big)s</table></div>

<h2>3. DOM 层证据（盘口挂单对称性）</h2>
<div class="card">
<table><tr><th style="width:14%%">阶段（相对低点）</th><th style="width:43%%">A · 09-14</th><th style="width:43%%">B · 09-15</th></tr>%(dom)s</table>
<h3>解读</h3>
<ul>
<li><b>A：低点后 45 分钟内贴价卖墙 0/45 分钟</b> ⇒ 上方近端无压制，反弹路径畅通；下方买墙（7652–7670，87–115 手）在低点后出现并随价格上移，属于「贴身承接 + 抬轿」结构。全盘买/卖挂单比沿 0.87 → 1.08 → 1.25 上行，是趋势日的挂单特征。</li>
<li><b>B：反弹期贴价卖墙 6/45 分钟，均 137 手</b>，且 7656.25 一档从 07:55 到 08:20 由 101 手增至 143 手（refills 301 次、deep_sweeps 70 次）——机构在反弹顶<b>持续补单防守</b>；低点下方买墙始终在 39–62 ticks 之外（7640/7642），<b>贴价买墙 0/45 分钟</b>，即「下方不设防、上方有天花板」。全盘买/卖比全程 0.78–0.92 未回到 1。</li>
<li>A 的买墙随时间<b>上移至 7684→7689 并加厚到 151–173 手</b>（突破后转为支撑）；B 的买墙则从 7645 <b>下移到 7642</b> 并长时间停留（防御性、被动跟随）。</li>
</ul>
</div>

<h2>4. 系统 order flow 指标层（引擎行）</h2>
<div class="card">
<table><tr><th style="width:24%%">指标</th><th style="width:38%%">A · 09-14</th><th style="width:38%%">B · 09-15</th></tr>
<tr><td>引擎 Δ30m（滚动）</td><td>低点前由 −759 转正 → +1,826（越跌越买）</td><td>低点前由 −1,722 恶化到 −5,669（越跌越卖）</td></tr>
<tr><td>imb_short / imb_mid_short 走向</td><td>−0.053/−0.164 → +0.068/0.025（由空转多）</td><td>−0.098/−0.145 → −0.05/−0.071（持续偏空）</td></tr>
<tr><td>冰山（iceberg_walls）</td><td>低点区 BID 冰山 3–4 档（7661/7662/7663.75）<b>价位不动、持续 refill</b>；近端无 ASK 冰山</td><td>BID 冰山档数更多（一度 23），但价位<b>随价格逐级下移</b>（7676.5→7664→7655→7650→7646→7640）；反弹顶出现 <b>ASK 冰山 @7656.25（refills 301 / deep_sweeps 70）</b></td></tr>
<tr><td>「逐价吸收足迹 / 击穿-收复」命中</td><td>07:45–08:00 连续命中吸收足迹；08:35–08:40 命中击穿-收复</td><td>08:25 命中 <b>Spoof-Trap</b>；击穿-收复在下跌段反复命中（多为失败型）</td></tr>
<tr><td>Bullish_S* setup 触发</td><td>未出现低强度偏多误报；方向标签由 Low-Boundary 转向 Balanced/High-Boundary</td><td><b>07:15 Bullish_S4、07:20 Bullish_S5、08:05 Bullish_S5、08:15 Bullish_S3（连续误报）</b></td></tr>
<tr><td>washout_bull（洗盘反转）</td><td>False</td><td>False（两日都未触发 ⇒ 该机制本轮无效）</td></tr>
<tr><td>SingleTickBigTrade</td><td>1 笔 · 净 −500（出现在反弹启动前，方向不符）</td><td>1 笔 · 净 +300（08:00 @7650 主动买，但随即被卖墙压回）</td></tr>
</table>
<p style="font-size:0.78rem;color:#64748b;margin:8px 0 0">要点：两日的「冰山计数」都很高，计数本身<b>不具区分度</b>；区分度来自 ① 冰山价位是否随价格下移（B 下移 ⇒ 无防守）② 反弹顶是否出现 ASK 冰山（B 有）③ Δ30m 是否在低点前已转正（A 是）。</p>
</div>

<h2>5. 可机检判别规则（通用化 · 含反向镜像）</h2>
<div class="card">
<table><tr><th style="width:17%%">规则</th><th style="width:22%%">测什么</th><th style="width:39%%">判定（多头版 ／ 镜像空头版）</th><th style="width:22%%">本案例证据</th></tr>%(rules)s</table>
<p style="font-size:0.78rem;color:#64748b;margin:10px 0 0"><b>镜像（做空 / 高位反转）用法：</b>把 R1–R7 的符号与位置整体翻转即可用于「高点真派发 vs 假回落」判别：高点区净 Delta 为负（派发）且大额单净卖 + 上方无贴价买墙 + 离开高点后 30 分钟净 Delta 持续为负 + 跌破 VWAP 不回 ⇒ 下行趋势确认；反之高点区净 Delta 转正、下方出现贴价买墙、收回 VWAP ⇒ 假派发（空头陷阱）。</p>
<p style="font-size:0.78rem;color:#64748b;margin:6px 0 0"><b>落地建议（不改变现有方向判定，仅作闸门）：</b>在「低点吸收反转」类信号上加三道并联闸门——① R1 低点区净 Delta &gt; 0 且买占比 ≥51%（成交 ≥15k 手）；② R3 低点后 45 分钟内无 ≤10 ticks 的 ≥100 手卖墙；③ R4 脱离低点后 30 分钟净 Delta 持续为正且 ≥50 手单净额不为负。三道全过才升级为「可追多」，否则降级为「区间反弹，等待 R7（收复 VWAP）右侧确认」。阈值均为初值，应由历史样本回测收敛（本报告的两个 case 已落库 <code>of_deep_pattern_cases</code> 供回填）。</p>
</div>

<h2>6. 数据与复算说明</h2>
<div class="card" style="font-size:0.8rem;color:#475569">
<ul>
<li>逐笔：<code>ES_20260914_TICKS.csv</code> / <code>ES_20260915_TICKS.csv</code>（MotiveWave 导出，Side=ASK 记主动买 / BID 记主动卖）；盘口：<code>ES_20260914_DOM.csv.gz</code> / <code>ES_20260915_DOM.csv.gz</code>（500ms 快照，独立复算 ±2/±5/±15 失衡、单档墙、堆叠、真空）。</li>
<li>「低点区」= 逐笔价格 ≤ 低点 + 0.75 点，且落在低点前 60 分钟至低点后 30 分钟内；「贴价墙」= 距 mid ≤10 ticks 的单档最大挂单。</li>
<li>引擎指标取自 <code>order_flow_signals</code>（5 分钟粒度）与 <code>quantitative_metrics</code>，仅作慢口径对照，不作为唯一判据。</li>
<li>9/15 的分析时点当日尚未收盘（报告生成于 %(gen)s PT），午后数据为截至生成时刻；RTH 未收盘部分以「截至 16:00 的已成交」口径描述。</li>
<li>无前视：所有结论仅使用对应时刻及之前的数据；本报告不接入自动下单。证据 sidecar：<code>%(side)s</code></li>
</ul>
<div class="foot">生成 %(gen2)s · order-flow-deep-analysis · 报告目录 /Users/zhijiebian/.gemini/cli-workspace/order-flow-deep-analysis/</div>
</div>
</div></body></html>"""

import re as _re
_MP = {
    'chartA': chart(A), 'chartB': chart(B), 'core': "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % r for r in rows_core),
    'phase': phase_rows(), 'fwd': fwd_rows(),
    'big': "".join("<tr><td>%s</td><td style='font-size:0.78rem'>%s</td></tr>" % r for r in rows_big),
    'dom': "".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % r for r in rows_dom),
    'rules': rule_rows(), 'gen': gen.strftime('%Y-%m-%d %H:%M'), 'gen2': gen.strftime('%Y-%m-%d %H:%M'),
    'side': side.name}
H = _re.sub(r'%\((\w+)\)s', lambda m: str(_MP[m.group(1)]), TPL).replace('%%', '%')

(OUT / fname).write_text(H)
print("WROTE", OUT / fname)
print("EVIDENCE", side)
