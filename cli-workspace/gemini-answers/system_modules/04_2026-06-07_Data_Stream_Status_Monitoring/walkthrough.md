# Walkthrough · 多源实时数据流健康监控（module 04）

> 本文件按时间线记录该模块的**验收 / 修复报告**。

## 2026-09-14 · 修复：MW 时段覆盖水平条全线不显示

### 现象（用户报障）

`http://127.0.0.1:5005/bbt_signals?date=2026-09-14` 页面上，MW 数据健康 widget 的「**时段覆盖**」区只有两行汇总（TICK / DOM「写入中（尚未成形）」），**一条 5 分钟水平条都没画**；用户提问「开盘了 为什么没有画出今天的 TICK 和 DOM 水平 bar」。

### 诊断

| 步骤 | 证据 |
| :--- | :--- |
| 原始文件在写 | `ES_20260914_TICKS.csv` 3.9MB / `ES_20260914_DOM.csv.gz` 59MB，mtime = 当前分钟（MW 正在写） |
| API 返回 | `/data/mw_data_health?date=2026-09-14` 的 `coverage_rows` 全部 `lines=0, first=None, last=None, truncated=True, day_strip=None` |
| 直接调用扫描器 | `scan_timestamps(任意文件)` ⇒ `ok=False lines=0 err="AttributeError: 'MwBinaryFile' object has no attribute 'path'"` |
| 影响面 | **所有日期**（`ES_20260911_TICKS.csv` 等历史文件同样 0 行）—— 不是「今天没数据」，而是覆盖分析**整体失效** |

### 根因

`PyTools/py_lib/mw_gzip.py` 的容错二进制读取类 `MwBinaryFile`：

```python
def __init__(self, path, chunk_size=1 << 20):
    self.raw = Path(path).read_bytes()      # ← 只存了「文件字节」
...
def _iter_chunks(self):
    self._flag = [False]
    for out in _iter_member_chunks(self.path, self._flag):   # ← 引用 self.path（**从未赋值**）
```

`_iter_member_chunks(path)` 内部用 `os.path.getsize(path)` / `open(path, "rb")` ⇒ 必须传**路径**，而实例上没有 `path` 属性 ⇒ 每次二进制读取抛 `AttributeError`。

`mw_data_health_check.scan_timestamps()` 以 `mw_open_text(path, "rb")` 打开（`'b' in mode` ⇒ `MwBinaryFile`），异常被其 `try/except` 吞成 `truncated=True, ok=False, lines=0` ⇒ `buckets={}` ⇒ `build_coverage()` 直接 `summary="无有效数据行"`、`day_strip=None` ⇒ **页面无条可画**。

### 修复

```python
def __init__(self, path, chunk_size=1 << 20):
    # ★ 2026-09-14 修复：_iter_chunks() 依赖 self.path（_iter_member_chunks 用 os.path.getsize/open(path)），
    #   原实现只赋 self.raw（文件字节）⇒ 任何二进制读取都抛 AttributeError，被上层吞成 lines=0。
    self.path = Path(path)
    self.chunk_size = chunk_size

@property
def raw(self) -> bytes:
    """兼容旧 API：原始文件字节。惰性读取（原实现在 __init__ 无条件读全文件，
    DOM 单文件 ~59MB ⇒ 每次完整性校验白白占用内存）。"""
    return self.path.read_bytes()
```

### 验收

| 文件 | 修复前 | 修复后 |
| :--- | :--- | :--- |
| `ES_20260914_TICKS.csv` | ok=False · lines=0 | ok=True · **117,325 行 · 81 桶** |
| `ES_20260914_DOM.csv.gz` | ok=False · lines=0 | ok=True · **16,434,731 行 · 81 桶**（扫描 11.5s） |
| `ES_20260913_TICKS.csv` | ok=False · lines=0 | ok=True · 33,405 行 · 108 桶 |
| `ES_20260911_TICKS.csv` | ok=False · lines=0 | ok=True · **996,592 行 · 168 桶** |

触发巡检（`POST /data/mw_data_health/scan`，等价页面「刷新」）后，`/data/mw_data_health?date=2026-09-14` 的 `coverage_rows` 已返回 **288 字符 `day_strip`**：当日 81 个有数据桶（00:00–06:43，`111111111---` 形态）、`requested_date_status={'OK': 4}` ⇒ 页面恢复绘制 TICK / DOM 水平条。

