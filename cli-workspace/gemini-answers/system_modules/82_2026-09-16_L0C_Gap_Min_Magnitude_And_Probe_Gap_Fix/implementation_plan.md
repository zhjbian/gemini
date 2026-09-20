# L0-C 背景支「跳空」最小幅度门槛 + 探针缺口口径修正 实施计划 (Plan)

- **日期**：2026-09-16（PT）
- **归属模块**：**M09. Option Seller 自动化交易引擎与开仓仲裁系统**（能力域 = L0 统一门槛前置过滤 / 开仓仲裁；交叉引用 **M10. Option Seller 多机制触发系统** —— L0-F⑨ 单边掩码此前记于 M10，本改动按「一个改动一个最相关 module」只落在 M09，并在 M09 历史行点名）
- **触发场景**：用户在 `http://127.0.0.1:5005/bbt_option_seller` →「当日高低点自动触发机制检测」卡片看到 **08:45 高点#1** 的 L0-C 行显示「多 ✓空 ✗」，问「为什么不满足开空仓条件」，并要求把这次门槛改动按规则 (11)/(10) 落入规则手册与模块页。
- **性质**：**门槛缺失修复 ×1（真问题 B）＋ 探针口径错误修复 ×1（真问题 A）＋ 实盘取数审计（真问题 C，仅记录、不接线）**
- **技术栈**：Python 3.11 · `PyTools/option_seller/`（`auto_mechanisms` 编排层 + `intraday_probe` 探针）· `PyTools/order_flow_analysis/ema_engine.py`（纯函数复用块）· `PyTools/pivots/quant_pivot.py`（缺口分界口径）· Flask（`bbt_data_web`）· unittest 契约测试 · 规则手册 HTML/MD 双写 · `bbt_trading_modules.html` 模块页

---

## 1. 用户问题与诊断链

### 1.1 问题原文意

08:45 高点#1 的 L0-C 行「多 ✓空 ✗」—— 该点统一口径方向为 **做空（卖 Call / Bear Call Spread，`mandated_side = BEARISH`）**，为何空侧不通过？

### 1.2 诊断链（三层，缺一层都不足以解释）

| 层 | 事实（2026-09-16 08:45 高点，探针实测） | 结论 |
| :--- | :--- | :--- |
| 判据 | L0-C 的 `l0_side_ok = side not in masked`；此刻 L0-C 掩码 = `BEARISH` | 空侧 ✗（直接原因） |
| 掩码三连 | ① L0-C⑥：`active=True; 掩码=BEARISH`（高开 +0.279% 背景成立，且距 15m 带上沿 0.079% ≤ 0.10%）；② L0-F⑨：偏向 `BULLISH` ⇒ 掩 BEARISH；③ L0-B⑤：`Pos=78.3% ≥ 60%` ⇒ 掩 `BULLISH`。合并掩码 `['BEARISH','BULLISH']` | 双向掩码，本周期等价于不交易（保守侧） |
| 三维共振 | 做空侧 **3** 分（门槛 ≥ 55）：维度1 订单流 `0/60`（**无取数**）、维度2 Gamma `0/30`（对侧 24）、维度3 EMA `3/10`（对侧 10）；对侧做多 **34** 分；`qualified_bear=False` | **即使没有 L0-C 掩码，这个高点也开不了空** |

**因此**：用户看到的「空 ✗」确由 L0-C 造成，但**不是唯一原因、也不是决定性原因**；L0 之后还有三维共振与 Setup 闸门两道更硬的门槛。

---

## 2. 三个发现

### (A) 探针 `gap_pct` 口径错误（已修）

