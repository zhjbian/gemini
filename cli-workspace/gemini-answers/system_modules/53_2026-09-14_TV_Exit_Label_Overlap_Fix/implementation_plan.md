# 卖家系统：TradingView 出场标签重叠修复（同组双腿同时出场）实施计划

- **日期**：2026-09-14
- **模块**：期权卖家「生成TradingView指标」Pine 生成器（`PyTools/trading_view/tv_option_seller_trades.py`）
- **归档目录**：`53_2026-09-14_TV_Exit_Label_Overlap_Fix`
- **技术栈**：Python 3.11 / Pine Script v5（生成的指标）/ `POST /api/option_seller/generate_tv_script`（未改接口）/ 夹具 + 真实数据不变量契约测试

---

## 1. 背景与问题（用户报障 + 截图）

用户报障：**「止损的两个 label overlap 了」**。截图（SPY 0DTE，G1 = 08:41 开仓的 BEAR CALL 764/766）显示两条标签压在一起：

```
[ [G1-T2] 止损 -$14.00 ]
 08:44 | 762.09
• G1-T1: -$14.00
 08:44 | 762.09
```

对应两笔流水（用户贴出）：

| 序列 | 腿 | 开仓 | 平仓 | 平仓价 | 盈亏 | 状态 |
|---|---|---|---|---|---|---|
| #5 | 批次1 | 08:41:50 | **08:44:16** | 0.26 | −$14.00 | CLOSED_STOP_LOSS |
| #6 | 批次2 | 08:41:52 | **08:44:18** | 0.26 | −$14.00 | CLOSED_STOP_LOSS |

⇒ 同一订单组双腿**相差 2 秒、同价出场**。

### 根因（两层，缺一不可）

| 层 | 缺陷 |
|---|---|
| **Pine 侧** | 去重数组 `exitTimesDrawn` 按 `close_time_ms` **毫秒精确相等**去重；两腿相差 2000 ms ⇒ `array.includes` 不命中 ⇒ **两个标签都被画** |
| **后端侧** | exit cluster 的**代表**挂「合并标签」（`[G1-T1+T2] 止损 -$28.00` + 两行明细），**其余成员又挂「个体标签」**（原注释写 fallback，但聚类判据本身就是「≤120 s 且同 tranche」或「≤60 s 且 Δspot ≤0.30」）⇒ 两者必然落在同一视觉位置 ✗ |

## 2. 实施目标

| 目标 | 交付 |
|---|---|
| 同一事件只出一个出场标签 | 后端：**只有 cluster 代表挂标签**，其余成员 `label_exit=''`（与「开仓」侧同一约定） |
| Pine 侧去重口径正确 | 把「毫秒精确」改为**容差判据**：Δt ≤ 60 s **且** Δ价 ≤ 0.12 ⇒ 视为重复，跳过 |
| 近邻不压字且不丢信息 | 对**近邻**标签（Δt ≤ 5 min 且 Δ价 ≤ 0.60，但非重复）做 **y 阶梯错位 ±0.45 点**，两个标签都保留可读 |
| **不矫枉过正**（双向覆盖） | 分次出场（如 G9 的 T1 09:56 止盈 / T2 10:41 止盈）必须**各自保留**标签 |
| 防回归 | 新增 `PyTools/option_seller/test_tv_exit_label_overlap.py`（9 条：夹具双向 + Pine 契约 + 真实数据不变量） |

## 3. 关键设计与依据

### 3.1 为什么「后端只留代表标签」是正解（而不是在 Pine 里叠加偏移）

聚类判据已经把「同一事件的出场」归到一组：代表标签**本身已含每条腿的明细**（`• G1-T1: -$14.00` / `• G1-T2: -$14.00`）⇒ 成员标签是**冗余**，任何偏移都只是把冗余摆到别处。因此与**开仓侧**保持一致：一组一个标签（`group_leads` 只给 `t_idx==0` 挂 `label_entry`，其余为空）。

### 3.2 Pine 容差判据与近邻错位

```pine
bool exitDup = false
int  exitNear = 0
int  drawnN = array.size(exitTimesDrawn)
if drawnN > 0
    for k = 0 to drawnN - 1
        float dtMs = math.abs(tr.close_time_ms - array.get(exitTimesDrawn, k))
        float dPx  = math.abs(tr.close_spot     - array.get(exitSpotsDrawn, k))
        if dtMs <= 60000 and dPx <= 0.12
            exitDup := true
            break
        if dtMs <= 300000 and dPx <= 0.60
            exitNear += 1
if not exitDup
    array.push(exitTimesDrawn, tr.close_time_ms)
    array.push(exitSpotsDrawn, tr.close_spot)
    float yNudge = exitNear == 0 ? 0.0 : 0.45 * math.ceil(exitNear / 2.0) * (exitNear % 2 == 1 ? 1 : -1)
    label.new(x=tr.close_time_ms, y=tr.close_spot + yNudge, …)
```

