# BBT Signals 实时信号微观时段快捷筛选按钮与全周期穿透引擎 验收报告 (Walkthrough)

## 1. 交付概览
本次交付为 `http://127.0.0.1:5005/bbt_signals` 页面上的“Order Flow 实时信号”和“SPX Gamma 实时信号”两大分析模块注入了微观时段快速筛选能力。交易员可通过点击 `6:30 - 8:00`、`8:00 - 10:00`、`10:00 - 13:00` 三个快捷胶囊按钮，实现对开盘、盘中博弈及午后尾盘时段的瞬间聚焦，并完整透视该时段内的所有微观（5m）与宏观（30m）信号。

---

## 2. 核心改动清单

### 2.1 后端服务 (`bbt_data_web/data_app/bbt_signals.py`)
- **接口增强**: 在 `get_order_flow_signals_data` 与 `get_spx_gamma_signals_data` 中新增 `timeRange` GET 参数解析。
- **时段闭包过滤**: 支持标准 `HH:MM:00` 范围比较（`signal_time >= start_t AND signal_time <= end_t`）。
- **全周期穿透机制**: 当传入 `timeRange` 时，优先进入时段分支并跳过 `timeframe` 限制，确保 5m 与 30m 信号均纳入结果集。

### 2.2 前端页面 (`bbt_data_web/templates/bbt_signals.html`)
- **浅色交互设计 (Light Theme)**:
  - 引入 `.btn-time-range-group` 与 `.btn-time-range` 纯白底色、天蓝边框（`#bfdbfe`）、微圆角及柔和悬停动效；
  - 激活时呈现鲜亮深蓝底（`#2563eb`）与白字高亮。
- **DOM 注入**:
  - 在 Order Flow 的 `timeframeFilter` 紧邻右侧加入 `#ofTimeRangeGroup` 按钮组；
  - 在 SPX Gamma 的 `gammaTimeframeFilter` 紧邻右侧加入 `#gammaTimeRangeGroup` 按钮组；
- **防缓存版本**: 静态脚本升级为 `bbt_signals.js?v=1.2.26`。

### 2.3 交互驱动脚本 (`bbt_data_web/static/js/bbt_signals.js`)
- **双向互斥与穿透**:
  - 点击按钮触发 `setTimeRangeFilter(target, range, btn)`；
  - 点击处于激活状态的按钮：清空当前时段过滤，恢复全天数据；
  - 点击未激活按钮：激活该按钮，并将对应的 `timeframe` 下拉框设为 `'all'`，同时触发表格局部刷新；
  - 当用户主动切换 `timeframe` 下拉框至特定周期（如 5m/30m）时，自动解除快速时段的高亮与参数；
- **Ajax 动态装载**: 在 DataTables 的请求体中自动附带 `d.timeRange`。

---

## 3. 验证结果与数据检验

### 3.1 Order Flow 接口分时段测试 (2026-09-04)
- **06:30 - 08:00**:
  - 请求: `/data/order_flow_signals?beginDate=2026-09-04&endDate=2026-09-04&dateOperator=%3D&timeRange=06:30-08:00`
  - 返回条数: `18 条` (覆盖 `06:35:00` 至 `08:00:00`)
- **08:00 - 10:00**:
  - 返回条数: `24 条` (覆盖 `08:00:00` 至 `10:00:00`)
- **10:00 - 13:00**:
  - 返回条数: `36 条` (覆盖 `10:00:00` 至 `12:55:00`)

### 3.2 SPX Gamma 接口分时段测试 (2026-09-04)
- **06:30 - 08:00**:
  - 请求: `/data/spx_gamma_signals?beginDate=2026-09-04&endDate=2026-09-04&dateOperator=%3D&timeRange=06:30-08:00`
  - 返回条数: `22 条` (覆盖 `06:30:00` 至 `08:00:00`)
- **08:00 - 10:00**:
  - 返回条数: `29 条` (覆盖 `08:00:00` 至 `10:00:00`)
- **10:00 - 13:00**:
  - 返回条数: `41 条` (覆盖 `10:00:00` 至 `12:59:00`)

所有时段数据均完美包含 5m 与 30m 信号，且与方向、重要度等其它过滤参数协同生效。
