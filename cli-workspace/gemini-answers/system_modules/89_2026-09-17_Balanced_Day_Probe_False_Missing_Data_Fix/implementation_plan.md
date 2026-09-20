# 平衡日边界探针「假性数据缺失」判定修正计划

## 问题背景与现状分析

在 `http://127.0.0.1:5005/bbt_option_seller` 的「当日高低点自动触发机制检测」中，当某个时点（如低点 #2 08:05）的平衡日边界机制因边界距离偏大（如 0.44 SPY 点 > 0.30 容差上限）导致评分不足未入围候选池时，判据表格中出现了 4 处显示为 **`— 数据缺失`** 的假象：

1. **前置：昨收方向（边界级）**：显示 `本侧未出方向候选 ⇒ 未评估`，判定为 `— 数据缺失`。
2. **前置：边界有效性（边界级 · 仅 Saty ±61.8%）**：显示 `本侧未出方向候选 ⇒ 未评估`，判定为 `— 数据缺失`。
3. **机制命中方向 vs 本点统一口径**：显示 `机制方向=None / 统一口径=BULLISH（做多）`，判定为 `— 数据缺失`。
4. **L0 方向掩码（L0-B⑤/C⑥/F⑨）**：显示 `命中方向=-- / 掩码=BEARISH`，判定为 `— 数据缺失`。

**核心矛盾**：
底层市场数据（ES/SPY 现价、ES/SPY 昨收、ES/SPY 当日高低点、各档位边界、订单流、EMA）**全部完备，无一缺失**。
之所以呈现「数据缺失」，是因为探针代码中机械地将所有 `passed is None` 映射为 `missing = True`（渲染为 `— 数据缺失`），而原本应有的业务判定（未通过 / 通过 / 真实前置比对）因机制未出开仓方向而被跳过，导致了严重的语义误导。

---

## 拟修正方案

### 1. 机制命中方向 vs 本点统一口径
- **问题**：机制未出方向（`mech_dir is None`）时，`side_match = None` 导致判定为数据缺失。
- **修正**：统一口径是做多（BULLISH），机制未产出做多方向，属于**方向不一致/未命中**，判定结果应为 **`passed = False`**（页面显示 **`✗ 未通过`**）。
- **实际值文案**：`机制方向=无(未触发) / 统一口径=BULLISH（做多）`。

### 2. L0 方向掩码（L0-B⑤/C⑥/F⑨）
- **问题**：机制未出方向（`mech_dir is None`）时，代码返回 `passed = None` 导致显示为数据缺失。
- **修正**：既然机制未产生开仓信号，便不存在被掩码拦截的问题（未触发开仓，掩码不构成阻断）。判定结果应为 **`passed = True`**（页面显示 **`✓ 通过`**）。
- **实际值文案**：`命中方向=-- / 掩码=BEARISH（无开仓方向，未触及掩码拦截）`。

### 3. 前置：昨收方向（边界级）
- **问题**：评分器生产逻辑为了节省算力，仅在单侧评分达到入围门槛（>= 45 分）时才对候选执行昨收比对。多头侧仅 11.25 分未入围，导致 `bd['prev_close_gate']` 中无多头记录，探针降级显示未评估且 `passed=None`。
- **修正**：
  在评分器或探针中，当前侧（做多即下侧）的最近边界 `_bl` 及其档位名 `_bl_nm`、子族 `_bl_sf` 已经通过 `_nearest_bounds` 明确计算得出（本例中下侧最近边界就在 0.44 点处）。
  探针对统一口径指定侧的最近边界，**直接执行真实的 `check_balanced_boundary_prev_close` 校验**：
  - 如果下侧边界 < 昨收，如实展示 `最近边界=... / 昨收=...（下侧边界 < 昨收）` 并判定为 **`✓ 通过`**。
  - 如果下侧边界 >= 昨收，如实展示并判定为 **`✗ 未通过`**。
  - 只有在昨收价在底层数据库中真正为 `None` 时，才标为 `— 数据缺失`。

### 4. 前置：边界有效性（边界级 · 仅 Saty ±61.8%）
- **问题**：同上，因多头未入围候选池，未执行该侧边界破位校验，探针降级显示未评估且 `passed=None`。
- **修正**：
  探针对指定侧已定位的最近边界，**直接执行真实的 `check_balanced_boundary_integrity` 校验**：
  - 若该边界属于豁免档位（如 Saty ±100%、fut/fdt、运行极值），如实展示 `边界=... ⇒ 本档位豁免`，判定为 **`✓ 通过`**。
  - 若该边界属于 Saty ±61.8% 受限档位，取当日运行极值（`day_low`/`day_high`）与边界计算跌穿幅度，如实判定 **`✓ 通过`**（未有效跌穿）或 **`✗ 未通过`**（已被有效击穿）。
  - 只有当必要极值在数据库中真正为 `None` 时，才标为 `— 数据缺失`。

---

## 影响范围与修改文件

#### [MODIFY] [intraday_probe.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/intraday_probe.py)
- 在 `_mech_balanced_day` 中：
  1. 当 `bd.get('prev_close_gate')` 中没有 `side` 侧的计算结果时，尝试从 `bd.get('nearest_bounds')` 或调用 `_nearest_bounds` 取得本侧最近边界，并调用 `check_balanced_boundary_prev_close` 与 `check_balanced_boundary_integrity` 给出本侧真实的边界前置校验结果，彻底替代原先硬编码的 `本侧未出方向候选 ⇒ 未评估` (None)。
  2. `side_match`：当 `mech_dir is None` 时，由原先的 `None` 改为 `False`（未命中统一方向），实际值明确标出 `无(未触发)`。
  3. `L0 方向掩码`：当 `mech_dir is None` 时，由原先的 `None` 改为 `True`（未产生开仓信号，未触及掩码拦截）。

#### [MODIFY] [balanced_day_boundary.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/balanced_day_boundary.py)
- 在 `score_balanced_day_boundary_v2` 中：
  将 `_nearest_bounds` 算出的 `_bu`（上侧边界信息）与 `_bl`（下侧边界信息）一并沉淀留痕在 `bd["nearest_bounds"]` 中，便于探针与上层复盘模块随时引用最近边界信息，避免重复计算。

#### [MODIFY] [test_intraday_probe.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/test_intraday_probe.py)
- 增加与更新针对机制 ③ 未出分时各判据真实输出的单元测试，确保无假性「数据缺失」。

---

## 验证计划

### 自动化测试
- 运行 `/usr/local/bin/python3 PyTools/option_seller/test_intraday_probe.py` 验证探针所有判据测试。
- 运行 `/usr/local/bin/python3 PyTools/option_seller/test_balanced_day_prev_close_gate.py` 验证前置闸门回归。
- 编写专项针对低分未触发场景的测试用例，验证上述 4 项不再输出 `passed=None`。

### 用户手动验证
- 用户刷新 `http://127.0.0.1:5005/bbt_option_seller` 页面，在「当日高低点自动触发机制检测」展开「低点 #2 08:05」，验证 4 个判据已如实展示为 `✓ 通过` / `✗ 未通过`，再无假性「数据缺失」。