### 回归测试（新增）

`PyTools/jobs/test_mw_reader.py`（7 例，**自造 fixtures**，不依赖真实 MW 文件）：

1. 纯 CSV / 单成员 gz / 多成员 gz 均可读；
2. **尾部截断 gz**（MW 正在写）：已刷盘部分仍可读、`bad_rows=0`、不抛异常；
3. **无可解码成员**（合法 gz 头 + 垃圾体）：0 行、不抛异常、读取器 `truncated=True`；
   （注：若只写 `b'\x1f\x8b' + 零字节`，3 字节 magic 比较会判为纯 CSV 而被当文本读出 1 行垃圾 —— 属另一路径，测试已注明）
4. `.raw` 惰性属性仍返回完整字节（API 兼容）；
5. 分桶正确（跨 5 分钟桶 ⇒ 2 桶）。

### 遗留（非本次范围）

`NQ_20260913_DOM.csv.gz`（2.4MB）确为**无可解码成员**的坏文件（首行 `b''`、`truncated=True`、0 行）⇒ 属独立的「空文件/损坏」项，需按页面提示走 `python PyTools/jobs/mw_dom_recover_and_recompute.py --date 2026-09-13` 抢救流程。

### 回滚点

- `PyTools/py_lib/mw_gzip.py` 术前：`/tmp/l0c_bak/mw_gzip.py.pre_fix`
- 模块索引术前：`/tmp/mods_pre_mwfix.html.bak`

## 2026-09-14 · 追加：明细只显示「当天 + 前一天」，更早明细归档到本地文件

**用户要求**：MW 数据健康明细「只显示当天和前一天的；更早的信息保存只保存到本地文件，不显示」。

### 改动

| 层 | 改动 |
| :--- | :--- |
| 后端 `/data/mw_data_health` | 明细列表（`actionable` / `ignored` / `in_progress`）按 **窗口 = {最新数据日, 最新数据日−1 天}** 过滤；`summary`（顶部 chip）与 `counts` 同步改为**窗口口径**，全量计数另存 `summary_all`；新增 `details_window{from,to,kept,hidden,archived_new}` / `details_hidden_count` / `details_log_path` |
| 归档 | 窗口外的行 **append-only** 追加到 `Config/mw_data_health_details.log`，按 `(data_date,ticker,kind,status)` **签名去重**（前端 4 秒轮询不重复刷屏）；写盘失败仅记日志、**不影响接口** |
| 前端 `bbt_signals.js` | 新增 `mwArchiveHint()`：在 chip 行与「需要处理（N 项）」表头显示「明细窗口 2026-09-13 ~ 2026-09-14 · 更早 18 项已归档（复制路径）」；提示 title 内含完整规则与文件路径 |

### 实测（2026-09-14 07:5x）

```
details_window   = {'from': '2026-09-13', 'to': '2026-09-14', 'kept': 1, 'hidden': 18, 'archived_new': 18}
summary（窗口）   = {'OK': 7, 'IN_PROGRESS': 1, 其余 0}      ← 与表格同口径（原为全历史 OK:33 / SUSPECT:16 / EMPTY:2）
summary_all      = {'OK': 33, 'SUSPECT': 16, 'EMPTY': 2, 'IN_PROGRESS': 1}
列表日期          = ['2026-09-13']                            ← 08-30 起的 18 项不再下发
归档文件          = Config/mw_data_health_details.log（首次写入 18 项；重复调用行数稳定 42 行）
```

### 测试（新增 3 例）

`bbt_data_web/data_app/test_mw_health_window.py`：① 首次写入全部窗口外行、二次调用去重为 0、新增日期只追加 1 条；② 空输入不创建文件；③ 写盘失败（只读路径）返回 0 且不抛异常。全部通过。

### 过程记录（一次自伤与修复）

首次改动在模块**顶层**使用了 `Path(...)` 却未在顶层 `from pathlib import Path`（文件里只有函数内的局部导入）⇒ Flask reloader 重新导入该蓝图时 **NameError ⇒ 5005 应用崩溃**（`curl` HTTP 000）。已补顶层导入、`AST` 与模块导入自检通过，并在**新 Terminal 窗口**重启 `bbt_data_app.py`（恢复 HTTP 200；该应用非 launchd 托管，一直是手动终端启动）。

