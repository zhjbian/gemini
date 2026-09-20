# 卖家系统：账本「订单组合」分组键统一（group_order_id 优先）实施计划

- **日期**：2026-09-14
- **模块**：期权卖家账本分组（`bbt_data_web/templates/bbt_option_seller.html`）+ 账本接口（`bbt_data_web/data_app/bbt_option_seller.py`）+ TV 生成器（`PyTools/trading_view/tv_option_seller_trades.py`）
- **归档目录**：`54_2026-09-14_Journal_Group_Key_Unify`
- **技术栈**：Jinja2 模板内联 JS / Flask 接口 payload / Python Pine 生成器 / MySQL `bb_trade`（只读核对）/ 契约测试 + headless Chrome 实渲染断言

---

## 1. 背景与问题（用户报障 + 截图）

用户报障：**「过滤结果里 #11 #12 是一个单，但没有显示在自己的组里」**。截图显示：

- 组头 `订单-2 (2组4手)` 下面只有它自己的两批（#13/#14，09:48:53/54，767/769）；
- 紧随其后 **#12 / #11 各自单独成行**（09:33:33 / 09:33:29，764/766），**没有自己的组头**，批次徽标也退化成 **「单批次」**（正常应显示「第1批 / 第2批」）。

## 2. 根因：三处分组的「键」口径不一致

`group_order_id` 是**开仓路径写入 `entry_evidence` 的同组共享键**（DRY 与 LIVE 皆然，见 `option_seller_manager.py`：`c1/c2['group_order_id'] = shared_base_oid`），**仪表盘「活跃持仓」分组早已用它**（2026-09-14 已修）。但：

| 位置 | 旧口径 | 结果 |
|---|---|---|
| **账本** `renderHistoryTable()` | `order_id` 基名 → DRY 时间戳 → 同 strikes 且开仓 ≤**3 s** | ✗ |
| **TV 生成器** `tv_option_seller_trades.py` | 同上（少 DRY 分支） | ✗ |
| 仪表盘「活跃持仓」 | `group_order_id → order_id 基名 → open_time+strikes` ✓ | ✓ |

**LIVE 场景必然落空**：两批各自持有**独立券商 order_id**（实测 `1007916750080` / `1007916750091`，无 `-1/-2` 后缀），开仓时间又常差 **4–5 秒**（实测 09:33:29 / 09:33:33 = **4 s > 3 s**）⇒ 三条启发式全不命中 ⇒ 同一次开仓被拆成**两个「单成员组」**⇒ `isTwinGroup = tradesInGroup.length >= 2` 为 false ⇒ **组头不渲染**、批次徽标退化。

（DRY 单因 order_id 形如 `DRY-<ts>-1/-2`、基名相同而侥幸正常 —— 这正是该缺陷长期未被发现的原因。）

### 真实数据佐证（只读）

| id | order_id | 开仓 | 批次 | strikes | `entry_evidence.group_order_id` |
|---|---|---|---|---|---|
| 244 | 1007916750080 | 09:33:29 | T1 | 764/766 | **DRY-1789403609** |
| 245 | 1007916750091 | 09:33:33 | T2 | 764/766 | **DRY-1789403609** ← 同键 |

## 3. 实施目标

| 目标 | 交付 |
|---|---|
| 三处分组同口径 | 一律 **`group_order_id`（含 `entry_evidence.group_order_id`）优先**，再回落既有启发式 |
| 历史行不回归 | 无键行仍走原启发式（`order_id` 基名 / DRY 时间戳 / ≤3 s），行为不变 |
| 不误合并 | 权威键加 `GRP:` 前缀，避免与 `order_id` 基名空间冲突；单批仍自成一组（不强行并入别组） |
| 账本 payload 自带键 | `/api/option_seller/trades_by_date` 每条交易带回 `group_order_id`（与「活跃持仓」序列化同口径） |

## 4. 关键设计与依据

### 4.1 账本（唯一改动点：`renderHistoryTable` 分组循环）

