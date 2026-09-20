# 平衡日边界族重构 + Saty ATR 档位 + ARMED 条件哨兵单 —— 实施计划

- **日期**：2026-09-15
- **归档目录**：`69_2026-09-15_Balanced_Day_Saty_ATR_Boundary_Family`
- **归属能力域**：**M10 Option Seller 多机制触发系统**（机制 ② QuantPivot 边界反向 / 机制 ③ 平衡日边界）
- **代码位置**：`PyTools/option_seller/`（`balanced_day_boundary.py` / `balanced_day_data.py` / `option_seller_manager.py` / `intraday_probe.py` / `setup_classifier.py` / `balanced_day_shadow.py`）
- **触发事件**：用户口径指令（边界族与容差口径更正 1–3）+ 用户裁决（ARMED 执行方案 A、锚权威源、机制② L2/H2 生效）

---

## 1. 背景与目标

### 1.1 三部分边界族重构（只删 `ut1` / `dt1`）
机制 ③「平衡日边界」原边界族点位混杂 ES 点与 SPY 点两套尺度，且白名单含 4 个 Smashelito 字段（`ut1` / `dt1` / `fut` / `fdt`）。本轮按用户口径重构为**双子族 · 8 点位**：

| 子族 | 成员 | 尺度 | 判定基准 |
|---|---|---|---|
| **SPY 子族**（6） | `spy_day_high` / `spy_day_low`（当日 RTH 运行极值）+ Saty ATR 四档（`saty_up618` / `saty_up100` / `saty_dn618` / `saty_dn100`） | **SPY 点** | SPY 现价 |
| **ES 子族**（2） | `fut` / `fdt` | **ES 点**（距离 ÷10 折算为 SPY 点等值） | ES 现价（行价格） |

**只删除 `ut1` / `dt1`**（Smashelito 白名单收窄为 `("fut", "fdt")`），其余点位与数值示例不动。

### 1.2 SPY 单一口径 · 零点位换算
- Saty 四档在 **SPY 点**上直接计算（`锚 + ATR × 系数`），**不做点位换算** —— 判定只用**距离**，ES/SPY 基差在差值中天然抵消。
- 跨子族比较时**只折算距离**（ES 点 ÷10 ⇒ SPY 点等值），**绝不折算点位**（实测 ES 基差 ~16.6 ES 点 ≈ 1.66 SPY 点 ≫ 容差 0.2，折算点位会把整族挪出容差带）。
- 辅助留痕：`saty_domain="spy"`、`saty_anchor_spy`、`saty_atr_spy`、`saty_anchor_source`。

### 1.3 容差口径 ±0.2 / ±0.3（SPY 点）
- 触及带：`d ≤ 0.2` SPY 点；「接近」带：`d ≤ 1.5 × 0.2 = 0.3` SPY 点（**均含等号**）。
- ES 子族等值：2.0 / 3.0 ES 点。
- 生产配置遗留的 ES 口径 `boundary_tol = 4.0` **被忽略**（`BOUNDARY_TOL_LEGACY_MAX = 1.0` 上限守卫），统一取 0.2。

### 1.4 前置③④ 分族（缺口日保护 + 边界有效性）
- **前置③「昨收方向」（缺口日保护）**：SPY 子族用 **SPY 昨收**（= Saty 锚），ES 子族用 **ES 昨收**；两族各自在自身尺度内比较、**绝不混比**。**fail-closed**（缺数一律拦截）。
- **前置④「边界有效性」（未被有效突破）**：**只约束 Saty `±61.8%` 两档**（= 机制② L1/H1 等价档）；**Saty `±100%`、`fut` / `fdt` 远档、`spy_day_high` / `spy_day_low` 运行极值豁免**。阈值 **SPY 子族 0.8 SPY 点 / ES 子族 8.0 ES 点**（含等号）。**fail-open**（缺数放行）。

