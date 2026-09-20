# 期权卖家「当日方向抑制 → 自动降级 DRY-RUN 单」验收报告 (Walkthrough)

- **日期**：2026-09-17（PT）
- **归属模块**：**M09. Option Seller 自动化交易引擎与开仓仲裁系统**（能力域 = 开仓仲裁 / 执行降级通道）
- **用户指令原文**：「在页面顶部添加一个基于方向的抑制自动单的选项，某些天，我会选择，让自动单**绝对不开**空仓或多仓；如果某天某个方向被抑制，则开仓成 **DRY run 单**」
- **结论**：**已交付并验收通过** —— 顶部工具条三态实测正常；契约测试 **15/15 PASS**；LIVE 端到端实测「抑制方向**券商调用 0 次**、落 `DRY-` 前缀 `is_dry_run=True` 单」且「放行方向**照常实盘下单**」；相关回归 **25 个测试模块全绿**（另 3 处与本改动无关的历史/环境失败，见 §6）。

---

## 1. 交付清单

### 1.1 代码改动（3 个文件改动 + 1 个新测试文件）

| 文件 | 改动要点 |
| :--- | :--- |
| `PyTools/option_seller/option_seller_manager.py` | ① 新增模块级 `DIRECTION_SUPPRESS_CFG / _CHOICES / _DRY_CAP / _CATALOG` 与 9 个纯函数（`normalize_suppress_direction` / `direction_suppress_date` / `load_direction_suppress` / `save_direction_suppress` / `suppressed_directions` / `direction_suppressed` / `direction_suppress_snapshot` / `direction_suppress_catalog`）；② 新增类内 `_entry_evidence_of` / `_ev_dir_suppressed` / `_group_key_of` / `count_active_suppressed_dry_groups` / `apply_direction_suppression`；③ `open_trade()` 单一 choke point 置位降级 + 每方向 DRY 节流；④ `_open_single_contract()` 双层兜底 + 日志区分 + `dry_reason='DIRECTION_SUPPRESSED'`；⑤ **4 处活跃组数计数排除**方向抑制单；⑥ `get_status_summary()` 新增 `direction_suppress` |
| `bbt_data_web/data_app/bbt_option_seller.py` | ① 新端点 `GET/POST /api/option_seller/direction_suppress`；② `scan_now` 执行分支方向抑制预检 + 专属拒绝原因 + 响应字段 `direction_suppressed` / `is_dry_run`；③ `scan_now` 询价分支新增 `direction_suppressed_warning` |
| `bbt_data_web/templates/bbt_option_seller.html` | ① `<main>` 第一屏常驻工具条 `#dirSuppressBar`（浅色主题）；② `.dir-suppress-bar` 样式（生效中浅红强调）；③ JS：`dirSuppressRender / Apply / SyncFromStatus / saveDirectionSuppress / onDirectionSuppressChange`（4 秒轮询同步、保存中不覆盖、取消抑制二次确认）；④ `_dryReasonMap` 新增 `DIRECTION_SUPPRESSED`；⑤ 手动/UI 扫描弹窗三处提示（预警条 / 确认正文 / 成功文案）；⑥ 两处 DRY 徽标 tooltip 补充「当日方向抑制」 |
| `PyTools/option_seller/test_direction_suppress.py` | **新增契约测试 15 项**（配置归一与隔日失效 / 单笔决策零副作用 / LIVE 端到端 / cap 节流 / 不占额度 / JSON 证据兼容） |

**外置配置产物**（运行时生成，默认不存在 = 未设抑制）：`/Users/zhijiebian/Documents/MyDoc/Finance/Current/Config/option_seller_direction_suppress.json`

### 1.2 文档改动（规则 (10)）

