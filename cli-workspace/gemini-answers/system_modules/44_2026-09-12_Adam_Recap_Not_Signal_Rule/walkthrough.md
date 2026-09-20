# Adam 分类改进：回顾/确认帖不算信号（2026-09-12）

# 44. Adam 分类改进：回顾/确认帖不算信号（Recap ≠ Signal）

日期 2026-09-12 ｜ 关联 x_posts_adam_signal_v2.py / x_posts / Adam 深度分析链

## 1. 问题（真实误判）

2026-09-11 07:37:39 的帖被判为 is_signal=1 / bullish / reversal_bottom / scope=swing，实际内容是：

```
7590 is the Low of this Move.
Strong Support rallies this +90p Overnight.
I called this a Day Early-- it was.
--- Quoted ---
[Posted at 09/10/2026 07:14:21] $ES : 7590 : Shows Strong Support at Open. …
```

该帖引用自己前一天的帖并确认其正确（"I called this a Day Early"）⇒ 它是对过去信号的确认，不是新信号。而 Adam今日信号深度分析 把帖子的时间戳当作信号时刻，分析其前后 order flow ⇒ 对该帖而言时间戳无意义，不应纳入。

## 2. 改进内容

| 项 | 改动 |
|---|---|
| Prompt 规则 R | 新增「RECAP / CONFIRMATION POSTS ARE NOT SIGNALS」：若帖子主要回顾自己更早的信号（引用/转发自己的旧帖，或 "I called this" / "as I said" / "a day early" / "confirmed" / "this played out" 等措辞）⇒ is_signal=false, scope="none", signal_kind="commentary", conviction=null, importance=1, refers_prior=true；例外：若同时给出面向当下、可操作的新方向/价位 ⇒ 仍算信号，但置 refers_prior=true 以便下游识别其中的回顾成分。 |
| Prompt 规则 S | 显式写明：全部规则对多空同一标准（沿用对称性要求）。 |
| 新字段 | x_posts.refers_prior（tinyint ✓ 带注释）+ ORM（models.py 的 XPost ✓ 已校验为真列）+ 分类器写入 + prompt schema refers_prior (bool) |
| 版本 | LABEL_VER: v2-symmetric-switch-intraday → **v3-recap-aware**（规则变更必须升版，便于区分新旧标注） |
| 清理联动 | 该帖改判后立即清除其 adam_deep_payload 并从 adam_research_reports.sections 摘除整块（复用「判定非信号」端点逻辑 ✓） |

## 3. 验收（实测）

| 项 | 结果 |
|---|---|
| 重标注该帖（--post-id … --no-notify） | ✓ 模型证据引用了 "I called this a Day Early-- it was" |
| 字段结果 | is_signal=0 · signal_kind=commentary · scope=none · conviction=None · importance=1 · refers_prior=1 · label_ver=v3-recap-aware ✓ |
| 清理缓存（端点） | payload_removed=1 · report_rows_updated=1 · HTTP 200 ✓ |
| 深度分析区块 | 2026-09-11 帖块 1 → 0，该帖已彻底退出 ✓ |
| API 复核 | 09-11 帖块 0；09-10 / 09-09 未受影响（1 / 3 帖块）✓ |

## 4. 后续（需注意 ⚠️）

- watcher 会分批重标注全部历史帖（com.bbt.adam-classifier-watch，每 120 秒 --limit 25）⇒ 约 1,689 帖将在 2–3 小时内逐步换用新规则 ⇒ Adam 统计口径会随之变化（这正是修此类误判所必需；如需控制时点可临时停 watcher）。
- 需要一次"非信号剪枝"：重标注后会出现更多 is_signal=0 的帖，但它们的 adam_deep_payload 与已存报告副本仍在 ⇒ 需批量摘除（脚本化，复用端点逻辑）。
- 当某日所有帖都被判非信号时，该日深度分析区块只剩标题 ⇒ 可加占位文案「本日无可验证的方向性信号」。

## 5. 回滚

```
DB:   alter table x_posts drop column refers_prior;
文件: /tmp/xposts_sig.bak-recap-*   (分类器)   /tmp/models.py.bak-recap-*  (模型)
说明: LABEL_VER 改回 v2-symmetric-switch-intraday 即恢复旧规则（但该帖需另行还原）
```

