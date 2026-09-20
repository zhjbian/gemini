# DeepSeek Harness for VS Code 用量审计：$10 消耗根因与优化

## DeepSeek Harness for VS Code 用量审计：$10 消耗根因与优化

### 结论

**不是泄漏、也没有 bug —— 是你的会话上下文涨到 40–80 万 token，而「每一步」都要把整个上下文重发一次并计费。** 你那 $10 对应的是 **近 12 小时内 4 个会话、1276 次模型调用、5.29 亿 cache-read token**（平均每次调用上下文 **414,665 token**）。

### 账单从哪来（本机会话日志实测，非推测）

数据源：`harness-home/sessions/**/session.jsonl.zstd`（每次 `assistant/message` 都带 `usage`，字段：`inputTokens` / `outputTokens` / `cacheReadTokens` / `reasoningTokens`）

| 会话 | 调用次数 | cacheRead(命中) | 平均上下文/次 | 时间跨度 |
|---|---|---|---|---|
| `dsh-mtrin7v6-lqfl4g` | **4,598** | **2,121,341,247** | 462,014 | 09-07 → 09-13 |
| `dsh-mu01uk6z-pxqz1v` | 2,295 | 878,053,504 | 382,594 | 09-13 → 09-14 |
| `dsh-mu0gxyzz-qpsl52`（**本会话**） | 1,517 | 597,644,288 | 394,224 | 09-13 → 今 |
| `dsh-mu266unj-ctkx2m` | 574 | 208,021,248 | 362,406 | 09-14 晚 → 今 |
| `dsh-mtvy51q5-d7r593` | 431 | 189,645,312 | 440,012 | 09-10 → 09-11 |
| `dsh-mu1m9116-yg6wtg`（**ES 缺 bar 那个**） | 378 | 147,605,501 | 390,490 | 09-14 15:27→20:24 |
| 其余 10 个（多为子代理） | 221 | 15,589,568 | ~60,000 | — |
| **合计** | **10,014** | **4,157,900,668** | — | — |

**近 12 小时（≈你的 $10 窗口）**：4 会话 / **1,276 次调用** / cacheRead **529,116,088** / input 1,895,512 / output 1,253,336。

总量（09-07 → 09-15 全部会话）：`cacheRead 4,157,900,668` · `input(未命中) 14,226,719` · `output 10,117,566` · `reasoning 4,494,292`；cache-miss 占比仅 **0.34%** ⇒ 缓存命中率 99.6%。

**上下文增长曲线（每个会话都是从 3 万涨到 70–80 万）**：

```
mtrin7v6-lqfl4g  首轮 28,170 → 中位 418,011 → 末轮 775,239 → 峰值 800,357
mu0gxyzz-qpsl52  首轮 31,348 → 中位 357,979 → 末轮 652,635 → 峰值 793,729
mu1m9116-yg6wtg  首轮 32,277 → 中位 406,304 → 末轮 701,000
mu266unj-ctkx2m  首轮 31,358 → 中位 628,185 → 峰值 794,818
mu01uk6z-pxqz1v  首轮 31,434 → 中位 167,247 → 末轮 433,806 → 峰值 795,582
mtvy51q5-d7r593  首轮 30,498 → 中位 418,619 → 末轮 760,873 → 峰值 799,367
```

**机制**：成本 ≈ Σ(每一步的上下文大小)。会话从 3 万涨到 80 万、跑了 1500 步 ⇒ 1500 × 平均 40 万 ≈ **6 亿 token**。所以「2 个任务」其实是 2 个**长时自主运行**（`mu1m9116` 378 次调用、本会话 1517 次），加上另外 2 个并行会话同时计费。

**缓存是正常的**：cache-miss 只占 0.34%（14.2M / 4.17B），说明命中率 99.6%，已经是便宜的缓存价 —— 不是缓存失效导致的暴烧。

**排除项**：后台 Adam 分类守护（`com.bbt.adam-classifier-watch`，`StartInterval=120`，命令 `python3 x_posts_adam_signal_v2.py --provider deepseek --limit 25`）日志 408KB 里绝大多数是「✓ 无待分类帖」，**无新帖时不调 LLM** ⇒ 不是主因（有新帖时会分类，可留意）。另一个 `npx @deepseek-ai/dsh@latest web` 实例（端口 3080，PID 45736）会话目录停留 09-09，也基本闲置。

