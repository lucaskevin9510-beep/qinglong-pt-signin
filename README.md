<div align="center">

**🇨🇳 简体中文** · [🇺🇸 English](./README_EN.md)

</div>

# 🚀 青龙 PT 自动签到

适用于青龙面板的 PT 站自动签到脚本集合。

每个 PT 站使用独立脚本、独立环境变量，方便单独启用、停用、定时和维护。

## 🧪 示例

```text
👤 用户名：张三
🆔 UID：10086
🐱 猫粮：88,888.8
🔥 连续签到：28 天
🎁 签到奖励：150 猫粮
```

## ✅ 已支持站点

| 站点 | 脚本 | 环境变量 | 状态 |
| --- | --- | --- | --- |
| PterClub 猫站 | `pterclub.py` | `PTERCLUB_COOKIE` | ✅ 可用 |
| HDHome | `hdhome.py` | `HDHOME_COOKIE` | ✅ 可用 |
| HHanClub 憨憨 | `hhanclub.py` | `HHANCLUB_COOKIE` | ✅ 可用 |
| CarPT | `carpt.py` | `CARPT_COOKIE` | ✅ 可用 |
| HDArea 好大 | `hdarea.py` | `HDAREA_COOKIE` | ✅ 可用 |
| UBits | `ubits.py` | `UBITS_COOKIE` | ✅ 可用 |
| QingWa 青蛙 | `qingwa.py` | `QINGWA_COOKIE` | ✅ 可用 |
| PTSKIT 拾刻 | `ptskit.py` | `PTSKIT_COOKIE` | ✅ 可用 |
| MomentPT | `moment.py` | `MOMENT_COOKIE` | ✅ 可用 |

## 🐱 PterClub 猫站

### ✨ 功能

- 检查 Cookie 登录状态
- 获取用户名
- 获取当前猫粮
- 检查今日签到状态
- 未签到时自动执行签到
- 尝试获取本次签到奖励
- 尝试获取连续签到天数
- 签到后重新读取猫粮数据
- 遇到验证码、人机验证或风控时停止，不尝试绕过

### ⚙️ 青龙配置

先在青龙的“环境变量”中创建：

```text
名称：PTERCLUB_COOKIE
值：你的完整 PterClub Cookie
```

Cookie 格式示例：

```text
PTERCLUB_COOKIE=c_lang_folder=chs; c_secure_uid=<BASE64_UID>; c_secure_pass=v2%3A<FAKE_ENCRYPTED_PASS>.<FAKE_SIGNATURE>; c_secure_ssl=<BASE64_SSL_FLAG>; c_secure_tracker_ssl=<BASE64_TRACKER_SSL_FLAG>; c_secure_login=<BASE64_LOGIN_FLAG>; PHPSESSID=<FAKE_SESSION_ID>
```

> 🔐 请把上面的占位内容替换为你自己的 Cookie，并只保存在青龙环境变量中。

### 📦 依赖

```text
requests
```

如果青龙还没有安装，可以在 **依赖管理 → Python3** 中添加：

```text
requests
```

### ▶️ 任务命令

```bash
python3 pterclub.py
```

### ⏰ 建议定时

```cron
17 8 * * *
```

### 🌐 可选环境变量

```text
PTERCLUB_BASE_URL=https://pterclub.net
```

脚本默认已经使用 `https://pterclub.net`，通常无需额外设置。

## 🧾 PterClub 运行示例

### 当天第一次签到

```text
========== PterClub 猫站 ==========

✅ Cookie 登录有效
👤 用户：张三
🐱 当前猫粮：88,888.8
📅 今日状态：未签到
🎯 开始签到...
✅ 签到成功
🔥 连续签到：28 天
🎁 本次奖励：150 猫粮
📊 当前猫粮：89,038.8

执行完成 ✅
```

### 当天已经签到

```text
========== PterClub 猫站 ==========

✅ Cookie 登录有效
👤 用户：张三
🐱 当前猫粮：88,888.8
📅 今日状态：已签到
⚠️ 今日已经签到，无需重复执行
🔥 连续签到：28 天
📊 当前猫粮：88,888.8

执行完成 ✅
```

如果站点没有提供可以确认的连续签到数据，脚本会显示“未获取”，不会把累计签到次数误认为连续签到天数。

---

## 🏠 HDHome

### ✨ 功能

