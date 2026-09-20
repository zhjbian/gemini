#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""revert_module_51_52.py —— 把 `bbt_option_seller.html` 回退到**模块 51 + 52 之前**的形态。

为什么需要：BBTrading 仓库对此项目代码**几乎不纳入版本控制**（`git ls-files` 仅 2 个文件，
`bbt_data_web/` / `PyTools/` 均为 untracked）⇒ `git checkout -- <template>` **不可用**；
项目既有约定是就地留 `.bak-YYYYMMDD_HHMMSS` 快照。本脚本按「逐字面量反向替换」实现可复现回退，
并在写入前自动留快照、写后做校验（`node --check` + 残留标识检查）。

回退内容（= 当日两个改动模块）：
  · 模块 51（`51_2026-09-14_Journal_Live_DryRun_Filter`）：账本「运行模式」筛选 + 拆分徽标
  · 模块 52（`52_2026-09-14_Journal_Per_Group_TV_Export`）：每组订单行内「生成TradingView指标」
    （唯一内核 + 双作用域入口）

用法：
    python3 revert_module_51_52.py --dry-run      # 只报告将要替换的锚点命中情况（零写盘）
    python3 revert_module_51_52.py                # 留快照 → 回退 → 校验
"""
from __future__ import annotations

import argparse
import io
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TEMPLATE = Path('/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/'
                'bbt_data_web/templates/bbt_option_seller.html')

# ── 模块 52：唯一内核 + 双入口（当前文本 → 原始单体函数）────────────────────────────
_KERNEL_START = '    // ★ 2026-09-14（用户指令）：TradingView Pine 生成的**唯一内核** ——'
_KERNEL_END = "        '该组下没有交易流水记录，无法生成 TradingView 指标');\n    }\n"

_ORIGINAL_TV_FN = """    async function copyTradingViewPineScriptForCurrentDate(btnElem) {
      const now = new Date();
      const todayKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
      const targetDate = calSelectedDate || todayKey;

      const filteredTrades = window.__currentFilteredTrades || window.__currentRawTrades || [];
      if (filteredTrades.length === 0) {
        showToast("⚠️ 当前筛选无交易", "当前筛选条件下没有交易流水记录，无法生成 TradingView 指标");
        return;
      }

      const targetTradeIds = filteredTrades.map(t => t.id);
      const filterElem = document.getElementById('journalTypeFilter');
      const filterText = filterElem && filterElem.value !== 'ALL' ? filterElem.options[filterElem.selectedIndex].text.trim() : '全部';

      const originalHtml = btnElem ? btnElem.innerHTML : '';
      if (btnElem) {
        btnElem.disabled = true;
        btnElem.innerHTML = `<i class="fas fa-spinner fa-spin"></i> 生成中(${targetTradeIds.length}单)...`;
      }

      try {
        const resp = await fetch('/api/option_seller/generate_tv_script', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            date: targetDate,
            trade_ids: targetTradeIds
          })
        });
        const res = await resp.json();
        if (res.status === 'success' && res.pine_script) {
          const pineCode = res.pine_script;
          let copied = false;
          if (navigator.clipboard && navigator.clipboard.writeText) {
            try {
              await navigator.clipboard.writeText(pineCode);
              copied = true;
            } catch (clipErr) {
              console.warn("navigator.clipboard.writeText failed (document might not be focused), trying execCommand fallback:", clipErr);
            }
          }
          if (!copied) {
            const ta = document.createElement('textarea');
            ta.value = pineCode;
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            ta.style.top = '0';
            document.body.appendChild(ta);
            ta.focus();
            ta.select();
            try {
              document.execCommand('copy');
              copied = true;
            } catch (e) {
              console.error("execCommand fallback failed:", e);
            }
            document.body.removeChild(ta);
          }

          showToast(`已复制 ${targetDate} TradingView 指标！`, `已成功打包【${filterText}】筛选后的 ${targetTradeIds.length} 笔交易，请在 TV Pine Editor 粘贴保存`);
          if (btnElem) {
            btnElem.style.borderColor = '#10b981';
            btnElem.style.background = '#ecfdf5';
            btnElem.style.color = '#059669';
            btnElem.innerHTML = `<i class="fas fa-check"></i> 已复制 Pine (${targetTradeIds.length}单)!`;
            setTimeout(() => {
              btnElem.style.borderColor = '#93c5fd';
              btnElem.style.background = '#eff6ff';
              btnElem.style.color = '#1d4ed8';
              btnElem.innerHTML = originalHtml;
              btnElem.disabled = false;
            }, 2000);
          }
        } else {
          alert("生成 TradingView 代码失败: " + (res.message || '无交易数据'));
          if (btnElem) {
            btnElem.innerHTML = originalHtml;
            btnElem.disabled = false;
          }
        }
      } catch (err) {
        alert("请求生成 TradingView 代码异常: " + err);
        if (btnElem) {
          btnElem.innerHTML = originalHtml;
          btnElem.disabled = false;
        }
      }
    }