### 1.5 分档分派（Saty ⇒ 机制② 等价档）
| Saty 档位 | 等价档 | 风险档位 | 止盈模式 |
|---|---|---|---|
| `saty_up618` | H1 | `BALANCED` | `CONSERVATIVE`（保守 = 模式 B） |
| `saty_dn618` | L1 | `BALANCED` | `CONSERVATIVE` |
| `saty_up100` | H2 | `AGGRESSIVE` | `STANDARD`（标准 = 模式 A） |
| `saty_dn100` | L2 | `AGGRESSIVE` | `STANDARD` |

### 1.6 手册优先覆盖全局 + 机制② 不受全局开关
- **强制覆盖**：机制②/③ 的**档位绑定单**由手册口径决定 profile + 止盈模式（`SATY_PROFILE_OVERRIDE_ENABLED = True`），**不受**全局 `auto_strategy` 开关影响。
- **全局 `auto_strategy` 仅对无档位绑定的自动单生效**（机制① 5m 综合、机制④ 趋势日极限、机制⑤ 盘前大单、机制⑥ 洗盘反转）。机制③ 的「降级规则」保持为**整族不参与**（不退回固定 10 倍比例）。

### 1.7 ARMED 条件哨兵单（手册 §3.1.4.1.1 §④ · 执行方案 A）
- **仅对 Saty 受限档 `±61.8%`** 装配（≡ 机制② L1/H1）。
- **布防条件**：`0.2 < d`（SPY 点，严格）且 `d / 档位值 ≤ 0.5%`（含等号），且**前置③ + 前置④ 均通过**。
- **触发条件**：上侧 `SPY GTE 档位` / 下侧 `SPY LTE 档位`。
- **不装 ARMED**：Saty `±100%`、SPY 运行极值、ES 子族 `fut` / `fdt` —— 仍只在 `d ≤ 0.2` 时**即时开仓**。
- **跨进程携带**：`notes` 写 `[SatyLevel: …] [QPLevel: …] [L1H1: true] [Anchor: n]`。
- **已知产出特征**：布防带 ≈38 行/日 → **布防 ≈0.33 次/日**；含 ARMED 后触发 ≈**2.3 次/日**（旧口径基准 22 次 / ≈7.3 日）。

### 1.8 RTH 上界与零量 bar 过滤（实现手册既有 RTH 语义）
- SPY 快照窗口由「只有 06:30 下界」补为 **`[06:30, min(upto_time, 13:00)]`**（手册口径为「当日 **RTH** 运行极值 / RTH 收盘」）。
- 丢弃 `Volume <= 0` 的 bar（决策窗口 17 天内仅 4 个且价格正常）。
- **依据（只读量化）**：06:30–17:00 共 40,597 bar 中 `Volume<=0` 占 **36%（14,799）**、明显异常 **388** 个且**全部落在 13:00 之后**；而决策窗口 06:30–11:30 的 19,862 bar 中异常 **0** 个。

### 1.9 锚权威源切换（用户裁决 2026-09-15）
- **权威**：`BBTOS.get_ohlc_rth('SPY', 上一交易日)['close']`（券商 RTH 官方收盘，= 手册案例 `760.77`）。
- **回退**：BBTOS 不可用 / 取不到 ⇒ 回退 `QuantPivotCalculator.get_quant_pivot('SPY')['prev_close']`，**留痕** `saty_anchor_source='quant_pivot_fallback'`（正常为 `'bbtos_rth_close'`）⇒ 进 ctx / diag；**不因回退让整族停摆**；**两源都拿不到**才 `saty_data_missing=True`。
- **自检**：`check_spy_anchor_consistency()` 的 `source_used` 反转为 `'bbtos_rth_close'`（比较方向 = 权威 vs 回退），容忍 **0.05 SPY 点**告警不变。

---

## 2. 改动清单（文件 + 行 + 关键常量 / 字段名）

