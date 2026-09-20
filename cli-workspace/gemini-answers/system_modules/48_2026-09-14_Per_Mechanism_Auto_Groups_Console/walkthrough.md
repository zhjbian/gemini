# 卖家系统：按触发机制分别设置自动开仓组数（组数控制台）验收报告

- **日期**：2026-09-14
- **模块**：Option Seller 自动开仓组数（逐机制 `groups_for()` + 页面「组数控制台」）
- **归档目录**：`48_2026-09-14_Per_Mechanism_Auto_Groups_Console`
- **技术栈**：Python 3.11 / Flask API + Jinja2（`bbt_data_web`，127.0.0.1:5005）/ `PyTools/option_seller/option_seller_manager.py` / MySQL `bb_trade`（**本轮零写入**）/ 规则手册五部分级 / headless Chrome 实渲染校验

---

## 1. 交付结果（结论先行）

| 需求 | 结果 |
|---|---|
| 把「单一全局自动开仓组数」改为**不同触发机制可不同组数** | ✅ 新增 `Config/option_seller_auto_groups.json` + 唯一取值入口 `groups_for(触发标签)`；7 个机制（含 ⑦ 执行层）逐行可配 |
| 设计 UI，可考虑新建设置控制台 | ✅ 页面顶部「**组数控制台**」按钮 → 与「Force Dry 触发」**同款弹窗**（浅色主题，条目卡片 + 底栏保存/关闭）；每机制一行：名称 + 中文名标签 + 代码标签 + 组数步进 + 当前活跃 + 说明 + 「继承默认/单独设置」标签 + 「↺ 还原继承」；另含全局默认行与口径页脚 |
| **删除头部原「全局默认组数」步进器**（用户追加指令） | ✅ 头部仅保留「组数控制台」一个入口；全局默认值的唯一设置处在弹窗内的「全局默认组数」行（避免同一旋钮两处入口）；`stepAutoGroups()` 与其 status 回填一并删除 |
| **头部改为纵向堆叠**（用户追加指令） | ✅ 控制区从「标题右侧」移到「标题下方」，仍分两行：① 品牌标题 → ② 状态与控制 → ③ 交易操作（纯 CSS，三处 `justify-content`/`align-items` 调整） |
| 不破坏既有行为 | ✅ 旧接口 `set_auto_groups` 保留（写 `default`，后端兼容入口、页面已无调用方），旧行为 `default=1` 下与改造前**完全一致** |
| 文档同步（规则定义维护） | ✅ 手册新增 **§3.1.4.1.7 组数控制（按触发机制分别设置）**，并更新 §3.1.4.1.6「组数」条目与交叉引用；HTML/MD 均标注「头部原「全局默认组数」步进器已删除」 |

## 2. 语义（唯一口径）

**开仓组数 = 该机制单次自动开仓的组数上限**；未「单独设置」的机制继承全局默认。

| 机制 | 本次开仓组数 |
|---|---|
| ①②④⑤⑥ | `groups_for(标签)`（该机制上限值本身） |
| ③ 平衡日边界 | `min(五维评分器分档, 通道硬顶 groups_cap, groups_for(标签))` ⇒ 控制台**只能收紧、不能放宽** |

- 标签先 `normalize_label()` 归一、再**前缀匹配**落机制（`AUTO_PM_BIG_TRADE_UT1_…` ⇒ ⑤）；未匹配 ⇒ 回落 `default`
- 取值 **1–5**（与 L0-E `GLOBAL_GROUP_CAP` 对齐）
- **不绕过任何 L0**：机制级 / 机制数 / 全局并发仍由 L0-C / L0-D / L0-E 把关（面板页脚显式标注 `机制级活跃 < 2 组、全局活跃 < 5 组`）
- 配置文件**只写显式项**：继承值不固化 ⇒「改全局默认」能真正带动未单独设置的机制

## 3. 改动清单