"""

# ── 逐字面量反向替换：(说明, 新文本, 旧文本) ──────────────────────────────────────
EDITS: list[tuple[str, str, str]] = [
    # ── 模块 52 ──
    ('52 · 组头按钮 CSS',
     """    /* ★ 2026-09-14（用户指令）：账本每组订单行内「生成TradingView指标」按钮 ——
       与顶部同名按钮同色系（浅蓝），但只导出**本组**订单；与「开仓条件」并排（靛蓝）以区分功能 ✓ */
    .btn-tv-group {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      background: #eff6ff;
      color: #1d4ed8;
      border: 1px solid #93c5fd;
      padding: 2px 8px;
      border-radius: 5px;
      font-size: 0.72rem;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.16s ease;
      box-shadow: 0 1px 2px rgba(29, 78, 216, 0.08);
      outline: none;
      white-space: nowrap;
    }
    .btn-tv-group:hover {
      background: #dbeafe;
      border-color: #60a5fa;
      color: #1e40af;
      transform: translateY(-1px);
      box-shadow: 0 2px 5px rgba(29, 78, 216, 0.18);
    }
    .btn-tv-group:active { transform: translateY(0); }
    .btn-tv-group:disabled { opacity: 0.75; cursor: default; transform: none; }
""", ''),

    ('52 · 组头按钮模板',
     """
          // ★ 2026-09-14（用户指令）：**每组订单**一个「生成TradingView指标」按钮 ——
          //   与顶部同名按钮同色系；点击只导出**本组**订单（复用同一生成内核 ✓），
          //   组 key 走与「开仓条件」相同的 encodeURIComponent / 内部 decode 约定 ✓
          const tvGroupBtnHtml = `
            <button class="btn-tv-group" data-grpkey="${encodeURIComponent(grpKey)}" onclick="copyTradingViewPineScriptForGroup(this, this.dataset.grpkey)" title="只把【订单-${groupNum}】本组（${grpGroups}组${grpHands}手 · ${tradesInGroup.length} 笔）生成 TradingView Pine Script 指标并复制到剪切板">
              <i class="fas fa-chart-line"></i>
              <span>生成TradingView指标</span>
            </button>
          `;
""", ''),
    ('52 · 组头插入按钮', """                    ${autoConditionBtnHtml}
                    ${tvGroupBtnHtml}
""", """                    ${autoConditionBtnHtml}
"""),

    # ── 模块 51 ──
    ('51 · 运行模式筛选框',
     """
          <!-- ★ 2026-09-14（用户指令）：运行模式 Filter（LIVE / DRY-RUN）——
               与「类型」筛选**叠加**（AND）；口径与账本「运行模式」列徽标严格一致，
               避免出现「列显示 LIVE 却被 LIVE 筛选排除」的自相矛盾 ✓ -->
          <div style="display: inline-flex; align-items: center; gap: 6px; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 3px 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.03);">
            <label for="journalModeFilter" style="font-size: 0.76rem; font-weight: 700; color: #475569; margin: 0; display: inline-flex; align-items: center; gap: 4px; cursor: pointer;">
              <i class="fas fa-bolt" style="color: #b45309;"></i> 模式:
            </label>
            <select id="journalModeFilter" onchange="onJournalModeFilterChange()" style="border: none; background: transparent; font-size: 0.76rem; font-weight: 600; color: #0f172a; outline: none; cursor: pointer; padding: 1px 2px;">
              <option value="ALL">全部模式 (All)</option>
              <option value="LIVE">💵 LIVE（实盘）</option>
              <option value="DRY">🧪 DRY-RUN（试运行）</option>
            </select>
            <span id="journalModeBreakdown" style="font-size: 0.70rem; background: #f1f5f9; color: #475569; padding: 1px 7px; border-radius: 9999px; font-weight: 700; white-space: nowrap;" title="按当前「类型」筛选后的全集拆分：LIVE 实盘单 / DRY-RUN 试运行单">LIVE 0 · DRY 0</span>
          </div>
""", ''),
    ('51 · 模式判定函数',
     """
    // ★ 2026-09-14（用户指令）：运行模式筛选（LIVE / DRY-RUN）——
    //   判定口径与账本「运行模式」列徽标严格一致（`t.is_dry_run ? 'DRY' : 'LIVE'`），
    //   因此绝不会出现「列显示 LIVE、却被 LIVE 筛选排除」的自相矛盾 ✓
    //   （is_dry_run 为 NULL/undefined 的历史行 ⇒ 归 LIVE，与列徽标同口径 ✓）
    function isTradeMatchingModeFilter(trade, modeVal) {
      if (!modeVal || modeVal === 'ALL') return true;
      const isDry = !!(trade && trade.is_dry_run);
      if (modeVal === 'LIVE') return !isDry;
      if (modeVal === 'DRY') return isDry;
      return true;   // 未知值 ⇒ 不过滤（不静默命中空集 ✓）
    }
