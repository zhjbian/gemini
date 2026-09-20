# -*- coding: utf-8 -*-
"""候选低点（因果、无前视）事件研究 —— TICK 层特征 + 前向结果

候选低点定义（全部只用到 t 及之前的数据）：
  t 落在 06:45–10:30，t 的 1 分钟低点 == 最近 30 分钟最低，且自最近 30 分钟最高价回撤 ≥ DROP 点。
特征分层：
  S1（t+15 可判定，实时预判层）/ S2（t+45 可判定，确认层）
结果：自候选低点起 30/60/120 分钟的最大上行（MFE）与最大逆向（MAE）。
"""
import csv, json, sys, statistics as stats
from pathlib import Path
from collections import OrderedDict

RAW = Path("/Users/zhijiebian/Documents/MyDoc/Finance/Current/MotiveWave_OrderFlow_Data/Raw")
sys.path.insert(0, '/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools')
from py_lib.mw_gzip import open_text

DROP = 8.0          # 自 30 分钟高点回撤门槛（ES 点）
SEP = 25 * 60       # 相邻候选低点最小间隔（秒）
T0_MIN, T1_MIN = 6 * 3600 + 45 * 60, 10 * 3600 + 30 * 60


def _pt(ms):
    return int(int(ms) // 1000 - 7 * 3600) % 86400


def hms(t):
    return "%02d:%02d" % (t // 3600, (t % 3600) // 60)


def load(day):
    for name in ("ES_%s_TICKS.csv.gz", "ES_%s_TICKS.csv"):
        f = RAW / (name % day.replace('-', ''))
        if f.exists():
            break
    else:
        return None
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
            if v <= 0 or t > 15 * 3600:
                continue
            s = (r[3] or '').upper()
            rows.append((t, px, v, 1 if s == 'ASK' else (-1 if s == 'BID' else 0)))
    return rows


def minute_bars(rows):
    """{minute_start: (o,h,l,c,vol,net)}"""
    b = OrderedDict()
    for t, px, v, sg in rows:
        k = t // 60 * 60
        d = b.get(k)
        if d is None:
            b[k] = [px, px, px, px, v, sg * v]
        else:
            if px > d[1]:
                d[1] = px
            if px < d[2]:
                d[2] = px
            d[3] = px; d[4] += v; d[5] += sg * v
    return b


def zone_stats(rows, t_a, t_b, lo_px, zone=0.75):
    rs = [x for x in rows if t_a <= x[0] < t_b and x[1] <= lo_px + zone]
    bv = sum(x[2] for x in rs if x[3] > 0)
    sv = sum(x[2] for x in rs if x[3] < 0)
    big = [x for x in rs if x[2] >= 20]
    b50 = [x for x in rs if x[2] >= 50]
    imb = [x[3] > 0 for x in rs]
    return {"vol": bv + sv, "net": bv - sv, "ratio": (bv / (bv + sv)) if bv + sv else None,
            "n": len(rs),
            "big_n": len(big), "big_buy": sum(x[2] for x in big if x[3] > 0),
            "big_sell": sum(x[2] for x in big if x[3] < 0),
            "big_max_buy": max([x[2] for x in big if x[3] > 0], default=0),
            "b50_n": len(b50), "b50_net": sum(x[2] * x[3] for x in b50),
            "first": hms(min(x[0] for x in rs)) if rs else None,
            "last": hms(max(x[0] for x in rs)) if rs else None,
            "span_min": round((max(x[0] for x in rs) - min(x[0] for x in rs)) / 60, 1) if rs else 0}


def phase(rows, t_a, t_b):
    rs = [x for x in rows if t_a <= x[0] < t_b]
    bv = sum(x[2] for x in rs if x[3] > 0)
    sv = sum(x[2] for x in rs if x[3] < 0)
    big = [x for x in rs if x[2] >= 20]
    b50 = [x for x in rs if x[2] >= 50]
    return {"vol": bv + sv, "net": bv - sv, "ratio": (bv / (bv + sv)) if bv + sv else None,
            "big_net": sum(x[2] * x[3] for x in big), "big_max_buy": max([x[2] for x in big if x[3] > 0], default=0),
            "b50_net": sum(x[2] * x[3] for x in b50),
            "hi": max((x[1] for x in rs), default=None), "lo": min((x[1] for x in rs), default=None),
            "open": rs[0][1] if rs else None, "close": rs[-1][1] if rs else None}


def vwap_series(rows):
    """分钟末的 running VWAP（自 00:00 累计）"""
    out = OrderedDict()
    pv = v = 0.0
    cur = None
    for t, px, q, _ in rows:
        k = t // 60 * 60
        pv += px * q; v += q
        out[k] = pv / v if v else px
    return out


def scan_day(day, mode='low'):
    rows = load(day)
    if not rows:
        return None
    bars = minute_bars(rows)
    vw = vwap_series(rows)
    mins = sorted(bars)
    idx = {k: i for i, k in enumerate(mins)}
    cands = []
    last_t, last_ext = -10 ** 9, None
    for k in mins:
        if not (T0_MIN <= k <= T1_MIN):
            continue
        i = idx[k]
        w = [bars[mins[j]] for j in range(max(0, i - 30), i + 1)]
        if not w:
            continue
        if mode == 'low':
            ext = bars[k][2]; ref = max(x[1] for x in w)
            ok = (ext == min(x[2] for x in w)) and (ref - ext >= DROP)
        else:
            ext = bars[k][1]; ref = min(x[2] for x in w)
            ok = (ext == max(x[1] for x in w)) and (ext - ref >= DROP)
        if not ok:
            continue
        # 去重（因果口径）：间隔足够远，或「更极端的低点/更高的高点」且间隔 ≥5 分钟
        deeper = (last_ext is None) or (ext < last_ext if mode == 'low' else ext > last_ext)
        if (k - last_t >= SEP) or (deeper and k - last_t >= 300):
            last_t, last_ext = k, ext
            cands.append((k, ext))
    out = []
    for k, ext in cands:
        r = {"day": day, "mode": mode, "t": hms(k), "ext": ext}
        # ── S1：t+15 可判定 ──
        into = phase(rows, k - 1800, k)             # 低点前 30 分钟
        r["s1_into_net"] = into["net"]
        r["s1_into_ratio"] = into["ratio"]
        r["s1_into_big_net"] = into["big_net"]
        r["s1_into_b50_net"] = into["b50_net"]
        at = phase(rows, k, k + 900)                # 低点后 0–15 分钟
        r["s1_at_net"] = at["net"]
        r["s1_at_ratio"] = at["ratio"]
        r["s1_at_vol"] = at["vol"]
        r["s1_at_big_net"] = at["big_net"]
        r["s1_at_big_max_buy"] = at["big_max_buy"]
        r["s1_at_b50_net"] = at["b50_net"]
        z = zone_stats(rows, k - 1800, k + 900, ext)
        r["s1_zone_span"] = z["span_min"]
        r["s1_zone_vol"] = z["vol"]
        r["s1_zone_net"] = z["net"]
        r["s1_zone_ratio"] = z["ratio"]
        r["s1_zone_big_net"] = z["big_buy"] - z["big_sell"]
        r["s1_zone_big_max_buy"] = z["big_max_buy"]
        px_so_far = [x[1] for x in rows if x[0] <= k + 900]
        if px_so_far:
            hi_, lo_ = max(px_so_far), min(px_so_far)
            r["s1_pos_pct"] = (ext - lo_) / (hi_ - lo_) if hi_ > lo_ else 0.0
            r["s1_drop_from_hi"] = hi_ - ext
        # ── S2：t+45 可判定 ──
        mid = phase(rows, k + 900, k + 2700)        # 低点后 15–45 分钟
        r["s2_mid_net"] = mid["net"]
        r["s2_mid_ratio"] = mid["ratio"]
        r["s2_mid_big_net"] = mid["big_net"]
        r["s2_mid_b50_net"] = mid["b50_net"]
        fwd45 = phase(rows, k, k + 2700)
        r["s2_maxrev_45"] = ext - fwd45["lo"] if fwd45["lo"] is not None else None   # 45 分钟内最大逆向
        r["s2_up_45"] = fwd45["hi"] - ext if fwd45["hi"] is not None else None
        # VWAP 收复（60 分钟内首次价格 > 当日 VWAP 且其后不回破 5 分钟以上）
        rec = None
        for j in range(idx[k], min(len(mins), idx[k] + 61)):
            m = mins[j]
            if bars[m][3] > vw.get(m, 1e9) and m >= k:
                rec = m - k
                break
        r["s2_vwap_reclaim_min"] = rec
        # ── 结果 ──
        for h in (30, 60, 120):
            seg = [x for x in rows if k < x[0] <= k + h * 60]
            if not seg:
                continue
            hi_ = max(x[1] for x in seg); lo_ = min(x[1] for x in seg)
            r["mfe_%d" % h] = hi_ - ext
            r["mae_%d" % h] = ext - lo_
            r["close_%d" % h] = seg[-1][1] - ext
        out.append(r)
    return out


if __name__ == '__main__':
    days = sorted({f.name.split('_')[1][:8] for f in RAW.glob('ES_*_TICKS.csv*')})
    days = ["%s-%s-%s" % (d[:4], d[4:6], d[6:]) for d in days]
    res = {"low": [], "high": []}
    for d in days:
        for mode in ('low', 'high'):
            r = scan_day(d, mode)
            if r:
                res[mode].extend(r)
        print('scanned', d, 'cands', len(res['low']), len(res['high']), flush=True)
    Path('/tmp/base_tick_scan.json').write_text(json.dumps(res, ensure_ascii=False, default=str))

    def summarize(items, label):
        print('\n===', label, 'n =', len(items))
        for key, cmp_, th in [("s1_zone_net", '>', 0), ("s1_at_net", '>', 0), ("s1_into_net", '>', 0),
                              ("s2_mid_net", '>', 0), ("s2_mid_b50_net", '>=', 0)]:
            vals = [x.get(key) for x in items if x.get(key) is not None]
            hit = [x for x in vals if (x > th if cmp_ == '>' else x >= th)]
            print('  %-16s 命中 %3d/%3d = %.0f%%' % (key, len(hit), len(vals), 100 * len(hit) / max(1, len(vals))))
        for key in ("mfe_60", "mae_60", "mfe_120", "mae_120"):
            vals = sorted(x[key] for x in items if x.get(key) is not None)
            if vals:
                print('  %-16s 中位 %.1f  25%% %.1f  75%% %.1f  max %.1f' % (
                    key, stats.median(vals), vals[len(vals) // 4], vals[3 * len(vals) // 4], vals[-1]))
    summarize(res['low'], '候选低点')
    summarize(res['high'], '候选高点')
