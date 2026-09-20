# Adam 信号重要性评级（2026-09-12）

# 43. Adam 信号重要性评级（AI 定级 + 页面可人工覆盖）

日期 2026-09-12 ｜ 关联 x_posts / bbt_data_web / x_posts_adam_signal_v2.py

## 1. 需求

- Adam 的信号有日内小波动与大趋势反转之分 ⇒ 需用固定评级标准记录「信号重要性」
- 评级：1–5 打分并存对应文字等级
- AI 判定 signal 时一并给出该评级
- 页面必须可人工 override
- 与既有 conviction 区分：Conv＝「他有多确信」，Importance＝「该信号对交易有多重要」⇒ 两字段并存

## 2. 固定评级标准（imp-v1，通用且多空对称）

| 分值 | 文字 | 判据（固定，不看具体某日） |
|---|---|---|
| 5 | Critical（极高） | 多日/波段级别的趋势反转或拐点：明确关键价位 + 方向 + 结构结论（如"这是本轮下跌的底"） |
| 4 | High（高） | 波段级别方向判断或关键价位（构成持仓去留依据） |
| 3 | Medium（中） | 明确的日内方向/价位观点（当日可操作） |
| 2 | Low（低） | 短时/小波动观察（日内噪音级） |
| 1 | Noise（噪音） | 闲聊/情绪/无方向（与交易无关） |
| NULL | 未评定 | — |

三个判据维度：① 时间级别（日内 ↔ 波段/多日）② 明确性（是否给方向 + 价位）③ 可操作性（能否作为交易/仓位依据）；多空同一标准（避免看多严、看空松 ✗）。

## 3. 实施（改了哪些文件）

| 层 | 改动 | 说明 |
|---|---|---|
| DB | x_posts 新增 importance tinyint · importance_src varchar(8) · importance_ver varchar(24) | 均有列注释；src 记录 ai/user ⇒ 覆盖可追溯 |
| ORM | bbt_data_web/models.py 的 XPost 加 3 列 | 已用 InstrumentedAttribute 校验为真列（避免历史"假列"事故） |
| 分类器 | PyTools/jobs/x_posts_adam_signal_v2.py：新增 IMPORTANCE_VER="imp-v1" 与 IMPORTANCE_RUBRIC；prompt schema 加 importance (1-5)；写入 p.importance / importance_src='ai' / importance_ver | 加法式改动，且 LABEL_VER 未变 ⇒ 不触发全量重跑；仅新帖自动获得评级 |
| API | bbt_data_web/data_app/x_posts.py：行数据返回 importance/importance_src；/data/update_x_post_signal 接受 importance，写入时置 src='user' | 空值可清空；异常值静默忽略 |
| 页面 | templates/x_posts.html 在 Conv 之后新增 Imp 列（17 列）；static/js/x_posts.js 新增下拉渲染（1–5 + 文字 + tooltip）+ Update 负载带 importance | 人工覆盖后显示 ✎ 标记；列宽遵循既有"窄列按内容收缩"策略 |

## 4. 验收（已完成项）

| 检查 | 结果 |
|---|---|
| DB 三列存在 | ✓ |
| XPost ORM 映射 | ✓ 三列均为真列 |
| 分类器语法 + 可导入 | ✓（LABEL_VER 未改动 ✓） |
| prompt 含固定评级标准 | ✓（"5 = multi-day …" 已内联） |
| API 语法 / 页面 HTTP | ✓ 200 |
| 模板 17 列 = JS 17 列（Imp 紧随 Conv） | ✓ 一致 |
| node --check | ✓ 通过 |
| 接口返回 importance 字段 | ✓（历史行暂为 None ✓ 见下） |

## 5. 待办

- 历史回填：现有 1,689 行 importance 为 NULL（因 LABEL_VER 未变 ⇒ 分类器不会重跑旧帖）。方案：写一个只写 importance 的回填脚本（--importance-only 风格，不触碰既有标签）⇒ 待执行
- 页面硬刷新（⌘⇧R）后人工试一次覆盖 ⇒ 确认 ✎ 标记与 src='user' 落库
- （可选）在 adam_feature_* 统计里按 importance 分层做验证率分析

## 6. 回滚

```
DB:   alter table x_posts drop column importance, drop column importance_src, drop column importance_ver;
文件: /tmp/xposts_sig.bak-imp-*  (分类器)  /tmp/xposts_api.bak-imp-*  (API)
      /tmp/xposts.tpl.bak2-*     (模板)      /tmp/xposts.js.bak2-*      (JS)
```

