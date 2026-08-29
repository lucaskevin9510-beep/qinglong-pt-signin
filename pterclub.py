#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# cron: 17 8 * * *
# new Env("PterClub 猫站签到")

"""
PterClub（猫站）青龙独立签到脚本

环境变量：
  PTERCLUB_COOKIE   必填，猫站完整 Cookie
  PTERCLUB_BASE_URL 可选，默认 https://pterclub.net

依赖：
  requests

说明：
  - 当前默认使用猫站新域名 https://pterclub.net

功能：
  - 检查 Cookie 登录状态
  - 获取用户名
  - 获取当前猫粮（如果页面可解析）
  - 检查今日是否已经签到
  - 未签到时调用 attendance-ajax.php
  - 解析本次签到奖励
  - 签到后再次读取猫粮，必要时用前后差值计算奖励
  - 尝试解析连续签到天数
  - 不绕过验证码、人机验证或风控

说明：
  站点页面/接口随时可能调整。脚本对响应采用较宽松的解析方式，
  如果某个字段站点没有返回，会显示“未获取”，不会自行猜测。
"""

import json
import os
import re
import time
from html import unescape
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urljoin

import requests

COOKIE = os.getenv("PTERCLUB_COOKIE", "").strip()
BASE_URL = os.getenv("PTERCLUB_BASE_URL", "https://pterclub.net").strip().rstrip("/")
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
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        "Connection": "keep-alive",
    })
    requests.utils.add_dict_to_cookiejar(session.cookies, cookie_dict(COOKIE))
    return session


def request_get(session: requests.Session, path: str, *, ajax: bool = False) -> requests.Response:
    headers = {}
    if ajax:
        headers.update({
            "Accept": "application/json,text/javascript,*/*;q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": BASE_URL + "/",
        })
    return session.get(
        urljoin(BASE_URL + "/", path.lstrip("/")),
        headers=headers,
        timeout=TIMEOUT,
        allow_redirects=True,
    )


def detect_verification(text: str) -> bool:
    return bool(re.search(
        r"验证码|人机验证|机器人|captcha|geetest|turnstile|cloudflare|滑块|安全校验",
        text or "",
        flags=re.I,
    ))


def parse_username(html: str) -> Optional[str]:
    text = clean_text(html)
    patterns = [
        r"欢迎回来\s*[,，]\s*([^\s\[，,]+)",
        r"([^\s,，]+)\s*[,，]\s*欢迎回来",
        r"嗨[,，]\s*([^\s🎈\[]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return m.group(1).strip()
    m = re.search(
        r'<a[^>]+href=["\'][^"\']*userdetails\.php\?id=\d+[^"\']*["\'][^>]*>([^<]+)</a>',
        html or "",
        flags=re.I,
    )
    if m:
        name = clean_text(m.group(1))
        if name and len(name) < 80:
            return name
    return None


def parse_catfood(html: str) -> Optional[float]:
    text = clean_text(html)
    for pattern in [
        r"猫粮\s*(?:\[[^\]]*\])?\s*[:：]?\s*([0-9][0-9,.]*)",
        r"猫粮\s*([0-9][0-9,.]*)",
    ]:
        m = re.search(pattern, text, flags=re.I)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                pass
    return None


def fmt_number(value: Optional[float]) -> str:
    if value is None:
        return "未获取"
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.3f}".rstrip("0").rstrip(".")


def already_signed_from_html(html: str) -> bool:
    return bool(re.search(
        r"今日已签到|已经签到|已签到|签到已得|本次签到获得",
        clean_text(html), flags=re.I,
    ))


def has_sign_entry(html: str) -> bool:
    return bool(
        re.search(r'id=["\']showup["\']', html or "", flags=re.I)
        or re.search(r'>\s*签到\s*<', html or "", flags=re.I)
    )


