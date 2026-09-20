# 实施计划：机制 ③「平衡日边界」取消五维评分开仓门槛限制

## 1. 任务背景
在 Option Seller 自动期权卖方系统中，机制 ③「平衡日边界」（`AUTO_BALANCED_DAY_BOUNDARY`）主要捕获在震荡平衡日触及极值或关键边界（SPY 日内高/低、Saty ATR 四档、Smashelito `fut`/`fdt`）时的均值回归机会。
原规则设定了五维评分器（P 边界到位度 45 / M 动能衰竭 20 / B 吸收反制 25 / E 时间幅度 10），并设置通道级硬闸门 5：**五维总分 `score >= 70`（`score_threshold`）**。
然而，在真实盘面与回放分析中，当行情精准到达刚性边界（P 到位）且满足缺口昨收方向、边界有效性、趋势日门控和 L0 全局闸门时，强行要求叠加大额 M/B/E 佐证（总分 70）会导致大量高确定性胜率机会被误拦截。
依用户决策指令，本模块正式**取消五维评分对开仓的门槛限制**，使边界触及与方向准入作为开仓的核心逻辑，五维评分全量留痕于 evidence 与探针中供复盘审计。

---

## 2. 实施范围与技术方案

### 2.1 交易系统规则手册维护
- **`gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html`**：
  - 更新 **§3.1.4.1.3 五维评分细则**：标记 2026-09-17 规则变更，取消原 `score >= 70` 开仓限制，五维评分仅作信号质量观测与留痕。
  - 更新 **§3.1.4.1.4 通道级硬闸门**：将闸门 5「出分门槛」状态更新为已取消（直接放行）。
- **`gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.md`**：
  - 同步更新对应 Markdown 描述。

### 2.2 交易引擎与生产逻辑解绑
- **`PyTools/option_seller/balanced_day_boundary.py`**：
  - 将常量 `V2_SCORE_THRESHOLD` 调整为 `0.0`（仅作兼容，标记已停用）。
  - 在 `score_balanced_day_boundary_v2` 中，移除因分数低于门槛导致 `groups=0` 的拦截，确定方向后直接输出 `groups = max(1, min(int(groups_cap or 1), 1))`。
- **`PyTools/option_seller/option_seller_manager.py`**：
  - 更新 `BALANCED_DAY_DEFAULTS["score_threshold"]` 缺省值为 `0`。
  - 移除通道执行中 `if float(score) < float(cfg.get("score_threshold", 70)): return None` 的退出判断。
- **`PyTools/option_seller/intraday_probe.py`**：
  - 探针逐项判据中「五维总分 >= 出分门槛」调整为「五维总分（开仓门槛已取消）」，判定列置为 True（放行）。
  - 判定结论中 `QUALIFIED` / `REJECTED` 不再要求 `float(score) >= threshold`。
- **配置文件 `Config/option_seller_balanced_day.json`**：
  - 同步将生产配置文件中的 `"score_threshold"` 更新为 `0`。

---

## 3. 验证计划
1. 单元测试验证：运行平衡日边界全量单元测试（`test_balanced_day_*.py`），确保 238 个测试无损通过。
2. 边界断言验证：验证构造的 P 到位但 M/B/E 不足（总分 45 < 70）样本能够成功放行输出 1 组开仓。
3. 手册与归档检查：核对手册规范、技术栈标记与模块索引更新。
