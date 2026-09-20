# DSH VS Code 扩展「确认信息必达（二）· 卡片渲染必达兜底」实施计划

- **日期**：2026-09-15
- **模块**：63 `Question_Render_Guarantee`（承接模块 59 `Question_Delivery_Guarantee`）
- **目标**：修复补丁10 之后**仍然卡住**的 `ask_user_question`（确认卡片）—— 让「state 里有问句」与「UI 里出现卡片」之间**不再有静默断点**
- **技术栈**：VS Code 扩展（第三方）· 唯一入口 `scripts/repatch_vscode_changes_bar.py`（新增 **补丁12**）· minified JS 定点替换 + 锚点唯一性断言 + 幂等 · node 最小 stub 自测 · headless Chrome（`--headless=old`）隔离 harness 对照实验

---

## 1. 现象（用户报告）

模块 59 修完（补丁10）之后，用户反馈：**「这个 patch 后需要用户确认的问题好像更容易卡住了」**，并给出实例「上一个 task」——
本会话连续两次 `ask_user_question` 均以 `Error: ask_user_question was aborted before the user answered` 结束
（界面里只看到工具卡片 `Ask_user_question({...})` + `Worked for 1m 53s`，**没有确认卡片**，用户只能 `Esc` 中断）。

## 2. 现场取证（分层，逐层排除）

| 层 | 证据 | 结论 |
|---|---|---|
| ① 服务端 / mux | 会话日志中该两次调用均为 `tool/result = aborted` | 问句确实发出过（未答） |
| ② host 是否收到帧 | `/tmp/dsh_question_debug.log`（补丁10 的诊断）两次都出现：<br>`recv question session=dsh-mu3g2tzy-zme4lo active=dsh-mu3g2tzy-zme4lo pending=1` | ✅ **帧到了 host** |
| ③ host 发给 webview 的 state 里有没有问句 | 同日志紧接一行：`publish active=dsh-mu3g2tzy-zme4lo questions=1`（该计数取自 `gateway.snapshot()`，即**真正 push 给 webview 的那份 state**） | ✅ **state 里确实有 1 条问句** |
| ④ webview 渲染 | 界面无卡片 | ❌ **断点只剩 webview 渲染** |

⇒ 与模块 59 的结论不同：本次**不是**「帧没到 / 被会话过滤掉」，而是「host 把含问句的 state 发出去了，webview 没画出来」。

## 3. 根因（读 minified 源码定位，三处叠加）

### A. `fr()` 渲染链**只有三步被隔离**（补丁10 的覆盖不足）

```js
function fr(){ if(!z)return; let{state:e}=z,t=e.active;
  F.editorContext.setAutoAttach(…), dl(e), … 或 pt(),
  __bbtSafe("composer",()=>sl(t)),        // ← 补丁10 加了隔离
  g.keyBanner.classList.toggle(…), g.sessionTitle.textContent=…, Eg(t),
  g.backParent…, g.fork…, g.loadOlder…,
  __bbtSafe("messages",()=>dr(t)),        // ← 补丁10 加了隔离
  __bbtSafe("interactions",()=>ds(t)),    // ← 卡片渲染器（链尾）
  g.details…||xn(), yn(t), Xr(t), Cn(t), F.sessionChanges.update(…), uo(), …
}
```
补丁10 只保证了 `sl/dr/ds` **三者互不影响**，但链路上**其余语句（`dl/pt/Eg/g.*/yn/Xr/Cn/uo/_i/Qr/po` 等）依旧无隔离** ——
任一步抛错，后面的 `ds(t)` 仍被跳过，卡片依旧永不出现。**这正是本次线上形态**（harness 实测复现：在 `ds` 之前抛错 ⇒ 卡片数 = 0，见 §5 对照表）。

### B. `ds()` 的渲染指纹写入**早于** DOM 更新 ⇒ 一次失败即**永久短路**

```js
function ds(e){ let t=JSON.stringify({sessionId:e?.id,approvals:…,questions:…});
  if(t===pi) return;        // ← 内容未变则直接 return（memo）
  $r(t);                    // ← 指纹**先**写入
  let n=document.createDocumentFragment(); …构建卡片…;
  g.interactions.replaceChildren(n);   // ← 真正的 DOM 更新在后
}
```
`pi` 只在 `ds` 里被写入、**没有任何地方复位**。因此在 `$r(t)` 之后、`replaceChildren` 之前抛错（或 `g.interactions` 已脱离文档）⇒
指纹已更新、DOM 未更新；而问句 pending 期间 **state 内容不变** ⇒ 后续每次 `ds` 都在 `if(t===pi)return` 处短路
⇒ 卡片**永久**不出现（补丁10 的 `__bbtSafe` 还会把异常吞掉，界面看不出任何异常）。

### C. 异常只留在 webview 内存 ⇒ 事后无法定位

补丁10 把异常塞进 `window.__bbtRenderErrors`（webview 内），**没有通道送到 host/磁盘** ⇒ 事后只知道「没卡片」，不知道「哪个 tag 抛的」。

