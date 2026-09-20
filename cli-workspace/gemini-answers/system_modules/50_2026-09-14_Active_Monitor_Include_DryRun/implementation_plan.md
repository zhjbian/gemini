# 卖家系统：活跃持仓监控纳入 DRY-RUN 单（跨进程持仓重同步）实施计划

- **日期**：2026-09-14
- **模块**：Option Seller 仪表盘「活跃持仓监控 (Active Spread Monitor)」+ 10 秒风控守护线程的持仓来源
- **归档目录**：`50_2026-09-14_Active_Monitor_Include_DryRun`
- **技术栈**：Python 3.11 / Flask API + Jinja2（`bbt_data_web`，127.0.0.1:5005）/ MySQL `bb_trade`（`order_flow_option_seller_trades`）/ 线程安全（dict 原子替换）/ headless Chrome DOM 与截图核对

---

## 1. 背景与问题（用户报障）

> 流水账本里 4 笔 `OPEN`（模式 = `DRY`）没平仓，但「活跃持仓监控」显示「当前无未平仓价差」，TOS 里也没有。

排查结论分两部分：

| 部分 | 结论 |
|---|---|
| **TOS 里没有** | **正常**：#1–#4 是 **DRY-RUN（试运行）** 单（Force Dry 触发命中的「平衡日边界」）⇒ 不发券商、无真实成交；#5/#6 是 LIVE（QuantPivot），已于 08:44 止损平仓（各 −$14）⇒ 此刻 TOS 无持仓也正确 |
| **监控区显示 0** | **真缺陷**：DB 里明明有 4 行 `status='OPEN'`（含 `is_dry_run=1`），但仪表盘一块都看不到 |
| **用户明确的期望** | 「LIVE 模式下 活跃持仓监控现在只显示 LIVE 单 —— 需要修正为**显示 LIVE 和 DRY-RUN 单**」 |

### 根因（跨进程内存不同步）

1. **开单方**：自动单由 `daily_jobs → comprehensive_signals_job.py → order_flow_sentinel.py` 的**一次性子进程**开出并落库（`order_flow_sentinel.py:731` 处 `OptionSellerManager.get_instance()`），开完即退出；
2. **管理方**：只在**仪表盘进程**存在 —— `bbt_data_app.py:139 seller_manager.start_monitor()` 是全仓**唯一**启动 10 秒监控线程的位置；
3. **同步缺口**：仪表盘只在**进程启动时**调一次 `_reload_active_trades()`（全仓唯一调用点在 `__init__`），此后**永不重读 DB**；
4. ⇒ 子进程开出的单（**LIVE 与 DRY-RUN 都一样**）在仪表盘的 `self.active_trades` 里根本不存在：
   - 「活跃持仓监控」看不到（显示「当前无未平仓价差」）；
   - **DRY-RUN 单无人管理**：它没有券商侧止盈/止损单，只能靠内存里的监控线程平仓 ⇒ 实测 `current_mark`/`last_modified` 长时间冻结在开仓时的值；
   - 「立即刷新持仓」按钮也救不了：`refresh_active_positions_now()` 只对**内存里已有**的持仓重算标记，**不读库**。

## 2. 实施目标

| 目标 | 交付 |
|---|---|
| 监控区**同时显示 LIVE 与 DRY-RUN** 在管持仓 | 跨进程**周期性 DB 重同步**（10s 节流）→ `active_positions` 含两类；卡片加 `LIVE` / `DRY-RUN` 徽标；区块标题加计数徽标 |
| DRY-RUN 单**确实被风控管理** | 重同步接在 10s 监控循环内 ⇒ 标记刷新与止盈/止损/时间止损口径对 DRY 与 LIVE 一致（LIVE 独有步骤本就有 `is_dry_run` 守卫） |
| 「立即刷新持仓」名副其实 | `refresh_active_positions_now()` 先 `_resync_active_trades(force=True)` 再评估 |
| 不引入新竞态 | `_reload_active_trades()` 由「`clear()` + 逐条填」改为**先建新表再原子替换**（状态接口会无锁遍历 `self.active_trades.values()`，旧写法可能抛 *dictionary changed size during iteration*），失败时保留旧表 |

## 3. 关键设计

### 3.1 重同步策略

- 新增类常量 `TRADE_RESYNC_INTERVAL_SEC = 10.0` 与 `_resync_active_trades(force=False)`
- **接在 10s 监控循环内**（`_monitor_loop` 第 0.5 步，位于时段截断之后、条件单评估之前）：
  - 与监控同频 ⇒ 重同步到即被管理，避免「看得到但没人管」
  - 节流 10s ⇒ 每轮 1 次轻量 `select ... where status in ('OPEN','CLOSING')`
- 管理范围**不区分 LIVE / DRY**（口径与 DB 一致：`status ∈ OPEN/CLOSING`）

### 3.2 线程安全

| 位置 | 处理 |
|---|---|
| `_reload_active_trades` | `with self._lock` 内构建 `new_map`，成功后 `self.active_trades = new_map`（原子引用替换）；异常时**不清空**旧表 |
| `_evaluate_active_positions` | 已有 `with self._lock: trades_to_check = list(self.active_trades.values())` 快照 ⇒ 兼容 |
| `get_status_summary` | 无锁遍历 `self.active_trades.values()` ⇒ 原子替换后不再有「边遍历边 clear/fill」竞态 |

### 3.3 页面

- 区块标题：`活跃持仓监控 (Active Spread Monitor)` + `LIVE n` / `DRY-RUN n` 两个计数徽标（按 `status.active_positions` 现算）
- 持仓卡片：类型徽标之后加 `💵 LIVE`（浅绿）或 `🧪 DRY-RUN`（浅灰）徽标，含 title 说明（试运行不发券商、按实时报价模拟标记与止盈止损）
- 空态文案补充「LIVE 与 DRY-RUN 在管持仓一并显示」

## 4. 验证方案

1. **重启后即时可见**：manager 改动触发 Flask 重载 → `__init__` 载入 → `status.active_positions` 应含 DRY 单（`LIVE 0 / DRY-RUN n`）
2. **周期性重同步生效**：监控循环日志出现 `reloaded N active trades (LIVE x / DRY-RUN y)`，间隔≈10s
3. **DRY 单真的被管理**：观察其 `current_mark` / `last_modified` 随行情推进变化（不再冻结在开仓值）
4. **「立即刷新持仓」**：`?force_refresh=true` 后 DRY 单标记写入 DB
5. **页面渲染**：headless Chrome 截图核对计数徽标 + 卡片 `DRY-RUN` 徽标
6. **回归**：`py_compile` + 模板 JS `node --check` + `option_seller` 测试套件；除监控自身的标记/平仓写入外无其它 DB 写

## 5. 风险与回退

- **风险**：重同步会以 DB 为准**重建**内存表 ⇒ 丢掉仅存在于内存的瞬时字段（如 `_close_poll_count`、`_tp_defer_attempts`）。这些字段本就是**重试计数**、可自愈；关键状态（保本位移、止盈模式、券商订单 id）均持久化在 `entry_evidence` 且随重建恢复。当前生产 `status` 只有 `OPEN`（无 `CLOSING`）在管，风险窗口极小。
- **风险**：10s 一次 DB 查询开销可忽略（单表索引查询、毫秒级）。
- **回退**：`/tmp/bbt_drymon_backup_*/`（术前副本）；删除 `_monitor_loop` 内 `self._resync_active_trades()` 一行即回到旧行为（监控区恢复为「只显示本进程已知持仓」）。
