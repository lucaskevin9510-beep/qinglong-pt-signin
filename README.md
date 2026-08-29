# QingLong PT Sign-in / 青龙 PT 自动签到

青龙面板可用的 PT 站自动签到脚本集合。每个站点使用独立脚本、独立环境变量，方便单独启用、停用和维护。

A collection of PT tracker auto sign-in scripts for QingLong. Each tracker uses an independent script and environment variable for easy maintenance and scheduling.

## 已支持 / Supported

| 站点 / Tracker | 脚本 / Script | 环境变量 / Environment Variable | 状态 / Status |
| --- | --- | --- | --- |
| PterClub 猫站 | `pterclub.py` | `PTERCLUB_COOKIE` | ✅ 可用 / Working |

## PterClub 猫站

### 功能

- 检查 Cookie 登录状态
- 获取用户名
- 获取当前猫粮
- 检查今日签到状态
- 未签到时自动调用签到接口
- 尝试获取本次签到奖励
- 尝试获取连续签到天数
- 签到后重新读取猫粮数据
- 遇到验证码、人机验证或风控时停止，不尝试绕过

### 青龙配置

先在青龙的“环境变量”中创建：

```text
名称：PTERCLUB_COOKIE
值：你的完整 PterClub Cookie
```

> ⚠️ Cookie 属于账号凭证，请只保存在你自己的青龙环境变量中。不要提交到 GitHub、Issue、日志截图或其他公开位置。

脚本依赖：

```text
requests
```

如果青龙尚未安装，可在“依赖管理 → Python3”中添加：

```text
requests
```

推荐任务命令：

```bash
python3 pterclub.py
```

脚本内置建议定时规则：

```cron
17 8 * * *
```

### 可选环境变量

```text
PTERCLUB_BASE_URL=https://pterclub.net
```

默认已经使用当前域名 `https://pterclub.net`，通常无需设置。

### 运行示例

```text
========== PterClub 猫站 ==========

✅ Cookie 登录有效
👤 用户：example
🐱 当前猫粮：75,429.5
📅 今日状态：已签到
⚠️ 今日已经签到，无需重复执行
🔥 连续签到：未获取（站点响应未提供可确认的数据）
📊 当前猫粮：75,429.5

执行完成 ✅
```

如果站点没有提供可确认的连续签到数据，脚本会显示“未获取”，不会把累计签到次数误认为连续签到天数。

---

## English

This repository provides PT tracker sign-in scripts designed for QingLong.

### PterClub features

- Validate the login Cookie
- Read the username
- Read current cat-food bonus balance when available
- Detect today's sign-in status
- Call the sign-in endpoint when needed
- Parse the sign-in reward when available
- Try to parse consecutive sign-in days
- Refresh account statistics after sign-in
- Stop on CAPTCHA, anti-bot verification, or other verification challenges instead of bypassing them

### QingLong setup

Create the following environment variable in QingLong:

```text
Name: PTERCLUB_COOKIE
Value: your full PterClub Cookie
```

> ⚠️ Your Cookie is an account credential. Keep it only in your private QingLong environment variables. Never commit it to GitHub or publish it in issues, screenshots, or logs.

Python dependency:

```text
requests
```

Task command:

```bash
python3 pterclub.py
```

Suggested cron schedule:

```cron
17 8 * * *
```

Optional environment variable:

```text
PTERCLUB_BASE_URL=https://pterclub.net
```

The current default is already `https://pterclub.net`, so this is normally unnecessary.

## 免责声明 / Disclaimer

本项目仅用于个人账号的自动化管理与学习交流。PT 站点页面和接口可能随时变化，请遵守对应站点的规则。使用脚本产生的账号风险由使用者自行承担。

This project is intended for personal account automation and educational use. Tracker pages and APIs may change at any time. Please follow the rules of each tracker. You are responsible for any account risk caused by using these scripts.
