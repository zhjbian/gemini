# 深度 DOM 200 档采集与 Adam Set 四大核心特征落地实施计划

本计划旨在将 MotiveWave 中的 DOM 数据采集从原有的 10 档（2.5点）扩展至 **上下 50 点（原生 200 档 Tick）**，并采用 **`.csv.gz` 流式 GZIP 压缩** 彻底解决文件膨胀问题；同时在 Python 端与 AI 研判端落地 Adam Set 的四大核心微观订单流特征。

## User Review Required

> [!IMPORTANT]
> 1. **GZIP 格式兼容性**：Java 端默认输出为 `ES_YYYYMMDD_DOM.csv.gz`。Python 的 `pandas.read_csv` 原生支持直接读取 `.csv.gz`，无需解压即可无缝读取。
> 2. **GUI 控件与兼容性**：保留原有设置项并扩展：
>    * `MAX_DEPTH_LEVELS`：上限由 50 解锁至 250（默认 200）。
>    * `DEPTH_RANGE_POINTS`：新增价格跨度（默认 50.0 点）。
>    * `COMPRESS_GZIP`：新增开关（默认 true，输出 `.csv.gz`）。
>    * 若用户关闭 GZIP 开关，仍可输出普通 `.csv`。

---

## Proposed Changes

### Java 采集层 (`BBT_Studies`)

#### [MODIFY] [StudyOrderFlowDataExporter.java](file:///Users/zhijiebian/Intellj-workspace/BBT_Studies/src/bbt/StudyOrderFlowDataExporter.java)
1. **设置描述符升级**:
   * 将 `MAX_DEPTH_LEVELS` 的上限从 50 修改为 250，默认值由 10 修改为 200。
   * 新增 `DoubleDescriptor("DEPTH_RANGE_POINTS", "Depth Range (Points)", 50.0, 5.0, 100.0, 5.0)`。
   * 新增 `BooleanDescriptor("COMPRESS_GZIP", "Compress DOM with GZIP (.csv.gz)", true)`。
2. **GZIP 流式写入与追加实现**:
   * 重构 `domWriter` 的创建逻辑：当 `COMPRESS_GZIP` 为 true 时，使用 `new GZIPOutputStream(new FileOutputStream(file, true))` + `OutputStreamWriter(..., StandardCharsets.UTF_8)` + `PrintWriter`。
   * 针对 `.gz` 文件的最后时间戳检测（`getLastTimestampFromFile`）：由于压缩文件无法用 `RandomAccessFile` 直接从末尾逆向读取纯文本，增加对 `.csv.gz` 的解压流式尾部时间戳解析器或辅助时间戳缓存，避免重复写入与去重失效。
3. **50 点价格区间过滤与深度提取**:
   * 在 `update(DOM dom)` 中，计算当前市场基准价（当前价或买一卖一中间价 `midPrice`）。
   * 遍历 `bids` 与 `asks` 时，仅提取满足 `abs(row.getPrice() - midPrice) <= depthRangePoints` 且档位索引小于 `maxLevels`（最高 200）的所有挂单。
   * 增加队列吞吐与批处理能力（每次循环 drain 上限从 10000 提升至 50000），确保快节奏行情下无内存溢出。
4. **编译与部署**:
   * 使用 `ant -f build.xml deploy` 编译生成类文件并自动热部署至 `/Users/zhijiebian/MotiveWave Extensions/dev`。

---

### Python 特征工程层 (`BBTrading`)

#### [MODIFY] [order_flow_feature_generator.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/order_flow_feature_generator.py)
1. **文件发现兼容 `.csv.gz`**:
   * 扩展 `glob` 扫描逻辑，优先加载 `ES_{date}_DOM.csv.gz`，若不存在则回退加载 `ES_{date}_DOM.csv`。
2. **动态多档位解析**:
   * 废除硬编码的 `range(10)` 循环，动态检测实际提取到的全部档位（0 至 199 档）。
