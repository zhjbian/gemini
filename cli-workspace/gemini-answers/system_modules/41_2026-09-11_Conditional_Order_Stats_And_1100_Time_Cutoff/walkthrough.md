# 验收报告 (Walkthrough)

**模块编号**: 41
**归档目录**: `41_2026-09-11_Conditional_Order_Stats_And_1100_Time_Cutoff`
**发生日期**: 2026-09-11
**核心模块名称**: 系统自动条件单统计引擎与 11:00 PST 时段截断自动撤单 (Auto Conditional Order Statistics Engine & 11:00 PST Time-Cutoff Sweep)
**涉及技术栈**: Python / OptionSellerManager Monitor Loop / MySQL 事件流表 / Seattle(PT) 时区标准化 / Flask API / Light-Theme UI / Rule Manual

---

## 1. 交付清单

| 层 | 文件 | 变更 |
| --- | --- | --- |
| 模型 | `bbt_data_web/models.py` | 新增 `OptionSellerConditionalOrderEvent`（表 `option_seller_conditional_order_events`），既有条件单表**零改动** |
| 建表 | 直接 DDL（见下） | `CREATE TABLE option_seller_conditional_order_events`（含 6 个索引） |
| 数据访问 | `bbt_data_web/db_query_module/db_query_option_seller.py` | `..._event_add` / `..._events_query` / `..._cancel_events_map` / `..._stats`；`..._cancel(order_id, reason)` 支持撤销原因落库 |
| 管理器 | `PyTools/option_seller/option_seller_manager.py` | 布防窗口常量与判定、事件埋点（PLACED/TRIGGERED/CANCELLED）、`cancel_all_conditional_orders`、`enforce_conditional_order_cutoff`、监控循环每轮先执行截断扫描、自动布防闸门；**移除 created_at/last_modified 的 +7h UTC 补偿** |
| API | `bbt_data_web/data_app/bbt_option_seller.py` | 创建闸门（截断区 409 拒绝）、条件单列表补充 `cancel_reason`/`is_time_cutoff`/`source`/`cancelled_at` 与 23:30 页面清除、新增 `GET /api/option_seller/conditional_order_stats`；`_local_dt_str` 移除时区补偿 |
| UI | `bbt_data_web/templates/bbt_option_seller.html` | 「11:00 PST 时段截断」分组（灰底 + 「未触发且不会再触发」标注 + 保留至 23:30 说明）与「条件单统计」面板（KPI + 5 张分组表，浅色主题） |
| 工具 | `scripts/backfill_conditional_order_events.py` | 存量条件单事件回填（幂等、支持补洞） |
| 工具 | `scripts/migrate_mysql_tz_to_seattle.py` | 误存 UTC 的 datetime 列 → PT（证据判定 + 备份 + 回滚） |
| 规则 | 规则手册 HTML + 对应 `.md` | 决策架构 §1 追加「11:00 PST 自动撤销全部条件单（执行面强制）」 |

## 2. 验收结果

### 2.1 时段截断（需求 1）

| 验收项 | 结果 | 证据 |
| --- | --- | --- |
| 截断区自动撤销全部 PENDING | **通过（真实运行中自证）** | 3 条残留 PENDING（#57/#58/#59）于 **2026-09-11 19:40:17 PT** 被运行中的监控循环自动撤销；`status=CANCELLED`，事件流 `cancel_reason=TIME_CUTOFF_1100`，`notes` 落 `[TIME_CUTOFF_1100]` 标记 |
| 布防窗口内不误撤 | 通过 | `is_conditional_arming_window()` 仅在 `[11:00, 23:30)` PT 判定为截断区 |
| 页面仍展示 + 标注 | 通过 | headless 实测：`#cutoffConditionalWrap` 可见、3 张卡片、徽标「3 单」、卡片含「已时段截断 · 未触发且不会再触发」、显示撤销时间 19:40:17 与原因 `TIME_CUTOFF_1100` |
| 保留至 23:30 后清除显示 | 通过 | 接口按 PT 时刻 `< 23:30:00` 返回 `cutoff_display_active`；其后过滤 `is_time_cutoff` 单（DB 事件保留） |
| 截断区禁止新建布防 | 通过 | `POST /conditional_order/create` 返回 **409** + 说明文案（`BLOCK_CREATE_OUTSIDE_ARM_WINDOW=True` 可一键回退为仅告警） |