### 2.1 `PyTools/option_seller/balanced_day_boundary.py`
| 行 | 内容 |
|---|---|
| `:58` | `BALANCED_BOUNDARY_TOL_SPY = 0.2` |
| `:59` | `BALANCED_NEAR_MULT = 1.5` ⇒「接近」= 0.3 SPY 点（含等号） |
| `:61` | `ES_TO_SPY_DIST = 0.1` |
| `:62` | `BALANCED_BREAK_TOL_SPY = 0.8` |
| `:64` | `BALANCED_SATY_LEVELS = ("saty_up618","saty_up100","saty_dn618","saty_dn100")` |
| `:66` | `BALANCED_SPY_FAMILY`（6 点位） |
| `:68` | `BALANCED_ES_FAMILY = ("fut","fdt")` |
| `:82/:86/:87/:88/:90` | `BALANCED_ARM_PCT=0.005` / `BALANCED_ARM_DIST_ROUND=6` / `BALANCED_ARM_PCT_ROUND=9` / `BALANCED_ARM_SUBSCENARIO` / `BALANCED_ARM_TIERS`（仅 ±61.8%） |
| `:128` / `:998` | `score_balanced_day_boundary`（v1 影子）/ `score_balanced_day_boundary_v2`（P45/M20/B25/E10，D 停用，1 组） |
| `:335` | `classify_boundary_distance(d, boundary_tol)`（含等号 + 精度取整） |
| `:376` | `parse_saty_arm_meta(notes_str)` |
| `:398` | `balanced_day_arm_spec(...)`（唯一权威布防判据） |
| `:484` / `:570` | `boundary_pool()` / `nearest_boundary_refs()`（按子族取价 + 距离归一） |
| `:630` | `check_balanced_boundary_prev_close(..., subfamily=)` 前置③ |
| `:716` | `BALANCED_BREAK_TOL_ES = 8.0` |
| `:721` | `triggered_boundary_name(breakdown, direction)` |
| `:774` | `SATY_GRADE_DISPATCH`（四档 ⇒ 等价档 / profile / 止盈） |
| `:785` | `TP_MODE_LABELS` |
| `:791` | `saty_grade_dispatch(breakdown, direction)` |
| `:843` | `check_balanced_boundary_integrity(..., subfamily=)` 前置④（`:911/:919` 精度取整修复「恰好 0.8 漏拦」） |

### 2.2 `PyTools/option_seller/balanced_day_data.py`
| 行 | 内容 |
|---|---|
| `:203/:215` | `SPY_RTH_START=(6,30)` / **`SPY_RTH_END=(13,0)`** |
| `:265/:266` | `SPY_ANCHOR_SOURCE_BBTOS='bbtos_rth_close'` / `SPY_ANCHOR_SOURCE_QP='quant_pivot_fallback'` |
| `:269` | **`load_spy_anchor(date_str)`**（权威 BBTOS + 回退 QuantPivot + 来源留痕） |
| `:332` | `_load_spy_anchor_and_atr`（接入 `load_spy_anchor`，缓存体带 `anchor_source` 等 5 字段） |
| `:354` | `_spy_snapshot_from_df(..., *, rth_end=SPY_RTH_END, drop_zero_volume=True)`；窗口 + 审计字段 |
| `:421` | `get_saty_atr_meta()` 暴露锚来源 5 字段 |
| `:474` | `load_spy_bars()`（**未改**，仍返回按日整段 df） |
| `:496` | `spy_rth_snapshot_from_bars(..., *, rth_end=..., drop_zero_volume=...)` |
| `:516` | `_load_spy_rth_snapshot()`（审计字段 + 零量 warning 留痕） |
| `:594` | 零量 > 0 ⇒ `logger.warning` 逐条留痕（计数 + O/H/L/C/V 样例） |
| `:647` | `SPY_ANCHOR_CHECK_TOL = 0.05` |
| `:651` | `_prev_session_date(date_str)` |
| `:668` | `check_spy_anchor_consistency()` |
| `:779` | `source_used = SPY_ANCHOR_SOURCE_BBTOS`（方向反转） |
| `:791` | `load_balanced_day_context(...)`（ctx + diag 双留痕） |
| `:914/:970-972` | diag：`saty_anchor_source` / `saty_anchor_prev_session` / `saty_anchor_fallback_reason` |
| `:1031-1035` | ctx：`saty_anchor_source` / `saty_anchor_prev_session` / `saty_anchor_bbtos_rth_close` / `saty_anchor_quant_pivot_prev_close` / `saty_anchor_fallback_reason` |
| ctx | `spy_snapshot_audit`（`rth_end` / `bars_before_filter` / `zero_volume_dropped` / `zero_volume_samples` / `clipped_after_rth`） |

