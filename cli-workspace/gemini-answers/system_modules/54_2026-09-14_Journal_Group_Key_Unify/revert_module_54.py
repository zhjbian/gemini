#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""revert_module_54.py —— 回退「订单组合分组键统一（group_order_id 优先）」（模块 54）。

为什么需要：BBTrading 仓库几乎不纳入版本控制（`bbt_data_web/`、`PyTools/` 均 untracked）
⇒ 无 `git checkout` 可用；项目约定是就地留 `.bak-YYYYMMDD_HHMMSS` 快照。
本脚本按「逐字面量反向替换」实现可复现回退，写前自动留快照、写后做语法校验。

回退内容（= 2026-09-14 模块 54 的三处改动，共 4 个替换点）：
  ① 账本 `renderHistoryTable()`：去掉「权威键优先」，恢复旧的 order_id 基名 / DRY 时间戳 / ≤3s 启发式；
  ② 后端 `/api/option_seller/trades_by_date`：去掉 payload 里的 `group_order_id`；
  ③ TV 生成器 `tv_option_seller_trades.py`：同上（去掉权威键优先）。
⚠️ 回退后 LIVE 双批次（独立券商 order_id + 开仓差 4–5s）会再次被拆成两个「单成员组」✗。

用法：
    python3 revert_module_54.py --dry-run    # 只报告锚点命中（零写盘）
    python3 revert_module_54.py              # 留快照 → 回退 → 语法校验
