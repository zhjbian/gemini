# -*- coding: utf-8 -*-
"""两日 DOM 近端结构对照：逐分钟 ±5/±15 失衡、最近卖墙/买墙、墙位迁移"""
import json, sys
from pathlib import Path
sys.path.insert(0, '/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools')
sys.path.insert(0, '/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs')
from adam_dom_analysis import dom_analysis, TICK

DAYS = {'2026-09-14': [8 * 3600 + 20 * 60, 9 * 3600 + 20 * 60],
        '2026-09-15': [8 * 3600 + 20 * 60, 9 * 3600 + 20 * 60]}

out = {}
for day, ts in DAYS.items():
    series = {}
    for t0 in ts:
        d = dom_analysis(day, t0)
        if not d:
            continue
        for p in d.get('_series', []):
            series[p['time'] // 60 * 60] = p
    rows = []
    for k in sorted(series):
        p = series[k]
        mid = p['mid']
        # 近端墙：mid ±10 ticks 内最大单档（避免远端大墙干扰）
        rows.append({
            'hm': "%02d:%02d" % (k // 3600, (k % 3600) // 60),
            'mid': mid,
            'imb5': p.get('imb_5'), 'imb15': p.get('imb_15'),
            'bid5': p.get('bid_5'), 'ask5': p.get('ask_5'),
            'tot_ratio': (p['tot_bid'] / p['tot_ask']) if p['tot_ask'] else None,
            'wall_bid_px': p['wall_bid']['px'], 'wall_bid_sz': p['wall_bid']['sz'],
            'wall_bid_dist': p['wall_bid']['dist'],
            'wall_ask_px': p['wall_ask']['px'], 'wall_ask_sz': p['wall_ask']['sz'],
            'wall_ask_dist': p['wall_ask']['dist'],
            'spread': p['spread'],
        })
    out[day] = {'series': rows, 'events': [{'hm': "%02d:%02d" % (e['t'] // 3600, (e['t'] % 3600) // 60),
                                            'side': e['side'], 'px': e['px'], 'd': e['d'], 'sz': e['sz']}
                                           for e in d.get('_events', [])],
                'vwap': d.get('_vwap')}
    print(day, 'snapshots', len(rows), 'vwap', d.get('_vwap'))

Path('/tmp/ofa_dom_series.json').write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
print('ok')