### 2.3 `PyTools/option_seller/option_seller_manager.py`
| 行 | 内容 |
|---|---|
| `:130` | `BALANCED_DAY_DEFAULTS["boundary_tol"] = 0.2` |
| `:170/:173` | `BOUNDARY_TOL_LEGACY_MAX = 1.0` + `load_balanced_day_config()` 忽略旧值 |
| `:1516` | `_open_from_engine(..., profile_locked=False, tp_mode_locked=None)` |
| `:1654` | 机制② ARMED 档位锁定 |
| `:1694-1695` | 机制② QUALIFIED 档位锁定 |
| `:1712` | `_mech_balanced_day_boundary`（**即时开仓优先**，否则 ARMED） |
| `:1734` | `_arm_balanced_day_saty()`（开关 + 掩码 + 窗口 + 去重 + `add_conditional_order`） |
| `:1955/:1978` | 机制② H2 对称（`in ('L2','H2')`） |
| `:2821/:2862` | `_saty_forced` + `candidate['take_profit_mode']` |
| `:2914-2918` | evidence：`saty_profile` / `saty_tp_mode` / `saty_tp_strategy` |
| `:3067/:3073` | `TP_MODE_LABELS` / `_tp_mode_label` |
| `:3082` | **`MANUAL_TIER_LOCKS`**（L1/H1 ⇒ BALANCED+CONSERVATIVE；**L2/H2 ⇒ AGGRESSIVE+STANDARD · 已生效**） |
| `:3089-3095` | `_qp_tier_lock(qp_level)` |
| `:3137` | `SATY_PROFILE_OVERRIDE_ENABLED = True`（定稿） |
| `:3139` | `_saty_profile_override()` |
| `:3253` | `is_conditional_arming_window()`（仅时段窗口） |
| `:3328` | `add_conditional_order()` |
| `:3436/:3466/:3475/:3483` | `parse_qp_meta` / `_saty_arm_meta` / `_is_saty_armed_order` / `derive_target_short_anchor` |
| `:3819` | 触发侧 Saty ARMED 分支（不套 QuantPivot 口径闸门） |

### 2.4 其它文件
| 文件 | 行 | 内容 |
|---|---|---|
| `intraday_probe.py` | `:693-695` | 探针同口径兜底 `_bd_tol`（>1.0 忽略） |
| `intraday_probe.py` | `:515/:574` | 机制② 双侧档位标签 H1/H2、L1/L2（已对称） |
| `setup_classifier.py` | `:130/:195` | 死键清理 + 尺度陷阱注释（`fdt` / `fut` 按子族分流，**不得**并入 `smash`） |
| `balanced_day_shadow.py` | `:20/:131/:151-200/:274-282` | 影子 ARMED 布防 / 真触及 / 触及后质量 |

---

## 3. 实施纪律（本次遵守的边界）

- 未修改任务清单外的文件（新增文件均已说明理由）。
- 未修改任何规则手册文件（本轮手册两处修订由用户**单独授权**并按用户给定字面文本执行）。
- 未触碰 `Ticker_ATR.csv`、未触碰 Java 工程、未改外部配置文件、未改全局默认 profile / TP 档位、未重启服务。
- 数据库 `bb_trade` **只读**；凭证未进入任何报告 / 日志 / 提交。
- 未 commit / push；回滚点见 §5。

---

## 4. 待裁决项（实施时点）