- 检查 Cookie 登录状态
- 获取用户名
- 获取当前魔力值
- 检查今日签到状态
- 未签到时自动执行签到
- 尝试获取累计签到次数
- 尝试获取连续签到天数
- 尝试获取本次魔力奖励
- 签到后重新读取魔力值
- 遇到验证码、人机验证或风控时停止，不尝试绕过

### ⚙️ 青龙配置

在青龙的“环境变量”中创建：

```text
名称：HDHOME_COOKIE
值：你的完整 HDHome Cookie
```

### 📦 依赖

```text
requests
```

### ▶️ 任务命令

```bash
python3 hdhome.py
```

### ⏰ 建议定时

```cron
23 8 * * *
```

### 🌐 可选环境变量

```text
HDHOME_BASE_URL=https://hdhome.org
```

脚本默认已经使用 `https://hdhome.org`，通常无需额外设置。

## 🧾 HDHome 运行示例

### 当天第一次签到

```text
========== HDHome ==========

✅ Cookie 登录有效
👤 用户：张三
✨ 当前魔力：88,888.8
📅 今日状态：未签到
🎯 开始签到...
✅ 签到成功
📆 累计签到：123 次
🔥 连续签到：28 天
🎁 本次奖励：50 魔力值
📊 当前魔力：88,938.8

执行完成 ✅
```

### 当天已经签到

```text
========== HDHome ==========

✅ Cookie 登录有效
👤 用户：张三
✨ 当前魔力：88,888.8
📅 今日状态：已签到
⚠️ 今日已经签到，无需重复执行
📆 累计签到：未获取
🔥 连续签到：未获取
📊 当前魔力：88,888.8

执行完成 ✅
```

无法从站点返回中确认的数据会显示“未获取”。

---

## 💰 HHanClub 憨憨

### ✨ 功能

- 检查 Cookie 登录状态
- 获取用户名
- 获取当前憨豆
- 检查今日签到状态
- 未签到时自动执行签到
- 获取累计签到次数
- 获取连续签到天数
- 获取本次憨豆奖励
- 签到后重新读取憨豆余额
- 遇到 2FA、验证码、人机验证或风控时停止，不尝试绕过

### ⚙️ 青龙配置

在青龙的“环境变量”中创建：

```text
名称：HHANCLUB_COOKIE
值：你的完整 HHanClub Cookie
```

### 📦 依赖

```text
requests
```

### ▶️ 任务命令

```bash
python3 hhanclub.py
```

### ⏰ 建议定时

```cron
31 8 * * *
```

### 🌐 可选环境变量

```text
HHANCLUB_BASE_URL=https://hhanclub.net
```

脚本默认已经使用 `https://hhanclub.net`，通常无需额外设置。

## 🧾 HHanClub 运行示例

```text
========== HHanClub 憨憨 ==========

✅ Cookie 登录有效
👤 用户：张三
💰 当前憨豆：88,888
📅 今日状态：未签到或首页未明确显示
🎯 开始签到...
✅ 签到成功
📆 累计签到：123 次
🔥 连续签到：28 天
🎁 本次奖励：10 憨豆
📊 当前憨豆：88,898

执行完成 ✅
```

---

## 🚗 CarPT

### ✨ 功能

- 检查 Cookie 登录状态
- 获取用户名
- 获取当前魔力值
- 检查今日签到状态
- 未签到时自动执行签到
- 获取本次签到魔力奖励
- 尝试获取累计签到次数
- 尝试获取连续签到天数
- 签到后重新读取魔力值
- 遇到 2FA、验证码、人机验证或风控时停止，不尝试绕过

### ⚙️ 青龙配置

在青龙的“环境变量”中创建：

```text
名称：CARPT_COOKIE
值：你的完整 CarPT Cookie
```

### 📦 依赖

```text
requests
```

### ▶️ 任务命令

```bash
python3 carpt.py
```

### ⏰ 建议定时

```cron
37 8 * * *
```

### 🌐 可选环境变量

```text
CARPT_BASE_URL=https://carpt.net
```

脚本默认已经使用 `https://carpt.net`，通常无需额外设置。

## 🧾 CarPT 运行示例

```text
========== CarPT ==========

✅ Cookie 登录有效
👤 用户：张三
💰 当前魔力：88,888
📅 今日状态：已签到
⚠️ 今日已经签到，无需重复执行
📆 累计签到：123 次
🔥 连续签到：28 天
🎁 本次签到：10 魔力
📊 当前魔力：88,888

执行完成 ✅
```

