# -*- coding: utf-8 -*-
"""adam_tick_analysis —— TICK（逐笔成交）**深度分析**：与 DOM 深度分析并列呈现 ✓

一次扫描 tick 文件（截至 t0 ✓ 无前视 ✓），产出：
  ① 概览：成交量 / 主动买·卖 / 净 Delta / 买占比 / 笔数 / 平均单笔 / 最大单笔 ✓
  ② 分窗口（5/10/15/30/60 分钟 ✓）：净 Delta / 量 / 价格位移 / Delta 比 ✓
  ③ **价位分布（Volume Profile ✓）**：POC / VAH / VAL（70% 价值区 ✓）+ Top5 成交密集价 ✓
  ④ **大单**（≥ BIG_LOT 手 ✓）：笔数 / 买卖分布 / 最大 3 笔 ✓
  ⑤ **逐分钟节奏**：成交量 / 净 Delta / 买占比（供图表与吸收判断 ✓）
  ⑥ **数据质量**：有成交的 5 分钟格数（trade bins ✓ 引擎曾出现 =0 的退化 ✗）
仅分析参考 ✓ 不接入自动下单 ✓
"""
from __future__ import annotations
import csv, sys
from pathlib import Path

sys.path.append('/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools')
RAW_DIR = Path("/Users/zhijiebian/Documents/MyDoc/Finance/Current/MotiveWave_OrderFlow_Data/Raw")
TICK = 0.25
WINDOWS = [5, 10, 15, 30, 60]
BIG_LOT = 20                # 单笔 ≥20 手视为大单 ✓（ES 语境 ✓）


