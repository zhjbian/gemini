# BBT Signals Order Flow 展开详情：基本规则方向准入与强度打分 UI 可视化集成

本方案旨在根据系统核心手册《[第一部分：Order Flow 订单流分析规则](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html)》中的：
- **3. 第一步：基本规则方向准入判定 (Direction Qualifying Rules)**
- **4. 第二步：底层数据强度打分体系 (Strength Scoring 1 ~ 10 分)**

在 `http://127.0.0.1:5005/bbt_signals` 页面中的 **Order Flow 实时信号** 表格每一行展开详情（Child Row）中进行全新升级。

保留现有的 4 个基础数据卡片（`Recent 5-Min Micro`、`Recent 30-Min Metrics`、`RTH Cumulative`、`PM Metrics`）以及底部的 `Adam Set DOM 盘口深度与微观结构` 卡片，追加两大道量化检测与评分卡片，实时检测对应底层数据并直观标记是否达到规则指标。

---

## User Review Required

> [!IMPORTANT]
> **1. 展开行 UI 布局与信息层次设计**:
> - **保留项**: 保留截图中的 4 个基础卡片以及全景 `Adam Set DOM` 卡片。
> - **替换项**: 移除过时废弃的旧版哨兵条件卡片（已过时的 4 条件 A/B/C/D 判定），由全新的两步判定法组件全面替代。
> - **新增项 1**: 【第一步：基本规则方向准入判定】卡片，涵盖：前置硬性约束拦截（反追高/反杀跌空间红线、DOM 虚假撤单陷阱、大单压制）、三大核心形态检验矩阵（Setup 1 底部/顶部吸收反转、Setup 2 趋势日双柱回踩/回抽、Setup 3 价值区突破/破位点火），分层展示第一道门（空间门槛）与第二道门（微观特征）的实时达标状态。
> - **新增项 2**: 【第二步：底层数据强度打分体系】卡片，涵盖：1~10 分强度仪表板（含 High/Medium/Low/Neutral 分级徽章与彩色分段进度条）、9 大客观底层数据加分项检测清单，并附实时实测数值对比与“+1分 达标 (MET)”/“0分 未达标 (UNMET)”状态标记。

> [!NOTE]
> **2. 浅色主题 (Light Theme) 规范**:
> 严格遵循全局规则（12），统一采用白底 (`#ffffff`)、浅天蓝 (`#f0f9ff`)、浅青绿 (`#f0fdf4`)、浅粉红 (`#fef2f2`) 等清新护眼的高对比度浅色调，杜绝暗色背景。

> [!NOTE]
> **3. 兼容性支持**:
> 既支持包含最新结构化 `quantitative_metrics` 字段的信号，也对旧版/无预存指标的历史信号进行客户端实时微观数据计算与规则验证，确保每一条记录展开均能获得完整解析。

---

## Proposed Changes

### 1. 前端交互与视图组件 (`bbt_data_web/static/js/bbt_signals.js`)

