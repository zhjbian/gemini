# 卖家系统：活跃持仓监控纳入 DRY-RUN 单（跨进程持仓重同步）验收报告

- **日期**：2026-09-14
- **模块**：Option Seller 仪表盘「活跃持仓监控 (Active Spread Monitor)」+ 10 秒风控守护线程的持仓来源
- **归档目录**：`50_2026-09-14_Active_Monitor_Include_DryRun`
- **技术栈**：Python 3.11 / Flask API + Jinja2（bbt_data_web，127.0.0.1:5005）/ MySQL `bb_trade` / 线程安全（dict 原子替换）/ headless Chrome 截图与 DOM 核对

---

## 1. 结论先行

| 用户观察 | 结论 |
|---|---|
| 流水账本 4 笔 `OPEN`（模式 = `DRY`）未平仓 | 事实：DB 中 `status='OPEN'`，`is_dry_run=1` |
| **TOS 里没有** | ✅ **正常**：DRY-RUN 不发券商、无真实成交（Force Dry 触发命中的「平衡日边界」）；另外两笔 LIVE（QuantPivot）已于 08:44 止损平仓（各 −$14），故 TOS 此刻本就没有持仓 |
| **监控区显示「当前无未平仓价差」** | ❌ **缺陷（已修）**：仪表盘只在**进程启动时**读一次 DB，自动单由**一次性子进程**开出 ⇒ 内存里根本没有这些单（**LIVE 与 DRY-RUN 一视同仁**） |
| 用户要求 | 监控区**同时显示 LIVE 与 DRY-RUN** ⇒ 已交付：跨进程 10s 重同步 + `LIVE n` / `DRY-RUN n` 计数徽标 + 卡片 `LIVE` / `DRY-RUN` 徽标 |

## 2. 根因（完整链路，均有证据）

1. **开单方 = 短命子进程**：`daily_jobs → comprehensive_signals_job.py → order_flow_sentinel.py`，后者在 `:731` 处 `OptionSellerManager.get_instance()` 开单落库后**立即退出**。
2. **管理方 = 仪表盘进程**：全仓**唯一**启动 10 秒监控线程的位置是 `bbt_data_app.py:139 seller_manager.start_monitor()`。
3. **同步缺口**：`_reload_active_trades()` 全仓**唯一调用点**是 manager `__init__` ⇒ 进程启动后**永不重读 DB**。
4. **「立即刷新持仓」不解决**：`refresh_active_positions_now()` 只对**内存里已有**的持仓重算标记，**不读库**。
5. ⇒ 后果：监控区看不到子进程开的单；**DRY-RUN 单更严重** —— 它没有券商侧止盈/止损单，只有内存里的监控线程能平仓，所以**只要进程不重启就永远无人管理**。

### 2.1 关键反证（意外却有力的证据）

修复过程中的日志显示：DRY 单此前**仅在 Flask 进程重启后**才被管理 ——

```
08:52:44  OptionSellerManager background monitor thread started.        ← Flask 重启（编辑触发 reloader）
08:52:44  OptionSellerManager reloaded 4 active trades.                  ← 此时才把 4 笔 DRY 单读进内存
08:54:37  OptionSellerManager background monitor thread started.
08:54:37  OptionSellerManager reloaded 4 active trades (LIVE 0 / DRY-RUN 4).
08:54:38  Trade #235 CLOSED (CLOSED_STOP_LOSS) @ 0.34 (Credit=0.15) Realized PnL=$-19.0   ← 重启后的监控线程才止损
08:54:39  Trade #234 CLOSED (CLOSED_STOP_LOSS) @ 0.34 (Credit=0.15) Realized PnL=$-19.0
```

即：08:35 开出的 DRY 单，直到 **08:54 的进程重启**才被风控看到并止损（mark 0.34 ≈ 2.27× 权利金）；**没有重启就不会被管理**。这正是本次修复要消除的依赖。

## 3. 修复内容

| 层 | 文件 | 改动 |
|---|---|---|
| 同步 | `PyTools/option_seller/option_seller_manager.py` | 新增 `TRADE_RESYNC_INTERVAL_SEC = 10.0` 与 `_resync_active_trades(force=False)`（节流重载） |
| 接线 | 同上 | `_monitor_loop` 第 0.5 步接入重同步（时段截断后、条件单评估前）：**与 10s 风控同频** ⇒ 读到即被管理 |
| 按钮 | 同上 | `refresh_active_positions_now()` 先 `_resync_active_trades(force=True)` ⇒ 「立即刷新持仓」真正从 DB 刷新 |
| 线程安全 | 同上 | `_reload_active_trades()` 由 `clear()` + 逐条填 → **先建新表再原子替换**，失败保留旧表；日志补 `LIVE x / DRY-RUN y` 计数 |
| 页面 | `bbt_data_web/templates/bbt_option_seller.html` | 区块标题加 `LIVE n` / `DRY-RUN n` 计数徽标；持仓卡片加 `💵 LIVE` / `🧪 DRY-RUN` 徽标（含 title 说明）；空态文案说明两类一并显示 |

