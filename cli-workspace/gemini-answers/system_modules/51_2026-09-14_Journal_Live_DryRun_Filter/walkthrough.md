# 交易流水账本「运行模式」筛选（LIVE vs DRY-RUN）验收报告

- **日期**：2026-09-14
- **模块**：`bbt_option_seller` 页面「今日交易流水账本 (Today's Execution Journal)」
- **归档目录**：`51_2026-09-14_Journal_Live_DryRun_Filter`
- **用户指令**：今日交易流水账本 (Today's Execution Journal) 加上 LIVE vs DRY RUN 过滤

---

## 1. 交付物

| # | 交付 | 位置 |
|---|---|---|
| 1 | 账本工具条新增「模式」筛选（含 LIVE·DRY 拆分徽标） | `bbt_data_web/templates/bbt_option_seller.html` |
| 2 | 筛选判定 + 双筛选叠加 + 变更处理器 | 同上（内联 JS） |
| 3 | 空态提示 / TV 导出文案跟随筛选 | 同上 |
| 4 | 契约测试（9 条） | `PyTools/option_seller/test_journal_mode_filter.py` |

**页面上的最终形态**（工具条一行，从左到右）：

```
今日交易流水账本 (Today's Execution Journal)     类型: 全部类型 (All) [20 笔]   模式: 全部模式 (All) [LIVE 10 · DRY 10]   生成TradingView指标   全部删除
```

## 2. 实现要点

### 2.1 判定函数（与列徽标同口径）

```js
function isTradeMatchingModeFilter(trade, modeVal) {
  if (!modeVal || modeVal === 'ALL') return true;
  const isDry = !!(trade && trade.is_dry_run);
  if (modeVal === 'LIVE') return !isDry;
  if (modeVal === 'DRY') return isDry;
  return true;   // 未知值 ⇒ 不过滤
}
```

- 与账本最右「运行模式」列徽标 `${t.is_dry_run ? 'DRY' : 'LIVE'}` **同源**；
- 历史回补行 `is_dry_run` 为 NULL ⇒ 归 LIVE（与徽标一致，老数据不会自相矛盾）。

### 2.2 两个筛选 AND 叠加（唯一入口）

```js
const typeMatchedTrades = rawTrades.filter(t => isTradeMatchingFilter(t, filterVal));
const filteredTrades    = typeMatchedTrades.filter(t => isTradeMatchingModeFilter(t, modeVal));
window.__currentFilteredTrades = filteredTrades;     // ← TV 导出自动继承
```

- `#journalModeBreakdown` 徽标显示**按类型筛选后**全集的两类笔数（便于一眼看出两类各有几笔），选中某个模式时徽标变色（LIVE 绿 / DRY 灰）；
- 笔数徽标「全部」判定改为 `类型=ALL && 模式=ALL`，否则显示 `筛后 / 全部`。

### 2.3 下游自动继承

「生成 TradingView 指标」读 `window.__currentFilteredTrades` ⇒ **无需改导出逻辑**即只导出筛后的单；toast 文案改为 `【类型文案 · 模式文案】`，避免「筛了 DRY 却提示全部」。

## 3. 验收证据

### 3.1 JS 语法（整段内联脚本）

```
抽取模板内联 <script>（242,921 字符）→ node --check  ⇒ 通过 ✓
（模板内无 Jinja 变量，纯静态 HTML+JS）
```

### 3.2 新增契约测试 —— 9/9 通过

```
/usr/local/bin/python3 PyTools/option_seller/test_journal_mode_filter.py
Ran 9 tests in 0.078s — OK
```

| 测试 | 断言 |
|---|---|
| `test_select_present_with_three_options` | 下拉存在且含 `ALL`/`LIVE`/`DRY` 三选项 + `onchange` 接线 |
| `test_breakdown_badge_present` | 拆分徽标存在 |
| `test_mode_filter_is_anded_into_render_path` | `applyJournalFilterAndRender` 同时含两个 filter 且写 `__currentFilteredTrades` |
| `test_handler_defined_and_delegates` | 变更处理器委托唯一入口 |
| `test_unknown_mode_value_passthrough` | 未知值 ⇒ 不过滤 |
| `test_empty_state_message_mentions_both_filters` | 空态提示含两类筛选名 |
| `test_tv_export_inherits_mode_filter` | TV 导出走 `__currentFilteredTrades` + 文案带模式 |
| `test_predicate_and_badge_consistency`（Node 实跑） | 7 例判定表 + **列徽标 ⇔ 筛选一致性不变量** |
| `test_combined_and_semantics`（Node 实跑） | 类型 × 模式 = AND 的交集口径 |

Node 实跑判定表（真实模板函数）：

| 用例 | LIVE | DRY | ALL / 空 / 未知 | 徽标 |
|---|---|---|---|---|
| `is_dry_run=False` | ✓ | ✗ | 全通过 | LIVE |
| `is_dry_run=True` | ✗ | ✓ | 全通过 | DRY |
| 缺字段（NULL） | ✓ | ✗ | 全通过 | LIVE |
| `is_dry_run=None` | ✓ | ✗ | 全通过 | LIVE |
| `is_dry_run=0` | ✓ | ✗ | 全通过 | LIVE |
| `is_dry_run=1` | ✗ | ✓ | 全通过 | DRY |
| `is_dry_run='true'` | ✗ | ✓ | 全通过 | DRY |

### 3.3 无回归

```
/usr/local/bin/python3 PyTools/option_seller/test_journal_filter_catalog.py
Ran 11 tests in 0.103s — OK      # 类型筛选目录 / 归类 / 历史值兼容 / 徽标配色 全绿
```

### 3.4 真实页面渲染 + 与数据库对照

| 项 | 结果 |
|---|---|
| 服务端渲染 | `GET http://127.0.0.1:5005/bbt_option_seller` → HTTP 200，页面含 `journalModeFilter` 与三选项、`journalModeBreakdown` |
| headless Chrome 截图实测 | 工具条渲染为 `类型: 全部类型 (All) [20 笔]` + **`模式: 全部模式 (All) [LIVE 10 · DRY 10]`** + 两个按钮，布局单行不换行 |
| 与 DB 对照 | `order_flow_option_seller_trades` 2026-09-14：`sum(is_dry_run=1)=10`（DRY）、`=0` 者 10（LIVE）、合计 20 ⇒ **徽标 10/10 与库完全一致** |
| 数据混合实例（本筛选的存在意义） | 同日 20 笔中一半实盘一半试运行（`LIVE_FALLBACK` / Force Dry / 全局试运行所致）；9/11 全 DRY、9/8–9/9 全 LIVE |

## 4. 边界与未做

| 项 | 说明 |
|---|---|
| 后端过滤 | **不做**。当日流水量级为几十条，沿用既有「一次取回 + 前端筛」架构，零 API / 零 DB 改动 |
| 运行模式列徽标 | 未改动（本次筛选**对齐**它，而非替换它） |
| KPI 卡 / 日历的 LIVE·DRY 拆分 | 未改动（早已存在） |
| 规则手册 | **无需更新** —— 属 UI 展示/筛选实现，不构成趋势或交易决策规则（规则 11 口径） |
| 生效方式 | 模板改动需**硬刷新**（⌘⇧R）；页面路由已带 `Cache-Control: no-store`（module 50 引入） |

## 5. 回滚

```bash
cd ~/Documents/Workplace/PycharmProjects/BBTrading
# ⚠️ 本仓库几乎不纳入版本控制（`git ls-files` 仅 2 个文件，`bbt_data_web/` 与 `PyTools/` 均为 untracked）
#    ⇒ `git checkout -- <template>` **不可用**。改用模块归档里的**可复现回退脚本**（先自动留快照 → 逐字面量反向替换 → node --check 校验）：
python3 ~/.gemini/cli-workspace/gemini-answers/system_modules/52_2026-09-14_Journal_Per_Group_TV_Export/revert_module_51_52.py --dry-run    # 先看锚点命中（零写盘）
python3 ~/.gemini/cli-workspace/gemini-answers/system_modules/52_2026-09-14_Journal_Per_Group_TV_Export/revert_module_51_52.py              # 实回退（自动留 .bak-<时间戳>）
rm PyTools/option_seller/test_journal_test_journal_mode_filter.py.py   # 可选：一并移除对应契约测试
# 若要“再改回来”：用本机快照 cp bbt_data_web/templates/bbt_option_seller.html.bak-20260914_194023 → 恢复
```


## 6. 后续可选增强（未做，待用户确认）

1. 把「运行模式」也加入**类型筛选的组合记忆**（localStorage），刷新后保留组合；
2. 账本表头「运行模式」列加排序（按 LIVE / DRY 分组显示）；
3. 日历点击某日进入历史账本时，默认沿用上次的模式筛选。
