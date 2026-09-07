# 订单流盘中分析去除 30 分钟 AI 调用全面统一 5 分钟规则引擎与历史全量回填实施计划

## 1. 业务背景与问题定义
交易系统中 Order Flow 分析在盘中原本存在双轨运行机制：
1. 每 30 分钟（整点与半点，如 07:00, 07:30 等）由 `comprehensive_signals_job.py` 调度 `ai_tape_analyst.py` 调用 Gemini 大模型生成 AI 研判记录，写入 `order_flow_signals` 表（`ai_model='gemini-...'`）。
2. 每 5 分钟（排除整点与半点）由 `daily_jobs.py` 调度 `order_flow_sentinel.py` 基于规则的两步判定法（Setup 准入 + 9项底层指标累加）生成规则研判记录（`ai_model='Rule-Based-5m'`）。
3. 当 5 分钟哨兵触发 HIGH 信号时，还会主动拉起 `ai_tape_analyst.py` 调用 Gemini 覆盖规则信号。

**核心问题与重构目标**：
- 盘中 30 分钟周期的 AI 分析存在响应延迟（经常耗时数十秒甚至超时）、消耗 Token、且方向容易受大模型发散影响，与底层两步判定法的量化风控（如空间红线硬性一票否决、加分项累加）存在冲突。
- 用户明确指示：
  1. **去除 30 分钟周期的 AI 分析，只保留盘后最后一次（13:15）的 Day Type AI 分析**。
  2. **盘中所有时间节点统一执行 5 分钟周期基于规则的分析 (`Rule-Based-5m`)**。
  3. **全量回填 2026-09-03 与 2026-09-04 两天的 Order Flow 分析结果**。

## 2. 详细技术方案

### 2.1 修改核心执行模块
1. **`PyTools/order_flow_analysis/order_flow_sentinel.py`**：
   - **动态前序基准检索 (`find_baseline_from_db`)**：重构原本按 30 分钟倒推的硬编码逻辑，改为动态获取该日期在目标时间戳之前的最新一条有效信号记录作为 Baseline，实现 5 分钟逐级平滑累加。
   - **全面放开 30 分钟整点/半点边界**：废除整点跳过逻辑，使 07:00, 07:30 等时间节点均无缝执行 5 分钟规则研判。
   - **定义 `combined_intervals`**：修复微观时间区间变量未定义隐患，统一挂接为 `formatted_parsed_bins`。
   - **严格保护 13:15 Day Type 记录**：持久化时仅对收盘 Day Type (`sig.day_type`) 提供保护，盘中整点/半点的历史 Gemini 记录均允许被最新的 `Rule-Based-5m` 规则覆盖更新。
   - **去除 HIGH 信号调用 AI**：当 5m 规则检出 HIGH 信号时，记录日志但不调用 `ai_tape_analyst`，杜绝盘中 AI 覆盖。

2. **`PyTools/order_flow_analysis/comprehensive_signals_job.py`**：
   - 在 `run_sub_analyses` 的 Order Flow 分析步骤中，将原本调用的 `ai_tape_analyst.py` 替换为 `order_flow_sentinel.py -d {date_str} -t {time_str}`，确保 30 分钟综合分析作业统一生成 `Rule-Based-5m` 规则记录。

3. **`PyTools/daily_jobs.py`**：
   - 调整 `sentinel_times` 调度队列：从 `06:35` 到 `13:00` 每 5 分钟无遗漏全量调度 `run_order_flow_sentinel_job`（包含 07:00, 07:30 等整点半点）。
   - 保留美西时间 `13:15` 的 `schedule_weekdays("13:15", ...)`，这是全天唯一保留的 `--day-type` 大模型 AI 分析。

4. **`PyTools/order_flow_analysis/ai_tape_analyst.py`**：
   - 入口参数 `call_ai` 严格限制为 `args.force_ai or (args.day_type and not args.rule_based)`，非 Day Type 模式下禁止调用大模型 API。

### 2.2 历史数据全量回填
- 针对 `2026-09-03` 和 `2026-09-04`，遍历全天美西时间 `06:35` 至 `13:00` 共计 78 个 5 分钟节点，顺序执行 `order_flow_sentinel`。
- 保证 13:15 Day Type 记录完好保留。