---

## 🌊 HDArea 好大

### ✨ 功能

- 检查 Cookie 登录状态
- 获取用户名
- 获取当前魔力值
- 检查今日签到状态
- 未签到时自动执行签到
- 使用 `sign_in.php` 完成每日签到
- 尝试获取本次签到奖励
- 显示站点返回信息
- 签到后重新读取魔力值
- 遇到验证码、人机验证或风控时停止，不尝试绕过

### ⚙️ 青龙配置

在青龙的“环境变量”中创建：

```text
名称：HDAREA_COOKIE
值：你的完整 HDArea Cookie
```

### 📦 依赖

```text
requests
```

### ▶️ 任务命令

```bash
python3 hdarea.py
```

### ⏰ 建议定时

```cron
43 8 * * *
```

### 🌐 可选环境变量

```text
HDAREA_BASE_URL=https://hdarea.club
```

脚本默认已经使用 `https://hdarea.club`，通常无需额外设置。

## 🧾 HDArea 运行示例

```text
========== HDArea 好大 ==========

✅ Cookie 登录有效
👤 用户：张三
💰 当前魔力：88,888.8
📅 今日状态：已签到
⚠️ 今日已经签到，无需重复执行
💬 站点返回：请不要重复签到哦！
📊 当前魔力：88,888.8

执行完成 ✅
```


---

## 💎 UBits

### ✨ 功能

- 检查 Cookie 登录状态
- 获取用户名
- 获取当前 U币余额
- 检查今日签到状态
- 未签到时自动执行签到
- 使用 `attendance.php` 完成每日签到
- 获取累计签到次数
- 获取连续签到天数
- 获取本次 U币奖励
- 签到后重新读取 U币余额
- 遇到 2FA、验证码、人机验证、Cloudflare Challenge 或风控时停止，不尝试绕过

### ⚙️ 青龙配置

在青龙的“环境变量”中创建：

```text
名称：UBITS_COOKIE
值：你的完整 UBits Cookie
```

### 📦 依赖

```text
requests
```

### ▶️ 任务命令

```bash
python3 ubits.py
```

### ⏰ 建议定时

```cron
49 8 * * *
```

### 🌐 可选环境变量

```text
UBITS_BASE_URL=https://ubits.club
```

脚本默认已经使用 `https://ubits.club`，通常无需额外设置。

## 🧾 UBits 运行示例

```text
========== UBits ==========

✅ Cookie 登录有效
👤 用户：张三
💰 当前U币：88,888.8
📅 今日状态：已签到
⚠️ 今日已经签到，无需重复执行
📆 累计签到：54 次
🔥 连续签到：1 天
🎁 本次签到：10 U币
📊 当前U币：88,888.8

执行完成 ✅
```

---

## 🐸 QingWa 青蛙

### ✨ 功能

- 检查 Cookie 登录状态并读取用户名、UID
- 使用 `attendance.php` 完成或确认每日签到
- 获取累计签到次数、连续签到天数和签到奖励
- 从首页 `color_uploaded` 字段读取站点实际显示的上传量
- 每天最多一次在首页群聊发送“蛙总，求上传”请求额外上传量
- 发送后重新读取上传量并计算实际增加值
- 按 UID 和日期记录发送状态，避免重复刷群聊
- Cookie 只发送给 `qingwapt.com` 域名族，外域跳转会直接停止
- 遇到 2FA、验证码、人机验证或 Cloudflare 风控时停止，不尝试绕过

### ⚙️ 青龙配置

在青龙的“环境变量”中创建：

```text
名称：QINGWA_COOKIE
值：你的完整 QingWa Cookie
```

### 📦 依赖

```text
curl_cffi
```

### ▶️ 任务命令

```bash
python3 qingwa.py
```

### ⏰ 建议定时

```cron
55 8 * * *
```

### 🌐 可选环境变量

```text
QINGWA_BASE_URL=https://www.qingwapt.com
```

脚本默认已经使用 `https://www.qingwapt.com`，通常无需额外设置。

## 🧾 QingWa 运行示例

