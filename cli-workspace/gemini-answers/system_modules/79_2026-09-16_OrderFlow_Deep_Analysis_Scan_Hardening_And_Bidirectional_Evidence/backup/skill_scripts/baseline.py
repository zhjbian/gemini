# -*- coding: utf-8 -*-
"""order-flow baseline v1.0 —— LAR（低位吸收反转）/ HDR（镜像高位派发）

设计原则
  ① 因果、无前视：候选点与所有特征只用 t 及之前的数据；分层给出「可判定时刻」。
  ② 阈值来自样本内事件研究（2026-08-16 ~ 2026-09-15，27 个交易日，候选低点 184 / 候选高点 175），
     每条判据都带实测提升（条件成功率 − 基准成功率），不做无依据的断言。
  ③ 反例必须可判（NEG 形态成功率 0%）——负对照是本 baseline 的一部分。
  ④ 镜像对称：高位派发（HDR）用同一套逻辑取反，独立验证。

CLI
  # 单点评估（真实使用：给定你认定的候选低点时刻/价格）
  python3 baseline.py --date 2026-09-14 --at 07:54 --px 7664.00
  # 事件研究 / 重新标定
  python3 baseline.py --scan --emit-spec /path/spec.json --emit-json /path/scan.json
  # 列出某日全部候选低点
  python3 baseline.py --date 2026-09-15 --list
"""
from __future__ import annotations
import argparse, csv, json, sys, statistics as st
from pathlib import Path
from collections import OrderedDict

RAW = Path("/Users/zhijiebian/Documents/MyDoc/Finance/Current/MotiveWave_OrderFlow_Data/Raw")
SKILL = Path(__file__).resolve().parent
CACHE = SKILL.parent / "cache" / "dom_minutes"
sys.path.insert(0, '/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools')
from py_lib.mw_gzip import open_text

VERSION = "LAR/HDR v1.0"
# ── 触发参数 ──
DROP = 8.0            # 自 30 分钟高点（低点）/ 低点（高点）的回撤门槛（ES 点）
LOOKBACK = 30 * 60    # 新极值回看窗口（秒）
SEP = 25 * 60         # 同波段去重间隔（秒）
SEP2 = 5 * 60         # 出现更极端极值时的允许间隔（秒）
T0_MIN, T1_MIN = 6 * 3600 + 45 * 60, 10 * 3600 + 30 * 60
ZONE = 0.75           # 低点区宽度（点）
BIG = 20.0            # 大单门槛（手）
BIG_INST = 100.0      # 机构级单笔门槛（手）
ZONE_RATIO = 0.51     # 低点区买占比门槛