模型口径（全部 `reasoningEffort=high`、`maxTokens=256000`）：`deepseek-v4-flash`（mtrin7v6）、`deepseek-v4-flash-vision-exp`（mu01uk6z / mu0gxyzz / mu1m9116 / mtvy51q5）、`deepseek-v4-pro`（mu266unj）。

### 为什么压缩没能救回来

harness 自带压缩（`dsh-compaction` + `dsh-compaction-basic` + `dsh-compaction-tool-result-pruner`），但**默认阈值很宽**：

- `dsh-compaction-basic`：`thresholdRatio = 0.8`（上下文到窗口 80% 才压缩）、`retainRatio = 0.16`（压完仍保留 16%）
- 另有 `thresholdTokens` / `retainTokens` 可覆盖，`auto`（bool）、`modelPolicies`、`summarizationModel` 等
- `dsh-compaction-tool-result-pruner`：`thresholdChars` / `headChars` / `tailChars`（裁剪超大工具结果）

⇒ 上下文长期在 **30 万 ~ 80 万** 之间徘徊，每一步都在为这个体量付费。（本会话确实触发过 3 次压缩：`compaction/start ×3`、`compaction/summary ×2`、`compaction/prune ×12`，但依然如此。）

### 建议（按收益排序）

| 措施 | 预期效果 |
|---|---|
| **① 新任务开新会话**（别在 40–80 万上下文的会话里 continue） | 上下文回到 3–5 万 ⇒ **单步成本降 8–20 倍** |
| **② 调紧压缩**：`compaction.thresholdRatio` 0.8→**0.15**、`retainRatio` 0.16→**0.08**（写进 `harness-home/settings.yaml`） | 上下文封顶 ~12 万 ⇒ **总成本降约 4–5 倍** |
| **③ 打开工具结果裁剪**：`dsh-compaction-tool-result-pruner.thresholdChars` 调小 | 大输出不再永久驻留上下文 |
| ④ 不要同时跑多个大会话 | 账单份数线性下降 |
| ⑤ `reasoningEffort: high` → medium/low；`v4-pro` → `v4-flash` | 输出/推理 token 与单价双降（注：output+reasoning 合计约 14.6M，相对 cacheRead 4.16B 占比很小，收益远小于 ②③） |
| ⑥ 归档 `dsh-mtrin7v6-lqfl4g` 并别再 continue | 它一只占**全部用量 51%** |
| ⑦ 平台侧设**消费限额/告警**（platform.deepseek.com） | 防止再次静默烧完 |
| ⑧ 让 agent 别把巨型文件打进上下文（本次调查中 dump minified 包也加剧了） | 抑制膨胀速度 |

**最大单项**：②③ 是纯配置、立刻生效、风险最低（只影响压缩时机，不改行为语义）；①⑥ 是使用习惯，收益最大。

## 配置与修复实施：压缩阈值调紧 + 确认信息必达（补丁10 / 补丁11）

### （1）gem-doc 已保存完整报告

| 文件 | 大小 |
|---|---|
| `gemini_answer-dsh_vs_code_token_burn_usage-2026-09-15_06-49-19.html` | 17.1 KB |
| `gemini_answer-dsh_vs_code_token_burn_usage-2026-09-15_06-49-19.md` | 5.6 KB |

路径：`/Users/zhijiebian/.gemini/cli-workspace/gemini-answers/`

标题：**DeepSeek Harness for VS Code 用量审计：\$10 消耗根因与优化**；四个 h2 小节（结论 / 账单从哪来 / 为什么压缩没能救回来 / 建议），浅色主题；**未做任何压缩摘要**，全部原始数字、表格与代码块原样保留。

### （2）配置与修复已按建议实施（走唯一入口 `scripts/repatch_vscode_changes_bar.py`）

#### 关键发现（决定了修复方式）

- **真实上下文窗口 = 1,000,000 token**（会话日志 `request/context` 实证）。
- **旧默认压缩口径**：`thresholdRatio 0.8` / `retainRatio 0.16` ⇒ **涨到 800,000 才压缩、压完仍留 160,000** —— 这与实测峰值 **800,357** 完全吻合，就是暴烧的根源。
- **`dsh-compaction-basic` 不读 `settings.yaml`** ⇒ 只能改**预设文件**（`dsh/config/agent-presets/<preset>/agent.cordis.yml`）。
- `dsh-token-meter` 的 Config 是空对象 ⇒ **harness 没有内置 token 预算/熔断**，所以平台侧限额（建议⑦）不可省。