| 项 | 内容 |
| :--- | :--- |
| 原实现 | `_pct_ago(bars_upto[0].spy_open, bars_upto[0].spy_close)` = **当日首根 5m bar 自身的开收差** |
| 语义冲突 | 手册 L0-C 的「跳空低开 / 跳空高开」= **RTH 开盘 vs 昨收**；活引擎/回测脚本的 `pivot_data.gap_pct` 亦为 RTH 开盘 vs 昨收 |
| 实测（2026-09-16） | 原口径 **+0.036%**（噪声级）→ 真实缺口 **+0.279%**（QuantPivot `open 759.50` / `prev_close 757.39`） |
| 修复 | 改用 QuantPivot 的 `open` / `prev_close`；**两者缺一即 `None`**（fail-open，不伪造） |

### (B) L0-C 背景支「跳空」无最小幅度要求（已修 · 本次主改动）

| 项 | 内容 |
| :--- | :--- |
| 原实现 | `gap_pct < 0`（下行）/ `gap_pct > 0`（上行）—— **任何方向、任何幅度**的缺口都让背景成立 |
| 后果 | 0.01% 量级的噪声缺口也会打开「EMA 禁区一票否决」的语境前置 |
| 修复 | 新增常量 **`GAP_MIN_VETO_PCT = 0.05`**（%），背景支改为 `gap_pct <= -0.05%` / `gap_pct >= +0.05%`，**双侧严格对称** |
| 阈值取值依据 | 与系统**既有缺口判定分界**一致：QuantPivot 以 `gap_threshold = 0.0005 × 开盘价`（即 0.05%）把当日分为 `GAP_UP` / `GAP_DOWN` / `FLAT`（`PyTools/pivots/quant_pivot.py`）。取该值即复用同一套「什么算缺口」口径，不引入第三方阈值 |
| 参考刻度 | **0.05%**（本门槛 · 噪声地板）< **0.30%**（引擎开盘大幅缺口保护 `|gap_pct| >= 0.30%`，`option_seller_engine.py` Hard Veto 6）< **0.40%**（本机制**日内极值支路**阈值） |
| 边界语义 | **恰好 0.05% 视为达标**（`<=` / `>=`，含等号）；**0.049% 不达标** —— 已由契约测试锁定 |

### (C) 实盘取数审计：`gap_pct` 在生产链没有生产者（**仅记录，未接线**）

| 支路 | 实盘可用性 | 证据（实盘取数链已逐点核实） |
| :--- | :--- | :--- |
| 日内极值支（`day_low_pct <= -0.40%` / `day_high_pct >= +0.40%`） | **可用** | `PyTools/order_flow_analysis/order_flow_sentinel.py:934-935` 计算 `pivot_dict['day_high_pct']`、`pivot_dict['day_low_pct']`（口径 = 相对当日 RTH 开盘代理，取首个 5m bin 的 `price_start`），并在**同一轮评估**中于 `order_flow_sentinel.py:950` 以 `pivot_data=pivot_dict` 传入卖家引擎；`auto_mechanisms.ema_forbidden_zone_mask` 的取值链是 `_num(om…, raw…, pivot…)`，**对 pivot 有兜底**（`auto_mechanisms.py:328`） |
| 跳空支（`gap_pct`） | **当前实际不可触发（待接线）** | `gap_pct` 在**生产链完全没有生产者** —— 全仓仅探针与回测脚本构造它；QuantPivot（`PyTools/pivots/quant_pivot.py`）返回 `open` / `prev_close` / `gap_mode` 而**没有** `gap_pct`；哨兵的 `pivot_dict` 也未写入该键；`option_seller_manager.py:1615` 读 `pivot_data.gap_pct` 或 `om.gap_pct` **均为空** |
| **旁证：三键均不落库** | 不能用「查库」验证 | 实测 2026-09-16 的 **79 行** `order_flow_signals.quantitative_metrics` 中 `gap_pct` / `day_high_pct` / `day_low_pct` **均未出现**（0 行命中；仅 SELECT 只读复核）⇒ 实盘是否生效**必须在哨兵进程内看** |