**回滚点**：`/tmp/l0c_bak/bbt_signals.py.pre_window` · `/tmp/l0c_bak/bbt_signals.js.pre_window` · `/tmp/mods_pre_window.html.bak`。

## 2026-09-14 · 追加：MW DOM 导出间隔 500ms → 250ms 的实测确认，与「读取截断静默」双缺陷修复

**用户要求**：「2026-09-14 07:51:30 我把 ES DOM 导出间隔从 500ms 改成了 250ms，请检查一个 DOM 导出文件，分析确认」→ 我给出结论与两项修复建议（① 读取器截断不再静默；② 文档同步）后，用户回复「需要」。

### 一、导出间隔变更的实测确认（结论：变更已生效，且只改了频率）

同一天同一个 `ES_20260914_DOM.csv.gz` 内含 **2 个 gzip 成员**，成员边界正好落在变更时刻：

| 成员 | 时间范围 | 快照间隔（峰值 / 中位数） | 快照数/分 | 行数/分 | 行/快照 |
| :--- | :--- | :--- | ---: | ---: | ---: |
| #1（旧） | 00:00:00 → 07:50:48 | 500 / 501 / 502 ms · 中位 560ms | 100 | 40,053 | 400 |
| #2（新） | 07:51:28 → 08:03:22 | **252 / 259 / 271 ms** · 中位 311ms | **148** | **59,275** | 400 |

**判定**：① 间隔峰值由 500ms 档降到 **250ms 档**，与 07:51:30 的时间点吻合（成员边界 07:50:48 → 07:51:28）；② **行/快照恒为 400 档不变** ⇒ 只改了**采样频率**，档位深度未变；③ 文件体积：08:03 时已达 76.9MB（昨日全天 68MB）⇒ 全天预计 **130–150MB/日**。

**对现有指标的影响（无需重标定）**：`extract_5m_dom_metrics()` 仍以 `sample_interval_ms = 500` 建 600 点网格，源快照按 `idx = (t−start)//500` **覆盖写**（同格后者胜出），`vacuum_*_sec = Σ(格) × 0.5` ⇒ 秒数折算不变、不会 2× 膨胀；**代价是每格较早的那个样本被丢弃**（250ms 信息只利用约一半）。若要吃满密度需把 `sample_interval_ms` 改 250（函数已参数化），但必须**同步审计按「样本计数」比较的阈值**（`raw_snapshots_count` / `samples_count` / `coverage = raw/samples` / `vacuum_min_coverage = 0.20`，期望样本数 600 → 1200），否则会出现覆盖率 >1 之类误判。**当前未切换**（列为待批准项）。

### 二、修复 ①：读取器「成员中段坏区」导致最新成员被跳过，且截断状态不上报

**用户可见症状**：健康巡检显示的 DOM 最新时间**停在 07:33**、`truncated=False`，而文件实际已写到 08:1x。

| 层 | 缺陷 | 修复 |
| :--- | :--- | :--- |
| `PyTools/py_lib/mw_gzip.py` `_iter_member_chunks()` | 捕获成员内 decode 异常后按 `pos` **前进 1 字节**继续找下一个 gzip magic，坏区较大时**永远走不出当前成员**，后续成员（含最新数据）**静默丢失** | 失败时把 `pos` **重置到该成员起点**再 `+MIN_SKIP` 重新同步（`pos = st + 1 if got else max(p, st + MIN_SKIP)`）；同时 `__init__` 补 `self.path`、`.raw` 改惰性 property（见上一节修复） |
| `PyTools/jobs/mw_data_health_check.py` `scan_timestamps()` | 只上报自身判断的截断，**不读取 `fh.truncated`** ⇒ 读取器内部的截断**对上层完全不可见**（静默丢数据） | 改为 `res["truncated"] = res["truncated"] or getattr(fh, "truncated", False)` |

**验证（当日实测）**：

```
修复前：ES_20260914_DOM  lines=18,444,876  last=07:33  truncated=False
修复后：ES_20260914_DOM  lines=19,631,687  last=08:10:26  truncated=True    ← 恢复 1.19M 行 / 37 分钟
巡检后（08:12:02）：lines=19,697,354  first=00:00  last=08:11  truncated=True  桶=96
                    近端 5 分钟桶全为 1；counts={'actionable':0,'ignored':1,'in_progress':1,'ok':7}
```

