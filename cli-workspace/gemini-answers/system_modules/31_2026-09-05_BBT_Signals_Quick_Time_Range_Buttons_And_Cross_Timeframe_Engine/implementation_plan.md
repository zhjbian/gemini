# BBT Signals 实时信号微观时段快捷筛选按钮与全周期穿透引擎 实施计划 (Implementation Plan)

## 1. 需求背景与目标
在 `http://127.0.0.1:5005/bbt_signals` 页面中，伴随 5 分钟微观周期的全面引入，日内信号数据量显著增加。为了辅助交易员在盘中分时段精准复盘和微观研判（如开盘冲高回落、欧盘美盘交接洗盘、午盘收敛与尾盘定向）：
1. 在“Order Flow 实时信号”与“SPX Gamma 实时信号”的现存 `Timeframe` 下拉框后，分别追加三个极速时段过滤按钮：
   - `6:30 - 8:00`（开盘定式波段）
   - `8:00 - 10:00`（盘中主趋势与博弈波段）
   - `10:00 - 13:00`（午后收敛与尾盘变盘波段）
2. **核心业务逻辑与过滤要求**：
   - 点击时段按钮后，只显示该时间段内符合其他过滤条件（如方向、重要性、日期等）的记录；
   - **不包括 Timeframe dropdown**：即无论记录是 30m 还是 5m 周期，只要落在该时段内均完整呈现，实现跨周期的纵向时段穿透；
   - 按钮支持再次点击取消激活（Toggle），恢复全天信号；若用户手动切换 Timeframe 下拉框，则自动解除时段高亮。

---

## 2. 详细技术方案

### 2.1 后端 API 接口升级 (`bbt_signals.py`)
- 在 `/data/order_flow_signals` 和 `/data/spx_gamma_signals` 两个数据接口中，接收 `timeRange` 参数（如 `06:30-08:00`）。
- 当 `timeRange` 存在且包含 `-` 时：
  - 提取起止时间并标准化为 `HH:MM:00` 格式；
  - 加入 SQL 过滤：`signal_time >= start_t AND signal_time <= end_t`；
  - **穿透 Timeframe**：通过 `elif timeframe: ...` 的优先互斥，让 `timeRange` 自然穿透并跳过 `timeframe` 限制。

### 2.2 前端页面布局与样式 (`bbt_signals.html`)
- 在页面顶部 `<style>` 中补充符合规则 (12) 浅色主题规范的 `.btn-time-range-group` 与 `.btn-time-range` 样式。
- 默认状态：白色背景、清新天蓝边框与字体（`#2563eb`）；悬停时变为浅蓝底色（`#eff6ff`）；激活状态：深蓝底白字（`#2563eb`）并带有微投影。
- 在两个 section 的 `timeframeFilter` / `gammaTimeframeFilter` 右侧注入对应按钮组。

### 2.3 前端事件与数据联动 (`bbt_signals.js`)
- 维护 `selectedOfTimeRange` 与 `selectedGammaTimeRange` 状态；
- 实现 `window.setTimeRangeFilter(target, range, btn)` 函数，处理 Toggle 状态切换；
- 点击快捷按钮时，将对应 `timeframeFilter` 自动重置为 `'all'`，确保下拉框呈现与后端全周期穿透一致；
- 绑定 `timeframeFilter.on('change')`，当用户主动改变下拉框且值非 `all` 时，自动取消时段高亮并清空变量；
- 在 DataTables 的 `ajax.data` 钩子中传递 `d.timeRange = selectedOfTimeRange` / `selectedGammaTimeRange`；
- 更新静态资源版本号为 `?v=1.2.26` 彻底防缓存。

---

## 3. 验收标准
1. API 单元请求：`curl` 请求 `/data/order_flow_signals` 与 `/data/spx_gamma_signals`，带 `timeRange` 参数能精确过滤起止时间内的记录，且包含 5m 与 30m 所有信号。
2. 页面交互测试：按钮展示美观自然，浅色风格协调；点击激活后高亮，再次点击取消高亮。
3. 规则遵从：不自动打开浏览器测试（规则 5）；保持浅色 Light Theme（规则 12）。