#### 已改动（新增「补丁11：压缩阈值调紧」）

对 **3 个预设**（`standard` / `code` / `cordis`）写入：

```yaml
    - id: compaction-basic
      name: '@deepseek-ai/dsh-compaction-basic'
      config:
        thresholdRatio: 0.15      # 0.8  → 触发点 800,000 → 150,000 tok
        retainRatio: 0.08         # 0.16 → 压缩后保留 160,000 → 80,000 tok

    - id: tool-result-pruner
      name: '@deepseek-ai/dsh-compaction-tool-result-pruner'
      config:
        thresholdChars: 4096      # 8192
        headChars: 2048           # 4096
        tailChars: 512            # 1024
```

**预期**：平均上下文 ~400K → **~115K**，单步成本约降 **3.5 倍**（`\$10` 从"12 小时烧完"变成"约 2 天"）；且 80K→150K 的间隔足够大，不会导致压缩过于频繁。

#### 验证

| 检查 | 结果 |
|---|---|
| `--dry-run` 锚点 | 3 个预设全部命中 ✓ |
| 实跑 | 3 个文件全部 `config` 写入 ✓ |
| YAML 结构（用支持 Cordis `!!js` 标签的 loader 解析） | 3/3 解析 OK，读出 `{'thresholdRatio': 0.15, 'retainRatio': 0.08}` ✓ |
| 幂等复跑 | `[补丁11] … 已调过, 跳过 ✓` ✓ |
| 既有补丁回归 | 补丁1–9「生效: 是」、补丁10「已打过」、`node --check` ×2 OK ✓ |
| 备份 | `agent-presets/{standard,code,cordis}/agent.cordis.yml.bbt-bak` ✓ |

#### 需要你做一步（与补丁10 同一次重载即可）

`Cmd+Shift+P` → **Developer: Reload Window**

重载后**立即见效的两件事**：

1. 你现在这个会话的上下文已 ~65 万 > 15 万 ⇒ **下一次请求就会触发压缩，降到 ~8 万**（单步成本当场降 ~8 倍）。
2. 之后所有新会话的上下文都会在 **8 万 ~ 15 万** 之间波动。

**验收命令**（重载跑一会儿后执行；应看到 `compaction/start` 时的上下文在 15 万左右，而不是 80 万）：

```bash
zstdcat ~/Library/Application\ Support/Code/User/globalStorage/skymecode.deepseek-harness-for-vscode/harness-home/sessions/*/*/session.jsonl.zstd \
 | grep -o '"type":"compaction/start"[^}]*' | tail -5
```

#### 回滚

| 范围 | 方式 |
|---|---|
| 只撤压缩调参 | 重跑加 `--no-compaction-tune`，或直接用 `agent-presets/*/agent.cordis.yml.bbt-bak` 覆盖回去 |
| 全局回滚 | `--revert`（从 `*.bbt-bak` 还原全部补丁） |
| 重新调参 | `--compact-threshold-ratio 0.25 --compact-retain-ratio 0.12 --prune-threshold-chars 8192` |
| 脚本本体 | 快照 `/tmp/repatch_pre_mod59_tune.py.bak` |

#### 我没有做、建议你手动做的（避免影响业务数据）

- **① 新任务开新会话**：这是省钱最大的一项（上下文回到 3–5 万，单步成本再降 3 倍以上）—— 属于使用习惯，我无法配置。
- **⑥ 归档 `dsh-mtrin7v6-lqfl4g`**（占全部历史用量 **51%**，2.12B）：我没有动你的会话数据；要不要我调 gateway API 归档（可 `restoreSession` 一键恢复）？
- **⑦ 平台侧消费限额/告警**（platform.deepseek.com）：只能你在网页设；harness 没有内置预算熔断，这道防线不可省。
- **⑤ 降 effort / 换便宜模型**：我核算过 —— 输出+推理合计仅 ~14.6M token，相对 4.16B cacheRead 占比极小，**降档省不到钱却会掉质量**，所以没有改。

