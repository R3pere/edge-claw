# Edge Claw

在 Windows 屏幕边框上爬来爬去的 Clawd 桌宠，顺便替 Claude Code 提醒你：

- 沿着任务栏、左右两侧和顶部来回横着挪，贴墙走、倒挂走
- Claude 干活时走走停停，停下来思考、趴着敲笔记本或坐到台式电脑前
- 需要你批准权限或回答问题时，原地举灯泡，直到你处理完
- 任务完成时原地跳跃挥手，头顶闪黄色「!!!」，直到你切回 Claude；长任务先放礼花
- 摸它、戳它、把鼠标停在它旁边，都有反应；闲久了会打盹

非官方个人项目。Clawd 是 Anthropic 的角色；动画素材从本机安装的 Claude 桌面应用里生成，不随仓库分发。

## 安装（本机）

需要 Windows、Claude 桌面应用（Claude Code 2.1.287 以上）、Python 3（带 tkinter）、Node.js。

```powershell
node tools/sprites.js extract
& "$env:APPDATA\Claude\claude-code\<版本>\...\claude.exe" plugin marketplace add D:\edge-claw
& "$env:APPDATA\Claude\claude-code\<版本>\...\claude.exe" plugin install edge-claw@edge-claw-local
```

开一个新的 Claude 会话，点输入框下面的「🦀 召唤 Clawd」，或者输入 `/clawd`。

开发说明见 [CLAUDE.md](CLAUDE.md)。
