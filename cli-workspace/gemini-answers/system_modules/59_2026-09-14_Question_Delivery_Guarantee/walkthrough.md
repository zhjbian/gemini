# DSH VS Code 扩展「确认信息必达」修复 —— 验收报告

- **日期**：2026-09-14
- **模块**：59 `Question_Delivery_Guarantee`
- **归档目录**：`59_2026-09-14_Question_Delivery_Guarantee`
- **技术栈**：第三方 VS Code 扩展补丁（`scripts/repatch_vscode_changes_bar.py` 唯一入口）· minified JS 定点替换 + 锚点断言 · headless Chrome 隔离 harness · WebSocket mux 探针 · 会话日志取证

---

## 1. 结论先行

| 项 | 结果 |
|---|---|
| 现象 | VS Code 面板里 `ask_user_question` 卡片**从不出现在 UI**，工具挂起直到用户按 Esc 中断 |
| 取证 | 5 个会话共 **11 次调用 / 10 次失败**（`Error: ask_user_question was aborted before the user answered`，Δ≈464s，`turn/end reason=user`） |
| 服务端 | ✅ 正常 —— 自建 WS 探针在 gateway mux 上**抓到 `question/requested`** |
| 客户端 schema | ✅ 不会丢帧（前后端 `askUserQuestionItemSchema` 逐字一致）—— 但 `readSocket()` 的 `catch{}` 属**静默丢帧**隐患 |
| webview 渲染能力 | ✅ 有能力 —— 隔离 harness 中可直接渲染出 `.question-card` |
| 本地既有补丁 | ✅ 无罪 —— `fr()/ds()/fd()` 与 `.bbt-bak` 逐字节一致 |
| **根因** | **A. webview `fr()` 渲染链无错误隔离 ⇒ `ds()`（唯一卡片渲染器）被前面的异常跳过；B. host 问句只在当前会话才记录、切会话即清空，且只在 mux 重连时重放 ⇒ 一次漏渲染/一次会话切换即永久丢失** |
| 修复 | 补丁10：`__bbtSafe()` 隔离 `sl/dr/ds` 三步 + 问句按 `(sessionId,rpcId)` 全量缓冲 + 快照按当前会话投放 + 诊断日志 |
| 验证 | `node --check` ×2 通过；harness 修前 `cards=0` → 修后 **`cards=1`** |

## 2. 取证链（每一步都可复现）

### 2.1 会话日志（权威）

```
tool/call    seq=158007  name=ask_user_question
  args={"questions":[{"id":"next_action","header":"下一步",
        "question":"ES 图缺 bar 的修复走哪条路？","options":[A/B/A+B 三项]}]}
tool/result  seq=158011  Error: ask_user_question was aborted before the user answered   ← Δ=463.6s
turn/end     seq=158013  reason={kind:'aborted', reason:{kind:'user'}}
```

⇒ 用户不是「没点」，而是**根本没看到卡片**，等不下去才中断。

### 2.2 服务端确实发出（自建 mux 探针）

```js
const ws = new WebSocket('ws://127.0.0.1:59793/api/events.mux');
// … 9.5s 收到：
// ★ question/requested rpcId=91370822-… session=dsh-mu0gxyzz-qpsl52
//   questions=[{id:'probe2',header:'决定性探针',options:[A,B]}]
// 75s 后探针自动 POST /api/respond 选 B → HTTP 200 {"accepted":true}
```

**关键判据**：工具最终返回的正是探针的 **B**（「界面上没有显示」）而不是用户会选的 A
⇒ 用户界面**确实没有渲染卡片**（故障当场复现）。

### 2.3 webview 有能力渲染（隔离 harness）

用扩展自身的 HTML 模板 + `chat.css` + `chat.js`，shim `acquireVsCodeApi`，投递合成 state：

```js
state.active = {id:'S1', …, questions:[{key:'question:r1',
  questions:[{id:'q1',question:'测试问题？',header:'测试头',
              options:[{label:'A 选项'},{label:'B 选项'}]}]}]}
```

| 版本 | harness 结果 |
|---|---|
| 原始 `fr()` | `cards:0`（`sl(t)` 先抛 `Cannot read properties of undefined (reading 'split')` ⇒ `ds()` 被跳过） |
| **补丁10 后** | **`cards:1`**，文本 `Harness needs your input / 测试头 / 测试问题？/ A 选项 / B 选项 / Submit answer` |

⇒ **webview 渲染能力没问题，问题在「渲染链被前面的异常打断」。**

### 2.4 排除本地补丁

```
function fr(){   patched@317387  bak@317331  identical=True
function ds(e){  patched@52973   bak@52973   identical=True
function fd(e){  patched@53746   bak@53746   identical=True
```

⇒ 卡片渲染相关代码与补丁前**逐字节一致**，故障来自上游设计。

## 3. 根因细节

### A. webview（`chat.js` · `fr()` 渲染链无隔离）

