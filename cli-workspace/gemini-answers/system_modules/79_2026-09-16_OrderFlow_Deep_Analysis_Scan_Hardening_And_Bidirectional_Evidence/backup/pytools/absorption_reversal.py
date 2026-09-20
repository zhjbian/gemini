#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""absorption_reversal —— 「吸收反转」（PAIR v1.1）判定器（★ 2026-09-15 新增）

用途：把 2026-09-14（低点真反转）/ 2026-09-15（低点假反弹）两个相反案例提炼的**对照模板**，
     做成可机检判定器，供 OrderFlow 侧产出契约字段、卖家系统机制 `AUTO_ABSORPTION_REVERSAL` 消费。

设计纪律（对齐 auto_mechanisms 的「机制不得自行计算指标」）：
  · 本模块 = OF 侧（生产端），卖家系统机制只读 `of_metrics['absorption_reversal']`，不重复计算。
  · 纯函数 + 无副作用：文件复算（回放/回测/测试）与滚动缓冲（实盘）共用同一套数学。

判定口径（与 baseline_templates_v1.json 一致）：
  候选低点：1 分钟低点创 30 分钟新低 且 自 30 分钟高点回撤 ≥ 8 点（06:45–10:30 PST）
  硬门槛  ：低点 ±15 分钟累计 Delta > 0（不过 = 不参与）
  投票    ：9 个决定性维度逐维判断「更像 A（真反转锚点）还是更像 B（假反弹锚点）」
            ≥ +6 → A 型（低点吸收）；≤ −6 → B 型（假反弹）；其余 不可判
  DOM 缺失时降级为 6 维投票（门槛不变，阈值等比例：need = ceil(6 * 6/9) = 4）
  镜像    ：高点派发 = 同一套逻辑整体取反（BEARISH 方向），保证双向通用。
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

RAW_DIR = Path("/Users/zhijiebian/Documents/MyDoc/Finance/Current/MotiveWave_OrderFlow_Data/Raw")
CACHE_DIR = Path(__file__).resolve().parent / "cache"
TEMPLATES_PATH = Path(__file__).resolve().parent / "absorption_reversal_templates_v1.json"

PAIR_VERSION = "PAIR v1.1"
DROP = 8.0                 # 自 30 分钟反向极值的回撤门槛（ES 点）
LOOKBACK_MIN = 30          # 新极值回看窗口（分钟）
SEP_SEC = 25 * 60          # 同波段去重间隔
SEP2_SEC = 5 * 60          # 出现更极端极值时的允许间隔
T0_SEC, T1_SEC = 6 * 3600 + 45 * 60, 10 * 3600 + 30 * 60
ZONE = 0.75                # 低点区宽度（点）
BIG = 20.0                 # 大单门槛（手）
TICK = 0.25

# 决定性维度（顺序即投票顺序；dom_* 为盘口维度，缺失时降级）
DECISIVE = ["into30_net", "cvd_delta_30m", "mid30_net", "next45_net", "zone_span",
            "dom_ask_near_min", "dom_bid_near_min", "dom_tot_max", "vwap_reclaim"]
DOM_DIMS = {"dom_ask_near_min", "dom_bid_near_min", "dom_tot_max"}
VOTE_THRESHOLD = 6         # 9 维全可用时的门槛
REQUIRED_AGE_SEC = 45 * 60  # 候选低点出现后至少 45 分钟才可判定（V/C 层可判时刻）
DECISION_TTL_SEC = 75 * 60  # 超过该时长不再对同一候选重复判定（避免陈旧触发）


