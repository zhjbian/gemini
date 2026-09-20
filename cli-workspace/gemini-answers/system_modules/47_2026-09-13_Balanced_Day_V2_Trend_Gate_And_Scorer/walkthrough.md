# 验收报告：平衡日边界机制 v2（趋势日门控 + 评分器 v2 + 命名统一）

- **日期**：2026-09-13
- **触发标签**：`AUTO_BALANCED_DAY_BOUNDARY`（旧别名 `AUTO_RANGE_BOUNDARY` / `AUTO_MOVE_END` 仅历史归类）
- **归档目录**：`47_2026-09-13_Balanced_Day_V2_Trend_Gate_And_Scorer`
- **样本**：2026-08-27 ~ 2026-09-11 共 **12 个交易日**，窗口 06:35–11:30，窗口内 **446 行**（v1 口径 188 行出方向 / v2 口径 283 行出方向）
- **结果口径**：未来 30 分钟（6 根 5m 行）ES 点位 MFE/MAE；**adverse（假信号）= 方向不利偏移 MAE > 12 ES 点**

---

## 1. 改动清单

| 层 | 文件 | 改动 |
|---|---|---|
| 文档 | `system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html` | §1.2 三段式重构、§1.4 压缩为判读层、§3.1.4 按 §3.1.3 模板重构、§3.1.4.1 具体化、§3.1.4.4.5 新增证据节、6 处一致性修复 |
| 代码 | `PyTools/quantdata/trend_regime.py` | 新增可选 `window_end`（默认 11:00，既有调用方零影响） |
| 代码 | `PyTools/option_seller/balanced_day_boundary.py` | 新增 `score_balanced_day_boundary_v2` + `W2` / `V2_SCORE_THRESHOLD` / `V2_DIRECTION_GATE`（v1 未改动一行） |
| 代码 | `PyTools/option_seller/balanced_day_data.py` | **新增**（由 `move_end_data.py` 改名）：`load_balanced_day_context()` |
| 代码 | `PyTools/option_seller/balanced_day_shadow.py` | **新增**：影子回放 CLI，支持 `--scorer v2/v1`，输出 `/tmp/balanced_day_shadow_*.json` |
| 代码 | `PyTools/option_seller/move_end_data.py` / `move_end_shadow.py` / `move_end_evaluator.py` | 改为显式兼容薄壳（转发 + 别名） |
| 代码 | `PyTools/option_seller/option_seller_manager.py` | 命名统一 + 新配置键 + v2 调用 + v1 影子 + 趋势门控 + 边界确认收紧 + 组数夹取 |
| 代码 | `bbt_data_web/data_app/bbt_option_seller.py` | 新路由 `/api/option_seller/balanced_day_config`（旧路径为同一处理器别名） |
| 代码 | `PyTools/order_flow_analysis/{order_flow_config,of_contract,backfill_order_flow_signals}.py` | 注释中的旧模块名同步 |
| 配置 | `Config/option_seller_balanced_day.json` | **新增**（旧文件 `option_seller_move_end.json` 自动迁移，旧文件保留为回退源） |

## 2. 验收证据

### 2.1 趋势日判据判别力（在产生信号的行上）

| 分组 | n | 假信号率 | 净(MFE−MAE) | MFE>MAE |
|---|---|---|---|---|
| 旧口径「非趋势日」 | 21 | **19%** | +5.0 | 71% |
| 旧口径「趋势日」 | 71 | **6%** | +3.2 | 65% |
| SPY 引擎「非趋势日」 | 39 | **0%** | +4.6 | 82% |
| SPY 引擎「趋势日」 | 53 | **15%** | +2.9 | 55% |
| **SPY 引擎「逆向趋势」** | 43 | **19%** | +0.3 | 44% |
| **SPY 引擎「非逆向」** | 49 | **0%（0/49）** | **+6.6** | 86% |

- 两法一致率 **65%**（A 趋势/B 非趋势 106 行；B 趋势/A 非趋势 51 行）；标记率：旧 47%（210/446）、SPY 引擎 35%（155/446）
- **全部 8 个假信号 100% 落在「逆向趋势」组**
- SPY 引擎与事实一致：09-03 净 +46.5 ⇒ 标记 88%；09-04 净 −28.5 ⇒ 56%；09-07（振幅 10.2、净 −5.8，inside day）⇒ 0%

### 2.2 v1 评分器有效性（v2 修订依据，188 个已出方向样本）

| 分档 | n | 假信号率 | 95%CI | 净 |
|---|---|---|---|---|
| 45–69（组数 0） | 96 | 10% | 6–18 | +1.9 |
| 70–84（1 组） | 65 | 6% | 2–15 | **+5.2** |
| 85+（原映射 2 组） | 27 | **15%** | 6–32 | **−0.2** |