| # | 事项 | 实施时状态 |
|---|---|---|
| 1 | ARMED 频率口径（前置④ 与布防带互斥） | **已裁决：接受现状（方案 c）**，不放宽 |
| 2 | SPY 锚权威源 | **已裁决：券商 RTH 官方收盘**（QuantPivot 为回退） |
| 3 | 机制② L2/H2 改 AGGRESSIVE 生效时机 | **已裁决：立即生效** |
| 4 | 方案 (d)：是否为 ±100% 两档装 ARMED | **未决**（只读测算见 Walkthrough §3） |
| 5 | 手册案例「接近」与实现 0.30 上界的表述一致性 | 手册已由用户更新为「带外」口径（与实现一致） |

---

## 5. 回滚方式

- **回滚点**：`/tmp/bbt_mech3_backup_20260915_221306/`（原始 7 文件 + `ROLLBACK_README.txt` + `option_seller_manager.py.post-mech2lock`）；本轮手册修订另备份于 `/tmp/bbt_manual_backup_20260915_234538/`。
- **逐项回退**：
  1. **锚源切换**：① 临时 —— 把 `_load_spy_anchor_and_atr` 中的 `load_spy_anchor(_key)` 换回 QuantPivot `prev_close`；② 彻底 —— 删 `load_spy_anchor()` / 两常量 / 来源字段，`check_spy_anchor_consistency` 的 `source_used` 改回 `'quant_pivot'`；③ 测试夹具 `_ANCHOR_915` / `_SATY` / `_SPY_PREV` 改回 `760.88` 并恢复 8 点位期望距离。
  2. **RTH 上界 + 零量过滤**：调用处传 `rth_end=None, drop_zero_volume=False`（能力内建，无需改码）；或删除 `SPY_RTH_END` 与相关代码段。
  3. **ARMED**：删 `_mech_balanced_day_boundary` 中的 `_arm_balanced_day_saty` 调用 + 触发侧 `elif` 分支。
  4. **机制② L2/H2 立即生效**：`MANUAL_TIER_LOCKS` 中 L2/H2 改回 `(BALANCED, CONSERVATIVE)`（或返回 `(None, None)` 走全局）。
  5. **锚值自检**：纯新增，删 ctx / diag 两处引用 + 函数本体即完全回退。
  6. **容差口径**：`BALANCED_BOUNDARY_TOL_SPY` 改回 4.0 并须一并回退 `es_price` / 子族参数（旧口径为 ES 点域）。
  7. **新增测试文件**：删除即完成对应回滚。

---

## 9. 追加项（2026-09-15 用户指令「请都做」）

### 9.1 ±100% 两档亦装配 ARMED（方案 d 实施）
- **规则文本（手册 §3.1.4.1.1 §④ 追加，逐字落盘）**：除受限档 `±61.8%` 外，**Saty `±100%` 两档亦装配 ARMED 条件哨兵单**；因其为**豁免档**，布防条件**仅需** `0.2 < d` 且 `d / 档位值 ≤ 0.5%`（**不要求前置③ / ④**）；`notes` 携带 `[SatyLevel: saty_up100] [QPLevel: H2] [L1H1: false] [Anchor: n]`；`±61.8%` 布防条件**不变**。
- **实现**：`balanced_day_boundary.py` `BALANCED_ARM_TIERS` 由 2 档扩为 **4 档**，元组第三元 = `requires_pre_gates`（618 ⇒ `True`、100 ⇒ `False`）；`balanced_day_arm_spec()` 按该标志跳过/执行前置③④，并在 spec 中回传 `requires_pre_gates` / `is_l1_h1`，`notes` 写 `[L1H1: true|false]`；布防带（`BALANCED_BOUNDARY_TOL_SPY = 0.2`）与 0.5% 口径（`BALANCED_ARM_PCT`）**均不变**。
- **预期 vs 实测**：预期布防 ≈0.33 → **≈1.33 次/日**；实测三日 **4 次 / 3 日 = 1.33 次/日** ✓（与 (d) 测算逐值吻合）。