def _pt(ms):
    return int(int(ms) // 1000 - 7 * 3600) % 86400


def tick_analysis(day, t0_sec):
    f = RAW_DIR / ("ES_%s_TICKS.csv" % str(day).replace('-', ''))
    if not f.exists():
        return None
    rows = []            # (t, px, vol, side_sign)
    try:
        from py_lib.mw_gzip import open_text
        with open_text(str(f), 'rt') as fh:
            rdr = csv.reader(fh)
            next(rdr, None)
            for r in rdr:
                if len(r) < 4:
                    continue
                try:
                    t = _pt(r[0])
                except Exception:
                    continue
                if t > t0_sec:
                    break
                if t < t0_sec - 3600:
                    continue
                try:
                    px, vol = float(r[1]), (float(r[2]) if r[2] else 0.0)
                except Exception:
                    continue
                if vol <= 0:
                    continue
                s = (r[3] or '').upper()
                sg = 1 if (s == 'ASK' or 'BUY' in s) else (-1 if (s == 'BID' or 'SELL' in s) else 0)
                rows.append((t, px, vol, sg))
    except Exception:
        return None
    if not rows:
        return None
    out = {}
    tv = sum(x[2] for x in rows)
    bv = sum(x[2] for x in rows if x[3] > 0)
    sv = sum(x[2] for x in rows if x[3] < 0)
    out["overview"] = {"vol": tv, "buy": bv, "sell": sv, "net": bv - sv,
                       "ratio": (bv / (bv + sv)) if (bv + sv) else None,
                       "n": len(rows), "avg": (tv / len(rows)) if rows else None,
                       "max": max((x[2] for x in rows), default=None), "px": rows[-1][1]}
    # ② 分窗口
    win = {}
    for w in WINDOWS:
        seg = [x for x in rows if x[0] >= t0_sec - w * 60]
        if not seg:
            continue
        b = sum(x[2] for x in seg if x[3] > 0)
        s_ = sum(x[2] for x in seg if x[3] < 0)
        win[w] = {"net": b - s_, "vol": b + s_, "ratio": (b / (b + s_)) if (b + s_) else None,
                  "dpx": seg[-1][1] - seg[0][1], "n": len(seg)}
    out["windows"] = win
    # ③ 价位分布（Volume Profile ✓ 70% 价值区 ✓）
    hist = {}
    for _, px, vol, _ in rows:
        k = round(px / TICK)
        hist[k] = hist.get(k, 0.0) + vol
    total = sum(hist.values())
    poc = max(hist, key=hist.get)
    area = {poc: hist[poc]}
    lo = hi = poc
    while sum(area.values()) < total * 0.70 and (lo > min(hist) or hi < max(hist)):
        up = hist.get(hi + 1, 0.0)
        dn = hist.get(lo - 1, 0.0)
        if up >= dn and hi < max(hist):
            hi += 1; area[hi] = up
        elif lo > min(hist):
            lo -= 1; area[lo] = dn
        elif hi < max(hist):
            hi += 1; area[hi] = up
        else:
            break
    top5 = sorted(hist.items(), key=lambda kv: -kv[1])[:5]
    out["profile"] = {"poc": poc * TICK, "vah": hi * TICK, "val": lo * TICK,
                      "top5": [(k * TICK, v) for k, v in top5], "total": total}
    # ④ 大单
    big = [x for x in rows if x[2] >= BIG_LOT]
    out["big"] = {"n": len(big), "vol": sum(x[2] for x in big),
                  "buy": sum(x[2] for x in big if x[3] > 0), "sell": sum(x[2] for x in big if x[3] < 0),
                  "top3": sorted(big, key=lambda x: -x[2])[:3]}
    # ⑤ 逐分钟节奏
    per = {}
    for t, px, vol, sg in rows:
        k = t // 60
        d = per.setdefault(k, {"vol": 0.0, "net": 0.0, "b": 0.0, "s": 0.0, "px": px})
        d["vol"] += vol
        d["net"] += sg * vol
        if sg > 0:
            d["b"] += vol
        elif sg < 0:
            d["s"] += vol
        d["px"] = px
    out["per_min"] = [{"t": k * 60, **v, "ratio": (v["b"] / (v["b"] + v["s"])) if (v["b"] + v["s"]) else None}
                      for k, v in sorted(per.items())]
    # ⑥ 数据质量：有成交的 5 分钟格
    out["bins"] = len({t // 300 for t, _, _, _ in rows})
    return out


def _hms(t):
    return "%02d:%02d:%02d" % (t // 3600, (t % 3600) // 60, t % 60) if isinstance(t, int) else "—"


def _f(v, nd=2, signed=True):
    if v is None:
        return '—'
    return ("%+.*f" % (nd, v)) if signed else ("%.*f" % (nd, v))


def render(a, aside):
    if not a:
        return "<div style='font-size:0.8rem;color:#94a3b8;'>（当日无 tick 文件 ⇒ TICK 深度分析不可用 ✗）</div>"
    sign = 1 if aside == 'bullish' else -1
    up = aside == 'bullish'
    o = a["overview"]
    ov = ("<table style='border-collapse:collapse;font-size:0.78rem;width:auto;'>"
          "<tr style='background:#f1f5f9;color:#475569;'>"
          + "".join("<th style='padding:4px 8px;border:1px solid #e2e8f0;'>" + x + "</th>"
                    for x in ("成交量", "主动买 / 卖", "净 Delta", "买占比", "笔数", "平均/最大单笔", "最新价"))
          + "</tr><tr>"
          + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(o['vol'], 0, False) + "</td>"
          + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(o['buy'], 0, False) + " / " + _f(o['sell'], 0, False) + "</td>"
          + "<td style='padding:4px 8px;border:1px solid #e2e8f0;font-weight:700;'>" + _f(o['net'], 0) + "</td>"
          + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(o['ratio'], 3, False) + "</td>"
          + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(o['n'], 0, False) + "</td>"
          + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(o['avg'], 2, False) + " / " + _f(o['max'], 0, False) + "</td>"
          + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(o['px'], 2, False) + "</td></tr></table>")
    wr = "".join("<tr><td style='padding:4px 8px;border:1px solid #e2e8f0;'>T−" + str(w) + "′</td>"
                 + "<td style='padding:4px 8px;border:1px solid #e2e8f0;text-align:right;font-weight:700;'>" + _f(d['net'], 0) + "</td>"
                 + "<td style='padding:4px 8px;border:1px solid #e2e8f0;text-align:right;'>" + _f(d['vol'], 0, False) + "</td>"
                 + "<td style='padding:4px 8px;border:1px solid #e2e8f0;text-align:right;'>" + _f(d['dpx']) + "</td>"
                 + "<td style='padding:4px 8px;border:1px solid #e2e8f0;text-align:right;'>" + _f(d['ratio'], 3, False) + "</td>"
                 + "<td style='padding:4px 8px;border:1px solid #e2e8f0;text-align:center;'>"
                 + ("<span style='color:#047857;'>顺势 ✓</span>" if d['net'] * sign > 0 else "<span style='color:#b91c1c;'>逆势 ✗</span>") + "</td></tr>"
                 for w, d in sorted(a["windows"].items(), key=lambda kv: kv[0]))
    win = ("<div style='font-weight:700;font-size:0.8rem;color:#0f172a;margin:8px 0 2px;'>分窗口（截至发帖 ✓ tick 严格口径 ✓）</div>"
           "<table style='border-collapse:collapse;font-size:0.78rem;width:auto;'>"
           "<tr style='background:#f1f5f9;color:#475569;'>"
           + "".join("<th style='padding:4px 8px;border:1px solid #e2e8f0;'>" + x + "</th>"
                     for x in ("窗口", "净 Delta", "成交量", "价格位移", "买占比", "判定")) + "</tr>" + wr + "</table>")
    pf = a["profile"]
    prof = ("<div style='font-weight:700;font-size:0.8rem;color:#0f172a;margin:8px 0 2px;'>价位分布（Volume Profile ✓ 70% 价值区 ✓）</div>"
            "<table style='border-collapse:collapse;font-size:0.78rem;width:auto;'>"
            "<tr style='background:#f1f5f9;color:#475569;'>"
            + "".join("<th style='padding:4px 8px;border:1px solid #e2e8f0;'>" + x + "</th>"
                      for x in ("VAL（价值区下沿）", "POC（最密集）", "VAH（价值区上沿）", "收盘价相对价值区"))
            + "</tr><tr>"
            + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(pf['val'], 2, False) + "</td>"
            + "<td style='padding:4px 8px;border:1px solid #e2e8f0;font-weight:700;'>" + _f(pf['poc'], 2, False) + "</td>"
            + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(pf['vah'], 2, False) + "</td>"
            + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>"
            + ("<b style='color:#047857;'>价内（VAL–VAH 之间 ✓）</b>" if pf['val'] <= o['px'] <= pf['vah']
               else ("<b style='color:#b45309;'>低于 VAL ⇒ 折价 ✓</b>" if o['px'] < pf['val'] else "<b style='color:#b45309;'>高于 VAH ⇒ 溢价 ⚠️</b>"))
            + "</td></tr></table>"
            + "<div style='font-size:0.76rem;color:#475569;margin-top:2px;'>Top5 成交密集价："
            + " · ".join(_f(p, 2, False) + "（" + _f(v, 0, False) + " 手）" for p, v in pf["top5"]) + "</div>")
    b = a["big"]
    bigs = ("<div style='font-weight:700;font-size:0.8rem;color:#0f172a;margin:8px 0 2px;'>大单（单笔 ≥" + str(BIG_LOT) + " 手 ✓）</div>"
            "<table style='border-collapse:collapse;font-size:0.78rem;width:auto;'>"
            "<tr style='background:#f1f5f9;color:#475569;'><th style='padding:4px 8px;border:1px solid #e2e8f0;'>笔数</th>"
            "<th style='padding:4px 8px;border:1px solid #e2e8f0;'>合计量</th>"
            "<th style='padding:4px 8px;border:1px solid #e2e8f0;'>主动买 / 卖</th>"
            "<th style='padding:4px 8px;border:1px solid #e2e8f0;'>最大 3 笔</th></tr>"
            + "<tr><td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + str(b['n']) + "</td>"
            + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(b['vol'], 0, False) + "</td>"
            + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(b['buy'], 0, False) + " / " + _f(b['sell'], 0, False) + "</td>"
            + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>"
            + " · ".join(_hms(x[0])[:5] + " " + _f(x[2], 0, False) + "手@" + _f(x[1], 2, False)
                         + ("（主动买 ✓）" if x[3] > 0 else "（主动卖 ✗）") for x in b["top3"]) + "</td></tr></table>")
    # 逐分钟节奏（采样显示 ✓ 每 5 分钟 ✓）
    pm = a["per_min"]
    samp = [x for i, x in enumerate(pm) if i % 5 == 0 or i == len(pm) - 1]
    pace = ("<div style='font-weight:700;font-size:0.8rem;color:#0f172a;margin:8px 0 2px;'>逐分钟成交节奏（每 5 分钟采样 ✓）</div>"
            "<table style='border-collapse:collapse;font-size:0.76rem;width:auto;'>"
            "<tr style='background:#f1f5f9;color:#475569;'>"
            + "".join("<th style='padding:4px 7px;border:1px solid #e2e8f0;'>" + x + "</th>"
                      for x in ("时刻", "成交量", "净 Delta", "买占比", "价"))
            + "</tr>"
            + "".join("<tr><td style='padding:4px 7px;border:1px solid #e2e8f0;'>" + _hms(x['t'])[:5] + "</td>"
                      + "<td style='padding:4px 7px;border:1px solid #e2e8f0;text-align:right;'>" + _f(x['vol'], 0, False) + "</td>"
                      + "<td style='padding:4px 7px;border:1px solid #e2e8f0;text-align:right;font-weight:700;'>" + _f(x['net'], 0) + "</td>"
                      + "<td style='padding:4px 7px;border:1px solid #e2e8f0;text-align:right;'>" + _f(x['ratio'], 3, False) + "</td>"
                      + "<td style='padding:4px 7px;border:1px solid #e2e8f0;'>" + _f(x['px'], 2, False) + "</td></tr>"
                      for x in samp) + "</table>")
    # 解读
    sup, con = [], []
    if o['net'] * sign > 0:
        sup.append("发帖前 60 分钟净 Delta <b>%s</b>（买占比 %.3f ✓）与其方向同向 ⇒ 主动成交支持他 ✓" % (_f(o['net'], 0), o['ratio'] or 0))
    else:
        con.append("发帖前 60 分钟净 Delta <b>%s</b> 与其方向相反 ✗（但短窗口可能已转 ✓ 见分窗口表）" % _f(o['net'], 0))
    if a['windows'].get(5) and a['windows'][5]['net'] * sign > 0:
        sup.append("最近 5 分钟净 Delta <b>%s</b> 已同向 ⇒ 短周期动能确认 ✓" % _f(a['windows'][5]['net'], 0))
    if o['px'] < pf['val']:
        sup.append("最新价 <b>%.2f</b> 低于 70%% 价值区下沿 %.2f ⇒ 处于**折价区** ✓（利于其看多 ✓）" % (o['px'], pf['val']))
    elif o['px'] > pf['vah']:
        con.append("最新价 <b>%.2f</b> 高于价值区上沿 %.2f ⇒ 溢价区 ⚠️" % (o['px'], pf['vah']))
    if b['n'] and b['buy'] > b['sell'] * 1.2:
        sup.append("大单主动买 <b>%s</b> 手 > 卖 %s 手 ⇒ 大额资金偏多 ✓" % (_f(b['buy'], 0, False), _f(b['sell'], 0, False)))
    elif b['n'] and b['sell'] > b['buy'] * 1.2:
        con.append("大单主动卖 <b>%s</b> 手 > 买 %s 手 ✗" % (_f(b['sell'], 0, False), _f(b['buy'], 0, False)))
    if a['bins'] < 8:
        con.append("⚠️ 数据质量：窗口内仅 <b>%d</b> 个 5 分钟格有成交（偏少 ⚠️）—— 与引擎 <code>trade_bins</code> 退化现象相符 ✓" % a['bins'])
    def _ul(items, color, title, empty):
        if items:
            return ("<div style='margin:4px 0 2px;font-size:0.78rem;color:" + color + ";font-weight:700;'>" + title + "</div>"
                    + "<ul style='margin:2px 0 2px 18px;font-size:0.78rem;line-height:1.65;'>"
                    + "".join("<li>" + x + "</li>" for x in items) + "</ul>")
        return ("<div style='margin:4px 0 2px;font-size:0.78rem;color:" + color + ";font-weight:700;'>" + title + "</div>"
                + "<div style='margin-left:18px;font-size:0.78rem;color:#94a3b8;'>（" + empty + "）</div>")
    return ("<div style='margin-top:10px;padding:8px 12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;'>"
            "<div style='font-weight:800;color:#0f172a;font-size:0.84rem;margin-bottom:4px;'>6️⃣ 📈 TICK 深度分析（逐笔成交 · 全部指标 ✓）</div>"
            "<div style='font-size:0.78rem;color:#64748b;margin-bottom:6px;'>"
            "数据：原始 tick（截止发帖时刻 ✓ 无前视 ✓）；主动买 = 吃 ASK ✓ 主动卖 = 吃 BID ✓（与 MW 口径一致 ✓）</div>"
            + ov + "<div style='height:6px;'></div>" + win + prof + bigs + pace
            + _ul(sup, '#047857', '✅ TICK 提供的支持证据', '无 —— 成交未给出支持信号 ✗')
            + _ul(con, '#b91c1c', '⚠️ TICK 提示的反向 / 风险', '无 ✓')
            + "</div>")


if __name__ == '__main__':
    import re
    day = sys.argv[1] if len(sys.argv) > 1 else '2026-09-10'
    t = sys.argv[2] if len(sys.argv) > 2 else '07:14:21'
    h, m, s = t.split(':')
    a = tick_analysis(day, int(h) * 3600 + int(m) * 60 + int(s))
    print(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' | ', render(a, 'bullish')))[:1800])
