# -*- coding: utf-8 -*-
"""对照模板 baseline（PAIR v1.1）—— 只用 2026-09-14 / 2026-09-15 两个相反案例

方法：不做大样本标定，而是把两天的锚定低点各算一条特征向量（A 模板 / B 模板），
对任意候选低点**逐维投票**（该维更像 A 还是更像 B），得到 A 票数得分。
只在「两案例确实分得开」的维度上投票；两案例同样取值的维度列为**无区分度维度**（同样重要的结论）。

CLI
  python3 baseline_pair.py --build                 # 重算并写 baseline_templates_v1.json
  python3 baseline_pair.py --eval --date 2026-09-15 --at 07:53 --px 7643.50
  python3 baseline_pair.py --rank --date 2026-09-14   # 当日全部候选低点排序
  python3 baseline_pair.py --selfcheck             # 两锚点自检 + 两日候选排序
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from collections import OrderedDict

SKILL = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL))
import baseline as B

TEMPLATE_FILE = SKILL / "baseline_templates_v1.json"

# 锚定点（两案例的低点；tick 极值口径为主，引擎口径作为稳健性复核）
ANCHORS = OrderedDict([
    ("A", {"day": "2026-09-14", "t": "07:54", "px": 7664.00,
           "label": "真反转 · 09-14 07:54", "alt": {"t": "07:55", "px": 7665.25}}),
    ("B", {"day": "2026-09-15", "t": "07:53", "px": 7643.50,
           "label": "假反弹 · 09-15 07:53", "alt": {"t": "08:00", "px": 7646.25}}),
])

# 决定性维度（两案例分开的维度；顺序即展示顺序）
DECISIVE = [
    ("into30_net", "低点前 30 分钟净 Delta", "手", "A 越跌越买 / B 越跌越卖"),
    ("cvd_delta_30m", "低点 ±15 分钟累计 Delta 变化", "手", "低点附近的净流方向"),
    ("mid30_net", "低点后 15–45 分钟净 Delta", "手", "承接是否延续"),
    ("next45_net", "低点后 45–90 分钟净 Delta", "手", "脱离后是否有后续买盘"),
    ("zone_span", "低点区（≤低点+0.75）停留时长", "分钟", "横盘吸收基底 vs V 型尖底"),
    ("dom_ask_near_min", "贴价卖墙（≤10t 且 ≥100 手）出现分钟数", "分钟", "上方是否被钉住"),
    ("dom_bid_near_min", "贴价买墙（≤10t 且 ≥80 手）出现分钟数", "分钟", "下方是否有贴身承接"),
    ("dom_tot_max", "全盘买/卖挂单比峰值", "比", "挂单是否转向买优"),
    ("vwap_reclaim", "60 分钟内收复当日 VWAP", "秒/未收复", "结构位收复"),
]
# 两案例分不开的维度（同样重要的结论：不可用作判据）
NON_DECISIVE = [
    ("zone_vol", "低点区成交量", "引擎口径几乎相同（17,691 vs 17,971 手）；tick 极值口径差异大 ⇒ 口径敏感，不作判据"),
    ("at15_net", "低点后 0–15 分钟净 Delta", "两案例都为正，B 甚至更大（+1,602 vs +1,355）"),
    ("at15_big_max_buy", "低点后最大单笔主动买", "B 的单笔更大（300 vs 257 手）⇒ 单笔大单无区分度"),
    ("at15_big_net", "低点后 ≥20 手大单净额", "B 更大（+270 vs +230）"),
    ("maxrev45", "低点后 45 分钟最大逆向", "B 的低点根本没被跌破（0.0 < A 的 1.75–3.0）"),
    ("pos_pct", "低点在当日区间分位", "两案例都在极低位（0.08 / 0.05）⇒ 位置不是区分点"),
    ("zone_ratio", "低点区买占比", "0.50 vs 0.48～0.52 接近"),
]


def _dom_drift(day, t_sec, a=0, b=45):
    s = B.dom_series(day)
    if not s:
        return {}
    t0 = t_sec // 60
    sel = [x for x in s if t0 + a <= x['min'] <= t0 + b]
    if len(sel) < 10:
        return {}
    ask_near = [x for x in sel if x['wall_ask']['dist'] is not None and x['wall_ask']['dist'] <= 10 and x['wall_ask']['sz'] >= 100]
    bid_near = [x for x in sel if x['wall_bid']['dist'] is not None and x['wall_bid']['dist'] <= 10 and x['wall_bid']['sz'] >= 80]
    tr = [(x['tot_bid'] / x['tot_ask']) if x['tot_ask'] else None for x in sel]
    tr = [v for v in tr if v]
    imb = [x['imb5'] for x in sel if x['imb5'] is not None]
    return {"ask_near_min": len(ask_near),
            "ask_near_sz": (sum(x['wall_ask']['sz'] for x in ask_near) / len(ask_near)) if ask_near else 0,
            "ask_near_px": ask_near[0]['wall_ask']['px'] if ask_near else None,
            "bid_near_min": len(bid_near),
            "bid_near_sz": (sum(x['wall_bid']['sz'] for x in bid_near) / len(bid_near)) if bid_near else 0,
            "bid_near_px": bid_near[0]['wall_bid']['px'] if bid_near else None,
            "tot_max": max(tr) if tr else None, "tot_min": min(tr) if tr else None,
            "imb5_mean": (sum(imb) / len(imb)) if imb else None, "cover": len(sel)}


def vector(day, t_hm, px):
    rows = B.load_ticks(day)
    t = B.sec(t_hm)
    f = B.features(rows, t, px, 'low', with_dom=False, day=None)
    d = _dom_drift(day, t)
    next45 = B.phase(rows, t + 2700, t + 5400)
    cvd = 0.0
    for x in rows:
        if t - 900 <= x[0] <= t + 900:
            cvd += x[3] * x[2]
    v = OrderedDict([
        ("t", B.hms(t)), ("px", px),
        ("into30_net", f.get("into_net")),
        ("cvd_delta_30m", cvd),
        ("mid30_net", f.get("mid_net")),
        ("next45_net", next45["net"]),
        ("zone_span", f.get("zone_span")),
        ("zone_net", f.get("zone_net")), ("zone_ratio", f.get("zone_ratio")), ("zone_vol", f.get("zone_vol")),
        ("at15_net", f.get("at_net")), ("at15_ratio", f.get("at_ratio")),
        ("at15_big_net", f.get("at_big_net")), ("at15_big_max_buy", f.get("at_big_max_buy")),
        ("mid30_b50_net", f.get("mid_b50_net")),
        ("maxrev45", f.get("maxrev_45")), ("maxup45", f.get("up_45")), ("pos_pct", f.get("pos_pct")),
        ("vwap_reclaim", f.get("vwap_reclaim_min")),
        ("mfe60", f.get("mfe_60")), ("mae60", f.get("mae_60")), ("mfe120", f.get("mfe_120")),
    ])
    for k in ("ask_near_min", "ask_near_sz", "ask_near_px", "bid_near_min", "bid_near_sz", "bid_near_px",
              "tot_max", "tot_min", "imb5_mean", "cover"):
        v["dom_" + k] = d.get(k)
    if not d:
        v["dom_available"] = False
    else:
        v["dom_available"] = d.get("cover", 0) >= 10
    return v


def vote(x, a, b, key):
    """返回 +1（更像 A）/ −1（更像 B）/ 0（不可判）"""
    if key == "vwap_reclaim":
        xa, xb, xv = a.get(key), b.get(key), x.get(key)
        fa, fb = xa is not None, xb is not None
        fv = xv is not None
        if not fa and not fb:
            return 0
        if fa == fb:
            return 0
        return (1 if fv == fa else -1) if not (fa and fb) else 0
    xv = x.get(key); av = a.get(key); bv = b.get(key)
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


def judge(x, tpl, need=6, gate=True):
    """gate=True 时加硬门槛：低点 ±15 分钟累计 Delta 必须 > 0（两案例在此维完全分开：
    A +2,326 / +2,257，B −2,566 / −1,510）。缺此门槛会把 09-14 07:19、07:24 两个失败低点误判为 A 型。"""
    a, b = tpl["A"], tpl["B"]
    votes = OrderedDict()
    s = 0
    for key, name, unit, note in DECISIVE:
        v = vote(x, a, b, key)
        votes[key] = v
        s += v
    n = len(DECISIVE)
    g = x.get("cvd_delta_30m")
    g = float(g) if g is not None else None
    gate_ok = (g is not None and g > 0) if gate else True
    if gate and not gate_ok:
        verdict = "不参与（低点区净流反向）"
    elif s >= need:
        verdict = "A 型（低点吸收）"
    elif s <= -need:
        verdict = "B 型（假反弹）"
    else:
        verdict = "不可判"
    return s, n, verdict, votes, gate_ok


def build():
    tpl = {"version": "PAIR v1.1", "anchors": ANCHORS,
           "decisive": [{"key": k, "name": n_, "unit": u, "note": nt} for k, n_, u, nt in DECISIVE],
           "non_decisive": [{"key": k, "name": n_, "note": nt} for k, n_, nt in NON_DECISIVE]}
    for k, cfg in ANCHORS.items():
        tpl[k] = vector(cfg["day"], cfg["t"], cfg["px"])
        alt = cfg.get("alt")
        tpl[k + "_alt"] = vector(cfg["day"], alt["t"], alt["px"]) if alt else None
    TEMPLATE_FILE.write_text(json.dumps(tpl, ensure_ascii=False, indent=1, default=str))
    return tpl


def load_tpl():
    if TEMPLATE_FILE.exists():
        return json.load(open(TEMPLATE_FILE))
    return build()


def show(tpl):
    a, b = tpl["A"], tpl["B"]
    a2, b2 = tpl.get("A_alt") or {}, tpl.get("B_alt") or {}
    print("=== 决定性维度（A 模板 vs B 模板；alt = 引擎口径锚点复核）===")
    print("%-22s %14s %14s %14s %14s" % ("维度", "A(07:54)", "B(07:53)", "A_alt(07:55)", "B_alt(08:00)"))
    for key, name, unit, note in DECISIVE:
        def fm(r):
            v = r.get(key)
            if v is None:
                return "未收复" if key == "vwap_reclaim" else "—"
            if key == "vwap_reclaim":
                return "%d 秒" % int(float(v))
            return ("%+.0f" % float(v)) if abs(float(v)) >= 100 else ("%+.2f" % float(v))
        print("%-22s %14s %14s %14s %14s" % (name, fm(a), fm(b), fm(a2), fm(b2)))
    print("\n=== 无区分度维度（不可用作判据）===")
    for key, name, note in NON_DECISIVE:
        def fm(r):
            v = r.get(key)
            if v is None:
                return "—"
            return ("%+.0f" % float(v)) if abs(float(v)) >= 100 else ("%+.2f" % float(v))
        print("  %-24s A %10s | B %10s   ← %s" % (name, fm(a), fm(b), note))


def eval_one(tpl, day, t_hm, px, quiet=False):
    x = vector(day, t_hm, px)
    s, n, verdict, votes, gate_ok = judge(x, tpl)
    if not quiet:
        print("%s %s @%.2f → 得分 %+d/%d ｜ 净流门槛 %s → %s" % (
            day, t_hm, px, s, n, "PASS" if gate_ok else "BLOCK（低点±15m CVD ≤ 0）", verdict))
        for key, name, unit, note in DECISIVE:
            a, b = tpl["A"], tpl["B"]
            def fm(r):
                v = r.get(key)
                if v is None:
                    return "未收复"
                return ("%+.0f" % float(v)) if abs(float(v)) >= 100 else ("%+.2f" % float(v))
            print("   %-34s 候选 %10s ｜ A %10s ｜ B %10s → %s" % (
                name, fm(x), fm(a), fm(b), {1: "像 A ✓", -1: "像 B ✗", 0: "不可判"}[votes[key]]))
        if x.get("mfe60") is not None:
            print("   后验（仅回看）: mfe60 %+.2f / mae60 %+.2f / mfe120 %s" % (
                float(x["mfe60"]), float(x["mae60"]),
                ("%+.2f" % float(x["mfe120"])) if x.get("mfe120") is not None else "—"))
    return x, s, n, verdict, votes, gate_ok


def rank(tpl, day):
    rows = B.load_ticks(day)
    out = []
    for t_sec, ext in B.candidates(rows, 'low'):
        x = vector(day, B.hms(t_sec), ext)
        s, n, verdict, votes, gate_ok = judge(x, tpl)
        out.append((s, B.hms(t_sec), ext, verdict, x, gate_ok))
    out.sort(key=lambda r: -r[0])
    print("\n%s 候选低点排序（A 票数从高到低）" % day)
    print("  %-6s %10s %14s %8s %10s %10s %10s %8s" % ("时刻", "极值", "判定", "得分", "mfe60", "mae60", "maxrev45", "zone_span"))
    for s, hm, ext, verdict, x, gate_ok in out:
        print("  %-6s %10.2f %-22s %+5d/%d %10s %10s %10s %8s" % (
            hm, ext, verdict, s, len(DECISIVE),
            ("%+.1f" % float(x["mfe60"])) if x.get("mfe60") is not None else "—",
            ("%+.1f" % float(x["mae60"])) if x.get("mae60") is not None else "—",
            ("%.1f" % float(x["maxrev45"])) if x.get("maxrev45") is not None else "—",
            ("%.1f" % float(x["zone_span"])) if x.get("zone_span") is not None else "—"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--show', action='store_true')
    ap.add_argument('--eval', action='store_true')
    ap.add_argument('--rank')
    ap.add_argument('--selfcheck', action='store_true')
    ap.add_argument('--date'); ap.add_argument('--at'); ap.add_argument('--px', type=float)
    a = ap.parse_args()
    tpl = build() if a.build else load_tpl()
    if a.build or a.show:
        show(tpl)
    if a.eval and a.date and a.at:
        eval_one(tpl, a.date, a.at, a.px if a.px is not None else 0.0)
    if a.rank:
        rank(tpl, a.rank)
    if a.selfcheck:
        print("=== 锚点自检 ===")
        for k in ("A", "B"):
            c = tpl["anchors"][k]
            eval_one(tpl, c["day"], c["t"], c["px"])
            if c.get("alt"):
                eval_one(tpl, c["day"], c["alt"]["t"], c["alt"]["px"])
        for d in ("2026-09-14", "2026-09-15"):
            rank(tpl, d)


if __name__ == '__main__':
    main()
