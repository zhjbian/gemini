# 前置④「边界有效性」适用范围收订 + 扩展到机制 ③ 平衡日边界 —— 实施计划

- **日期**：2026-09-15
- **模块**：64 `Boundary_Integrity_Gate_Scope_And_Balanced_Day`（延续模块 62 的前置④）
- **用户口径（本轮，原文）**：
  1. 「**L2/H2 不受限**」⇒ 机制 ② 的前置④ **收窄为只约束 L1 / H1**（与前置③ 昨收方向的 H2/L2 豁免完全同口径）；
  2. 「**需要扩展到平衡日边界**」⇒ 机制 ③ 平衡日边界新增同一前置（按其边界族做对称映射）。
- **技术栈**：Python 3.11 · `PyTools/option_seller/`（引擎纯函数 + 平衡日边界评分器 + 探针 + 影子回放）· unittest 契约测试 · 规则手册 HTML/MD 双写

---

## 1. 范围与设计（两件事，一个原则）

**统一原则**：破位后回抽的失效性只对「**第一档主边界**」成立 ——
第二档/极值档位（机制② 的 L2/H2、机制③ 的远档 `fut`/`fdt`、以及运行极值本身）
必然处于「极限位置」，在其外侧再叠一层熔断会把「极值反转」这一类合法机制整体掐掉。故**逐档位判定 + 第二档豁免**。

| 机制 | 边界族 | 受限档位（第一档） | 豁免档位（第二档 / 极值） | 阈值 |
|---|---|---|---|---|
| ② QuantPivot边界反向 | `L1/L2/H1/H2`（SPY 口径绝对点位） | **L1 / H1** | **L2 / H2** | SPY 0.8 点（≥2000 的高点位标的 → 8.0 点） |
| ③ 平衡日边界 | `day_high`/`day_low` + Smashelito `ut1/fut/dt1/fdt`（ES 口径） | **`ut1` / `dt1`** | **`fut` / `fdt`** + **`day_high` / `day_low`** | **8.0 ES 点**（= SPY 0.8 × 10，与本机制 ±4 点容差同尺度） |

**判据（严格双向对称，含等号）**
- 做多 BULLISH（依据**下侧**最近边界 `B`）：`day_low > B − tol` 才放行；
- 做空 BEARISH（依据**上侧**最近边界 `B`）：`day_high < B + tol` 才放行；
- 不满足 ⇒ 该方向被拦，**回退校验另一方向**（两侧全拦才 veto，不静默降级为「不出信号」）；
- 极值单调 ⇒ 一旦有效突破，该档位当日后续一律禁止该方向开仓（**单调熔断**）。

**数据缺失口径**：两条机制的前置④ 均为 **fail-open（放行）+ `data_missing=True` 留痕** ——
与机制③ 前置③「昨收方向」的 fail-closed **显式不同**（本项是幅度类判据，缺数时容差带/波幅位置仍在把关）。

## 2. 变更清单

| # | 文件 | 改动 |
|---|---|---|
| 1 | `option_seller_engine.py` | 新增常量 `QP_INTEGRITY_LEVELS = ('L1','H1')`；`check_qp_boundary_integrity()` 对 **L2/H2 直接返回 N/A（`applicable=False`，reason 注明「1-SD 极值档位豁免」）**；docstring 同步「适用范围」段 |
| 2 | `balanced_day_boundary.py` | 新增 `BALANCED_BREAK_TOL_ES = 8.0` / `BALANCED_INTEGRITY_LEVELS = ('ut1','dt1')`、`nearest_boundary_named()`（返回**带字段名**的最近上下侧边界）、`check_balanced_boundary_integrity()`（纯函数，单一权威）；`_select_direction_with_prev_close(cands, prev_close, day_low, day_high)` 现在**同时施加两条边界级前置**并留痕 `boundary_integrity`；v1 / v2 两个评分器新增 `key_levels_named` 入参、候选改为 4 元组 `(方向, 分, 边界值, 边界名)`、gate 明细写 `breakdown.boundary_integrity_gate` |
| 3 | `balanced_day_data.py` | 新增 `_load_key_levels_named()`（与 `_load_key_levels` **同一条 SQL / 同一决胜规则**，仅保留字段名）；`load_balanced_day_context()` 新增 `key_levels_named`（与 `key_levels` 同源同长度） |
| 4 | `option_seller_manager.py` | `_score_kw` 传入 `key_levels_named`（生产实时通道） |
| 5 | `balanced_day_shadow.py` | 影子回放同样保留命名版并传入（与实盘同口径，避免影子/实盘分叉） |
| 6 | `intraday_probe.py` | 机制③ 判据表新增行「**前置：边界有效性（边界级 · 仅 ut1/dt1）**」（限制档位判 `passed`、豁免档位标「本档位豁免」）；机制② 前置④ 行在 L2/H2 时改为标「**档位豁免**」文案 |
| 7 | `test_qp_boundary_integrity_gate.py` | 「逐档位独立」用例改写为「**L2/H2 豁免**」（含「即便 L2 已被跌破也放行」的反证），头部口径同步；29/29 |
| 8 | `test_balanced_day_boundary_integrity_gate.py`（新增） | 机制③ 前置④ 契约测试 **25 条**：命名边界选择 / 阈值含等号 / 双向对称 / 远档与运行极值豁免 / 缺数 fail-open / 选择器回退与 3 元组向后兼容 / 上下文带名贯通 / 探针判据行（真实数据 `dt1` 被拦） |
| 9 | 规则手册（`.html` + `.md`） | §3.1.3.1 ④ 行：标题改「**仅 L1 / H1**」、新增「适用范围（L2/H2 豁免）」、机制归属补入机制③ 并指向新节；§3.1.4.2 新增「边界级前置 · 边界有效性」条目；**新增 HTML §3.1.4.1.9**（含判据表 / 尺度铁律 / 留痕 / 真实案例），机制③ 概览处加一条指向新节 |

