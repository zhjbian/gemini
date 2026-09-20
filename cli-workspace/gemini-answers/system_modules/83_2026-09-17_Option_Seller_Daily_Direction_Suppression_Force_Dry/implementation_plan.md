# 期权卖家「当日方向抑制 → 自动降级 DRY-RUN 单」实施计划 (Plan)

- **日期**：2026-09-17（PT）
- **归属模块**：**M09. Option Seller 自动化交易引擎与开仓仲裁系统**（能力域 = 开仓仲裁 / 执行降级通道；与既有「Force Dry 触发」同源通道；交叉引用 **M10** —— 被抑制方向的信号仍由各触发机制产生，本改动不改机制判定）
- **触发场景**：用户在 `http://127.0.0.1:5005/bbt_option_seller` 提出 —— 「在页面顶部添加一个基于方向的抑制自动单的选项，某些天，我会选择，让自动单**绝对不开**空仓或多仓；如果某天某个方向被抑制，则开仓成 **DRY run 单**」。
- **性质**：**新能力（用户政策开关 ×1）＋ 复用既有降级通道（零新增券商路径）＋ 契约测试 15 项**
- **技术栈**：Python 3.11 · `PyTools/option_seller/option_seller_manager.py`（`open_trade()` 单一 choke point + `Force Dry` 同源通道）· Flask（`bbt_data_web/data_app/bbt_option_seller.py`）· 模板内联 JS（`bbt_option_seller.html`）· 外置 JSON 配置（`Config/option_seller_direction_suppress.json`）· unittest 契约测试 · 规则手册 HTML/MD（见 §8 判定）· `bbt_trading_modules.html` 模块页

---

## 1. 用户口径与语义定义

| 用户原话 | 落地语义 |
| :--- | :--- |
| 「基于**方向**的抑制自动单」 | 按**卖方方向**而非按触发机制 / 按品种：`BULLISH` = 多头仓（卖 Put 价差 Bull Put Spread）、`BEARISH` = 空头仓（卖 Call 价差 Bear Call Spread），两者可分别抑制 |
| 「让自动单**绝对不开**空仓或多仓」 | 命中方向的**所有开仓路径**（自动机制单 ①–⑧ / 自动条件单触发 / UI 扫描单 / 手动单）最终都经 `OptionSellerManager.open_trade()` —— 在这**唯一 choke point** 拦截，**绝不发出券商单** |
| 「则开仓成 **DRY run 单**」 | 不是「丢弃信号」，而是**降级为 DRY-RUN 单**：`is_dry_run=True` 落库、`order_id` 用 `DRY-` 前缀、无券商单号、无保护性止损单、计入 **Dry Run PnL**，`dry_reason = 'DIRECTION_SUPPRESSED'` |
| 「**某些天**，我会选择」 | 设定**仅当日有效**（配置 `date` = 生效日，PT 日期）；`date ≠ 今日` ⇒ **自动失效**（`effective=[]`、`expired=True`），配置内容保留、页面显式提示「已过期」——杜绝「昨天设的抑制今天还在悄悄生效」这类隐形状态 |
| 「页面顶部添加一个…选项」 | 页面 `<main>` 第一屏常驻**工具条**（浅色主题）：两个勾选框（抑制多头 / 抑制空头）+ 生效状态文字；勾选即保存（取消抑制在 LIVE 下需二次确认） |

**关键增量口径（用户未明说、由本次实现确定，已在页面与文档中显式声明）**

1. **不占实盘组数额度**：被抑制方向的 DRY 单**不计入** `get_active_auto_groups_count()`（L0-E 全局上限 + `has_active_auto_trades()` 的 2 组实盘闸门）、`get_active_groups_count(mechanism)`（L0-D 机制级）、`get_active_auto_trades_count()`、`get_active_groups_by_mechanism()`（控制台「活跃 n 组」）。理由：若计入，被抑制方向的纸面单会**占满额度**，导致**放行方向**也开不出实盘仓 —— 与「抑制一个方向、另一方向照常交易」的意图直接冲突。
2. **自身节流**：每个被抑制方向同时最多 `DIRECTION_SUPPRESS_DRY_CAP = 2` 组 DRY 单（与 2 组实盘额度同刻度）。理由：额度被排除后若无节流，同一方向可能被机制在一天内反复刷成纸面单。既有 DRY 单按止盈 / 止损 / 时间止损了结后可再记录。
3. **无豁免**：与 L0-F⑨ Gamma 掩码（纯手工单豁免）**不同**，方向抑制**不豁免任何路径**（用户原话「绝对不开」）。UI 扫描单 / 手动单在确认弹窗与预检提示中**明确告知**本次只会落 DRY-RUN 单，并指引「如需实盘请先在顶部取消该方向抑制」。
4. **不新增旁路**：抑制走的是与「Force Dry 触发」**完全相同**的既有降级链路（`candidate['force_dry_run']=True`），因此在引擎暂停（`is_enabled=False`）、数据降级禁开仓（L0-A③）、L0-F⑨ 方向掩码、组数闸门上的行为与 Force Dry **逐条一致**（抑制只是在这些闸门之后、在组数闸门之前追加一个降级理由）。