| 层 | 文件 | 关键改动 |
|---|---|---|
| 配置层 | `PyTools/option_seller/option_seller_manager.py` | `AUTO_GROUPS_CFG` / `AUTO_GROUPS_MIN=1` / `AUTO_GROUPS_MAX=5`、`clamp_auto_groups()`、`_read_auto_groups_raw()`、`load_auto_groups_config()`、`save_auto_groups_config()`（支持 `default` / `per_mechanism` / `null` 删除 / `clear_per_mechanism`） |
| 取值层 | 同上 | `groups_for(trigger_label, scorer_groups=None)`、`get_active_groups_by_mechanism()`、`_auto_groups_status_payload()` |
| 接线 | 同上 | `__init__` 载入配置（`self.auto_groups` 降级为兼容镜像）；`_open_from_engine` 由 `self.auto_groups` 改读 `groups_for(trigger_label)`；机制 ③ 的 `cap = min(groups_cap, groups_for(LABEL_BALANCED_DAY))` |
| 兼容 | 同上 | `set_auto_groups(n)` ⇒ 写 `default`；`status.auto_groups` 保留 |
| API | `bbt_data_web/data_app/bbt_option_seller.py` | 新增 `GET/POST /api/option_seller/auto_groups_config`；`POST /set_auto_groups` 回包补 `auto_groups_config` |
| 页面 | `bbt_data_web/templates/bbt_option_seller.html` | **头部布局改为纵向堆叠**（标题在上、控制区在下，控制区两行；`.header` / `.header-actions` / `.header-col-controls` / `.header-col-actions` 四处 CSS）；**头部删除原「全局默认组数」步进器**（连带 `stepAutoGroups()` 与 `autoGroupsVal` status 回填），仅保留「组数控制台」按钮（文案带默认值与单独设置项数）；`#autoGroupsModal` **弹窗**（与 Force Dry 同款 `.modal-overlay/.modal-card` 结构）+ `.agc-*` 浅色样式 + JS（`openAutoGroupsModal` / `closeAutoGroupsModal` / `handleAutoGroupsOverlayClick` / `loadAutoGroupsConsole` / `renderAutoGroupsConsole` / `agcUpdateHeaderState` / `stepAgcDefault` / `stepAgcMechanism` / `unsetAgcMechanism` / `resetAutoGroupsConsole` / `saveAutoGroupsConsole` / `syncAutoGroupsConsole`），并挂入 `fetchStatus` 的 status 同步 |
| API 补充 | `bbt_data_web/data_app/bbt_option_seller.py` | `GET /auto_groups_config` 回包新增 `meta`（与 `status.auto_groups_config` **同结构**，由模块级 `auto_groups_meta()` 生成）⇒ 弹窗打开即可独立渲染，不依赖 status 轮询时序 |
| 手册 | `gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html` | 新增 §3.1.4.1.7（锚点 `os-groups-ctrl`）、更新 §3.1.4.1.6 组数条、新增 §3.1.1.1 锚点 `os-l0-gates` 供交叉引用 |

## 4. 验证证据

### 4.1 配置语义（离线单测，Python 3.11）

```
A. default=2      -> 全部机制继承 2；文件只写 {"default":2,"per_mechanism":{}}
B. 5m=3           -> 文件 {"default":2,"per_mechanism":{"AUTO_5M_SYNTHESIS":3}}
C. default=4      -> 5m 保持 3，其余随默认升到 4
D. 5m=null        -> 5m 回到继承（4）
E. clear+default=1-> 全部回归 1，per_mechanism 清空
groups_for: 5m=1 / PM子场景标签(AUTO_PM_BIG_TRADE_UT1_…)=1 / QP=1 / 未知标签=1(default)
③ 只收紧：min(2, 控制台1)=1 · min(1, 控制台5)=1 · min(2, 控制台5)=2
clamp: 99->5 · -3->1 · 'x'->1
```

### 4.2 API 往返（真实 127.0.0.1:5005）

```
GET  /api/option_seller/auto_groups_config → success=true, limits={min:1,max:5},
     path=/Users/.../Config/option_seller_auto_groups.json
POST {"default":2,"per_mechanism":{"AUTO_5M_SYNTHESIS":3},"clear_per_mechanism":true}
     → config.default=2, 5m=3, 其余=2
     文件实际内容 = {"default":2,"per_mechanism":{"AUTO_5M_SYNTHESIS":3},"updated_at":"..."}
GET  /api/option_seller/status → auto_groups=2（兼容镜像）；
     auto_groups_config.mechanisms[0] = {label:AUTO_5M_SYNTHESIS, name:5分钟综合信号,
     groups:3, explicit:true, active:0, exec:false}；其余 explicit=false/groups=2
恢复：POST {"default":1,"per_mechanism":{},"clear_per_mechanism":true}
     → 文件 {"default":1,"per_mechanism":{}}，status explicit 计数 = 0
```

`POST` 回包亦带 `meta`（与 GET / status 同结构），使页面保存后**立即**刷新 explicit 标记与头部文案。

### 4.2.1 端到端 UI 流程（headless Chrome 真跑页面 JS）

在真实页面上注入脚本执行「打开弹窗 → 步进 5分钟综合信号 +1 → 全局默认 +1 → 保存 → 关闭 → 重开」：

