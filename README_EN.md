<div align="center">

[🇨🇳 简体中文](./README.md) · **🇺🇸 English**

</div>

# 🚀 QingLong PT Auto Sign-in

A collection of automated PT tracker sign-in scripts designed for QingLong.

Each tracker uses its own standalone script and environment variable, so every tracker can be enabled, disabled, scheduled, and maintained independently.

## 🧪 Example

```text
👤 Username: 张三
🆔 UID: 10086
🐱 Cat-food: 88,888.8
🔥 Consecutive sign-in: 28 days
🎁 Sign-in reward: 150 cat-food points
```

## ✅ Supported Trackers

| Tracker | Script | Environment Variable | Status |
| --- | --- | --- | --- |
| PterClub | `pterclub.py` | `PTERCLUB_COOKIE` | ✅ Working |
| HDHome | `hdhome.py` | `HDHOME_COOKIE` | ✅ Working |
| HHanClub | `hhanclub.py` | `HHANCLUB_COOKIE` | ✅ Working |
| CarPT | `carpt.py` | `CARPT_COOKIE` | ✅ Working |
| HDArea | `hdarea.py` | `HDAREA_COOKIE` | ✅ Working |
| UBits | `ubits.py` | `UBITS_COOKIE` | ✅ Working |
| QingWa | `qingwa.py` | `QINGWA_COOKIE` | ✅ Working |
| PTSKIT | `ptskit.py` | `PTSKIT_COOKIE` | ✅ Working |

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

Cookie format example:

```text
PTERCLUB_COOKIE=c_lang_folder=chs; c_secure_uid=<BASE64_UID>; c_secure_pass=v2%3A<FAKE_ENCRYPTED_PASS>.<FAKE_SIGNATURE>; c_secure_ssl=<BASE64_SSL_FLAG>; c_secure_tracker_ssl=<BASE64_TRACKER_SSL_FLAG>; c_secure_login=<BASE64_LOGIN_FLAG>; PHPSESSID=<FAKE_SESSION_ID>
```

> 🔐 Replace the placeholders above with your own Cookie and keep it only in your QingLong environment variables.

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

## 🧾 PterClub Example Output

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

---

## 🏠 HDHome

### ✨ Features

- Validate the login Cookie
- Read the username
- Read the current magic-point balance
- Detect today's sign-in status
- Automatically sign in when needed
- Try to parse total sign-in count
- Try to parse consecutive sign-in days
- Try to parse the current sign-in reward
- Refresh the magic-point balance after sign-in
- Stop on CAPTCHA, anti-bot verification, or other verification challenges instead of bypassing them

### ⚙️ QingLong Setup

Create the following environment variable in QingLong:

```text
Name: HDHOME_COOKIE
Value: your full HDHome Cookie
```

### 📦 Dependency

```text
requests
```

### ▶️ Task Command

```bash
python3 hdhome.py
```

### ⏰ Suggested Schedule

```cron
23 8 * * *
```

### 🌐 Optional Environment Variable

```text
HDHOME_BASE_URL=https://hdhome.org
```

The script already uses `https://hdhome.org` by default, so this variable is normally unnecessary.

## 🧾 HDHome Example Output

### First sign-in of the day

```text
========== HDHome ==========

✅ Cookie login valid
👤 User: 张三
✨ Current magic points: 88,888.8
📅 Today: not signed in
🎯 Starting sign-in...
✅ Sign-in successful
📆 Total sign-ins: 123
🔥 Consecutive sign-in: 28 days
🎁 Reward: 50 magic points
📊 Current magic points: 88,938.8

Completed ✅
```

### Already signed in

```text
========== HDHome ==========

✅ Cookie login valid
👤 User: 张三
✨ Current magic points: 88,888.8
📅 Today: already signed in
⚠️ No duplicate sign-in needed
📆 Total sign-ins: Not available
🔥 Consecutive sign-in: Not available
📊 Current magic points: 88,888.8

Completed ✅
```

Data that cannot be confirmed from the tracker response is shown as `Not available`.

---

## 💰 HHanClub

### ✨ Features

- Validate the login Cookie
- Read the username
- Read the current HanBean balance
- Detect today's sign-in status
- Automatically sign in when needed
- Read the total sign-in count
- Read consecutive sign-in days
- Read the current HanBean reward
- Refresh the HanBean balance after sign-in
- Stop on 2FA, CAPTCHA, anti-bot verification, or other verification challenges instead of bypassing them

### ⚙️ QingLong Setup

