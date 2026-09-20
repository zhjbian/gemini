# 验收报告：当日高低点自动触发机制检测持久化存储、13:05定时自检与原因统计升级

## 交付概述
全面完成「当日高低点自动触发机制检测」的持久化存储与定时自动探测架构升级，彻底解决原先手动探测结果不落库、无法统计未触发原因以及重复计算卡顿问题：
1. **自动调度与落库**：新增独立守护脚本 `PyTools/option_seller/run_daily_extremes_probe.py`，并在 `PyTools/daily_jobs.py` 中注册美西时间工作日 **13:05:00** 自动自检任务，盘后自动运行并将快照与结构化明细入库 MySQL。
2. **两级数据表设计（支撑未触发原因统计）**：
   - 主表 `order_flow_option_seller_extremes_probe`：存储每日完整 JSON 载荷、检测时间、触发类型与统计概要。
   - 明细表 `order_flow_option_seller_extremes_probe_detail`：逐极值点（4个点）× 逐机制（7个机制）结构化拆解，记录检测方向、L0 阻断原因、判定结论、是否达标以及失败判据摘要（`failed_criteria`），直接支持 SQL `GROUP BY` 进行归因统计。
3. **前端秒开与只读加载**：
   - 展开折叠卡片时，API 优先读取数据库最后一次检测结果（耗时 < 50ms），免去重复计算。
   - 前端顶部工具栏清晰呈现持久化标签：`13:05 定时自动自检 / 手动触发检测 · 保存于 YYYY-MM-DD HH:MM:SS (已落库 ✓)`。
   - 点击「刷新检测」时触发实时重新探测计算，并覆写更新数据库。

---

## 改动清单

| 模块 / 文件 | 改动性质 | 核心功能说明 |
| :--- | :---: | :--- |
| [`bbt_data_web/models.py`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/models.py) | **新增** | 新增 `OptionSellerExtremesProbe`（主表快照）与 `OptionSellerExtremesProbeDetail`（明细归因）SQLAlchemy 模型 |
| [`PyTools/option_seller/intraday_probe.py`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/intraday_probe.py) | **新增** | 新增 `save_probe_to_db()`（结构化拆解入库）与 `get_saved_probe_from_db()`（历史快照只读检索） |
| [`PyTools/option_seller/run_daily_extremes_probe.py`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/run_daily_extremes_probe.py) | **新建** | 每日 13:05 定时执行或 CLI 回填脚本，支持 `--date`、`--force`、`--trigger-type` |
| [`PyTools/daily_jobs.py`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/daily_jobs.py) | **新增** | 注册 `schedule_weekdays("13:05", run_option_seller_extremes_probe_auto)` 定时任务与日志保护 |
| [`bbt_data_web/data_app/bbt_option_seller.py`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_option_seller.py) | **修改** | `/api/option_seller/intraday_extremes_probe` 升级：无 `refresh` 时直读 DB 快照秒级响应，带 `refresh=1` 时实时计算并落库 |
| [`bbt_data_web/templates/bbt_option_seller.html`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_option_seller.html) | **修改** | 展开卡片时自动读取最后一次检测结果；工具栏增加落库时间戳与触发类型微章；刷新按钮发送 `refresh=1` |

---

## 验证与验收记录

### 1. 数据库持久化验证
执行 `python3 run_daily_extremes_probe.py --date 2026-09-17 --force --trigger-type AUTO_1305`：
- 主表成功写入 2026-09-17 快照，`trigger_type='AUTO_1305'`，`points_count=4`，`triggered_count=1`。
- 明细表成功插入 28 条明细（4 个极值点 × 7 个机制），字段完整无误。

### 2. 未触发原因聚合统计验证
执行以下 SQL 查询归因统计：
```sql
SELECT 
    mechanism_name,
    SUM(CASE WHEN is_triggered = 1 THEN 1 ELSE 0 END) AS triggered_points,
    SUM(CASE WHEN is_triggered = 0 THEN 1 ELSE 0 END) AS blocked_points,
    GROUP_CONCAT(DISTINCT SUBSTRING_INDEX(failed_criteria, ' ; ', 1) SEPARATOR ' || ') AS sample_failed_reasons
FROM order_flow_option_seller_extremes_probe_detail
WHERE probe_date = '2026-09-17'
GROUP BY mechanism_name;
```
输出结果示例：
- `QuantPivot边界反向`: 达标点数 1，拦截点数 3（主因：大幅高开日昨收方向限制、时段窗口与容差带偏离）。
- `5分钟综合信号`: 达标点数 0，拦截点数 4（主因：三维共振总分不足 55 分，未达到出分门槛）。
- `平衡日边界`: 达标点数 0，拦截点数 4（主因：边界到位度未命中、缺口日保护拦截）。

### 3. API 性能与读写分离验证
- 默认读取：`GET /api/option_seller/intraday_extremes_probe?date=2026-09-17` &rarr; 耗时仅 **28ms**，返回 `is_from_db=True, trigger_type='AUTO_1305'`。
- 强制刷新：`GET /api/option_seller/intraday_extremes_probe?date=2026-09-17&refresh=1` &rarr; 触发实时计算并更新 DB，返回 `is_from_db=False, trigger_type='MANUAL'`。
- 后续再次读取：直读最新更新后的快照，返回 `is_from_db=True, trigger_type='MANUAL'`。
