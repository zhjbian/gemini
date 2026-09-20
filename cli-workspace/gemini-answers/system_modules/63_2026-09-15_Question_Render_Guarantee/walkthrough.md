# DSH VS Code 扩展「确认信息必达（二）· 卡片渲染必达兜底」验收报告 (Walkthrough)

- **日期**：2026-09-15
- **归档目录**：`63_2026-09-15_Question_Render_Guarantee`（承接模块 59）
- **一句话结论**：本次卡住**不是**「帧没到」（补丁10 的诊断日志证明帧到了 host、且发给 webview 的 state 里就有 1 条问句），而是 **webview `fr()` 渲染链在 `ds()` 之前被别的语句抛错打断 + `ds()` 渲染指纹一次失败即永久短路**；补丁12 用「整链隔离 + 卡片必达兜底 + 诊断上报 + host 有限次重发」把这条静默断点封死，四组 harness 对照实验证明：**补丁10-only + 链路抛错 ⇒ 卡片数 0（复现）；补丁12 + 同一抛错 ⇒ 卡片数 1 且上报 `fr`/`cards-restored`**。

---

## 1. 结论先行

| 项 | 结果 |
|---|---|
| 现象 | 补丁10 之后 `ask_user_question` 仍卡：界面只有工具卡片 + `Worked for …`，无确认卡片，用户只能 `Esc` |
| 取证（新） | `/tmp/dsh_question_debug.log`：`recv question … pending=1` **且** `publish active=… questions=1` ⇒ 帧到 host、state 含问句 |
| 定位 | 断点在 **webview 渲染**：① `fr()` 仅 `sl/dr/ds` 三步被隔离，其余语句抛错仍会跳过 `ds`；② `ds()` 的 `pi` 指纹先写、DOM 后更，失败即永久短路；③ 异常无通道出 webview |
| 修复 | **补丁12**：`fr` 整链包装 + `__bbtEnsureCards()` 必达兜底（实时 DOM 查找 / 清指纹 / 强制重绘）+ `__bbtQDiag()` 上报（host 落盘）+ host pending 期间有限次 state 重发 |
| 验证 | `node --check` ×2 ok；`--selftest` 补丁12 **12/12 断言**；headless harness 四组对照（见 §3）；幂等复跑 ok；`--revert` → 重打 演练通过 |
| 生效 | **需重载窗口**（`Cmd+Shift+P` → `Developer: Reload Window`） |

## 2. 关键代码事实（minified 源码，逐条可复现）

```
chat.js   ds():  if(t===pi)return; $r(t); …构建…; g.interactions.replaceChildren(n);
          ↑ 指纹 pi 在 DOM 更新前写入，且**全文件无任何地方复位 pi** ⇒ 失败一次 = 同一内容永久不重绘
chat.js   fr():  …setAutoAttach/dl/pt/sl(keyBanner,sessionTitle,Eg,backParent,fork,loadOlder)
                 /dr/ds/xn/yn/Xr/Cn/sessionChanges/uo/_i/Qr/po
          ↑ 补丁10 只包了 sl/dr/ds；其余语句仍在链路中可抛错
chat.js   __bbtQDiag 新：U("bbtDiag", {tag,msg,stack,errors,extra}) —— U() = si.postMessage({type,...})
extension.cjs handleMessage(e){ … switch(e.type){ case"ready": … } }   ← 新增 case"bbtDiag"
extension.cjs drainPublishQueue:  await this.postToHosts({type:"state",state:e,…})  ← 其后追加有限次重发
```

## 3. 验证

### 3.1 离线自测（`--selftest`，node + 最小 DOM stub，不碰扩展文件）

```
[补丁12（问句卡片必达兜底 + 诊断上报） 自测]
  ✓ 卡片缺失 ⇒ 强制重绘一次          ✓ 重绘后卡片出现在 DOM
  ✓ 渲染指纹已清（避免 memo 永久短路） ✓ 上报 cards-restored
  ✓ 卡片已在 ⇒ 不重绘、不上报          ✓ 无卡片需求 / 快照为空 ⇒ 零副作用
  ✓ ds 抛错时兜底自身不冒泡            ✓ ds 抛错 ⇒ 上报 ds-forced
  ✓ bbtDiag 去重节流生效               ✓ fr 链路上游抛错不外泄
  ✓ fr 抛错后卡片仍渲染（必达兜底）     ✓ 上报 fr 标签的异常
OK 补丁12 全部断言通过          （连同补丁7 / 8-9：3 组自测全部通过）
```
> 说明：`fr` 抛错用例通过「`z.state` 首次读取抛错、再次读取正常」模拟「原函数体第一条语句失败」，正是线上形态。

### 3.2 headless Chrome 隔离 harness（真实模板 + `chat.css` + 真实 `chat.js`）