| 文件 | 改动 |
| :--- | :--- |
| `system_modules/83_2026-09-17_Option_Seller_Daily_Direction_Suppression_Force_Dry/implementation_plan.md` | 本归档 Plan |
| `system_modules/83_2026-09-17_Option_Seller_Daily_Direction_Suppression_Force_Dry/walkthrough.md` | 本归档 Walkthrough |
| `system_modules/bbt_trading_modules.html` | M09 卡片：系统职责 / 架构定位 / 技术栈补写 + 「累计演进历程」**7 → 8**；M09 历史表**新增 1 行**（2026-09-17）；TOC 徽标 `7次演进 → 8次演进`；总览表 M09 行 `badge-count 7 次 → 8 次`、最后更新 `2026-09-16 → 2026-09-17`、技术栈新增 `Daily Direction Suppression`、职责补一句 |

**规则 (11) 判定**：本特性**未**写入决策规则手册 —— 它是**用户临场的操作性政策开关**（不参与任何趋势/方向推断，系统不据此产生方向判断），本体是执行层降级通道 + 页面控件 + 配置落盘，属工程实现与运维控制，按规则 (11) 原文不属「决策性规则」。**但其副作用口径**（不占 L0-D/L0-E 组数额度、每方向 2 组 DRY 上限）如用户认为构成组数闸门的一条新规则，可在手册 §3.1.1.1 补一段（等用户确认，见 §7）。

---

## 2. 验收清单逐条核对

| # | 验收项 | 结果 | 证据 |
| :--- | :--- | :--- | :--- |
| 1 | 页面**顶部**出现「方向抑制」选项 | ✅ | 截图 `/tmp/dir_suppress_top.png`（工具条位于 `<header>` 之下、指标带之上，首屏可见） |
| 2 | 可**按方向**分别抑制多头 / 空头 | ✅ | 两个独立勾选框（`BULLISH` / `BEARISH`），后端 `choices` 唯一权威 |
| 3 | 抑制方向的自动单**绝对不发券商** | ✅ | LIVE 端到端：`BBTOS.place_vertical_credit_spread` **调用 0 次**（测试 `test_suppressed_direction_never_reaches_broker`）；双层兜底（`open_trade` + `_open_single_contract`） |
| 4 | 抑制方向的开仓**成 DRY-RUN 单** | ✅ | 落库 `is_dry_run=True`、`order_id` 前缀 `DRY-`、`dry_reason='DIRECTION_SUPPRESSED'`、`entry_evidence.direction_suppressed=True` |
| 5 | **另一方向照常实盘** | ✅ | 测试 `test_allowed_direction_still_trades_live`：抑制 BEARISH 时 BULL_PUT_SPREAD **真实下单 2 次**（双批次） |
| 6 | 设定**仅当日有效**、隔日自动失效 | ✅ | 单测 `test_yesterday_setting_expires_and_is_kept`（`date=2000-01-01` ⇒ `effective=[]`、`expired=True`、原内容保留）+ 活体 DOM 三态实测 |
| 7 | 不改动既有闸门 / Force Dry 语义 | ✅ | `test_force_dry_degrade`（18）、`test_l0_gamma_one_sided_gate`（31）全绿；`option_seller_engine` / `auto_mechanisms` **零改动** |
| 8 | 页面状态可读（生效中 / 已过期 / 未设） | ✅ | 三态 DOM 断言见 §3.3 |
| 9 | 可回滚 | ✅ | 清空配置即回到改动前行为（§6 给出两条命令） |

---

## 3. 实测命令与输出

### 3.1 契约测试 15/15 PASS

