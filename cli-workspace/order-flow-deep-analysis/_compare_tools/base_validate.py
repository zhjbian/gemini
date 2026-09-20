# -*- coding: utf-8 -*-
"""LAR-v1（低位吸收反转 baseline）与镜像 HDR-v1（高位派发）的样本内验证

输出 /tmp/base_validation.json + 控制台摘要
"""
import json, math, statistics as st
from pathlib import Path

SKILL_CACHE = Path("/Users/zhijiebian/.agents/skills/order-flow-deep-analysis/cache/dom_minutes")
scan = json.load(open('/tmp/base_tick_scan.json'))


def num(x, k, d=None):
    v = x.get(k)
    if v in (None, 'None', ''):
        return d
    try:
        return float(v)
    except Exception:
        return d


DOM_CACHE = {}
for f in SKILL_CACHE.glob('ES_*.json'):
    try:
        DOM_CACHE[f.stem.split('_')[1]] = json.load(open(f))['series']
    except Exception:
        pass


def dom_feats(day, t_hm, minutes=45):
    """候选低点后 0–45 分钟的盘口特征（无 DOM 覆盖返回 None）"""
    s = DOM_CACHE.get(day.replace('-', ''))
    if not s:
        return None
    h, m = t_hm.split(':')
    t0 = int(h) * 60 + int(m)
    sel = [x for x in s if t0 <= x['min'] <= t0 + minutes]
    if len(sel) < 10:            # 覆盖不足
        return {"cover": len(sel)}
    ask_near = [x for x in sel if x['wall_ask']['dist'] is not None and x['wall_ask']['dist'] <= 10 and x['wall_ask']['sz'] >= 100]
    bid_near = [x for x in sel if x['wall_bid']['dist'] is not None and x['wall_bid']['dist'] <= 10 and x['wall_bid']['sz'] >= 80]
    imb = [x['imb5'] for x in sel if x['imb5'] is not None]
    tr = [(x['tot_bid'] / x['tot_ask']) if x['tot_ask'] else None for x in sel]
    tr = [v for v in tr if v]
    return {"cover": len(sel), "ask_near_min": len(ask_near),
            "ask_near_sz": (sum(x['wall_ask']['sz'] for x in ask_near) / len(ask_near)) if ask_near else 0,
            "ask_near_px": ask_near[0]['wall_ask']['px'] if ask_near else None,
            "bid_near_min": len(bid_near),
            "bid_near_sz": (sum(x['wall_bid']['sz'] for x in bid_near) / len(bid_near)) if bid_near else 0,
            "bid_near_px": bid_near[0]['wall_bid']['px'] if bid_near else None,
            "imb5_mean": (sum(imb) / len(imb)) if imb else None,
            "tot_ratio_max": max(tr) if tr else None}


def rate(sel):
    if not sel:
        return None
    return sum(1 for _, s in sel if s) / len(sel)


def evaluate(items, mode='low'):
    out = []
    for x in items:
        s = num(x, 'mfe_60'); a = num(x, 'mae_60')
        if s is None or a is None:
            continue
        if mode == 'low':
            succ = (s >= 15.0 and a <= 5.0)
            adverse45 = num(x, 's2_maxrev_45', 99)
        else:
            succ = (a >= 15.0 and s <= 5.0)          # 自高点下行 ≥15 且上行 ≤5
            adverse45 = num(x, 's2_up_45', 99)
        out.append((x, succ, adverse45))
    return out


def crit(x, kind):
    z = num(x, 's1_zone_net'); zr = num(x, 's1_zone_ratio', 0)
    at = num(x, 's1_at_net'); bm = num(x, 's1_at_big_max_buy', 0)
    mid = num(x, 's2_mid_net'); b50 = num(x, 's2_mid_b50_net', 0)
    pos = num(x, 's1_pos_pct', 0.5); vw = x.get('s2_vwap_reclaim_min')
    vwv = num(x, 's2_vwap_reclaim_min', 9e9)
    vwok = vw not in (None, 'None') and vwv <= 60
    adv = adverse45_of(x, kind)
    if kind == 'low':
        S1 = {"zone_net>0且ratio≥0.51": (z is not None and z > 0 and zr >= 0.51),
              "at_net>0": (at is not None and at > 0),
              "big_max_buy≥100": bm >= 100,
              "pos_pct≤0.20": pos <= 0.20}
        S2 = {"maxrev45≤5": adv <= 5, "mid_net>0": (mid is not None and mid > 0),
              "mid_b50_net≥0": b50 >= 0, "vwap_reclaim≤60": vwok}
        NEG = {"zone_net<0": (z is not None and z < 0), "at_net<0": (at is not None and at < 0),
               "mid_net<0": (mid is not None and mid < 0), "maxrev45>10": adv > 10}
    else:
        S1 = {"zone_net<0且ratio≤0.49": (z is not None and z < 0 and zr <= 0.49),
              "at_net<0": (at is not None and at < 0),
              "big_max_buy≥100(承接)": bm >= 100,
              "pos_pct≥0.80": pos >= 0.80}
        S2 = {"maxup45≤5": adv <= 5, "mid_net<0": (mid is not None and mid < 0),
              "mid_b50_net≤0": b50 <= 0, "vwap_break≤60": vwok}
        NEG = {"zone_net>0": (z is not None and z > 0), "at_net>0": (at is not None and at > 0),
               "mid_net>0": (mid is not None and mid > 0), "maxup45>10": adv > 10}
    return S1, S2, NEG


ADV = {}


def adverse45_of(x, kind):
    key = (x['day'], x['t'], kind)
    if key not in ADV:
        ADV[key] = num(x, 's2_maxrev_45', 99) if kind == 'low' else num(x, 's2_up_45', 99)
    return ADV[key]


