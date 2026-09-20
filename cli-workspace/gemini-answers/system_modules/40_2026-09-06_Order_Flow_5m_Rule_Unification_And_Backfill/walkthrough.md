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

---

## 2026-09-14 · 故障修复：5 分钟综合信号任务全线失败（SyntaxError，0.05s 退出）

### 现象

用户报「今天 5 分钟周期的 orderflow 和 SPX gamma 分析一个报告没生成，应该程序错误了」，并附调度日志：

```
2026-09-14 06:47:11 run_comprehensive_signals_0645 Starting
Daily_job_failure: run_comprehensive_signals_0645
An error occurred: Command '... comprehensive_signals_job.py -t 06:45' returned non-zero exit status 1.
STDERR:   File ".../comprehensive_signals_job.py", line 936
    return 0
    ^^^^^^^^
SyntaxError: 'return' outside function
                           06:47:11 run_comprehensive_signals_0645 Ended, took 0.05 seconds
```

### 根因

`PyTools/order_flow_analysis/comprehensive_signals_job.py` 的 `--email-only` 分支（item 5「父进程分离调用，只发邮件」）写在 **模块级代码块** 里：

```python
if __name__ == "__main__":
    ...
    if args.email_only:      # ★ item 5：分离子进程模式 —— 只发邮件
        build_and_send_comprehensive_email(args.date, args.time)
        return 0            # ← 模块级 `return` ⇒ SyntaxError
```

`if __name__ == "__main__":` 不是函数体，`return` 非法 ⇒ **整个脚本无法编译**：

- 失败发生在**编译期**，所以两个子分析（`spx_gamma_analyst.py`、`order_flow_sentinel.py`）与邮件**一条都没跑**；
- 表现即「0.05 秒就 Ended」；
- 今日受影响槽位：`06:35 / 06:40 / 06:45 / 06:50`（调度 06:35–13:00 每 5 分钟），日志中今日 `run_comprehensive_signals` **成功 0 次、失败 5 条**。

### 修复

```python
    if args.email_only:      # ★ item 5：分离子进程模式 —— 只发邮件
        build_and_send_comprehensive_email(args.date, args.time)
        # ★ 2026-09-14 修复：`if __name__ == "__main__":` 是**模块级**代码块，此处 `return 0`
        #   属语法错误（SyntaxError: 'return' outside function）⇒ 整个脚本无法编译，
        #   5 分钟综合信号任务（comprehensive_signals_job.py -t HH:MM）每次启动即失败。
        #   模块级退出必须用 raise SystemExit / sys.exit。
        raise SystemExit(0)
```

### 验收

| 项 | 结果 |
| :--- | :--- |
| `py_compile` | 通过 |
| **全仓语法扫描**（PyTools / bbt_data_web / bbt_signal_web / scripts 共 **478** 个 .py） | **0 失败**（确认无其它同类破坏） |
| `--help` | 正常（argparse 可用） |
| 修复后首个**调度运行**（06:55） | `06:55:38 SUCCESS` → `spx_gamma_analyst → order_flow_sentinel → 邮件已交分离子进程发送 → BBT Comprehensive Signals Job Completed` |

### 数据修复（补齐今日缺失槽位）

使用既有工具 `PyTools/order_flow_analysis/backfill_comprehensive_slots.py`（**只跑子分析落库、不发邮件**，幂等）：

```
--dry-run: 应生成 78 槽 | 已有 0 槽 | 缺失 4 槽: ['06:35','06:40','06:45','06:50']
--apply  : [1/2] 06:45 ✓ gamma=ok sentinel=ok 用时 28.0s
           [2/2] 06:50 ✓ gamma=ok sentinel=ok 用时 31.4s
           （前两槽 06:35/06:40 在首次 --apply 中已完成）
复核      : 应生成 78 槽 | 已有 4 槽 | **缺失 0 槽**
```

如需**补发邮件**，可逐槽执行（会真的发信，未擅自执行）：
`python3 PyTools/order_flow_analysis/comprehensive_signals_job.py -d 2026-09-14 -t 06:35 --email-only`（同理 06:40 / 06:45 / 06:50）。