### 9.2 ARMED 触发时点复校（机制③ 版三闸门，替代 QP 口径闸门）
- **规则文本（同节追加，逐字落盘）**：触发、开仓之前复校 —— ① 机制开关 `enabled` 与 L0-B 方向掩码；② 前置③（SPY 昨收方向 · SPY 子族口径）；③ 前置④（边界有效性：`spy_day_high` / `spy_day_low` + `0.8` SPY 点）。**仅 `±61.8%` 复校 ②③**；`±100%` **仅复校 ①**。任一不通过 ⇒ **放弃开仓**并记 `TRIGGERED_GUARD_BLOCK`（留痕原因与数值）。**严禁**套用 `can_open_quant_pivot_level` / `check_qp_prev_close_direction` / `check_qp_boundary_integrity`。
- **实现**：
  - 纯函数 `balanced_day_boundary.check_saty_armed_trigger_guard(meta, *, enabled, masked_directions, spy_prev_close, spy_day_high, spy_day_low, level_value, trigger_direction)` ⇒ `(ok, reason, detail)`，`detail['gates']` 含三闸门各自判定与数值。
  - manager 侧取数辅助：`_resolve_saty_trigger_masks()`（L0-F⑨ `resolve_l0f_gamma_mask()` ∪ L0-B `position_mask(pos, minutes_since_open, is_trend_day)`，`pos` 由新增 `resolve_es_position_pct_for_gate()` 取）、`_resolve_spy_prev_close_for_saty_guard()`（= 权威锚）、`_resolve_spy_extreme_for_saty_guard()`（SPY 1m 快照优先，退化 ES 快照 % 折算）。
  - 只在 **Saty ARMED 触发分支**（`_evaluate_conditional_orders`）调用；未通过 ⇒ `continue` 且落 `TRIGGERED_GUARD_BLOCK`；通过 ⇒ 事件 `TRIGGERED_GUARD_PASS` 增记 `trigger_guard` 与三闸门明细。
  - **机制② 的 `RANGE_BOUND_*` 分支与其三项闸门（L0-F / `check_qp_prev_close_direction` / `check_qp_boundary_integrity`）逐字未动。**
  - 档位值取条件单 `trigger_price`（两位小数）⇒ 已测「四舍五入不改变判定」。

### 9.3 机制② ARMED 布防组数随档位
- **规则文本（§3.1.3.2 追加，逐字落盘）**：机制② ARMED 条件单的组数按档位取 —— **L2 / H2 ⇒ 2 组**、**L1 / H1 ⇒ 1 组**（与 §3.1.3.2 档位口径及盘前大单路径 `groups_to_open` 同口径）。
- **实现**：机制② ARMED 布防点（`option_seller_manager.py` `add_conditional_order(...)`，`_arm_grp = 2 if qp_level in ('L2','H2') else 1`）写入 `groups`，并同步 `pending_conditional_orders[oid]['groups']`；机制③ Saty ARMED 布防点按**等价档** `qp_level` 同规则写组数；**触发侧沿用**条件单字段（`cand['groups'] = int(order.get('groups', 1) or 1)`，原有逻辑）。

### 9.4 外围 L2 对称
- `PyTools/order_flow/order_flow_big_trade_analyst.py` 两处 L2 专属特判改为对称：`:305` `if signal_lvl in ('L2','H2'): multiplier = 3.0 / elif signal_lvl in ('L1','H1'): multiplier = 2.0`；`:366` `multiplier_val = 3.0 if sig['level'] in ('L2','H2') else 2.0`。该文件当前**恒只产 L1/L2** ⇒ **今日零行为变化**（防御性）。
- 另两处 `== 'L2'`（`option_seller_engine.py:1218` 上侧 H2 / `:1313` 下侧 L2；`option_seller_manager.py:3580` 锚位分侧）经核查**本已上下对称** ⇒ **未改动**。

### 9.5 手册（逐字落盘，3 段）
| 落点 | 内容 |
|---|---|
| §3.1.4.1.1 §④ | ARMED 装配对象扩充（±100% 亦布防） |
| §3.1.4.1.1 §④ | ARMED 触发时点复校（三闸门 + `TRIGGERED_GUARD_BLOCK`） |
| §3.1.3.2 | ARMED 布防组数随档位（L2/H2 ⇒ 2、L1/H1 ⇒ 1） |
| §3.1.4.1.9（HTML） | 补回「（L1/H1 等价档）」四字 |

