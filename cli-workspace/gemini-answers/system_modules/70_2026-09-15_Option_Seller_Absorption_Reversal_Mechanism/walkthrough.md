# 验收报告 (Walkthrough) · 卖家系统机制 ⑦「吸收反转-双向」

- **日期**：2026-09-15
- **对应 Plan**：同目录 `implementation_plan.md`
- **结论**：**已交付并默认关闭**。判定器与机制两侧契约测试 29 例全绿；既有卖家系统测试回归通过；
  两个对照案例在系统内复算结果与 skill 侧完全一致。

---

## 1. 交付物

### 1.1 新增

| 文件 | 行数/大小 | 说明 |
|---|---|---|
| `PyTools/order_flow_analysis/absorption_reversal.py` | 514 行 | PAIR v1.1 判定器（纯函数 + 滚动缓冲 + 契约输出） |
| `PyTools/order_flow_analysis/absorption_reversal_templates_v1.json` | 6.2 KB | A/B 锚点模板与判据清单 |
| `PyTools/option_seller/test_absorption_reversal_module.py` | 175 行 | 判定器契约测试（13 例） |
| `PyTools/option_seller/test_mech_absorption_reversal.py` | 218 行 | 机制契约测试（16 例） |

### 1.2 修改

| 文件 | 改动摘要 |
|---|---|
| `PyTools/option_seller/auto_mechanisms.py` | 标签 `AUTO_ABSORPTION_REVERSAL` + 中文名「吸收反转-双向」+ 口径说明；注册 ⑦（DIRECT）、执行层顺延 ⑧；Force Dry 清单 6→7 项；新增默认关闭开关 `absorption_reversal_enabled()` |
| `PyTools/option_seller/option_seller_manager.py` | 新增 `_mech_absorption_reversal`（只读契约 → 校验 → `_open_from_engine`） |
| `PyTools/order_flow_analysis/order_flow_sentinel.py` | 周期内刷新滚动缓冲并写入 `of_eval_metrics['absorption_reversal']`；异常时写 `available=False`（fail-closed） |
| `bbt_data_web/templates/bbt_option_seller.html` | 新增 `.badge-subtype-absorption`（浅色：`#ecfdf5`/`#047857`）+ 徽标类与图标（`fa-layer-group`）映射 |
| `PyTools/option_seller/test_force_dry_degrade.py` | 漂移守卫同步（CANON 增行；Force Dry 计数 6→7） |
| `PyTools/option_seller/test_journal_filter_catalog.py` | 目录清单同步（MECH_ORDER 增行、JS 分类用例增行、目录 9→10、选项 11→12） |
| `system_modules/gemini_answer-trading_system_rules_manual-*.{md,html}` | **规则手册**：新增 **§3.1.8 吸收反转-双向机制**（含 3.1.8.1 判据 9 维表与排除维度表 / 3.1.8.2 机制契约 / 3.1.8.3 样本纪律），原 §3.1.8 条件单顺延 **§3.1.9**（锚点 `os-rule-13` 不变），新章节锚点 `os-rule-16`；命名表、§3.1.1.2 顺序表、§3.1.1.4 概览表、§3.1.1.5 契约表、导航 TOC 与 L0-F 适用范围（①–⑥→①–⑦）全部同步 |

### 1.3 备份（可回滚）

```
/tmp/backup_auto_mechanisms.py.235242
/tmp/backup_option_seller_manager.py.235324
/tmp/backup_order_flow_sentinel.py.235546
/tmp/backup_bbt_option_seller.html.000705
/tmp/backup_test_force_dry_degrade.py.235602
/tmp/backup_test_journal_filter_catalog.py.000654
```

---

## 2. 判定器验收（`test_absorption_reversal_module.py` 13/13 全绿）