def recursive_items(obj: Any):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield str(key), value
            yield from recursive_items(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from recursive_items(value)


def find_continuous_days(obj: Any, fallback_text: str = "") -> Optional[int]:
    likely_keys = {
        "continuousdays", "continuous_days", "consecutivedays", "consecutive_days",
        "streak", "streakdays", "streak_days", "serialdays", "serial_days",
        "continuous", "consecutive",
    }
    for key, value in recursive_items(obj):
        normalized = re.sub(r"[^a-z0-9_]", "", key.lower())
        if normalized in likely_keys:
            try:
                n = int(str(value).strip())
                if 0 <= n < 100000:
                    return n
            except (TypeError, ValueError):
                pass
    try:
        blob = json.dumps(obj, ensure_ascii=False)
    except Exception:
        blob = str(obj)
    blob += " " + (fallback_text or "")
    for pattern in [
        r"连续(?:签|簽)到\s*[:：]?\s*(\d+)\s*天",
        r"连续\s*(\d+)\s*天",
        r"已连续(?:签|簽)到\s*(\d+)\s*天",
        r"连续(?:签到|簽到)天数\s*[:：]?\s*(\d+)",
    ]:
        m = re.search(pattern, blob, flags=re.I)
        if m:
            return int(m.group(1))
    return None


def find_reward(obj: Any, fallback_text: str = "") -> Optional[float]:
    likely_keys = {
        "bonus", "bonusgain", "bonus_gain", "reward", "rewardvalue", "reward_value",
        "integral", "points", "point", "catfood", "cat_food", "gain", "amount",
    }
    for key, value in recursive_items(obj):
        normalized = re.sub(r"[^a-z0-9_]", "", key.lower())
        if normalized in likely_keys:
            if isinstance(value, (int, float)) and 0 <= float(value) < 100000000:
                return float(value)
            if isinstance(value, str):
                m = re.search(r"([0-9]+(?:\.[0-9]+)?)", value.replace(",", ""))
                if m:
                    try:
                        return float(m.group(1))
                    except ValueError:
                        pass
    try:
        blob = json.dumps(obj, ensure_ascii=False)
    except Exception:
        blob = str(obj)
    blob += " " + (fallback_text or "")
    for pattern in [
        r"(?:本次)?签到(?:获得|已得)\s*([0-9,.]+)\s*(?:克)?(?:猫粮|魔力值)?",
        r"获得\s*([0-9,.]+)\s*(?:克)?猫粮",
        r"猫粮\s*[+＋]\s*([0-9,.]+)",
    ]:
        m = re.search(pattern, blob, flags=re.I)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                pass
    return None


def response_message(obj: Any) -> str:
    if isinstance(obj, dict):
        for key in ("message", "msg", "data", "text", "info"):
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                return clean_text(value)
    return clean_text(str(obj))


def is_ajax_success(obj: Any) -> Tuple[bool, bool]:
    message = response_message(obj)
    if re.search(r"今日已签到|已经签到|已签到|请勿重复", message):
        return True, True
    if isinstance(obj, dict):
        if obj.get("success") is True:
            return True, False
        if str(obj.get("status")) == "1":
            return True, False
        if str(obj.get("state", "")).lower() in {"success", "ok"}:
            return True, False
    if re.search(r"签到成功|本次签到获得|签到已得|获得\s*[0-9,.]+\s*(?:克)?猫粮", message):
        return True, False
    return False, False


def fetch_home(session: requests.Session) -> Tuple[str, requests.Response]:
    r = request_get(session, "/")
    r.raise_for_status()
    return r.text, r


def login_is_valid(html: str, final_url: str) -> bool:
    text = clean_text(html)
    if "login.php" in (final_url or "").lower():
        return False
    if re.search(r"该页面必须在登录后才能访问|请先登录|登录后才能", text):
        return False
    if re.search(r"userdetails\.php\?id=\d+|logout\.php|欢迎回来|欢迎回來", html or "", flags=re.I):
        return True
    return parse_username(html) is not None


def main() -> int:
    print("========== PterClub 猫站 ==========\n")
    if not COOKIE:
        print("❌ 未配置环境变量 PTERCLUB_COOKIE")
        return 1

    session = make_session()
    try:
        before_html, before_resp = fetch_home(session)
    except Exception as e:
        print(f"❌ 无法访问猫站首页：{e}")
        return 1

    before_text = clean_text(before_html)
    if detect_verification(before_text):
        print("❌ 检测到验证码 / 人机验证 / Cloudflare 等验证措施")
        print("   脚本不会尝试绕过，请先在浏览器中人工处理。")
        return 1
    if not login_is_valid(before_html, before_resp.url):
        print("❌ Cookie 登录失效，请重新获取 PTERCLUB_COOKIE")
        return 1

    username = parse_username(before_html) or "未获取"
    before_catfood = parse_catfood(before_html)
    print("✅ Cookie 登录有效")
    print(f"👤 用户：{username}")
    if before_catfood is not None:
        print(f"🐱 当前猫粮：{fmt_number(before_catfood)}")

    was_already = already_signed_from_html(before_html)
    sign_entry = has_sign_entry(before_html)
    if was_already:
        print("📅 今日状态：已签到")
    elif sign_entry:
        print("📅 今日状态：未签到")
    else:
        print("📅 今日状态：页面未明确显示，继续调用签到接口确认")

    ajax_obj: Any = {}
    ajax_text = ""
    success = False
    already = was_already
    reward = None
    continuous_days = None

    if not was_already:
        print("🎯 开始签到...")
        try:
            r = request_get(session, "/attendance-ajax.php", ajax=True)
        except Exception as e:
            print(f"❌ 签到请求失败：{e}")
            return 1
        ajax_text = r.text or ""
        if r.status_code != 200:
            print(f"❌ 签到接口 HTTP {r.status_code}")
            print("   返回内容：", clean_text(ajax_text)[:300] or "<空>")
            return 1
        if re.search(r"该页面必须在登录后才能访问|请先登录|登录后才能", clean_text(ajax_text)):
            print("❌ 签到接口提示登录失效，请重新获取 Cookie")
            return 1
        if detect_verification(clean_text(ajax_text)):
            print("❌ 签到接口触发验证码 / 人机验证")
            print("   脚本不会尝试绕过，请人工处理。")
            return 1
        try:
            ajax_obj = r.json()
        except Exception:
            ajax_obj = {"message": clean_text(ajax_text)}

        success, ajax_already = is_ajax_success(ajax_obj)
        already = already or ajax_already
        reward = find_reward(ajax_obj, ajax_text)
        continuous_days = find_continuous_days(ajax_obj, ajax_text)
        if not success:
            msg = response_message(ajax_obj)
            print("❌ 未能确认签到成功")
            print(f"   接口返回：{msg[:400] or '<空>'}")
            return 1
        if ajax_already:
            print("⚠️ 接口返回：今日已经签到")
        else:
            print("✅ 签到成功")
        time.sleep(1.2)

    try:
        after_html, _ = fetch_home(session)
    except Exception:
        after_html = before_html

    after_catfood = parse_catfood(after_html)
    after_text = clean_text(after_html)
    if continuous_days is None:
        continuous_days = find_continuous_days({}, after_text)
    if reward is None and before_catfood is not None and after_catfood is not None:
        delta = after_catfood - before_catfood
        if 0 < delta < 100000000:
            reward = delta

    final_signed = already or success or already_signed_from_html(after_html) or (not has_sign_entry(after_html) and was_already)

    if was_already:
        print("⚠️ 今日已经签到，无需重复执行")
    if continuous_days is not None:
        print(f"🔥 连续签到：{continuous_days} 天")
    else:
        print("🔥 连续签到：未获取（站点响应未提供可确认的数据）")
    if reward is not None and not was_already:
        print(f"🎁 本次奖励：{fmt_number(reward)} 猫粮")
    elif not was_already:
        print("🎁 本次奖励：未获取")
    if after_catfood is not None:
        print(f"📊 当前猫粮：{fmt_number(after_catfood)}")
    elif before_catfood is not None:
        print(f"📊 当前猫粮：{fmt_number(before_catfood)}")
    else:
        print("📊 当前猫粮：未获取")

    print()
    if final_signed:
        print("执行完成 ✅")
        return 0
    print("执行结束，但未能确认今日签到状态 ❌")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n任务已中止")
        raise SystemExit(130)
    except Exception as e:
        print(f"\n❌ 脚本异常：{type(e).__name__}: {e}")
        raise SystemExit(1)