harness = 从 `extension.cjs` 抽取的 webview HTML 模板（去掉 CSP meta，本地无安全需求）+ 真实 `media/chat.css`
+ `acquireVsCodeApi` shim（`postMessage` 收集到 `window.__posted`）+ 载入后 200ms 灌入合成 state：
`active.questions=[{key:'question:S1:rpc1', questions:[{id:'q1',header,question,multiSelect:false,options:[{label,description}×2]}]}]`。

| 变体 | 卡片数（`.question-card`） | webview 上报 |
|---|---|---|
| 补丁10-only，正常 state | 1 | — |
| **补丁10-only + 在 `ds` 之前抛错** | **0** | — ← **线上故障复现** |
| **补丁12 + 同一抛错** | **1** | `{"tag":"fr",…}` + `{"tag":"cards-restored",extra:{need:1,cards:1}}` |
| 补丁12，正常 state | 1 | `{"tag":"composer","msg":"Cannot read properties of undefined (reading 'reasoning')"}` |

- 第 4 行是**意外收获**：harness 的合成 `configuration:{}` 恰好让 `sl(t)` 抛错（`reasoning` 未定义）——
  即「上游某步抛错」在真实环境里完全可能发生，而**这次它被隔离并上报，卡片照常渲染**（改前这就会静默变成 0）。
- 运行命令（可复现）：`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --headless=old --no-sandbox --disable-gpu
  --user-data-dir=/tmp/<唯一名> --virtual-time-budget=3000 --dump-dom file:///tmp/bbt_qharness/harness.html`
  （**`--headless=new` 在本机会挂住**，必须用 `--headless=old`；profile 用独立目录并在结束时删除）。

### 3.3 落盘与工程性检查

| 检查 | 结果 |
|---|---|
| `python3 scripts/repatch_vscode_changes_bar.py` | `[补丁12] … 应用中`；`[校验] node --check chat.js: ok` / `extension.cjs: ok`；补丁1–9 回检全部「是 ✓」 |
| 幂等复跑 | `[补丁12] webview 整链隔离…: 已打过, 跳过 ✓` / `host 诊断落盘 + pending 重发: 已打过, 跳过 ✓` |
| 标记落盘 | `chat.js`: `__bbtEnsureCards` ×1；`extension.cjs`: `case"bbtDiag"` ×1、`__bbtQLog` ×3、`__bbtQNudge` ×1 |
| 回滚演练 | `--revert` → `chat.js __bbtSafe=0 __bbtEnsureCards=0`、`extension.cjs __bbtQLog=0`（还原成功）；重跑脚本 → 全部回位 + `node --check` ok |
| 语法 | `node --check` 两文件 ok；(补丁脚本) `python3 -m py_compile` ok |

## 4. 生效方式（重要）

1. VS Code：`Cmd+Shift+P` → **`Developer: Reload Window`**（webview 与 extension host 都需重载，缺一不可）。
2. 之后再发起一次需要确认的提问：
   - 正常：面板出现卡片，作答后工具立刻返回；
   - 万一仍不出卡片：`/tmp/dsh_question_debug.log` 里应出现
     `webview diag {"tag":"<抛错点>","msg":"…","errors":[…],"stack":"…"}` —— **直接给出是哪一步抛的**，
     配合 host 侧的 `recv …` / `publish … questions=1 keys=[…]` 可一眼判定断点。
3. 该日志随时可删（`rm /tmp/dsh_question_debug.log`），仅诊断用。

## 5. 回滚

```bash
# 全部撤销（从 *.bbt-bak 还原，随后按需重打）
python3 scripts/repatch_vscode_changes_bar.py --revert

# 只跳过补丁12（保留补丁10 及其余补丁）
python3 scripts/repatch_vscode_changes_bar.py --no-question-guarantee
```

## 6. 遗留与上游建议

1. **`fr()` 渲染链整体无错误隔离**（上游设计缺陷）：正确的改法是给每个渲染步骤独立 try/catch（或把 `ds`/卡片渲染前移），本补丁用「整链包装 + 必达兜底」在补丁层根治。
2. **`ds()` 的 memo 语义有隐患**：`if(t===pi)return` 与 `$r(t)` 的位置应改为「渲染成功后再更新指纹」，否则任何一次渲染失败都会永久短路同内容重绘。
3. **webview 异常无出口**：`readSocket()` 的 `catch{}` 与 `window.__bbtRenderErrors` 都只留在本地；建议上游把渲染异常上报 host 输出通道。
4. 本模块**不涉及交易决策规则**，故**未**写入交易规则手册（规则 11 只覆盖决策性规则）；仅按规则 10 归档到本目录并更新 `bbt_trading_modules.html`。
