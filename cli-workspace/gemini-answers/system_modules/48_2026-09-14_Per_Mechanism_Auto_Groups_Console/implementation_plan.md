# 卖家系统：按触发机制分别设置自动开仓组数（组数控制台）实施计划

- **日期**：2026-09-14
- **模块**：Option Seller 自动开仓组数（`OptionSellerManager.auto_groups` → 逐机制 `groups_for()`）+ 页面「组数控制台」
- **归档目录**：`48_2026-09-14_Per_Mechanism_Auto_Groups_Console`
- **技术栈**：Python 3.11 / Flask API + Jinja2（`bbt_data_web`）/ `PyTools/option_seller/option_seller_manager.py` / MySQL `bb_trade`（只读，无写入）/ 规则手册五部分级

---

## 1. 背景与问题

页面 `http://127.0.0.1:5005/bbt_option_seller` 顶部只有一个全局步进器决定「一次自动开仓开几组」（`self.auto_groups`，1 组 = 2 手双批次）。该单值同时被 7 个触发机制共用：

1. **无法表达不同机制的不同风险预算**——不同机制的实测胜率、假信号率与机会频率并不相同（例如机制 ③ 平衡日边界经数据回放已被否定「多组」口径，而机会更多的机制可能需要更高组数）。
2. **旋钮语义单一但结构耦合**——机制 ③ 的组数本应由五维评分器分档 + 通道硬顶 `groups_cap` 决定，却被全局值二次覆盖，口径不清。
3. **无可视对照**——页面看不到「某机制当前配置几组 / 实际活跃几组」，改完只能靠交易日志反查。

## 2. 实施目标

| 目标 | 交付 |
|---|---|
| 组数可按**触发机制**分别设置 | 新增 `Config/option_seller_auto_groups.json`（`{default, per_mechanism}`）+ `groups_for(触发标签)` 唯一取值入口 |
| 提供可视化设置入口 | 页面新增「组数控制台」（每机制一行：组数 / 当前活跃 / 说明） |
| 语义唯一、不产生歧义 | 统一为**上限口径**；机制 ③ 只能**收紧**（`min(评分器分档, 通道硬顶, 控制台值)`） |
| 不破坏既有行为与闸门 | 旧接口 `set_auto_groups` 保留（写 `default`）；L0-C / L0-D / L0-E 一律不绕过 |
| 配置可维护 | 配置文件**只写显式项**（继承值不固化），故「改全局默认」能真正带动未单独设置的机制 |

## 3. 关键设计

### 3.1 配置结构（`Config/option_seller_auto_groups.json`）

```json
{
  "default": 1,
  "per_mechanism": { "AUTO_5M_SYNTHESIS": 2 },
  "updated_at": "2026-09-14 06:30:02"
}
```

- `default`：全局默认组数，**未显式配置的机制继承此值**
- `per_mechanism`：仅存**显式设置**的机制（值 `null` ⇒ 删除该项回到继承；`clear_per_mechanism: true` ⇒ 清空全部显式项）
- 范围 **1–5**，与 `auto_mechanisms.GLOBAL_GROUP_CAP`（L0-E）对齐，越界截断

### 3.2 取值语义（唯一入口 `groups_for(trigger_label, scorer_groups=None)`）

| 机制 | 本次开仓组数 |
|---|---|
| ①②④⑤⑥（一般机制） | `groups_for(标签)`（该机制上限值本身） |
| ③ 平衡日边界 | `min(五维评分器分档, balanced_day.groups_cap, groups_for(标签))` ⇒ 控制台**只能收紧、不能放宽** |

- 标签先 `normalize_label()` 归一，再**前缀匹配**落机制（子场景标签 `AUTO_PM_BIG_TRADE_UT1_…` ⇒ ⑤）
- 未匹配任何机制的标签 ⇒ 回落 `default`
- **不绕过任何 L0**：机制级 / 机制数 / 全局组数仍由 L0-C / L0-D / L0-E 把关

### 3.3 改动清单

| 层 | 文件 | 改动 |
|---|---|---|
| 配置层 | `PyTools/option_seller/option_seller_manager.py` | `AUTO_GROUPS_CFG` / `AUTO_GROUPS_MIN/MAX/DEFAULT`、`clamp_auto_groups`、`_read_auto_groups_raw`、`load/save_auto_groups_config` |
| 取值层 | 同上 | `groups_for()`、`get_active_groups_by_mechanism()`、`_auto_groups_status_payload()` |
| 接线 | 同上 | `__init__` 载入配置；`_open_from_engine` 改读 `groups_for(trigger_label)`；机制 ③ 的 `cap` 再与 `groups_for(LABEL_BALANCED_DAY)` 取 min |
| 兼容 | 同上 | `set_auto_groups(n)` ⇒ 写 `default`（旧调用方零改动） |
| API | `bbt_data_web/data_app/bbt_option_seller.py` | 新增 `GET/POST /api/option_seller/auto_groups_config`（GET 带回 `meta`，与 status 同结构）；`status` 增 `auto_groups_config` |
| 页面 | `bbt_data_web/templates/bbt_option_seller.html` | **头部删除原「全局默认组数」步进器**，仅保留「组数控制台」按钮；**与「Force Dry 触发」同款弹窗**（`#autoGroupsModal`，内含全局默认行）+ JS（草稿 / 保存 / 全部归为默认 / 单项还原继承 / 关闭即弃稿） |

## 4. 验证方案

1. **配置语义单测**（离线）：继承 / 显式 / 删除回继承 / 清空 / 越界截断 / 前缀匹配 / ③ 只收紧
2. **API 往返**：`POST → 文件内容 → GET → status 载荷` 一致；改回默认不残留显式项
3. **页面渲染**：headless Chrome 实渲染，逐行断言机制名、组数、活跃数、标签与页脚口径说明
4. **无回归**：`py_compile` + 模板 JS 语法 + 现有 smoke；不写任何业务表

## 5. 风险与回退

- **风险**：逐机制设置若被误设为 &gt;1，会使单次开仓实际组数上升 ⇒ 已限定 1–5、并在面板页脚显式标注 L0 闸门不被绕过；机制 ③ 另有「只收紧」硬约束。
- **回退**：`POST {"default":1,"per_mechanism":{},"clear_per_mechanism":true}` 即恢复「全部 1 组」的旧行为；或直接删除 `Config/option_seller_auto_groups.json`（缺失即取缺省 1）。
- **代码回退点**：`/tmp/bbt_autogroups_backup_062623/`（三文件术前副本）。