**结论**：**实盘 L0-C 目前只有「日内极值 ≥ 0.40%」支路可触发；「跳空 ≥ 0.05%」支路因缺 `gap_pct` 而不可触发**（探针之所以能触发，是因为它自行构造了该输入，而原口径还是错的）。本次改动的实际影响 = 仅「剔除噪声级缺口 + 修正探针口径」，在**探针 / 回放链路**立即生效；「跳空」支在实盘要真正生效，仍需**单独接线**，故标注为 **待接线（未实施，需用户确认）**。

**建议接线方式（未实施）**：在哨兵侧按 `(RTH 开盘 − 昨收) / 昨收 × 100` 产出 `pivot_dict['gap_pct']`（与 `day_*_pct` **同处、同一 SPY 尺度**）。这样探针与实盘口径一致，且 `auto_mechanisms` 无需改动（其 `_num(pivot, om, raw)` 兜底已就绪）。**该接线会改变实盘拦截行为，须用户单独确认，本次不实施。**

---

## 3. 设计取舍

| # | 取舍 | 理由 |
| ---: | :--- | :--- |
| 1 | **为何取 0.05%，而非 0.10% 或 0.30%** | 0.05% 是系统**既有**的 FLAT/GAP 分界（QuantPivot `0.0005 × 开盘价`），复用同一套「什么算缺口」口径 ⇒ 零新增自由度、可解释、与其它模块不冲突。取 0.10% 会把 QuantPivot 判定为 GAP 的弱缺口排除在本闸门背景之外（两处口径打架）；取 0.30% 会在开盘 45 分钟之后（引擎大幅缺口保护只覆盖 06:30–07:15）漏掉 0.05%–0.30% 区间的真实跳空日 |
| 2 | **为何只改背景，不动空间条件** | 空间条件（距带沿 ≤ 0.10% / 带内或带外 ≤ 0.50% 且未站稳 2 根）已由 2026-09-13 的口径修补验证，且「有界」设计是为避免单边日长期掩码多头（过度拦截）。本次问题在**背景**，不在空间；同批改动空间条件会混淆归因 |
| 3 | **为何两份实现都要改** | 权威实现 `auto_mechanisms.ema_forbidden_zone_mask`（面向 `MechanismContext`）与纯函数版 `ema_engine.forbidden_zone_mask`（离线回放 / 单测 / 其他调用方复用）是**同一判据的两份代码**；只改一份会让「探针与实盘」「回放与实盘」出现口径分叉。本次同时把纯函数版签名默认值定为 `gap_min_pct: float = 0.05`，与常量对齐，并新增「两份实现结论一致」的契约测试 |
| 4 | **为何 (C) 只记录、不接线** | 接线 = 给生产链新增写者 ⇒ **改变实盘 L0-C 拦截行为**（此前「跳空」支从未生效，接线后会开始生效）。按用户既定纪律（行为改动须单独确认 + 先纸面回归），本次只把**事实与建议**写入手册与归档，等待用户确认 |

---

## 4. 改动清单与关键代码点

| 文件 | 改动 | 状态 |
| :--- | :--- | :--- |
| `PyTools/option_seller/auto_mechanisms.py` | ① 新增常量 `GAP_MIN_VETO_PCT = 0.05`（含取值依据与参考刻度注释，约 212–219 行）；② 背景支 `bearish_ctx` / `bullish_ctx` 改为 `<= -gap_min` / `>= gap_min`（约 385–408 行）；③ `out["thresholds"]` 记录 `gap_min_pct / day_extreme_pct / band_tol_pct / band_zone_pct / stand_bars`；④ `veto_bull` / `veto_bear` 文案写出门槛；⑤ L0-C 闸门 `actual` 增回显 `gap=%+.3f%%`，`threshold` 改为含「背景」段的完整口径（约 786–797 行） | **已落地并实测** |
| `PyTools/order_flow_analysis/ema_engine.py` | 纯函数版 `forbidden_zone_mask(..., gap_min_pct: float = 0.05)` 同步同一语义；`detail.inputs` 增 `gap_min_pct` / `day_extreme_pct`（约 286–320 行） | **已落地并实测** |
| `PyTools/option_seller/intraday_probe.py` | `gap_pct` 口径改为 QuantPivot `open` / `prev_close`（真实缺口），缺一即 `None`（约 951–960 行） | **已落地并实测** |
| `PyTools/option_seller/test_l0c_gap_floor.py` | **新增**契约测试 10 项：对称性 / 边界语义（恰好 0.05% 达标、0.049% 不达标）/ 日内极值支不受缺口门槛影响 / 语境与位置必须同侧 / 两份实现口径一致 / 闸门读数回显门槛与实测 gap | **10/10 PASS** |