```js
const tAuthKey = t.group_order_id || (t.entry_evidence && t.entry_evidence.group_order_id) || null;
const authGrpKey = tAuthKey ? ('GRP:' + tAuthKey) : null;
let matchedGrpKey = (authGrpKey && groupsMap.has(authGrpKey)) ? authGrpKey : null;
…
for (const [existingKey, existingTrades] of (matchedGrpKey ? [] : groupsMap.entries())) { …启发式… }
const grpKey = matchedGrpKey || authGrpKey || tOidBase || `${t.open_time}_…`;
```

- **命中权威键即跳过启发式循环**（`? [] : …`）⇒ 既快又不会被错误并入别的组；
- 未命中（历史无键行）时行为与改造前**逐行一致**。

### 4.2 后端 payload

`history_list.append({...})` 增加 `'group_order_id': ev.get('group_order_id')` —— 与 `option_seller_manager` 的持仓序列化同一字段口径。

### 4.3 TV 生成器

同样在分组循环里先取 `t['group_order_id'] or t['entry_evidence']['group_order_id']`（+`GRP:` 前缀），命中则跳过启发式；`grp_key` 回退链插入 `auth_grp_key`。副带好处：Pine 里的「订单组合」编号与账本/仪表盘**完全一致**（模块 53 的出场标签合并也因此更整齐）。

## 5. 改动清单

| # | 文件 | 位置 | 改动 |
|---|---|---|---|
| 1 | `bbt_data_web/templates/bbt_option_seller.html` | `renderHistoryTable()` 分组循环 | 权威键优先 + 命中即跳过启发式 + `grpKey` 回退链插入 |
| 2 | `bbt_data_web/data_app/bbt_option_seller.py` | `trades_by_date` payload | 新增 `'group_order_id': ev.get('group_order_id')` |
| 3 | `PyTools/trading_view/tv_option_seller_trades.py` | 分组循环 | 同 (1) 的 Python 版 |
| 4 | `PyTools/option_seller/test_journal_group_key.py` | 新增 | 12 条契约测试（模板 / 接口 / 生成器 / 真实数据不变量） |
| 5 | 归档 | 本目录 | Plan / Walkthrough（md+html）/ `revert_module_54.py` |

## 6. 验收口径

| 层 | 手段 | 通过标准 |
|---|---|---|
| 模板契约 | `test_journal_group_key.py` | 权威键在启发式之前；命中即跳过；回退链含 `authGrpKey`；旧启发式仍在 |
| 接口契约 | 同上 + 实调 | payload 每条交易带 `group_order_id`（实测 20/20） |
| 生成器行为 | 夹具（真实 244/245 行） | 两批**同一 g_idx**；全日组数 == 权威键去重数（**10 == 10**）；单批不产生第二个组合 |
| 真实数据不变量 | DB（2026-09-14） | 每行都有键；244/245 同键；每个键内同 strikes 且开仓跨度 ≤10 s |
| 实渲染 | headless Chrome `--dump-dom` | **10 个组头 × 每组 2 批 = 20 行**；报障那两批落在同一组（`订单-6 (1组2手)`）；渲染表中无「单批次」 |
| 无回归 | 5 套件 | 全绿（group_key 12 / label overlap 9 / TV scope 8 / mode filter 9 / filter catalog 11） |
| 语法 | `py_compile` ＋ `node --check` | 通过 |

## 7. 风险与回滚

| 项 | 说明 |
|---|---|
| 风险 | 权威键若**跨次开仓被误复用**会把两单并成一组 —— 但该键由开仓路径**每次开仓新建**（`GRP-<ts>` / `DRY-<ts>`），且测试断言「同键行必须同 strikes 且开仓跨度 ≤10 s」；旧行无键 ⇒ 走启发式，不臆造分组 |
| 生效方式 | 模板改动需**硬刷新**（⌘⇧R）；后端 `.py` 由 Flask debug-reloader 自动重载（已实测接口即时返回新字段） |
| 回滚 | `revert_module_54.py`（`--dry-run` 看锚点；实跑先留 `.bak` 再逐字面量反向替换，末尾 `py_compile` + `node --check` 校验；副本实测残留标识 0）；另留三文件快照 `*.bak-20260914_202239` |
