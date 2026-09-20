# DSH VS Code 扩展「确认信息必达」修复 —— 实施计划

- **日期**：2026-09-14
- **模块**：59 `Question_Delivery_Guarantee`
- **目标**：修复 `skymecode.deepseek-harness-for-vscode` 聊天面板中 **`ask_user_question`（确认卡片）100% 收不到** 的故障
- **技术栈**：VS Code 扩展（第三方）· 补丁脚本 `scripts/repatch_vscode_changes_bar.py` · minified JS（chat.js / extension.cjs）· WebSocket mux 协议 · headless Chrome 隔离验证

---

## 1. 现象（用户报告）

`http://127.0.0.1:5005/...` 无关；问题在 **DeepSeek Harness for VS Code** 面板：

> 「有时间要求确认的信息发不出来，卡在那里」

- 面板里只看到工具卡片 `Ask_user_question({...})` + `Worked for 10m 52s`，**没有确认卡片**。
- 用户等 7~10 分钟后按 `Esc` 中断。

## 2. 现场取证（会话日志，权威）

扫描 `harness-home/sessions/**/session.jsonl.zstd`：

| 会话 | `ask_user_question` 调用 | 结果 |
|---|---|---|
| dsh-mtrin7v6-lqfl4g | 2 | 1 失败 / 1「结果未持久化」 |
| dsh-mu01uk6z-pxqz1v | 4 | 4 失败 |
| dsh-mu0gxyzz-qpsl52 | 2 | 2 失败 |
| dsh-mu1m9116-yg6wtg | 1 | 1 失败 |
| dsh-mu266unj-ctkx2m | 2 | 2 失败 |
| **合计** | **11** | **10 失败（91%）** |

失败形态一致：

```
tool/call  ask_user_question  {"questions":[{"id":"next_action","header":"下一步",
           "question":"ES 图缺 bar 的修复走哪条路？","options":[…3 项…]}]}
tool/result  Error: ask_user_question was aborted before the user answered   (Δ=463.6s)
turn/end     reason={kind:'aborted', reason:{kind:'user'}}      ← 用户自己按 Esc
```

⇒ **不是服务端 abort，是问句从未出现在 UI，用户只能中断。**

## 3. 分层定位（本机实测，非推测）

| 层 | 验证方式 | 结论 |
|---|---|---|
| ① 服务端是否发出问句 | 自建 WebSocket 探针直连扩展自带 gateway（`ws://127.0.0.1:<port>/api/events.mux`） | ✅ **发出了**：`question/requested rpcId=… sessionId=dsh-mu0gxyzz-qpsl52`（探针 75s 后自动作答被接受，`accepted:true`） |
| ② 客户端 schema 是否会静默丢帧 | 逐字比对 `dsh-client-connection`（客户端）与 `dsh-host-apiproxy`（服务端）的 `askUserQuestionItemSchema` / `sessionIdSchema` | ⚠️ 两者**完全相同**，解析不会失败；但 `readSocket()` 的 `catch{}` **确实会静默吞掉任何解析失败帧**（无日志） |
| ③ webview 能否渲染问句卡片 | 用扩展模板 + `chat.js`/`chat.css` 搭隔离 harness（headless Chrome + `acquireVsCodeApi` shim + 合成 state） | ✅ **能**：`#interactions` 出现 `.question-card`（文本「Harness needs your input / 测试头 / 测试问题？/ A 选项 / B 选项 / Submit answer」） |
| ④ 补丁是否破坏了它 | `chat.js` vs `chat.js.bbt-bak` 的 `fr()`/`ds()`/`fd()` 逐字节比对 | ✅ 完全一致 ⇒ **不是本地补丁造成的** |

## 4. 根因（两处，均为上游设计缺陷）

### A. webview：`fr()` 渲染链**无错误隔离**，`ds()`（唯一的卡片渲染器）在链尾

```js
function fr(){ … let t=e.active;
  F.editorContext.setAutoAttach(…), dl(e), …,
  sl(t),                                   // ① composer 配置（会抛）
  …,
  dr(t),                                   // ② 消息列表（会抛）
  ds(t),                                   // ③ ← 唯一渲染 approval/question 卡片
  … }
```

**任一步抛错 ⇒ 其后语句全部跳过 ⇒ `ds(t)` 永不执行 ⇒ 卡片永不出现**；问句只投递一次、没有重试 ⇒ 永久挂起。

harness 实测复现：state 中带 `questions` 时，若 `sl(t)` 抛错（`Cannot read properties of undefined (reading 'split')`），`ds()` 不执行、`cards=0`；把 `sl/dr/ds` 各自加 try/catch 后 **`cards=1`**。

### B. host：问句只在「当前会话」才被记录，且切换会话即清空

```js
else if (r.type === "question/requested" && String(r.sessionId) === this.activeSessionId) {
    this.questions.set(`question:${rpcId}`, …);      // 非当前会话 ⇒ 直接丢弃
}
…
selectSession(){ … this.questions.clear(); … }        // 切换会话 ⇒ 清空
```

服务端**只在 mux 重连时**重放 pending 问句（`for (const pending of pendingQuestions.values()) queue.push(...)`）
⇒ 落在非当前会话（或切过一次会话）的问句**永久丢失**。

## 5. 方案（补丁 10，走唯一入口 `scripts/repatch_vscode_changes_bar.py`）

| 目标文件 | 改动 |
|---|---|
| `dist/webview/chat.js` | 注入 `__bbtSafe(tag,fn)`；把 `fr()` 中 `sl(t)` / `dr(t)` / `ds(t)` 三步各自包进 `__bbtSafe(...)`；`ds()` 渲染后若 `#interactions` 非空则确保未被隐藏 |
| `dist/extension.cjs` | `question/requested` **不再按 activeSessionId 过滤**；键改为 `question:<sessionId>:<rpcId>` 并记 `sessionId`；`question/resolved` 按 rpcId 后缀清理；快照 `questions` 只投放当前会话；`selectSession` 不再 `questions.clear()`；注入 `__bbtQLog()` 写 `/tmp/dsh_question_debug.log`（收帧 / publish 计数） |

设计原则：**只加隔离与缓冲，不改协议、不改语义**；补丁幂等（重复执行跳过）、可 `--revert` 还原、`--no-question-fix` 单独跳过。

## 6. 验收标准

1. `node --check dist/webview/chat.js` / `dist/extension.cjs` 均通过。
2. 隔离 harness（合成 state + 让 `sl(t)` 抛错）中 **`.question-card` 必须出现**（修前 0 / 修后 1）。
3. 重载窗口后，实测发起一次 `ask_user_question`：卡片出现在面板中、可作答、工具立即返回（不再等 75s 自动作答）。
4. `/tmp/dsh_question_debug.log` 应出现 `recv question session=… active=…` 与 `publish active=… questions=1`。
5. 重复执行补丁脚本幂等（`[补丁10] … 已打过, 跳过 ✓`）。

## 7. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 改 minified 代码引入语法错误 | 脚本内置 `node --check` + 锚点唯一性断言（不匹配即中止不写） |
| 宿主半区需重载窗口才生效 | 明确提示用户；webview 半区只需重开视图 |
| 缓冲后旧问句残留 | `question/resolved` 事件与 `turn/end` 都会清理；快照只投放当前会话 |
| 回滚 | `python3 scripts/repatch_vscode_changes_bar.py --revert`（从 `.bbt-bak` 还原全部补丁）；或 `--no-question-fix` 只跳过补丁10 |