| 用例 | 结果 |
|---|---|
| A 锚点（09-14 07:54） | 门槛 **PASS**、得分 **+9/9**、A 型、`OPEN_BULLISH` ✓ |
| B 锚点（09-15 07:53） | 门槛 **BLOCK**（±15 分钟累计 Delta −2,566）、不参与 ✓ |
| 09-14 07:19 / 07:24（结构像 A 但净流反向） | 门槛 BLOCK，动作 NONE（投票确实仍 ≥+7，正是必须设门槛的原因） ✓ |
| 09-14 全天 | 仅 07:40、07:54 产出 `OPEN_BULLISH`（后验 +31.5 / +42.5） ✓ |
| 09-15 全天 11 个候选 | 无一个 A 型、无一个开仓动作 ✓ |
| 实盘半窗（数据到 t+46 分钟） | `next45` 未满窗 ⇒ 自动降为 **8 维/门槛 6**，仍判 A 型 ✓ |
| 实盘满窗（数据到 t+96 分钟） | 恢复 **9 维**，得分 +9 ✓ |
| 无盘口 | 降为 **6 维/门槛 4**，仍判 A 型 ✓ |
| 镜像（高点派发） | 方向恒 `BEARISH`；未过门槛不得开仓 ✓ |
| 契约结构 | 15 个字段齐备；空状态 `available=False` + reason ✓ |

**系统内 vs skill 侧一致性**（同一对案例，各自独立实现）：

| 案例 | skill 侧（baseline_pair.py） | 系统侧（absorption_reversal.py） |
|---|---|---|
| 09-14 07:54 | A 型 +9/9 → OPEN_BULLISH | A 型 +9/9 → OPEN_BULLISH ✓ |
| 09-14 07:40 | A 型 +7/9 → OPEN_BULLISH | A 型 +7/9 → OPEN_BULLISH ✓ |
| 09-15 全部候选 | 无一 A 型 | 无一 A 型 ✓ |

---

## 3. 机制验收（`test_mech_absorption_reversal.py` 16/16 全绿）

| 用例 | 断言 | 结果 |
|---|---|---|
| 默认关闭 | `absorption_reversal_enabled() is False` | ✓ |
| **关闭态给 A 型契约** | 必须 MISS 且**开仓路径零调用**（`recorder.calls == []`） | ✓ |
| 开关取值 | `1/true/YES/on` ⇒ True；`0/off/no/空` ⇒ False | ✓ |
| 契约缺失（三态） | fail-closed，零调用 | ✓ |
| 契约 `available=False` | MISS 且理由回传 OF 侧原因 | ✓ |
| A 型（低点吸收） | `OPENED`；direction=`BULLISH`、profile=`BALANCED`、trigger=`AUTO_ABSORPTION_REVERSAL`、理由含「吸收反转」、`debug_info.ar_score=9` | ✓ |
| A 型（镜像高点） | direction=`BEARISH`、理由含「高点派发」 | ✓ |
| 门槛不过 / 不可判 | MISS「判定不开仓」，零调用 | ✓ |
| 方向被 L0 掩码 | MISS 含「掩码」，零调用 | ✓ |
| 无合格 spread | MISS（`ids` 为空时不返回 OPENED） | ✓ |
| 盘口降级仍可开仓 | OPENED，理由标注「无盘口」 | ✓ |
| 注册表 | ⑦ 在册/DIRECT/evaluator 存在/非布防型；⑧ 顺延且 EXEC | ✓ |
| 命名唯一权威 | 中文名「吸收反转-双向」、在 Force Dry 清单、归一正确 | ✓ |

---

## 4. 回归验收

| 测试文件 | 结果 |
|---|---|
| `test_force_dry_degrade.py`（含机制中文名/注册表/Force Dry 漂移守卫） | **18/18 OK** |
| `test_journal_filter_catalog.py`（流水账本目录与前端徽标契约） | **11/11 OK** |
| `test_conditional_order_trigger_3131.py` | 9/9 OK |
| 其余 22 个 option_seller 测试文件（含 balanced_day / QP 边界 / gamma 掩码 / 条件单） | 全部 OK |

