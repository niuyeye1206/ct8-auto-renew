# ct8 自动续期

ct8.pl 免费主机自动登录保活：每 60 天左右登录一次 DevilWEB 面板，登录本身就是续期（90 天内登录一次即可）。

> Fork 自 [tina25311/serv00-auto-login](https://github.com/tina25311/serv00-auto-login)，改成单账号 ct8 专用、每 2 个月跑一次、TG 通知。

## 续期机制（已核实）

- ct8 条款第 12 条：90 天内没有通过 DevilWEB 面板或 SSH 正确登录，账号自动删除。
- 面板首页的 `Valid until` 就是 90 天倒计时，每次登录刷新。
- **不需要走 ADMIN.NET.PL 计费面板**（`platnosci.admin.net.pl`，那是另一套账号，免费用户很可能没有）。本仓库不碰计费面板，不走任何代理，GitHub Runner 直连 `panel.ct8.pl`。

## 定时规则

- 每月 1 号 UTC 22:30（北京时间次日 06:30）自动跑。
- **奇数月**（1/3/5/7/9/11 月）：登录面板续期，约 60 天一次，每次间隔都小于 90 天。
- **偶数月**：不登录，只更新 `time.txt` 提交一次，防止仓库 60 天无活动导致 GitHub 停用定时任务。
- 每次登录成功/失败都发 TG 通知到 `@senmuse_bot`，成功时带上新的有效期；脚本异常退出时 workflow 会发一条兜底通知。

## 配置 Secrets

仓库页面 → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`，逐个添加：

| Secret 名 | 填什么 |
|---|---|
| `CT8_USERNAME` | ct8 面板账号：`asen0122` |
| `CT8_PASSWORD` | ct8 面板密码（激活邮件里系统发的那个） |
| `TG_BOT_TOKEN` | Telegram Bot Token（`@senmuse_bot` 用的那个，和 katabump-renew 仓库里同一个值） |
| `TG_CHAT_ID` | Telegram Chat ID（和 katabump-renew 仓库里同一个值） |

密码不要写进代码、不要发在任何聊天记录里，只填在 Secrets 里。

## 手动运行

仓库页面 → `Actions` → 左侧选 `ct8 自动续期` → `Run workflow` → `Run workflow`。11 月是奇数月，手动跑会真的登录一次。

## 文件

- `ct8_renew.py`：登录脚本（无头浏览器登录面板，抓取新有效期，发 TG 通知）
- `.github/workflows/renew.yml`：定时任务
- `time.txt`：每次运行更新的运行时间（防定时任务被停用）