### 2.2 统计功能（需求 2）

`GET /api/option_seller/conditional_order_stats?date_from=2026-08-29&date_to=2026-09-11` 返回（存量回填后实测）：

- 挂单 **21** / 触发 **6** / 撤销 **15**（其中 11:00 截断 **3**）；触发率 **28.6%**
- **按方向（双向对称）**: 看涨 BULLISH 挂单 12 / 触发 3 / 触发率 25.0% / 平均触发偏差 −0.04 点；看空 BEARISH 挂单 9 / 触发 3 / 触发率 33.3% / 平均触发偏差 +0.71 点
- 按来源: 系统自动 AUTO 挂单 10 / 触发 3（30.0%）；手动 MANUAL 挂单 11 / 触发 3（27.3%）
- 按触发条件: SPX:LTE / SPY:GTE / SPY:LTE / SPX:GTE / ES:GTE 五组
- 平均等候（挂单→触发）**394.3 分**；事件流 42 条、覆盖 21 单
- **布局修复（2026-09-11 追加）**：5 张分组表原先各自按内容自适应列宽 → 列宽不一致、纵向不对齐，观感破碎。改为**统一列网格**（`colgroup` 固定 7 列 + `table-layout:fixed`）+ 外层 `overflow-x:auto` 兜底，KPI 行由 flex 改为 `grid-template-columns:repeat(auto-fit,minmax(158px,1fr))`。实测（headless，1440/1100/900 三档视口）：5 表 `col` 数均为 7、**表头列坐标完全一致（aligned=true）**、无页面横向溢出。
- **时区二次修正（2026-09-11 追加，用户指出「按小时段」小时非 Seattle）**：统计面板「按小时段 (PT)」曾出现 14/15/18/03 等异常小时。逐行取证结论：事件的三个时间源分属两个时钟 —— `created_time`（应用 PT）/`triggered_at`（应用 PT）/`created_at`（DB UTC，已转换）而 **`last_modified` 由数据库 `onupdate=CURRENT_TIMESTAMP` 写入 ⇒ 当时为 UTC**（同表 `created_at` 同源，上轮被误判为“保持不动”）。证据：`#54` 修正后创建 07:00:31 → 撤销 07:05:54（同一 PT 口径，合理）；`#56` `triggered_at`(01:00:17) 与 `last_modified`(01:00:16) 落在同一时刻。
  处置：① 以**服务器时区切换时刻 `2026-09-11 19:36:00` 为界**，仅转换该时刻之前的 `last_modified`（18 行，避免对切换后已正确的 #57–59 二次偏移），备份批次 `lastmod_20260911_1940`；② 删除并重建由该列派生的 12 条回填 `CANCELLED` 事件。修正后小时分布全部落于合理 PT 时段（挂单 06/07/08/10/11/18h；撤销 00/01/07/08/11/17/18/19/20h）。
  附带观察（非时区问题，**用户 2026-09-11 明确确认：无需处理**）：`TRIGGERED` 含 **01:00 PT 隔夜触发 2 笔**，属**真实且预期的触发** —— 条件单触发判定**有意不限定 RTH**（监控循环固定 8s 常驻，条件单武装后即持续比对实时报价）。因此「平均等候（挂单→触发）」指标天然包含长时间/隔夜等待（该例 17.8 小时），属正常口径，**不加「仅 RTH 触发」闸门**。注：11:00 PST 时段截断规则约束的是**布防（武装）与存活**，与「何时允许触发」是两条独立规则，二者不冲突。
- **默认收起（2026-09-11 追加）**：统计面板正文 `#condStatsBody` 默认 `display:none`，标题栏右侧新增「展开/收起」按钮（`toggleCondStats()`，图标随状态切换 chevron-right/down）。**首次展开才发起统计请求**（`condStatsLoaded` 标记，之后复用数据），60s 轮询仅在展开状态下执行——首屏不再产生无用请求。标题行（含徽标、来源筛选、刷新）保持常显以承载该按钮。实测：首屏 `display=none`、按钮「展开」、表格数 0、无请求；点击后 `display=block`、5 张表、按钮「收起」；再收起/再展开均正常且不重复加载。
- UI 实测：面板徽标「2026-08-29 ~ 2026-09-11 · 挂单 21 / 触发 6」，5 张分组表（方向/来源/子场景/小时段/按日），浅色主题（面板白底 + `#f8fafc` 卡片）

