# Edge Claw

一只住在 Windows 屏幕边框上的 Clawd 桌宠，加一个 Claude Code mod（插件）把 Claude 的状态告诉它。
用户说中文，回复用中文。用户喜欢先看演示再决定，改动外观后最好截图或让它当场表演一遍。

## 结构

| 路径 | 作用 |
|---|---|
| `hooks/register.tsx` | mod：写状态文件、输入框下面的「召唤 / 收起 Clawd」按钮、`/clawd` 命令、启动桌宠 |
| `hooks/register.test.ts` | mod 测试（`claude plugin test .`） |
| `types/index.d.ts` | mod 的 `$.state` 类型契约（`PluginState['edge-claw']`） |
| `pet/clawd.pyw` | 桌宠本体：Python 3 + tkinter，单文件，无第三方依赖 |
| `pet/clawd_sprites.json` | 动画素材，**不进 git**，用 `node tools/sprites.js extract` 从本机 Claude 应用里生成 |
| `tools/sprites.js` | 素材工具：extract / list / gallery / frames / ids |
| `scripts/dev.ps1` | 开发脚本：reload / launch / quit / play / doze / state / test |
| `.claude-plugin/` | 插件清单和本地 marketplace（`edge-claw@edge-claw-local`，目录型，指向本文件夹） |

## mod 和桌宠怎么通信