```console
$ /usr/local/bin/python3 PyTools/option_seller/test_direction_suppress.py
[TEST GUARD] 已安装测试隔离：拦截 7 个券商写方法、13 个数据库写方法；测试日志 -> .../bbt_option_seller_test.log
test_hit_sets_force_dry_and_evidence ... ok
test_miss_is_zero_side_effect ... ok
test_no_suppression_is_zero_side_effect ... ok
test_aliases_normalized ... ok
test_clear_suppression ... ok
test_default_is_no_suppression ... ok
test_save_stamps_today_and_drops_unknown ... ok
test_snapshot_payload_for_web ... ok
test_yesterday_setting_expires_and_is_kept ... ok
test_allowed_direction_still_trades_live ... ok
test_both_directions_suppressed_both_are_dry ... ok
test_dry_cap_throttles_repeat_records ... ok
test_evidence_of_tolerates_json_string ... ok
test_suppressed_direction_never_reaches_broker ... ok
test_suppressed_dry_trades_do_not_consume_group_quota ... ok

----------------------------------------------------------------------
Ran 15 tests in 0.643s

OK
```

（测试用临时配置文件 + `test_isolation` 守卫：**不触碰真实 Config、不写真实 MySQL、不发真实券商单**。）

### 3.2 相关回归（25 个测试模块）

```console
test_direction_suppress.py          :: Ran 15 tests  OK   ← 本次新增
test_force_dry_degrade.py           :: Ran 18 tests  OK
test_l0_gamma_one_sided_gate.py     :: Ran 31 tests  OK
test_l0c_gap_floor.py               :: Ran 12 tests  OK
test_journal_filter_catalog.py      :: Ran 11 tests  OK
test_journal_group_key.py           :: Ran 12 tests  OK
test_journal_mode_filter.py         :: Ran  9 tests  OK
test_journal_tv_export_scopes.py    :: Ran  8 tests  OK
test_option_seller_notifier_badges.py :: Ran 5 tests OK
test_qp_boundary_integrity_gate.py  :: Ran 29 tests  OK
test_qp_prev_close_gate.py          :: Ran 21 tests  OK
test_qp_meta_parse.py               :: Ran 20 tests  OK
test_setup_classifier_saty_keys.py  :: Ran  7 tests  OK
test_strike_anchor_3131.py          :: Ran 11 tests  OK
test_tv_exit_label_overlap.py       :: Ran  9 tests  OK
test_l1_h1_breakeven_stop.py        :: OK  [SUCCESS] test_l1_h1_dual_tranche_breakeven_flow passed perfectly!
test_mech_absorption_reversal.py    :: Ran 16 tests  OK
test_orphan_position_reconcile.py   :: Ran 22 tests  OK
test_monitor_single_instance_lease.py :: Ran 15 tests OK
test_live_resting_limit_order.py    :: Ran 14 tests  OK
test_quant_pivot_tier_lock.py       :: Ran 17 tests  OK
test_conditional_order_notes_limit.py :: Ran 3 tests OK
test_balanced_day_prev_close_gate.py :: Ran 24 tests OK
test_min_open_credit_dte_fallback.py :: FAILED (1)   ← 见 §6（当日实时 Gamma 数据依赖，与本改动无关）
test_conditional_order_trigger_3131.py :: FAILED (2) ← 见 §6（同上）
```

### 3.3 活体只读验证（Flask 自动重载后）

```console
# ① GET 端点（默认 = 未设抑制）
$ curl -s "http://127.0.0.1:5005/api/option_seller/direction_suppress" | python3 -m json.tool
{ "success": true, "today": "2026-09-17", "date": null, "suppress": [], "effective": [],
  "expired": false, "updated_at": null, "choices": ["BULLISH","BEARISH"],
  "catalog": [ {id: BULLISH, name: 抑制多头（卖 Put 价差 Bull Put Spread）, ...},
               {id: BEARISH, name: 抑制空头（卖 Call 价差 Bear Call Spread）, ...} ],
  "dry_cap": 2 }

# ② POST 写入（含未知方向，验证剔除与归一）
$ curl -s -X POST .../direction_suppress -H 'Content-Type: application/json' \
       -d '{"suppress":["BEARISH","nonsense"]}'
{ "success": true, "date": "2026-09-17", "suppress": ["BEARISH"],
  "effective": ["BEARISH"], "expired": false, "dry_cap": 2 }      # 'nonsense' 被剔除

# ③ 落盘配置（可人读、可回滚）
$ cat .../Config/option_seller_direction_suppress.json
{ "date": "2026-09-17", "suppress": ["BEARISH"], "updated_at": "2026-09-17 06:46:45" }

# ④ status 同步（页面 4 秒轮询读同一字段）
$ curl -s .../api/option_seller/status | python3 -c "import json,sys;print(json.load(sys.stdin)['direction_suppress'])"
{today: 2026-09-17, date: 2026-09-17, suppress: ['BEARISH'], effective: ['BEARISH'], expired: False}
```