rep = {}
for mode, label in (('low', 'LAR-v1 低位吸收反转'), ('high', 'HDR-v1 镜像高位派发')):
    S = evaluate(scan[mode], mode)
    base = rate([(x, s) for x, s, _ in S])
    rep[mode] = {"label": label, "n": len(S), "base": base}
    print('\n' + '=' * 78)
    print('%s ｜ 候选 n=%d ｜ 基准成功率 %.1f%%' % (label, len(S), 100 * base))
    # 单判据
    names = list(crit(S[0][0], mode)[0].keys()) + list(crit(S[0][0], mode)[1].keys())
    single = {}
    for nm in names:
        sel = []
        for x, s, _ in S:
            S1, S2, _N = crit(x, mode)
            if S1.get(nm) or S2.get(nm):
                sel.append((x, s))
        r = rate(sel)
        single[nm] = {"n": len(sel), "rate": r, "lift": (r - base) if r is not None else None}
        print('  %-26s n=%3d  成功率 %5.1f%%  提升 %+5.1fpt' % (nm, len(sel), 100 * r if r is not None else -1,
                                                                100 * ((r - base) if r is not None else 0)))
    rep[mode]["single"] = single
    # 组合
    def combos(x):
        S1, S2, NEG = crit(x, mode)
        return S1, S2, NEG
    rules = Ordered = [
        ("S2 核心：maxrev45≤5", lambda S1, S2, N: S2[list(S2)[0]]),
        ("S1 全 4 条", lambda S1, S2, N: all(S1.values())),
        ("S1 全 4 条 + S2 核心", lambda S1, S2, N: all(S1.values()) and S2[list(S2)[0]]),
        ("S1 的 (zone_net + at_net) + S2 核心 + (mid_net或b50)", lambda S1, S2, N: (
            list(S1.values())[0] and list(S1.values())[1] and S2[list(S2)[0]] and (S2[list(S2)[1]] or S2[list(S2)[2]]))),
        ("★ BASELINE：zone_net + mid_net + maxrev≤5", lambda S1, S2, N: (
            list(S1.values())[0] and list(S1.values())[1] and S2[list(S2)[0]] and S2[list(S2)[1]])),
        ("BASELINE-min：mid_net + maxrev≤5", lambda S1, S2, N: S2[list(S2)[0]] and S2[list(S2)[1]]),
        ("★ BASELINE-full：(zone│at│big) + maxrev + (mid│b50│vwap)", lambda S1, S2, N: (
            (list(S1.values())[0] or list(S1.values())[1] or list(S1.values())[2]) and S2[list(S2)[0]]
            and (S2[list(S2)[1]] or S2[list(S2)[2]] or S2[list(S2)[3]]))),
        ("反例 NEG 全 4 条（应显著低于基准）", lambda S1, S2, N: all(N.values())),
        ("反例 3 条（zone+at+mid 反向）", lambda S1, S2, N: (list(N.values())[0] and list(N.values())[1] and list(N.values())[2])),
    ]
    print('  --- 组合 ---')
    rep[mode]["combos"] = {}
    for nm, fn in rules:
        sel = [(x, s) for x, s, _ in S if fn(*crit(x, mode))]
        r = rate(sel)
        tp = sum(1 for _, s in sel if s)
        tot_pos = sum(1 for _, s, _ in S if s)
        rec = tp / max(1, tot_pos)
        rep[mode]["combos"][nm] = {"n": len(sel), "rate": r, "lift": (r - base) if r is not None else None, "recall": rec}
        print('  %-50s n=%3d  成功率 %5.1f%%  提升 %+5.1fpt  召回 %4.1f%%' % (
            nm, len(sel), 100 * r if r is not None else -1, 100 * ((r - base) if r is not None else 0), 100 * rec))

# DOM 层（仅覆盖日）
print('\n' + '=' * 78)
print('DOM 层单判据（仅 06:30–11:00 有 DOM 覆盖的候选）')
dom_rows = []
for x, s, _ in evaluate(scan['low'], 'low'):
    f = dom_feats(x['day'], x['t'])
    if f and f.get('cover', 0) >= 10:
        dom_rows.append((x, s, f))
print('有 DOM 覆盖的候选低点 n=%d ｜ 其中成功 %d (基准 %.1f%%)' % (
    len(dom_rows), sum(1 for _, s, _ in dom_rows if s),
    100 * sum(1 for _, s, _ in dom_rows if s) / max(1, len(dom_rows))))
db = sum(1 for _, s, _ in dom_rows if s) / max(1, len(dom_rows))
for nm, fn in [("贴价卖墙(≤10t,≥100手) 0 分钟", lambda f: f['ask_near_min'] == 0),
               ("贴价买墙(≤10t,≥80手) ≥1 分钟", lambda f: f['bid_near_min'] >= 1),
               ("全盘买/卖比曾 ≥1.0", lambda f: (f['tot_ratio_max'] or 0) >= 1.0),
               ("imb5 均值 > 0", lambda f: (f['imb5_mean'] or -1) > 0),
               ("③④⑤ 全满足", lambda f: f['ask_near_min'] == 0 and f['bid_near_min'] >= 1 and (f['tot_ratio_max'] or 0) >= 1.0)]:
    sel = [(x, s) for x, s, f in dom_rows if fn(f)]
    r = rate(sel)
    print('  %-30s n=%2d  成功率 %5.1f%%  提升 %+5.1fpt' % (nm, len(sel), 100 * r if r is not None else -1,
                                                            100 * ((r - db) if r is not None else 0)))
rep['dom'] = {"n": len(dom_rows), "base": db}

Path('/tmp/base_validation.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str))
print('\nWROTE /tmp/base_validation.json')
