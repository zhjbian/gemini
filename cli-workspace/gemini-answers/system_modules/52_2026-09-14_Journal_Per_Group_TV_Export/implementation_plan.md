# 卖家系统：账本每组订单行内「生成TradingView指标」（作用域双入口）实施计划

- **日期**：2026-09-14
- **模块**：期权卖家系统「今日交易流水账本 (Today's Execution Journal)」（`bbt_data_web/templates/bbt_option_seller.html`）
- **归档目录**：`52_2026-09-14_Journal_Per_Group_TV_Export`
- **技术栈**：Jinja2 模板内联 JS（127.0.0.1:5005）/ 既有 `POST /api/option_seller/generate_tv_script`（**未改动**）/ Node 契约测试 / headless Chrome `--dump-dom` 实渲染断言

---

## 1. 背景与问题（用户指令引出）

用户指令：**「对每组订单加入 '生成TradingView指标' 按钮，点击生成**只包含所在组订单**的指标，参见现在的 生成TradingView指标 按钮」**。

账本表格是**两级结构**：订单组头行（`<tr class="trade-group-header-row">`，形如 `⛁ 订单-6 (1组2手)` + `⛁ 开仓条件 ↗`）＋ 其下 1–2 条批次行（第1批 40%止盈 / 第2批 75%止盈·保本）。

改造前：

| 入口 | 作用域 |
|---|---|
| 工具条「生成TradingView指标」（`#btnCopyTvPineScript`） | **当前筛选条件下的全集**（类型 × 运行模式，见模块 51） |
| —— | **没有**按组导出的入口 |

而实际复盘时经常只需要**某一个订单组**的两条腿（同一组的两批共享 same strikes / 同一入场理由），全量导出还要在 TV 里手工剔除，且容易把不同组混在同一张指标里。

## 2. 实施目标

| 目标 | 交付 |
|---|---|
| 每个订单组一个行内按钮 | 组头行在「开仓条件」右侧新增 `生成TradingView指标`（浅蓝 `.btn-tv-group`，与「开仓条件」靛蓝区分） |
| 点击只导出**本组**订单 | 组内交易取自渲染时缓存的 `window.__twinGroupsMap[grpKey].trades`（与「开仓条件」控制台**同源**） |
| **口径不漂移** | 与顶部按钮共用**唯一内核** `_generateTvPineForTradeIds()`：`POST /api/option_seller/generate_tv_script` 全仓**只有 1 个调用点**；按钮态 / 剪贴板回退 / toast / 失败还原只有一份 |
| 手动单组也有按钮 | 按钮**无条件**渲染（不挂在 `isAuto` 三元里）—— 手动组没有「开仓条件」按钮，但同样要能导出 |
| 文案可区分作用域 | toast：顶部 `已成功打包【类型 · 模式】筛选后的 N 笔…` / 组头 `已成功打包【订单-N】本组的 N 笔…` |
| 防回归 | 新增契约测试 `PyTools/option_seller/test_journal_tv_export_scopes.py`（8 条，含实渲染） |

## 3. 关键设计与依据

### 3.1 唯一内核（避免两份生成逻辑漂移）

```js
function _tvTargetDate() { … return calSelectedDate || todayKey; }          // 日期口径（历史日账本一致）
async function _generateTvPineForTradeIds(btnElem, targetTradeIds, targetDate, scopeLabel, emptyHint) {
  … fetch('/api/option_seller/generate_tv_script') …剪贴板回退… toast(scopeLabel) …按钮态还原…
}
async function copyTradingViewPineScriptForCurrentDate(btnElem) { …全集… await _generateTvPineForTradeIds(…) }
async function copyTradingViewPineScriptForGroup(btnElem, grpKeyOrElem) { …本组… await _generateTvPineForTradeIds(…) }
```

- **后端零改动**：接口本就接收 `{date, trade_ids}` ⇒ 传本组的 id 数组即可（无需新增 API / 不新增查询）；
- 「按钮态还原」沿用原顶部按钮的配色常量（`#93c5fd / #eff6ff / #1d4ed8`）⇒ 组按钮用同色系，还原逻辑天然通用。

### 3.2 组 key 与数据源：复用既有约定，不另建映射

| 项 | 采用 |
|---|---|
| 组 key | 与「开仓条件」按钮**同一约定**：`data-grpkey="${encodeURIComponent(grpKey)}"` → 入口函数内部 `decodeURIComponent` |
| 组内交易 | `window.__twinGroupsMap[grpKey].trades`（`renderHistoryTable` 渲染组头时写入，`openAutoGroupDetailModal` 也读它）⇒ **单一数据源**，不会出现「按钮导出与开仓诊断看到的组不一致」 |
| 组号 | 同 map 的 `groupNum` ⇒ toast / title 显示 `订单-N（M组K手 · X 笔）` |

### 3.3 无条件渲染（可验证）

按钮单独一个 `const tvGroupBtnHtml = …`（**不**包在 `isAuto ? … : ''` 里），在组头 `display:flex` 左簇内紧随 `${autoConditionBtnHtml}` 插入。实测佐证：当日 **10 个订单组** vs **8 个「开仓条件」按钮**（2 个手动组没有开仓条件）⇒ 组头按钮 10 个 = 组数，说明确实与「是否自动单」无关。

## 4. 改动清单

| # | 文件 | 位置 | 改动 |
|---|---|---|---|
| 1 | `bbt_data_web/templates/bbt_option_seller.html` | CSS（`.btn-entry-condition` 之后） | 新增 `.btn-tv-group` 及其 `:hover / :active / :disabled` |
| 2 | 同上 | `renderHistoryTable()` 组头渲染 | 新增 `const tvGroupBtnHtml` 并无条件插入组头左簇（含 title 说明本组组数/手数/笔数） |
| 3 | 同上 | TV 生成逻辑 | 抽出内核 `_tvTargetDate()` + `_generateTvPineForTradeIds()`；`copyTradingViewPineScriptForCurrentDate()` 改为薄封装；新增 `copyTradingViewPineScriptForGroup()` |
| 4 | `PyTools/option_seller/test_journal_tv_export_scopes.py` | 新增 | 7 条模板契约 + 1 条 headless Chrome 实渲染（组头按钮数 == 组数） |

## 5. 验收口径

| 层 | 手段 | 通过标准 |
|---|---|---|
| JS 语法 | 整段内联脚本 `node --check`（244,937 字符） | 通过 |
| 唯一入口 | 模板契约：`fetch('/api/option_seller/generate_tv_script'` 出现 **1** 次；内核函数定义 **1** 次；两入口均委托内核 | 全绿 |
| 无条件性 | 契约：`tvGroupBtnHtml` 赋值语句不含 `isAuto` | 全绿 |
| 实渲染 | headless Chrome `--dump-dom` + 计数 | `class="btn-tv-group"` 数 **==** `trade-group-header-row` 数（当日 **10 == 10**），onclick 同数；对照 `btn-entry-condition` 仅 8（2 个手动组） |
| 无回归 | `test_journal_mode_filter.py` / `test_journal_filter_catalog.py` | 9/9 · 11/11 通过 |
| 零副作用 | —— | 无 API 改动、无 DB 改动、无新增文件依赖 |

## 6. 风险与回滚

| 项 | 说明 |
|---|---|
| 风险 | 组头左簇多一个按钮（该行 `flex-wrap: wrap`，窄屏自动换行）；内核重构**行为等价**（仅把 id 计算与筛选文案移出内核，其余逻辑逐行保留） |
| 剪贴板 | 复用原内核的「`navigator.clipboard` → `execCommand` 回退」链路，未改 |
| 回滚 | ⚠️ **`git checkout` 不适用**（本仓库不跟踪 `bbt_data_web/`）⇒ 用归档内 `revert_module_51_52.py`（`--dry-run` 先看锚点；实跑会先留 `.bak` 快照再逐字面量反向替换，最后 `node --check` 校验）；新增测试文件可直接删 |
| 生效方式 | 模板改动需**硬刷新**（⌘⇧R） |
