# -*- coding: utf-8 -*-
"""adam_dom_analysis —— DOM（盘口挂单）**深度分析**：把盘口翻译成人能读懂的结论

用户需求（2026-09-12）：TICK 指标可直观理解，但 **DOM 几乎不会自己看** ⇒ 必须给出
**深入、充分、可读**的 DOM 分析 ✓（含"这意味着什么"的中文解读 ✓）。

计算项（全部来自原始 DOM 快照 ✓ 无前视 ✓）
  ① 盘口概览：mid / best bid·ask 及手数 / 价差 ✓
  ② 分带宽失衡 + **买卖挂单总量对比**（±2 / ±5 / ±15 / ±25 ticks ✓）
  ③ **挂单墙**：两侧最大单档（价位 / 手数 / 距 mid 点数 ✓）
  ④ **堆叠**：连续相邻大档 ≥N 手 的组数与合计（Stack ✓）
  ⑤ **真空**：盘口内最大的无挂单价格缺口（Vacuum ✓）
  ⑥ 全盘总量：200 档买/卖手数合计与比值 ✓
  ⑦ **时间演变**：T−60 / −30 / −15 / −5 / T0 五个快照的（mid / ±5 失衡 / 买墙 / 卖墙 / 总量比 ✓）
  ⑧ 引擎 11 项 dom_metrics 同名对照（能复算的复算 ✓ 不能的如实标注 ✗ 如冰山需 tick 交互 ✓）
仅分析参考 ✓ 不接入自动下单 ✓
"""
from __future__ import annotations
import csv, sys
from pathlib import Path

sys.path.append('/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools')
RAW_DIR = Path("/Users/zhijiebian/Documents/MyDoc/Finance/Current/MotiveWave_OrderFlow_Data/Raw")
TICK = 0.25
BANDS = [2, 5, 15, 25]
STACK_MIN = 30          # 单档 ≥30 手视为"大档"✓
WALL_DELTA = 40         # 分钟间墙变动 ≥40 手 ⇒ 记为新增/撤走事件 ✓
EVO_OFFSETS = [60, 30, 15, 5, 0]