---

## 10. 追加项（2026-09-15 用户口径「同机制同闸门」收口）

### 10.1 ARMED 继承机制③ 趋势日门控（布防 + 触发两处）
- **用户口径**：ARMED 是机制③ 的**延迟执行** ⇒ 必须与即时通道**同闸门**（不是新增规则）。
- **实现（唯一权威判定，三处共用）**：新增纯函数 `balanced_day_boundary.saty_trend_gate_decision(direction, gate, trend_up, trend_dn, fail_closed)` ⇒ `(ok, reason, detail)`，逐字复刻即时通道判定顺序：`off`/无方向 ⇒ 放行 → `unknown && fail_closed` ⇒ 否决 → `opposing` ⇒ 否决 → `require_range && is_trend` ⇒ 否决 → 放行。
  - **即时通道**（`_mech_balanced_day_boundary`）**改为调用该纯函数**（行为等价，`gate_info` 字段名保持不变）；
  - **布防**（`_arm_balanced_day_saty`）新增同一门控：不通过 ⇒ **不布防**并留痕「趋势日门控 [reason] ⇒ 不布防」；
  - **触发复校**：并入 `check_saty_armed_trigger_guard()` 作为**闸门 ④**，**`±61.8%` 与 `±100%` 一律适用**（`±100%` 豁免的只是前置③/④ 两项**幅度类**判据）；不通过 ⇒ 放弃开仓 + `TRIGGERED_GUARD_BLOCK`（`reason='trend_gate: …'`）。
- **取数入口**：`OptionSellerManager._saty_trend_gate(direction, current_time_str, cfg)`（引擎 `evaluate_intraday_trend_regime`，窗口 `trend_window_end` 缺省 `11:30`）。

### 10.2 触发复校 ① 的 L0-B 口径对齐
- 触发侧 `is_trend_day` **不再硬编码 `False`**：新增 `_resolve_trend_regime_for_l0b()`，复用**同一趋势引擎取数**取当日体制（`is_trend = trend_up or trend_dn`）；取不到 ⇒ `False` + 留痕 `unknown_fail_open`（fail-open，不误拦）。
- 体制来源写入 `detail['gates']['mask']['l0b']['regime_source']`（形如 `trend_engine(up=…,dn=…)`）⇒ 可复盘对齐编排层 L0-B。

### 10.3 时间解析加固（本轮实测发现的**误拦**隐患）
- **现场**：布防侧 `current_time_str` 可能来自 DB `TIME`（非零填充 `7:30:00`）；原写法 `str(t)[:5]` 切出 `'7:30:'` ⇒ `strptime` 抛错 ⇒ 趋势门控误判「引擎无结论」⇒ 被 `trend_gate_fail_closed` **误拦**（影子回放实测：40/33/41 次拦截中绝大多数为该误判）。
- **修复**：新增 `OptionSellerManager._norm_hm(t)`（兼容 `5:30` / `05:30` / `05:30:00` / `timedelta` / `YYYY-MM-DD HH:MM:SS`；不可解析 ⇒ `None`），`_saty_trend_gate()` 与影子 `_trend_gate_for()` 均改用之。加固后影子拦截**全部**为 `blocked_opposing_trend`（无虚假 unknown）。

### 10.4 过期测试计数 → 不变量断言
`test_quant_pivot_tier_lock…test_unbound_callers_do_not_pass_lock_args`：硬编码「3 个调用点」改为**不变量断言**（遍历**全部** `_open_from_engine` 调用点，断言无 `profile_locked=True` / `tp_mode_locked=True`，且条件锁定入参各只出现 1 次），新增信息性常量 `_EXPECTED_CALLS_INFO = 4`（注明外部新增 `LABEL_ABSORPTION_REVERSAL` 的来源与日期，不一致时 `skipTest` 提示而非失败）。**被测代码未因此改动。**