## 3. 为什么机制 ③ 需要「带名边界」（实现关键）

机制③ 的边界族是**值列表**（`key_levels` = `ut1/fut/dt1/fdt` 的位置序），
`nearest_boundary_values()` 只回值 ⇒ 无法判断「被判定的这个边界属于第一档还是远档」，
也就无法实现「L2/H2 不受限」的对称映射。故：
**`nearest_boundary_named()` 回 `(值, 名)`，把「档位身份」一路传到闸门**；
不传名的调用方（旧接口/旧测试）⇒ 本项 N/A（**向后兼容**，且不会误拦）。

## 4. 触发侧是否需要兜底重校验

**机制 ③ 不需要**：与机制② 不同，平衡日边界**没有条件单/布防链路**（`evaluate_balanced_day_channel()`
在 5 分钟判定周期内评分并直接出信号），故本项只需在**评分器的方向选择处**执行一次（单一时点，无 TOCTOU 窗口）。
已核验：`option_seller_manager.py` 中 `balanced` 相关代码**不产生** `conditional_orders` 记录。

## 5. 验收标准

1. `unittest test_qp_boundary_integrity_gate` **29/29**、`test_balanced_day_boundary_integrity_gate` **25/25** 通过；
2. `test_balanced_day_prev_close_gate`（模块 57）**24/24**、`test_intraday_probe` **34/34** 等既有套件不回归；
3. 真实数据（2026-09-15 11:10 ES）复现：`dt1` 被当日最低跌破 **12.75 点** ⇒ 机制③ 判据行 `前置：边界有效性（边界级 · dt1）passed=False`；
4. `L2/H2` 在机制② 中返回 N/A（`applicable=False`）且引擎不再拦截；
5. 全部改动文件 `py_compile` 通过；服务 `http://127.0.0.1:5005/bbt_option_seller` 200；
6. 规则手册 HTML 标签配平（div/ul/li/table/h6 全平衡），MD 同步。

## 6. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 阈值尺度错用（ES 8.0 vs SPY 0.8） | 机制③ **只比 ES 与 ES**（边界族与运行极值同为 ES 点，**不涉及 ES↔SPY 换算**）；阈值以常量集中定义并有单测断言 |
| 「豁免」被误实现成「漏判」 | 单测含**反证**：`fut/fdt` 即便被有效突破也必须放行（`applicable=False`）；L2/H2 同理 |
| 旧调用方（3 元组候选、不传名）行为变化 | 本项 N/A（fail-open）⇒ 仅前置③ 生效；已有单测固定该向后兼容语义 |
| 机制③ 目前 `balanced_day.enabled=False`（生产开关） | 本项随开关生效，不改变现状；开关打开即按新口径把关 |
| 回滚 | `cd PyTools && git checkout -- option_seller/{option_seller_engine,balanced_day_boundary,balanced_day_data,balanced_day_shadow,option_seller_manager,intraday_probe,test_qp_boundary_integrity_gate}.py && rm -f option_seller/test_balanced_day_boundary_integrity_gate.py`；手册用同目录 `*.bak-64-20260915_195716` 快照还原 |
