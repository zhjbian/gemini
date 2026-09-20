# -*- coding: utf-8 -*-
"""在候选低点事件样本上评估 baseline 判据的条件命中率（条件概率 / 精确率 / 召回率）"""
import json, statistics as st
from itertools import product

d = json.load(open('/tmp/base_tick_scan.json'))
lows = d['low']


def num(x, k, default=None):
    v = x.get(k)
    return default if v in (None, 'None') else float(v)


def success(x, up=15.0, dn=5.0):
    mfe = num(x, 'mfe_60'); mae = num(x, 'mae_60')
    if mfe is None or mae is None:
        return None
    return mfe >= up and mae <= dn


S = [(x, success(x)) for x in lows]
S = [(x, s) for x, s in S if s is not None]
base = sum(1 for _, s in S if s) / len(S)
print('样本 n=%d ｜ 基准成功率 (mfe60≥15 且 mae60≤5) = %.1f%%' % (len(S), 100 * base))
print('（参考：mfe60≥10 且 mae60≤5 = %.1f%%；mfe60≥20 = %.1f%%）' % (
    100 * sum(1 for x, s in S if num(x, 'mfe_60', 0) >= 10 and num(x, 'mae_60', 99) <= 5) / len(S),
    100 * sum(1 for x, s in S if num(x, 'mfe_60', 0) >= 20) / len(S)))

print('\n--- 单判据（阈值 / 命中数 / 条件成功率 / 提升倍数）---')
tests = [
    ("zone_net>0", lambda x: num(x, 's1_zone_net', -1) > 0),
    ("zone_net>0 且 zone_ratio≥0.51", lambda x: num(x, 's1_zone_net', -1) > 0 and num(x, 's1_zone_ratio', 0) >= 0.51),
    ("zone_vol≥15000", lambda x: num(x, 's1_zone_vol', 0) >= 15000),
    ("zone_span≥15min", lambda x: num(x, 's1_zone_span', 0) >= 15),
    ("at_net>0", lambda x: num(x, 's1_at_net', -1) > 0),
    ("at_big_net>0", lambda x: num(x, 's1_at_big_net', -1) > 0),
    ("at_big_max_buy≥100", lambda x: num(x, 's1_at_big_max_buy', 0) >= 100),
    ("into_net>0", lambda x: num(x, 's1_into_net', -1) > 0),
    ("pos_pct≤0.20", lambda x: num(x, 's1_pos_pct', 1) <= 0.20),
    ("mid_net>0", lambda x: num(x, 's2_mid_net', -1) > 0),
    ("mid_b50_net≥0", lambda x: num(x, 's2_mid_b50_net', -1) >= 0),
    ("maxrev45≤5", lambda x: num(x, 's2_maxrev_45', 99) <= 5),
    ("vwap_reclaim≤60min", lambda x: num(x, 's2_vwap_reclaim_min', 999) is not None and (x.get('s2_vwap_reclaim_min') not in (None, 'None') and float(x['s2_vwap_reclaim_min']) <= 60)),
]
for name, fn in tests:
    sel = [(x, s) for x, s in S if fn(x)]
    if not sel:
        print('  %-34s n=0' % name); continue
    p = sum(1 for _, s in sel if s) / len(sel)
    print('  %-34s n=%2d  成功率 %5.1f%%  提升 %+.1fpt' % (name, len(sel), 100 * p, 100 * (p - base)))

print('\n--- 组合（S1 三闸 / S1+S2 五闸 / 全闸）---')
combos = {
    "S1: zone_net>0 + at_net>0": lambda x: num(x, 's1_zone_net', -1) > 0 and num(x, 's1_at_net', -1) > 0,
    "S1: zone_net>0 + at_big_net>0 + into_net>0": lambda x: num(x, 's1_zone_net', -1) > 0 and num(x, 's1_at_big_net', -1) > 0 and num(x, 's1_into_net', -1) > 0,
    "S1: zone_net>0 + at_big_max_buy≥100": lambda x: num(x, 's1_zone_net', -1) > 0 and num(x, 's1_at_big_max_buy', 0) >= 100,
    "S1+S2: + mid_b50_net≥0 + maxrev45≤5": lambda x: num(x, 's1_zone_net', -1) > 0 and num(x, 's2_mid_b50_net', -1) >= 0 and num(x, 's2_maxrev_45', 99) <= 5,
    "S1+S2: + mid_net>0 + maxrev45≤5": lambda x: num(x, 's1_zone_net', -1) > 0 and num(x, 's2_mid_net', -1) > 0 and num(x, 's2_maxrev_45', 99) <= 5,
    "S1+S2: + vwap_reclaim≤60": lambda x: num(x, 's1_zone_net', -1) > 0 and x.get('s2_vwap_reclaim_min') not in (None, 'None') and float(x['s2_vwap_reclaim_min']) <= 60,
    "S2 仅确认层: mid_net>0+b50≥0+maxrev≤5+vwap≤60": lambda x: num(x, 's2_mid_net', -1) > 0 and num(x, 's2_mid_b50_net', -1) >= 0 and num(x, 's2_maxrev_45', 99) <= 5 and x.get('s2_vwap_reclaim_min') not in (None, 'None') and float(x['s2_vwap_reclaim_min']) <= 60,
}
for name, fn in combos.items():
    sel = [(x, s) for x, s in S if fn(x)]
    if not sel:
        print('  %-52s n=0' % name); continue
    p = sum(1 for _, s in sel if s) / len(sel)
    tp = sum(1 for _, s in sel if s)
    recall = tp / max(1, sum(1 for _, s in S if s))
    print('  %-52s n=%2d  成功率 %5.1f%%  提升 %+5.1fpt  召回 %4.1f%%' % (name, len(sel), 100 * p, 100 * (p - base), 100 * recall))

print('\n--- 命中组合的具体案例 ---')
fn = combos["S1+S2: + vwap_reclaim≤60"]
for x, s in S:
    if fn(x):
        print('  %s %s 低点%.2f  zoneNet=%+.0f atNet=%+.0f bigMax=%.0f midNet=%+.0f b50=%+.0f maxrev=%.1f vwapRec=%s | mfe60=%.1f mae60=%.1f %s' % (
            x['day'], x['t'], float(x['ext']), num(x, 's1_zone_net', 0), num(x, 's1_at_net', 0), num(x, 's1_at_big_max_buy', 0),
            num(x, 's2_mid_net', 0), num(x, 's2_mid_b50_net', 0), num(x, 's2_maxrev_45', 0), x.get('s2_vwap_reclaim_min'),
            num(x, 'mfe_60', 0), num(x, 'mae_60', 0), '✓' if s else '✗'))