### 10.5 手册
- 新增（逐字）：「**ARMED 的趋势日门控（2026-09-15 追加）**」（§3.1.4.1.1 §④）；
- 修正：ARMED 成员句改为「**ARMED 装配对象**：`±61.8%`（受限档·须过前置③④）与 `±100%`（豁免档·2026-09-15 起亦装配、不要求前置③④）；**不装 ARMED 的成员**：SPY 运行极值、ES 子族 `fut`/`fdt`」（原「不装 ARMED 的成员：Saty `±100%`…」与新增段落字面矛盾）。
- **注**：HTML 侧该句在本轮开始时**仍为旧版**（预期中的改动未落盘）⇒ 本轮**由我一并改为你给定措辞**（MD 同步），并把「这三类」改为「**这两类**」（成员由 3 项变 2 项）。

---

## 11. 重新下发的四项收口（2026-09-15 · 确认与字面对齐）

> 本节追记「四项收口」指令的**第二次下发**（前次已在 §10 落地）：本轮除复核外，
> 完成 ① 手册第 4 项按用户**给定字面**对齐（措辞差异：`±100%` 前不带「Saty」、
> 「**2026-09-15 用户追加起亦装配**」加粗）② 影子新增**只读** `--trend-gate` 口径开关。

| 项 | 状态 | 位置 |
|---|---|---|
| ① ARMED 继承趋势日门控（布防 + 触发 / `±100%` 亦适用 / 无结论 fail-closed） | **已在位** | `balanced_day_boundary.py` `saty_trend_gate_decision()` + `check_saty_armed_trigger_guard()` 闸门④；`option_seller_manager.py` `_saty_trend_gate()`、布防门控、触发传参 |
| ② 触发复校 ① 的 L0-B 体制对齐 | **已在位** | `option_seller_manager.py` `_resolve_trend_regime_for_l0b()`；`detail['gates']['mask']['l0b']['regime_source']` |
| ③ 过期计数 → 不变量断言 | **已在位** | `test_quant_pivot_tier_lock.py`（`_EXPECTED_CALLS_INFO = 4` 信息性 + 注释注明外部来源） |
| ④ 手册矛盾修正（HTML + MD 均改） | **本轮按给定字面对齐** | 见 §11.1 |
| 附 | 影子只读口径开关 | `balanced_day_shadow.py` `--trend-gate {veto_opposing,require_range,off}`（**只读回放，不改生产配置**） |

### 11.1 手册第 4 项（§3.1.4.1.1 §④）落地字面
- **改前**：`**不装 ARMED 的成员**：Saty ±100%（L2/H2 等价档 · 豁免前置③④）、SPY 运行极值（随时间移动）、ES 子族 fut/fdt（ES 口径，跨标的布防不成立）—— 这三类仍只在 d ≤ 0.2 SPY 点 时即时开仓。`
- **改后**（用户字面）：`**ARMED 装配对象**：Saty ±61.8%（受限档 · 须过前置③④）与 ±100%（豁免档 · **2026-09-15 用户追加起亦装配**、不要求前置③④）；**不装 ARMED 的成员**：SPY 运行极值（随时间移动）、ES 子族 fut/fdt（ES 口径，跨标的布防不成立）—— 这两类仍只在 d ≤ 0.2 SPY 点 时即时开仓。`

### 11.2 影子门控模式对照（只读）
`veto_opposing`（= 生产缺口）与 `require_range` 在 09-11 / 09-14 / 09-15 三日**结果完全相同**（布防 1 / 1 / 1，触及 1 / 1 / 0）——**原因**：09-14 存活的布防发生在 **06:45**，而趋势引擎在 **06:45 起的逐 5 分钟读数均为「非趋势日」（`up=False, dn=False`）**（仅 06:35–06:40 读数为 `dn=True`）。⇒ 该笔在两种模式下都不被拦。**门控是逐时点判据，不是「当日曾为趋势日则全天禁」**。