""", ''),
    ('51 · 双筛选叠加',
     """      const modeElem = document.getElementById('journalModeFilter');
      const modeVal = modeElem ? modeElem.value : 'ALL';

      // ★ 两个筛选**叠加**（AND）：类型 × 运行模式 ✓
      const typeMatchedTrades = rawTrades.filter(t => isTradeMatchingFilter(t, filterVal));
      const filteredTrades = typeMatchedTrades.filter(t => isTradeMatchingModeFilter(t, modeVal));
      window.__currentFilteredTrades = filteredTrades;

      // 运行模式拆分徽标：按**类型筛选后**的全集统计 LIVE / DRY 各几笔 ✓
      const modeBadge = document.getElementById('journalModeBreakdown');
      if (modeBadge) {
        const _nDry = typeMatchedTrades.filter(t => !!(t && t.is_dry_run)).length;
        const _nLive = typeMatchedTrades.length - _nDry;
        modeBadge.innerText = `LIVE ${_nLive} · DRY ${_nDry}`;
        const _modeActive = (modeVal === 'LIVE' || modeVal === 'DRY');
        modeBadge.style.background = _modeActive ? (modeVal === 'LIVE' ? '#ecfdf5' : '#f1f5f9') : '#f1f5f9';
        modeBadge.style.color = _modeActive ? (modeVal === 'LIVE' ? '#047857' : '#475569') : '#475569';
      }""",
     """      const filteredTrades = rawTrades.filter(t => isTradeMatchingFilter(t, filterVal));
      window.__currentFilteredTrades = filteredTrades;"""),
    ('51 · 计数徽标「全部」判定',
     """        const allFiltersOff = (filterVal === 'ALL' && modeVal === 'ALL');
        if (allFiltersOff) {""",
     """        if (filterVal === 'ALL') {"""),
    ('51 · 变更处理器',
     """
    // ★ 2026-09-14（用户指令）：运行模式下拉变更 ⇒ 与类型筛选同一条渲染路径 ✓
    function onJournalModeFilterChange() {
      applyJournalFilterAndRender();
    }
""", ''),
    ('51 · 空态提示语',
     """        const modeElem = document.getElementById('journalModeFilter');
        const modeVal = modeElem ? modeElem.value : 'ALL';
        const _activeNames = [];
        if (filterVal !== 'ALL') _activeNames.push('类型');
        if (modeVal !== 'ALL') _activeNames.push('运行模式');
        const msg = _activeNames.length === 0 ? '暂无交易记录'
                  : `当前${_activeNames.join(' + ')}筛选下暂无交易记录`;""",
     """        const msg = filterVal === 'ALL' ? '暂无交易记录' : '当前类型筛选下暂无交易记录';"""),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='只报告锚点命中（零写盘）')
    a = ap.parse_args()

    html = io.open(TEMPLATE, encoding='utf-8').read()
    orig_len = len(html)
    problems: list[str] = []

    for name, new, old in EDITS:
        n = html.count(new)
        if n != 1:
            problems.append('%s: 锚点命中 %d 次（期望 1）' % (name, n))
        else:
            html = html.replace(new, old)
            print('  ✓ %s' % name)

    # 内核块（用标记切片，避免粘贴长文本）
    if _KERNEL_START in html and _KERNEL_END in html:
        i = html.index(_KERNEL_START)
        j = html.index(_KERNEL_END, i) + len(_KERNEL_END)
        html = html[:i] + _ORIGINAL_TV_FN + html[j:]
        print('  ✓ 52 · 唯一内核 → 原始单体函数')
    else:
        problems.append('52 · 内核块标记未命中（起=%s 止=%s）' % (_KERNEL_START in html, _KERNEL_END in html))

    if problems:
        print('\n✗ 回退未执行（锚点不匹配，模板可能已被改动）：')
        for p in problems:
            print('   · ' + p)
        return 1

    left = [t for t in ('journalModeFilter', 'journalModeBreakdown', 'isTradeMatchingModeFilter',
                        'onJournalModeFilterChange', 'btn-tv-group', 'tvGroupBtnHtml',
                        '_generateTvPineForTradeIds', 'copyTradingViewPineScriptForGroup')
            if t in html]
    if left:
        print('\n✗ 回退后仍残留标识：%s' % left)
        return 1
    print('\n  校验：残留标识 = 0 ✓   长度 %d → %d' % (orig_len, len(html)))

    if a.dry_run:
        print('  [dry-run] 未写盘 ✓')
        return 0

    bak = TEMPLATE.with_name(TEMPLATE.name + '.bak-' + time.strftime('%Y%m%d_%H%M%S'))
    shutil.copy2(TEMPLATE, bak)
    print('  已留快照：%s' % bak.name)
    io.open(TEMPLATE, 'w', encoding='utf-8').write(html)

    blocks = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.S)
    tmp = Path('/tmp/_revert_check.js')
    tmp.write_text('\n;\n'.join(blocks), encoding='utf-8')
    r = subprocess.run(['node', '--check', str(tmp)], capture_output=True, text=True)
    print('  node --check：%s' % ('通过 ✓' if r.returncode == 0 else '失败 ✗\n' + r.stderr[:400]))
    return r.returncode


if __name__ == '__main__':
    sys.exit(main())