---

## 2. 为什么放在 `open_trade()`（单一 choke point）

`open_trade()` 是系统内**唯一**的开仓入口（`_open_mechanisms → _open_from_engine`、条件单触发、UI 扫描、手动开仓全部经此），并且它已经承载了「Force Dry 降级」「L0-A③ 禁开仓」「L0-F⑨ 方向掩码」「2 组并发闸门」「$0.10 权利金下限」等全部仲裁。

代码检索确认：真实券商下单调用 `BBTOS.place_vertical_credit_spread(...)` 在 `option_seller_manager.py` 内**仅 1 处**（`_open_single_contract`），而 `_open_single_contract` 仅由 `_open_tranche_with_fallback` 调用，后者仅由 `open_trade` 调用 ⇒ **改一处即覆盖全部路径**（含跨进程的条件单触发侧）。

**双层兜底**：`open_trade()` 置位 + `_open_single_contract()` 入口再复核一次（`apply_direction_suppression` 幂等、无副作用），确保任何（含测试 / 直连的）调用都不会在抑制方向发出真实券商单。

---

## 3. 判定与生效期实现

```python
# PyTools/option_seller/option_seller_manager.py
DIRECTION_SUPPRESS_CFG = ".../Config/option_seller_direction_suppress.json"
DIRECTION_SUPPRESS_CHOICES = ["BULLISH", "BEARISH"]   # 唯一权威（页面不自建副本）
DIRECTION_SUPPRESS_DRY_CAP = 2                        # 每方向同时最多 2 组 DRY 单

def load_direction_suppress() -> dict:
    """⇒ {today, date, suppress(已存), effective(今日生效), expired, updated_at}"""

def save_direction_suppress(items, date_str=None) -> dict:
    """归一 + 去重 + 剔除未知方向；把 date 盖为生效日（缺省 = 今日）"""

def suppressed_directions() -> set          # 今日生效集（隔日 ⇒ 空集）
def direction_suppressed(direction) -> bool # 别名归一后判定（'bull'/'多'/'LONG' ⇒ BULLISH）
```

配置文件形态（外置、可人读、可回滚）：

```json
{
  "date": "2026-09-17",
  "suppress": ["BEARISH"],
  "updated_at": "2026-09-17 06:46:45"
}
```

**方向由 `spread_type` 归一**（复用既有权威 `_spread_direction_of`）：`BULL*` ⇒ `BULLISH`；`BEAR*` ⇒ `BEARISH`；不可识别 ⇒ `None`（fail-open，不影响既有路径）。

---

## 4. 改动清单与关键代码点

### 4.1 执行层（`PyTools/option_seller/option_seller_manager.py`）

