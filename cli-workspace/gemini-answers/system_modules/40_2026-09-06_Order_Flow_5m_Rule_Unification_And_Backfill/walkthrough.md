# 订单流盘中分析去除 30 分钟 AI 调用全面统一 5 分钟规则引擎与历史全量回填交付报告

## 1. 交付目标概述
针对交易系统中 Order Flow 盘中存在 30 分钟大模型 AI 分析与 5 分钟两步法规则分析双轨混杂的问题，全面落实用户指令：
1. **彻底去除盘中 30 分钟周期的 AI 分析**，只保留盘后收盘美西时间 13:15 的 Day Type AI 分析。
2. **盘中所有时间节点（包括 07:00, 07:30 等整点与半点）统一执行 5 分钟周期基于规则的分析 (`Rule-Based-5m`)**。
3. **全量回填 2026-09-03 与 2026-09-04 历史订单流分析结果**，彻底替换原有盘中 Gemini 记录为标准的 `Rule-Based-5m` 信号，且 100% 完好保留 13:15 的 Day Type 记录。

## 2. 核心代码变更清单

### 2.1 `PyTools/order_flow_analysis/order_flow_sentinel.py`
- **动态前序基准检索 (`find_baseline_from_db`)**:
  - 原代码按 30 分钟倒推跳步寻找基准（导致早盘 06:35-06:55 无法找到基准而产生断层），修改为动态检索目标时间戳之前、且已计算 `rth_delta` 的最新一条有效记录作为前序 Baseline。
- **取消 30 分钟边界跳过限制**:
  - 移除了 `if target_mins % 30 == 0 and not args.include_30m: return` 的跳过逻辑，使哨兵系统支持全天任意 5 分钟节点。
- **变量定义完备性修复**:
  - 明确指定 `combined_intervals = formatted_parsed_bins`，彻底排除多步判定与区间统计中的 NameError 隐患。
- **数据库持久化保护精细化**:
  - 原代码只要发现历史记录包含 `gemini` 便放弃更新规则；修改为仅当记录属于收盘日类型 (`sig.day_type and sig.day_type.strip()`) 时保护，其余所有盘中记录（包括整点半点的旧 Gemini 记录）均允许更新为标准的 `Rule-Based-5m`。
- **解除 HIGH 信号盘中调用 AI**:
  - 5m 规则检测出 HIGH 强信号时，只输出日志标记，不再触发 `run_ai_tape_analyst`，杜绝盘中 AI 覆盖规则信号。

### 2.2 `PyTools/order_flow_analysis/comprehensive_signals_job.py`
- 在 `run_sub_analyses(date_str, time_str)` 中：
  - 废除原步骤 2 调用的 `ai_tape_analyst.py -d {date_str} -t {time_str} --realtime --no-email`。
  - 全面替换为调度 `order_flow_sentinel.py -d {date_str} -t {time_str}`，使 30 分钟综合决策作业的底层订单流输入统一来自 `Rule-Based-5m` 规则引擎。

### 2.3 `PyTools/daily_jobs.py`
- 更新 `sentinel_times` 调度队列：
  - 将原条件 `390 <= mins < 780 and mins % 30 != 0` 修改为 `390 < mins <= 780`。
  - 从 `06:35` 至 `13:00` 每 5 分钟无缝调度一次 `run_order_flow_sentinel_job`。
  - 保留 `13:15` 的 `schedule_weekdays("13:15", ...)` 作为全天唯一的大模型 Day Type 分析。

### 2.4 `PyTools/order_flow_analysis/ai_tape_analyst.py`
- 强化入口保护：
  - `call_ai` 严格限制为 `args.force_ai or (args.day_type and not args.rule_based)`。即使被外部调用，只要未携带 `--day-type` 或 `--force-ai`，均默认走规则模式，绝不消耗大模型 API。

## 3. 验收验证与数据比对

### 3.1 历史数据回填验证 (2026-09-03 & 2026-09-04)
- 遍历两天的全天美西时间 `06:35` 至 `13:00` 共 78 个时间戳进行全量顺序回填。
- 数据库校验确认：
  1. 盘中整点与半点（07:00, 07:30, 08:00, 08:30, 09:00, 09:30, 10:00, 10:30, 11:00, 11:30, 12:00, 12:30, 13:00）全部更新为 `ai_model = 'Rule-Based-5m'`。
  2. 信号方向、强度得分（0~10）、Setup 形态与底层 DOM/CVD 量化指标均完整入库。
  3. 收盘 `13:15:00` 记录（2026-09-03 Active Buying / 2026-09-04 Active Selling）完好保留大模型 Day Type 分析，未受任何干扰。