**页面三态（headless Chrome `--dump-dom` 实测，独立 `--user-data-dir` + 按 PID 精确回收）**

| 状态 | DOM 实测输出 |
| :--- | :--- |
| **生效中**（`date`=今日，抑制 BEARISH） | `生效中（2026-09-17）：空头（Bear Call Spread） 今日一律走 🧪 DRY-RUN 单、绝不发券商 · 每方向最多 2 组 DRY 单 设定时间 2026-09-17 06:46:45 · 仅当日有效，隔日自动失效`；工具条 `.dsb-active`（浅红强调）、空头勾选框 `checked`、`dsb-on` |
| **已过期**（`date`=2026-09-16，存 BULLISH+BEARISH） | `上次设定（2026-09-16）已自动失效：多头（Bull Put Spread）、空头（Bear Call Spread） ⇒ 今日未抑制任何方向；如需继续请重新勾选（仅当日有效）`；工具条**无** `.dsb-active`、两个勾选框**均未勾选**（隔日设定不生效 ✓） |
| **未设抑制**（配置文件不存在） | `未设抑制：两个方向的自动单均按 LIVE 实盘 执行` |

**内联 JS 语法校验**：抽出 2 个 inline `<script>` 块 ⇒ `node --check` 均 **JS SYNTAX OK**（含新增工具条全部逻辑）。

**收尾**：写入测试用的配置文件已删除，`GET` 复核回到 `{date: null, suppress: [], effective: [], expired: false}` ⇒ **当前系统处于「未设抑制」状态，行为与改动前完全一致**。

---

## 4. 模块页（规则 10）与一致性核查

```console
$ python3 (结构核查脚本)
len 164278
tr open/close: 124 124          # 标签配平
table open/close: 19 19
tbody open/close: 19 19
M09 rows: 8 (minus header)      # 历史表 7 → 8 行
M09 archive dirs: [... '82_2026-09-16_...', '83_2026-09-17_Option_Seller_Daily_Direction_Suppression_Force_Dry']
badge 8 次 near M09: True
```

- M09 卡片「累计演进历程」= **8 次**；总览表 `badge-count` = **8 次**；TOC 徽标 = **8次演进** —— 四处计数一致 ✓
- 新行 Plan / Walkthrough 链接指向本归档目录（`file:///...83_2026-09-17_...`）；归档目录名与单元格 `<code>` 一致 ✓
- 按「一个改动一个最相关 module」，本改动**只**记入 M09（机制判定层零改动 ⇒ 不在 M10 建行）✓

---

## 5. 需要用户知道的实现决定（用户未明说、由本次确定）

| 决定 | 取值 | 理由 |
| :--- | :--- | :--- |
| 生效期 | **仅当日有效**（PT 日期），隔日自动失效并显式提示「已过期」 | 「某些天我会选择」⇒ 防止「昨天设的抑制今天忘关」导致整日不实盘开仓 |
| 额度占用 | 被抑制方向的 DRY 单**不占**任何实盘组数额度（L0-D / L0-E / 2 组闸门 / 控制台活跃组数） | 若占用，纸面单会把额度占满 ⇒ **放行方向也开不出实盘仓**，与「只抑制一个方向」意图冲突 |
| 自身节流 | 每方向同时最多 **2 组** DRY 单（`DIRECTION_SUPPRESS_DRY_CAP`） | 额度被排除后需防止机制反复刷纸面单；既有 DRY 单了结后可再记录 |
| 手动单是否豁免 | **不豁免**（手动 / UI 扫描单同样降级），但预检条 + 确认弹窗 + 成功提示**三处如实告知**「只落 DRY-RUN、未发券商」并给出取消路径 | 用户原话「**绝对**不开」；同时确保用户不会误以为已实盘成交 |
| 取消抑制的确认 | LIVE 模式下取消抑制需**二次确认**（提示会恢复真实下单） | 取消抑制是「风险增加」方向的操作，防误点 |

