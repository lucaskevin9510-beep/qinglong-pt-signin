#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# cron: 37 8 * * *
# new Env("CarPT 签到")

"""
CarPT 青龙独立签到脚本

环境变量：
  CARPT_COOKIE    必填，CarPT 完整 Cookie
  CARPT_BASE_URL  可选，默认 https://carpt.net

依赖：
  requests

功能：
  - 检查 Cookie 登录状态
  - 获取用户名
  - 获取当前魔力值（页面可解析时）
  - 使用 /attendance.php 执行或确认每日签到
  - 解析签到奖励
  - 尝试解析累计签到次数、连续签到天数
  - 签到后重新读取魔力值
  - 遇到 2FA / 验证码 / 人机验证 / 风控时停止，不尝试绕过

说明：
  无法确认的数据会显示“未获取”，不会自行猜测。
"""

import os
import re
import time
from html import unescape
from typing import Dict, Optional
from urllib.parse import urljoin

import requests


COOKIE = os.getenv("CARPT_COOKIE", "").strip()
BASE_URL = os.getenv("CARPT_BASE_URL", "https://carpt.net").strip().rstrip("/")

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

    # 登录页本身会展示 2FA 输入框；只有当前页面实际落在登录/2FA挑战页时才拦截。
    if re.search(r"take2fa\.php", final_url or "", flags=re.I):
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
        r"未登录|未登錄|该页面必须在登录后才能访问|"
        r"該頁面必須在登錄後才能訪問|请先登录|請先登錄|"
        r"you must be logged in|please log in",
        text,
        flags=re.I,
    ):
        return False

    if re.search(
        r"userdetails\.php\?id=\d+|logout\.php|欢迎回来|歡迎回來|"
        r"控制面板|用户中心|用戶中心|usercp\.php",
        html or "",
        flags=re.I,
    ):
        return True

    return parse_username(html) is not None


def number_from_string(value: str) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def parse_magic(html: str) -> Optional[float]:
    text = clean_text(html)

    patterns = [
        r"魔力值\s*(?:\([^)]*\)\s*)?(?:\[[^\]]*\]\s*)?[:：]?\s*([0-9][0-9,.]*)",
        r"\[魔力值\s*[:：]\s*([0-9][0-9,.]*)",
        r"魔力\s*[:：]?\s*([0-9][0-9,.]*)",
        r"Bonus\s*[:：]?\s*([0-9][0-9,.]*)",
    ]
    for pattern in patterns:
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
        r"Attend got\s*[:：]?\s*[0-9,.]+|"
        r"今日已签到|今日已簽到|今天已经签到|今天已經簽到",
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

    # CarPT / NexusPHP 常见返回：签到已得N 或 Attend got: N
    m = re.search(r"签到已得\s*([0-9,.]+)", text, flags=re.I)
    if not m:
        m = re.search(r"簽到已得\s*([0-9,.]+)", text, flags=re.I)
    if not m:
        m = re.search(r"Attend got\s*[:：]?\s*([0-9,.]+)", text, flags=re.I)
    if m:
        result["success"] = True
        result["reward"] = number_from_string(m.group(1))
        result["message"] = m.group(0)

    # 部分 NexusPHP 主题会给更完整的签到文案。
    total_patterns = [
        r"这是您的第\s*(\d+)\s*次签到",
        r"這是您的第\s*(\d+)\s*次簽到",
        r"累计签到\s*[:：]?\s*(\d+)\s*(?:次|天)?",
        r"累計簽到\s*[:：]?\s*(\d+)\s*(?:次|天)?",
    ]
    for pattern in total_patterns:
        m2 = re.search(pattern, text, flags=re.I)
        if m2:
            result["total_times"] = int(m2.group(1))
            result["success"] = True
            break

    streak_patterns = [
        r"已连续签到\s*(\d+)\s*天",
        r"已連續簽到\s*(\d+)\s*天",
        r"连续签到\s*[:：]?\s*(\d+)\s*天",
        r"連續簽到\s*[:：]?\s*(\d+)\s*天",
    ]
    for pattern in streak_patterns:
        m2 = re.search(pattern, text, flags=re.I)
        if m2:
            result["streak_days"] = int(m2.group(1))
            break

    full_reward_patterns = [
        r"本次签到获得\s*([0-9,.]+)\s*个?魔力值",
        r"本次簽到獲得\s*([0-9,.]+)\s*個?魔力值",
        r"签到获得\s*([0-9,.]+)\s*个?魔力值",
    ]
    for pattern in full_reward_patterns:
        m2 = re.search(pattern, text, flags=re.I)
        if m2:
            result["reward"] = number_from_string(m2.group(1))
            result["success"] = True
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
        m2 = re.search(pattern, text, flags=re.I)
        if m2:
            result["success"] = True
            result["already"] = True
            result["message"] = m2.group(0)
            break

    return result


def main() -> int:
    print("========== CarPT ==========\n")

    if not COOKIE:
        print("❌ 未配置环境变量 CARPT_COOKIE")
        return 1

    session = make_session()

    try:
        home_resp = get(session, "/")
        home_resp.raise_for_status()
        home_html = home_resp.text
    except Exception as e:
        print(f"❌ 无法访问 CarPT 首页：{e}")
        return 1

    home_text = clean_text(home_html)

    verification = detect_verification(home_text, home_resp.url)
    if verification:
        print(f"❌ 检测到{verification}")
        print("   脚本不会尝试绕过，请先在浏览器中人工处理。")
        return 1

    if not login_is_valid(home_html, home_resp.url):
        print("❌ Cookie 登录失效，请重新获取 CARPT_COOKIE")
        return 1

    username = parse_username(home_html) or "未获取"
    before_magic = parse_magic(home_html)
    home_signed = homepage_already_signed(home_html)

    print("✅ Cookie 登录有效")
    print(f"👤 用户：{username}")
    if before_magic is not None:
        print(f"💰 当前魔力：{fmt_number(before_magic)}")

    if home_signed:
        print("📅 今日状态：已签到")
    else:
        print("📅 今日状态：未签到或首页未明确显示")
        print("🎯 开始签到...")

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
            r"未登录|未登錄|该页面必须在登录后才能访问|"
            r"該頁面必須在登錄後才能訪問|请先登录|請先登錄|"
            r"you must be logged in|please log in",
            att_text,
            flags=re.I,
        )
    ):
        print("❌ 签到页面提示登录失效，请重新获取 CARPT_COOKIE")
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

    if streak_days is not None:
        print(f"🔥 连续签到：{streak_days} 天")

    if reward is not None and not parsed["already"]:
        print(f"🎁 本次签到：{fmt_number(reward)} 魔力")
    elif not (parsed["already"] or home_signed):
        print("🎁 本次签到：未获取")

    if not (parsed["already"] or home_signed):
        time.sleep(1.0)

    try:
        after_resp = get(session, "/")
        after_magic = parse_magic(after_resp.text)
    except Exception:
        after_magic = before_magic

    if after_magic is not None:
        print(f"📊 当前魔力：{fmt_number(after_magic)}")
    elif before_magic is not None:
        print(f"📊 当前魔力：{fmt_number(before_magic)}")
    else:
        print("📊 当前魔力：未获取")

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