# ── 判据定义（含样本内实测提升，单位 pt = 百分点；n = 命中候选数）──
SPEC = OrderedDict([
    ("version", VERSION),
    ("sample", {"from": "2026-08-16", "to": "2026-09-15", "sessions": 27,
                "cand_low": 184, "cand_high": 175,
                "success_def_low": "自低点 60 分钟内最大上行 mfe60 ≥ 15 点 且 最大逆向 mae60 ≤ 5 点",
                "success_def_high": "自高点 60 分钟内最大下行 mae60 ≥ 15 点 且 最大上行 mfe60 ≤ 5 点",
                "base_low": 0.185, "base_high": 0.229}),
    ("trigger", {"desc": "1 分钟极值创 30 分钟新极值 且 自 30 分钟反向极值回撤 ≥ %.0f 点" % DROP,
                 "drop": DROP, "lookback_min": 30, "window": "06:45–10:30",
                 "dedup": "间隔 ≥25 分钟，或出现更极端极值且间隔 ≥5 分钟"}),
    ("layers", OrderedDict([
        ("P 预判层（低点后 15 分钟可判定）", OrderedDict([
            ("P1 低点区净买", {"测": "低点区（≤低点+0.75）净 Delta > 0 且买占比 ≥ 0.51",
                            "实测": "n=11 · 27.3% · +8.8pt"}),
            ("P2 低点后净买", {"测": "低点后 0–15 分钟净 Delta > 0",
                            "实测": "n=78 · 28.2% · +9.7pt"}),
            ("P3 机构级出手", {"测": "低点后 0–15 分钟出现 ≥100 手主动买单",
                            "实测": "n=42 · 26.2% · +7.7pt"}),
            ("P4 位置", {"测": "低点在当日截至 t+15 区间的分位 ≤ 0.20",
                        "实测": "n=81 · 23.5% · +5.0pt"}),
        ])),
        ("V 验证层（低点后 45 分钟可判定）", OrderedDict([
            ("V1 低点未被有效跌破 ★", {"测": "低点后 45 分钟内最大逆向 ≤ 5 点",
                                   "实测": "n=85 · 40.0% · +21.5pt（最强单判据）"}),
            ("V2 净买延续", {"测": "低点后 15–45 分钟净 Delta > 0",
                          "实测": "n=103 · 22.3% · +3.9pt"}),
            ("V3 大额不净卖", {"测": "低点后 15–45 分钟 ≥50 手单净额 ≥ 0",
                           "实测": "n=104 · 20.2% · +1.7pt"}),
        ])),
        ("C 右侧确认层（低点后 60 分钟；DOM 需盘口快照）", OrderedDict([
            ("C1 收复 VWAP", {"测": "60 分钟内价格站上当日累计 VWAP",
                           "实测": "n=50 · 20.0% · +1.5pt"}),
            ("C2 上方无贴价卖墙 ★DOM", {"测": "0–45 分钟内无「距 mid ≤10 ticks 且 ≥100 手」卖墙",
                                     "实测": "n=14 · 28.6% · +13.2pt"}),
            ("C3 下方有贴价买墙 DOM", {"测": "0–45 分钟内出现「距 mid ≤10 ticks 且 ≥80 手」买墙",
                                    "实测": "n=40 · 17.5% · +2.1pt"}),
            ("C4 全盘挂单转买优 DOM", {"测": "0–45 分钟内全盘买/卖挂单比曾 ≥1.0",
                                   "实测": "n=38 · 21.1% · +5.7pt"}),
        ])),
    ])),
    ("verdict_rules", OrderedDict([
        ("HIT-多头", "P≥2 且 V1 且 V2"),
        ("WATCH", "V1 且（V2 或 P≥2）"),
        ("AVOID-多头（反例）", "低点区净卖 且 低点后净卖 且 15–45 分钟净卖（NEG 三条）"),
        ("其他", "中性 / 不交易"),
    ])),
    ("measured", {
        "base_low": 0.185, "base_high": 0.229,
        "low": {"n": 184, "HIT": {"n": 26, "rate": 0.577, "lift_pt": 39.2, "recall": 0.441},
                "WATCH": {"n": 32, "rate": 0.375, "lift_pt": 19.0, "recall": 0.353},
                "AVOID-反例": {"n": 52, "rate": 0.077}, "NEUTRAL": {"n": 74, "rate": 0.041},
                "V1_only": {"n": 85, "rate": 0.40, "recall": 1.0},
                "V1+V2": {"n": 47, "rate": 0.489, "recall": 0.676},
                "P>=2": {"n": 65, "rate": 0.292}},
        "high": {"n": 175, "HIT": {"n": 34, "rate": 0.559, "lift_pt": 33.0, "recall": 0.475},
                 "WATCH": {"n": 44, "rate": 0.386, "lift_pt": 15.8, "recall": 0.425},
                 "AVOID-反例": {"n": 40, "rate": 0.025}, "NEUTRAL": {"n": 57, "rate": 0.053},
                 "V1+V2": {"n": 66, "rate": 0.50, "recall": 0.825}},
        "dom_subset_low": {"n": 52, "base": 0.154,
                           "C2_上方无贴价卖墙": {"n": 14, "rate": 0.286, "lift_pt": 13.2},
                           "C2+C3+C4": {"n": 12, "rate": 0.333, "lift_pt": 17.9}},
        "anchor_cases": [
            {"case": "2026-09-14 07:54 @7664.00（真反转）", "verdict": "HIT",
             "evidence": "P2/P3/P4 ✓（atNet +1,420、机构单 257 手、pos 0.08）；V1/V2/V3 ✓（maxrev 1.8、midNet +2,992、b50 +494）；C 全 ✓（DOM 卖墙 0 分钟、买墙 3 分钟、全盘比 max 1.47）",
             "outcome": "mfe60 +42.5 / mae60 +1.8"},
            {"case": "2026-09-15 07:50 @7648.50（假反弹）", "verdict": "AVOID-反例",
             "evidence": "低点区净卖 −1,439、低点后净卖 −593、15–45m 净卖 −509（反例三条全中）；C 全 ✗（DOM 卖墙 6 分钟 @7656.25、买墙 0 分钟、全盘比 max 0.98）",
             "outcome": "mfe60 +11.2 / mae60 +5.0"},
        ],
    }),
    ("caveats", [
        "样本仅 27 个交易日、真反转样本 34 例（低点）/ 40 例（高点）：置信区间宽，阈值属「初值」。",
        "案例式推断中「越跌越买（低点前 30 分钟净买）」在样本内为负提升（13.0% vs 基准 18.5%），已从判据降级为 context，不作闸门。",
        "「低点区成交量大」在样本内为负提升（≥15k 手 → 9.8%）：放量不构成承接证据，方向（符号）才是。",
        "maxrev45≤5（V1）是最强判据，但它在时间上最晚（t+45）：P 层仅用于「提前关注」，不可单独作为入场依据。",
        "域外有效性未验证（仅 2026-08-16~09-15 单一市场状态）；建议每周用 --scan 重跑并把结果写入版本记录。",
    ]),
])


