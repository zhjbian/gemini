# MotiveWave v6 → v7 升级评估 · 备份与回退方案（2026-09-12 · v1.1 实测修正版）

# 42. MotiveWave v6 → v7 升级评估 · 备份与回退方案

日期 2026-09-12（v1.1：按实测修正"必须重编译"判断 ✗ ⇒ 见 §3.1） ｜ 现状 v6.9.12（生产）→ 目标 v7.1.0（build 644，2026-09-06 发布）｜ 关联目录 42_2026-09-12_MotiveWave_v7_Upgrade_Assessment

## 1. 需求与背景

- 生产长期使用 MotiveWave_6_9_12.app；v6.9.12 本身是纯 bugfix 版（官方 Release Notes 原文）✓
- 曾试用 7.0.x（本机遗留工作区名 dxFeed_7 / dxFeed-7 / dxFeed-7-0-22 可证）但问题较多 ✗
- 刚安装 7.1.0（2026-09-06 发布）⇒ 需评估：(1) 主要更新/性能、(2) 升级需要改动什么（已知 v7 本地 Tick 文件格式与 v6 不同）
- 硬性要求：若 v7 有问题必须能快速切回 v6 ⇒ 回退机制 + 全面备份为前置条件 ✓

## 2. 官方 Release Notes 关键内容（v7.1.0 PDF 原文提取）

> 官方硬声明 ①：Data formats have changed in version 7 of MotiveWave. Workspaces created using older versions are forward compatible (they can be used in Version 7) but once the workspace has been opened in version 7, it will not be able to be opened by older versions. Please consider creating a new workspace for version 7 testing and restore from a backup of an existing workspace.

> 官方硬声明 ②：SDK changes were made to the SDK in version 7. Custom studies/strategies will need to be recompiled.（a. Volume Profile classes added. b. DOM Notes added.）

### 7.1.0 三项特性（原文要点）

| # | 特性 | 原文要点 | 对本系统的意义 |
|---|---|---|---|
| 1 | Compressed Historical Data | Historical Time & Sales (Tick) data is now left compressed into daily files stored locally ⇒ 8–10× improvement in storage requirements | 这就是"v7 本地 Tick 文件格式不同"的根因 ✓；MW 内部历史库不再逐笔明文存储 ✓ |
| 2 | Smooth Scrolling | 线性周期 ≤ 2 秒时启用（默认开，配合 Auto Move Bar） | 盯盘体验 ✓（与本系统无耦合） |
| 3 | Performance Improvements | Time & Sales 数据加载与处理改进（用于构建 Volume Profile / TPO）⇒ 大 TPO / VP 载入快 2–4× | VP/TPO 类分析显著受益 ✓ |

### 7.0.x 累积要点（原文摘录）

- Java 26 / JavaFX 运行时升级（7.0.21）⇒ v7 的 Java 运行时与 v6 不同 ✓
- alerts / study signals 改为按需加载（启动性能）
- Shorten Axis Values（默认开）、Import Data 监视输入文件自动重载（默认每分钟）、Study Legend 悬停按钮、DOM 文本颜色可改、Coinbase Advanced API 等

## 3. 本机实测事实（2026-09-12）

