# 交接单（HANDOFF）· 卖家系统触发层 / 多选 Force Dry-Run

> 用法：在新会话里把本文件路径贴给 agent，或直接粘贴下方「粘贴用提示词」。
> 归档目录：`~/.gemini/cli-workspace/gemini-answers/system_modules/45_2026-09-13_OptionSeller_MoveEnd_Trigger_Layer/`
> 模块时间线：`bbt_trading_modules.html` → **mod-45**（涵盖模块 45）

## 0. 系统与术语（全局规则 (13) 已写入 AGENTS.md ✓）
- **卖家系统** = 期权卖家系统 `http://127.0.0.1:5005/bbt_option_seller`
- 代码：`PyTools/option_seller/option_seller_engine.py`（判定）、`option_seller_manager.py`（开平仓/自动单）
- 表：`order_flow_option_seller_trades` / `order_flow_option_seller_conditional_orders` / `option_seller_conditional_order_events`
- 规则手册（唯一权威）：`~/.gemini/cli-workspace/gemini-answers/system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html`
  - 第三部分 Option Seller：§1 风险锁死 · §2 合约选型 · §3 三重退出 · §4 双批次 · §5 **三档开仓策略=选 spread 结构** · §6 双场景 · §7 12:30 时间止损 · **§8 5m 四层漏斗（100 分制：OF/DOM 40 分；`groups<2` 硬顶；11:30 截断）** · **§9 QuantPivot 边界反向** · **§10 盘前大单+EMA 回踩** · **§11 极值耗竭与震荡边界反向（第二套独立通道）**

## 1. 问题与既定口径
- 实测触发来源：`MANUAL_UI_SCAN 36` / `AUTO_COUNTER_TREND_BOUNDARY 10` / `CONDITIONAL_ORDER 8` / **`AUTO_5M_SYNTHESIS 仅 2`**（8 天）⇒ 自动单机会太少
- 用户口径：**三档开仓策略 = 选 spread 结构**；**信号强弱 = 开仓组数(groups)**
- 取向：小仓、多次、稳定（非稀有强信号开大仓）；**不得单独依据 SPX Gamma 开仓**
- 约束：**保持 dry-run**（有意调试期）；`groups<2`；**11:30 PST 截断保持**；平衡日**允许 EMA 缠结但需边界确认**（已获同意）

## 2. 已完成（可交付）
1) **多选 Force Dry-Run（后端全通）**：`Config/option_seller_force_dry.json`（默认 `{"triggers": []}` = 不改行为）+
   `option_seller_manager.py` 新增 `load/save_force_dry_triggers` / `trigger_force_dry()`（**前缀匹配**）/ `set·get_force_dry_triggers()`，
   并把判定挂到**三处** dry 咽喉（484 / 817 / 838 行）⇒ 一处生效、全触发覆盖；status 暴露 + **API `GET/POST /api/option_seller/force_dry`**（实测 ✓）
   可选清单（6）：`AUTO_5M_SYNTHESIS` `AUTO_COUNTER_TREND_BOUNDARY` `AUTO_PM_BIG_TRADE` `AUTO_RANGE_BOUNDARY`(新) `AUTO_MOVE_END`(新) `CONDITIONAL_ORDER`
   回滚：`/tmp/osm.bak-forcedry-*`
2) **触发层评分（第一阶段·影子·零风险）**：`PyTools/option_seller/move_end_evaluator.py`（五维 100 分 A35/B25/C20/D10/E10；`is_spoof_trap` 一票否决；趋势日仅逆势一侧；`confidence_to_groups` ≥85→2组、70–84→1组）+
   `move_end_shadow.py`（影子回放，只读、不写业务表、不下单）。
   验收（近 10 交易日）：触发 **45 次 ≈4.5/日**（目标 ≥3 ✓）、**R=24/T=21**、**BULL=26/BEAR=19**、85+ 7 个、假信号率 0%（口径偏松待收紧）