```
保存后 title:  AGC_DONE default=2 draftExplicit={"AUTO_5M_SYNTHESIS":2} explicitRows=1
               header=组数控制台 (默认 2 组 · 单独设置 1 项)
关闭再打开:    reopenedDraft={"AUTO_5M_SYNTHESIS":2}   ← 关闭弃稿后按后端真值重建，显式项保留
配置文件:      {"default":2,"per_mechanism":{"AUTO_5M_SYNTHESIS":2}}
```

即：UI 改值 → 保存 → 落盘 → 重开弹窗，全链路一致；测试后已恢复 `default=1` / 无显式项。

### 4.3 页面实渲染（headless Chrome，独立 `--user-data-dir`，用后即删）

**按用户追加指令改为「与 Force Dry 触发同款弹窗」后重测**：以 `--virtual-time-budget=5000` 渲染并在 `load` 后调用 `openAutoGroupsModal()`，对渲染后 DOM 逐行断言，**7 行机制全部正确**：

| 机制 | 组数 | 当前活跃 | 标签 |
|---|---|---|---|
| 5分钟综合信号 | 1 | 活跃 0 组 | 继承默认 |
| QuantPivot边界反向 | 1 | 活跃 0 组 | 继承默认 |
| 平衡日边界 | 1 | 活跃 0 组 | 继承默认 · 受评分器约束 · 只收紧 |
| 趋势日极限终点 | 1 | 活跃 0 组 | 继承默认 |
| ES盘前大单开盘回调 | 1 | 活跃 0 组 | 继承默认 |
| 洗盘反转-双向 | 1 | 活跃 0 组 | 继承默认 |
| 自动条件单触发 | 1 | 活跃 0 组 | 继承默认 · 执行层 |

- 弹窗容器：`class="modal-overlay active" id="autoGroupsModal"`（与 Force Dry 弹窗同一套 `.modal-overlay/.modal-card/.modal-header/.modal-body/.modal-footer` 结构；浅色主题，白底卡片 + 浅蓝标题栏）
- 全局默认行：`全局默认组数 = 1` + 右侧「全机制活跃 0 组」
- 头部按钮文案：`组数控制台 (默认 1 组)`（显式项数按后端 `meta.explicit` 统计，非 `per_mechanism` 键数）
- 页脚：`口径：开仓组数 = 该机制单次自动开仓的组数上限；未「单独设置」的机制继承全局默认（当前 1 组）。③ 平衡日边界另受五维评分器分档与通道硬顶约束，只能收紧。并发仍受 L0 闸门把关：机制级活跃 < 2 组、全局活跃 < 5 组（本配置不绕过任何 L0）；已单独设置 0 项。 已与配置文件一致`
- `#agcSaveBtn` 在无改动时可点但置灰提示（`opacity` 0.6）；改动后高亮
- 渲染截图人工核对：弹窗居中、条目卡片圆角浅灰边、步进器右对齐、「继承默认 / 执行层 / 受评分器约束·只收紧」标签配色清晰；无深色元素

### 4.3.1 一次实现缺陷与修复（记录在案）

首版弹窗**打开后列表为空**：`renderAutoGroupsConsole()` 依赖 `status.auto_groups_config`（含机制中文名），而弹窗在 `load` 后立即打开时 `status` 尚未返回 ⇒ `mechs = []`。修复：**GET 接口自带 `meta`**（新增模块级 `auto_groups_meta()`，status 与 API 共用同一份结构，避免两份逻辑漂移），`loadAutoGroupsConsole()` 优先取 `res.meta`，活跃组数仍由 4 秒 status 轮询刷新。该修复同时消除了「必须等 status 才能打开控制台」的时序耦合。

### 4.3.2 头部「全局默认组数」删除后的复测（用户追加指令）

- DOM 断言：页面内 `id="autoGroupsVal"` 出现 **0 次**；`stepAutoGroups` 仅在注释中出现；头部保留 `组数控制台` 单一入口
- 弹窗复测：7 行机制完整渲染（含 2 项「单独设置」浅蓝高亮行与 `↺ 还原继承` 按钮）、全局默认行 `− 1 ＋` 与「全机制活跃 0 组」正常
- **真实使用验证**：复测时读到线上配置已被用户在控制台内实际修改并保存 ——
  `{"default":1,"per_mechanism":{"AUTO_QUANT_PIVOT_BOUNDARY":2,"AUTO_WASHOUT_REVERSAL":2}}`，
  弹窗头部随之显示 `组数控制台 (默认 1 组 · 单独设置 2 项)`、页脚「已单独设置 2 项」、两行高亮为「单独设置」——
  即 **UI→落盘→回填** 在生产页面上真实闭环（该配置为用户的生产设置，**未被测试改动**）。

### 4.3.3 头部布局改为纵向堆叠（用户追加指令）