"""
from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading')
TEMPLATE = ROOT / 'bbt_data_web/templates/bbt_option_seller.html'
ENDPOINT = ROOT / 'bbt_data_web/data_app/bbt_option_seller.py'
GENERATOR = ROOT / 'PyTools/trading_view/tv_option_seller_trades.py'

# ── ① 账本分组（模板）────────────────────────────────────────────────────────
_JS_FIX_HEAD = "        // ★ 2026-09-14（用户报障「#11 #12 是一个单"
_JS_FIX_TAIL = "        for (const [existingKey, existingTrades] of (matchedGrpKey ? [] : groupsMap.entries())) {\n"
_JS_ORIG = """        let matchedGrpKey = null;
        const tOidBase = t.order_id ? String(t.order_id).replace(/-[12]$/, '') : null;
        
        // Check existing groups to match by base order_id or close open timestamp (within 3 seconds)
        for (const [existingKey, existingTrades] of groupsMap.entries()) {
"""
_JS_CHAIN_FIX = "const grpKey = matchedGrpKey || authGrpKey || tOidBase ||"
_JS_CHAIN_ORIG = "const grpKey = matchedGrpKey || tOidBase ||"

# ── ② 后端 payload ──────────────────────────────────────────────────────────
_BE_FIX = """            # ★ 2026-09-14：**带回分组权威键** —— 同一次开仓的两批共享 `group_order_id`。
            #   账本分组按它聚合（`t.group_order_id || entry_evidence.group_order_id`），
            #   与「活跃持仓」序列化（option_seller_manager._to_dict）保持同一口径 ✓
            'group_order_id': ev.get('group_order_id'),
"""

# ── ③ 生成器分组 ────────────────────────────────────────────────────────────
_GEN_FIX_HEAD = "        # ★ 2026-09-14（用户报障「同一单的两批没显示在自己的组里」）：分组键**优先取后端权威键**"
_GEN_FIX_TAIL = "        for existing_key, existing_trades in ([] if matched_key else list(trades_by_group.items())):\n"
_GEN_ORIG = """        # Check if matches an existing group by oid_base or within 3 seconds
        matched_key = None
        for existing_key, existing_trades in trades_by_group.items():
"""
_GEN_CHAIN_FIX = "grp_key = matched_key or auth_grp_key or oid_base or"
_GEN_CHAIN_ORIG = "grp_key = matched_key or oid_base or"


def _revert_file(path: Path, dry_run: bool) -> int:
    src = io.open(path, encoding='utf-8').read()
    orig_len = len(src)
    problems: list[str] = []
    if path == TEMPLATE:
        if _JS_FIX_HEAD in src and _JS_FIX_TAIL in src:
            i = src.index(_JS_FIX_HEAD)
            j = src.index(_JS_FIX_TAIL, i) + len(_JS_FIX_TAIL)
            src = src[:i] + _JS_ORIG + src[j:]
            print('  ✓ ① 账本分组 → 恢复启发式（去掉权威键优先）')
        else:
            problems.append('① 账本分组锚点未命中')
        if _JS_CHAIN_FIX in src:
            src = src.replace(_JS_CHAIN_FIX, _JS_CHAIN_ORIG)
            print('  ✓ ① 账本 grpKey 回退链 → 去掉 authGrpKey')
        else:
            problems.append('① 账本 grpKey 回退链锚点未命中')
    elif path == ENDPOINT:
        if _BE_FIX in src:
            src = src.replace(_BE_FIX, '')
            print('  ✓ ② 后端 payload → 去掉 group_order_id')
        else:
            problems.append('② 后端 payload 锚点未命中')
    elif path == GENERATOR:
        if _GEN_FIX_HEAD in src and _GEN_FIX_TAIL in src:
            i = src.index(_GEN_FIX_HEAD)
            j = src.index(_GEN_FIX_TAIL, i) + len(_GEN_FIX_TAIL)
            src = src[:i] + _GEN_ORIG + src[j:]
            print('  ✓ ③ 生成器分组 → 恢复启发式')
        else:
            problems.append('③ 生成器分组锚点未命中')
        if _GEN_CHAIN_FIX in src:
            src = src.replace(_GEN_CHAIN_FIX, _GEN_CHAIN_ORIG)
            print('  ✓ ③ 生成器 grp_key 回退链 → 去掉 auth_grp_key')
        else:
            problems.append('③ 生成器 grp_key 回退链锚点未命中')

    if problems:
        print('  ✗ %s 未回退：%s' % (path.name, '；'.join(problems)))
        return 1
    print('    长度 %d → %d' % (orig_len, len(src)))
    if dry_run:
        return 0
    bak = path.with_name(path.name + '.bak-' + time.strftime('%Y%m%d_%H%M%S'))
    shutil.copy2(path, bak)
    io.open(path, 'w', encoding='utf-8').write(src)
    print('    已留快照：%s' % bak.name)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    rc = 0
    for f in (TEMPLATE, ENDPOINT, GENERATOR):
        print('== %s' % f.name)
        rc |= _revert_file(f, a.dry_run)

    if rc:
        print('\n✗ 存在未命中锚点 ⇒ 未完整回退（请人工确认改动）')
        return 1

    if not a.dry_run:
        checks = [
            (sys.executable, '-c', 'import py_compile;py_compile.compile(%r,doraise=True)' % str(ENDPOINT)),
            (sys.executable, '-c', 'import py_compile;py_compile.compile(%r,doraise=True)' % str(GENERATOR)),
        ]
        for cmd in checks:
            r = subprocess.run(list(cmd), capture_output=True, text=True)
            print('  py_compile %s: %s' % (cmd[-1].split("'")[1].split('/')[-1],
                                           '通过 ✓' if r.returncode == 0 else '失败 ✗ ' + r.stderr[:200]))
        # 模板内联 JS 语法
        html = io.open(TEMPLATE, encoding='utf-8').read()
        import re
        blocks = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.S)
        tmp = Path('/tmp/_revert54_check.js')
        tmp.write_text('\n;\n'.join(blocks), encoding='utf-8')
        r = subprocess.run(['node', '--check', str(tmp)], capture_output=True, text=True)
        print('  node --check 模板 JS: %s' % ('通过 ✓' if r.returncode == 0 else '失败 ✗\n' + r.stderr[:300]))
    else:
        print('\n[dry-run] 未写盘 ✓')
    return 0


if __name__ == '__main__':
    sys.exit(main())