# ── 数据加载 ────────────────────────────────────────────────────────────
def _pt(ms):
    return int(int(ms) // 1000 - 7 * 3600) % 86400


def hms(t):
    return "%02d:%02d" % (t // 3600, (t % 3600) // 60)


def sec(hm):
    h, m = str(hm).split(':')[:2]
    return int(h) * 3600 + int(m) * 60


def load_ticks(day):
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


def dom_series(day):
    p = CACHE / ("ES_%s.json" % day.replace('-', ''))
    if not p.exists():
        return None
    try:
        return json.load(open(p))['series']
    except Exception:
        return None


def dom_features(day, t_sec, minutes=45):
    s = dom_series(day)
    if not s:
        return {"available": False}
    t0 = t_sec // 60
    sel = [x for x in s if t0 <= x['min'] <= t0 + minutes]
    if len(sel) < 10:
        return {"available": False, "cover": len(sel)}
    ask_near = [x for x in sel if x['wall_ask']['dist'] is not None
                and x['wall_ask']['dist'] <= 10 and x['wall_ask']['sz'] >= 100]
    bid_near = [x for x in sel if x['wall_bid']['dist'] is not None
                and x['wall_bid']['dist'] <= 10 and x['wall_bid']['sz'] >= 80]
    imb = [x['imb5'] for x in sel if x['imb5'] is not None]
    tr = [(x['tot_bid'] / x['tot_ask']) if x['tot_ask'] else None for x in sel]
    tr = [v for v in tr if v]
    return {"available": True, "cover": len(sel),
            "ask_near_min": len(ask_near), "ask_near_sz": (sum(x['wall_ask']['sz'] for x in ask_near) / len(ask_near)) if ask_near else 0,
            "ask_near_px": ask_near[0]['wall_ask']['px'] if ask_near else None,
            "bid_near_min": len(bid_near), "bid_near_sz": (sum(x['wall_bid']['sz'] for x in bid_near) / len(bid_near)) if bid_near else 0,
            "bid_near_px": bid_near[0]['wall_bid']['px'] if bid_near else None,
            "imb5_mean": (sum(imb) / len(imb)) if imb else None,
            "tot_ratio_max": max(tr) if tr else None}


# ── 特征计算 ────────────────────────────────────────────────────────────
def phase(rows, a, b):
    rs = [x for x in rows if a <= x[0] < b]
    bv = sum(x[2] for x in rs if x[3] > 0)
    sv = sum(x[2] for x in rs if x[3] < 0)
    big = [x for x in rs if x[2] >= BIG]
    b50 = [x for x in rs if x[2] >= 50]
    return {"vol": bv + sv, "net": bv - sv, "ratio": (bv / (bv + sv)) if bv + sv else None,
            "big_net": sum(x[2] * x[3] for x in big),
            "big_buy": sum(x[2] for x in big if x[3] > 0), "big_sell": sum(x[2] for x in big if x[3] < 0),
            "big_max_buy": max([x[2] for x in big if x[3] > 0], default=0),
            "big_max_sell": max([x[2] for x in big if x[3] < 0], default=0),
            "b50_net": sum(x[2] * x[3] for x in b50), "n": len(rs),
            "hi": max((x[1] for x in rs), default=None), "lo": min((x[1] for x in rs), default=None),
            "open": rs[0][1] if rs else None, "close": rs[-1][1] if rs else None}


def zone(rows, a, b, ext, side='low'):
    rs = [x for x in rows if a <= x[0] < b and (x[1] <= ext + ZONE if side == 'low' else x[1] >= ext - ZONE)]
    bv = sum(x[2] for x in rs if x[3] > 0)
    sv = sum(x[2] for x in rs if x[3] < 0)
    big = [x for x in rs if x[2] >= BIG]
    return {"vol": bv + sv, "net": bv - sv, "ratio": (bv / (bv + sv)) if bv + sv else None,
            "big_net": sum(x[2] * x[3] for x in big),
            "big_max_buy": max([x[2] for x in big if x[3] > 0], default=0),
            "span_min": round((max(x[0] for x in rs) - min(x[0] for x in rs)) / 60, 1) if rs else 0,
            "first": hms(min(x[0] for x in rs)) if rs else None,
            "last": hms(max(x[0] for x in rs)) if rs else None}


def minute_bars(rows):
    b = OrderedDict()
    for t, px, v, sg in rows:
        k = t // 60 * 60
        d = b.get(k)
        if d is None:
            b[k] = [px, px, px, px, v, sg * v]
        else:
            d[1] = max(d[1], px); d[2] = min(d[2], px); d[3] = px; d[4] += v; d[5] += sg * v
    return b


def running_vwap(rows):
    out = OrderedDict(); pv = v = 0.0
    for t, px, q, _ in rows:
        k = t // 60 * 60; pv += px * q; v += q
        out[k] = pv / v if v else px
    return out


def candidates(rows, mode='low'):
    """因果候选极值点 [(t_sec, ext_px)]"""
    bars = minute_bars(rows); mins = sorted(bars); idx = {k: i for i, k in enumerate(mins)}
    out = []; last_t, last_ext = -10 ** 9, None
    for k in mins:
        if not (T0_MIN <= k <= T1_MIN):
            continue
        i = idx[k]
        w = [bars[mins[j]] for j in range(max(0, i - LOOKBACK // 60), i + 1)]
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
        deeper = (last_ext is None) or (ext < last_ext if mode == 'low' else ext > last_ext)
        if (k - last_t >= SEP) or (deeper and k - last_t >= SEP2):
            last_t, last_ext = k, ext
            out.append((k, ext))
    return out


def features(rows, t_sec, ext, mode='low', with_dom=True, day=None):
    vw = running_vwap(rows)
    f = {"mode": mode, "t": hms(t_sec), "ext": ext}
    into = phase(rows, t_sec - 1800, t_sec)
    at = phase(rows, t_sec, t_sec + 900)
    mid = phase(rows, t_sec + 900, t_sec + 2700)
    z = zone(rows, t_sec - 1800, t_sec + 900, ext, mode)
    f.update({"into_net": into["net"], "into_ratio": into["ratio"], "into_big_net": into["big_net"],
              "at_net": at["net"], "at_ratio": at["ratio"], "at_vol": at["vol"],
              "at_big_net": at["big_net"], "at_big_max_buy": at["big_max_buy"], "at_big_max_sell": at["big_max_sell"],
              "mid_net": mid["net"], "mid_ratio": mid["ratio"], "mid_big_net": mid["big_net"],
              "mid_b50_net": mid["b50_net"],
              "zone_net": z["net"], "zone_ratio": z["ratio"], "zone_vol": z["vol"], "zone_span": z["span_min"],
              "zone_big_net": z["big_net"], "zone_big_max_buy": z["big_max_buy"]})
    px_so_far = [x[1] for x in rows if x[0] <= t_sec + 900]
    if px_so_far:
        hi_, lo_ = max(px_so_far), min(px_so_far)
        f["pos_pct"] = (ext - lo_) / (hi_ - lo_) if hi_ > lo_ else 0.0
    fw = phase(rows, t_sec, t_sec + 2700)
    f["maxrev_45"] = (ext - fw["lo"]) if (mode == 'low' and fw["lo"] is not None) else ((fw["hi"] - ext) if fw["hi"] is not None else None)
    f["up_45"] = (fw["hi"] - ext) if fw["hi"] is not None else None
    rec = None
    for m in range(t_sec // 60 * 60, t_sec + 3600 + 1, 60):
        px = [x[1] for x in rows if x[0] // 60 * 60 == m]
        if not px:
            continue
        last = px[-1]
        if (last > vw.get(m, 1e9)) if mode == 'low' else (last < vw.get(m, 1e9)):
            rec = m - t_sec
            break
    f["vwap_reclaim_min"] = rec
    if with_dom and day:
        f["dom"] = dom_features(day, t_sec)
    for h in (30, 60, 120):
        seg = [x for x in rows if t_sec < x[0] <= t_sec + h * 60]
        if seg:
            hi_ = max(x[1] for x in seg); lo_ = min(x[1] for x in seg)
            f["mfe_%d" % h] = hi_ - ext; f["mae_%d" % h] = ext - lo_
    return f


# ── 判定 ────────────────────────────────────────────────────────────────
def judge(f, mode='low'):
    """返回 (verdict, P命中, V命中, C命中, neg 命中)"""
    if mode == 'low':
        P = OrderedDict([
            ("P1", (f.get("zone_net") or 0) > 0 and (f.get("zone_ratio") or 0) >= ZONE_RATIO),
            ("P2", (f.get("at_net") or 0) > 0),
            ("P3", (f.get("at_big_max_buy") or 0) >= BIG_INST),
            ("P4", (f.get("pos_pct") if f.get("pos_pct") is not None else 1) <= 0.20),
        ])
        V = OrderedDict([("V1", (f.get("maxrev_45") if f.get("maxrev_45") is not None else 99) <= 5),
                         ("V2", (f.get("mid_net") or 0) > 0),
                         ("V3", (f.get("mid_b50_net") if f.get("mid_b50_net") is not None else -1) >= 0)])
        d = f.get("dom") or {}
        C = OrderedDict([("C1", f.get("vwap_reclaim_min") is not None and f["vwap_reclaim_min"] <= 3600),
                         ("C2", (d.get("ask_near_min") == 0) if d.get("available") else None),
                         ("C3", (d.get("bid_near_min", 0) >= 1) if d.get("available") else None),
                         ("C4", ((d.get("tot_ratio_max") or 0) >= 1.0) if d.get("available") else None)])
        NEG = OrderedDict([("低点区净卖", (f.get("zone_net") or 0) < 0),
                           ("低点后净卖", (f.get("at_net") or 0) < 0),
                           ("15–45m 净卖", (f.get("mid_net") or 0) < 0)])
    else:
        P = OrderedDict([
            ("P1", (f.get("zone_net") or 0) < 0 and (f.get("zone_ratio") if f.get("zone_ratio") is not None else 1) <= 0.49),
            ("P2", (f.get("at_net") or 0) < 0),
            ("P3", (f.get("at_big_max_sell") or 0) >= BIG_INST),
            ("P4", (f.get("pos_pct") if f.get("pos_pct") is not None else 0) >= 0.80),
        ])
        V = OrderedDict([("V1", (f.get("maxrev_45") if f.get("maxrev_45") is not None else 99) <= 5),
                         ("V2", (f.get("mid_net") or 0) < 0),
                         ("V3", (f.get("mid_b50_net") if f.get("mid_b50_net") is not None else 1) <= 0)])
        d = f.get("dom") or {}
        C = OrderedDict([("C1", f.get("vwap_reclaim_min") is not None and f["vwap_reclaim_min"] <= 3600),
                         ("C2", (d.get("bid_near_min") == 0) if d.get("available") else None),
                         ("C3", (d.get("ask_near_min", 0) >= 1) if d.get("available") else None),
                         ("C4", ((d.get("tot_ratio_max") or 9) <= 1.0) if d.get("available") else None)])
        NEG = OrderedDict([("高点区净买", (f.get("zone_net") or 0) > 0),
                           ("高点后净买", (f.get("at_net") or 0) > 0),
                           ("15–45m 净买", (f.get("mid_net") or 0) > 0)])
    np_ = sum(1 for v in P.values() if v); nv = sum(1 for v in V.values() if v)
    if V["V1"] and V["V2"] and np_ >= 2:
        verdict = "HIT"
    elif all(NEG.values()):
        # 反例形态：样本内 n=16 / 成功率 0%（低点）、n=13 / 0%（高点）⇒ 优先于 WATCH
        verdict = "AVOID-反例"
    elif V["V1"] and (V["V2"] or np_ >= 2):
        verdict = "WATCH"
    else:
        verdict = "NEUTRAL"
    return verdict, P, V, C, NEG


# ── CLI ────────────────────────────────────────────────────────────────
def _fmt(v, nd=2, signed=True):
    if v is None:
        return "—"
    return ("{:+,." + str(nd) + "f}" if signed else "{:." + str(nd) + "f}").format(v)


def evaluate_day(day, at=None, px=None, mode='low', verbose=True):
    rows = load_ticks(day)
    if not rows:
        print("无 tick 数据:", day); return None
    cands = [(sec(at), px)] if at else candidates(rows, mode)
    if px is not None and at:
        cands = [(sec(at), px)]
    out = []
    for t_sec, ext in cands:
        f = features(rows, t_sec, ext, mode, with_dom=True, day=day)
        verdict, P, V, C, NEG = judge(f, mode)
        out.append({"day": day, "t": hms(t_sec), "ext": ext, "verdict": verdict,
                    "P": {k: bool(v) for k, v in P.items()}, "V": {k: bool(v) for k, v in V.items()},
                    "C": {k: (None if v is None else bool(v)) for k, v in C.items()},
                    "NEG": {k: bool(v) for k, v in NEG.items()}, "features": f})
        if verbose:
            print("\n%s %s  极值 %.2f   →  %s" % (day, hms(t_sec), ext, verdict))
            print("  P 预判(t+15) : " + "  ".join("%s=%s" % (k, "✓" if v else "✗") for k, v in P.items())
                  + "   zoneNet=%s zoneRatio=%s atNet=%s bigMax=%s pos=%s" % (
                      _fmt(f.get("zone_net"), 0), _fmt(f.get("zone_ratio"), 3, False),
                      _fmt(f.get("at_net"), 0), _fmt(f.get("at_big_max_buy"), 0),
                      _fmt(f.get("pos_pct"), 2, False)))
            print("  V 验证(t+45) : " + "  ".join("%s=%s" % (k, "✓" if v else "✗") for k, v in V.items())
                  + "   maxrev45=%s midNet=%s b50=%s" % (_fmt(f.get("maxrev_45"), 1), _fmt(f.get("mid_net"), 0),
                                                         _fmt(f.get("mid_b50_net"), 0)))
            d = f.get("dom") or {}
            print("  C 确认(t+60) : " + "  ".join("%s=%s" % (k, ("n/a" if v is None else ("✓" if v else "✗"))) for k, v in C.items())
                  + ("   DOM覆盖=%d 分钟 卖墙%d分钟 买墙%d分钟 全盘比max=%s" % (
                      d.get("cover", 0), d.get("ask_near_min", 0), d.get("bid_near_min", 0),
                      _fmt(d.get("tot_ratio_max"), 2, False)) if d.get("available") else "   DOM 不可用"))
            print("  反例          : " + "  ".join("%s=%s" % (k, "✓" if v else "✗") for k, v in NEG.items()))
            if f.get("mfe_60") is not None:
                print("  后验(仅回看)  : mfe60=%s mae60=%s mfe120=%s" % (
                    _fmt(f.get("mfe_60"), 1), _fmt(f.get("mae_60"), 1), _fmt(f.get("mfe_120"), 1)))
    return out


def scan(days=None, mode='low', emit_json=None):
    fs = sorted({p.name.split('_')[1][:8] for p in RAW.glob('ES_*_TICKS.csv*')})
    days = days or ["%s-%s-%s" % (d[:4], d[4:6], d[6:]) for d in fs]
    res = []
    for d in days:
        rows = load_ticks(d)
        if not rows:
            continue
        for t_sec, ext in candidates(rows, mode):
            f = features(rows, t_sec, ext, mode, with_dom=True, day=d)
            v, P, V, C, NEG = judge(f, mode)
            res.append({"day": d, **{k: f.get(k) for k in (
                "t", "ext", "pos_pct", "zone_net", "zone_ratio", "zone_vol", "at_net", "at_big_max_buy",
                "at_big_max_sell", "mid_net", "mid_b50_net", "maxrev_45", "vwap_reclaim_min", "mfe_60", "mae_60",
                "mfe_120", "mae_120")},
                "verdict": v, "P_n": sum(P.values()), "V1": V["V1"], "V2": V["V2"], "V3": V["V3"],
                "NEG_all": all(NEG.values()),
                "dom_ok": (f.get("dom") or {}).get("available"),
                "dom_c2": (f.get("dom") or {}).get("ask_near_min"), "dom_c3": (f.get("dom") or {}).get("bid_near_min"),
                "dom_c4": (f.get("dom") or {}).get("tot_ratio_max")})
    if emit_json:
        Path(emit_json).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    # 汇总
    def ok(x):
        if mode == 'low':
            return x["mfe_60"] is not None and float(x["mfe_60"]) >= 15 and float(x["mae_60"]) <= 5
        return x["mae_60"] is not None and float(x["mae_60"]) >= 15 and float(x["mfe_60"]) <= 5
    for x in res:
        x["_ok"] = ok(x)
    n = len(res); base = sum(1 for x in res if x["_ok"]) / max(1, n)
    print('候选 n=%d ｜ 基准成功率 %.1f%%（%s）' % (n, 100 * base, VERSION))
    groups = OrderedDict([
        ("HIT", lambda x: x["verdict"] == "HIT"),
        ("WATCH", lambda x: x["verdict"] == "WATCH"),
        ("AVOID-反例", lambda x: x["verdict"] == "AVOID-反例"),
        ("NEUTRAL", lambda x: x["verdict"] == "NEUTRAL"),
        ("V1 only (maxrev≤5)", lambda x: x["V1"]),
        ("V1+V2", lambda x: x["V1"] and x["V2"]),
        ("P≥2", lambda x: x["P_n"] >= 2),
        ("P≥2 且 V1 且 V2", lambda x: x["P_n"] >= 2 and x["V1"] and x["V2"]),
        ("DOM 全过(C2+C3+C4)", lambda x: x["dom_ok"] and x["dom_c2"] == 0 and (x["dom_c3"] or 0) >= 1
         and ((x["dom_c4"] or 0) >= 1.0 if mode == 'low' else (x["dom_c4"] is not None and x["dom_c4"] <= 1.0))),
    ])
    print('%-24s %5s %8s %10s %8s' % ('组', 'n', '成功率', '提升', '召回'))
    for name, fn in groups.items():
        sel = [x for x in res if fn(x)]
        if not sel:
            print('%-24s %5d' % (name, 0)); continue
        r = sum(1 for x in sel if x["_ok"]) / len(sel)
        tp = sum(1 for x in sel if x["_ok"]); tot = sum(1 for x in res if x["_ok"])
        print('%-24s %5d %7.1f%% %+9.1fpt %7.1f%%' % (name, len(sel), 100 * r, 100 * (r - base), 100 * tp / max(1, tot)))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date'); ap.add_argument('--at'); ap.add_argument('--px', type=float)
    ap.add_argument('--mode', default='low', choices=['low', 'high'])
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--scan', action='store_true')
    ap.add_argument('--emit-spec'); ap.add_argument('--emit-json')
    a = ap.parse_args()
    acted = False
    if a.emit_spec:
        Path(a.emit_spec).write_text(json.dumps(SPEC, ensure_ascii=False, indent=1))
        print('SPEC →', a.emit_spec); acted = True
    if a.scan:
        scan(mode=a.mode, emit_json=a.emit_json); return
    if a.date:
        evaluate_day(a.date, at=a.at, px=a.px, mode=a.mode, verbose=True); return
    if not acted:
        print(__doc__)


if __name__ == '__main__':
    main()
