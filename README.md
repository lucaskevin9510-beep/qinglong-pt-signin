<div align="center">

**🇨🇳 简体中文** · [🇺🇸 English](./README_EN.md)

</div>

# 🚀 青龙 PT 自动签到

适用于青龙面板的 PT 站自动签到脚本集合。

每个 PT 站使用独立脚本、独立环境变量，方便单独启用、停用、定时和维护。

## 🧪 演示账号与示例

仓库里展示的账号、Cookie、积分和签到结果全部都是虚构示例，不对应任何真实用户。

```text
👤 演示用户名：张三
🆔 演示 UID：10086
🐱 演示猫粮：88,888.8
🔥 演示连续签到：28 天
🎁 演示签到奖励：150 猫粮
```

PterClub Cookie 结构示例：

```text
c_lang_folder=chs; c_secure_uid=<BASE64_UID>; c_secure_pass=v2%3A<FAKE_ENCRYPTED_PASS>.<FAKE_SIGNATURE>; c_secure_ssl=<BASE64_SSL_FLAG>; c_secure_tracker_ssl=<BASE64_TRACKER_SSL_FLAG>; c_secure_login=<BASE64_LOGIN_FLAG>; PHPSESSID=<FAKE_SESSION_ID>
```

> ⚠️ 上面的 Cookie 保留了真实字段名、字段顺序和整体结构，但所有值都是明确的占位符，不能用于登录任何账号。

## ✅ 已支持站点

| 站点 | 脚本 | 环境变量 | 状态 |
| --- | --- | --- | --- |
| PterClub 猫站 | `pterclub.py` | `PTERCLUB_COOKIE` | ✅ 可用 |

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

只想核对格式时，可以参考下面这个无效示例：

```text
PTERCLUB_COOKIE=c_lang_folder=chs; c_secure_uid=<BASE64_UID>; c_secure_pass=v2%3A<FAKE_ENCRYPTED_PASS>.<FAKE_SIGNATURE>; c_secure_ssl=<BASE64_SSL_FLAG>; c_secure_tracker_ssl=<BASE64_TRACKER_SSL_FLAG>; c_secure_login=<BASE64_LOGIN_FLAG>; PHPSESSID=<FAKE_SESSION_ID>
```

> 🔐 真实 Cookie 属于账号凭证，只应保存在你自己的青龙环境变量中。不要提交到 GitHub、Issue、日志截图或其他公开位置。

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

## 🧾 运行示例

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

## 🔐 凭证安全

仓库中不要提交任何真实 Cookie、Passkey、Token、密码、Session ID 或其他账号凭证。

## ⚠️ 免责声明

本项目仅用于个人账号自动化管理和学习交流。PT 站点页面与接口可能随时变化，请遵守对应站点规则。使用脚本产生的账号风险由使用者自行承担。
