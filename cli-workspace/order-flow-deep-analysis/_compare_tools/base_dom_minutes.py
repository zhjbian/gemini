# -*- coding: utf-8 -*-
"""按日抽取 DOM 逐分钟画像（06:00–11:00，一次扫描一天），供 baseline 事件研究使用。

缓存：<skill>/cache/dom_minutes/ES_<yyyymmdd>.json
画像字段：mid / imb2,5,15 / bid5,ask5 / tot_bid,tot_ask / wall_bid(px,sz,dist) / wall_ask(px,sz,dist)
"""
import csv, json, sys, time
from pathlib import Path

SKILL = Path("/Users/zhijiebian/.agents/skills/order-flow-deep-analysis")
CACHE = SKILL / "cache" / "dom_minutes"
RAW = Path("/Users/zhijiebian/Documents/MyDoc/Finance/Current/MotiveWave_OrderFlow_Data/Raw")
sys.path.insert(0, '/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools')
sys.path.insert(0, str(SKILL / 'scripts'))
sys.path.insert(0, '/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs')
from adam_dom_analysis import _profile, _pt, TICK


def build(day, t_from=6 * 3600, t_to=11 * 3600):
    f = RAW / ("ES_%s_DOM.csv.gz" % day.replace('-', ''))
    if not f.exists():
        f = RAW / ("ES_%s_DOM.csv" % day.replace('-', ''))
        if not f.exists():
            return None
    from py_lib.mw_gzip import open_text
    by_min = {}
    cur = None
    buf = []
    t0 = time.time()
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
                cur = None
                buf = []
                continue
            if row[0] != cur:
                if buf:
                    p = _profile(buf, None)
                    if p:
                        by_min[p['time'] // 60] = p
                buf = []
                cur = row[0]
            try:
                buf.append((_pt(row[0]), row[1].upper(), float(row[3]), float(row[4])))
            except Exception:
                pass
    out = []
    for k in sorted(by_min):
        p = by_min[k]
        mid = p['mid']
        out.append({"hm": "%02d:%02d" % (k // 60, k % 60), "min": k,
                    "mid": mid, "imb2": p.get('imb_2'), "imb5": p.get('imb_5'), "imb15": p.get('imb_15'),
                    "bid5": p.get('bid_5'), "ask5": p.get('ask_5'),
                    "tot_bid": p['tot_bid'], "tot_ask": p['tot_ask'],
                    "wall_bid": p['wall_bid'], "wall_ask": p['wall_ask']})
    return {"day": day, "n": len(out), "secs": round(time.time() - t0, 1), "series": out}


if __name__ == '__main__':
    CACHE.mkdir(parents=True, exist_ok=True)
    days = sys.argv[1:] or ["2026-09-01", "2026-09-02", "2026-09-04", "2026-09-08", "2026-09-09",
                            "2026-09-10", "2026-09-11", "2026-09-13", "2026-09-14", "2026-09-15"]
    for d in days:
        p = CACHE / ("ES_%s.json" % d.replace('-', ''))
        if p.exists():
            print('cached', d, flush=True)
            continue
        r = build(d)
        if not r:
            print('no dom', d, flush=True)
            continue
        p.write_text(json.dumps(r, ensure_ascii=False))
        print('built', d, 'minutes', r['n'], 'secs', r['secs'], flush=True)