### 另发现（待用户确认，本次未处置）

机器上有**两个 `daily_jobs.py` 调度进程**同时运行：

```
PID 46875  起于 Thu Sep 10 23:53:59
PID 70885  起于 Sat Sep 12 08:17:09
```

两者都会按同一张 `schedule_weekdays` 表到点触发 ⇒ 存在**同一槽位被重复调度**（重复跑分析、重复发邮件）的可能。建议确认是否只保留一个；本次未终止任何进程。

### 回滚点

- `PyTools/order_flow_analysis/comprehensive_signals_job.py` 术前：`/tmp/l0c_bak/comprehensive_signals_job.py.pre_retfix`
- 模块索引术前：`/tmp/mods_pre_jobfix.html.bak` · 本文件术前：`/tmp/wt40_md_pre.bak`

### 附：调度器去重（2026-09-14 用户指令「请 只保留一个」）

**处置**：保留 **launchd 托管的 `com.bbt.daily-jobs`**（PID **46875**），终止**终端手启的重复实例**（PID **70885**，`ttys002`，PPID 70882，起于 09-12 08:17）。

**判据（为何保留 46875）**：

| 实例 | 归属 | 证据 |
| :--- | :--- | :--- |
| **46875（保留）** | **launchd 服务** `com.bbt.daily-jobs` | `launchctl list` 显示 `com.bbt.daily-jobs → PID 46875`；plist `~/Library/LaunchAgents/com.bbt.daily-jobs.plist` 且 **`RunAtLoad=1` / `KeepAlive=1`**（开机自启 + 掉线自动重启）、stdout/err → `bbt_daily_jobs.log`；**PPID=1**（daemon 化） |
| 70885（终止） | 手工从终端启动 | `TTY=ttys002`、父进程链 `70885 → 70882 → 3269(-zsh, Sep 7 17:25)`；无 launchd 托管，终端关闭即消失 |

**重复运行的证据**：终止前同一槽位被**两个调度器各触发一次** —— `comprehensive_signals_job.py -t 06:35` 在 `bbt_data_web.log` 中出现 **2 次**（06:38:08 / 06:49:41），而两个进程都把 stdout 指向同一份 `bbt_data_web.log`（`lsof` 可见两者 FD 3w 均为该文件）。终止后 `pgrep -fl daily_jobs.py` **仅剩 1 个实例**，且该进程**持续在派发任务**（`pgrep -P 46875` 可见 bash/子 Python 作业）。

**顺带核对（无需处置）**：`ws_client_watcher.py` 看似 2 个进程，实为 **1 个逻辑实例** —— PID 57456 是 `sh -c … &` 包装壳、PID 57457 是其子 Python 进程。

**遗留观察（非本次处置范围，但会直接影响「5 分钟报告是否按时生成」）**：
调度器主循环为

```python
while True:
    schedule.run_pending()
    for _ in range(60):        # ~60s 一次派发窗口
        time.sleep(1)
        ...
```

且**作业串行**执行 ⇒ **单个长作业会阻塞后续所有槽位**。今日实测：`option_chain_auto_after_open_tos` 于 `07:05:00 TIMEOUT (420s)`、`option_chain_auto.py` 于 `06:57:59 TIMEOUT (420s)`，把 `07:00` / `07:05` 的 5 分钟综合信号槽位**压在队列里延迟执行**（`schedule` 语义：超时槽位在队列空闲后**仍会补跑一次**，之后下一个周期是下一个交易日）。此前的重复调度器在某种程度上「掩盖」了该延迟（代价是重复执行 / 重复邮件）。

**建议（待用户定）**：① 收敛那些 420s 超时的期权链作业（缩短超时或移出 5 分钟调度器）；② 需要立即补齐时可用 `backfill_comprehensive_slots.py --apply`（只落库不发邮件）；③ 如需补发邮件：`comprehensive_signals_job.py -d 2026-09-14 -t HH:MM --email-only`。