- 新增 `exitSpotsDrawn`（`array.new<float>()`）与时间数组**同步 push**，长度为容差判据服务；
- `if drawnN > 0` 保证空数组不进入 `for`（避免 `0 to -1` 的边界不确定性）；
- **未知/新场景仍安全**：判据只看「时间 + 价位」，不依赖组号 ⇒ 跨组同时出场（如 G4–G8 那次 09:18 集体止损）同样只留一个合并标签。

### 3.3 为什么保留「近邻错位」而不是直接跳过

跨组、跨批次但**点位相近**的两次出场（判据窗 5 min / 0.60 点）不构成「同一事件」（金额与原因可能不同），直接跳过会**丢信息**；错位 ±0.45 点后两者都完整可读 ✓。

## 4. 改动清单

| # | 文件 | 位置 | 改动 |
|---|---|---|---|
| 1 | `PyTools/trading_view/tv_option_seller_trades.py` | exit cluster 标签赋值（`cluster[0]['label_exit'] = cluster_text` 之后） | 成员标签由「个体标签」改为 `''`（附根因注释） |
| 2 | 同上 | Pine 类型定义之后 | 新增 `var exitSpotsDrawn = array.new<float>()` |
| 3 | 同上 | `if barstate.islast` 初始化段 | 新增 `array.clear(exitSpotsDrawn)` |
| 4 | 同上 | 出场标签绘制段 | 旧的「毫秒精确」去重 → **容差去重 + 近邻错位**（`yNudge`） |
| 5 | `PyTools/option_seller/test_tv_exit_label_overlap.py` | 新增 | 9 条契约测试 |
| 6 | 归档 | 本目录 | 实施计划 / 验收报告（md + html）/ `revert_module_53.py`（可复现回退） |

## 5. 验收口径

| 层 | 手段 | 通过标准 |
|---|---|---|
| 语法 | `py_compile` | 通过 |
| 夹具行为（双向） | 同组双腿「同时出场」（Δ2 s / 同价） | **只留 1 个**出场标签，且为**合并**标签（含 T1+T2 明细） |
| 夹具行为（反向） | 同组双腿「分次出场」（Δ45 min） | **保留 2 个**标签（T1 / T2 各自） |
| 夹具行为（不变） | 开仓侧 | 仍为「一组一个标签」 |
| Pine 产物契约 | `test_tv_exit_label_overlap.py` | 含 `exitSpotsDrawn` / `dtMs <= 60000 and dPx <= 0.12` / `dtMs <= 300000 and dPx <= 0.60` / `+ yNudge`；**不含** `array.includes(exitTimesDrawn, tr.close_time_ms)` |
| 真实数据不变量 | 2026-09-14 全量 | 不存在「两条都带出场标签且 Δt ≤ 60 s 且 Δ价 ≤ 0.12」；止损标签两两不重合 |
| 端到端 | `POST /api/option_seller/generate_tv_script`（`trade_ids=[238,239]`） | 238 带合并标签、**239 空**（用户报障那一组） |
| 无回归 | 账本三套件 | 8/8 · 9/9 · 11/11 通过 |

## 6. 风险与回滚

| 项 | 说明 |
|---|---|
| 风险 | 后端只留合并标签 ⇒ 极端情况下（cluster 跨多组，如 G4–G8）单个标签行数变多；已由「明细逐行列出」覆盖，且 `max_labels_count=500` 充裕 |
| Pine 语法 | 新增仅用 v5 既有构造（`for` / `break` / `array.get` / `math.abs` / `math.ceil` / 三元）；`if drawnN > 0` 规避空数组边界；本地无 Pine 编译器 ⇒ 以「产物逐行复核 + 纯构造白名单」控制风险 |
| 回滚 | `revert_module_53.py`（`--dry-run` 先看锚点；实跑先留 `.bak` 再逐字面量反向替换，最后 `py_compile` 校验；已在副本实测「残留标识 0 / 编译通过」）；另留快照 `PyTools/trading_view/tv_option_seller_trades.py.bak-20260914_195934` |
| 生效方式 | 页面「生成TradingView指标」按钮即时生效（无缓存）；已生成的旧 Pine 需重新生成并替换 TV 上的指标 |