| 位置 | 改动 |
| :--- | :--- |
| 模块常量/函数区（`trigger_force_dry` 之后） | 新增 `DIRECTION_SUPPRESS_CFG` / `DIRECTION_SUPPRESS_CHOICES` / `DIRECTION_SUPPRESS_DRY_CAP` / `DIRECTION_SUPPRESS_CATALOG` 与 `normalize_suppress_direction` / `direction_suppress_date` / `load_direction_suppress` / `save_direction_suppress` / `suppressed_directions` / `direction_suppressed` / `direction_suppress_snapshot` / `direction_suppress_catalog` |
| 类内辅助 | 新增 `_entry_evidence_of` / `_ev_dir_suppressed` / `_group_key_of` / `count_active_suppressed_dry_groups(direction)` / `apply_direction_suppression(candidate, entry_evidence)` |
| `get_active_auto_groups_count()` | 跳过方向抑制单（L0-E / 2 组实盘闸门不占额度） |
| `get_active_auto_trades_count()` | 同上（腿数口径一致） |
| `get_active_groups_count(mechanism)` | 同上（L0-D 机制级不占） |
| `get_active_groups_by_mechanism()` | 同上（控制台「活跃 n 组」= 真·实盘活跃组数） |
| `open_trade()` | ① 在 `is_manual` 之后调用 `apply_direction_suppression`（置 `force_dry_run` + `direction_suppressed*` 留痕 + WARNING 日志）；② 组数闸门处新增每方向 `DIRECTION_SUPPRESS_DRY_CAP` 节流 |
| `_open_single_contract()` | ① 入口再复核（兜底，绝不发券商）；② 降级日志区分 `[方向抑制·当日]` 与 `[FORCE DRY 触发]`；③ `dry_reason` 归因新增最高优先级 `DIRECTION_SUPPRESSED` |
| `get_status_summary()` | 新增 `direction_suppress`（今日生效 / 已存 / 是否过期 / choices / catalog / dry_cap）—— 页面唯一数据源 |

### 4.2 Web 层（`bbt_data_web/data_app/bbt_option_seller.py`）

| 位置 | 改动 |
| :--- | :--- |
| 新端点 | `GET/POST /api/option_seller/direction_suppress`（GET 读、POST 保存并回传；POST 受既有 `_require_write_auth()` 保护；未知方向剔除并记 WARNING） |
| `scan_now`（`execute=true` 分支） | 开仓前预检方向抑制：命中则写 `evidence['direction_suppressed*']` 并记 `MANUAL_ORDER_DIRECTION_SUPPRESSED`；响应新增 `direction_suppressed` / `is_dry_run`；被 cap 拦下时返回可读原因（不再误报「系统处于暂停状态」） |
| `scan_now`（询价分支） | 响应新增 `direction_suppressed_warning`（预检提示，只提示不拦截） |

### 4.3 前端（`bbt_data_web/templates/bbt_option_seller.html`）

| 位置 | 改动 |
| :--- | :--- |
| `<main>` 第一屏 | 新增常驻工具条 `#dirSuppressBar`（标题 + 说明 + 两个方向勾选框 + 生效状态：生效中 / 已过期 / 未设抑制） |
| `<style>` | 新增 `.dir-suppress-bar` 系列样式（**浅色主题**，生效中为浅红强调；`accent-color:#dc2626`） |
| JS | `dirSuppressRender / dirSuppressApply / dirSuppressSyncFromStatus / saveDirectionSuppress / onDirectionSuppressChange`；4 秒轮询同步；保存中不覆盖本地勾选；**取消抑制**在 LIVE 下二次确认；`fetchStatus` 内接线 `dirSuppressSyncFromStatus(data)` |
| 归因文案 | `_dryReasonMap` 新增 `DIRECTION_SUPPRESSED`（复制持仓调试信息可见） |
| 手动 / UI 扫描弹窗 | 询价即显示「方向抑制（当日有效）预警」黄色提示；确认弹窗正文追加「本次只落 DRY-RUN 单、绝不发券商」；`executed` 且命中抑制时成功提示改写为「已记录为 DRY-RUN 单（未发券商）」；被 cap 拦下时给出专属提示 |

### 4.4 测试

新增 `PyTools/option_seller/test_direction_suppress.py`（**15 项**，继承 `test_isolation.GuardedTestCase`，配置路径 patch 到临时文件 —— 绝不触碰真实 Config）：

| 组 | 覆盖 |
| :--- | :--- |
| ① 配置 | 别名归一 / 默认无抑制 / 保存盖章今日 + 剔除未知 + 去重 / **隔日自动失效且内容保留** / 主动清空 ≠ 过期 / snapshot 载荷字段 |
| ② 单笔决策 | 命中 ⇒ `force_dry_run=True` + 留痕三字段（且不丢既有 trigger）；未命中 ⇒ **原样返回同一对象**（零副作用）；无抑制 ⇒ 零副作用 |
| ③ LIVE 端到端 | 抑制方向**券商调用 0 次**且落 `DRY-` 前缀双批次 `is_dry_run=True` + `dry_reason=DIRECTION_SUPPRESSED`；**放行方向照常实盘下单（2 次）**；双向抑制 ⇒ 双向皆 DRY；**cap 节流**（满 2 组后不再记录且仍不发券商）；**不占额度**（对照普通 DRY 单仍占额度）；`entry_evidence` 为 JSON 字符串的 DB 行同样被识别 |

