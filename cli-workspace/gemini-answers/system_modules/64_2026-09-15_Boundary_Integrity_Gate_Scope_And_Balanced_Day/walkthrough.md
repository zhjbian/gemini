# 前置④「边界有效性」适用范围收订 + 扩展到机制 ③ 平衡日边界 —— 验收报告 (Walkthrough)

- **日期**：2026-09-15
- **归档目录**：`64_2026-09-15_Boundary_Integrity_Gate_Scope_And_Balanced_Day`
- **一句话结论**：按用户口径把前置④ **收窄到 L1 / H1**（L2 / H2 豁免），并**扩展到机制 ③ 平衡日边界**（受限档位 = Smashelito 第一档 `ut1` / `dt1`，阈值 **8.0 ES 点**；`fut` / `fdt` 远档与 `day_high` / `day_low` 运行极值豁免），实现为「带名边界 + 单一权威纯函数 + 评分器方向选择处统一裁决」，**29 + 25 条契约测试全绿**、既有套件无回归、真实数据复现 `dt1` 被拦。

---

## 1. 交付结果速览

| 项 | 结果 |
|---|---|
| 机制 ② 前置④ | **只约束 L1 / H1**；L2 / H2 返回 `applicable=False`（reason 明确「1-SD 极值档位豁免」），引擎不再拦截 |
| 机制 ③ 前置④ | 新增；**只约束 `ut1` / `dt1`**，阈值 **8.0 ES 点**，含等号；`fut` / `fdt` 与运行极值豁免 |
| 判定位置 | 机制②：布防时点（QUALIFIED / ARMED）+ 触发侧兜底；机制③：**评分器方向选择处单点**（该机制无条件单链路，无 TOCTOU 窗口） |
| 留痕 | 机制② `debug_info.boundary_integrity_upper/_lower`；机制③ `breakdown.boundary_integrity_gate[方向]` |
| 探针 | 机制②：L2/H2 行显示「档位豁免」；机制③：新增「前置：边界有效性（边界级 · 仅 ut1/dt1）」行 |
| 测试 | 机制② `test_qp_boundary_integrity_gate` **29/29**；机制③（新增）`test_balanced_day_boundary_integrity_gate` **25/25**；模块57 `test_balanced_day_prev_close_gate` 24/24；`test_intraday_probe` 34/34；其余套件无回归 |
| 服务 | `http://127.0.0.1:5005/bbt_option_seller` → **200** |

## 2. 真实数据验证（2026-09-15 11:10 ES，本机 DB 实取）

上下文（`load_balanced_day_context('2026-09-15','11:10')`）：

```
day_high = 7682.50   day_low = 7646.25   px = 7659.25
key_levels_named = {'ut1': 7711.0, 'fut': 7757.0, 'dt1': 7659.0, 'fdt': 7620.0}
prev_close(ES)   = 7625.0
nearest_boundary_named(px, dh, dl, named) = (7682.5, 'day_high', 7659.0, 'dt1')
```

闸门逐档位实测：

| 边界 | 方向 | 判据 | 结果 |
|---|---|---|---|
| `dt1 = 7659.0` | BULLISH | `day_low 7646.25` 低于 `dt1` **12.75 点** ≥ 8.0 | **拦截**（破位后回抽） |
| `ut1 = 7711.0` | BEARISH | `day_high 7682.50` 高于 `ut1` −28.5 点（未触及） | 放行 |
| `fdt = 7620.0` | BULLISH | 远档 ⇒ 豁免（即便被跌破也不拦） | N/A |
| `fut = 7757.0` | BEARISH | 远档 ⇒ 豁免 | N/A |
| `day_low` | BULLISH | 运行极值 ⇒ 豁免（「被自己突破」定义上不成立） | N/A |

> 说明：该时点两侧候选同时受两条前置约束 —— 前置③（昨收方向）先拦下 `dt1` 做多（`dt1 7659 > 昨收 7625`，缺口日保护），
> 前置④ 独立地给出**同一结论**（`dt1` 已被有效跌破 12.75 点）。
> 两条前置互为冗余校验，任一不满足即拦截；单测中另用 `prev_close=7700` 的夹具把前置④ **隔离**出来单测。

机制 ② 收窄实测（SPY 口径，模块62 的事故夹具）：

```
L1 → (False) Boundary integrity gate (L1 long) failed: session low 756.34 is 1.48 pts below L1=757.82 ...
L2 → (True,  'L2: 1-SD 极值档位豁免「边界有效性」前置（本项仅约束 L1 / H1） -> integrity gate N/A.')
H1 → (False) ... H1 ... blocked ...
H2 → (True,  'H2: 1-SD 极值档位豁免 ... -> integrity gate N/A.')
```

