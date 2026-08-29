<div align="center">

[🇨🇳 简体中文](./README.md) · **🇺🇸 English**

</div>

# 🚀 QingLong PT Auto Sign-in

A collection of automated PT tracker sign-in scripts designed for QingLong.

Each tracker uses its own standalone script and environment variable, so every tracker can be enabled, disabled, scheduled, and maintained independently.

## 🧪 Demo Account & Examples

All account details, cookies, balances, and sign-in results shown in this repository are fictional examples and do not belong to any real user.

```text
👤 Demo username: 张三
🆔 Demo UID: 10086
🐱 Demo cat-food balance: 88,888.8
🔥 Demo consecutive sign-in: 28 days
🎁 Demo sign-in reward: 150 cat-food points
```

Example PterClub Cookie structure:

```text
c_lang_folder=chs; c_secure_uid=<BASE64_UID>; c_secure_pass=v2%3A<FAKE_ENCRYPTED_PASS>.<FAKE_SIGNATURE>; c_secure_ssl=<BASE64_SSL_FLAG>; c_secure_tracker_ssl=<BASE64_TRACKER_SSL_FLAG>; c_secure_login=<BASE64_LOGIN_FLAG>; PHPSESSID=<FAKE_SESSION_ID>
```

> ⚠️ The example above preserves the real field names and overall Cookie structure, but every value is an explicit placeholder. It cannot be used to log in to any account.

## ✅ Supported Trackers

| Tracker | Script | Environment Variable | Status |
| --- | --- | --- | --- |
| PterClub | `pterclub.py` | `PTERCLUB_COOKIE` | ✅ Working |

## 🐱 PterClub

### ✨ Features

- Validate the login Cookie
- Read the username
- Read the current cat-food balance
- Detect today's sign-in status
- Automatically sign in when needed
- Try to parse the sign-in reward
- Try to parse consecutive sign-in days
- Refresh account statistics after sign-in
- Stop on CAPTCHA, anti-bot verification, or other verification challenges instead of bypassing them

### ⚙️ QingLong Setup

Create the following environment variable in QingLong:

```text
Name: PTERCLUB_COOKIE
Value: your full PterClub Cookie
```

Format-only example:

```text
PTERCLUB_COOKIE=c_lang_folder=chs; c_secure_uid=<BASE64_UID>; c_secure_pass=v2%3A<FAKE_ENCRYPTED_PASS>.<FAKE_SIGNATURE>; c_secure_ssl=<BASE64_SSL_FLAG>; c_secure_tracker_ssl=<BASE64_TRACKER_SSL_FLAG>; c_secure_login=<BASE64_LOGIN_FLAG>; PHPSESSID=<FAKE_SESSION_ID>
```

> 🔐 Your real Cookie is an account credential. Keep it only in your private QingLong environment variables. Never commit it to GitHub or publish it in issues, screenshots, or logs.

### 📦 Dependency

```text
requests
```

If it is not installed in QingLong, add `requests` under **Dependency Management → Python3**.

### ▶️ Task Command

```bash
python3 pterclub.py
```

### ⏰ Suggested Schedule

```cron
17 8 * * *
```

### 🌐 Optional Environment Variable

```text
PTERCLUB_BASE_URL=https://pterclub.net
```

The script already uses `https://pterclub.net` by default, so this variable is normally unnecessary.

## 🧾 Example Output

### First sign-in of the day

```text
========== PterClub ==========

✅ Cookie login valid
👤 User: 张三
🐱 Current cat-food: 88,888.8
📅 Today: not signed in
🎯 Starting sign-in...
✅ Sign-in successful
🔥 Consecutive sign-in: 28 days
🎁 Reward: 150 cat-food points
📊 Current cat-food: 89,038.8

Completed ✅
```

### Already signed in

```text
========== PterClub ==========

✅ Cookie login valid
👤 User: 张三
🐱 Current cat-food: 88,888.8
📅 Today: already signed in
⚠️ No duplicate sign-in needed
🔥 Consecutive sign-in: 28 days
📊 Current cat-food: 88,888.8

Completed ✅
```

If the tracker does not provide verifiable consecutive sign-in data, the script displays `Not available` instead of incorrectly treating the total sign-in count as a streak.

## 🔐 Credential Safety

Never commit any real Cookie, Passkey, Token, password, session ID, or other account credential to this repository.

## ⚠️ Disclaimer

This project is intended for personal account automation and educational use. Tracker pages and APIs may change at any time. Please follow the rules of each tracker. You are responsible for any account risk caused by using these scripts.
