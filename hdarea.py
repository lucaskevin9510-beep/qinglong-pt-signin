#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# cron: 43 8 * * *
# new Env("HDArea 签到")

"""
HDArea 青龙独立签到脚本

环境变量：
  HDAREA_COOKIE    必填，HDArea 完整 Cookie
  HDAREA_BASE_URL  可选，默认 https://hdarea.club

依赖：
  requests

功能：
  - 检查 Cookie 登录状态
  - 获取用户名
  - 获取当前魔力值（页面可解析时）
  - 检查首页签到状态
  - 使用 /sign_in.php 执行或确认每日签到
  - 优先 POST action=sign_in，必要时兼容 GET ?action=sign_in
  - 尝试解析签到奖励与站点返回信息
  - 签到后重新读取魔力值
  - 遇到验证码、人机验证或风控时停止，不尝试绕过

说明：
  站点无法确认的数据会显示“未获取”，不会自行猜测。
"""

import os
import re
import time
from html import unescape
from typing import Dict, Optional, Tuple
from urllib.parse import urljoin

import requests


COOKIE = os.getenv("HDAREA_COOKIE", "").strip()
BASE_URL = os.getenv("HDAREA_BASE_URL", "https://hdarea.club").strip().rstrip("/")

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


def post_sign(session: requests.Session) -> requests.Response:
    return session.post(
        urljoin(BASE_URL + "/", "sign_in.php"),
        data={"action": "sign_in"},
        headers={
            "Referer": BASE_URL + "/",
            "Origin": BASE_URL,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "*/*",
        },
        timeout=TIMEOUT,
        allow_redirects=True,
    )


def get_sign(session: requests.Session) -> requests.Response:
    return session.get(
        urljoin(BASE_URL + "/", "sign_in.php?action=sign_in"),
        headers={
            "Referer": BASE_URL + "/",
            "Accept": "*/*",
        },
        timeout=TIMEOUT,
        allow_redirects=True,
    )


def detect_verification(text: str, final_url: str = "") -> Optional[str]:
    source = f"{final_url}\n{text or ''}"

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
        r"Welcome back\s*[,，]?\s*([^\s\[，,]+)",
        r"嗨[,，]\s*([^\s🎈\[]+)",
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
        r"该页面必须在登录后才能访问|該頁面必須在登錄後才能訪問|"
        r"请先登录|請先登錄|登录后才能访问|登錄後才能訪問|"
        r"you must be logged in|please log in",
        text,
        flags=re.I,
    ):
        return False

    if re.search(
        r"userdetails\.php\?id=\d+|logout\.php|欢迎回来|歡迎回來|"
        r"控制面板|用户中心|用戶中心|usercp\.php|id=[\"']?sign_in",
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


def fmt_number(value: Optional[float]) -> str:
    if value is None:
        return "未获取"
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.3f}".rstrip("0").rstrip(".")


