# 验收报告：机制 ③「平衡日边界」取消五维评分开仓门槛限制

## 1. 交付概述
依据用户指令，正式取消机制 ③「平衡日边界」（`AUTO_BALANCED_DAY_BOUNDARY`）五维评分对开仓的门槛限制（原 70 分硬拦截取消），彻底解除对高确定性边界反转机会的过度过滤：
1. **开仓门槛与五维评分彻底解绑**：原规则中闸门 5「五维总分 score >= 70」正式取消；开仓准入完全由边界到达判定（P 到位）、方向准入、昨收方向、边界有效性、趋势日门控及 L0 全局闸门把关。
2. **五维评分全量留痕**：五维评分体系（P 45 / M 20 / B 25 / E 10）继续运行并计算分值，写入 日志、MySQL DB 订单与探针 evidence 供审计观测，但不做开仓否决。
3. **手册与系统全链路一致**：交易系统规则手册（HTML 与 MD）、生产通道引擎、探针判定及生产配置文件完全同步，无逻辑漂移。

---

## 2. 改动清单

| 模块 / 文件 | 改动性质 | 核心功能说明 |
| :--- | :---: | :--- |
| [`PyTools/option_seller/balanced_day_boundary.py`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/balanced_day_boundary.py) | **修改** | 常量 `V2_SCORE_THRESHOLD` 设为 `0.0`（停用）；移除 `groups = 0 if final < score_threshold`，确定方向后直接输出 1 组 |
| [`PyTools/option_seller/option_seller_manager.py`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/option_seller_manager.py) | **修改** | 缺省配置 `score_threshold` 置 `0`；移除执行流程中 `float(score) < score_threshold` 的退出判断 |
| [`PyTools/option_seller/intraday_probe.py`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/intraday_probe.py) | **修改** | 探针中「五维总分 >= 出分门槛」调整为「已取消（仅观测留痕）」；`QUALIFIED` 判定中移除 `float(score) >= threshold` 限制 |
| [`Config/option_seller_balanced_day.json`](file:///Users/zhijiebian/Documents/MyDoc/Finance/Current/Config/option_seller_balanced_day.json) | **修改** | 生产配置文件中 `"score_threshold"` 由 `70` 更新为 `0` |
| [`gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html`](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html) | **修改** | 规则手册 §3.1.4.1.3 更新出分门槛条款；§3.1.4.1.4 闸门 5 标注为已取消，更新关系说明 |
| [`gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.md`](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.md) | **修改** | 同步更新规则手册 Markdown 版本对应条款 |

---

## 3. 验证结果

### 3.1 单元测试验证
运行平衡日边界全量单元测试（`test_balanced_day_*.py`）：
```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m unittest discover -s PyTools/option_seller -p "*balanced*.py"
```
**测试输出**：
```text
Ran 238 tests in 3.027s
OK
```
全量 238 项用例 100% 通过，未破坏任何既有边界到达、方向反转与分档逻辑。

### 3.2 低分样本放行测试
构造 P 到位（45 分），无任何 M/B/E 额外得分（总分 45.0 < 70.0）的用例：
```python
score, path, groups, bd, veto = score_balanced_day_boundary_v2(
    row, day_high=5600.0, day_low=5580.0, spy_price=560.0, spy_day_high=560.0, spy_day_low=558.0,
    prev_close=5585.0, spy_prev_close=558.5, boundary_tol=0.2
)
```
**断言结果**：
- `Score`: `45.0`
- `Groups`: `1`（不再因分值小于 70 归零）
- `Direction`: `BEARISH`
- `Veto`: `None`
验证通过，成功放行 1 组开仓。