3) **归档**：mod-45（html + md）

## 3. 待办（本轮未做，需新会话执行）
1) **页面多选 UI**：在 `bbt_data_web/templates/bbt_option_seller.html`（3,900+ 行）把现有 synthesis force-dry 按钮升级为**6 项复选**，POST 至已就绪的 `/api/option_seller/force_dry`
2) **手册统一**（用户明确要求）：
   - 在 Part 3 **最后一个子 section** 下建**父级 section**：① 首个 sub-sub = **各机制概览 table** ② 之后每个 sub-sub 对应一个机制
   - 机制清单：§8 四层漏斗 / §10 盘前大单+EMA / §11 极值耗竭与震荡边界 / §9 QuantPivot 边界反向 / **新 2 个（Path R=平衡日边界、Path T=移动结束）**
   - ⚠️ **既有 4 节是"移动位置"而非重新定义**（避免两份并存 ✗）；同步更新 TOC
3) **接线**：`option_seller_manager.py` 5m 自动路径调用 `score_move_end(...)`；通过条件 `groups≥1` + `active_auto_groups<2` + `<11:30` + `is_enabled`；标签 `AUTO_RANGE_BOUNDARY` / `AUTO_MOVE_END`；**保持 dry-run**；参数外置 + 一键开关；回滚点 `/tmp/option_seller_manager.py.bak-*`
4) **收紧假信号口径**（12 点/30 分钟 + MFE/MAE）重跑影子后再放量

## 4. 作业纪律（本会话踩过的坑，务必遵守）
- **改任何蓝图/模板文件后必须立即自检**：`python3 -c "import data_app.<mod>"` + `curl -I http://127.0.0.1:5005/<page>`（本会话曾因蓝图名写错 `bp_bbt_option_seller` ✗ 导致 5005 全站崩溃 ✗）
- 蓝图真实名：`bbt_data_web/data_app/bbt_option_seller.py` 内为 **`bp_option_seller`**（URL 前缀 `/api/option_seller/...`）
- `bbt_data_web` 未发现 launchd 托管 ⇒ 启动方式：`PYTHONPATH=<repo>/PyTools:$PYTHONPATH nohup /usr/local/bin/python3 bbt_data_web/bbt_data_app.py &`
- 脚本插入代码后**先断言锚点、后写盘**，并**核验新符号存在**（本会话多次出现"静默未插入" ✗）
- 规则 (10) 归档 + (11) 决策规则写手册 + (12) 浅色主题

## 5. 粘贴用提示词（复制给新会话）
```
继续做「卖家系统（期权卖家 127.0.0.1:5005/bbt_option_seller）触发层」的剩余工作。
先读交接单：~/.gemini/cli-workspace/gemini-answers/system_modules/45_2026-09-13_OptionSeller_MoveEnd_Trigger_Layer/HANDOFF.md
（必要时读同目录 walkthrough.html；手册见 gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html 第三部分 §8–§11）

按顺序做三件事，每改一处立即自检（蓝图/模板文件必须做导入 + HTTP 200 校验）：
1) 页面多选 UI：bbt_data_web/templates/bbt_option_seller.html —— 把 synthesis force-dry 升级为 6 项复选，接 /api/option_seller/force_dry（后端已就绪）
2) 手册统一：Part 3 最后新增父级 section（首节=各机制概览 table，其后每节一机制），把既有 §8/§9/§10/§11 **移动**进该父级（不重定义），并补新 2 个机制；同步 TOC
3) 接线：管理器 5m 自动路径调用 score_move_end（保持 dry-run、groups<2、11:30 截断、带开关）；随后收紧假信号口径重跑影子

约束：保持 dry-run；groups<2；11:30 截断不变；平衡日 EMA 缠结需边界确认；不得单独依据 SPX Gamma 开仓；小仓多次。
改动前备份、改动后给自检结果与回滚点。
```