def parse_magic(html: str) -> Optional[float]:
    text = clean_text(html)

    patterns = [
        r"魔力值\s*(?:\([^)]*\)\s*)?(?:\[[^\]]*\]\s*)?[:：]?\s*([0-9][0-9,.]*)",
        r"\[魔力值\s*[:：]\s*([0-9][0-9,.]*)",
        r"魔力\s*[:：]?\s*([0-9][0-9,.]*)",
        r"Bonus\s*[:：]?\s*([0-9][0-9,.]*)",
        r"Karma\s*[:：]?\s*([0-9][0-9,.]*)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            value = number_from_string(m.group(1))
            if value is not None:
                return value

    return None


def homepage_already_signed(html: str) -> bool:
    if re.search(r'id=["\']sign_in_done["\']', html or "", flags=re.I):
        done_match = re.search(
            r'<[^>]+id=["\']sign_in_done["\'][^>]*>([\s\S]{0,500}?)</[^>]+>',
            html or "",
            flags=re.I,
        )
        if done_match:
            text = clean_text(done_match.group(1))
            if text and not re.search(r"display\s*:\s*none", done_match.group(0), flags=re.I):
                return True

    text = clean_text(html)
    return bool(re.search(
        r"今日已签到|今日已簽到|今天已经签到|今天已經簽到|"
        r"已经签到|已經簽到|签到完成|簽到完成|"
        r"signed\s*in|already\s*signed|sign[-\s]?in\s*done",
        text,
        flags=re.I,
    ))


def response_is_login_expired(text: str, final_url: str) -> bool:
    return bool(
        "login.php" in (final_url or "").lower()
        or re.search(
            r"该页面必须在登录后才能访问|該頁面必須在登錄後才能訪問|"
            r"请先登录|請先登錄|登录后才能访问|登錄後才能訪問|"
            r"you must be logged in|please log in",
            text or "",
            flags=re.I,
        )
    )


def parse_sign_response(raw: str) -> Dict[str, object]:
    text = clean_text(raw)

    result: Dict[str, object] = {
        "success": False,
        "already": False,
        "reward": None,
        "message": text[:500],
    }

    already_patterns = [
        r"重复签到",
        r"重複簽到",
        r"请勿重复",
        r"請勿重複",
        r"已经签到",
        r"已經簽到",
        r"今日已签到",
        r"今日已簽到",
        r"already\s+signed",
        r"repeat",
    ]
    for pattern in already_patterns:
        if re.search(pattern, text, flags=re.I):
            result["success"] = True
            result["already"] = True
            break

    reward_patterns = [
        r"(?:获得|獲得|得到|奖励|獎勵)\s*([0-9][0-9,.]*)\s*(?:魔力值?|积分|積分|bonus)?",
        r"(?:魔力值?|积分|積分|bonus)\s*[+＋:：]?\s*([0-9][0-9,.]*)",
        r"([0-9][0-9,.]*)\s*(?:魔力值?|积分|積分|bonus)",
    ]
    for pattern in reward_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            result["reward"] = number_from_string(m.group(1))
            break

    success_patterns = [
        r"签到成功",
        r"簽到成功",
        r"签到完成",
        r"簽到完成",
        r"签到.*(?:获得|獲得|奖励|獎勵)",
        r"sign[-\s]?in\s+success",
        r"success",
    ]
    if any(re.search(p, text, flags=re.I) for p in success_patterns):
        result["success"] = True

    fatal_patterns = [
        r"error",
        r"失败",
        r"失敗",
        r"forbidden",
        r"denied",
        r"非法",
        r"invalid",
    ]
    if text and not any(re.search(p, text, flags=re.I) for p in fatal_patterns):
        result["success"] = True

    return result


def request_sign(session: requests.Session) -> Tuple[requests.Response, str]:
    resp = post_sign(session)
    text = clean_text(resp.text or "")

    if resp.status_code in (404, 405, 501) or re.search(
        r"method\s+not\s+allowed|请求方式错误|请求方法错误",
        text,
        flags=re.I,
    ):
        resp = get_sign(session)
        return resp, "GET"

    return resp, "POST"


def main() -> int:
    print("========== HDArea 好大 ==========\n")

    if not COOKIE:
        print("❌ 未配置环境变量 HDAREA_COOKIE")
        return 1

    session = make_session()

    try:
        home_resp = get(session, "/")
        home_resp.raise_for_status()
        home_html = home_resp.text or ""
    except Exception as e:
        print(f"❌ 无法访问 HDArea 首页：{e}")
        return 1

    home_text = clean_text(home_html)

    verification = detect_verification(home_text, home_resp.url)
    if verification:
        print(f"❌ 检测到{verification}")
        print("   脚本不会尝试绕过，请先在浏览器中人工处理。")
        return 1

    if not login_is_valid(home_html, home_resp.url):
        print("❌ Cookie 登录失效，请重新获取 HDAREA_COOKIE")
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
        sign_resp, method = request_sign(session)
        sign_raw = sign_resp.text or ""
        sign_text = clean_text(sign_raw)
    except Exception as e:
        print(f"❌ 签到请求失败：{e}")
        return 1

    verification = detect_verification(sign_text, sign_resp.url)
    if verification:
        print(f"❌ 签到页面触发{verification}")
        print("   脚本不会尝试绕过，请人工处理。")
        return 1

    if response_is_login_expired(sign_text, sign_resp.url):
        print("❌ 签到接口提示登录失效，请重新获取 HDAREA_COOKIE")
        return 1

    if sign_resp.status_code != 200:
        print(f"❌ 签到接口 HTTP {sign_resp.status_code}")
        print(f"   返回内容：{sign_text[:300] or '<空>'}")
        return 1

    parsed = parse_sign_response(sign_raw)

    if not parsed["success"]:
        print("❌ 未能确认签到成功")
        print(f"   请求方式：{method}")
        print(f"   站点返回：{sign_text[:500] or '<空>'}")
        return 1

    if parsed["already"] or home_signed:
        print("⚠️ 今日已经签到，无需重复执行")
    else:
        print("✅ 签到成功")

    reward = parsed["reward"]
    if reward is not None and not parsed["already"]:
        print(f"🎁 本次奖励：{fmt_number(reward)} 魔力")

    message = str(parsed["message"] or "").strip()
    if message:
        print(f"💬 站点返回：{message[:300]}")

    if not (parsed["already"] or home_signed):
        time.sleep(1.0)

    try:
        after_resp = get(session, "/")
        after_magic = parse_magic(after_resp.text or "")
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