def _pt(ms):
    return int(int(ms) // 1000 - 7 * 3600) % 86400


def _profile(buf, ref):
    """单快照 → 结构化盘口画像（无效返回 None ✓）"""
    bids = [(pr, sz) for _, ty, pr, sz in buf if ty == 'BID']
    asks = [(pr, sz) for _, ty, pr, sz in buf if ty == 'ASK']
    if len(bids) < 50 or len(asks) < 50:
        return None
    bb, ba = max(p for p, _ in bids), min(p for p, _ in asks)
    if bb >= ba:
        return None
    mid = (bb + ba) / 2.0
    if ref is not None and abs(mid - ref) > 20.0:
        return None
    out = {"time": buf[0][0], "mid": mid, "bb": bb, "ba": ba,
           "bb_sz": next(s for p, s in bids if p == bb), "ba_sz": next(s for p, s in asks if p == ba),
           "spread": ba - bb, "n_bid": len(bids), "n_ask": len(asks),
           "tot_bid": sum(s for _, s in bids), "tot_ask": sum(s for _, s in asks)}
    for b in BANDS:
        bs = sum(s for p, s in bids if abs(p - mid) <= b * TICK)
        a_s = sum(s for p, s in asks if abs(p - mid) <= b * TICK)
        out["imb_%d" % b] = ((bs - a_s) / (bs + a_s)) if (bs + a_s) else None
        out["bid_%d" % b] = bs
        out["ask_%d" % b] = a_s
    # 挂单墙（两侧最大单档 ✓）
    wb = max(bids, key=lambda x: x[1])
    wa = max(asks, key=lambda x: x[1])
    out["wall_bid"] = {"px": wb[0], "sz": wb[1], "dist": (mid - wb[0]) / TICK}
    out["wall_ask"] = {"px": wa[0], "sz": wa[1], "dist": (wa[0] - mid) / TICK}
    # 堆叠（同侧相邻大档 ✓）
    def _stack(levels, side):
        lv = sorted(levels, key=lambda x: x[0], reverse=(side == 'BID'))
        best = cur = 0
        cur_sum = best_sum = 0
        prev = None
        for p, s in lv:
            if s >= STACK_MIN and prev is not None and abs(p - prev) <= TICK * 1.5:
                cur += 1; cur_sum += s
            elif s >= STACK_MIN:
                cur, cur_sum = 1, s
            else:
                cur, cur_sum = 0, 0
            if cur > best:
                best, best_sum = cur, cur_sum
            prev = p
        return best, best_sum
    out["stack_bid"] = _stack(bids, 'BID')
    out["stack_ask"] = _stack(asks, 'ASK')
    # 真空（盘口内最大无挂单缺口 ✓ 以 tick 为单位 ✓）
    def _vacuum(levels):
        px = sorted(p for p, _ in levels)
        gaps = [(px[i + 1] - px[i], px[i], px[i + 1]) for i in range(len(px) - 1)]
        if not gaps:
            return None
        g, p0, p1 = max(gaps)
        return {"ticks": g / TICK, "from": p0, "to": p1}
    out["vac_bid"] = _vacuum(bids)
    out["vac_ask"] = _vacuum(asks)
    return out


def dom_analysis(day, t0_sec, ref_price=None, offsets=None, extra_targets=None):
    """一次扫描 DOM 文件 → 返回 {offset: profile}（offset=分钟前 ✓ 0=T0 ✓）"""
    offsets = offsets or EVO_OFFSETS
    f = RAW_DIR / ("ES_%s_DOM.csv.gz" % str(day).replace('-', ''))
    if not f.exists():
        f = RAW_DIR / ("ES_%s_DOM.csv" % str(day).replace('-', ''))
        if not f.exists():
            return None
    targets = {o: t0_sec - o * 60 for o in offsets}
    _extra = list(extra_targets or [])          # ★ 各引擎行时刻的 DOM 画像 ✓
    _extra_state = {t: None for t in _extra}
    lo = min(targets.values()) - 180
    best = {o: None for o in offsets}
    last_valid = {}
    by_min = {}          # ★ 逐分钟序列（取该分钟最后一个有效快照 ✓）
    cur = None
    buf = []
    try:
        from py_lib.mw_gzip import open_text
        with open_text(str(f), 'rt') as fh:
            rdr = csv.reader(fh)
            next(rdr, None)
            for row in rdr:
                if len(row) < 5:
                    continue
                try:
                    t = _pt(row[0])
                except Exception:
                    continue
                if t > t0_sec:
                    break
                if t < lo:
                    continue
                if row[0] != cur:
                    if buf:
                        prof = _profile(buf, ref_price)
                        if prof:
                            by_min[prof["time"] // 60] = prof     # ★ 逐分钟（覆盖 ⇒ 取每分钟最后一个 ✓）
                            for _t in _extra:
                                if prof['time'] <= _t:
                                    _extra_state[_t] = prof      # 保留"不晚于该时刻"的最近快照 ✓
                            for o, tt in targets.items():
                                if prof["time"] <= tt:
                                    last_valid[o] = prof        # 保留"不晚于目标时刻"的最近快照 ✓
                    buf = []
                    cur = row[0]
                try:
                    buf.append((_pt(row[0]), row[1].upper(), float(row[3]), float(row[4])))
                except Exception:
                    pass
            if buf:
                prof = _profile(buf, ref_price)
                if prof:
                    by_min[prof["time"] // 60] = prof
                    for o, tt in targets.items():
                        if prof["time"] <= tt:
                            last_valid[o] = prof
    except Exception:
        return None
    for o in offsets:
        best[o] = last_valid.get(o)
    # ★ 组装逐分钟序列（最近 60 分钟 ✓）
    series = [by_min[k] for k in sorted(by_min) if k >= (t0_sec // 60) - 60]
    # ★ 墙变化事件（分钟间最大单档变动 ≥ WALL_DELTA 手 ✓ ⇒ 新增/撤走 ✓ 近似撤单识别 ✓）
    events = []
    for i in range(1, len(series)):
        a, b = series[i - 1], series[i]
        for side, key in (('买', 'wall_bid'), ('卖', 'wall_ask')):
            d = b[key]['sz'] - a[key]['sz']
            if abs(d) >= WALL_DELTA:
                events.append({"t": b["time"], "side": side, "px": b[key]['px'], "d": d, "sz": b[key]['sz']})
    best["_at"] = _extra_state          # ★ 各引擎行时刻的 DOM 画像 ✓
    best["_series"] = series
    best["_events"] = events
    try:
        _vp = vwap_poc(day, t0_sec)
        if _vp:
            best["_vwap"] = _vp
    except Exception:
        pass
    return best


def vwap_poc(day, t0_sec):
    """★ 用 tick 复算 **session VWAP** 与 **POC**（截至 t0 ✓ 无前视 ✓）。"""
    famt = fvol = 0.0
    hist = {}
    f = RAW_DIR / ("ES_%s_TICKS.csv" % str(day).replace('-', ''))
    if not f.exists():
        return None
    try:
        from py_lib.mw_gzip import open_text
        with open_text(str(f), 'rt') as fh:
            rdr = csv.reader(fh)
            next(rdr, None)
            for row in rdr:
                if len(row) < 3:
                    continue
                try:
                    t = _pt(row[0])
                except Exception:
                    continue
                if t > t0_sec:
                    break
                try:
                    px, vol = float(row[1]), (float(row[2]) if row[2] else 0.0)
                except Exception:
                    continue
                if vol <= 0:
                    continue
                famt += px * vol
                fvol += vol
                hist[round(px / TICK)] = hist.get(round(px / TICK), 0.0) + vol
    except Exception:
        return None
    if not fvol:
        return None
    poc_t = max(hist, key=hist.get) if hist else None
    return {"vwap": famt / fvol, "poc": poc_t * TICK if poc_t is not None else None, "vol": fvol}


def _hms(t):
    return "%02d:%02d:%02d" % (t // 3600, (t % 3600) // 60, t % 60) if isinstance(t, int) else "—"


def _f(v, nd=2, signed=True):
    if v is None:
        return '—'
    return ("%+.*f" % (nd, v)) if signed else ("%.*f" % (nd, v))


def render(prof_by_off, aside, engine_dom=None):
    """DOM 深度分析 HTML（表格 + 中文解读 ✓）"""
    p0 = prof_by_off.get(0) if prof_by_off else None
    if not p0:
        return "<div style='font-size:0.8rem;color:#94a3b8;'>（当日无有效 DOM 快照 ⇒ DOM 深度分析不可用 ✗）</div>"
    sign = 1 if aside == 'bullish' else -1
    up = aside == 'bullish'
    # ① 概览
    ov = ("<table style='border-collapse:collapse;font-size:0.78rem;width:auto;'>"
          + "<tr style='background:#f1f5f9;color:#475569;'>"
          + "".join("<th style='padding:4px 8px;border:1px solid #e2e8f0;'>" + x + "</th>"
                    for x in ("快照时刻", "mid", "最优买/卖", "最优档手数 买/卖", "价差", "档位数 买/卖", "全盘总量 买/卖", "总量比"))
          + "</tr><tr>"
          + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _hms(p0['time']) + "</td>"
          + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(p0['mid'], 2, False) + "</td>"
          + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(p0['bb'], 2, False) + " / " + _f(p0['ba'], 2, False) + "</td>"
          + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(p0['bb_sz'], 0, False) + " / " + _f(p0['ba_sz'], 0, False) + "</td>"
          + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(p0['spread'] / TICK, 0, False) + " ticks</td>"
          + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + str(p0['n_bid']) + " / " + str(p0['n_ask']) + "</td>"
          + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(p0['tot_bid'], 0, False) + " / " + _f(p0['tot_ask'], 0, False) + "</td>"
          + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'><b>" + _f(p0['tot_bid'] / p0['tot_ask'] if p0['tot_ask'] else None, 2, False) + "</b></td>"
          + "</tr></table>")
    # ② 分带宽
    bw = ("<table style='border-collapse:collapse;font-size:0.78rem;width:auto;'>"
          + "<tr style='background:#f1f5f9;color:#475569;'>"
          + "".join("<th style='padding:4px 8px;border:1px solid #e2e8f0;'>" + x + "</th>"
                    for x in ("带宽", "买挂单", "卖挂单", "失衡 (买−卖)/(买+卖)", "解读"))
          + "</tr>"
          + "".join("<tr><td style='padding:4px 8px;border:1px solid #e2e8f0;'>±" + str(b) + " ticks（≈" + _f(b * TICK, 2, False) + " 点）</td>"
                    + "<td style='padding:4px 8px;border:1px solid #e2e8f0;text-align:right;'>" + _f(p0.get('bid_%d' % b), 0, False) + "</td>"
                    + "<td style='padding:4px 8px;border:1px solid #e2e8f0;text-align:right;'>" + _f(p0.get('ask_%d' % b), 0, False) + "</td>"
                    + "<td style='padding:4px 8px;border:1px solid #e2e8f0;text-align:right;font-weight:700;'>" + _f(p0.get('imb_%d' % b), 3) + "</td>"
                    + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>"
                    + ("<span style='color:#047857;'>买侧占优 ✓</span>" if (p0.get('imb_%d' % b) or 0) * sign > 0.02
                       else ("<span style='color:#b91c1c;'>卖侧占优 ✗</span>" if p0.get('imb_%d' % b) is not None and (p0.get('imb_%d' % b)) * sign < -0.02
                             else "<span style='color:#64748b;'>接近平衡</span>"))
                    + "</td></tr>" for b in BANDS) + "</table>")
    # ③ 墙 / ④ 堆叠 / ⑤ 真空
    wb, wa = p0['wall_bid'], p0['wall_ask']
    walls = ("<table style='border-collapse:collapse;font-size:0.78rem;width:auto;'>"
             + "<tr style='background:#f1f5f9;color:#475569;'>"
             + "".join("<th style='padding:4px 8px;border:1px solid #e2e8f0;'>" + x + "</th>"
                       for x in ("项", "买侧", "卖侧"))
             + "</tr>"
             + "<tr><td style='padding:4px 8px;border:1px solid #e2e8f0;'>最大单档（墙 ✓）</td>"
             + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(wb['sz'], 0, False) + " 手 @ " + _f(wb['px'], 2, False)
             + "（距 mid " + _f(wb['dist'], 0, False) + " ticks ✓）</td>"
             + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(wa['sz'], 0, False) + " 手 @ " + _f(wa['px'], 2, False)
             + "（距 mid " + _f(wa['dist'], 0, False) + " ticks ✓）</td></tr>"
             + "<tr><td style='padding:4px 8px;border:1px solid #e2e8f0;'>堆叠（相邻 ≥" + str(STACK_MIN) + " 手 ✓）</td>"
             + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + str(p0['stack_bid'][0]) + " 档 / 合计 " + _f(p0['stack_bid'][1], 0, False) + " 手</td>"
             + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + str(p0['stack_ask'][0]) + " 档 / 合计 " + _f(p0['stack_ask'][1], 0, False) + " 手</td></tr>"
             + "<tr><td style='padding:4px 8px;border:1px solid #e2e8f0;'>最大真空（缺口 ✓）</td>"
             + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>"
             + (_f(p0['vac_bid']['ticks'], 0, False) + " ticks（" + _f(p0['vac_bid']['from'], 2, False) + "→" + _f(p0['vac_bid']['to'], 2, False) + "）" if p0.get('vac_bid') else '—') + "</td>"
             + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>"
             + (_f(p0['vac_ask']['ticks'], 0, False) + " ticks（" + _f(p0['vac_ask']['from'], 2, False) + "→" + _f(p0['vac_ask']['to'], 2, False) + "）" if p0.get('vac_ask') else '—') + "</td></tr>"
             + "</table>")
    # ⑥ 演变
    evo = ""
    if prof_by_off:
        rows = []
        for o in EVO_OFFSETS:
            pr = prof_by_off.get(o)
            if not pr:
                continue
            rows.append("<tr><td style='padding:4px 8px;border:1px solid #e2e8f0;'>"
                        + ("T0（发帖 ✓）" if o == 0 else "T−" + str(o) + "′") + "</td>"
                        + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _hms(pr['time']) + "</td>"
                        + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(pr['mid'], 2, False) + "</td>"
                        + "<td style='padding:4px 8px;border:1px solid #e2e8f0;text-align:right;'>" + _f(pr.get('imb_5'), 3) + "</td>"
                        + "<td style='padding:4px 8px;border:1px solid #e2e8f0;text-align:right;'>" + _f(pr.get('imb_15'), 3) + "</td>"
                        + "<td style='padding:4px 8px;border:1px solid #e2e8f0;text-align:right;'>" + _f(pr['tot_bid'] / pr['tot_ask'] if pr['tot_ask'] else None, 2, False) + "</td>"
                        + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(pr['wall_bid']['sz'], 0, False) + " 手 @ " + _f(pr['wall_bid']['px'], 2, False) + "</td>"
                        + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(pr['wall_ask']['sz'], 0, False) + " 手 @ " + _f(pr['wall_ask']['px'], 2, False) + "</td></tr>")
        evo = ("<div style='font-weight:700;font-size:0.8rem;color:#0f172a;margin:8px 0 2px;'>"
               "DOM 时间演变（发帖前 60/30/15/5 分钟 → 发帖时刻 ✓）</div>"
               "<table style='border-collapse:collapse;font-size:0.76rem;width:auto;'>"
               "<tr style='background:#f1f5f9;color:#475569;'>"
               + "".join("<th style='padding:4px 7px;border:1px solid #e2e8f0;'>" + x + "</th>"
                         for x in ("时点", "快照", "mid", "±5 失衡", "±15 失衡", "全盘买/卖比", "最大买墙", "最大卖墙"))
               + "</tr>" + "".join(rows) + "</table>")
    # ⑦ 引擎 11 项同名对照
    eng = ""
    if engine_dom:
        kmap = [("imb_near", "近端失衡（±2 定义未公开 ✗）"), ("imb_mid", "中部失衡"), ("imb_deep", "深层失衡"),
                ("spoof_ask", "虚假挂单 卖（Spoof ✓）"), ("spoof_bid", "虚假挂单 买 ✓"),
                ("stack_ask", "卖侧堆叠 ✓"), ("stack_bid", "买侧堆叠 ✓"),
                ("vacuum_ask", "卖侧真空 ✓"), ("vacuum_bid", "买侧真空 ✓"),
                ("iceberg_bear", "卖侧冰山（需 tick 交互 ✗ 不可复算 ✓）"), ("iceberg_bull", "买侧冰山（同上 ✓）")]
        eng = ("<div style='font-weight:700;font-size:0.8rem;color:#0f172a;margin:8px 0 2px;'>"
               "引擎 <code>dom_metrics</code> 全部 11 项（同名对照 ✓）</div>"
               "<table style='border-collapse:collapse;font-size:0.76rem;width:auto;'>"
               "<tr style='background:#f1f5f9;color:#475569;'><th style='padding:4px 8px;border:1px solid #e2e8f0;'>引擎字段</th>"
               "<th style='padding:4px 8px;border:1px solid #e2e8f0;'>含义</th>"
               "<th style='padding:4px 8px;border:1px solid #e2e8f0;'>发帖前值</th>"
               "<th style='padding:4px 8px;border:1px solid #e2e8f0;'>本模块复算</th></tr>"
               + "".join("<tr><td style='padding:4px 8px;border:1px solid #e2e8f0;'><code>" + k + "</code></td>"
                         + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + lab + "</td>"
                         + "<td style='padding:4px 8px;border:1px solid #e2e8f0;text-align:right;'>" + _f(_num(engine_dom.get(k)), 3) + "</td>"
                         + "<td style='padding:4px 8px;border:1px solid #e2e8f0;text-align:right;'>"
                         + ({'imb_near': _f(p0.get('imb_2'), 3), 'imb_mid': _f(p0.get('imb_5'), 3),
                             'imb_deep': _f(p0.get('imb_15'), 3), 'stack_bid': str(p0['stack_bid'][0]) + " 档",
                             'stack_ask': str(p0['stack_ask'][0]) + " 档",
                             'vacuum_bid': _f(p0['vac_bid']['ticks'], 0, False) if p0.get('vac_bid') else '—',
                             'vacuum_ask': _f(p0['vac_ask']['ticks'], 0, False) if p0.get('vac_ask') else '—'}.get(k, '（不适用 ✗）'))
                         + "</td></tr>" for k, lab in kmap) + "</table>")
    # ⑧ 中文解读
    sup, con = [], []
    if (p0.get('imb_5') or 0) * sign > 0.02:
        sup.append("±5 ticks（≈1.25 点）内 **买挂单多出卖 %s 手**（失衡 %s ✓）⇒ 近端下方有承接 ✓" % (
            _f((p0.get('bid_5') or 0) - (p0.get('ask_5') or 0), 0, False), _f(p0.get('imb_5'), 3)))
    elif (p0.get('imb_5') or 0) * sign < -0.02:
        con.append("±5 ticks 内 **卖挂单多出买 %s 手**（失衡 %s ✗）⇒ 近端上方压制 ✓" % (
            _f((p0.get('ask_5') or 0) - (p0.get('bid_5') or 0), 0, False), _f(p0.get('imb_5'), 3)))
    ratio = (p0['tot_bid'] / p0['tot_ask']) if p0['tot_ask'] else None
    if ratio is not None:
        if ratio >= 1.05:
            sup.append("全盘 200 档挂单 **买/卖 = %.2f**（买侧总量占优 ✓）⇒ 整体挂单结构偏多 ✓" % ratio)
        elif ratio <= 0.95:
            con.append("全盘 200 档挂单 **买/卖 = %.2f**（卖侧总量占优 ✗）" % ratio)
    wb, wa = p0['wall_bid'], p0['wall_ask']
    if wb['sz'] >= wa['sz']:
        sup.append("**买墙更大**（%s 手 @ %s，距 mid %s ticks ✓ vs 卖墙 %s 手）⇒ 近端下方有大额防守 ✓" % (
            _f(wb['sz'], 0, False), _f(wb['px'], 2, False), _f(wb['dist'], 0, False), _f(wa['sz'], 0, False)))
    else:
        con.append("**卖墙更大**（%s 手 @ %s，距 mid %s ticks ✗ vs 买墙 %s 手）⇒ 上方阻力更重 ✗" % (
            _f(wa['sz'], 0, False), _f(wa['px'], 2, False), _f(wa['dist'], 0, False), _f(wb['sz'], 0, False)))
    if p0['stack_bid'][0] > p0['stack_ask'][0]:
        sup.append("买侧**堆叠** %d 档（合计 %s 手 ✓）多于卖侧 %d 档 ⇒ 买方分批囤单 ✓" % (
            p0['stack_bid'][0], _f(p0['stack_bid'][1], 0, False), p0['stack_ask'][0]))
    elif p0['stack_ask'][0] > p0['stack_bid'][0]:
        con.append("卖侧**堆叠** %d 档（合计 %s 手 ✗）多于买侧 %d 档 ⇒ 卖方分批压制 ✗" % (
            p0['stack_ask'][0], _f(p0['stack_ask'][1], 0, False), p0['stack_bid'][0]))
    vac_b = (p0.get('vac_bid') or {}).get('ticks')
    if vac_b and vac_b >= 4:
        sup.append("买侧存在 **%s ticks 真空**（缺口 %s→%s ✓）⇒ 若跌破该缺口下行会加速 ⚠️（双刃 ✓）" % (
            _f(vac_b, 0, False), _f(p0['vac_bid']['from'], 2, False), _f(p0['vac_bid']['to'], 2, False)))
    # 演变解读（±5 失衡的方向变化 ✓）
    a60, a0 = (prof_by_off.get(60) or {}).get('imb_5'), p0.get('imb_5')
    if a60 is not None and a0 is not None:
        if a0 * sign > 0 and a60 * sign < 0:
            sup.append("±5 失衡由 **T−60 的 %s → T0 的 %s** ⇒ 近端挂单**由空转多**（与他同向 ✓✓）" % (_f(a60, 3), _f(a0, 3)))
        elif a0 * sign < 0 and a60 * sign > 0:
            con.append("±5 失衡由 T−60 的 %s → T0 的 %s ⇒ 近端挂单**转空** ✗" % (_f(a60, 3), _f(a0, 3)))
    def _ul(items, color, title, empty):
        if items:
            return ("<div style='margin:4px 0 2px;font-size:0.78rem;color:" + color + ";font-weight:700;'>" + title + "</div>"
                    + "<ul style='margin:2px 0 2px 18px;font-size:0.78rem;line-height:1.65;'>"
                    + "".join("<li>" + x + "</li>" for x in items) + "</ul>")
        return ("<div style='margin:4px 0 2px;font-size:0.78rem;color:" + color + ";font-weight:700;'>" + title + "</div>"
                + "<div style='margin-left:18px;font-size:0.78rem;color:#94a3b8;'>（" + empty + "）</div>")
    # 1️⃣ 逐分钟序列（每 5 分钟采样 ✓ 便于阅读与邮件 ✓）
    series = prof_by_off.get('_series') or []
    evs = prof_by_off.get('_events') or []
    samp = [x for i, x in enumerate(series) if i % 5 == 0 or i == len(series) - 1]
    ser_tbl = ""
    if samp:
        ser_tbl = ("<div style='font-weight:700;font-size:0.8rem;color:#0f172a;margin:8px 0 2px;'>"
                   "买卖压力与挂单墙 · 逐分钟序列（每 5 分钟采样 ✓ 完整分钟序列见页面图表 ✓）</div>"
                   "<table style='border-collapse:collapse;font-size:0.76rem;width:auto;'>"
                   "<tr style='background:#f1f5f9;color:#475569;'>"
                   + "".join("<th style='padding:4px 7px;border:1px solid #e2e8f0;'>" + x + "</th>"
                             for x in ("时刻", "mid", "±5 失衡", "全盘买/卖比", "买墙", "卖墙"))
                   + "</tr>"
                   + "".join("<tr><td style='padding:4px 7px;border:1px solid #e2e8f0;'>" + _hms(x['time'])[:5] + "</td>"
                             + "<td style='padding:4px 7px;border:1px solid #e2e8f0;'>" + _f(x['mid'], 2, False) + "</td>"
                             + "<td style='padding:4px 7px;border:1px solid #e2e8f0;text-align:right;'>" + _f(x.get('imb_5'), 3) + "</td>"
                             + "<td style='padding:4px 7px;border:1px solid #e2e8f0;text-align:right;'>"
                             + _f(x['tot_bid'] / x['tot_ask'] if x['tot_ask'] else None, 2, False) + "</td>"
                             + "<td style='padding:4px 7px;border:1px solid #e2e8f0;'>" + _f(x['wall_bid']['sz'], 0, False) + " @" + _f(x['wall_bid']['px'], 2, False) + "</td>"
                             + "<td style='padding:4px 7px;border:1px solid #e2e8f0;'>" + _f(x['wall_ask']['sz'], 0, False) + " @" + _f(x['wall_ask']['px'], 2, False) + "</td></tr>"
                             for x in samp) + "</table>")
    ev_tbl = ""
    if evs:
        ev_tbl = ("<div style='font-weight:700;font-size:0.8rem;color:#0f172a;margin:8px 0 2px;'>"
                  "挂单墙**出现/消失**追踪（分钟间变动 ≥" + str(WALL_DELTA) + " 手 ✓ 近似撤单识别 ✓）</div>"
                  "<table style='border-collapse:collapse;font-size:0.76rem;width:auto;'>"
                  "<tr style='background:#f1f5f9;color:#475569;'>"
                  + "".join("<th style='padding:4px 7px;border:1px solid #e2e8f0;'>" + x + "</th>"
                            for x in ("时刻", "侧", "价位", "变动", "变动后手数", "解读"))
                  + "</tr>"
                  + "".join("<tr><td style='padding:4px 7px;border:1px solid #e2e8f0;'>" + _hms(e['t'])[:5] + "</td>"
                            + "<td style='padding:4px 7px;border:1px solid #e2e8f0;'>" + e['side'] + "</td>"
                            + "<td style='padding:4px 7px;border:1px solid #e2e8f0;'>" + _f(e['px'], 2, False) + "</td>"
                            + "<td style='padding:4px 7px;border:1px solid #e2e8f0;text-align:right;font-weight:700;color:"
                            + ("#047857" if e['d'] > 0 else "#b91c1c") + ";'>" + _f(e['d'], 0) + "</td>"
                            + "<td style='padding:4px 7px;border:1px solid #e2e8f0;text-align:right;'>" + _f(e['sz'], 0, False) + "</td>"
                            + "<td style='padding:4px 7px;border:1px solid #e2e8f0;'>"
                            + ("<b>新增大额挂单</b>（可能是真实防守 ✓ 也可能是诱导 ✗ 需结合成交判断 ✓）" if e['d'] > 0
                               else "<b>撤走大额挂单</b>（可能是撤单 ✗ 也可能是被成交 ✓ 快照无法区分 ⚠️）") + "</td></tr>"
                            for e in evs) + "</table>")
    # 2️⃣ 结构位（VWAP / POC ✓ 与墙位叠加 ✓）
    vp = prof_by_off.get('_vwap') or {}
    struct = ""
    if vp.get('vwap') and p0:
        def _rel(px):
            if px is None:
                return '—'
            d = (p0['mid'] - px) / TICK
            return _f(px, 2, False) + "（mid 上方 " + _f(-d, 0, False) + " ticks ✓）" if d < 0 else _f(px, 2, False) + "（mid 下方 " + _f(d, 0, False) + " ticks ✓）"
        struct = ("<div style='font-weight:700;font-size:0.8rem;color:#0f172a;margin:8px 0 2px;'>"
                  "价格结构位 × 挂单墙（VWAP / POC ✓ 与墙位叠加 ✓）</div>"
                  "<table style='border-collapse:collapse;font-size:0.76rem;width:auto;'>"
                  "<tr style='background:#f1f5f9;color:#475569;'>"
                  + "".join("<th style='padding:4px 8px;border:1px solid #e2e8f0;'>" + x + "</th>"
                            for x in ("结构位", "价位", "相对发帖价", "与墙位关系"))
                  + "</tr>"
                  + "<tr><td style='padding:4px 8px;border:1px solid #e2e8f0;'>Session VWAP ✓</td>"
                  + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(vp['vwap'], 2, False) + "</td>"
                  + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _rel(vp['vwap']) + "</td>"
                  + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>"
                  + ("价格在 VWAP <b>下方</b> ⇒ 处于**折价区** ✓（利于其看多逻辑 ✓）" if p0['mid'] < vp['vwap'] else "价格在 VWAP **上方** ⇒ 处于溢价区 ⚠️") + "</td></tr>"
                  + "<tr><td style='padding:4px 8px;border:1px solid #e2e8f0;'>POC（成交最密集价 ✓）</td>"
                  + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(vp.get('poc'), 2, False) + "</td>"
                  + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _rel(vp.get('poc')) + "</td>"
                  + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>"
                  + ("价格在 POC <b>下方</b> ⇒ 位于**价值区之下** ✓（拍卖理论：折价 ✓）" if (vp.get('poc') and p0['mid'] < vp['poc']) else "价格在 POC 上方 ⇒ 溢价 ⚠️") + "</td></tr>"
                  + "<tr><td style='padding:4px 8px;border:1px solid #e2e8f0;'>买墙（最大买档 ✓）</td>"
                  + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(wb['px'], 2, False) + "（" + _f(wb['sz'], 0, False) + " 手）</td>"
                  + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _rel(wb['px']) + "</td>"
                  + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>下方 " + _f(wb['dist'], 0, False) + " ticks 处的大额防守 ✓</td></tr>"
                  + "<tr><td style='padding:4px 8px;border:1px solid #e2e8f0;'>卖墙（最大卖档 ✓）</td>"
                  + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _f(wa['px'], 2, False) + "（" + _f(wa['sz'], 0, False) + " 手）</td>"
                  + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>" + _rel(wa['px']) + "</td>"
                  + "<td style='padding:4px 8px;border:1px solid #e2e8f0;'>上方 " + _f(wa['dist'], 0, False) + " ticks 处的压力 ✗</td></tr>"
                  + "</table>")
    # 图表占位（页面 JS 用 Highcharts 渲染 ✓ 邮件中自动忽略 ✓）
    import json as _json
    chart_data = [{"t": _hms(x['time'])[:5], "mid": x['mid'], "imb5": x.get('imb_5'),
                   "ratio": round(x['tot_bid'] / x['tot_ask'], 3) if x['tot_ask'] else None,
                   "wb": x['wall_bid']['sz'], "wbpx": x['wall_bid']['px'],
                   "wa": x['wall_ask']['sz'], "wapx": x['wall_ask']['px']} for x in series]
    chart = ("<div class='adam-dom-chart' data-vwap='" + str(vp.get('vwap') or '') + "' data-poc='" + str(vp.get('poc') or '') + "'"
             " data-series='" + _json.dumps(chart_data, ensure_ascii=False).replace("'", "&#39;") + "'"
             " style='height:260px;margin-top:8px;'></div>")
    return ("<div style='margin-top:10px;padding:8px 12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;'>"
            "<div style='font-weight:800;color:#0f172a;font-size:0.84rem;margin-bottom:4px;'>5️⃣ 🧱 DOM 深度分析（盘口挂单 · 全部指标 ✓）</div>"
            "<div style='font-size:0.78rem;color:#64748b;margin-bottom:6px;'>"
            "数据：原始 DOM 快照（500ms 级 ✓ 取发帖时刻及之前最近**有效**快照 ✓ 无前视 ✓）；"
            "本模块为**独立复算** ✓（引擎 <code>imb_*</code> 定义未公开 ✗ 但三档方向已对照 ✓）</div>"
            + ov + "<div style='height:6px;'></div>" + bw + "<div style='height:6px;'></div>" + walls + evo + eng
            + _ul(sup, '#047857', '✅ DOM 提供的支持证据', '无 —— 盘口未给出支持信号 ✗')
            + _ul(con, '#b91c1c', '⚠️ DOM 提示的反向 / 风险', '无 ✓')
            + ser_tbl + ev_tbl + struct + chart
            + "</div>")


def _num(v):
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


if __name__ == '__main__':
    import datetime
    day = sys.argv[1] if len(sys.argv) > 1 else '2026-09-10'
    t = sys.argv[2] if len(sys.argv) > 2 else '07:14:21'
    h, m, s = t.split(':')
    p = dom_analysis(day, int(h) * 3600 + int(m) * 60 + int(s), 7594.50)
    import re
    print(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' | ', render(p, 'bullish')))[:2200])