```text
========== QingWa 青蛙 ==========

✅ Cookie 登录有效
👤 用户：张三
🆔 UID：10086
⬆️ 当前上传量：8.888 TB
📅 今日状态：已签到
⚠️ 今日已经签到，无需重复执行
📆 累计签到：123 次
🔥 连续签到：28 天
🎁 本次签到：10 魔力

🐸 请求额外上传量...
💬 发送：蛙总，求上传
✅ 群聊消息发送成功
⬆️ 获取后上传量：8.988 TB
🎁 本次增加上传量：+102.40 GB
📊 当前魔力：未获取

执行完成 ✅
```

当天已经自动发送过“蛙总，求上传”时，脚本会跳过重复发送。

---

## ⏱️ PTSKIT 拾刻

### ✨ 功能

- 检查 Cookie 登录状态并读取用户名、UID
- 从首页精确读取当前魔力值
- 从首页读取上传量、下载量和做种积分
- 检查今日签到状态
- 未签到时使用 `attendance.php` 完成每日签到
- 获取今日签到魔力奖励
- 获取补签卡数量
- 尝试获取累计签到次数和连续签到天数
- 签到后重新读取魔力值
- 遇到 2FA、验证码、人机验证或风控时停止，不尝试绕过

### ⚙️ 青龙配置

在青龙的“环境变量”中创建：

```text
名称：PTSKIT_COOKIE
值：你的完整 PTSKIT Cookie
```

### 📦 依赖

```text
requests
```

### ▶️ 任务命令

```bash
python3 ptskit.py
```

### ⏰ 建议定时

```cron
59 8 * * *
```

### 🌐 可选环境变量

```text
PTSKIT_BASE_URL=https://www.ptskit.com
```

脚本默认已经使用 `https://www.ptskit.com`，通常无需额外设置。

## 🧾 PTSKIT 运行示例

```text
========== PTSKIT 拾刻 ==========

✅ Cookie 登录有效
👤 用户：张三
🆔 UID：10086
💰 当前魔力：88,888.8
⬆️ 上传量：60.485 TB
⬇️ 下载量：1.116 TB
🌱 做种积分：149,087
📅 今日状态：已签到
⚠️ 今日已经签到，无需重复执行
🎁 今日签到：10 魔力
🎫 补签卡：20

执行完成 ✅
```

---

## 🎞️ MomentPT

### ✨ 功能

- 检查 Cookie 登录状态并读取用户名、UID
- 从首页读取当前魔力值、上传量和下载量
- 检查今日签到状态，未签到时使用 `attendance.php` 完成每日签到
- 获取今日签到魔力奖励和补签卡数量
- 每天依次向喊话框发送“茄子”和“保一条”
- 两条消息之间随机等待 4～5 秒
- 按 UID、日期和每条消息分别记录状态，避免重复发送
- 发送后重新读取魔力值，并在发生变化时显示增减量
- 外域跳转会直接停止，不继续携带 Cookie 请求
- 遇到 2FA、验证码、人机验证或风控时停止，不尝试绕过

### ⚙️ 青龙配置

在青龙的“环境变量”中创建：

```text
名称：MOMENT_COOKIE
值：你的完整 MomentPT Cookie
```

### 📦 依赖

```text
requests
```

### ▶️ 任务命令

```bash
python3 moment.py
```

### ⏰ 建议定时

```cron
7 9 * * *
```

### 🌐 可选环境变量

```text
MOMENT_BASE_URL=https://www.momentpt.top
```

脚本默认已经使用 `https://www.momentpt.top`，通常无需额外设置。

## 🧾 MomentPT 运行示例

```text
========== MomentPT ==========

✅ Cookie 登录有效
👤 用户：张三
🆔 UID：10086
💰 当前魔力：888,888
⬆️ 上传量：8.888 TB
⬇️ 下载量：888.88 GB
📅 今日状态：已签到
⚠️ 今日已经签到，无需重复执行
🎁 今日签到：10 魔力
🎫 补签卡：1

🎞️ Moment 每日喊话...
💬 发送：茄子
✅ 群聊消息发送成功
⏳ 等待 4.6 秒后发送下一条...
💬 发送：保一条
✅ 群聊消息发送成功

📊 当前魔力：889,139
🎁 魔力变化：+251

执行完成 ✅
```

当天已经记录过某一条消息时，脚本只跳过该条；未成功确认进入喊话记录的消息不会写入已发送状态。

## ⚠️ 免责声明

本项目仅用于个人账号自动化管理和学习交流。PT 站点页面与接口可能随时变化，请遵守对应站点规则。使用脚本产生的账号风险由使用者自行承担。
