# 深度 DOM 200 档采集与 Adam Set 四大核心特征落地总结

本阶段已全面完成 MotiveWave Java 端 DOM 采集升级、流式 GZIP 压缩、定期数据清理工具、Python 端多梯队特征计算以及 AI 研判决策链路的对齐改造。

---

## 一、 完成的核心变更

### 1. Java 采集层 (`BBT_Studies`)
* **[StudyOrderFlowDataExporter.java](file:///Users/zhijiebian/Intellj-workspace/BBT_Studies/src/bbt/StudyOrderFlowDataExporter.java)**:
  * **深度解锁至 200 档**: 将 `MAX_DEPTH_LEVELS` 上限解锁至 `250`（默认值由 10 调整为 `200`，完全覆盖 ES 上下 50 点范围）。
  * **50 点价格区间过滤**: 新增 `DEPTH_RANGE_POINTS` 参数（默认 `50.0` 点），在 `update(DOM dom)` 中以市场中间价为基准动态筛选 `abs(price - midPrice) <= 50.0` 的所有挂单。
  * **流式 GZIP 压缩 (`.csv.gz`)**: 新增 `COMPRESS_GZIP` 开关（默认 `true`）。直接通过 `java.util.zip.GZIPOutputStream` 流式写入 `.csv.gz`，将单日文件体积压缩 **85%~90%**。
  * **异步队列吞吐扩容**: 将 `domQueue` 单词批量处理上限由 10000 提升至 `50000`，确保 200 档高频写入零卡顿。
  * **零点自动联动清理**: 每日零点切割文件时，自动异步触发历史过期数据清理脚本。
  * **热部署生效**: 已通过 `ant -f build.xml deploy` 编译并热部署到 `/Users/zhijiebian/MotiveWave Extensions/dev`。

### 2. Python 数据管理与归档层 (`BBTrading`)
* **[cleanup_old_order_flow_raw.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/cleanup_old_order_flow_raw.py)**:
  * **自动清理过期文件**: 默认安全清理保留期（14 天）以外的 `*_DOM.csv` 与 `*_TICKS.csv`。
  * **存量 GZIP 压缩**: 支持将未压缩的历史文件原地转换为 `.csv.gz`，释放数十 GB 空间。
  * **安全保护机制**: 基于文件名日期严格保护今日与未来活跃文件；支持 `--dry-run` 预览。

### 3. Python 特征工程层 (`BBTrading`)
* **[order_flow_feature_generator.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/order_flow_feature_generator.py)**:
  * **`.csv.gz` 透明支持**: 新增 `find_file` 智能检索，原生直接读取 `.csv.gz`。
  * **动态多档位解析**: 移除旧有的 10 档限制，自适应解析 0 至 199 档全部深度。
  * **落地 Adam Set 四大核心特征**:
    1. **多梯队失衡度**: `imbalance_near` (近端 1~5 档)、`imbalance_mid` (中端 6~20 档 / 5点)、`imbalance_deep` (深层 20~200 档 / 50点)。
    2. **挂单堆叠与撤单追踪 (Stacking vs Spoofing)**: 计算差分，识别 `spoofing_pull_bid`、`spoofing_pull_ask`（闪烁撤单）与 `stacking_bid`、`stacking_ask`（筑墙防御）。
    3. **冰山被动吸收检测**: 细化识别 `iceberg_absorption_bull`（负 Delta 价格不跌，买方冰山吸筹）与 `iceberg_absorption_bear`（正 Delta 价格不涨，卖方冰山拦截）。
    4. **流动性真空**: 标记 `vacuum_bid` 与 `vacuum_ask`（近端单档挂单 < 10 手的高滑移真空区）。

### 4. Python AI 研判与报表层 (`BBTrading`)
* **[ai_tape_analyst.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/ai_tape_analyst.py)** & **[order_flow_html_renderer.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/order_flow_html_renderer.py)**:
  * 在 `get_session_stats` 中汇总 Adam Set 4 大特征指标。
  * 在系统 Prompt 中新增专门的 **`Section 9. Adam Set 核心 DOM 盘口微观结构`**，将 50 点宏观深度、冰山防御点位、撤单异动与真空带直接作为最高优先级输入注入给 Gemini。
  * 在生成的 HTML 实时监控卡片中直接渲染呈现多梯队失衡、堆撤单异动与冰山真空统计。

---

## 二、 验证结果

1. **Java 编译与部署**:
   * `ant -f build.xml deploy` 编译耗时 1 秒，成功将 `StudyOrderFlowDataExporter.class` 部署至 MotiveWave Extensions 目录。
2. **特征工程端到端测试**:
   * 对 `2026-08-28` 执行特征提取，全量 243,021 条记录均成功计算出 `imbalance_near`, `imbalance_mid`, `imbalance_deep`, `spoofing_pull_bid`, `stacking_bid`, `iceberg_absorption_bull` 等字段，保存至 `ES_ANALYSIS_2026-08-28.h5`。
3. **AI 研判与报表生成测试**:
   * 运行 `analyze_realtime_accumulation("09:30", "2026-08-28", symbol="ES")`：
   * 成功读取新特征，生成包含 Section 9 DOM 微观结构的 Prompt，并顺利在 `/Users/zhijiebian/Documents/MyDoc/Finance/Current/MotiveWave_OrderFlow_Data/Realtime/es_order_flow_realtime_2026-08-28.html` 中渲染出全新的 DOM 统计卡片。
5. **周日 Globex 实盘实时数据检测验证 (2026-08-30 15:00 - 15:30 PST)**:
   * **文件流式采集**: MotiveWave 实时持续写入 `ES_20260830_DOM.csv.gz`（体积约 3.6MB，解压相当于 34MB+ 纯文本，压缩比约 10:1）；
   * **200 档全景深度覆盖**: 实盘采集确认档位达到 `Level 0 ~ 199`，价格跨度覆盖 `7655.25 ~ 7772.75`（上下超过 50 点范围）；
   * **流式 GZIP 安全读取**: Python `safe_read_csv` 成功解决活跃追加写入时的未封闭 EOFError，实现无锁实时读取；
   * **Adam Set 4 大特征即时推演**:
     * 盘口多梯队失衡度：近端 `imb_near` (-0.057)、中端 `imb_mid` (-0.004)、深端 `imb_deep` (-0.025)；
     * 冰山被动吸收：成功检测出 18 次看多冰山吸收与 39 次看空冰山拦截；
     * 核心吸收点位：`7706.00`（6次/158手，看空吸收）、`7723.50`（1次/105手，看空吸收）、`7713.00`（3次/20手，看多吸收）；
     * 流动性真空识别：开盘高流动性切换期捕获 1,408 次买单真空与 965 次卖单真空；
     * 走势与 Delta 匹配：价格由 `7723.50` 震荡回踩至 `7712.00`，Delta 累积为 `-228`，定性为精准的「空头打压」结构。