## 4. 验证证据

### 4.1 重启后即时可见（含 DRY）

```
status?force_refresh=true →
  active_positions_count: 2
  id=237 dry=True mark=0.17 upnl=-6.0 buf=28.00%
  id=236 dry=True mark=0.17 upnl=-6.0 buf=28.00%
```

### 4.2 周期性重同步按 10s 节流生效

```
09:00:42  reloaded 2 active trades (LIVE 0 / DRY-RUN 2)
09:00:31  reloaded 2 active trades (LIVE 0 / DRY-RUN 2)
09:00:15  reloaded 2 active trades (LIVE 0 / DRY-RUN 2)
08:59:59  reloaded 2 active trades (LIVE 0 / DRY-RUN 2)
08:59:43  reloaded 2 active trades (LIVE 0 / DRY-RUN 2)
```
（间隔 10–16s = 10s 节流 ∧ 8s 监控周期对齐；日志含 LIVE/DRY 分类计数，便于日后核查）

### 4.3 DRY 单**确实在被管理**（标记随行情推进）

```
08:57:57  id=236/237 current_mark=0.17  last_modified=08:57:57   ← force_refresh 写入
08:58:48  id=236/237 current_mark=0.15  last_modified=08:58:48   ← 10s 监控循环自行刷新（此前长期冻结在开仓值 0.11/0.15）
```
⇒ 修复前 `last_modified` 长期等于开仓时间；修复后每 ~10s 随实时报价更新。

### 4.4 页面渲染（headless Chrome 截图核对）

- 区块标题：`活跃持仓监控 (Active Spread Monitor)` + **`LIVE 0`** + **`DRY-RUN 2`** 计数徽标
- 卡片：`自动 · 平衡日边界 · 🧪 DRY-RUN · BEAR_CALL_SPREAD · 8DTE · 平衡`，含安全垫缓冲、当前买回价、止盈/止损徽标
- 顶部指标「活跃持仓数 = 2」与监控区一致

### 4.5 回归与安全

| 检查 | 结果 |
|---|---|
| `py_compile`（manager / web app） | OK |
| 模板内联 JS `node --check` | OK |
| 手册 HTML 结构 | errors = **0** |
| HTTP | `/bbt_option_seller` 200 · `/api/option_seller/status` 200 |
| DB 写入 | 仅监控线程自身的标记/平仓写入（原行为）；无额外写入 |
| 竞态 | 原子替换后，无锁遍历 `self.active_trades.values()` 的状态接口不再可能触发 *dictionary changed size during iteration* |

### 4.6 追加：模式标识加强 + 页面缓存治理（用户第二次反馈）

用户在看到第一版后反馈「需要标识出是 LIVE 还是 DRY RUN」——排查发现**服务端已带徽标但其浏览器渲染的是缓存的旧 HTML**（本页全部交互逻辑都是模板内联 JS，旧 HTML ⇒ 新功能看不见，而 4 秒轮询拿到的却是新数据，极易误判为「功能没生效」）。据此做两项加强：

**（a）把模式标识做成「不可能看漏」**

| 位置 | 标识 |
|---|---|
| 区块标题 | `活跃持仓监控 (Active Spread Monitor)` + `LIVE n` / `DRY-RUN n` **计数徽标** |
| 组头（`开仓-1 (双批次 · 1组 · 2手)` 行） | **`🧪 DRY-RUN（试运行）`**（琥珀虚线 chip）/ `💵 LIVE（实盘）`（浅绿 chip）；同组混杂时显式标 `⚠ 混合 x LIVE / y DRY`（不误导为单一模式） |
| 持仓卡片 | 模式徽标**提到第一位**（在「自动 / 机制名」之前）；DRY 卡片另加**琥珀虚线外框 + 米色底**（`.pos-card-dry`，保留左侧多空实心色条） |
| 顶部指标「活跃持仓数」 | 副行拆分为 `活跃 N 手（LIVE x · DRY-RUN y）` |

**（b）页面改为不缓存（根治误判）**：`/bbt_option_seller` 路由显式回 `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` + `Pragma: no-cache` + `Expires: 0`，避免「改了模板但页面没变」再次发生。

**复测**（headless Chrome 实渲染）：区块标题 `LIVE 0` / `DRY-RUN 2`；组头 `🧪 DRY-RUN（试运行）`；卡片首个徽标 `🧪 DRY-RUN（试运行）` + 虚线琥珀框；指标副行 `活跃 2 手（LIVE 0 · DRY-RUN 2）`；响应头实测含 `Cache-Control: no-store…`；`py_compile` / `node --check` 通过。