```js
g.loadOlder.classList.toggle("hidden",!t?.hasMore),
dr(t),      // ← 消息列表：可能抛
ds(t),      // ← ★ 唯一的 approval/question 卡片渲染器
g.details.classList.contains("hidden")||xn(), yn(t), Xr(t), …
```

前面还有 `sl(t)`（composer 配置，同样可能抛）。**任何一步抛错 ⇒ 后续语句全跳过 ⇒ 卡片不渲染**，而问句只投递一次、**无重试** ⇒ 永久挂起。

### B. host（`extension.cjs` · 问句作用域过窄 + 无重放兜底）

```js
else if(r.type==="question/requested" && String(r.sessionId)===this.activeSessionId){ … }
…
selectSession(){ … this.questions.clear(); … }
```

服务端只在 **mux 重连**时重放 pending 问句 ⇒ 落错会话/切过一次会话即永久丢失。
另外 `readSocket()` 的 `catch{}` 会把任何解析失败帧**静默丢弃且无日志**（本次 payload 校验通过，但该隐患已记录）。

## 4. 修复内容（补丁10）

| 文件 | 定点改动（全部带锚点唯一性断言） |
|---|---|
| `dist/webview/chat.js` | ① 注入 `__bbtSafe(tag,fn)`；② `sl(t),` → `__bbtSafe("composer",()=>sl(t)),`；③ `dr(t),ds(t),` → `__bbtSafe("messages",()=>dr(t)),__bbtSafe("interactions",()=>ds(t)),`；④ `ds` 渲染后若 `#interactions` 非空则移除 `hidden` 并打 `data-bbt-interactions="visible"` |
| `dist/extension.cjs` | ① 去掉 `question/requested` 的 `activeSessionId` 过滤；② 键 `question:<sessionId>:<rpcId>` 且记录 `sessionId`；③ `question/resolved` 按 rpcId 后缀清理；④ 快照 `questions` 只投放当前会话；⑤ `selectSession` 不再 `questions.clear()`；⑥ 注入 `__bbtQLog()` 写 `/tmp/dsh_question_debug.log`（收帧 + publish 计数） |

**原则**：只加隔离与缓冲，**不改协议、不改交互语义**；幂等、可 `--revert`、可 `--no-question-fix` 单跳过。

## 5. 实测

```
$ python3 scripts/repatch_vscode_changes_bar.py --dry-run
  [补丁10] webview 渲染隔离(ds 必达): 应用中 (dry-run) | 复用已有备份
  [补丁10] host 问句按会话缓冲: 应用中 (dry-run) | 复用已有备份

$ python3 scripts/repatch_vscode_changes_bar.py
  [校验] node --check extension.cjs: ok
  ✅ 补丁完成。请重载窗口: Cmd+Shift+P -> Developer: Reload Window

$ node --check dist/webview/chat.js   → chat.js syntax OK
$ node --check dist/extension.cjs     → extension.cjs syntax OK
$ grep -c __bbtSafe dist/webview/chat.js → 命中；grep -o '__bbtSafe("interactions",()=>ds(t))' → 命中
```

harness 回归（同一合成 state，故意让 `sl(t)` 抛错）：

| 版本 | `.question-card` |
|---|---|
| 修前 | 0 |
| **修后** | **1** ✅ |

## 6. 用户侧生效步骤

1. `Cmd+Shift+P` → **Developer: Reload Window**（宿主半区必须重载才会生效；会话持久化在 `harness-home/sessions`，重载后可继续）。
2. 重载后随便问一次（或让我再跑一次探针）⇒ 面板应出现「Harness needs your input」卡片，可点选项 / 填自定义答案。
3. 事后核对 `tail /tmp/dsh_question_debug.log`：
   ```
   … recv question session=dsh-… active=dsh-… pending=1
   … publish active=dsh-… questions=1
   ```
   两条都在 ⇒ 全链路通；只有 `recv` 没有 `publish` ⇒ 问题在快照；两条都没有 ⇒ 帧没到 host。

## 7. 回滚

| 范围 | 命令 / 位置 |
|---|---|
| 全部补丁 | `python3 scripts/repatch_vscode_changes_bar.py --revert`（从 `*.bbt-bak` 还原） |
| 只撤补丁10 | 重跑时加 `--no-question-fix`（或从 `chat.js.bbt-bak` / `extension.cjs.bbt-bak` 局部还原） |
| 补丁脚本本体 | 修改前快照 `/tmp/repatch_pre_mu0gxyzz.py.bak` |

## 8. 遗留

1. **上游应修的两处**（建议反馈给扩展作者）：`fr()` 渲染链错误隔离；`question/requested` 不应依赖会话作用域，且问句应有「未答则重放/超时提示」机制。
2. **静默丢帧隐患**：`readSocket()` 的 `catch{}` 建议改为「记日志 + 计数」，否则任何 schema 演进都会静默黑掉某类帧。
3. **工具侧无超时提示**：`ask_user_question` 挂起期间 UI 只有 `Worked for …`，建议在 host 侧对 pending 问句加**桌面提醒兜底**（可复用补丁5 的 `/task-notify` 通道），本次未做以免过度打扰。
