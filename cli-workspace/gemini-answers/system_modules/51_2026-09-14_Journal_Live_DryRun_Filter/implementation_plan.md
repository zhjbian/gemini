# 卖家系统：交易流水账本「运行模式」筛选（LIVE vs DRY-RUN）实施计划

- **日期**：2026-09-14
- **模块**：期权卖家系统「今日交易流水账本 (Today's Execution Journal)」（`bbt_data_web/templates/bbt_option_seller.html`）
- **归档目录**：`51_2026-09-14_Journal_Live_DryRun_Filter`
- **技术栈**：Python 3.11 / Flask + Jinja2 模板内联 JS（127.0.0.1:5005）/ MySQL `bb_trade`.`order_flow_option_seller_trades`（只读）/ Node 实跑契约测试 / headless Chrome 渲染核对

---

## 1. 背景与问题（用户指令引出）

用户指令：**「今日交易流水账本 (Today's Execution Journal) 加上 LIVE vs DRY RUN 过滤」**。

账本数据源是 `order_flow_option_seller_trades`，其中 **`is_dry_run` 是「单笔级」真相**：以下三种情形都会让**同一天的流水里混着两类口径**——

| 情形 | 机制 | 落库标记 |
|---|---|---|
| 全局 DRY-RUN 模式 | `option_seller_manager.dry_run = True`（页面模式开关） | `is_dry_run=True`，`entry_evidence.dry_reason='GLOBAL_DRY_RUN'` |
| Force Dry 触发命中 | 页面多选把某机制降级为试运行（仅 LIVE 模式可用） | `is_dry_run=True`，`dry_reason='FORCE_DRY_TRIGGER'` |
| LIVE 开仓失败自动降级 | 券商报错 ⇒ 复用单笔级 dry-run 机制记录该次触发 | `is_dry_run=True`，`dry_reason='LIVE_FALLBACK'` |

实测（本次改动前）：

| 日期 | LIVE | DRY | 合计 |
|---|---|---|---|
| 2026-09-14 | **10** | **10** | 20 |
| 2026-09-11 | 0 | 4 | 4 |
| 2026-09-09 | 4 | 0 | 4 |
| 2026-09-08 | 10 | 0 | 10 |

⇒ **混合是常态**（9/14 恰好一半一半）。而此前账本**只能逐行看最右「运行模式」列徽标人工挑**：账户级 KPI 卡与日历早已按 LIVE / DRY 拆分（`trades.filter(t => !t.is_dry_run)`），**唯独账本表没有对应的筛选**。

## 2. 实施目标

| 目标 | 交付 |
|---|---|
| 账本可按运行模式筛选 | 新增下拉 `journalModeFilter`：`全部模式 (All)` / `💵 LIVE（实盘）` / `🧪 DRY-RUN（试运行）` |
| **口径与列徽标零冲突** | 判定复用列徽标的同一表达式语义（`t.is_dry_run ? 'DRY' : 'LIVE'`）⇒ 不允许出现「列显示 LIVE 却被 LIVE 筛选排除」 |
| 与「类型」筛选协同 | 两个筛选 **AND 叠加**（类型 × 运行模式），改任一下拉都走同一条渲染路径 |
| 拆分可见 | 新增徽标 `journalModeBreakdown`：按「类型筛选后」的全集显示 `LIVE n · DRY m` |
| 导出/提示一致 | 「生成 TradingView 指标」用的 `window.__currentFilteredTrades` 自动继承两种筛选；导出 toast 文案带上模式；空表提示语区分是哪几个筛选 |
| 防回归 | 新增契约测试 `PyTools/option_seller/test_journal_mode_filter.py`（模板契约 + Node 实跑 + 与列徽标一致性不变量） |

## 3. 关键设计与依据

### 3.1 口径唯一：以「列徽标」为基准，而非另立一套判断

账本每行的运行模式徽标模板（改动前已存在）：

```js
${t.is_dry_run ? 'DRY' : 'LIVE'}
```

新增判定**显式对齐**该表达式，并把「一致性」写成测试不变量（从模板正则抽取徽标表达式，在 Node 里逐案断言 `badge==='LIVE' ⇔ isTradeMatchingModeFilter(t,'LIVE')`）：

```js
function isTradeMatchingModeFilter(trade, modeVal) {
  if (!modeVal || modeVal === 'ALL') return true;
  const isDry = !!(trade && trade.is_dry_run);
  if (modeVal === 'LIVE') return !isDry;
  if (modeVal === 'DRY') return isDry;
  return true;   // 未知值 ⇒ 不过滤（不静默命中空集 ✓）
}
```

**历史行口径**：`is_dry_run` 为 `NULL/undefined`（早期回补行）⇒ 归 **LIVE** —— 与列徽标同口径（`!!undefined === false` ⇒ 徽标也是 LIVE），因此老数据不会出现「筛选与显示互相矛盾」。

### 3.2 叠加而非替代（AND）

```js
const typeMatchedTrades = rawTrades.filter(t => isTradeMatchingFilter(t, filterVal));
const filteredTrades    = typeMatchedTrades.filter(t => isTradeMatchingModeFilter(t, modeVal));
window.__currentFilteredTrades = filteredTrades;
```

组合示例（用户实际会用的）：类型=`🤖 全部自动单` + 模式=`LIVE` ⇒ 只看**实盘的自动单**，一次点击即可把试运行与手动单全部滤掉。

### 3.3 唯一入口 ⇒ 下游功能自动继承

`applyJournalFilterAndRender()` 是账本筛选的**唯一入口**，两个下拉与数据刷新都汇入它；`window.__currentFilteredTrades` 亦只在此写入。因此：

- **生成 TradingView 指标**（`copyTradingViewPineScriptForCurrentDate`）读的正是 `__currentFilteredTrades` ⇒ 自动只导出筛后的单（无需改导出逻辑）；
- 导出 toast 文案追加模式名（`类型文案 · 模式文案`），避免「筛了 DRY 却提示全部」的误读。

### 3.4 未知值不过滤（沿用类型筛选的既有教训）

类型筛选在 2026-09-13 因历史值消失而「静默命中空集」，故引入了 legacyMap 回落。运行模式筛选虽只有三个值，仍按同一原则处理：**未知值 ⇒ 全通过**（宁可多显示，不可静默空表），并写成测试。

## 4. 改动清单

| # | 文件 | 位置 | 改动 |
|---|---|---|---|
| 1 | `bbt_data_web/templates/bbt_option_seller.html` | 账本标题栏（原类型筛选框右侧） | 新增模式筛选框：`label[for=journalModeFilter]` + `select#journalModeFilter`（含 `onchange="onJournalModeFilterChange()"`）+ 徽标 `#journalModeBreakdown`；样式复用类型筛选框（同一套内联样式，浅色主题） |
| 2 | 同上 | `isTradeMatchingFilter` 之后 | 新增 `isTradeMatchingModeFilter(trade, modeVal)` |
| 3 | 同上 | `applyJournalFilterAndRender()` | 读取 `modeVal`；两级 filter AND；更新 `#journalModeBreakdown`（按类型筛选后全集统计 `LIVE n · DRY m`，选中模式时徽标变色）；计数徽标「全部」判定改为 `filterVal==='ALL' && modeVal==='ALL'` |
| 4 | 同上 | `onJournalTypeFilterChange` 之后 | 新增 `onJournalModeFilterChange()` ⇒ 委托 `applyJournalFilterAndRender()` |
| 5 | 同上 | `renderHistoryTable()` 空态文案 | 提示语按实际生效的筛选拼装（`当前类型 + 运行模式筛选下暂无交易记录`） |
| 6 | 同上 | TV 导出文案 | `filterText = 类型文案 · 模式文案` |
| 7 | `PyTools/option_seller/test_journal_mode_filter.py` | 新增 | 9 条契约测试（见 §5） |

## 5. 验收口径

| 层 | 手段 | 通过标准 |
|---|---|---|
| JS 语法 | 抽取模板内联脚本 `node --check` | 通过 |
| 行为（Node 实跑真实函数） | `test_journal_mode_filter.py` | 7 例判定表全对；`ALL/空值/未知值` 全通过；**列徽标 ⇔ LIVE/DRY 筛选一致性**逐案成立 |
| 模板契约 | 同上（静态断言） | 三选项存在、接线正确、`applyJournalFilterAndRender` 同时含两个 filter、TV 导出继承路径存在 |
| 无回归 | `PyTools/option_seller/test_journal_filter_catalog.py` | 11/11 通过 |
| 真实渲染 | headless Chrome 截图 + 与 DB 对照 | 工具条出现 `模式: 全部模式 (All)` 与徽标 `LIVE 10 · DRY 10`，与当日 DB（10 LIVE / 10 DRY）一致 |

## 6. 风险与回滚

| 项 | 说明 |
|---|---|
| 风险 | 纯前端筛选（数据量 = 当日流水，量级几十条）⇒ 不引入后端过滤，**不改任何 API / DB 结构**；唯一副作用是工具条多一个控件（该行 `flex-wrap: wrap`，窄屏自动换行） |
| 误伤风险 | 运行模式列徽标、KPI 卡拆分、日历拆分逻辑**均未触碰** |
| 回滚 | ⚠️ **`git checkout` 不适用**（本仓库不跟踪 `bbt_data_web/`）⇒ 用归档内 `revert_module_51_52.py`（`--dry-run` 先看锚点；实跑会先留 `.bak` 快照再逐字面量反向替换，最后 `node --check` 校验）；新增测试文件可直接删除 |
| 生效方式 | 模板改动需**硬刷新**（⌘⇧R） |