`truncated` 在健康判定里属**非告警状态**（`TRUNCATED` / `IN_PROGRESS` 与 `OK` 同级展示）⇒ 不会因这次「如实上报」引发告警刷屏。

**回归测试**：新增 `PyTools/jobs/test_mw_reader.py` **7 例**（自造多成员 gzip fixture：正常多成员合并、成员中段坏区后仍取到后续成员、末成员截断、`truncated` 传播到 `scan_timestamps`、空文件、坏文件、`raw` 惰性属性）——全部通过。

### 三、修复 ③：规则手册同步（`gemini_answer-trading_system_rules_manual-…html` / `.md`）

| 位置 | 改动 |
| :--- | :--- |
| §1.2.2 / §1.2.3.3（book_flip「采样与量化基准」） | 补 `sample_interval_ms = 500` 显式标注 + **「⚠️ 采样间隔变更（2026-09-14 07:51:30 起）」** 说明块：实测数据、网格覆盖写口径不变、若切 250ms 必须审计的计数类阈值清单 |
| §1.2.4 / §1.2.3.5（vacuum 定义） | 定义句补注「源采样间隔变更见 §1.2.2 / §1.2.3.3 开头说明；**网格口径与秒数折算不变**」 |
| §1.4.1 / §1.7.1（DOM 覆盖度闸门） | 补注「源间隔 500→250ms，但网格仍 500ms ⇒ **覆盖率口径与阈值不变**，`raw_snapshots_count / samples_count` 分母仍是 600」 |
| 锚点 | 为 §1.2.3.3 标题新增 `id="os-rule-dombookflip"`，两处新交叉引用直链（原先误指 `#os-rule-15` = §3.1.2.1） |

**校验**：`/tmp/validate_manual.py` → 标签配平 0 / 内部锚点缺失 无 / 重复 id 仅既有 `chapter-18` / 残留占位符仅既有 `{anchor`；MD 侧未闭合 `<sub>` 1 处为**改动前既有**（对照 `/tmp/manual_pre_dom250.md.bak` 同为 1）。

### 四、覆盖率闸门的实测复核（本次新发现，已写入手册）

核查「间隔减半会不会动到按计数比较的阈值」时，先核清了 `vacuum_coverage` 的**既有口径**，结论与原先的假设不同：

| 事实 | 数值 / 说明 |
| :--- | :--- |
| `raw_snapshots_count` 到底数什么 | `len(snapshots)`，而 `_read_snapshots()` 的读取起点是 `read_start_dt = start_dt − (iceberg_lookback_min − window_mins)` ⇒ **读取区间是 `[start−25min, end]`（共 30 分钟）**，5 分钟窗口只是其中的尾部 |
| `samples_count` | `num_bins` = 5 分钟 500ms 网格 = **600**（与读取区间无关） |
| 因此 `vacuum_coverage = raw/samples` | **结构性 > 1**（2026-09-14 实测 2.26 / 3.25 / 3.41 / 5.98），它实际是**「读取量代理」**，**不是** 5 分钟覆盖率分数 |
| 间隔减半后的变化 | 分子（同一 30 分钟区间的快照数）近似 ×2 ⇒ `raw/samples` 升至 3.4–6.0；分母仍 600 |
| 对闸门的影响 | 阈值是**下界比较**（`>= 0.20`）⇒ **判定不变**（原本通过者仍通过），但**等效灵敏度减半**：同一阈值现在只要求「一半的读取密度」，一次「读了一半」的坏读取更容易蒙混过关 |
| 建议（待批准） | 若要维持 2026-09-13 标定时的灵敏度，把 `vacuum_min_coverage` 由 **0.20 → ≈0.40**（或把该指标改为**按分钟归一**后再比较）；切换 `sample_interval_ms=250` 时分子分母同时 ×2、比值大致不变，但真空检测分辨率变细（每格 1 个真实样本、不再覆盖写丢弃）⇒ 需重新标定 20s 阈值 |

