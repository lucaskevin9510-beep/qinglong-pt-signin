#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# cron: 31 8 * * *
# new Env("HHanClub 签到")

"""
HHanClub 青龙独立签到脚本

环境变量：
  HHANCLUB_COOKIE    必填，HHanClub 完整 Cookie
  HHANCLUB_BASE_URL  可选，默认 https://hhanclub.net

依赖：
  requests

功能：
  - 检查 Cookie 登录状态
  - 获取用户名
  - 获取当前憨豆（页面可解析时）
  - 使用 /attendance.php 执行或确认每日签到
  - 解析累计签到次数、连续签到天数、本次憨豆奖励
  - 签到后重新读取首页憨豆
  - 遇到 2FA / 验证码 / 人机验证 / 风控时停止，不尝试绕过

说明：
  站点页面可能随时调整。无法确认的数据会显示“未获取”，不会自行猜测。
"""

import os
import re
import time
from html import unescape
from typing import Dict, Optional
from urllib.parse import urljoin

import requests


COOKIE = os.getenv("HHANCLUB_COOKIE", "").strip()
BASE_URL = os.getenv("HHANCLUB_BASE_URL", "https://hhanclub.net").strip().rstrip("/")

TIMEOUT = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


def clean_text(text: str) -> str:
    text = unescape(text or "")
    text = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style\b[^>]*>[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def cookie_dict(cookie: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for part in cookie.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    requests.utils.add_dict_to_cookiejar(session.cookies, cookie_dict(COOKIE))
    return session


def get(session: requests.Session, path: str, referer: Optional[str] = None) -> requests.Response:
    headers = {}
    if referer:
        headers["Referer"] = referer
    return session.get(
        urljoin(BASE_URL + "/", path.lstrip("/")),
        headers=headers,
        timeout=TIMEOUT,
        allow_redirects=True,
    )


def detect_verification(text: str, final_url: str = "") -> Optional[str]:
    source = f"{final_url}\n{text or ''}"

    if re.search(r"take2fa\.php|两步验证|兩步驗證|2FA|TOTP|two[-\s]?factor", source, flags=re.I):
        return "两步验证 / 2FA"

    if re.search(
        r"验证码|驗證碼|人机验证|人機驗證|机器人验证|機器人驗證|"
        r"captcha|geetest|turnstile|cloudflare challenge|"
        r"滑块验证|滑塊驗證|安全校验|安全驗證|请确认您是合法用户",
        source,
        flags=re.I,
    ):
        return "验证码 / 人机验证 / 风控"

    return None


def parse_username(html: str) -> Optional[str]:
    text = clean_text(html)

    patterns = [
        r"欢迎回来\s*[,，]\s*([^\s\[，,]+)",
        r"([^\s,，]+)\s*[,，]\s*欢迎回来",
        r"歡迎回來\s*[,，]\s*([^\s\[，,]+)",
        r"([^\s,，]+)\s*[,，]\s*歡迎回來",
        r"嗨[,，]\s*([^\s🎈\[]+)",
        r"Welcome back\s*[,，]?\s*([^\s\[，,]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return m.group(1).strip()

    # NexusPHP 常见用户详情链接
    matches = re.findall(
        r'<a[^>]+href=["\'][^"\']*userdetails\.php\?id=\d+[^"\']*["\'][^>]*>([\s\S]*?)</a>',
        html or "",
        flags=re.I,
    )
    for raw in matches:
        name = clean_text(raw)
        if name and 1 <= len(name) <= 80 and not re.search(r"详情|details", name, flags=re.I):
            return name

    return None


def login_is_valid(html: str, final_url: str) -> bool:
    text = clean_text(html)

    if "login.php" in (final_url or "").lower():
        return False

    if re.search(
        r"该页面必须在登录后才能访问|該頁面必須在登錄後才能訪問|"
        r"请先登录|請先登錄|登录后才能访问|登錄後才能訪問|"
        r"you must be logged in|please log in",
        text,
        flags=re.I,
    ):
        return False

    if re.search(
        r"userdetails\.php\?id=\d+|logout\.php|欢迎回来|歡迎回來|"
        r"控制面板|用户中心|用戶中心|usercp\.php|签到得憨豆",
        html or "",
        flags=re.I,
    ):
        return True

    return parse_username(html) is not None


def number_from_string(value: str) -> Optional[float]:
    if value is None:
        return None
    raw = str(value).replace(",", "").strip()
    try:
        return float(raw)
    except ValueError:
        return None


def parse_hanbean(html: str) -> Optional[float]:
    text = clean_text(html)

    # HHanClub 首页常见区域会出现：
    # [签到得憨豆] [邀请] : N 123,456 [勋章] 1.23 TB ...
    # 这里优先解析“邀请数后面的憨豆余额”。
    panel_patterns = [
        r"\[?签到得憨豆\]?\s*\[?邀请\]?\s*[:：]\s*\d+\s+([0-9][0-9,.]*)\s*\[?勋章\]?",
        r"签到得憨豆\s+邀请\s*[:：]?\s*\d+\s+([0-9][0-9,.]*)",
    ]
    for pattern in panel_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            value = number_from_string(m.group(1))
            if value is not None:
                return value

    direct_patterns = [
        r"憨豆\s*(?:\[[^\]]*\]\s*)?[:：]?\s*([0-9][0-9,.]*)",
        r"当前憨豆\s*[:：]?\s*([0-9][0-9,.]*)",
        r"當前憨豆\s*[:：]?\s*([0-9][0-9,.]*)",
        r"HanBean\s*[:：]?\s*([0-9][0-9,.]*)",
    ]
    for pattern in direct_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            value = number_from_string(m.group(1))
            if value is not None:
                return value

    return None


def fmt_number(value: Optional[float]) -> str:
    if value is None:
        return "未获取"
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.3f}".rstrip("0").rstrip(".")


def homepage_already_signed(html: str) -> bool:
    text = clean_text(html)
    return bool(re.search(
        r"签到已得\s*[0-9,.]+|簽到已得\s*[0-9,.]+|"
        r"今日已签到|今日已簽到|今天已经签到|今天已經簽到|"
        r"已经签到|已經簽到|已签到|已簽到|"
        r"Attend got\s*[:：]?\s*[0-9,.]+|Showed\s*Up",
        text,
        flags=re.I,
    ))


def parse_attendance(html: str) -> Dict[str, object]:
    text = clean_text(html)

    result: Dict[str, object] = {
        "success": False,
        "already": False,
        "total_times": None,
        "streak_days": None,
        "reward": None,
        "message": "",
    }

    # NexusPHP 常见：
    # 这是您的第 N 次签到，已连续签到 N 天，本次签到获得 N 个憨豆。
    full_patterns = [
        (
            r"这是您的第\s*(\d+)\s*次签到[,，]?\s*"
            r"已连续签到\s*(\d+)\s*天[,，]?\s*"
            r"本次签到获得\s*([0-9,.]+)\s*个?(?:憨豆|魔力值)",
            1, 2, 3,
        ),
        (
            r"這是您的第\s*(\d+)\s*次簽到[,，]?\s*"
            r"已連續簽到\s*(\d+)\s*天[,，]?\s*"
            r"本次簽到獲得\s*([0-9,.]+)\s*個?(?:憨豆|魔力值)",
            1, 2, 3,
        ),
    ]
    for pattern, i_total, i_streak, i_reward in full_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            result["success"] = True
            result["total_times"] = int(m.group(i_total))
            result["streak_days"] = int(m.group(i_streak))
            result["reward"] = number_from_string(m.group(i_reward))
            result["message"] = m.group(0)
            return result

    total_patterns = [
        r"这是您的第\s*(\d+)\s*次签到",
        r"這是您的第\s*(\d+)\s*次簽到",
        r"累计签到\s*[:：]?\s*(\d+)\s*(?:次|天)?",
        r"累計簽到\s*[:：]?\s*(\d+)\s*(?:次|天)?",
    ]
    for pattern in total_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            result["total_times"] = int(m.group(1))
            break

    streak_patterns = [
        r"已连续签到\s*(\d+)\s*天",
        r"已連續簽到\s*(\d+)\s*天",
        r"连续签到\s*[:：]?\s*(\d+)\s*天",
        r"連續簽到\s*[:：]?\s*(\d+)\s*天",
    ]
    for pattern in streak_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            result["streak_days"] = int(m.group(1))
            break

    reward_patterns = [
        r"本次签到获得\s*([0-9,.]+)\s*个?(?:憨豆|魔力值)",
        r"本次簽到獲得\s*([0-9,.]+)\s*個?(?:憨豆|魔力值)",
        r"签到获得\s*([0-9,.]+)\s*个?憨豆",
        r"簽到獲得\s*([0-9,.]+)\s*個?憨豆",
        r"签到已得\s*([0-9,.]+)",
        r"簽到已得\s*([0-9,.]+)",
        r"Attend got\s*[:：]?\s*([0-9,.]+)",
        r"憨豆\s*[+＋]\s*([0-9,.]+)",
    ]
    for pattern in reward_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            result["reward"] = number_from_string(m.group(1))
            break

    already_patterns = [
        r"您今天已经签到过了[,，]?\s*请勿重复刷新",
        r"您今天已經簽到過了[,，]?\s*請勿重複刷新",
        r"今天已经签到",
        r"今天已經簽到",
        r"今日已经签到",
        r"今日已經簽到",
        r"今日已签到",
        r"今日已簽到",
        r"已经签到过",
        r"已經簽到過",
        r"already\s+(?:signed|attended|showed)",
    ]
    for pattern in already_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            result["success"] = True
            result["already"] = True
            result["message"] = m.group(0)
            return result

    success_patterns = [
        r"本次签到获得\s*[0-9,.]+\s*个?(?:憨豆|魔力值)",
        r"本次簽到獲得\s*[0-9,.]+\s*個?(?:憨豆|魔力值)",
        r"签到成功",
        r"簽到成功",
        r"签到已得\s*[0-9,.]+",
        r"簽到已得\s*[0-9,.]+",
        r"Attend got\s*[:：]?\s*[0-9,.]+",
    ]
    for pattern in success_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            result["success"] = True
            result["message"] = m.group(0)
            return result

    return result


def main() -> int:
    print("========== HHanClub 憨憨 ==========\n")

    if not COOKIE:
        print("❌ 未配置环境变量 HHANCLUB_COOKIE")
        return 1

    session = make_session()

    try:
        home_resp = get(session, "/")
        home_resp.raise_for_status()
        home_html = home_resp.text
    except Exception as e:
        print(f"❌ 无法访问 HHanClub 首页：{e}")
        return 1

    home_text = clean_text(home_html)

    verification = detect_verification(home_text, home_resp.url)
    if verification:
        print(f"❌ 检测到{verification}")
        print("   脚本不会尝试绕过，请先在浏览器中人工处理。")
        return 1

    if not login_is_valid(home_html, home_resp.url):
        print("❌ Cookie 登录失效，请重新获取 HHANCLUB_COOKIE")
        return 1

    username = parse_username(home_html) or "未获取"
    before_bean = parse_hanbean(home_html)
    home_signed = homepage_already_signed(home_html)

    print("✅ Cookie 登录有效")
    print(f"👤 用户：{username}")
    if before_bean is not None:
        print(f"🫘 当前憨豆：{fmt_number(before_bean)}")

    if home_signed:
        print("📅 今日状态：已签到")
    else:
        print("📅 今日状态：未签到或首页未明确显示")

    if not home_signed:
        print("🎯 开始签到...")

    # HHanClub 仍使用 NexusPHP 的 attendance.php 签到入口。
    # 即使首页已经显示已签到，也访问一次 attendance.php 获取权威状态；
    # 已签到时通常只会返回“今天已经签到”的提示，不会重复发放奖励。
    try:
        att_resp = get(session, "/attendance.php", referer=BASE_URL + "/")
        att_html = att_resp.text or ""
    except Exception as e:
        print(f"❌ 签到请求失败：{e}")
        return 1

    att_text = clean_text(att_html)

    verification = detect_verification(att_text, att_resp.url)
    if verification:
        print(f"❌ 签到页面触发{verification}")
        print("   脚本不会尝试绕过，请人工处理。")
        return 1

    if (
        "login.php" in (att_resp.url or "").lower()
        or re.search(
            r"该页面必须在登录后才能访问|該頁面必須在登錄後才能訪問|"
            r"请先登录|請先登錄|登录后才能访问|登錄後才能訪問|"
            r"you must be logged in|please log in",
            att_text,
            flags=re.I,
        )
    ):
        print("❌ 签到页面提示登录失效，请重新获取 HHANCLUB_COOKIE")
        return 1

    if att_resp.status_code != 200:
        print(f"❌ 签到页面 HTTP {att_resp.status_code}")
        print(f"   返回内容：{att_text[:300] or '<空>'}")
        return 1

    parsed = parse_attendance(att_html)

    if not parsed["success"]:
        print("❌ 未能确认签到成功")
        print(f"   页面返回：{att_text[:500] or '<空>'}")
        return 1

    if parsed["already"] or home_signed:
        print("⚠️ 今日已经签到，无需重复执行")
    else:
        print("✅ 签到成功")

    total_times = parsed["total_times"]
    streak_days = parsed["streak_days"]
    reward = parsed["reward"]

    if total_times is not None:
        print(f"📆 累计签到：{total_times} 次")
    else:
        print("📆 累计签到：未获取")

    if streak_days is not None:
        print(f"🔥 连续签到：{streak_days} 天")
    else:
        print("🔥 连续签到：未获取")

    if reward is not None and not (parsed["already"] or home_signed):
        print(f"🎁 本次奖励：{fmt_number(reward)} 憨豆")
    elif not (parsed["already"] or home_signed):
        print("🎁 本次奖励：未获取")

    if not (parsed["already"] or home_signed):
        time.sleep(1.0)

    try:
        after_resp = get(session, "/")
        after_html = after_resp.text
        after_bean = parse_hanbean(after_html)
    except Exception:
        after_bean = before_bean

    # 若 attendance.php 没明确给奖励，则用签到前后憨豆差值兜底。
    if (
        reward is None
        and not (parsed["already"] or home_signed)
        and before_bean is not None
        and after_bean is not None
    ):
        delta = after_bean - before_bean
        if 0 < delta < 100000000:
            reward = delta
            print(f"🎁 憨豆变化：+{fmt_number(delta)}")

    if after_bean is not None:
        print(f"📊 当前憨豆：{fmt_number(after_bean)}")
    elif before_bean is not None:
        print(f"📊 当前憨豆：{fmt_number(before_bean)}")
    else:
        print("📊 当前憨豆：未获取")

    print("\n执行完成 ✅")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n任务已中止")
        raise SystemExit(130)
    except Exception as e:
        print(f"\n❌ 脚本异常：{type(e).__name__}: {e}")
        raise SystemExit(1)