### 2.3 数据库时区标准化（Seattle 时间）

| 项 | 结果 |
| --- | --- |
| 服务器持久化 | `/opt/homebrew/etc/my.cnf` 增加 `[mysqld] default-time-zone = 'America/Los_Angeles'`（备份 `/tmp/my.cnf.bak-*`） |
| 运行时生效 | `SET GLOBAL time_zone='America/Los_Angeles'`；新会话 `NOW()` = PT（实测 19:36:45 与系统 `date` 一致） |
| 历史数据迁移 | **21,983 行 → PT**：`order_flow_option_seller_conditional_orders.created_at`(21)、`spx_gamma_signals.created_at`(1423)、`x_news.received_at`(18856)、`x_posts.created_at`(1683) |
| 迁移正确性 | 条件单 `created_at` 与 PT `created_time` 差值由 +420 分变为 **0 分** |
| 备份/回滚 | 备份表 `tz_migration_backup_datetime`（批次 `20260911_193811`）；`--rollback` 一键还原 |
| 应用侧一致性 | 移除管理器 `+7h` UTC 补偿与 API `_local_dt_str` 补偿（否则对 PT 值二次偏移） |
| 判定方法 | **表内锚点法**（同表应用端 PT 列逐行比对）+ 就近法（最近行 <90min）；`timestamp` 列自动随会话时区换算故不迁移；upsert 表（锚点非决定性）不采信锚点 |

**12 个「待确认」列的最终裁定（2026-09-11，按用户指定判据）**：

判据 = 这些 `created_at` / `last_modified*` 事件**大部分应落在 Seattle 06:00–23:00**；仅当某列存在**明确比例（≥50%）的取值落在窗口之外、且整体前移 7h/8h 后可回到窗口内**时，才判为 UTC 并转换；两侧都能自洽（即“不能判定”）则**一律不转换**，以后按 Seattle 时间入库即可。

实测结论：**12 列全部保持不动（0 列转换）**。原因：各列窗口外占比最高仅 36.9%（`whale_trade_case_studies.created_at`），且时段分布在“已是 PT”与“原为 UTC”两种假设下**都可以自洽**（例：`order_flow_pivots` 的 04:00–05:00 既可能是 PT 夜间计算任务，也可能是 UTC 前移后的 11:00–12:00；`economic_events` 的 05:00 既可能是 PT 盘前抓取，也可能是 UTC 前移后的 22:00 夜间抓取），证据不足以支撑不可逆的 7–8 小时偏移，故按用户兜底准则保持现状。

**生效范围**：自服务器时区改为 `America/Los_Angeles` 起，上述所有列的**新写入数据均为 Seattle(PT)**；旧数据可能仍为 UTC（列内新旧不一致），但均为非关键审计时间戳，按用户判断可接受。
裁定工具：`scripts/decide_timezone_by_business_window.py`（dry-run 默认；`--apply` 可对将来判定为 UTC 的列批量转换，先备份后转换）。

## 3. 回滚

1. 行为回退：`BLOCK_CREATE_OUTSIDE_ARM_WINDOW=False`（仅告警放行）；删除 `_monitor_loop` 中的 `enforce_conditional_order_cutoff()` 调用即恢复「不自动撤单」。
2. 数据回退：`python3 scripts/migrate_mysql_tz_to_seattle.py --rollback`；`DROP TABLE option_seller_conditional_order_events`（既有表未改动，无影响）。
3. 时区回退：`/opt/homebrew/etc/my.cnf` 还原备份并 `SET GLOBAL time_zone='SYSTEM'`，重启 mysqld。
4. 文档回退：删除手册 §1 中「11:00 PST 自动撤销全部条件单」条目（HTML 与 `.md` 各一处）。