Create the following environment variable in QingLong:

```text
Name: HHANCLUB_COOKIE
Value: your full HHanClub Cookie
```

### 📦 Dependency

```text
requests
```

### ▶️ Task Command

```bash
python3 hhanclub.py
```

### ⏰ Suggested Schedule

```cron
31 8 * * *
```

### 🌐 Optional Environment Variable

```text
HHANCLUB_BASE_URL=https://hhanclub.net
```

The script already uses `https://hhanclub.net` by default, so this variable is normally unnecessary.

## 🧾 HHanClub Example Output

```text
========== HHanClub ==========

✅ Cookie login valid
👤 User: 张三
💰 Current HanBean: 88,888
📅 Today: not signed in or not clearly shown on the homepage
🎯 Starting sign-in...
✅ Sign-in successful
📆 Total sign-ins: 123
🔥 Consecutive sign-in: 28 days
🎁 Reward: 10 HanBeans
📊 Current HanBean: 88,898

Completed ✅
```

---

## 🚗 CarPT

### ✨ Features

- Validate the login Cookie
- Read the username
- Read the current magic-point balance
- Detect today's sign-in status
- Automatically sign in when needed
- Read the current sign-in reward
- Try to parse total sign-in count
- Try to parse consecutive sign-in days
- Refresh the magic-point balance after sign-in
- Stop on 2FA, CAPTCHA, anti-bot verification, or other verification challenges instead of bypassing them

### ⚙️ QingLong Setup

Create the following environment variable in QingLong:

```text
Name: CARPT_COOKIE
Value: your full CarPT Cookie
```

### 📦 Dependency

```text
requests
```

### ▶️ Task Command

```bash
python3 carpt.py
```

### ⏰ Suggested Schedule

```cron
37 8 * * *
```

### 🌐 Optional Environment Variable

```text
CARPT_BASE_URL=https://carpt.net
```

The script already uses `https://carpt.net` by default, so this variable is normally unnecessary.

## 🧾 CarPT Example Output

```text
========== CarPT ==========

✅ Cookie login valid
👤 User: 张三
💰 Current magic points: 88,888
📅 Today: already signed in
⚠️ No duplicate sign-in needed
📆 Total sign-ins: 123
🔥 Consecutive sign-in: 28 days
🎁 Current sign-in: 10 magic points
📊 Current magic points: 88,888

Completed ✅
```

---

## 🌊 HDArea

### ✨ Features

- Validate the login Cookie
- Read the username
- Read the current magic-point balance
- Detect today's sign-in status
- Automatically sign in when needed
- Use `sign_in.php` for the daily sign-in
- Try to parse the current sign-in reward
- Display the tracker's response message
- Refresh the magic-point balance after sign-in
- Stop on CAPTCHA, anti-bot verification, or other verification challenges instead of bypassing them

### ⚙️ QingLong Setup

Create the following environment variable in QingLong:

```text
Name: HDAREA_COOKIE
Value: your full HDArea Cookie
```

### 📦 Dependency

```text
requests
```

### ▶️ Task Command

```bash
python3 hdarea.py
```

### ⏰ Suggested Schedule

```cron
43 8 * * *
```

### 🌐 Optional Environment Variable

```text
HDAREA_BASE_URL=https://hdarea.club
```

The script already uses `https://hdarea.club` by default, so this variable is normally unnecessary.

## 🧾 HDArea Example Output

```text
========== HDArea ==========

✅ Cookie login valid
👤 User: 张三
💰 Current magic points: 88,888.8
📅 Today: already signed in
⚠️ No duplicate sign-in needed
💬 Tracker response: Already signed in today
📊 Current magic points: 88,888.8

Completed ✅
```

---

## 💎 UBits

### ✨ Features

- Validate the login Cookie
- Read the username
- Read the current UCoin balance
- Detect today's sign-in status
- Automatically sign in when needed
- Use `attendance.php` for the daily sign-in
- Read the total sign-in count
- Read consecutive sign-in days
- Read the current UCoin reward
- Refresh the UCoin balance after sign-in
- Stop on 2FA, CAPTCHA, Cloudflare Challenge, anti-bot verification, or other verification challenges instead of bypassing them

### ⚙️ QingLong Setup

Create the following environment variable in QingLong:

```text
Name: UBITS_COOKIE
Value: your full UBits Cookie
```

### 📦 Dependency

```text
requests
```

### ▶️ Task Command

```bash
python3 ubits.py
```

### ⏰ Suggested Schedule