**实测方式（可复现）**：`extract_5m_dom_metrics("2026-09-14","08:15")` → `samples=600 raw=3589`（比值 5.98）；同一窗口用容错读取器直接统计唯一时间戳 = **677 个 / 5 分钟（2.3 快照/秒，间隔 p50 = 318ms）**，677 × (30/5) ≈ 4.0k 与 3589 同量级，印证「分子含 30 分钟回看」。

上述事实已同步进规则手册：§1.2.2/§1.2.3.3 新增两条明细（口径澄清 + 减半影响 + 建议值），§1.4.1/§1.7.1 补注改写为「(a) 分母不变 (b) 分子近似翻倍 (c) 判定不变但等效灵敏度减半、建议 0.20→0.40」。

### 五、遗留（待用户批准，本次未动）

1. **切换 `extract_5m_dom_metrics(sample_interval_ms=250)`**：需先重标定 `vacuum_min_coverage` 与真空 `>= 20s` 阈值，并复核 `of_contract` 旧键折算系数（清单已见上）。
2. **`vacuum_min_coverage` 0.20 → 0.40**：等效灵敏度补偿（上表最后一行），属规则阈值变更，须用户批准。
3. `NQ_20260913_DOM.csv.gz` 空/损坏文件仍走独立抢救流程（与本次无关）。

> 注：`PyTools/order_flow_analysis/of_contract.py` 的旧真空键注释**已在本轮**标注 deprecated（见上节 ⑤），故不再列为遗留。

### 回滚点

- `PyTools/py_lib/mw_gzip.py`：`/tmp/l0c_bak/mw_gzip.py.pre_resync`
- `PyTools/jobs/mw_data_health_check.py`：`/tmp/l0c_bak/mw_data_health_check.py.pre_trunc`
- 手册 MD / HTML：`/tmp/manual_pre_dom250.md.bak` · `/tmp/manual_pre_dom250.html.bak`
- 本文件：`/tmp/wt04_pre_dom250.bak`

## 2026-09-14 · 追加：ES 250ms / NQ 500ms 的**间隔自适应**落地（用户批准「都执行」）

**用户决策**：「都执行」；并追问「`sample_interval_ms` 是 ES 和 NQ 共用吗？我只把 ES 设成 250，NQ 还是 500ms」。**答案**：DOM 指标路径**只有 ES** —— `extract_5m_dom_metrics()` 硬编码 `find_dom_file(date_str, "ES")`，三个调用点（`order_flow_sentinel` / `mw_dom_recover_and_recompute` / 手册说明）都在 ES 上；NQ 只被数据健康巡检扫描（按体积/时效/时段桶判定，**与采样间隔无关**）。因此本次改动**只影响 ES**，NQ 的 500ms 行为必须原样保留 —— 这也决定了「阈值不能按品种硬编码成 0.40」，必须**随源间隔自适应**。

### 一、实施①：网格间隔自动跟随源间隔

| 项 | 内容 |
| :--- | :--- |
| 新增纯函数 | `estimate_src_interval_ms(ts)`：相邻间隔 **p10 低分位** → 吸附 50ms → clamp [125,1000]（低分位抓住源节奏；中位数会被读取空洞拉大，实测 p50=318ms / p10=259ms） |
| 新增纯函数 | `resolve_grid_interval_ms(explicit, src)`：显式值 > 源间隔 > 500ms 兜底 |
| 签名 | `extract_5m_dom_metrics(..., sample_interval_ms=None, ...)`（原默认 500 → **None = 自动**）；显式传 500 完全保持历史行为 |
| 网格构建 | 由「读文件前」推迟到「读完快照后」，以便先估源间隔；`idx` 分箱与真空秒数折算改用 `_grid_interval_ms` |
| 效果 | **ES（250ms 源）⇒ 250ms 网格 / 1200 点**；**NQ / 旧 ES（500ms 源）⇒ 500ms 网格 / 600 点**；每格 1 个真实快照，不再覆盖写丢弃一半样本 |
| 新增审计字段 | `sample_interval_ms`（实际网格）/ `source_interval_ms`（估出的源间隔）/ `grid_interval_auto` |

### 二、实施②：覆盖度闸门「与源间隔无关」

旧口径 `raw/samples ≥ 0.20` 是**比值**比较：分子随源密度近似翻倍、分母不变 ⇒ 判定不变但**等效灵敏度减半**。改为**绝对条数**（新纯函数 `vacuum_gate_min_raw()`）：