**关键代码点（闸门读数前后对照）**

```
# 改前
actual    = "active=%s; 掩码=%s"                                → "active=True; 掩码=BEARISH"
threshold = "距带沿 <= 0.10%；或带内/带外 <= 0.50% 且未站稳 2 根"

# 改后
actual    = "active=True; 掩码=BEARISH; gap=+0.279%"
threshold = "背景：缺口 >= 0.05%（对称）或 日内极值 >= 0.40%；
             空间：距带沿 <= 0.10% 或 带内/带外 <= 0.50% 且未站稳 2 根"
```

---

## 5. 验证方法

1. **契约测试**：`option_seller/test_l0c_gap_floor.py` 10 项全绿（含边界 0.05% / 0.049%、双侧对称、两份实现一致、闸门回显）。
2. **回归测试**：`option_seller/test_intraday_probe.py` 34 项、`option_seller/test_l0_gamma_one_sided_gate.py` 31 项全绿（合计 75 项）。
3. **只读活体验证**：`GET /api/option_seller/intraday_extremes_probe?date=2026-09-16`（路由注释明确「绝不触发开仓 / 布防 / 写库」）—— 08:45 高点 L0-C 行读数见 §6。
4. **今日结论不变校验**：真实缺口 +0.279% ≥ 0.05% 且距 15m 带上沿 0.079% ≤ 0.10% ⇒ **仍掩码 BEARISH**；本次改动的实际作用 = **剔除噪声级缺口** + **修正探针口径**，不改变 2026-09-16 当日结论。

---

## 6. 活体读数（2026-09-16 08:45 高点#1，探针实测）

```json
{
  "time": "08:45", "kind": "HIGH", "mandated_side": "BEARISH",
  "l0": { "masked": ["BEARISH", "BULLISH"],
    "gates": [
      { "id": "L0-C⑥", "name": "EMA 禁区反向开仓掩码", "passed": false,
        "actual": "active=True; 掩码=BEARISH; gap=+0.279%",
        "threshold": "背景：缺口 >= 0.05%（对称）或 日内极值 >= 0.40%；空间：距带沿 <= 0.10% 或 带内/带外 <= 0.50% 且未站稳 2 根",
        "per_direction": { "BEARISH": false, "BULLISH": true } },
      { "id": "L0-F⑨", "actual": "active=True; 偏向=BULLISH; 掩码=BEARISH" },
      { "id": "L0-B⑤", "actual": "Pos=78.3%（is_trend_day=False）⇒ 掩码 BULLISH" } ] },
  "inputs": { "ema_forbidden_zone": { "thresholds": { "band_tol_pct": 0.1, "band_zone_pct": 0.5,
              "day_extreme_pct": 0.4, "gap_min_pct": 0.05, "stand_bars": 2 },
              "inputs": { "gap_pct": 0.279, "day_high_pct": 0.294, "day_low_pct": -0.097, "price": 761.08 } } },
  "mechanism_5m_synthesis": { "bear_score": 3, "bull_score": 34, "qualified_bear": false, "verdict": "REJECTED" }
}
```

---

## 7. 回滚方式

