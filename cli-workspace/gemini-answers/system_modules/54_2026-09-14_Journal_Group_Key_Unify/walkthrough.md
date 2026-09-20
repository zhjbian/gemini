# 账本「订单组合」分组键统一 验收报告

- **日期**：2026-09-14
- **归档目录**：`54_2026-09-14_Journal_Group_Key_Unify`
- **用户报障**：过滤结果里 #11 #12 是一个单，但没有显示在自己的组里

---

## 1. 报障现象 → 根因 → 修复

| 环节 | 内容 |
|---|---|
| **现象** | 同一次开仓的两批各自单独成行、**无组头**，批次徽标退化成「单批次」 |
| **根因** | 三处分组的「键」口径不一致：账本与 TV 生成器只用 `order_id` 基名 / DRY 时间戳 / 开仓 **≤3 s** 启发式，**没用后端权威键 `group_order_id`**（仪表盘早已用）。LIVE 下两批持有**独立券商 order_id**、开仓相差 **4 s** ⇒ 三条全落空 ⇒ 拆成两个「单成员组」⇒ `isTwinGroup=false` ⇒ 组头不渲染 |
| **修复** | 三处统一为 **`group_order_id`（含 `entry_evidence.group_order_id`）优先**，命中即跳过启发式；无键行仍走原启发式（行为不变）。账本 payload 同时补回该键 |

### 真实数据佐证（只读）

```
id 244  order_id 1007916750080  open 09:33:29  T1  764/766  group_order_id = DRY-1789403609
id 245  order_id 1007916750091  open 09:33:33  T2  764/766  group_order_id = DRY-1789403609   ← 同键
```

## 2. 交付物

| # | 交付 | 位置 |
|---|---|---|
| 1 | 账本分组：权威键优先（`GRP:` 前缀 + 命中跳过启发式） | `bbt_data_web/templates/bbt_option_seller.html` |
| 2 | 接口 payload 带回 `group_order_id` | `bbt_data_web/data_app/bbt_option_seller.py` |
| 3 | TV 生成器分组同口径 | `PyTools/trading_view/tv_option_seller_trades.py` |
| 4 | 契约测试 12 条 | `PyTools/option_seller/test_journal_group_key.py` |
| 5 | 可复现回退脚本 | 本目录 `revert_module_54.py` |

## 3. 验收证据

### 3.1 契约测试 12/12 通过

```
/usr/local/bin/python3 PyTools/option_seller/test_journal_group_key.py
Ran 12 tests in 0.534s — OK
```

| 组 | 测试 | 断言 |
|---|---|---|
| 模板契约 | `test_authoritative_key_used_first` | 权威键在启发式循环**之前**出现（且带 `GRP:` 前缀） |
| | `test_heuristic_skipped_when_authoritative_hit` | `(matchedGrpKey ? [] : groupsMap.entries())` |
| | `test_authoritative_key_in_final_fallback_chain` | `matchedGrpKey \|\| authGrpKey \|\| tOidBase \|\| …` |
| | `test_legacy_heuristics_preserved` | 旧启发式仍在（历史无键行行为不变） |
| 接口契约 | `test_payload_carries_group_order_id` / `test_group_key_present_next_to_tranche_fields` | payload 含该键且与批次字段同处返回 |
| 生成器行为 | `test_reported_pair_shares_one_group` | 真实 244/245 两批 ⇒ **同一 g_idx** |
| | `test_group_count_matches_authoritative_keys` | 全日组数 **10 == 权威键去重数 10** |
| | `test_single_tranche_keeps_own_group` | 单批不产生第二个组合（不误合并） |
| 真实数据不变量 | `test_every_row_has_group_order_id` | 2026-09-14 全 20 行都有键 |
| | `test_reported_pair_shares_key_in_db` | 244/245 同键 |
| | `test_each_group_covers_one_open_event` | 每个键内同 strikes 且开仓跨度 ≤10 s |

### 3.2 实渲染（headless Chrome `--dump-dom`）

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 组头行 | 10（#11/#12 那两个「单成员组」**无组头**） | **10 个组头 × 每组 2 批 = 20 行** ✓ |
| 报障那两批 | 各自单行、徽标「单批次」 | 同组 **`订单-6 (1组2手)`**，2 批 ✓ |
| 渲染表内「单批次」徽标 | 2 | **0** ✓ |

### 3.3 接口实调

```
GET /api/option_seller/trades_by_date?date=2026-09-14
→ HTTP 200 · 交易 20 笔 · 带 group_order_id 的 20 笔
→ 244 group_order_id=DRY-1789403609 (tranche 1, 09:33:29)
→ 245 group_order_id=DRY-1789403609 (tranche 2, 09:33:33)   ⇒ 同键 ✓
```

### 3.4 TV 生成器组数（副带修正）

| | 修复前 | 修复后 |
|---|---|---|
| 订单组合数（2026-09-14 全日） | 11（244/245 被拆） | **10**（== DB 权威键去重数）✓ |
| 组编号 G1…G10 | 与账本/仪表盘不一致 | **三处完全一致** ✓ |

### 3.5 无回归 + 语法

| 项 | 结果 |
|---|---|
| `test_journal_group_key.py` | **12/12** OK |
| `test_tv_exit_label_overlap.py`（模块 53） | **9/9** OK |
| `test_journal_tv_export_scopes.py`（模块 52） | **8/8** OK |
| `test_journal_mode_filter.py`（模块 51） | **9/9** OK |
| `test_journal_filter_catalog.py` | **11/11** OK |
| `py_compile`（后端 + 生成器） / `node --check`（模板 JS 246,675 字符） | 通过 ✓ |

### 3.6 回退脚本实测（副本）

```
python3 revert_module_54.py --dry-run
  ✓ ① 账本分组 → 恢复启发式（去掉权威键优先）
  ✓ ① 账本 grpKey 回退链 → 去掉 authGrpKey
  ✓ ② 后端 payload → 去掉 group_order_id
  ✓ ③ 生成器分组 → 恢复启发式
  ✓ ③ 生成器 grp_key 回退链 → 去掉 auth_grp_key
副本实跑：3 个 .bak 快照 + py_compile×2 通过 + node --check 通过；回退产物残留标识 0；线上文件未受影响
```

## 4. 用户侧操作

- **模板改动需硬刷新**（⌘⇧R）→ 账本应立即显示 10 个「订单-N」组头，每组 2 批；
- 后端 `.py` 已由 Flask debug-reloader 自动重载（接口已实测返回新字段），无需重启服务；
- 若之前已导出过 TV 指标，建议**重新生成**（组编号与账本现在完全一致）。

## 5. 边界与未做

| 项 | 说明 |
|---|---|
| 分组语义 | 未改 `isTwinGroup`（单批仍不显示组头 —— 那是设计如此，非本 bug） |
| 键的选取 | 只认 `group_order_id`（后端权威）；**不臆造**：无键行仍按旧启发式，避免误合并 |
| 规则手册 | **无需更新**（分组键/UI 口径属工程实现，非决策规则） |
| 历史无键行 | 行为与改造前逐行一致（测试锁定） |