```
min_raw = base(0.20) × 窗口毫秒 / 源间隔毫秒
  500ms 源 ⇒ 120 条   ← 与 2026-09-13 标定完全一致（行为不变）
  250ms 源 ⇒ 240 条   ← 同一「60 秒数据量」含义，灵敏度不被减半
```

`vacuum_min_coverage` 基准**保持 0.20**（不按品种改 0.40 —— 那会误伤 500ms 的 NQ）；新审计字段 `vacuum_min_raw_snapshots` / `vacuum_min_coverage_effective`；`of_contract._vacuum_trustworthy()` 采信优先级改为 **显式 `vacuum_suppressed` → 等效门槛 `vacuum_min_coverage_effective` → 基准 0.20 兜底**（历史行无新键且全是 500ms 源，兜底正确）。

### 三、实施③（核查中新发现并一并修复）：源导出中断造成的「陈旧窗口」

核查 07:45 窗口时发现该窗口**一个快照都没有**，但函数仍返回了「看着正常」的指标。逐行扫描整个文件确认：

```
07:40 之前最后一个快照 : 07:33:29
07:45 之后第一个快照   : 07:51:28
缺口长度              : 18.0 分钟
```

⇒ 当日 **07:33:29 → 07:51:28 源导出整段中断 18 分钟**（正是用户改导出间隔的时段；此前把「last=07:33」全部归因于读取器 bug 的说法据此修正：读取器确实被修好并取回了新成员（18.44M → 19.63M 行），但 07:33→07:51 这段**文件里本来就没有数据**）。
此时 30 分钟读取区间内总快照数（旧快照 + 新成员）仍然很多 ⇒ 旧闸门放行；而窗口内 600/1200 个格子**全部由前向填充的旧盘口填充**（金标准意义上的「静默陈旧」）。

**修复**：新增窗口内判据 —— 窗口内快照数 < 同一 `min_raw` ⇒ 真空一律归零；输出 `dom_window_snapshots` / `dom_window_min_snapshots` / `dom_window_quality`（`OK` / `SPARSE_WINDOW` / `STALE_WINDOW`）。

**实测（2026-09-14，`extract_5m_dom_metrics` 逐窗口）**：

```
time     src grid  bins    raw   win min_win    cov    supp  winq
07:45   None  500   600   1948     0   120.0 3.2467    True  STALE_WINDOW   ← 缺口内：真空归零
07:55    250  250  1200   1358   459   240.0 1.1317   False  OK
08:15    250  250  1200   3589   677   240.0 2.9908   False  OK
08:45    250  250  1200   4650   777   240.0  3.875   False  OK
09:00    250  250  1200   3760   412   240.0 3.1333   False  OK
```

### 四、附带口径变化（已写入手册，未改阈值）

真空秒数由「500ms 网格抽样」变为「250ms 网格全样本」⇒ 实测量更接近真实持续时长，**20s 加分阈值在 250ms 网格下相对更严**（更易被跨过）。本次**未**改动 `bonus_vacuum_sec`，建议按实盘数据回看几日后再评估。

### 五、测试与校验

- 新增 `PyTools/order_flow_analysis/test_dom_interval_adaptive.py`：**16 例全通过** —— 源间隔估计（250/500/被空洞拉大的中位数仍识别 250/clamp 上下限/样本不足/异常输入）、网格解析（显式优先/跟随源/500 兜底）、门槛（500ms=120 与标定一致、250ms=240、`门槛×源间隔 ≡ base×窗口` 的间隔无关性、缺源回退、坏输入、陈旧窗口必低于门槛、配置基准仍为 0.20）。
- 既有回归：`PyTools/jobs/test_mw_reader.py` 7/7 OK；`bbt_data_web/data_app/test_mw_health_window.py` OK。
- `py_compile` + 未定义名扫描：`dom_sentinel_evaluator.py` / `of_contract.py` / `order_flow_config.py` / `order_flow_sentinel.py` 全绿。
- 消费方核查：`bbt_signals.js` 仅把 `samples_count` / `sample_interval_ms` 当遥测文本展示（默认值 600/500，不参与运算）；`mw_dom_recover_and_recompute.py` 只判 `samples_count == 0`；`order_flow_sentinel.py` 日志标签已由固定「(500ms Grid)」改为打印实际网格与源间隔。
- 手册同步（MD + HTML）：§1.2.2 / §1.2.3.3 三条「已实施①/②/追加③」+ 附带口径变化；§1.4.1 / §1.7.1 注记改为「(a) 分母随源间隔 (b) 分子结构性 >1 (c) 绝对条数门槛 (d) 窗口内判据」；`order_flow_config.THRESHOLDS["vacuum_min_coverage"]` 处补「含义 = 500ms 源基准，实际门槛按源间隔换算为绝对条数」。

