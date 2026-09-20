# TradingView 出场标签重叠修复 验收报告

- **日期**：2026-09-14
- **模块**：`PyTools/trading_view/tv_option_seller_trades.py`（卖家系统「生成TradingView指标」）
- **归档目录**：`53_2026-09-14_TV_Exit_Label_Overlap_Fix`
- **用户报障**：止损的两个 label overlap 了（SPY 0DTE G1，08:41 开仓 / 08:44 双腿止损）

---

## 1. 交付物

| # | 交付 | 位置 |
|---|---|---|
| 1 | 后端：同一 exit cluster **只留代表标签** | `PyTools/trading_view/tv_option_seller_trades.py` |
| 2 | Pine：**容差去重 + 近邻错位**（替代毫秒精确去重） | 同上（生成的 Pine 文本） |
| 3 | 契约测试（9 条） | `PyTools/option_seller/test_tv_exit_label_overlap.py` |
| 4 | 可复现回退脚本 | 本目录 `revert_module_53.py` |

## 2. 报障复现 → 修复对照

**修复前**（原因：cluster 代表挂合并标签 + 成员又挂个体标签；Pine 按毫秒精确去重，而两腿差 2 秒）：

```
id=238  exit='[G1-T1+T2] 止损 -$28.00\n• G1-T1: -$14.00\n• G1-T2: -$14.00\n08:44 | 762.09'
id=239  exit='[G1-T2] 止损 -$14.00\n08:44 | 762.09'          ← 叠在 238 上面 ✗
```

**修复后**（同一组、经真实接口 `POST /api/option_seller/generate_tv_script` 取回）：

```
id=238  exit='[G1-T1+T2] 止损 -$28.00\n• G1-T1: -$14.00\n• G1-T2: -$14.00\n08:44 | 762.09'
id=239  exit=''                                              ← 不再产生第二个标签 ✓
```

## 3. 验收证据

### 3.1 契约测试 9/9 通过

```
/usr/local/bin/python3 PyTools/option_seller/test_tv_exit_label_overlap.py
Ran 9 tests in 0.607s — OK
```

| 测试 | 断言 | 结果 |
|---|---|---|
| `test_simultaneous_exit_keeps_single_label` | 夹具：同组双腿 **Δ2 秒 / 同价** ⇒ **只 1 个**标签，且为**合并**标签（含 `T1+T2`） | ok |
| `test_separated_exits_keep_both_labels` | 夹具：同组双腿 **Δ45 分钟** ⇒ **保留 2 个**标签（T1 / T2） | ok |
| `test_entry_side_convention_unchanged` | 开仓侧仍「一组一个标签」 | ok |
| `test_tolerance_dedupe_present` | 含 `exitSpotsDrawn` / `dtMs <= 60000 and dPx <= 0.12` / `exitDup` | ok |
| `test_near_neighbour_nudge_present` | 含 `dtMs <= 300000 and dPx <= 0.60` / `yNudge` / `tr.close_spot + yNudge` | ok |
| `test_old_exact_ms_dedupe_removed` | **不含** `array.includes(exitTimesDrawn, tr.close_time_ms)`（旧口径已移除） | ok |
| `test_backend_keeps_one_label_per_cluster` | cluster 非代表成员 `item['label_exit'] = ''`，且不再挂个体标签 | ok |
| `test_no_duplicate_exit_labels_in_real_data` | 2026-09-14 全量：不存在「两条都带标签且 Δt ≤ 60 s 且 Δ价 ≤ 0.12」 | ok |
| `test_all_stop_loss_labels_have_unique_position` | 2026-09-14 全量止损标签两两不重合 | ok |

### 3.2 端到端（真实接口 · 用户报障那一组）

```
POST /api/option_seller/generate_tv_script   {"date":"2026-09-14","trade_ids":[238,239]}
→ HTTP 200 · trade_count=2 · pine 156 行
→ id=238 带合并标签；id=239 exit=''            ✓
→ Pine 含新逻辑：exitSpotsDrawn ✓ / dtMs<=60000 and dPx<=0.12 ✓ / dtMs<=300000 and dPx<=0.60 ✓ / + yNudge ✓
→ 旧口径 array.includes(exitTimesDrawn 已无 ✓
```

### 3.3 全量产物复核（2026-09-14，25 笔 / 13 组）

| 组 | 出场情形 | 标签归属（修复后） |
|---|---|---|
| G1 | T1+T2 同刻止损 | 仅代表（合并标签），伙伴空 ✓ |
| G2 | T1+T2 同刻止损 | 仅代表 ✓ |
| G3（用户报障那组；**单独导出该组时组号重编为 G1**，故 §2 里显示 `[G1-…]`） | T1+T2 相差 2 秒同价止损 | 仅代表，**伙伴空** ✓ |
| G4–G8 | 五组 09:18 集体止损 | 仅代表（合并标签含各腿明细），其余全空 ✓ |
| G9 | T1 09:56 止盈 / T2 10:41 止盈 | **两个标签都保留** ✓（不矫枉过正） |
| G10 | T1+T2 同刻保本 | 仅代表 ✓ |
| G11 | T1 12:17 止盈 / T2 12:30 止盈 | **两个标签都保留** ✓ |

### 3.4 无回归

| 套件 | 结果 |
|---|---|
| `test_journal_tv_export_scopes.py` | **8/8** OK（每组订单按钮 — 模块 52） |
| `test_journal_mode_filter.py` | **9/9** OK（运行模式筛选 — 模块 51） |
| `test_journal_filter_catalog.py` | **11/11** OK（类型筛选目录） |
| `py_compile` | 通过 ✓ |

### 3.5 回退脚本实测（副本上）

```
python3 revert_module_53.py --dry-run
  ✓ ① cluster 成员标签 → 恢复个体标签
  ✓ ② exitSpotsDrawn 声明 → 删除
  ✓ ② array.clear(exitSpotsDrawn) → 删除
  ✓ ③ 出场标签判据 → 恢复「毫秒精确相等」旧口径
  校验：残留标识 = 0 ✓
副本实跑：已留快照 + py_compile 通过 ✓（线上文件未受影响）
```

## 4. 用户侧操作

1. 在账本点「生成TradingView指标」（或组头按钮）**重新生成** Pine；
2. 到 TV Pine Editor **替换**已保存的旧指标（旧脚本里仍是旧逻辑）；
3. 期望：同一组双腿同时止损/止盈时**只有一个合并标签**；分次出场仍各自有标签；近邻标签上下错开不再压字。

## 5. 边界与未做

| 项 | 说明 |
|---|---|
| 接口/前端 | **未改**（同一个 `build_option_seller_pine_script`，页面按钮链路不变） |
| 「近邻」窗口 | 固定 5 min / 0.60 点 + 阶梯 0.45 点（经验值；如觉得偏移过大/过小可调 `yNudge` 系数） |
| 规则手册 | **无需更新**（属图表展示实现，非决策规则） |
| 历史 Pine | 已生成并保存到 TV 的旧版本不会自动更新 —— 需重新生成替换 |