## 3. 探针实测（机制 ③，`balanced_cfg.enabled=True`）

```
verdict  : REJECTED
rationale: 测试点统一口径【做多】：③ 评分器否决：Prev-Close gate (balanced BULLISH) failed:
           nearest lower boundary 7659.00 >= PrevClose 7625.00 -> Bull Put blocked (gap-up ...)
判据行    : 前置：昨收方向（边界级 · 下侧边界）      passed=False
           前置：边界有效性（边界级 · dt1）         passed=False   ← 本模块新增
```

## 4. 测试与回归

```
test_qp_boundary_integrity_gate ............. Ran 29 tests   OK   （含改写后的「L2/H2 豁免」用例）
test_balanced_day_boundary_integrity_gate ... Ran 25 tests   OK   （本模块新增）
test_balanced_day_prev_close_gate ........... Ran 24 tests   OK
test_conditional_order_trigger_3131 ......... Ran  9 tests   OK
test_qp_prev_close_gate ..................... Ran 21 tests   OK
test_intraday_probe ......................... Ran 34 tests   OK
test_qp_meta_parse / strike_anchor_3131 / force_dry_degrade /
min_open_credit_dte_fallback / l1_h1_breakeven_stop /
isolation / journal_* ×4 / tv_exit_label_overlap ......       OK
test_live_resting_limit_order ............... FAILED(1)  ← 预先存在（git stash 基线复现同一失败，与本改动无关）
test_quant_pivot_option_seller .............. OK（以 PyTools.option_seller.* 从项目根导入时 0 错 0 失败；
                                              目录模式直跑是已知的 PyTools 包路径问题）
```

新增测试覆盖要点（`test_balanced_day_boundary_integrity_gate.py`）：
① `nearest_boundary_named` 选中 `dt1`（0.25 点）而非 `day_low`（13.0 点）；
② 恰好 8.0 点算突破、7.99 点放行；③ 双向对称（`ut1` 被突破 ⇒ 禁做空）；
④ **反证：`fut` / `fdt` 即便被有效突破也必须放行**（豁免优先于幅度判据）；
⑤ 运行极值豁免；⑥ 缺数/非法值 `nan`·`inf` → fail-open + `data_missing`；
⑦ 选择器回退（首选被拦 ⇒ 试对侧；两侧全拦 ⇒ `None`）；⑧ 3 元组候选向后兼容（N/A）；
⑨ 上下文带名贯通（`key_levels_named` 与 `key_levels` 同源同长度）；
⑩ 探针判据行存在 + 规则引用 `§3.1.4.1.9` + 真实数据 `dt1` 行为 `False`。

## 5. 规则手册同步（HTML + MD 双写）

| 位置 | 内容 |
|---|---|
| §3.1.3.1 前置规则 ④ 行 | 标题「仅 L1 / H1」；新增「适用范围（L2/H2 豁免）」条目（含理由）；机制归属补入机制③ 并指向新节 |
| §3.1.4.2 | 新增「边界级前置 · 边界有效性（未被有效突破 · 2026-09-15 新增）」完整条目（判据 / 映射 / 阈值 / fail-open / 留痕 / 案例） |
| **HTML §3.1.4.1.9（新节）** | 判据表（双向）+ 与机制② 的对称映射 + 尺度铁律 + 数据缺失口径 + 留痕 + 带名边界实现要点 + 真实案例 |
| 机制③ 概览 | 昨收方向条目之后新增一条指向 §3.1.4.1.9 |

校验：HTML 标签配平（`div`/`ul`/`li`/`table`/`h6` 差值全为 0）；MD 与 HTML 口径一致。

## 6. 遗留与说明

1. **fail-open vs fail-closed 尚未由用户最终确认**（模块62 遗留问题）：两条机制的「边界有效性」现均为 **fail-open**，
   而机制③ 的「昨收方向」前置为 **fail-closed**。手册已写明两者理由与差异；若用户要求统一为 fail-closed，改动点仅两处纯函数的缺数分支。
2. 机制③ 生产开关 `balanced_day_config.enabled` 当前为 **False**：本项随开关生效，未改变当前行为。
3. 机制③ 的「远档」判定依赖 Smashelito 字段名（`ut1/fut/dt1/fdt`）：若上游未来改字段命名，`BALANCED_INTEGRITY_LEVELS` 与
   `nearest_boundary_named()` 的映射需同步（已在常量处集中定义，便于一处修改）。