都在 `%USERPROFILE%\.claude\edge-claw\` 下，用 JSON 文件，桌宠每 400ms 读一次：

- `session-<会话id>.json`（每个会话的 mod 各写一份）：`{status: working|idle, attention, since, ts}`
  - turn.start 写 `working` 并每 5 秒刷新 `ts`（`$.clock.every` 心跳），turn 结束 / session.end 写 `idle`
  - 桌宠：**任一**会话 `working` 且 30 秒内刷新过就进入干活模式；`attention` 取所有会话里的（question 优先）；有会话开了新 turn（`since` 晚于完成提醒）就收起完成提醒；24 小时没动的文件桌宠自己删
  - `attention`：`permission` / `question` / `null`。`tool.check` 结果为 `ask` 时记下 tool_use_id，`tool.call` 结束时清掉；`AskUserQuestion`、`ExitPlanMode` 算 question
- `state.json`（mod 写）：只发事件 `{status, attention, ts, durationMs?, cmd?, cmdId?, anim?, then?}`
  - `status`：`done`（主循环 turn 正常结束）/ `interrupted`（Esc、出错、拒答）；mod 不再往这里写 `working`（会话崩了会卡住）。旧版 mod 和 `dev.ps1 state working` 写的 `working`/`attention` 桌宠仍然认
  - `ts` 变了才算新状态；`cmdId` 变了才执行 `cmd`：`quit`、`play`（`anim` + 可选 `then`）、`doze`
  - `durationMs` 随 `done` 一起发，≥5 分钟放礼花
- `alive.json`（桌宠写）：每秒心跳 `{ts, pid}`，mod 用它判断桌宠在不在（3 秒内）
- `memory.json`（桌宠写）：`firstSummon`、`fridaySpark`、`doneToday`，跨天的小记忆
- 单实例：桌宠启动时占用 `127.0.0.1:47391`，占不到就退出

## 桌宠行为（`pet/clawd.pyw`）

- 沿四条边走一圈：位置是一个周长坐标 `p`，`EDGES = bottom → right → top → left`；精灵按所在边旋转，脚贴边（`rotate`/`turn`/`unturn`）。拖拽松手离边 80px 内就吸附，否则掉到任务栏。
- 干活时：停下摆 Laptop/Thinking/Desktop 姿势 10–20 秒（`POSE_HOLD_S`），姿势之间只挪 ±300px（`WORK_STROLL`）。
- 动画优先级（`choose_anim`）：一次性动作（`oneshot` + 队列）> 拖拽/掉落 Dizzy > 打盹 > pose（Laptop/Thinking/Desktop/Lightbulb）> 看鼠标（眼珠/指向）> 横着挪 CrabWalking / 东张西望。
- 动画分段常量都在文件顶部：`SCUTTLE_LOOP`、`POSES`（开场/循环/收尾帧）、`DOZE_*`、`POINT_*`、`EYES`（眼珠 3×4 网格对应的帧）。分段是用 `node tools/sprites.js ids <Name>` 和 `frames` 逐帧看出来的。
- 提醒：权限/提问举灯泡，原地等到处理完；任务完成原地跳+挥手循环，黄色「!!!」只在跳到最高点那几帧出现（闪烁），直到 Claude 窗口到前台（`claude_in_front`，前台进程名 `claude.exe`）或点一下它。
- 交互：来回摸 3 次 → Excited；单击 → Jumping，2.5 秒内 5 下 → Facepalm；鼠标停在附近 → 眼珠看过去，3 秒后伸钳子指向；右键菜单「跳舞」随机舞种。
- 彩蛋：每天第一次召唤举仙女棒（Spark）、周五 18 点后一次、当天每第 5 个任务；长任务完成先放礼花（Confetti）。

## 开发流程

1. 改代码（在本文件夹）。
2. 改了桌宠或 mod 都要把 `.claude-plugin/plugin.json` 的 `version` 加一，否则缓存里的副本不会更新。
3. `powershell -File scripts\dev.ps1 reload`：校验、更新 marketplace、更新插件、重启桌宠。
4. mod（`hooks/`）的改动要**开新的 Claude 会话**才生效；桌宠的改动 reload 后立刻生效。
5. `powershell -File scripts\dev.ps1 test` 跑 `claude plugin validate` 和 `claude plugin test`。
6. 想看效果：`dev.ps1 play Confetti`、`dev.ps1 doze`、`dev.ps1 state done`、`dev.ps1 state working permission`。

桌宠逻辑可以不开窗口地测：用 `importlib.machinery.SourceFileLoader` 载入 `clawd.pyw`，写个 `Clawd` 子类覆盖 `__init__` 只设需要的字段，然后直接调 `choose_anim`/`frame_index`/`update_watch` 等。

截图验证：PowerShell 里 `EnumWindows` 按 `alive.json` 的 pid 找到桌宠窗口，`Graphics.CopyFromScreen` 截那一块（先 `SetProcessDPIAware`）。

## 坑（都踩过）

- **启动桌宠必须用 WMI**（`Invoke-CimMethod Win32_Process Create`）。Claude 桌面应用是 MSIX 包，它启动的所有子进程都在同一个 Windows job 里，应用自动更新/重启时 Windows 会把整个 job 关掉；`Start-Process`、`explorer.exe` 启动的都还在 job 里，只有 WMI 创建的进程不在。
- 用 desktop 自带的 Claude Code：`%APPDATA%\Claude\claude-code\<版本>\...\claude.exe`。PATH 上的 `claude` 版本旧，不支持 mod。
- `C:\Program Files\WindowsApps` 不能列目录，用 `Get-AppxPackage -Name Claude` 拿安装位置。
- Python 3.8（`%LOCALAPPDATA%\Programs\Python\Python38`）不支持超过 260 字符的路径；scratchpad 路径很长，脚本要通过 stdin 喂给 `python -I -`。没有 PIL。
- 装了 Blast Radius mod：它展不开 shell 变量，`rm "$VAR/..."` 会被拦；删文件用写全的路径，或用 PowerShell `Remove-Item -LiteralPath`。
- tkinter 不是 DPI 感知的，窗口、鼠标、工作区坐标都是逻辑像素（系统缩放 125%），截图时要换算。
- `-transparentcolor` 的透明像素会点击穿透，所以 `<Motion>`/点击只在 Clawd 身上触发。

## 素材和版权

- `clawd_sprites.json` 来自 Claude 桌面应用内置的 Clawd 小游戏（`clawdQuestEngine-*.js`，共 25 套），是 Anthropic 的素材，只供本机自用，不进 git、不分发。
- 要发布到 GitHub，必须换成原创形象，并写明是非官方项目。
- 不要用 rullerzhou-afk/clawd-on-desk 的美术：它的 `assets/LICENSE` 明确禁止在它自己的应用之外使用。
- 已经不用的官方动作：Walking、Running（侧身）、Turning（转身导致卡顿，已移除）、Meditating（换成了 Disappointed 中段的打盹）。