### 4.7 一次自伤与修复（记录在案）：加强编辑误伤「待触发条件单」卡片

用户随后报障：**「今日交易流水账本」与「待触发条件单监控」两张卡片变空**（后端明明有 6 笔交易、1 张挂起条件单）。

**根因（我的回归）**：在做 4.6 的「模式徽标前置 + DRY 卡片虚线框」时，用脚本按字符串匹配替换卡片容器，把它同时套到了**待触发条件单卡片**上 —— 该处循环变量是 `o`（条件单对象），却引用了持仓对象变量 `p`：

```js
// 误改（条件单卡片，变量是 o）
<div class="pos-card ${borderClass} ${p.is_dry_run ? 'pos-card-dry' : 'pos-card-live'}" ...>
```

⇒ 第一张条件单渲染时抛 `ReferenceError: p is not defined`（`renderDashboard:4528`），被外层静默捕获 ⇒ `renderDashboard` **中断在条件单渲染处**，其后的「条件单容器 innerHTML 赋值」「账本 `__currentRawTrades = data.today_history` + `applyJournalFilterAndRender()`」**全部没有执行**，于是两张卡停留在模板里的静态空态文案。这也解释了为何 `pendingCondBadge` 显示「1 单挂起」（该行在抛错之前）而列表却是空态。

**定位方法**（值得复用）：注入脚本包一层 `window.renderDashboard` 捕获异常与堆栈写入 `journalTitleText`，得到 `RENDER-ERR: p is not defined ← at …:4528 ← at Array.forEach ← renderDashboard:4457`。

**修复**：把条件单卡片还原为 `<div class="pos-card ${borderClass}" …>`（模式徽标只属于「活跃持仓监控」的持仓卡片）。

**复测**：账本 `historyTableBody` 9 行（3 组 × 组头 + 两批次，含 `订单-3 (1组2手) 组合状态: 双批止损 合计盈亏: $-28.00`），空态文案消失；条件单卡渲染出 `SPX ≥ 7639.00 (现价 …)`；`window.__currentRawTrades.length = 6`（注入探针实测）；`renderDashboard` 不再抛错。

**教训**：同一模板里存在**多个形如 `<div class="pos-card ${borderClass}">` 的字面量**（持仓卡片用 `p`、条件单卡片用 `o`）—— 批量字符串替换必须**带上下文锚点**（例如连同 `${o.trigger_symbol}` 一起匹配），并在替换后跑一次**真实渲染断言**（本次若在改完立刻跑探针即可当场发现）。

### 4.8 修复后的生产实证（DRY 单被完整闭环管理）

修复生效后，两笔在管 DRY 单由 10 秒监控线程**在无任何进程重启的情况下**完整管理至平仓：

```
09:18:27  Trade #236 CLOSED (CLOSED_STOP_LOSS) @ 0.24 (Credit=0.11) Realized PnL=$-13.0
09:18:27  Trade #237 CLOSED (CLOSED_STOP_LOSS) @ 0.24 (Credit=0.11) Realized PnL=$-13.0
```

平仓价 0.24 正好等于配置的硬止损 `2.2 × 0.11`，且此前已连续观测到其 `current_mark` 随实时报价变化（0.11 → 0.15 → 0.17 → 0.24）——**证明重同步 + 监控对 DRY-RUN 单已形成完整闭环**（对比修复前：08:35 开出的 DRY 单必须等到 08:54 的进程重启才被止损）。

## 5. 回滚

- 术前副本：`/tmp/bbt_drymon_backup_090044/`（`option_seller_manager.py` / `bbt_option_seller.html`）
- 只回退同步行为：删除 `_monitor_loop` 内 `self._resync_active_trades()` 一行 ⇒ 监控区恢复「只显示本进程已知持仓」的旧行为

## 6. 遗留与后续建议

1. **单写者架构建议（中期）**：当前「谁开单」与「谁管理」分离，靠轮询 DB 弥合。更稳的做法是**把自动开仓编排也放进仪表盘进程**（哨兵只发触发事件），或把监控做成独立守护进程并让仪表盘只读其状态；否则一旦仪表盘未运行，**所有**在管持仓（含 DRY）都无人管理。
2. **DRY 单的止损口径**：本次实测 DRY 单在 2.27× 权利金处止损（硬止损 2.20× + 报价滑点），与 LIVE 一致；如需 DRY 与 LIVE 差异化的止损/止盈口径，应显式配置而非默认一致。
3. **进程重启依赖已消除**，但**监控线程存在依赖仍在**：仪表盘关闭（或 `is_monitoring=False`）时，DRY 与 LIVE 单均不被评估（LIVE 尚有券商侧保护止损兜底，DRY 没有）。建议后续加一条巡检：若在管持仓非空而监控未运行则告警。