### 六、回滚点

- `PyTools/order_flow_analysis/dom_sentinel_evaluator.py`：`/tmp/l0c_bak/dom_sentinel_evaluator.py.pre_adaptive`
- `PyTools/order_flow_analysis/of_contract.py`：`/tmp/l0c_bak/of_contract.py.pre_adaptive`
- `PyTools/order_flow_analysis/order_flow_config.py`：`/tmp/l0c_bak/order_flow_config.py.pre_adaptive`
- `PyTools/order_flow_analysis/order_flow_sentinel.py`：`/tmp/l0c_bak/order_flow_sentinel.py.pre_adaptive`
- 手册：`/tmp/manual_pre_adaptive.md.bak` · `/tmp/manual_pre_adaptive.html.bak`
- 本文件：`/tmp/wt04_pre_adaptive.bak`

### 七、遗留（建议，未实施）

1. 若 250ms 网格下真空实测量系统性抬升，需回看实盘数据后决定是否上调 `bonus_vacuum_sec`（20s）。
2. 「窗口内陈旧」目前只作用于**真空列**；失衡类（`imb_*` / `weighted_imbalance`）在 `STALE_WINDOW` 下仍是前向填充值。若要彻底阻断，应让产出端在该情形直接**不落 `dom_metrics`**（或标记为不可用）—— 属规则/数据可用性变更，需另行确认。

## 2026-09-14 · 追加（用户「都执行」）：陈旧窗口拒绝产出、估计器 p02 修正、DB 回刷、`bonus_vacuum_sec` 复核

承接上一节的「遗留（建议）」三项，用户批复「都执行」。

### 一、`STALE_WINDOW` ⇒ 整段拒绝产出（不只归零真空列）

上一节只做了「真空归零 + 质量标记」，但失衡类（`imb_*` / `weighted_imbalance` / `book_flip_*`）在陈旧窗口里
仍是「前向填充的旧盘口」算出的**看似合理**的值 ⇒ 下游（1A/1B 准入、卖家系统机制 ①③）会拿陈旧盘口做决策。

**实现**：窗口内 0 快照（`STALE_WINDOW`）时 `extract_5m_dom_metrics()` **直接返回 `None`**，并打印诊断行：

```
[DOM Sentinel] 2026-09-14 07:40 窗口[07:35:00~07:40:00]内 0 个快照（读取区间快照 07:10:00~07:33:29，源导出可能中断） ⇒ 拒绝产出 dom_metrics（避免用前向填充的陈旧盘口做决策）
```

`None` 复用既有契约「本时段无 DOM 数据」⇒ sentinel 落 NULL / 数据健康标 `NO_DOM` / 规则层 fail-closed。
**`SPARSE_WINDOW`（有数据但低于门槛）仍产出**，只做真空归零 + 打标，避免把「低流动性时段」误判成「无 DOM 数据」。

### 二、估计器修正：p10 → **p02 + 过滤 [125,1000]**

回刷演练时发现 **08:55 窗口被估成 300ms 网格**（源实际 250ms）。实测该窗口的间隔分布：

```
08:55  n=316  min=251  p1=256  p5=266  p10=289  p25=389  p50=657
09:00  n=412  min=253  p1=255  p5=262  p10=271  p25=302  p50=400
08:15  n=677  min=250  p1=250  p5=254  p10=259  p25=283  p50=318
```

⇒ 读取空洞会把高分位整体抬高，`p10` 不稳定（259 / 271 / 289）；**只有极低分位稳定命中源节奏**。
改为「先滤掉 [125,1000] 之外的间隔（滤掉重复时间戳/resync 伪间隔）→ 取 **p02** → 吸附 50ms → clamp」。
修正后三个窗口均估为 **250ms**。新增/更新用例：`test_low_percentile_recognizes_250ms_when_most_gaps_inflated`（真机分布复现，断言 p10 会误判而 p02 正确）、
`test_tiny_gaps_from_resync_are_filtered`、`test_out_of_range_cadences_are_refused`、`test_snap_to_50ms_grid` ⇒ 测试总数 **19 例全通过**。

