#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回滚「TICK/DOM 行最后有效时间点实时徽标」改动（2026-09-16，归档目录 73_*）。

背景：这三处改动落在**未纳入 git** 的文件里，改动前没有生成时间戳备份，
因此回滚采用"按锚点精确切除本次新增块"的方式，并在切除后做语法校验。
幂等：已回滚过的文件再次运行不会有副作用（找不到锚点即跳过）。

用法：
    python3 rollback.py            # dry-run：只报告将切除的范围
    python3 rollback.py --apply    # 实际写盘（写前生成 <file>.bak-<ts>）
"""
from __future__ import annotations

import argparse
import ast
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading")

PY_PROBE_START = "★ 2026-09-16（用户要求）：单文件「最后确认数据有效时间点」尾部探测"
PY_PROBE_END = "def _window_buckets(d: date, span: tuple) -> list:"
ROUTE_START = "@bp_bbt_signals.route('/data/mw_file_last_valid', methods=['GET'])"
ROUTE_END = "@bp_bbt_signals.route('/data/mw_data_health/scan', methods=['POST'])"
JS_START = "★ 2026-09-16（用户要求）：TICK / DOM 文字行后紧跟"
JS_END = "    function mwCoverageGroup("   # 签名可能随迭代变化（第二批加了 onlyTicker），故只匹配前缀


def cut_block(text: str, start_sub: str, end_sub: str, label: str) -> tuple[str, str]:
    """切除 [start 所在行 .. end 之前] 的整块（保留 end 那行）。"""
    i = text.find(start_sub)
    if i < 0:
        return text, f"{label}: 未找到起始锚点（已回滚过？跳过）"
    # 回退到该行行首（连同上方由本次改动添加的分隔注释一起切掉）
    line_start = text.rfind("\n", 0, i) + 1
    while True:                                    # 吃掉紧邻上方的注释行（// ---- 或 # ====）
        prev = text.rfind("\n", 0, line_start - 1) + 1
        s = text[prev:line_start].strip()
        if s.startswith("// ---") or s.startswith("# ="):
            line_start = prev
        else:
            break
    j = text.find(end_sub, i)
    if j < 0:
        return text, f"{label}: 未找到结束锚点，放弃（未改动）"
    return text[:line_start] + text[j:], f"{label}: 切除 {j - line_start} 字符"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    ts = time.strftime("%Y%m%d_%H%M%S")
    jobs = []

    # 1) 巡检模块：删除 probe_last_valid 及其辅助块
    jobs.append((ROOT / "PyTools/jobs/mw_data_health_check.py", PY_PROBE_START, PY_PROBE_END, "py-probe"))
    # 2) 只读接口：删除路由
    jobs.append((ROOT / "bbt_data_web/data_app/bbt_signals.py", ROUTE_START, ROUTE_END, "flask-route"))
    # 3) 前端：删除徽标/轮询函数块
    jobs.append((ROOT / "bbt_data_web/static/js/bbt_signals.js", JS_START, JS_END, "js-block"))

    for path, s, e, label in jobs:
        text = path.read_text(encoding="utf-8")
        new, msg = cut_block(text, s, e, label)
        changed = new != text
        print(f"[{label}] {path.name}: {msg}")
        if changed and args.apply:
            shutil.copy2(path, path.with_name(path.name + f".bak-{ts}"))
            path.write_text(new, encoding="utf-8")

    # 4) 前端零散行：徽标调用 + 两处轮询钩子 + 版本号
    js = ROOT / "bbt_data_web/static/js/bbt_signals.js"
    t = js.read_text(encoding="utf-8")
    t2 = t.replace("            + mwLastValidBadge(r, c)\n", "")
    t2 = t2.replace("{ renderMwHealthDetail(d); mwLastValidStart(); }", "{ renderMwHealthDetail(d); }")
    t2 = t2.replace("            mwLastValidStop();                      // ★ 收起时停止「最后有效」轮询\n", "")
    t2 = t2.replace("        mwLastValidStart();                         // ★ 展开时启动「最后有效」轮询（5s）\n", "")
    print(f"[js-lines] bbt_signals.js: {'已回滚零散行' if t2 != t else '无匹配（跳过）'}")
    if t2 != t and args.apply:
        shutil.copy2(js, js.with_name(js.name + f".bak-{ts}"))
        js.write_text(t2, encoding="utf-8")

    # 4b) 第二批：NQ 行 / id 去重 / 回填按钮位置 —— 精确字符串回退
    NQ_PAIRS = [
        ("    var MW_COV_TICKERS = ['ES', 'NQ'];   // ★ 2026-09-16：ES 之外补 NQ（其 DOM 也常出问题，需同一实时徽标）\n",
         "    var MW_COV_TICKERS = ['ES'];\n"),
        ("function mwCoverageGroup(label, rows, bf, reqDate, onlyTicker) {",
         "function mwCoverageGroup(label, rows, bf, reqDate) {"),
        ("        // ★ 2026-09-16：新增 onlyTicker —— 同一 label 下可分别渲染 ES / NQ 两块（NQ 也要实时\"最后有效\"徽标）。\n"
         "        if (onlyTicker) {\n"
         "            list = list.filter(function (r) { return r.ticker === onlyTicker; });\n"
         "        }\n", ""),
        ("        // ★ 2026-09-16：该按钮回填 ES+NQ 两个标的（后端 tickers='ES,NQ'），因此只在 ES 行渲染一次，\n"
         "        //   避免 NQ 行重复渲染出第二个 id=\"mw-bf-btn\"（重复 id 会让按钮/状态互相覆盖）。\n"
         "        var bfBar = '';\n        if (label === 'TICK' && r.ticker === 'ES') {",
         "        var bfBar = '';\n        if (label === 'TICK') {"),
        ("+ '<div id=\"mw-gap-box-' + label + '-' + r.ticker + '\"",
         "+ '<div id=\"mw-gap-box-' + label + '\""),
        ("'mw-gap-box-' + (kind === 'TICKS' ? 'TICK' : 'DOM') + '-' + ticker);",
         "'mw-gap-box-' + (kind === 'TICKS' ? 'TICK' : 'DOM'));"),
        ("            var tickHtml = '', domHtml = '';\n"
         "            MW_COV_TICKERS.forEach(function (tk) {\n"
         "                tickHtml += mwCoverageGroup('TICK', cov.filter(function (r) { return r.kind === 'TICKS'; }),\n"
         "                                            (tk === 'ES' ? d.backfill : null), d.requested_date, tk);\n"
         "                domHtml += mwCoverageGroup('DOM', cov.filter(function (r) { return r.kind === 'DOM'; }),\n"
         "                                           null, d.requested_date, tk);\n"
         "            });",
         "            var tickHtml = mwCoverageGroup('TICK', cov.filter(function (r) { return r.kind === 'TICKS'; }), d.backfill, d.requested_date);\n"
         "            var domHtml = mwCoverageGroup('DOM', cov.filter(function (r) { return r.kind === 'DOM'; }), null, d.requested_date);"),
        ("<i class=\"fas fa-satellite-dish\"></i> 时段覆盖（ES / NQ · 每格 5 分钟）",
         "<i class=\"fas fa-satellite-dish\"></i> 时段覆盖（ES · 每格 5 分钟）"),
        ("下面为单日 ES / NQ TICK · DOM 时段覆盖水平条（每格 5 分钟）· 每行左侧徽标为该文件尾部实时探测的「最后有效」时间点",
         "下面为单日 ES TICK / DOM 时段覆盖水平条（每格 5 分钟）"),
    ]
    t = js.read_text(encoding="utf-8")
    n_hit = 0
    for old_s, new_s in NQ_PAIRS:
        if old_s in t:
            t = t.replace(old_s, new_s, 1)
            n_hit += 1
    print(f"[js-nq-rows] bbt_signals.js: 回退 {n_hit}/{len(NQ_PAIRS)} 处（第二批 NQ 行）")
    if n_hit and args.apply:
        shutil.copy2(js, js.with_name(js.name + f".bak-{ts}"))
        js.write_text(t, encoding="utf-8")

    html = ROOT / "bbt_data_web/templates/bbt_signals.html"
    h = html.read_text(encoding="utf-8")
    h2 = h.replace("bbt_signals.js') }}?v=1.2.103", "bbt_signals.js') }}?v=1.2.101")
    print(f"[html-ver] bbt_signals.html: {'版本号回退 1.2.103 → 1.2.101' if h2 != h else '无匹配（跳过）'}")
    if h2 != h and args.apply:
        shutil.copy2(html, html.with_name(html.name + f".bak-{ts}"))
        html.write_text(h2, encoding="utf-8")

    if not args.apply:
        print("\n[dry-run] 未写盘；加 --apply 生效")
        return 0

    # 校验
    ok = True
    for f in (ROOT / "PyTools/jobs/mw_data_health_check.py",
              ROOT / "bbt_data_web/data_app/bbt_signals.py"):
        try:
            ast.parse(f.read_text(encoding="utf-8"))
            print(f"  ✓ {f.name} 语法 OK")
        except SyntaxError as ex:
            ok = False
            print(f"  ✗ {f.name} 语法错误: {ex}")
    r = subprocess.run(["node", "--check", str(js)], capture_output=True, text=True)
    print(f"  {'✓' if r.returncode == 0 else '✗'} bbt_signals.js {r.stderr.strip()[:200]}")
    return 0 if ok and r.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