---

## 6. 核查中发现的、与本次改动**无关**的既有失败（逐条如实报告）

| 模块 | 失败 | 定位证据 | 结论 |
| :--- | :--- | :--- | :--- |
| `test_conditional_order_trigger_3131.py`（2 项，ARMED 上轨单） | `mock_open.assert_called_once()` → 调用 0 次 | 活体读到的当日 SPX Gamma 掩码 = `['BEARISH']`（`bias=BULLISH`，`L0-F: Gamma 结构明显偏向 BULLISH（禁卖 Call）⇒ 掩码 BEARISH`）；上轨单方向为 BEARISH ⇒ 被既有 L0-F⑨ 触发侧兜底复校跳过（该用例未 patch 掩码）。**把掩码 patch 为无掩码后 → 21 项全部 OK** | 当日实时行情数据依赖导致的既有失败，**非本次改动引入** |
| `test_min_open_credit_dte_fallback.py`（1 项，`$0.10 应被接受`） | `open_trade` 返回 None | 该用例候选为 `BEAR_CALL_SPREAD` + `MANUAL_UI_SCAN` ⇒ 同样被当日 `BEARISH` 掩码硬拦截（L0-F⑨ 对 UI 扫描单不豁免）；**同上 patch 后 OK** | 同上 |
| `test_quant_pivot_option_seller.py` | `ModuleNotFoundError: No module named 'PyTools'` | 该文件 `from PyTools.pivots.quant_pivot import ...`，在 `PyTools/option_seller/` 与项目父目录下运行**均**失败 | 该测试文件的路径自举已陈旧（环境性），**与本次改动无关** |
| `test_absorption_reversal_module.py` | 运行 >5 分钟（整日复算 + 原始数据解析，`AR.evaluate_day`） | 纯 order flow 分析模块，不涉及 `option_seller_manager` / Web / 模板 | 与本改动无关的重测，已终止（非失败） |

> 上述三项可用同一手法复现「与本改动无关」：把 `OptionSellerManager.resolve_l0f_gamma_mask` patch 为 `(set(), {...})` 后，`test_min_open_credit_dte_fallback` + `test_conditional_order_trigger_3131` 合计 21 项 **全部 OK**。

---

## 7. 结论与后续可选项

1. **功能已交付并验收通过**：页面顶部「方向抑制（当日有效）」工具条可用，命中方向**绝不发券商**并落 DRY-RUN 单留痕；放行方向照常实盘；隔日自动失效；不占实盘组数额度。
2. **当前实盘状态**：抑制设定为**空**（`suppress: []`）⇒ 系统行为与改动前一致，无需用户做任何事即可开始使用（在页面顶部勾选即生效）。
3. **回滚**：见 Plan §6（清空配置 = 零代码回滚；或按 git 撤销 3 个文件）。
4. **待用户确认的可选项**：
   - (a) 是否把「被抑制方向的 DRY 单不占 L0-D/L0-E 组数额度」写入**决策规则手册 §3.1.1.1**（本次按规则 (11) 判定为工程实现口径而**未**写入）；
   - (b) 若希望「只在自动单上生效、手动单仍可实盘」，可将豁免口径改为与 L0-F⑨ 同款（纯手工单豁免）—— 一行开关即可调整。
