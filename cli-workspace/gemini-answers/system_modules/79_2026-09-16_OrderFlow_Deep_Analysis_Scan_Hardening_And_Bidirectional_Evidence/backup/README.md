# 回滚点（2026-09-16 交付 · 改动前快照）

> 用途：本目录保存 2026-09-16「Order Flow 深度分析链路加固 + 候选扫描口径放宽」交付中**所有被修改文件的改动前版本**。
> 系统重启会清空 `/tmp`，故长期保留于此。**只读参考，不要直接运行本目录内的文件。**

## 1. 文件清单与回滚方式

| 文件 | 对应现役路径 | 改动前来源 | 回滚命令 |
| :--- | :--- | :--- | :--- |
| `skill_scripts/baseline.py` | `~/.agents/skills/order-flow-deep-analysis/scripts/baseline.py` | 2026-09-15 23:16 手工备份 | `cp backup/skill_scripts/baseline.py <现役路径>` |
| `skill_scripts/baseline_pair.py` | `~/.agents/skills/order-flow-deep-analysis/scripts/baseline_pair.py` | 2026-09-15 23:31 手工备份 | `cp backup/skill_scripts/baseline_pair.py <现役路径>` |
| `pytools/adam_dom_analysis.py` | `PyTools/jobs/adam_dom_analysis.py` | 2026-09-12 16:46 原始副本 | `cp backup/pytools/adam_dom_analysis.py <现役路径>` |
| `pytools/adam_tick_analysis.py` | `PyTools/jobs/adam_tick_analysis.py` | 2026-09-12 16:40 原始副本 | `cp backup/pytools/adam_tick_analysis.py <现役路径>` |
| `pytools/absorption_reversal.py` | `PyTools/order_flow_analysis/absorption_reversal.py` | **`PyTools` 独立 git 仓库 `HEAD`** 抽取 | `cd PyTools && git checkout -- order_flow_analysis/absorption_reversal.py` |
| `pytools/test_absorption_reversal_module.py` | `PyTools/option_seller/test_absorption_reversal_module.py` | **`PyTools` 独立 git 仓库 `HEAD`** 抽取 | `cd PyTools && git checkout -- option_seller/test_absorption_reversal_module.py` |
| `dom_cache_old/ES_2026091{4,5}.json` | `~/.agents/skills/order-flow-deep-analysis/cache/dom_minutes/` | 2026-09-15 23:08 旧缓存 | `cp backup/dom_cache_old/*.json <现役缓存目录>/`（**不推荐**：旧缓存已证实有缺陷，见下） |

## 2. 无改动前快照的文件（需人工还原）

以下文件在同日交付中被改动，但**改动前版本未留存**（改动为纯新增/定点替换，已在下表给出精确还原方法）：

| 文件 | 改动 | 还原方法 |
| :--- | :--- | :--- |
| `~/.agents/skills/order-flow-deep-analysis/scripts/run_analysis.py` | 新增 `evidence.dims`（吸收度 / 大档位迁移 / 瞬时事件）与报告展示区；移除重复 `interpret` 定义 | 删除 `_absorb_dims()` / `_wall_dims()` / `_dims_block()` 三段及 `"dims": _dims,` 一行；无需恢复其它逻辑 |
| `~/.agents/skills/order-flow-deep-analysis/scripts/build_dom_cache.py` | **全新文件** | `rm` 即可 |
| `~/.agents/skills/order-flow-deep-analysis/SKILL.md` | 新增「★ 双向证据维度」章节 + 3 条运维提示 | 删除对应小节 |
| `PyTools/jobs/adam_signal_deepdive.py` | 脏时间戳防截断（1 处） | 还原 `_beyond` 计数为 `if t > t0_sec: break` |

## 3. ⚠️ 关于 `dom_cache_old/` 的特别说明

旧缓存**不要**当作「正确基线」还原——经完整原始文件复算，旧缓存存在：

| 日 | 旧缓存分钟数 | 内部缺失 | 数值错误分钟 |
| :--- | ---: | ---: | :--- |
| 2026-09-14 | 285（05:59→11:00） | **17 分钟**（454–470，即 07:34–07:50） | `453`（`tot_ask` 2351 vs 完整 4074）、`660`（`tot_bid` 5313 vs 5353） |
| 2026-09-15 | 302（05:59→11:00） | 0 | `660`（`tot_bid` 6796 vs 6567） |

成因：缓存是在 **DOM 导出尚未写完**时建立的（当日导出文件还缺 07:34 之后的分钟，且最后一分钟的 ask 侧未累积完）。

影响：skill 侧 `dom_tot_max` 被虚高（09-14 07:19 得 1.623，完整数据为 1.020）⇒ 09-14 07:19 / 07:24 的 A 票数由 **+7 虚高**，修正后为 **+5**，与生产侧逐维完全一致。

保留旧缓存的唯一目的是**留证**。若必须回退，请知悉回退会把上述错误的 DOM 维度一并带回。