用户要求：右上角的按钮**移到标题下方**（不是右侧），控制区**仍分两行**显示。改动（纯 CSS，无 JS）：

- `.header`：`display:flex` 由「左右分栏」改为 `flex-direction: column; align-items: stretch; gap: 10px`
- `.header-actions`：`align-items: flex-end` → `stretch`（两行各自占满宽度）
- `.header-col-controls` / `.header-col-actions`：保持 `justify-content: flex-end`（**两行按钮靠右对齐**，均保留 `flex-wrap: wrap`）

结果三行结构：**① 品牌标题**（OPTION SELLER LAB • BBT.AI / SPY 0DTE Vertical Credit Spread Engine，左对齐）→ **② 状态与控制**（右对齐：LIVE TRADING · 自动单检测 · Force Dry 触发 · 自动开仓策略 · 自动止盈模式 · 组数控制台）→ **③ 交易操作**（右对齐：手动开仓 · 设置条件开仓 · 一键全平 · 取消全部）。

复核：无任何 JS 依赖头部高度（`offsetHeight` / `--header-height` / `scroll-margin` 全无引用），故加高不影响滚动定位；实渲染截图核对三行左对齐、无换行错位。

### 4.4 回归与静态检查

| 检查 | 结果 |
|---|---|
| `py_compile`（manager / web app） | OK |
| 模板内联 JS `node --check` | 0 failure |
| `option_seller` 测试套件（逐个模块运行） | `conditional_order_trigger` / `force_dry_degrade` / `intraday_probe` / `journal_filter_catalog` / `l1_h1_breakeven_stop` / `qp_meta_parse` / `strike_anchor` 全 **OK** |
| 既存失败 | `test_live_resting_limit_order` 1 例（`get_order_status` 批处理断言，**与组数无关**，前序模块已记录为既存失败） |
| HTTP | `/bbt_option_seller` 200 · `/api/option_seller/status` 200 · `/api/option_seller/auto_groups_config` 200 |
| 业务表写入 | **0**（本轮无任何 DB 写操作；仅写配置文件） |
| 生产值 | 测试后已恢复 `default=1`、无显式项（与改造前逐机制行为一致） |
| 模板残留 | 旧面板标识 `agcPanel` / `toggleAutoGroupsConsole` 残留 **0**；**头部 stepper 标识 `autoGroupsVal` / `stepAutoGroups` 残留 0**（仅注释说明删除原因）；临时验证页 `static/_agc*_verify.html` 已删除 **0** |

### 4.5 代码审计（无旁路）

`grep self\.auto_groups` ⇒ 仅剩：`__init__` 载入、`get/set_auto_groups_config` 镜像同步、`set_auto_groups` 兼容入口、`status` 回包；**没有任何机制再直读全局值**。唯一开仓取值入口为 `_open_from_engine` 的 `groups_for(trigger_label)` 与机制 ③ 通道的 `min(groups_cap, groups_for(...))`。

## 5. 回滚

| 场景 | 操作 |
|---|---|
| 恢复「全部 1 组」旧行为 | `POST /api/option_seller/auto_groups_config {"default":1,"per_mechanism":{},"clear_per_mechanism":true}`，或直接删除 `Config/option_seller_auto_groups.json`（缺失即取缺省 1） |
| 代码回退 | 三文件术前副本 `/tmp/bbt_autogroups_backup_062623/`（`option_seller_manager.py` / `bbt_option_seller.py` / `bbt_option_seller.html`） |
| 页面还原 | 硬刷新即可（模板改动；Flask debug reloader 对 `.py` 生效，模板/静态需浏览器强刷） |

## 6. 遗留与后续建议

1. **未在实盘/纸面跑过一轮触发**：本轮验证覆盖「配置→API→status→页面渲染」全链路与取值函数；真实触发开仓路径（`_open_from_engine` 实际开多组）需在下一个交易日由 Force Dry 试运行观察日志中的 `groups=N` 字段确认。
2. **控制台未能显示「继承 vs 显式」的历史差异**：面板已用标签区分（继承默认 / 单独设置）与「↺ 还原继承」按钮，但配置文件中显式项与默认值相同时仍会标「单独设置」——语义正确（确为显式），如需自动收敛可后续加「清理与默认同值的显式项」动作。
3. **机制 ③ 的 `groups_cap` 仍在平衡日配置内**（`Config/option_seller_balanced_day.json`），与控制台形成「双重上限」：控制台只能收紧。若后续希望统一入口，可把 `groups_cap` 并入控制台并保留其数据结论说明。
4. 既存索引缺口（非本轮引入）：`bbt_trading_modules.html` 主表仅列到 44，45 / 46 / 47 仅有详细节而无表格行。
