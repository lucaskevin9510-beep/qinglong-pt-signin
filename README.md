# QingLong PT Sign-in / 青龙 PT 自动签到

青龙面板可用的 PT 站自动签到脚本集合。每个站点使用独立脚本、独立环境变量，方便单独启用、停用和维护。

A collection of PT tracker auto sign-in scripts for QingLong. Each tracker uses an independent script and environment variable for easy maintenance and scheduling.

## 演示数据约定 / Demo Data Convention

本仓库中的账号、UID、Cookie、积分和签到数据均为**虚构演示数据**，不对应任何真实用户。为了让文档、截图和示例保持一致，统一使用下面这套演示身份：

```text
演示用户名：张三李四王二麻子
演示 UID：10086
演示猫粮：88,888.8
演示连续签到：28 天
演示签到奖励：150 猫粮
```

PterClub / NexusPHP Cookie 演示格式：

```text
c_secure_uid=10086; c_secure_pass=FAKE_TEST_00000000000000000000000000000000; c_secure_login=bm9wZQ%3D%3D; c_secure_ssl=eWVhaA%3D%3D; c_secure_tracker_ssl=eWVhaA%3D%3D
```

> ⚠️ 上面的 Cookie 只有字段结构与真实 NexusPHP Cookie 类似，所有凭证值都是故意构造的无效演示值，无法登录任何账号。仓库中禁止提交真实 Cookie、Passkey、Token、密码或其他账号凭证。

All usernames, UIDs, cookies, bonus balances, and sign-in data in this repository are **fictional demo data**. They do not belong to any real user. The same demo identity is used consistently throughout documentation and examples.

The Cookie example above mirrors the common NexusPHP Cookie key/value structure, but every credential value is intentionally fake and unusable.

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

如果只是阅读文档或测试变量格式，可以参考下面的**无效虚拟 Cookie**：

```text
PTERCLUB_COOKIE=c_secure_uid=10086; c_secure_pass=FAKE_TEST_00000000000000000000000000000000; c_secure_login=bm9wZQ%3D%3D; c_secure_ssl=eWVhaA%3D%3D; c_secure_tracker_ssl=eWVhaA%3D%3D
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

以下日志全部使用统一的虚拟演示账号：

```text
========== PterClub 猫站 ==========

✅ Cookie 登录有效
👤 用户：张三李四王二麻子
🐱 当前猫粮：88,888.8
📅 今日状态：未签到
🎯 开始签到...
✅ 签到成功
🔥 连续签到：28 天
🎁 本次奖励：150 猫粮
📊 当前猫粮：89,038.8

执行完成 ✅
```

如果当天已经签到：

```text
========== PterClub 猫站 ==========

✅ Cookie 登录有效
👤 用户：张三李四王二麻子
🐱 当前猫粮：88,888.8
📅 今日状态：已签到
⚠️ 今日已经签到，无需重复执行
🔥 连续签到：28 天
📊 当前猫粮：88,888.8

执行完成 ✅
```

如果站点没有提供可确认的连续签到数据，脚本会显示“未获取”，不会把累计签到次数误认为连续签到天数。

---

## English

This repository provides PT tracker sign-in scripts designed for QingLong.

### Demo identity

All examples use the same fictional identity:

```text
Demo username: 张三李四王二麻子
Demo UID: 10086
Demo cat-food balance: 88,888.8
Demo consecutive sign-in: 28 days
Demo sign-in reward: 150 cat-food points
```

Fake Cookie example using the common NexusPHP structure:

```text
c_secure_uid=10086; c_secure_pass=FAKE_TEST_00000000000000000000000000000000; c_secure_login=bm9wZQ%3D%3D; c_secure_ssl=eWVhaA%3D%3D; c_secure_tracker_ssl=eWVhaA%3D%3D
```

This Cookie is intentionally invalid and cannot log in to any account.

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

Fake format-only example:

```text
PTERCLUB_COOKIE=c_secure_uid=10086; c_secure_pass=FAKE_TEST_00000000000000000000000000000000; c_secure_login=bm9wZQ%3D%3D; c_secure_ssl=eWVhaA%3D%3D; c_secure_tracker_ssl=eWVhaA%3D%3D
```

> ⚠️ Your real Cookie is an account credential. Keep it only in your private QingLong environment variables. Never commit it to GitHub or publish it in issues, screenshots, or logs.

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