- **A 与 C 完全共线**：188/188 行 `A>0 ⇔ C 到达`；C 的「接近 / 仅突破失败」分支命中 **0**
- **D 为负向**：D 命中 19 行 → 21%（4/19）；未命中 169 行 → 8%
- **LOO**：去掉 A ⇒ 命中 0；去掉 C ⇒ 2.2 次/日、15%、−0.8；去掉 D ⇒ 85 命中、7%、+3.9；**只用 A+B ⇒ 7.5 次/日、6%、+4.2**（优于五维 9%/+3.6）

### 2.3 v2 + 门控标定（门槛 × 门控）

| 配置 | n | 次/日 | 假信号率 | 净 |
|---|---|---|---|---|
| v2 @70 × 无门控 | 114 | 9.5 | 9% | +2.4 |
| **v2 @70 × veto_opposing（生产缺省）** | **49** | **4.1** | **4%（2/49）** | **+4.8** |
| v2 @65 × veto_opposing | 65 | 5.4 | 3% | +4.6 |
| v2 @65 × require_range | 48 | 4.0 | 2% | +4.2 |
| v2 @75 × veto_opposing | 23 | 1.9 | 0% | +7.7 |

### 2.4 文档 ↔ 代码一致性

- **机器校验 35 项全通过**（`/tmp/audit_doc_code.py`）：v1/v2 权重与代码逐值一致、缺省值一致、门控三档与 fail-closed 已写入、在线配置 11 键逐一对应、4 类旧措辞零残留
- **数据复刻 4 组全一致**（用当前生产决策序重放 12 交易日，核对 §3.1.4.4.5 每一行）
- 已修复审计发现的 **6 处**手册滞后：§3.1.1.4 概览表行、§3.1.1 迁移说明、§3.1.4.1 判定链、§3.1.4.1 缺省参数列表、§3.1.4.1.5 组数、§3.1.4.4.4 标题与脚注

## 3. 运行验证（实机）

| 项 | 结果 |
|---|---|
| 配置自动迁移 | 日志 `2026-09-13 20:55:41 WARNING: OptionSeller 平衡日边界: 配置已由旧名迁移 → .../option_seller_balanced_day.json` |
| 新接口 | `GET /api/option_seller/balanced_day_config` 正常返回配置；旧路径同处理器别名可用 |
| 热加载健康 | 重载后日志无 ImportError / SyntaxError / AttributeError / TypeError（仅既有券商 refresh token 过期报错） |
| 影子 CLI | `balanced_day_shadow.py --scorer v2`：2026-09-11 命中 18 次、0 假信号，输出 `/tmp/balanced_day_shadow_recent.json` |
| 语法 | 全部改动文件 `py_compile` 通过 |

## 4. 已知残余风险

1. **门控依赖 yfinance SPY 1 分钟**（按日缓存）：取数失败/越窗口 ⇒ 缺省 fail-closed 不出信号（漏做而非逆势）。周末实测引擎返回 `(False, False, None)`。
2. **2 例残余假信号未被覆盖**：① `2026-08-27 08:00` 空头——边界被打穿后上冲 16.5 点（"边界失效"型）；② `2026-09-09 06:55` 多头——引擎判多头趋势日且**方向一致**故放行、MAE 12.5 点（切 `require_range` 可拦）。
3. **样本小**：49–92 次命中、2–8 个假信号；「0%」在 n≤50 时 CI 上限仍有 7–9%，不得当作绝对保证。
4. **结果是代理指标**：ES 点位 MFE/MAE ≠ 期权价差真实盈亏（未计权利金、Delta、止损/止盈触发与滑点）。

## 5. 回退方式

- **配置级（无需改代码）**：`scorer_version=v1` 回旧评分器；`trend_gate=off` 关趋势门控；`d_enabled=true` 回开 D 维；`groups_cap=2` 回 2 组上限
- **文件级**：代码备份 `/tmp/bbt_impl2_backup_212248/`（`trend_regime.py` / `balanced_day_boundary.py` / `option_seller_manager.py`）、`/tmp/bbt_rename_backup_20260913_*`（命名改造前原件）、配置备份 `/tmp/bbt_impl2_backup_*_cfg.json`、手册备份 `/tmp/manual_pre_v2_*.html` 与 `/tmp/manual_sync_220135.html`

## 6. 复现脚本

`/tmp/analyze_balanced_day.py`（判别力 + v1 有效性）、`/tmp/calib_v2.py`（v2 标定网格）、`/tmp/v2_detail.py`（逐行明细）、`/tmp/audit_doc_code.py`（文档↔代码复检）；明细 `/tmp/balanced_day_eval.json`、`/tmp/v2_rows.json`、`/tmp/v2_calib.json`。

## 7. 后续待办

1. 兼容层清理（三个薄壳 + 旧接口别名 + 旧属性别名；需确认无外部引用）
2. `path_t_enabled` 历史键清理
3. 手册 `.md` 与 HTML 整体对齐（结构差异较大）
4. 残余假信号两条处理规则（边界被打穿否决；趋势日内顺向信号降级）
5. 持续 A/B：`evidence.v1_shadow` + `balanced_day_shadow.py --scorer v1|v2`