3. **计算 Adam Set 4 大核心特征**:
   * **多层级失衡度 (Multi-Tier Imbalance)**:
     * `imbalance_near`（近端 1~5 档，0-4）：反映瞬时突破阻力
     * `imbalance_mid`（中端 6~20 档，5-19）：反映 5 个点微观波段支撑/阻力
     * `imbalance_deep`（深层 21~200 档）：反映 50 点宏观挂单池大局厚度
   * **挂单堆叠与撤单追踪 (Stacking vs Pulling / Spoofing)**:
     * 计算主要价格阶梯上的挂单量时间导数 `Delta_Depth(t)`。
     * 当价格靠近关键位时挂单激增判定为 `Stacking`，若在临界 1-2 Tick 骤降判定为 `Spoofing Pulling`。
   * **冰山与被动吸收检测 (Passive Absorption)**:
     * 结合 `total_vol`、`tick_delta` 与 `price_change == 0`，对齐该价位的持续挂单消耗与补充，标记被动买盘吸收（看涨反转）与被动卖盘吸收（看跌反转）。
   * **流动性真空 (Liquidity Vacuum)**:
     * 标记前 10 档平均单档挂单量降至个位数（< 10 手）的时间区间与价格带。

### Python 数据归档与自动清理层 (`BBTrading`)

#### [NEW] [cleanup_old_order_flow_raw.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/cleanup_old_order_flow_raw.py)
* **现状**: 当前 `Raw/` 目录已积压 **51GB** 历史未压缩的 CSV 文件（追溯至 2026 年 5 月）。
* **自动化清理方案**:
  1. **保留周期 (Retention Policy)**:
     * 默认保留最近 **14 天**（可配置参数 `--days 14`，保障近两周回测与排查需求）。
     * 对超过保留期的 `*_DOM.csv` 与 `*_TICKS.csv` 自动清理删除。
  2. **存量历史压缩 (Backfill Compression)**:
     * 提供 `--compress-only` 选项：对未到删除期但未压缩的历史 `.csv` 自动转为 `.csv.gz`，预计可直接释放 **35GB ~ 40GB** 磁盘空间。
  3. **基于文件日期的安全校验 (Safety Lock)**:
     * 严格按文件名中解析出的 `YYYYMMDD` 计算账龄，绝不误删包含今天或未来日期的正在写入文件；支持 `--dry-run` 预览拟清理列表与释放空间。
  4. **零点自动联动**:
     * 可在 Java 端每日零点切割文件时或由每日特征处理管道自动静默调用此脚本。

---

### Python AI 研判决策层 (`BBTrading`)

#### [MODIFY] [ai_tape_analyst.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/ai_tape_analyst.py)
1. **统计指标提取**:
   * 在 `analyze_time_window()` 与 `get_session_stats()` 中，将上述 4 大特征（多梯队失衡、Stacking/Spoofing、Iceberg 吸收、真空带）汇总为结构化字段。
2. **Prompt 升级（全面对齐 Adam Set 拍卖理论与微观结构）**:
   * 将 50 点全景深度、挂单筑墙与闪烁撤单、冰山防御位、流动性真空注入系统 Prompt，要求 Gemini 按 Adam Set 的专业口吻输出判断。
3. **前端渲染与报告升级**:
   * 在生成的实时 HTML 监控卡片中，展示近端/中端/深端失衡仪表板与冰山吸筹标记。

---

## Verification Plan

### 1. Java 编译与热部署验证
* 运行 Ant 部署命令：
  ```bash
  ant -f /Users/zhijiebian/Intellj-workspace/BBT_Studies/build/build.xml deploy
  ```
* 检查 `/Users/zhijiebian/MotiveWave Extensions/dev/bbt/StudyOrderFlowDataExporter.class` 是否成功更新，`.last_updated` 时间戳是否刷新。

### 2. 导出文件与 GZIP 压缩有效性验证
* 在 MotiveWave 中运行或回放一段数据，验证是否成功生成 `ES_YYYYMMDD_DOM.csv.gz`。
* 验证行数覆盖范围（是否达到 200 档 / 上下 50 点）。
* 验证文件体积是否保持在原本未压缩 1/8 左右。
* 验证 Python `pd.read_csv("...DOM.csv.gz")` 能否秒级直接打开并解析。

### 3. 特征生成与 AI 分析端到端验证
* 运行 `order_flow_feature_generator.py` 对测试日期生成分析结果：
  ```bash
  /usr/local/bin/python3 /Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/order_flow_feature_generator.py -d 20260828 -s ES -f
  ```
* 运行 `ai_tape_analyst.py` 验证 4 大特征解析与 Gemini 研判输出：
  ```bash
  /usr/local/bin/python3 /Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/ai_tape_analyst.py
  ```