| 项 | 实测值 |
|---|---|
| 已安装应用 | /Applications/MotiveWave_6_9_12.app ✓ · /Applications/MotiveWave_7_1_0.app ✓（两者结构一致：Java/ Plugins/ javafx/ defaults/ etc/；v7 内含 MotiveWave.jar + bcpkix/bcprov/commons-* 等） |
| workspace 路径 | ~/Library/MotiveWave/workspaces/<名称>/ ⇒ 目录内容：analysis/FUTURE/<symbol>.XCME.DXFEED/*.mwml、config/{workspace,defaults,ofa,cmp_templates}.json、11 个 *.mwml |
| 现有 workspace | dxFeed（1 行 1464 KB，最后修改 2026-08-19，9 个文件引用 bbt/OrderFlow/QuantPivot）← 生产主库 ✓；dxFeed-7（444 KB，2026-08-16）← v7 试验库 ✓；另有 workspaces.json |
| MW 自动备份命名（揭示使用史） | BBT(9) → dxFeed(10) → dxFeed_7(10)/dxFeed-7-0-22(10)/dxFeed-7(4) ⇒ v7 试验早已存在 ✓ |
| 自定义 study 部署（共享目录 ✗） | ~/MotiveWave Extensions/dev/bbt/*.class = 33 个类 / md5 3118261a7b83（StudyQuantPivot、StudyOrderFlowReversal*、StudyBigTrades*、FlaskBridge*、StudyStackedLowVolumeHighLow* 等）—— 两版共用 ⇒ v7 重编译会覆盖 v6 类 ✗ |
| study 源码/构建材料 | ~/BB_Workspace/MotiveWave Studies/（bin/build/lib/src）✓ · MotiveWave_Studies7.zip 5.5 MB ✓ · sdk_api_doc7.zip 5.2 MB ✓ · ~/Intellj-workspace/BBT_Studies（17 MB）✓ |
| 偏置/设置 | ~/Library/Preferences/com.motivewave.platform.plist（4 KB）✓ · ~/Library/MotiveWave/{settings.json,startup.ini,mwave_license.txt} ✓ · ~/Library/Application Support/MotiveWave/（仅 webview，0 B） |
| 数据规模 | ~/Library/MotiveWave 合计 7.7 GB，其中 historical_data 7.6 GB、output 70 MB、workspaces 1.9 MB |
| 导出目录（本系统读取层） | ~/Documents/MyDoc/Finance/Current/MotiveWave_OrderFlow_Data/{Raw,Analysis,Realtime}；已新增 Raw_v7/ 供 v7 专用 ✓；单日 TICKS 32–38 MB、DOM.csv.gz 174–195 MB |

## 3.1 关键实证：v7 期间未重编译 SDK 也能运行，且导出格式一致 ✓

本节回答两个"是否为运行前提"的关键疑问，依据是本机历史导出文件（8 月为 v6/v7 混用期；工作区 dxFeed-7 最后修改 2026-08-16 ✓）：
| 日期 | 文件 | TICKS 表头 | DOM 表头 |
|---|---|---|---|
| 2026-08-16 ~ 08-23（v6/v7 混用期 ✓） | ES_2026081*_TICKS.csv.gz ✓ _DOM.csv.gz ✓（确实存在 ✓） | Timestamp,Price,Size,Side,Contract | Timestamp,Type,Level,Price,Size,Contract |
| 2026-09-01 ~ 09-11（v6 生产 ✓） | 同名规则文件 ✓ | 与本行完全相同 ✓ | 与本行完全相同 ✓ |

- 结论 1（对 A 的影响）：不重编译 study 也能在 v7 中运行并导出 ✓✓（与用户 7.0.x 实际经历一致 ✓）—— 官方"需要重编译"是建议（v7 SDK 为新增 Volume Profile 类与 DOM Notes，属增量改动，对旧编译字节码通常二进制兼容 ✓）
- 结论 2（对 B 的影响）：study 导出的 CSV 格式在 v7 期间未变 ✓✓（列名/顺序/时间戳 epoch-ms 单位/合约字段全部一致 ✓）⇒ 下游 mw_gzip + 各解析脚本 无需 adapter ✓
- 仍未知（诚实标注 ✗）：① 上述证据覆盖 7.0.x；7.1.0 新增的"历史 Tick 按日压缩"属 MW 内部存储改动 ✓，理论上不影响自研导出（study 经 MW API 取数 ✓ 再自行写 CSV ✓），但需一次实测确认 ✓；② 若未来用到 v7 新 SDK 特性（Volume Profile 类 / DOM Notes），届时必须重编译 ✓

## 4. 影响评估：升级到 v7 需要改什么

| # | 影响面 | 说明与动作 | 风险 |
|---|---|---|---|
| A | 自定义 study（Java 导出器） | 官方明文："SDK changes were made in version 7. Custom studies/strategies will need to be recompiled"。但实测反证：v7.0.x 期间未升级 SDK 仍正常运行并在 8/16–8/23 持续产出导出文件（见 §3.1 实证 ✓）⇒ 重编译是官方建议（消除 API 漂移风险）而非运行前提。涉及 BBT_Studies/src/bbt/StudyOrderFlowDataExporter.java 等；如需重编，用 v7 SDK/JDK（Java 26）重编到独立目录 | 低–中（保留旧编译通常可跑 ✓；API 若被移除/改签名或行为变更才需重编 ✗） |
| B | 本地数据格式 | v7 把 Tick 历史改为按日压缩文件（8–10×）。若读取器直读 MW 内部历史库（v6 未压缩日文件）⇒ 必须适配 ✓；若读取的是自研 study 导出的 CSV（ES_YYYYMMDD_{TICKS.csv,DOM.csv.gz}）⇒ 导出格式可能不变，需实测比对 | 中（取决于读哪一层） |
| C | workspace | v6→v7 前向兼容；但一旦 v7 打开过 ⇒ v6 再也打不开 ✗ ⇒ 必须用副本做 v7 测试 | 不可逆（唯一真正不可逆项） |

### 不受影响（好消息）

- 下游分析链读的是文件：py_lib/mw_gzip.py（容错读取器：多成员/空成员/截断/纯 CSV/二进制 gzip 自动识别 ✓）、jobs/mw_data_health_check.py、order_flow_analysis/*（引擎）、jobs/adam_*（Adam 深度分析）⇒ 只要导出格式不变或微变，几乎无需改动 ✓
- 数据库与 Adam 信号子系统（order_flow_signals 71 列、adam_deep_payload、adam_signal_verdicts）与 MW 版本完全无关 ✓

## 5. 迁移方案（建议顺序，每步可回退）

- 备份 v6（见 §6）— 已完成 ✓
- 复制 workspace：cp -R ~/Library/MotiveWave/workspaces/dxFeed ~/Library/MotiveWave/workspaces/dxFeed-v7test；v7 只打开副本，v6 继续用 dxFeed（原库保持纯净 ⇒ 回退零修复 ✓）
- 先用现有（v6 编译）study 直接试 v7 ✓（实测可行 §3.1）；仅当加载报错/输出异常时才用 v7 SDK 重编译（材料已有：sdk_api_doc7.zip ✓）→ 装到扩展目录 → 记录 mw_version_switch.py --snapshot --as 7；两种都需先存 v7 基线以便一键回退 ✓
- 并行导出 + 格式 diff：v6 输出 Raw/、v7 输出 Raw_v7/；同日同品种逐列比对（表头/列数/时间戳单位/排序/压缩方式）
- 下游试跑：用 v7 单日输出跑 健康检查 → 引擎 → Adam 深度分析；全部通过后切换默认，v6 与旧解析路径保留 ≥2 周

## 6. 备份方案（已实施并校验）

脚本：PyTools/jobs/mw_v6_backup.py（只读源 ✓ rsync -a 保元数据 ✓ 附 MANIFEST.json ✓）

```
python3 PyTools/jobs/mw_v6_backup.py                 # 完整备份（含 7.6G 历史数据 ✓ 推荐）
python3 PyTools/jobs/mw_v6_backup.py --no-data       # 只备状态（几 MB，秒级）
python3 PyTools/jobs/mw_v6_backup.py --zip           # 额外打 tar.gz 便于异地
```

本次结果：~/Documents/MyDoc/Finance/Current/MW_Backups/mw6_20260912_174434/，合计 8.19 GB / 50 秒：
| 项 | 大小 | 说明 |
|---|---|---|
| Library_MotiveWave/ | 7.7 GB | 含 historical_data 7.6 GB（唯一不可逆部分 ✓）；workspaces/dxFeed 1464 KB（与原库逐字节一致 ✓，11 mwml / 9 bbt 引用 ✓）、dxFeed-7 444 KB、config/、output/、settings.json、mwave_license.txt |
| MotiveWave_Extensions/ | 460 KB | 33 个 study class（md5 3118261a7b83 ✓ 与当前一致） |
| MotiveWave_Backup/ | 1.74 MB | MW 自动备份（BBT/dxFeed/dxFeed-7*） |
| prefs_com.motivewave.platform.plist | 4 KB | 校验和 49ec3d8baf724831e6e9d33b |
| study 源码与 zips | 13 MB | MotiveWave Studies + MotiveWave_Studies7.zip + sdk_api_doc{7,}.zip |
| Intellj_BBT_Studies/ | 15 MB | 另一份 study 工程 |
| MANIFEST.json | 4 KB | 时间/主机/macOS 15.5/两版应用存在性/workspace 清单/类指纹/关键文件校验和 |

### 还原命令

```
# ① 关闭所有 MotiveWave 实例（v6/v7 都关）
B=~/Documents/MyDoc/Finance/Current/MW_Backups/mw6_20260912_174434
# ② 还原（覆盖同名文件）
rsync -a "$B/Library_MotiveWave/"     ~/Library/MotiveWave/
rsync -a "$B/MotiveWave_Extensions/" ~/"MotiveWave Extensions"/
rsync -a "$B/MotiveWave_Backup/"     ~/"MotiveWave Backup"/
cp -p "$B/prefs_com.motivewave.platform.plist" ~/Library/Preferences/com.motivewave.platform.plist
# ③ 切回 v6 扩展类 + 打开 v6
python3 PyTools/jobs/mw_version_switch.py --to 6
open -a /Applications/MotiveWave_6_9_12.app
```

建议：把该备份目录另复制一份到外置盘（8.2 GB）—— 目前与源在同一块盘。

## 7. 回退机制（版本切换器）

脚本：PyTools/jobs/mw_version_switch.py（维护两套扩展 class 基线 + 一键互换 ✓ 绝不触碰 workspace ✓）

```
python3 PyTools/jobs/mw_version_switch.py --status            # 看当前状态
python3 PyTools/jobs/mw_version_switch.py --snapshot --as 6   # 首次必做：存 v6 基线（已做 ✓）
python3 PyTools/jobs/mw_version_switch.py --snapshot --as 7   # 在 v7 环境里存 v7 基线
python3 PyTools/jobs/mw_version_switch.py --to 7              # 切 v7（自动备份当前类）
python3 PyTools/jobs/mw_version_switch.py --to 6              # ★ 一键回退 v6
python3 PyTools/jobs/mw_version_switch.py --prep7             # 建 Raw_v7/ + 打印 workspace 指引
```

| 当前状态（实测） | 值 |
|---|---|
| 配置活动版本 | v6（Config/mw_version.json，2026-09-12 17:39） |
| 扩展类实际内容 / v6 基线 | 33 类 / md5 3118261a7b83 ✓ 一致 |
| v7 基线 | 尚未建立（需在 v7 环境 --snapshot --as 7） |
| 切换备份 | 每次切换自动备份当前类为 bbt.current-<时间戳> ✓ |

### 为什么需要切换器（三个不可逆风险）

| # | 风险 | 后果 | 对策 |
|---|---|---|---|
| ① | workspace 单向升级 | v7 打开过 ⇒ v6 打不开盘面 ✗ | 工具不碰 workspace；v7 只用副本 ✓ |
| ② | 扩展目录两版共享 | v7 重编译覆盖 v6 类 ⇒ v6 崩溃 ✗ | 两套 class 基线 + 一键互换 ✓ |
| ③ | 导出格式不同 | 同目录混写 ⇒ 下游解析错乱 ✗ | v7 输出到 Raw_v7/ ✓ |

## 8. 存储治理（与本轮同日完成，相关性强）

- 已有清理脚本：PyTools/order_flow_analysis/cleanup_old_order_flow_raw.py（压缩 .csv→.gz ✓ 按保留天数删除 ✓，默认 14 天 ✓）—— 但此前从未被调度 ✗
- 新增安全闸（默认开 ✓）：删除某日前检查 ① 该日 order_flow_signals 有行 ② 该日 Adam 方向性帖的 adam_deep_payload 全部 complete=1；源文件已缺失 ⇒ 允许删（不可恢复）✓；源文件仍在而不完整 ⇒ 跳过（留机会补跑）✓ —— DRY-RUN 实证：08-16（引擎行 0）✗、08-17/18/19/20（payload 不完整）✗ 均被拦下 ✓
- 已挂调度：launchd com.bbt.mw-raw-cleanup 工作日 15:00 --days 14 ✓（daily_jobs.py 内的同名调度已移除，避免重复 ✗ 单一来源 = launchd ✓）
- 与 v7 的关系：v7 的 8–10× 压缩是 MW 内部存储改进；本系统导出侧的 gz 压缩 + Adam 深度分析落库（adam_deep_payload ⇒ 原始 MW 文件 14 天后可安全删除 ✓）叠加后，磁盘压力显著下降 ✓

## 9. 待办与决策清单

| # | 事项 | 状态 |
|---|---|---|
| 1 | v6 全面备份（8.19 GB + MANIFEST） | 已完成 ✓ |
| 2 | 备份复制到外置盘 | 待办（建议） |
| 3 | 复制 workspace 供 v7 专用（dxFeed-v7test） | 待办（一行 cp -R） |
| 4 | 条件待办：先用现有 study 试 v7（实测可行 ✓）；仅当报错/输出异常才重编译 ⇒ 无论是否重编都先存 v7 基线（--snapshot --as 7） | 风险已降级 ✓ |
| 5 | 编写 mw_export_diff.py（v6/v7 导出格式比对：表头/列数/时间单位/排序/压缩） | 待办 |
| 6 | （若格式有变）编写 mw_export_adapter.py 兼容两版（复用 mw_gzip） | 条件待办 |
| 7 | 下游链在 v7 单日输出上试跑（健康检查→引擎→Adam 深度） | 待办 |

## 10. 命令速查

```
# 备份 / 还原
python3 PyTools/jobs/mw_v6_backup.py [--no-data] [--zip]
B=~/Documents/MyDoc/Finance/Current/MW_Backups/mw6_20260912_174434   # 还原见 §6

# 版本切换 / 回退
python3 PyTools/jobs/mw_version_switch.py --status | --snapshot --as 6|7 | --to 6|7 | --prep7

# MW 原始文件清理（14 天 + 安全闸）
python3 PyTools/order_flow_analysis/cleanup_old_order_flow_raw.py --days 14 --dry-run
python3 PyTools/order_flow_analysis/cleanup_old_order_flow_raw.py --days 14
#   launchd：com.bbt.mw-raw-cleanup（工作日 15:00）

# 关键路径
#   应用        /Applications/MotiveWave_{6_9_12,7_1_0}.app
#   workspace   ~/Library/MotiveWave/workspaces/{dxFeed,dxFeed-7,...}
#   扩展类      ~/MotiveWave Extensions/dev/bbt/*.class
#   历史数据    ~/Library/MotiveWave/historical_data（7.6 GB）
#   导出        .../MotiveWave_OrderFlow_Data/{Raw,Raw_v7}
#   配置        Config/{mw_version.json,mw_ext_store/}
```

## 11. 风险登记

| 风险 | 等级 | 缓解 |
|---|---|---|
| 不重编译 study 就用 v7 ⇒ 无法运行/无导出 (原判为高，已按实测修正 ✗) | 低–中 | 实测 v7.0.x 未重编译即可运行且导出正常 ✓（§3.1）；如遇加载报错或输出异常 ⇒ 再用 v7 SDK 重编（sdk_api_doc7.zip 已备 ✓） |
| v7 打开了 v6 主库 ⇒ 不可逆 | 高（不可逆） | 只用副本；切换器不碰 workspace ✓ |
| v7 重编译覆盖共享 class ⇒ v6 崩溃 | 中 | 两套 class 基线 + --to 6 ✓（v6 基线已存 ✓） |
| v7 迁移 historical_data 后 v6 读不了 | 中 | 已备份 7.6 GB 数据 ⇒ 可整目录还原 ✓ |
| 导出格式变化污染下游 | 中 | v7 独立输出目录 + 格式 diff + （必要）adapter ✓ |