## 4. 方案（补丁12，走唯一入口 `scripts/repatch_vscode_changes_bar.py`）

> 编号说明：`补丁11` 已被「压缩阈值调紧」占用，故本条编号跳到 **12**。

| 层 | 改动 | 目的 |
|---|---|---|
| A. webview `chat.js` | `fr` → 包装器：原函数体改名 `__bbtFrOrig`；`fr()` = `try{__bbtFrOrig()}catch{上报}finally{__bbtEnsureCards(z)}` | **链路上任何一步抛错都不再阻止卡片渲染** |
| B. webview `chat.js` | 新增 `__bbtEnsureCards(snap)`：`state` 说该有卡片（`questions+approvals>0`）而 DOM 里没有 ⇒ 清 `pi` 指纹 + 强制 `ds(active)` 重绘；并用 `document.querySelector("#interactions")` **实时查找**（若与缓存 `g.interactions` 不同则改指实时节点） | 修复 B（memo 永久短路）与「画进已脱离文档的幽灵节点」 |
| C. webview + host | 新增 `__bbtQDiag(tag,err,extra)`（节流 2.5s）→ `U("bbtDiag", …)`（含 `window.__bbtRenderErrors` 最近 6 条）；`__bbtSafe` 的 catch 也调用它；host `handleMessage` 新增 `case"bbtDiag"` 落 `/tmp/dsh_question_debug.log`；publish 日志追加 pending 问句的 `key` 列表 | **下次再卡，日志里直接给出是哪个 tag 抛的** |
| D. host `extension.cjs` | 问句 pending 期间**有限次**（3s × ≤20 次）重发 state；问句不再是 pending 时计数复位 | 兜底「webview 后创建 / 漏收该帧」 |

设计原则不变：**只加隔离、兜底与诊断，不改协议、不改语义**；补丁幂等、可 `--revert`、可 `--no-question-guarantee` 单跳过。

## 5. 验收口径

| # | 手段 | 通过标准 |
|---|---|---|
| 1 | `node --check dist/webview/chat.js` / `dist/extension.cjs` | 均 ok（脚本内置） |
| 2 | `--selftest` 新增「补丁12」用例（node + 最小 DOM stub，12 条断言） | 卡片缺失 ⇒ 强制重绘一次 / 重绘后卡片在 DOM / **渲染指纹已清** / 上报 `cards-restored`；卡片已在 ⇒ 零副作用；无问句 / 快照空 ⇒ 零副作用；`ds` 抛错不外泄且上报 `ds-forced`；`bbtDiag` 节流；**`fr` 链路上游抛错不外泄 + 卡片仍渲染 + 上报 `fr`** |
| 3 | headless Chrome 隔离 harness（真实模板 + `chat.css` + 真实 `chat.js`，合成 state 含 `question:S1:rpc1`） | 四组对照见下 |
| 4 | 幂等 | 复跑输出 `[补丁12] … 已打过, 跳过 ✓` |
| 5 | 回滚演练 | `--revert` 后 `__bbtSafe/__bbtEnsureCards/__bbtQLog` 全部归零；重跑脚本后全部回位 + `node --check` ok |
| 6 | 线上确认 | **重载窗口**后发起一次 `ask_user_question`：卡片出现、可作答；若仍不出现，`/tmp/dsh_question_debug.log` 应出现 `webview diag {"tag":"…"}` 指明抛错点 |

**harness 对照表（决定性证据）**

| 变体 | 卡片数 | webview 上报 |
|---|---|---|
| 补丁10-only，正常 state | 1 | — |
| **补丁10-only + 链路抛错** | **0** | —（**复现线上故障**） |
| **补丁12 + 链路抛错** | **1** | `fr` + `cards-restored` |
| 补丁12，正常 state | 1 | （harness 自身的 `composer` 异常被隔离并上报，证明诊断通道有效） |

## 6. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 改 minified 代码引入语法错误 | 脚本内置 `node --check` + 锚点唯一性断言（不匹配即中止不写）；补丁12 的锚点断言在应用前先跑 `--dry-run` |
| `fr` 包装引入递归 | 包装器对 `fr` 语义透明（`apply(this,arguments)` + 原体改名）；若原链自递归，行为与改前一致（未新增递归点） |
| 兜底反而刷屏 | `__bbtQDiag` 2.5s 同 tag+msg 去重；`cards-restored/cards-failed` 仅在**需要且缺卡**时上报；host 重发上限 20 次后停 |
| 生效条件 | **必须重载窗口**（`Cmd+Shift+P` → `Developer: Reload Window`）—— webview 与 extension host 都要重新加载；`--dry-run` 不会写盘 |
| 回滚 | `python3 scripts/repatch_vscode_changes_bar.py --revert`（从 `*.bbt-bak` 还原全部补丁）；或重跑时 `--no-question-guarantee` 只跳过补丁12 |
