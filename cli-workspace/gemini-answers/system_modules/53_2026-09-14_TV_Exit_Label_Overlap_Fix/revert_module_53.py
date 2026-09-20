#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""revert_module_53.py —— 回退「TradingView 出场标签防重叠」修复（模块 53）。

为什么需要：BBTrading 仓库对此项目代码**几乎不纳入版本控制**（`bbt_data_web/` / `PyTools/`
均为 untracked）⇒ 没有 `git checkout` 可用；项目约定是就地留 `.bak-YYYYMMDD_HHMMSS` 快照。
本脚本按「逐字面量反向替换」实现可复现回退，写前自动留快照、写后 `py_compile` 校验。

回退内容（= 2026-09-14 模块 53 的三处改动）：
  ① 后端：cluster 非代表成员**恢复**为「挂个体标签」（回退后双腿同时出场会再次叠字 ✗）；
  ② Pine：删除 `exitSpotsDrawn` 声明与 clear；
  ③ Pine：出场标签判据**恢复**为旧的「毫秒精确相等」去重（并把 label y 的 `+ yNudge` 去掉）。

⚠️ 只有在确认新逻辑有问题时才回退 —— 旧逻辑正是用户报障的成因。

用法：
    python3 revert_module_53.py --dry-run    # 只报告锚点命中（零写盘）
    python3 revert_module_53.py              # 留快照 → 回退 → py_compile 校验
"""
from __future__ import annotations

import argparse
import io
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path('/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/'
              'PyTools/trading_view/tv_option_seller_trades.py')

# ── ① 后端：cluster 成员标签 ─────────────────────────────────────────────────
_MEMBER_FIX_HEAD = "            # ★ 2026-09-14（用户报障「止损的两个 label overlap 了」）："
_MEMBER_FIX_TAIL = "                item['label_exit'] = ''\n"
_MEMBER_ORIG = """            # First item gets the unified cluster label, remaining items in cluster get their individual label as fallback
            cluster[0]['label_exit'] = cluster_text
            for item in cluster[1:]:
                item_be = 'BREAKEVEN' in item.get('status', '') or abs(item['pnl']) < 0.01
                item_title = "保本" if item_be else ("止盈" if item['pnl'] > 0 else "止损")
                item_pnl_str = f"+${item['pnl']:.2f}" if item['pnl'] > 0 else (f"-${abs(item['pnl']):.2f}" if item['pnl'] < 0 else "$0.00")
                item['label_exit'] = f"[G{item['g_idx']}-T{item['tranche']}] {item_title} {item_pnl_str}\\\\n{item['t_close'][:5]} | {item['close_spot']:.2f}"
"""

# ── ② Pine：数组声明 / 清空 ─────────────────────────────────────────────────
_DECL_FIX = '        "var exitSpotsDrawn = array.new<float>()",   # ★ 与 exitTimesDrawn 同步 push，供「近邻去重/错位」判据 ✓\n'
_CLEAR_FIX = '        "    array.clear(exitSpotsDrawn)",\n'

# ── ③ Pine：出场标签判据块 ───────────────────────────────────────────────────
_GUARD_FIX_HEAD = '        "                // Exit Label (半透明质感止盈 / 止损 / 保本，带指向 K 线点位的位置指示针)",'
_GUARD_FIX_TAIL = "ylabel='平仓出场详情与最终实现盈亏')\"\n"
_GUARD_FIX_TAIL_ALT = '平仓出场详情与最终实现盈亏\')"\n'
_GUARD_ORIG = """        "                // Exit Label (半透明质感止盈 / 止损 / 保本，带指向 K 线点位的位置指示针)",
        "                if tr.close_time_ms > tr.open_time_ms and tr.label_exit != ''",
        "                    if not array.includes(exitTimesDrawn, tr.close_time_ms)",
        "                        array.push(exitTimesDrawn, tr.close_time_ms)",
        "                        string exitStyle = isLoss ? label.style_label_up : label.style_label_down",
        "                        color exitBg = isBreakeven ? color.new(colBe, transpBe) : (isWin ? color.new(colWin, transpWin) : color.new(colLoss, transpLoss))",
        "                        color exitText = isBreakeven ? txtColBe : (isWin ? txtColWin : txtColLoss)",
        "                        label.new(x=tr.close_time_ms, y=tr.close_spot, text=tr.label_exit, xloc=xloc.bar_time, yloc=yloc.price, style=exitStyle, color=exitBg, textcolor=exitText, size=size.small, tooltip='平仓出场详情与最终实现盈亏')"
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    src = io.open(TARGET, encoding='utf-8').read()
    orig_len = len(src)
    problems: list[str] = []

    # ① cluster 成员标签
    if _MEMBER_FIX_HEAD in src and _MEMBER_FIX_TAIL in src:
        i = src.index(_MEMBER_FIX_HEAD)
        j = src.index(_MEMBER_FIX_TAIL, i) + len(_MEMBER_FIX_TAIL)
        src = src[:i] + _MEMBER_ORIG + src[j:]
        print('  ✓ ① cluster 成员标签 → 恢复个体标签')
    else:
        problems.append('① cluster 成员标签锚点未命中')

    # ② 数组声明 / 清空
    for name, block in (('② exitSpotsDrawn 声明', _DECL_FIX), ('② array.clear(exitSpotsDrawn)', _CLEAR_FIX)):
        if block in src:
            src = src.replace(block, '')
            print('  ✓ %s → 删除' % name)
        else:
            problems.append('%s 锚点未命中' % name)

    # ③ 出场标签判据块
    if _GUARD_FIX_HEAD in src:
        i = src.index(_GUARD_FIX_HEAD)
        j = src.index(_GUARD_FIX_TAIL_ALT, i) + len(_GUARD_FIX_TAIL_ALT)
        src = src[:i] + _GUARD_ORIG + src[j:]
        print('  ✓ ③ 出场标签判据 → 恢复「毫秒精确相等」旧口径')
    else:
        problems.append('③ 出场标签判据块锚点未命中')

    if problems:
        print('\n✗ 回退未执行（锚点不匹配，文件可能已被改动）：')
        for p in problems:
            print('   · ' + p)
        return 1

    if 'exitSpotsDrawn' in src or 'yNudge' in src:
        print('\n✗ 回退后仍残留新逻辑标识（exitSpotsDrawn / yNudge）')
        return 1
    if "item['label_exit'] = f\"[G{item['g_idx']}-T{item['tranche']}]" not in src:
        print('\n✗ ① 未正确恢复个体标签赋值')
        return 1
    print('\n  校验：残留标识 = 0 ✓   长度 %d → %d' % (orig_len, len(src)))

    if a.dry_run:
        print('  [dry-run] 未写盘 ✓')
        return 0

    bak = TARGET.with_name(TARGET.name + '.bak-' + time.strftime('%Y%m%d_%H%M%S'))
    shutil.copy2(TARGET, bak)
    print('  已留快照：%s' % bak.name)
    io.open(TARGET, 'w', encoding='utf-8').write(src)

    r = subprocess.run([sys.executable, '-m', 'py_compile', str(TARGET)], capture_output=True, text=True)
    print('  py_compile：%s' % ('通过 ✓' if r.returncode == 0 else '失败 ✗\n' + r.stderr[:400]))
    return r.returncode


if __name__ == '__main__':
    sys.exit(main())