```cron
49 8 * * *
```

### 🌐 Optional Environment Variable

```text
UBITS_BASE_URL=https://ubits.club
```

The script already uses `https://ubits.club` by default, so this variable is normally unnecessary.

## 🧾 UBits Example Output

```text
========== UBits ==========

✅ Cookie login valid
👤 User: 张三
💰 Current UCoin: 88,888.8
📅 Today: already signed in
⚠️ No duplicate sign-in needed
📆 Total sign-ins: 54
🔥 Consecutive sign-in: 1 day
🎁 Current sign-in: 10 UCoins
📊 Current UCoin: 88,888.8

Completed ✅
```

---

## 🐸 QingWa

### ✨ Features

- Validate the login Cookie and read the username and UID
- Use `attendance.php` for the daily sign-in
- Read total sign-in count, consecutive sign-in days, and the sign-in reward when available
- Read the upload total directly from the homepage `color_uploaded` field
- Send `蛙总，求上传` to the homepage shoutbox at most once per day to request extra upload credit
- Re-read the upload total after sending and calculate the actual increase
- Keep a per-UID daily local state to avoid duplicate shoutbox messages
- Send the Cookie only to the `qingwapt.com` domain family and stop on external redirects
- Stop on 2FA, CAPTCHA, Cloudflare, or other verification challenges instead of bypassing them

### ⚙️ QingLong Setup

Create the following environment variable in QingLong:

```text
Name: QINGWA_COOKIE
Value: your full QingWa Cookie
```

### 📦 Dependency

```text
curl_cffi
```

### ▶️ Task Command

```bash
python3 qingwa.py
```

### ⏰ Suggested Schedule

```cron
55 8 * * *
```

### 🌐 Optional Environment Variable

```text
QINGWA_BASE_URL=https://www.qingwapt.com
```

The script already uses `https://www.qingwapt.com` by default, so this variable is normally unnecessary.

## 🧾 QingWa Example Output

```text
========== QingWa 青蛙 ==========

✅ Cookie login valid
👤 User: 张三
🆔 UID: 10086
⬆️ Current upload: 8.888 TB
📅 Today: already signed in
⚠️ No duplicate sign-in needed
📆 Total sign-ins: 123
🔥 Consecutive sign-in: 28 days
🎁 Current sign-in: 10 magic points

🐸 Requesting extra upload credit...
💬 Message: 蛙总，求上传
✅ Shoutbox message sent
⬆️ Upload after request: 8.988 TB
🎁 Upload gained: +102.40 GB
📊 Current magic points: Not available

Completed ✅
```

If the automatic `蛙总，求上传` request has already been sent for the current day, the script skips the duplicate message.

---

## ⏱️ PTSKIT

### ✨ Features

- Validate the login Cookie and read the username and UID
- Read the current magic-point balance precisely from the homepage
- Read upload, download, and seed-point totals from the homepage
- Detect today's sign-in status
- Use `attendance.php` for the daily sign-in when needed
- Read today's magic-point sign-in reward
- Read the number of makeup sign-in cards
- Try to read total sign-in count and consecutive sign-in days
- Refresh the magic-point balance after sign-in
- Stop on 2FA, CAPTCHA, anti-bot verification, or other verification challenges instead of bypassing them

### ⚙️ QingLong Setup

Create the following environment variable in QingLong:

```text
Name: PTSKIT_COOKIE
Value: your full PTSKIT Cookie
```

### 📦 Dependency

```text
requests
```

### ▶️ Task Command

```bash
python3 ptskit.py
```

### ⏰ Suggested Schedule

```cron
59 8 * * *
```

### 🌐 Optional Environment Variable

```text
PTSKIT_BASE_URL=https://www.ptskit.com
```

The script already uses `https://www.ptskit.com` by default, so this variable is normally unnecessary.

## 🧾 PTSKIT Example Output

```text
========== PTSKIT ==========

✅ Cookie login valid
👤 User: 张三
🆔 UID: 10086
💰 Current magic points: 88,888.8
⬆️ Uploaded: 60.485 TB
⬇️ Downloaded: 1.116 TB
🌱 Seed points: 149,087
📅 Today: already signed in
⚠️ No duplicate sign-in needed
🎁 Today's sign-in: 10 magic points
🎫 Makeup cards: 20

Completed ✅
```

## ⚠️ Disclaimer

This project is intended for personal account automation and educational use. Tracker pages and APIs may change at any time. Please follow the rules of each tracker. You are responsible for any account risk caused by using these scripts.