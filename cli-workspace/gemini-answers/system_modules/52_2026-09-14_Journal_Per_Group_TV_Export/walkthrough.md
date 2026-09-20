# 账本每组订单行内「生成TradingView指标」验收报告

- **日期**：2026-09-14
- **模块**：`bbt_option_seller` 页面「今日交易流水账本 (Today's Execution Journal)」
- **归档目录**：`52_2026-09-14_Journal_Per_Group_TV_Export`
- **用户指令**：对每组订单加入「生成TradingView指标」按钮，点击生成只包含所在组订单的指标，参见现在的 生成TradingView指标 按钮

---

## 1. 交付物

| # | 交付 | 位置 |
|---|---|---|
| 1 | 组头行内按钮（浅蓝 `.btn-tv-group`，位于「开仓条件」右侧） | `bbt_data_web/templates/bbt_option_seller.html` |
| 2 | TV 生成**唯一内核** + 两个作用域入口 | 同上（内联 JS） |
| 3 | 契约测试（8 条，含 headless Chrome 实渲染） | `PyTools/option_seller/test_journal_tv_export_scopes.py` |

**页面形态**（每个订单组头行）：

```
⛁ 订单-9 (1组2手)   [⚙ 开仓条件 ↗]   [📈 生成TradingView指标]       组合状态: ✅双批全胜   合计盈亏: +$16.00
   └─ #15 自动/平衡日边界  SPY0914C-766+768 …
   └─ #16 自动/平衡日边界  SPY0914C-766+768 …
```

## 2. 实现要点

### 2.1 唯一内核（两个作用域共用一份实现）

```js
async function _generateTvPineForTradeIds(btnElem, targetTradeIds, targetDate, scopeLabel, emptyHint) {
  // fetch POST /api/option_seller/generate_tv_script → 剪贴板(clipboard→execCommand 回退)
  // → toast(scopeLabel) → 按钮态「已复制 Pine (N单)!」2s 后还原 / 失败还原
}
async function copyTradingViewPineScriptForCurrentDate(btnElem) {  // 顶部：当前筛选全集
  …await _generateTvPineForTradeIds(btnElem, filteredTrades.map(t=>t.id), _tvTargetDate(),
      `【${filterText}】筛选后的`, '当前筛选条件下没有交易流水记录…');
}
async function copyTradingViewPineScriptForGroup(btnElem, grpKeyOrElem) {   // 组头：仅本组
  let grpKey = …dataset.grpkey…; try { grpKey = decodeURIComponent(grpKey); } catch(e) {}
  const g = (window.__twinGroupsMap || {})[grpKey];
  await _generateTvPineForTradeIds(btnElem, (g && g.trades || []).map(t=>t.id), _tvTargetDate(),
      (g && g.groupNum) ? `【订单-${g.groupNum}】本组的` : '该组的', '该组下没有交易流水记录…');
}
```

要点：
- **后端零改动** —— 既有接口本就收 `{date, trade_ids}`，组导出只是传更小的 id 集；
- **唯一调用点** —— 生成接口在模板里只出现 1 次（测试锁定），两个作用域口径不可能漂移；
- **组数据与「开仓条件」控制台同源** —— 都读 `window.__twinGroupsMap`；
- **无条件渲染** —— 手动单组没有「开仓条件」按钮，但同样有导出按钮。

### 2.2 组头按钮（渲染产物实录）

```html
<span class="trade-group-tag">⛁ 订单-9 (1组2手)</span>
<button class="btn-tv-group" data-grpkey="1007918879655"
        onclick="copyTradingViewPineScriptForGroup(this, this.dataset.grpkey)"
        title="只把【订单-9】本组（1组2手 · 2 笔）生成 TradingView Pine Script 指标并复制到剪切板">
  <i class="fas fa-chart-line"></i> <span>生成TradingView指标</span>
</button>
```

## 3. 验收证据

### 3.1 契约测试 8/8 通过（2.6–3.1s）

```
/usr/local/bin/python3 PyTools/option_seller/test_journal_tv_export_scopes.py
Ran 8 tests in 3.088s — OK
```

| 测试 | 断言 |
|---|---|
| `test_single_api_call_site` | `fetch('/api/option_seller/generate_tv_script'` 在模板中**恰好 1 处**（唯一内核） |
| `test_kernel_defined_once` | `_generateTvPineForTradeIds` / `_tvTargetDate` 各定义 1 次 |
| `test_both_entry_points_delegate_to_kernel` | 顶部入口与组入口**都**委托内核 |
| `test_group_entry_uses_same_group_source_as_condition_console` | 组入口读 `window.__twinGroupsMap` + `decodeURIComponent` + 与「开仓条件」同款 `data-grpkey` 约定 |
| `test_group_button_is_unconditional` | `tvGroupBtnHtml` 赋值语句**不含 `isAuto`**，且组头确有 `${tvGroupBtnHtml}` |
| `test_group_button_style_present` | `.btn-tv-group {` CSS 与 `class="btn-tv-group"` 均在 |
| `test_scope_label_distinguishes_scopes` | 两个 toast 文案（全集 vs 本组）均存在 |
| `test_every_group_has_button`（**实渲染**） | headless Chrome `--dump-dom`：`btn-tv-group` 数 **==** 订单组头行数 |

### 3.2 实渲染计数（2026-09-14 当日数据）

| 计数项 | 实测 |
|---|---|
| `class="trade-group-header-row"`（订单组数） | **10** |
| `class="btn-tv-group"`（新按钮） | **10** ⇒ 每组都有 ✓ |
| 组入口 onclick 数 | **10** ✓ |
| 对照 `class="btn-entry-condition"`（开仓条件，仅自动组） | **8** ⇒ 2 个手动组没有开仓条件，但**同样有导出按钮** ✓（证实无条件性） |

### 3.3 无回归 + 语法

| 项 | 结果 |
|---|---|
| `test_journal_mode_filter.py`（运行模式筛选） | **9/9 通过** |
| `test_journal_filter_catalog.py`（类型筛选目录） | **11/11 通过** |
| 整段内联 JS `node --check`（244,937 字符） | 通过 |

### 3.4 测试对宿主环境的安全性

实渲染用 `--user-data-dir=<tempdir>` 独立 profile，并在读到 `</html>` 后**按进程组 SIGKILL**（`os.killpg`）—— 既避免 `--dump-dom` 后 Chrome 不退出导致的挂起（首版 90s 超时，已修），也**不触碰用户正在使用的 Chrome**；测试结束 profile 目录清理，实测无残留进程。

## 4. 边界与未做

| 项 | 说明 |
|---|---|
| 后端 | **未改**：无新增 API、无 DB 读写、无新查询 |
| 顶部按钮行为 | 与改造前**完全一致**（仍是「当前筛选全集」，含模块 51 的运行模式筛选文案） |
| 组内「批次」粒度 | 未做（用户要求「每组订单」= 订单组；批次的取舍由用户自行在组内裁剪——生成的是本组全部腿） |
| 规则手册 | **无需更新**（UI 导出作用域，非决策规则） |
| 生效方式 | 模板改动需**硬刷新**（⌘⇧R） |

## 5. 回滚

```bash
cd ~/Documents/Workplace/PycharmProjects/BBTrading
# ⚠️ 本仓库几乎不纳入版本控制（git ls-files 仅 2 个文件，bbt_data_web/ 与 PyTools/ 均为 untracked）
#    ⇒ `git checkout -- <template>` **不可用**。改用归档内**可复现回退脚本**（先留快照 → 逐字面量反向替换 → node --check 校验）：
python3 ~/.gemini/cli-workspace/gemini-answers/system_modules/52_2026-09-14_Journal_Per_Group_TV_Export/revert_module_51_52.py --dry-run    # 先看锚点命中（零写盘）
python3 ~/.gemini/cli-workspace/gemini-answers/system_modules/52_2026-09-14_Journal_Per_Group_TV_Export/revert_module_51_52.py              # 实回退（自动留 .bak-<时间戳>）
rm PyTools/option_seller/test_journal_tv_export_scopes.py   # 可选：一并移除对应契约测试
# 想再改回来：cp bbt_data_web/templates/bbt_option_seller.html.bak-20260914_194023 …
```

## 6. 后续可选（未做，待确认）

1. 组内**单批次**导出（只导第 1 批或第 2 批）；
2. 支持**多组勾选**后一次导出（表头加复选框 + 批量按钮）；
3. 导出成功后把 tv script 的入口价/止盈止损线也写入组头 tooltip，便于直接核对 Pine 参数。