**两处非本次引入的既有失败（如实记录）**：

1. `test_live_resting_limit_order.py` — `AssertionError: Expected 'get_order_status' to not have been called. Called 1 times.`
   该测试针对券商挂单状态轮询，代码路径与机制注册表无关；本次改动为**纯增量**（新增方法/常量/映射），
   且新机制默认关闭、不参与任何既有路径。
2. `test_quant_pivot_option_seller.py` — 以该 cwd 直接运行时 `ModuleNotFoundError: No module named 'PyTools'`（导入路径问题，与本次改动无关）。

---

## 5. 运行态冒烟

```
机制清单（序号/标签/类型/中文名）:
  1 AUTO_5M_SYNTHESIS            DIRECT 5分钟综合信号
  2 AUTO_QUANT_PIVOT_BOUNDARY    ARM    QuantPivot边界反向
  3 AUTO_BALANCED_DAY_BOUNDARY   DIRECT 平衡日边界
  4 AUTO_TREND_DAY_EXTREME       ARM    趋势日极限终点
  5 AUTO_PM_BIG_TRADE_PULLBACK   DIRECT ES盘前大单开盘回调
  6 AUTO_WASHOUT_REVERSAL        DIRECT 洗盘反转-双向
  7 AUTO_ABSORPTION_REVERSAL     DIRECT 吸收反转-双向     ← 新增
  8 AUTO_CONDITIONAL_ORDER       EXEC   自动条件单触发      ← 顺延
Force Dry 清单: ①–⑦（7 项）
启用开关默认值: False
manager 导入 OK（无导入期副作用）
```

滚动缓冲冒烟（09-14，数据截至 09:30）：`bars=211 / dom=195 分钟`，`latest_decision` 正确返回 07:54 候选并判 A 型。

---

## 6. 启用与回滚

**启用（真实开仓）**

```bash
export OS_AUTO_ABSORPTION_REVERSAL=1     # 卖家系统进程需带上该变量
```

**试运行（不真实下单）**：在页面「Force Dry 触发」多选中勾选「吸收反转-双向」，
命中的单会走既有降级路径（`DRY-` 前缀、`is_dry_run=True`、计入 Dry Run PnL）。

**回滚**

1. 立即止血：`unset OS_AUTO_ABSORPTION_REVERSAL`（机制回到关闭态，零自动单）。
2. 代码回滚：还原 §1.3 的 6 个备份文件；删除 4 个新增文件。
3. 数据库无需迁移（本机制不新增表、不新增列）。

---

## 7. 遗留与后续建议

1. **规则手册已更新**（2026-09-15 用户反馈「规则手册里没找到吸收反转-双向」后补做，见 §1.2 末行）：
   §3.1.8 为吸收反转-双向机制、条件单顺延 §3.1.9；命名表/顺序表/概览表/契约表/L0-F 范围同步。
   备份：`gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.{md,html}.{bak,bbt-bak}-20260916_001925`；
   该目录为 git 仓库，亦可 `git checkout -- <手册文件>` 回滚。
2. **样本扩充**：每出现新的「同形态相反结局」配对（多空皆可），追加进
   `absorption_reversal_templates_v1.json` 的锚点集并重跑 `--selfcheck` 式回归；
   在积累到 ≥10 对之前，不建议把该机制用于真实下单。
3. **盘口覆盖**：DOM 分钟画像依赖 06:30–11:00 的原始文件覆盖；`2026-09-01/09-02/09-13` 等日缺该时段数据时自动降级为 6 维投票。
4. **入场时点**：当前为 t+45 分钟右侧确认；若需要更早的「预判层」入口，可在积累样本后，
   把硬门槛+前 4 维（不含 DOM/VWAP/next45）单独做成 ARM 型布防机制（本次未做，避免无样本支撑的早触发）。
