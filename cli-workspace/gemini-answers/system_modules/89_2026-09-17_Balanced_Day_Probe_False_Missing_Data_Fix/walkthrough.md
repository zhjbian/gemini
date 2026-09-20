# 平衡日边界探针「假性数据缺失」判定修正验收报告

## 概述与改动背景
在 `http://127.0.0.1:5005/bbt_option_seller` 的「当日高低点自动触发机制检测」中，当某时点（如低点 #2 08:05）的平衡日边界机制因边界距离偏大（0.44 SPY 点 > 0.30 容差上限）导致评分不足（单侧仅 11.25 分 < 45.0 方向准入门槛）而未产出候选方向时，判据表格中曾出现 4 处显示为 **`— 数据缺失`** 的假象。

**问题根因**：
底层数据（ES/SPY 现价、ES/SPY 昨收、ES/SPY 当日高低点、各档位边界、订单流、EMA）**全部完备**。之所以呈现「数据缺失」，是因为机制未出开仓方向时，后续判据未被执行，探针代码传入 `passed = None`，前端被动将所有 `passed is None` 渲染为 `— 数据缺失`，导致业务逻辑上的「未通过/通过/未触发」被严重误导为「数据缺失」。

---

## 修正明细

### 1. 评分器留痕扩展 (`balanced_day_boundary.py`)
- 在 `score_balanced_day_boundary_v2` 中将 `_nearest_bounds` 找出的双侧最近边界字典留痕在 `bd["nearest_bounds"]`：
  ```python
  bd["nearest_bounds"] = {
      "BEARISH": {"boundary": _bu, "name": _bu_nm, "subfamily": _bu_sf},
      "BULLISH": {"boundary": _bl, "name": _bl_nm, "subfamily": _bl_sf},
  }
  ```
- 完善 `check_balanced_boundary_prev_close` 与 `check_balanced_boundary_integrity` 的返回明细字典，显式注入 `det["ok"] = True/False`，确保直接调用时返回字典的判定语义完整。

### 2. 探针独立实评与语义纠偏 (`intraday_probe.py`)
- **前置：昨收方向（边界级 · §3.1.4.1.6）**：
  若本侧因评分未达标未进入 `bd['prev_close_gate']`，探针自动取本侧已找出的最近边界 `_nb_val` 及其子族，独立调用 `check_balanced_boundary_prev_close` 执行真实校验：
  - 输出：`最近边界=759.96（spy_day_low）/ 昨收(SPY)=754.1`
  - 判定：`passed = False`（高开日下侧边界高于昨收，判定为 **`✗ 未过`**，真实体现缺口日保护拦截，而非数据缺失）。
- **前置：边界有效性（边界级 · §3.1.4.1.9）**：
  若未入围，探针对本侧最近边界独立调用 `check_balanced_boundary_integrity`：
  - 依据档位若为豁免档（如运行极值、Saty ±100%、fut/fdt），如实展示 `边界=spy_day_low ⇒ 本档位豁免`，判定为 **`✓ 通过`**；
  - 若为 Saty ±61.8% 受限档，根据极值突破幅度给出真判定；彻底消除假性「数据缺失」。
- **机制命中方向 vs 本点统一口径（§3.1.4.1）**：
  当机制未出方向（`mech_dir is None`）时，`side_match = False`：
  - 实际值：`机制方向=无(未触发) / 统一口径=BULLISH（做多）`
  - 判定：**`✗ 未过`**（明确表明因机制未触发做多方向而未匹配，不再是数据缺失）。
- **L0 方向掩码（L0-B⑤/C⑥/F⑨）**：
  当机制未出方向时，不存在需要被掩码拦截的开仓动作，判定为 **`✓ 通过`**：
  - 实际值：`命中方向=-- / 掩码=BEARISH（无开仓方向，未触及掩码拦截）`
  - 判定：**`✓ 通过`**。

---

## 验证结果

### 1. 实盘数据回归（以 2026-09-17 低点 #2 08:05 为例）
执行探针实时提取，四项判据输出完全符合预期：
- **P 边界到位度（45 分）**：`上行距=0.23 SPY 点；下行距=0.44 SPY 点 ⇒ 空/多 = 10.5/0.0` | `passed: True`
- **前置：昨收方向（边界级 · 下侧边界）**：`最近边界=759.96（spy_day_low）/ 昨收(SPY)=754.1` | `passed: False` (✗ 未过，缺口日保护)
- **前置：边界有效性（边界级 · 仅 Saty ±61.8%）**：`边界=spy_day_low ⇒ 本档位豁免` | `passed: True` (✓ 通过)
- **机制命中方向 vs 本点统一口径**：`机制方向=无(未触发) / 统一口径=BULLISH（做多）` | `passed: False` (✗ 未过)
- **L0 方向掩码（L0-B⑤/C⑥/F⑨）**：`命中方向=-- / 掩码=BEARISH（无开仓方向，未触及掩码拦截）` | `passed: True` (✓ 通过)

### 2. 自动化测试套件
- `/usr/local/bin/python3 PyTools/option_seller/test_balanced_day_prev_close_gate.py`：**24/24 OK**
- `/usr/local/bin/python3 PyTools/option_seller/test_balanced_day_boundary_integrity_gate.py`：**36/36 OK**
- `/usr/local/bin/python3 PyTools/option_seller/test_balanced_day_saty_armed.py`：**81/81 OK**
- `/usr/local/bin/python3 -m unittest PyTools/option_seller/test_intraday_probe.py -k "balanced_day"`：**4/4 OK**