### 三、DB 回刷（用户批准的一次性写入，脚本 `/tmp/recompute_dom_gap_20260914.py`）

默认 dry-run，`--apply` 才写；写前把 20 条旧 `dom_metrics` 备份到 `/tmp/dom_backup_20260914_adaptive.json`。
只动 `signal_date='20260914' AND ai_model='Rule-Based-5m'` 的目标时段。

| 时段 | 动作 | 结果 |
| :--- | :--- | :--- |
| 07:30 / 07:35 | 重算（源仍是 500ms） | `grid=500 bins=600 src=500 win=527/372 OK` |
| **07:40 / 07:45 / 07:50** | **置 NULL**（缺口内，新口径拒绝产出） | `dom_metrics=NULL` |
| 07:55 – 09:10（15 个时段） | 重算到 250ms 网格 | `grid=250 bins=1200 src=250`，`win=316–888`，`quality=OK`，`vacuum_suppressed=False` |
| 08:05（补洞） | 重算（此前该行为 JSON `null`） | `grid=250 bins=1200 raw=2046 win=888 OK` |

汇总：`recomputed=17 · nulled=3 · failed=0`；另补 08:05 一洞。当日 `06:30–09:20` 的 34 个时段中，
现在**只剩 07:40/07:45/07:50 三行 NULL** —— 精确对应真实的 18 分钟导出缺口。

### 四、`bonus_vacuum_sec` 复核（结论：**不调整**）

方法：同一份 250ms 源、**一次读取**，分别按 250ms / 500ms 网格前向填充重采样，比较真空秒数（脚本 `/tmp/vacuum_grid_ab.py`）：

```
window    snaps cells250 cells500   vac_bid 250/500   vac_ask 250/500
07:55       459     1200      600         0.0 / 0.0         0.0 / 0.0
08:00       781     1200      600         0.0 / 0.0         0.0 / 0.0
08:30      1078     1200      600         0.0 / 0.0         0.0 / 0.0
09:00       442     1200      600         0.0 / 0.0         0.0 / 0.0
09:15       974     1200      600         0.0 / 0.0         0.0 / 0.0
```

两种网格全部为 0.0 ⇒ **无通胀证据**。机制上真空秒数 = 处于「近端单档 < 10 手」状态的**墙钟秒数**；
250ms 网格只是把分辨率 0.5s → 0.25s 并把此前被丢弃的样本纳入统计，**不改变墙钟语义** ⇒ 达到 20s 仍需约 20 秒持续薄档。
故 `bonus_vacuum_sec = 20.0` 本次不动；若后续出现「真空读数密集日」，用同一方法复核后再定（已写入手册 §1.2.2）。

### 五、其它核实

- **源导出当前健康**：当日 93.8MB，文件内最新快照 **09:21:57**（扫描 23,399,830 行），导出在持续写入。
- 上一节把「last=07:33」全归因于读取器 bug 的说法已修正：读取器确已修好并取回新成员，但 **07:33:29–07:51:28 这段文件里本来就没有数据**。
- 手册（MD + HTML）同步：§1.2.2 三条（估计器 p02 / 拒绝产出 / 复核结论）、§1.4.1 注记 (d)。校验：HTML 配平 0、锚点无缺失。

### 六、回滚点（本轮追加）

- `PyTools/order_flow_analysis/dom_sentinel_evaluator.py`：`/tmp/l0c_bak/dom_sentinel_evaluator.py.pre_adaptive`（本轮所有自适应/拒绝产出改动的术前状态）
- 手册：`/tmp/manual_pre_adaptive2.md.bak` · `/tmp/manual_pre_adaptive2.html.bak`
- 本文件：`/tmp/wt04_pre_adaptive2.bak`；索引：`/tmp/mods_pre_adaptive2.html.bak`
- **DB 回滚**：`/tmp/dom_backup_20260914_adaptive.json`（20 条旧 `dom_metrics`，按 id 还原即可）