```bash
# 代码（PyTools 是独立 git 仓库）
git -C PyTools checkout -- option_seller/auto_mechanisms.py option_seller/intraday_probe.py order_flow_analysis/ema_engine.py
rm PyTools/option_seller/test_l0c_gap_floor.py     # 新增的契约测试
```

文档侧回滚：恢复同目录 `.bak-20260917_002415` 备份（手册 `.md` / `.html` 与模块页）。

---

## 8. 不影响面（同批未动）

| 项 | 状态 |
| :--- | :--- |
| 日内极值支路阈值（`day_low_pct <= -0.40%` / `day_high_pct >= +0.40%`） | **未动** |
| 空间条件（距带沿 ≤ 0.10%；带内/带外 ≤ 0.50% 且未站稳 2 根） | **未动** |
| L0-B⑤ 价格日内位置掩码、L0-F⑨ Gamma 单边掩码 | **未动** |
| 探针其余 13 项判据与 7 个机制卡片的判据展示 | **未动** |
| 实盘行为（门槛收紧 / 探针口径这一批） | **零变化** —— (C) 未接线，「跳空」支在实盘本就不生效；本批未新增/未删除任何写者。<br/>**（2026-09-16 追加更正）**：同日另有用户指定的 **L0-C 停用（bypass 仅观测）**，该动作**确实改变实盘 L0 行为** —— L0-C 不再参与任何方向的否决，详见 §10 |
| 数据库 / 部署 / 服务重启 | **零操作**（探针路由为只读 GET，注释明确不写库） |

---

## 9. 本次交付的文档同步（规则 (11)/(10)）

| 文档 | 修订位置 |
| :--- | :--- |
| `gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.md` / `.html` | §3.1.1.1 **L0-C** 小节：(1)(2) 两支「触发背景」补 **`|缺口| >= 0.05%`**（双侧对称）+ 依据段；「数据依赖」补缺口口径（RTH 开盘 vs 昨收）与探针误用口径的更正说明；「实现现状」段更正为**实盘生效范围**（日内极值支路可用 / 「跳空」支无生产者、待接线、含建议接线方式） |
| `bbt_trading_modules.html` | **M09. Option Seller 自动化交易引擎与开仓仲裁系统** 历史表新增 1 行（2026-09-16）；同步 TOC 徽标、总览 `badge-count`、模块「累计演进历程」与头部「归并自 N 项」 |

---

## 10. 追加（2026-09-16 用户指令）：在 L0 统一门槛中停用（bypass 仅观测）

- **用户指令原文**：「保留 code path for EMA 禁区反向开仓掩码，但暂时禁掉它在 第 0 层统一门槛，也就是说：L0 规则里不再检测 L0-C EMA 禁区否决」。
- **性质**：**闸门停用（bypass，仅观测）** —— 只改「在 L0 统一门槛中的生效状态」，**不改判据、不改阈值、不删代码、不改探针路径**（手册判据正文保留不动）。

### 10.1 实现方式

| 项 | 内容 |
| :--- | :--- |
| 常量 | `PyTools/option_seller/auto_mechanisms.py` 新增 `L0C_ENFORCE = False`（紧随 `L0A3_ENFORCE`，同款注释风格：保留实现与阈值，含 `GAP_MIN_VETO_PCT = 0.05%`） |
| bypass 语义（同 L0-A③） | `check_layer0()` 仍逐轮调用 `ema_forbidden_zone_mask(ctx)`，结果写入 `layer0.detail["ema_forbidden_zone"]` 并新增 `enforce` 观测字段；**不再并入** `res.masked_directions`（仅 `enforce=True` 时并入） |
| 闸门读数 | `L0-C⑥`：`bypass=True`、`passed=True`、`per_direction={'BULLISH':True,'BEARISH':True}`；`actual` = `active=True; 掩码=BEARISH; gap=+0.279%; 已停用（仅观测）`；`threshold` 末尾追加 `（当前 **bypass**：只观测、不拦截）`；`note` = `enforce=False ⇒ 已停用（2026-09-16 用户指定，仅观测）；本轮本应掩码 BEARISH` |
| 观测日志 | `run_cycle()` 新增（与 L0-A③ 那条并列）：`L0-C⑥ EMA 禁区闸门【暂时停用 · 仅观测】：本轮本应掩码 BEARISH，已 bypass`（仅当 `enforce=False` 且本应掩码非空时打印） |
| 回启开关 | `L0C_ENFORCE = True` 或 `mgr.l0c_enforce = True` |