# ── 基础工具 ─────────────────────────────────────────────────────────────
def _pt(ms: Any) -> int:
    """毫秒时间戳 → PST 当日秒数（与全系统口径一致：UTC-7）"""
    return int(int(ms) // 1000 - 7 * 3600) % 86400


def hms(sec: int) -> str:
    return "%02d:%02d" % (int(sec) // 3600, (int(sec) % 3600) // 60)


def sec_of(hm: str) -> int:
    h, m = str(hm).split(':')[:2]
    return int(h) * 3600 + int(m) * 60


# ── 模板 ────────────────────────────────────────────────────────────────
def load_templates(path: Optional[Path] = None) -> Dict[str, Any]:
    p = Path(path) if path else TEMPLATES_PATH
    with open(p, 'r', encoding='utf-8') as fh:
        return json.load(fh)


# ── 1 分钟 bar 与逐分钟盘口 ──────────────────────────────────────────────
def minute_bars_from_trades(trades: Sequence[Tuple[int, float, float, int]]) -> Dict[int, Dict[str, float]]:
    """trades = [(sec, px, vol, side_sign)] → {minute_start: {o,h,l,c,vol,net}}"""
    out: Dict[int, Dict[str, float]] = {}
    for t, px, vol, sg in trades:
        k = int(t) // 60 * 60
        d = out.get(k)
        if d is None:
            out[k] = {"o": px, "h": px, "l": px, "c": px, "vol": float(vol), "net": float(sg) * vol}
        else:
            if px > d["h"]:
                d["h"] = px
            if px < d["l"]:
                d["l"] = px
            d["c"] = px
            d["vol"] += vol
            d["net"] += float(sg) * vol
    return out


def detect_candidates(bars: Dict[int, Dict[str, float]], mode: str = 'low') -> List[Tuple[int, float]]:
    """因果候选极值点（与 skill 侧 baseline_pair 同口径）"""
    mins = sorted(bars)
    idx = {k: i for i, k in enumerate(mins)}
    out: List[Tuple[int, float]] = []
    last_t, last_ext = -10 ** 9, None
    for k in mins:
        if not (T0_SEC <= k <= T1_SEC):
            continue
        i = idx[k]
        win = [bars[mins[j]] for j in range(max(0, i - LOOKBACK_MIN), i + 1)]
        if not win:
            continue
        if mode == 'low':
            ext, ref = bars[k]["l"], max(x["h"] for x in win)
            ok = (ext == min(x["l"] for x in win)) and (ref - ext >= DROP)
        else:
            ext, ref = bars[k]["h"], min(x["l"] for x in win)
            ok = (ext == max(x["h"] for x in win)) and (ext - ref >= DROP)
        if not ok:
            continue
        deeper = (last_ext is None) or (ext < last_ext if mode == 'low' else ext > last_ext)
        if (k - last_t >= SEP_SEC) or (deeper and k - last_t >= SEP2_SEC):
            last_t, last_ext = k, ext
            out.append((k, ext))
    return out


def _phase(trades: Sequence[Tuple[int, float, float, int]], a: int, b: int) -> Dict[str, Any]:
    rs = [x for x in trades if a <= x[0] < b]
    bv = sum(x[2] for x in rs if x[3] > 0)
    sv = sum(x[2] for x in rs if x[3] < 0)
    return {"vol": bv + sv, "net": bv - sv, "n": len(rs),
            "ratio": (bv / (bv + sv)) if (bv + sv) else None}


def _running_vwap(trades: Sequence[Tuple[int, float, float, int]]) -> Dict[int, float]:
    out: Dict[int, float] = {}
    pv = v = 0.0
    for t, px, vol, _sg in trades:
        pv += px * vol
        v += vol
        out[int(t) // 60 * 60] = (pv / v) if v else px
    return out


# ── 逐分钟盘口画像（与 adam_dom_analysis 同口径的紧凑实现）──────────────
def dom_minutes_from_raw(day: str, t_from: int = 6 * 3600, t_to: int = 11 * 3600) -> List[Dict[str, Any]]:
    """扫描当日 DOM 原始文件 → 逐分钟盘口画像（mid / ±5 失衡 / 全盘比 / 双侧最大单档）"""
    import sys
    sys.path.insert(0, '/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools')
    from py_lib.mw_gzip import open_text
    f = RAW_DIR / ("ES_%s_DOM.csv.gz" % str(day).replace('-', ''))
    if not f.exists():
        f = RAW_DIR / ("ES_%s_DOM.csv" % str(day).replace('-', ''))
        if not f.exists():
            return []
    by_min: Dict[int, Dict[str, Any]] = {}
    cur, buf = None, []
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
            if t > t_to:
                break
            if t < t_from - 60:
                cur, buf = None, []
                continue
            if row[0] != cur:
                if buf:
                    prof = _dom_profile(buf)
                    if prof:
                        by_min[prof["min"]] = prof
                cur, buf = row[0], []
            try:
                buf.append((t, str(row[1]).upper(), float(row[3]), float(row[4])))
            except Exception:
                pass
    return [by_min[k] for k in sorted(by_min)]


def _dom_profile(buf: Sequence[Tuple[int, str, float, float]]) -> Optional[Dict[str, Any]]:
    bids = [(p, s) for _t, ty, p, s in buf if ty == 'BID']
    asks = [(p, s) for _t, ty, p, s in buf if ty == 'ASK']
    if len(bids) < 50 or len(asks) < 50:
        return None
    bb, ba = max(p for p, _ in bids), min(p for p, _ in asks)
    if bb >= ba:
        return None
    mid = (bb + ba) / 2.0
    band = 5 * TICK
    bs = sum(s for p, s in bids if abs(p - mid) <= band)
    as_ = sum(s for p, s in asks if abs(p - mid) <= band)
    wb = max(bids, key=lambda x: x[1])
    wa = max(asks, key=lambda x: x[1])
    tot_bid = sum(s for _, s in bids)
    tot_ask = sum(s for _, s in asks)
    return {"min": buf[0][0] // 60, "mid": mid,
            "imb5": ((bs - as_) / (bs + as_)) if (bs + as_) else None,
            "bid5": bs, "ask5": as_, "tot_bid": tot_bid, "tot_ask": tot_ask,
            "wall_bid": {"px": wb[0], "sz": wb[1], "dist": abs(mid - wb[0]) / TICK},
            "wall_ask": {"px": wa[0], "sz": wa[1], "dist": abs(wa[0] - mid) / TICK}}


# ── 特征向量 ────────────────────────────────────────────────────────────
def build_vector(trades: Sequence[Tuple[int, float, float, int]],
                 dom_minutes: Sequence[Dict[str, Any]],
                 t_sec: int, ext: float, mode: str = 'low',
                 now_sec: Optional[int] = None) -> Dict[str, Any]:
    v: Dict[str, Any] = {"t": hms(t_sec), "t_sec": int(t_sec), "ext": float(ext), "mode": mode}
    sgn = 1 if mode == 'low' else -1

    def flip(x: Optional[float]) -> Optional[float]:
        return None if x is None else sgn * float(x)

    into = _phase(trades, t_sec - 1800, t_sec)
    at15 = _phase(trades, t_sec, t_sec + 900)
    mid30 = _phase(trades, t_sec + 900, t_sec + 2700)
    next45 = _phase(trades, t_sec + 2700, t_sec + 5400)
    v["into30_net"] = flip(into["net"])
    v["at15_net"] = flip(at15["net"])
    v["at15_ratio"] = at15["ratio"]
    v["mid30_net"] = flip(mid30["net"])
    # 45–90 分钟窗口（next45）：**未满窗不得投票**（半窗会把它误算成 ~0，反向投给 B 模板）
    next45_ready = (now_sec is None) or (int(now_sec) >= t_sec + 5400)
    v["next45_ready"] = next45_ready
    v["next45_net"] = flip(next45["net"]) if next45_ready else None
    # 低点/高点区停留时长与成交量
    zone_a, zone_b = t_sec - 1800, t_sec + 900
    zrs = [x for x in trades if zone_a <= x[0] < zone_b and (x[1] <= ext + ZONE if mode == 'low' else x[1] >= ext - ZONE)]
    v["zone_span"] = round((max(x[0] for x in zrs) - min(x[0] for x in zrs)) / 60.0, 1) if zrs else 0.0
    v["zone_vol"] = sum(x[2] for x in zrs)
    # ±15 分钟累计 Delta（硬门槛；空头版取负，保证符号语义统一为「正向 = 支持该方向」）
    v["cvd_delta_30m"] = flip(sum(x[3] * x[2] for x in trades if t_sec - 900 <= x[0] <= t_sec + 900))
    # 45 分钟内最大逆向 / 最大顺向
    fw = [x for x in trades if t_sec < x[0] <= t_sec + 2700]
    if fw:
        hi = max(x[1] for x in fw)
        lo = min(x[1] for x in fw)
        v["maxrev45"] = (ext - lo) if mode == 'low' else (hi - ext)
        v["maxup45"] = (hi - ext) if mode == 'low' else (ext - lo)
    # VWAP 收复（≤60 分钟）
    vw = _running_vwap(trades)
    rec = None
    for m in range(t_sec // 60 * 60, t_sec + 3600 + 1, 60):
        px = [x[1] for x in trades if x[0] // 60 * 60 == m]
        if not px:
            continue
        last = px[-1]
        if (last > vw.get(m, 1e9)) if mode == 'low' else (last < vw.get(m, 1e9)):
            rec = m - t_sec
            break
    v["vwap_reclaim"] = rec
    # ── 盘口维度（0–45 分钟）──
    t0 = t_sec // 60
    sel = [x for x in dom_minutes if t0 <= x["min"] <= t0 + 45]
    if len(sel) >= 10:
        near_ask = [x for x in sel if x["wall_ask"]["dist"] <= 10 and x["wall_ask"]["sz"] >= 100]
        near_bid = [x for x in sel if x["wall_bid"]["dist"] <= 10 and x["wall_bid"]["sz"] >= 80]
        tr = [(x["tot_bid"] / x["tot_ask"]) if x["tot_ask"] else None for x in sel]
        tr = [t for t in tr if t]
        # 空头版镜像：上方（买墙）钉住 = 支持下行 ⇒ 交换两侧
        if mode == 'low':
            v["dom_ask_near_min"] = len(near_ask)
            v["dom_bid_near_min"] = len(near_bid)
            v["dom_tot_max"] = max(tr) if tr else None
        else:
            v["dom_ask_near_min"] = len(near_bid)     # 镜像：下方买墙 ⇒ 对下行是「反向阻挡」
            v["dom_bid_near_min"] = len(near_ask)     # 镜像：上方卖墙 ⇒ 对下行是「贴身压制」
            v["dom_tot_max"] = (1.0 / max(tr)) if tr and max(tr) else None
        v["dom_cover"] = len(sel)
        v["dom_available"] = True
    else:
        v["dom_cover"] = len(sel)
        v["dom_available"] = False
    return v


# ── 投票与判定 ──────────────────────────────────────────────────────────
def _vote(x: Dict[str, Any], a: Dict[str, Any], b: Dict[str, Any], key: str) -> int:
    if key == "vwap_reclaim":
        xa, xb, xv = a.get(key), b.get(key), x.get(key)
        fa, fb, fv = xa is not None, xb is not None, xv is not None
        if fa == fb:
            return 0
        return 1 if fv == fa else -1
    xv, av, bv = x.get(key), a.get(key), b.get(key)
    if xv is None or av is None or bv is None:
        return 0
    try:
        xv, av, bv = float(xv), float(av), float(bv)
    except Exception:
        return 0
    da, db = abs(xv - av), abs(xv - bv)
    if abs(da - db) < 1e-9:
        return 0
    return 1 if da < db else -1


def judge(x: Dict[str, Any], templates: Dict[str, Any], gate: bool = True) -> Dict[str, Any]:
    """返回 {score, n_dims, gate_ok, verdict, votes, direction}"""
    a = templates.get("A") or {}
    b = templates.get("B") or {}
    dom_ok = bool(x.get("dom_available"))
    n45_ok = bool(x.get("next45_ready", True))
    dims = [d for d in DECISIVE
            if (dom_ok or d not in DOM_DIMS) and (n45_ok or d != "next45_net")]
    votes = {d: _vote(x, a, b, d) for d in dims}
    score = sum(votes.values())
    need = VOTE_THRESHOLD if dom_ok else max(1, int(math.ceil(VOTE_THRESHOLD * len(dims) / float(len(DECISIVE)))))
    g = x.get("cvd_delta_30m")
    g = float(g) if g is not None else None
    gate_ok = (g is not None and g > 0) if gate else True
    if gate and not gate_ok:
        verdict = "不参与"
    elif score >= need:
        verdict = "A型"
    elif score <= -need:
        verdict = "B型"
    else:
        verdict = "不可判"
    mode = x.get("mode", 'low')
    direction = "BULLISH" if mode == 'low' else "BEARISH"
    if verdict == "A型" and direction == "BULLISH":
        action = "OPEN_BULLISH"
    elif verdict == "A型" and direction == "BEARISH":
        action = "OPEN_BEARISH"
    else:
        action = "NONE"
    return {"score": score, "n_dims": len(dims), "need": need, "gate_ok": gate_ok,
            "verdict": verdict, "votes": votes, "direction": direction, "action": action}


def evaluate_candidate(trades, dom_minutes, t_sec, ext, templates, mode='low',
                       now_sec: Optional[int] = None) -> Dict[str, Any]:
    v = build_vector(trades, dom_minutes, t_sec, ext, mode, now_sec=now_sec)
    j = judge(v, templates)
    out = dict(v)
    out.update(j)
    out["version"] = PAIR_VERSION
    return out


# ── 文件复算（回放 / 回测 / 测试）────────────────────────────────────────
def load_trades_from_raw(day: str, t_max: int = 13 * 3600) -> List[Tuple[int, float, float, int]]:
    """读原始 TICKS 文件 → [(sec, px, vol, side_sign)]（ASK=主动买 +1 / BID=主动卖 −1）"""
    import sys
    sys.path.insert(0, '/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools')
    from py_lib.mw_gzip import open_text
    f = RAW_DIR / ("ES_%s_TICKS.csv.gz" % str(day).replace('-', ''))
    if not f.exists():
        f = RAW_DIR / ("ES_%s_TICKS.csv" % str(day).replace('-', ''))
        if not f.exists():
            return []
    rows: List[Tuple[int, float, float, int]] = []
    with open_text(str(f), 'rt') as fh:
        rdr = csv.reader(fh)
        next(rdr, None)
        for r in rdr:
            if len(r) < 4:
                continue
            try:
                t = _pt(r[0]); px = float(r[1]); vol = float(r[2] or 0)
            except Exception:
                continue
            if vol <= 0 or t > t_max:
                continue
            s = (r[3] or '').upper()
            rows.append((t, px, vol, 1 if s == 'ASK' else (-1 if s == 'BID' else 0)))
    return rows


def evaluate_day(day: str, templates: Optional[Dict[str, Any]] = None,
                 mode: str = 'low', with_dom: bool = True) -> List[Dict[str, Any]]:
    """整天复算：全部因果候选极值点的判定（供回放/回测/测试）"""
    tpl = templates or load_templates()
    trades = load_trades_from_raw(day)
    if not trades:
        return []
    bars = minute_bars_from_trades(trades)
    dom = dom_minutes_from_raw(day) if with_dom else []
    return [evaluate_candidate(trades, dom, t, ext, tpl, mode) for t, ext in detect_candidates(bars, mode)]


# ── 滚动缓冲（实盘：跨 5 分钟周期累积 1 分钟 bar / 盘口画像）────────────
def _state_path(day: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / ("ar_state_%s.json" % str(day).replace('-', ''))


def load_state(day: str) -> Dict[str, Any]:
    p = _state_path(day)
    if not p.exists():
        return {"day": day, "bars": {}, "dom": {}, "decided": []}
    try:
        with open(p, 'r', encoding='utf-8') as fh:
            st = json.load(fh)
        st.setdefault("bars", {}); st.setdefault("dom", {}); st.setdefault("decided", [])
        return st
    except Exception:
        return {"day": day, "bars": {}, "dom": {}, "decided": []}


def save_state(day: str, st: Dict[str, Any]) -> None:
    p = _state_path(day)
    tmp = p.with_suffix(".tmp")
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(st, fh, ensure_ascii=False)
    tmp.replace(p)


def update_state(day: str, trades, dom_minutes) -> Dict[str, Any]:
    """把本周期新到的 tick / 盘口合并进当日滚动缓冲（幂等覆盖：同分钟取最新）"""
    st = load_state(day)
    for k, b in minute_bars_from_trades(trades).items():
        st["bars"][str(k)] = b
    for d in dom_minutes or []:
        st["dom"][str(d["min"])] = d
    save_state(day, st)
    return st


def _state_trades(st: Dict[str, Any]) -> List[Tuple[int, float, float, int]]:
    """滚动缓冲 → 伪 trades（用 bar 的 close/vol/net 还原，足以复算全部判据）"""
    out = []
    for ks, b in sorted(st.get("bars", {}).items(), key=lambda kv: int(kv[0])):
        k = int(ks)
        net, vol = float(b.get("net", 0.0)), float(b.get("vol", 0.0))
        buy = (vol + net) / 2.0
        sell = (vol - net) / 2.0
        if buy > 0:
            out.append((k, float(b["c"]), buy, 1))
        if sell > 0:
            out.append((k + 30, float(b["c"]), sell, -1))   # 同一分钟内占位，顺序不影响分窗聚合
    return out


def refresh_state(day: str, now_sec: int, lookback_min: int = 210,
                  with_dom: bool = True) -> Dict[str, Any]:
    """实盘每周期调用：读当日原始 TICKS（近 lookback 分钟）刷新滚动缓冲；
    盘口画像**当日只读一次**（gz 不可随机寻址，避免每周期重解开销）。"""
    st = load_state(day)
    trades = load_trades_from_raw(day, t_max=now_sec)
    trades = [x for x in trades if x[0] >= now_sec - lookback_min * 60]
    dom = None
    if with_dom and not st.get("dom"):
        try:
            dom = dom_minutes_from_raw(day, t_to=now_sec)
        except Exception:
            dom = None
    return update_state(day, trades, dom)


def latest_decision(day: str, now_sec: int, templates: Optional[Dict[str, Any]] = None,
                    mode: str = 'low', state: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """实盘入口：在滚动缓冲上找「已满 45 分钟、未超 TTL、且当前最新」的候选极值点并判定。"""
    st = state if state is not None else load_state(day)
    if not st.get("bars"):
        return None
    tpl = templates or load_templates()
    trades = _state_trades(st)
    bars = {int(k): v for k, v in st["bars"].items()}
    dom = [st["dom"][k] for k in sorted(st["dom"], key=lambda x: int(x))]
    best = None
    for t_sec, ext in detect_candidates(bars, mode):
        age = now_sec - t_sec
        if age < REQUIRED_AGE_SEC or age > REQUIRED_AGE_SEC + DECISION_TTL_SEC:
            continue
        if any(int(d.get("t_sec", -1)) == t_sec for d in st.get("decided", [])):
            continue
        res = evaluate_candidate(trades, dom, t_sec, ext, tpl, mode, now_sec=now_sec)
        if best is None or res["t_sec"] > best["t_sec"]:
            best = res
    return best


def mark_decided(day: str, t_sec: int, res: Dict[str, Any], st: Optional[Dict[str, Any]] = None) -> None:
    s = st if st is not None else load_state(day)
    s.setdefault("decided", []).append({"t_sec": int(t_sec), "t": hms(t_sec),
                                        "verdict": res.get("verdict"), "score": res.get("score"),
                                        "action": res.get("action")})
    save_state(day, s)


# ── 契约输出（供 of_metrics['absorption_reversal']）─────────────────────
def to_contract(res: Optional[Dict[str, Any]], enabled: bool = True) -> Dict[str, Any]:
    """证据向量 → OrderFlow 输出契约块（卖家系统机制只读此结构）"""
    if not res:
        return {"version": PAIR_VERSION, "available": False, "reason": "无满足时龄的候选极值点"}
    return {
        "version": PAIR_VERSION,
        "available": True,
        "enabled": bool(enabled),
        "candidate_time": res.get("t"),
        "candidate_px": res.get("ext"),
        "mode": res.get("mode"),
        "direction": res.get("direction"),
        "gate_ok": res.get("gate_ok"),
        "score": res.get("score"),
        "n_dims": res.get("n_dims"),
        "need": res.get("need"),
        "verdict": res.get("verdict"),
        "action": res.get("action"),
        "dom_available": res.get("dom_available"),
        "dims": {k: res.get(k) for k in (
            "into30_net", "cvd_delta_30m", "mid30_net", "next45_net", "zone_span",
            "zone_vol", "dom_ask_near_min", "dom_bid_near_min", "dom_tot_max", "vwap_reclaim")},
        "votes": res.get("votes"),
    }


__all__ = ["PAIR_VERSION", "load_templates", "minute_bars_from_trades", "detect_candidates",
           "dom_minutes_from_raw", "build_vector", "judge", "evaluate_candidate", "evaluate_day",
           "load_trades_from_raw", "load_state", "save_state", "update_state", "refresh_state", "latest_decision",
           "mark_decided", "to_contract", "RAW_DIR", "CACHE_DIR"]