#### [MODIFY] [bbt_signals.js](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/static/js/bbt_signals.js)
- 在 `format(d)` 展开渲染函数中：
  1. **保留 4 大卡片与 DOM 卡片**:
     - `microCardHtml` (`Recent 5-Min-Bar Micro`)
     - `thirtyMinCardHtml` (`Recent 30-Min Metrics`)
     - `rthCardHtml` (`RTH Cumulative` + `30-Min Progression`)
     - `pmCardHtml` (`PM Metrics` + `30-Min Progression`)
     - `domCardHtml` (`Adam Set DOM 盘口深度与微观结构`)
  2. **提取/兜底计算实时微观指标**:
     - `price_position_pct`: 价格处于全天振幅的相对百分比
     - `net_delta_30m`, `price_change_30m`, `dper_30m`
     - `last_15m_delta`, `last_10m_delta`, `last_5m_delta`
     - `w_imb` (DOM 加权失衡), `imb_mom` (失衡动量), `vac_ask`, `vac_bid` (流动性真空), `ice_bull`, `ice_bear` (冰山托压单)
     - `spoof_bid`, `spoof_ask`, `stack_bid`, `stack_ask`, `book_flip_bull`, `book_flip_bear`
     - `big_trade_net_2h`
  3. **构建 UI 元件 A: 基本规则方向准入判定 (Direction Qualifying)**:
     - 判定概览横幅：当前方向判定（Bullish / Bearish / Neutral）、生效的基准形态名称、起跑分赋值。
     - 前置刚性约束与风控过滤器（空间红线检测、虚假撤单诱捕过滤、大单反向压制过滤）。
     - 三大形态准入检测网格（Setup 1 吸收反转、Setup 2 趋势日双柱重燃、Setup 3 价值区点火）：
       - 第一道门：物理位置/空间准入门槛（途径 A/B/C 或宏观条件）。
       - 第二道门：微观订单流确认判据（量价背离、DOM 翻盘、冰山护盘、机构吸筹等）。
       - 标记每一个分支条件的“通过 / 未通过”及实时数值。
  4. **构建 UI 元件 B: 底层数据强度打分体系 (Strength Scoring 1 ~ 10 分)**:
     - 强度总分仪表板：`得分 / 10 分`，分级 Badge（`High [8-10分]`、`Medium [5-7分]`、`Low [1-4分]`、`Neutral [0分]`），带 0~10 分段色条。
     - 9 大客观底层数据加分项检测清单：
       - 加分 1: 30m 持续大单边推进 (`|net_delta_30m| >= 3000`)
       - 加分 2: 30m 极强爆发式推力 (`|net_delta_30m| >= 5000`)
       - 加分 3: 最新 10m 双柱强动能 (`|last_10m_delta| >= 800`)
       - 加分 4: 最新 5m 单柱脉冲放量 (`|last_5m_delta| >= 500`)
       - 加分 5: DOM 深度显著失衡且动量一致 (`|w_imb| >= 20% 且 mom 顺向`)
       - 加分 6: DOM 阻力/支撑档位真空 (`vacuum_sec >= 20.0s`)
       - 加分 7: DOM 盘口被动冰山大单 (`iceberg >= 1`)
       - 加分 8: 2小时机构大单净流确认 (`|big_trade_net_2h| >= 1500 或机构吸筹/派发`)
       - 加分 9: 趋势日与均线带大势共振 (SPY趋势日且价格在 15m EMA13 顺向侧)
     - 每一加分项以清晰表格/卡片展示：【评估维度】、【规则标准】、【实时数据测量值】、【加分达标标记 (+1分 / 0分)】。
     - 计算汇总栏：`起跑分 (1分) + 加分项累加 (X分) = 最终强度得分 (Y分)`（Neutral 状态明确标明归 0 分）。
  5. **清除过时的旧代码**:
     - 彻底移除废弃的 `sentinelTriggerHtml` 与 旧版 4 条件 A/B/C/D `calcHtml`。

---

### 2. 页面与缓存控制 (`bbt_data_web/templates/bbt_signals.html`)

#### [MODIFY] [bbt_signals.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_signals.html)
- 将 `<script src="{{ url_for('static', filename='js/bbt_signals.js') }}?v=1.2.27"></script>` 升级为 `?v=1.2.28`，强制浏览器刷新静态资源。
- 在页面样式区补齐新卡片所需的光滑边框、轻盈投影与浅色徽章样式定义（保持纯 Light Theme）。

---

### 3. 系统技术档案归档与索引更新

#### [NEW] [implementation_plan.md](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/38_2026-09-06_OrderFlow_Two_Step_UI_Visualization/implementation_plan.md)
- 归档本实施计划至 `/Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/38_2026-09-06_OrderFlow_Two_Step_UI_Visualization/implementation_plan.md`。

#### [MODIFY] [bbt_trading_modules.html](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/bbt_trading_modules.html)
- 追加第 38 号模块条目，记录“BBT Signals Order Flow 展开详情两步判定法与 1~10 强度评分 UI 可视化集成”。

---

## Verification Plan

### Automated / Data Tests
- 使用 Python 脚本针对不同类型的真实信号数据运行检测：
  - 测试 `2026-09-04 07:55:00` (Neutral 记录，触发低位防守禁杀跌)：确认卡片正确识别 Neutral 状态、起跑分归0、前置红线生效、加分项明细展示。
  - 测试 `2026-09-04 08:00:00` (Bearish 记录)：确认卡片正确识别 Bearish 状态、起跑分1分、Setup 识别、9项加分项测量值匹配。
- 验证 `bbt_signals.js` 语法与 HTML 模版加载完整性，无 JS 语法错误。

### Manual Verification
- 用户刷新 `http://127.0.0.1:5005/bbt_signals`。
- 点击展开任意 Order Flow 信号行，检查：
  1. 原有 4 个基本数据卡片与 DOM 全息卡片保持原貌；
  2. 新增的第 1 步基本规则准入判定卡片清晰渲染，高亮显示命中形态与风控过滤；
  3. 新增的第 2 步强度打分卡片清晰展示 1~10 进度条与 9 项底层数据加分指标检测。
  4. 整体界面严格保持优雅美观的浅色主题 (Light Theme)。