### 10.2 代码级实测（同一 ctx：gap=+0.279%、价格贴 15m 带上沿）

| 状态 | `L0-C⑥` | 合并掩码 | `ok` | detail |
| :--- | :--- | :--- | :--- | :--- |
| 默认（`L0C_ENFORCE=False`） | `passed=True` `bypass=True` `per_direction={'BULLISH':True,'BEARISH':True}` | **`['BULLISH']`**（只剩 L0-B⑤ 高位掩多） | `True` | `enforce=False`、`masked=['BEARISH']`（观测值保留） |
| `mgr.l0c_enforce=True` | `passed=False` `bypass=False` `per_direction={'BULLISH':True,'BEARISH':False}` | 含 `BEARISH` | — | `enforce=True` |

> 该 ctx **不含 L0-F 读数**，故默认态合并掩码只剩 `['BULLISH']`；**真实 08:45 时点**的合并掩码仍为 `['BEARISH','BULLISH']` —— 其中 `BEARISH` 来自 **L0-F⑨**（见 §10.4）。

### 10.3 测试

- `option_seller/test_l0c_gap_floor.py` 由 10 项扩至 **12 项，12/12 PASS**：新增 `test_gate_is_bypassed_observation_only`（默认停用：`bypass=True` / `passed=True` / 两方向放行 / detail 仍含本应掩码 `BEARISH` / **不并入** merged）与 `test_gate_blocks_again_when_enabled`（`mgr.l0c_enforce=True` 时恢复 `passed=False`、`per_direction BEARISH=False`、merged 含 `BEARISH` ⇒ 证明 code path 完整可回启）。
- 回归：`test_intraday_probe.py` **34 OK**、`test_l0_gamma_one_sided_gate.py` **31 OK**。
- 同时修正前一轮指出的陈旧 docstring（0.10% → 0.05%、边界措辞）。

### 10.4 关键结论（务必如实，不得读成「开空现在可以了」）

- **L0-C 当前在 L0 统一门槛中停用（bypass = 只观测、不拦截）**；实现、阈值（0.05%）、探针路径、手册判据**全部保留**，可一键回启（`L0C_ENFORCE` / `mgr.l0c_enforce`）。
- **实盘影响**：原本（结合发现 (C)）实盘只有「日内极值 ≥ 0.40%」支路可能触发；停用后**该支也不再否决** ⇒ **实盘 L0-C 的净效果 = 完全不参与开仓否决**。
- **2026-09-16 08:45 高点#1 的结论不变**：该点做空**仍不满足**，原因改为 —— **L0-F⑨ SPX Gamma 单边结构掩码（仍启用，偏向 `BULLISH` ⇒ 掩 `BEARISH`）** + 三维共振做空侧仅 **3 分**（门槛 ≥55）+ `qualified_bear=False`；停用 L0-C 只是**移除三个拦截中的一条**，并不解锁该点。
- **探针卡片外观**：该行显示 `bypass` /「已停用（仅观测）」，并回显本应掩码方向与实测 `gap=+0.279%` —— 用于日后决定是否恢复启用。

### 10.5 回滚方式

```bash
# 方式一（推荐，仅改状态、零代码 diff）
#   置回 L0C_ENFORCE = True（或 mgr.l0c_enforce = True）即恢复拦截
# 方式二（回到本次停用前的实现）
git -C PyTools checkout -- option_seller/auto_mechanisms.py
```