---

## 5. 验证方法

```bash
# 1) 契约测试（15 项）
/usr/local/bin/python3 PyTools/option_seller/test_direction_suppress.py

# 2) 既有回归（本改动触及 Force Dry / L0-F / 组数口径）
/usr/local/bin/python3 PyTools/option_seller/test_force_dry_degrade.py
/usr/local/bin/python3 PyTools/option_seller/test_l0_gamma_one_sided_gate.py
/usr/local/bin/python3 PyTools/option_seller/test_journal_filter_catalog.py

# 3) 活体只读（Flask 自动重载后）
curl -s "http://127.0.0.1:5005/api/option_seller/direction_suppress" | python3 -m json.tool
curl -s "http://127.0.0.1:5005/api/option_seller/status" | python3 -c "import json,sys;print(json.load(sys.stdin)['direction_suppress'])"

# 4) 写入往返（验证后务必清空：POST {"suppress": []} 或删除配置文件即回到"未设抑制"）
curl -s -X POST "http://127.0.0.1:5005/api/option_seller/direction_suppress" \
     -H 'Content-Type: application/json' -d '{"suppress":["BEARISH"]}'
```

页面三态（headless Chrome DOM 校验，`--user-data-dir` 独立 + 按 PID 精确回收）：生效中 / 已过期（昨日设定自动失效、勾选不生效）/ 未设抑制。

---

## 6. 回滚方式

```bash
# 方式一（推荐，零代码 diff）：清空抑制设定
curl -s -X POST "http://127.0.0.1:5005/api/option_seller/direction_suppress" \
     -H 'Content-Type: application/json' -d '{"suppress":[]}'
rm -f /Users/zhijiebian/Documents/MyDoc/Finance/Current/Config/option_seller_direction_suppress.json

# 方式二（回到本次改动前）：撤销 3 个文件 + 1 个新测试（PyTools 为独立 git 仓库，按 git 状态回退）
#   PyTools/option_seller/option_seller_manager.py
#   bbt_data_web/data_app/bbt_option_seller.py
#   bbt_data_web/templates/bbt_option_seller.html
#   PyTools/option_seller/test_direction_suppress.py（新增，可删）
```

不变式：即使代码保留、抑制设定为空，行为与改动前**完全一致**（`apply_direction_suppression` 未命中 ⇒ 原样返回、零副作用）。

---

## 7. 不影响面

- **不改任何判定层**：`option_seller_engine` / `auto_mechanisms`（L0 闸门、机制求值、掩码）**零改动** —— 抑制只作用于「开仓执行」这一层。
- **不改 Force Dry 语义**：`trigger_force_dry()` 与 `force_dry_trigger` 留痕保持不变；两个通道可叠加（命中任一即 DRY）。
- **不改既有 DRY 单归因**：`dry_reason` 既有四条路径语义不变，仅新增最高优先级的 `DIRECTION_SUPPRESSED`。
- **不改券商交互**：抑制路径**不产生任何券商调用**（无下单、无撤单、无挂止盈/止损单）。
- **DB 结构**：零 DDL，`is_dry_run` / `entry_evidence` 既有列承载新标记。

---

## 8. 规则手册（规则 11）是否需记入 —— 判定与理由

本次**未**写入 `/Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html|.md`，理由按规则 (11) 原文：

> 只有规则是用来提供**趋势判断**的决策或**交易的决策**时才需要记入文档；**UI 展示规范、字段定义、格式表示法等工程实现方式**不需要记入。

方向抑制是**用户临场设定的操作性政策开关**（每日可选、不参与任何趋势/方向推断，系统不据此产生任何方向判断），其本体是「执行层降级通道 + 页面控件 + 配置落盘」，属工程实现与运维控制，而非系统内置的决策性规则。

**但**其**副作用口径**（「被抑制方向的 DRY 单不占实盘组数额度」「每方向最多 2 组 DRY 单」）与既有 **L0-D / L0-E 组数闸门**的解释直接相关 —— 若用户认为这已构成「组数闸门口径的一条新规则」，可在手册 §3.1.1.1「L0-D / L0-E」处补一段；**等用户确认后再落笔**（不擅自扩写决策规则手册）。
