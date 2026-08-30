#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# cron: 19 9 * * *
# new Env("星陨阁签到")

"""
星陨阁 / XingYunGePT 青龙独立签到脚本

环境变量：
  XINGYUNGE_COOKIE    必填，星陨阁完整 Cookie
  XINGYUNGE_BASE_URL  可选，默认 https://pt.xingyungept.org

依赖：
  curl_cffi

功能：
  - 使用 curl_cffi Chrome 浏览器指纹访问站点
  - 检查 Cookie 登录状态
  - 获取用户名与 UID
  - 通过 mybonus.php 精确读取当前“星焱”
  - 尝试读取上传量 / 下载量 / 分享率
  - 检查 attendance.php 签到状态
  - 未签到时自动执行签到
  - 尝试解析签到奖励
  - 签到后重新读取星焱
  - 遇到 2FA、验证码、人机验证或风控时停止，不尝试绕过
"""

import os
import re
from html import unescape
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse

from curl_cffi import requests


COOKIE = os.getenv("XINGYUNGE_COOKIE", "").strip()
BASE_URL = os.getenv(
    "XINGYUNGE_BASE_URL",
    "https://pt.xingyungept.org"
).strip().rstrip("/")

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


def allowed_host(hostname: str) -> bool:
    host = (hostname or "").lower().strip(".")
    base_host = (urlparse(BASE_URL).hostname or "").lower().strip(".")
    return bool(base_host) and (host == base_host or host.endswith("." + base_host))


def make_session() -> requests.Session:
    """
    使用 curl_cffi 模拟真实 Chrome TLS / HTTP 指纹。
    Cookie 仍只绑定到星陨阁当前主域。
    """
    session = requests.Session(impersonate="chrome")
    session.headers.update({
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })

    host = urlparse(BASE_URL).hostname or ""
    for key, value in cookie_dict(COOKIE).items():
        session.cookies.set(key, value, domain=host, path="/")

    return session


def safe_get(
    session: requests.Session,
    path: str,
    referer: Optional[str] = None,
) -> requests.Response:
    url = urljoin(BASE_URL + "/", path.lstrip("/"))

    resp = session.get(
        url,
        headers={"Referer": referer or (BASE_URL + "/")},
        timeout=TIMEOUT,
        allow_redirects=False,
    )

    redirects = 0
    while resp.status_code in (301, 302, 303, 307, 308):
        location = resp.headers.get("Location")
        if not location:
            break

        next_url = urljoin(resp.url, location)
        next_host = urlparse(next_url).hostname or ""

        if not allowed_host(next_host):
            raise RuntimeError(f"检测到外域跳转，已停止：{next_url}")

        redirects += 1
        if redirects > 5:
            raise RuntimeError("站内重定向次数过多")

        resp = session.get(
            next_url,
            headers={"Referer": resp.url},
            timeout=TIMEOUT,
            allow_redirects=False,
        )

    return resp


def detect_verification(text: str, final_url: str = "") -> Optional[str]:
    source = f"{final_url}\n{text or ''}"

    if re.search(r"take2fa\.php", final_url or "", flags=re.I):
        return "两步验证 / 2FA"

    if re.search(
        r"验证码|驗證碼|人机验证|人機驗證|机器人验证|機器人驗證|"
        r"captcha|geetest|turnstile|cloudflare challenge|cf-chl-|"
        r"just a moment|checking your browser|滑块验证|滑塊驗證",
        source,
        flags=re.I,
    ):
        return "验证码 / 人机验证 / 风控"

    return None


def page_is_login_page(html: str, final_url: str) -> bool:
    raw = html or ""
    text = clean_text(raw)

    if "login.php" in (final_url or "").lower():
        return True

    if re.search(
        r"请先登录|請先登錄|登录后才能访问|登錄後才能訪問|"
        r"you must be logged in|please log in",
        text,
        flags=re.I,
    ):
        return True

    if re.search(r"takelogin\.php", raw, flags=re.I):
        return True

    has_user = bool(re.search(
        r'<input[^>]+name=["\']username["\']',
        raw,
        flags=re.I,
    ))
    has_pass = bool(re.search(
        r'<input[^>]+(?:name=["\']password["\']|type=["\']password["\'])',
        raw,
        flags=re.I,
    ))
    return has_user and has_pass


def login_is_valid(html: str, final_url: str) -> bool:
    if page_is_login_page(html, final_url):
        return False

    return bool(re.search(
        r"logout\.php|usercp\.php|userdetails\.php\?id=\d+|"
        r"mybonus\.php|attendance\.php|控制面板|收藏",
        html or "",
        flags=re.I,
    ))


def parse_username(html: str) -> Optional[str]:
    text = clean_text(html)

    for pattern in [
        r"欢迎回来[,，]?\s*([^\s\[\]，,]+)",
        r"歡迎回來[,，]?\s*([^\s\[\]，,]+)",
        r"([^\s\[\]，,]+)\s*\[退出\]",
    ]:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return m.group(1).strip()

    m = re.search(
        r'<a[^>]+href=["\'][^"\']*userdetails\.php\?id=\d+[^"\']*["\'][^>]*>'
        r'([\s\S]*?)</a>',
        html or "",
        flags=re.I,
    )
    return clean_text(m.group(1)) if m else None


def parse_user_id(html: str) -> Optional[int]:
    m = re.search(
        r'href=["\'][^"\']*userdetails\.php\?id=(\d+)[^"\']*["\']',
        html or "",
        flags=re.I,
    )
    return int(m.group(1)) if m else None


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


def parse_starflame(html: str) -> Optional[float]:
    """
    用户已确认首页结构中：
      <a href="mybonus.php">使用</a>
      ...
      921,120.4

    以 mybonus.php 作为强锚点，读取其后的第一个数字。
    """
    raw = html or ""

    patterns = [
        r'<a[^>]+href=["\'][^"\']*mybonus\.php[^"\']*["\'][^>]*>'
        r'[\s\S]*?</a>'
        r'[\s\]\)】）:：&nbsp;]{0,160}'
        r'([0-9][0-9,.]*)',

        r'<a[^>]+href=["\'][^"\']*mybonus\.php[^"\']*["\'][^>]*>'
        r'[\s\S]*?</a>'
        r'([\s\S]{0,220}?)'
        r'([0-9][0-9,.]*)',
    ]

    for idx, pattern in enumerate(patterns):
        m = re.search(pattern, raw, flags=re.I)
        if not m:
            continue

        raw_num = m.group(1) if idx == 0 else m.group(2)
        value = number_from_string(raw_num)
        if value is not None:
            return value

    return None


def parse_labeled_size(html: str, labels) -> Optional[str]:
    raw = html or ""
    text = clean_text(raw)
    label_alt = "|".join(re.escape(x) for x in labels)

    for source in [raw, text]:
        m = re.search(
            rf"(?:{label_alt})\s*[:：]?\s*"
            rf"([0-9][0-9,.]*\s*[KMGTPE]?i?B)",
            source,
            flags=re.I,
        )
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()

    return None



def parse_labeled_number(html: str, labels) -> Optional[float]:
    text = clean_text(html or "")
    label_alt = "|".join(re.escape(x) for x in labels)

    m = re.search(
        rf"(?:{label_alt})\s*[:：]?\s*([0-9][0-9,.]*)",
        text,
        flags=re.I,
    )
    return number_from_string(m.group(1)) if m else None


def parse_home_attendance(html: str) -> Dict[str, object]:
    """
    用户已确认未签到时首页存在：
      <a href="attendance.php" class="faqlink">[签到得星焱]</a>
    """
    result: Dict[str, object] = {
        "found": False,
        "already": False,
        "reward": None,
        "text": "",
    }

    m = re.search(
        r'<a[^>]+href=["\'][^"\']*attendance\.php[^"\']*["\'][^>]*>'
        r'([\s\S]*?)</a>',
        html or "",
        flags=re.I,
    )

    if not m:
        return result

    text = clean_text(m.group(1))
    result["found"] = True
    result["text"] = text

    # “[签到得星焱]”表示入口仍可签到，不视为已签到
    if re.search(r"签到得星焱|簽到得星焱", text, flags=re.I):
        result["already"] = False
        return result

    if re.search(
        r"签到已得|簽到已得|今日已签到|今日已簽到|"
        r"已签到|已簽到|已经签到|已經簽到",
        text,
        flags=re.I,
    ):
        result["already"] = True

    reward_patterns = [
        r"签到已得\s*([0-9][0-9,.]*)",
        r"簽到已得\s*([0-9][0-9,.]*)",
        r"已得\s*([0-9][0-9,.]*)",
    ]
    for pattern in reward_patterns:
        rm = re.search(pattern, text, flags=re.I)
        if rm:
            result["reward"] = number_from_string(rm.group(1))
            break

    return result


def parse_attendance_page(html: str) -> Dict[str, object]:
    text = clean_text(html)

    result: Dict[str, object] = {
        "success": False,
        "already": False,
        "reward": None,
        "message": "",
    }

    if re.search(
        r"签到成功|簽到成功|签到已得\s*[0-9,.]+|簽到已得\s*[0-9,.]+",
        text,
        flags=re.I,
    ):
        result["success"] = True

    if re.search(
        r"今天已经签到|今天已經簽到|今日已签到|今日已簽到|"
        r"已经签到过|已經簽到過|请勿重复签到|請勿重複簽到",
        text,
        flags=re.I,
    ):
        result["success"] = True
        result["already"] = True

    reward_patterns = [
        r"签到已得\s*([0-9][0-9,.]*)",
        r"簽到已得\s*([0-9][0-9,.]*)",
        r"本次签到(?:获得|得到)?\s*([0-9][0-9,.]*)\s*(?:星焱)?",
        r"本次簽到(?:獲得|得到)?\s*([0-9][0-9,.]*)\s*(?:星焱)?",
        r"奖励\s*[:：]?\s*([0-9][0-9,.]*)\s*(?:星焱)?",
    ]

    for pattern in reward_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            result["reward"] = number_from_string(m.group(1))
            result["success"] = True
            break

    result["message"] = text[:300] if text else ""
    return result


def main() -> int:
    print("========== 星陨阁 ==========\n")

    if not COOKIE:
        print("❌ 未配置环境变量 XINGYUNGE_COOKIE")
        return 1

    session = make_session()

    try:
        print("🌐 网络模式：curl_cffi Chrome 指纹")
        home_resp = safe_get(session, "/")
        home_html = home_resp.text or ""
    except Exception as e:
        print(f"❌ 无法访问星陨阁首页：{e}")
        return 1

    if home_resp.status_code != 200:
        page_text = clean_text(home_html)
        print(f"❌ 星陨阁首页 HTTP {home_resp.status_code}")
        if page_text:
            print(f"   页面返回：{page_text[:300]}")
        print("   当前已使用 Chrome 指纹；若仍为 500，需要根据返回页面继续定位。")
        return 1

    verification = detect_verification(clean_text(home_html), home_resp.url)
    if verification:
        print(f"❌ 检测到{verification}")
        print("   脚本不会尝试绕过，请先人工处理。")
        return 1

    if not login_is_valid(home_html, home_resp.url):
        print("❌ 未能确认 Cookie 登录状态")
        print(f"   当前地址：{home_resp.url}")
        return 1

    username = parse_username(home_html) or "未获取"
    uid = parse_user_id(home_html)
    starflame = parse_starflame(home_html)
    uploaded = parse_labeled_size(home_html, ["上传量", "上傳量", "Uploaded"])
    downloaded = parse_labeled_size(home_html, ["下载量", "下載量", "Downloaded"])
    ratio = parse_labeled_number(home_html, ["分享率", "Ratio"])
    att = parse_home_attendance(home_html)

    print("✅ Cookie 登录有效")
    print(f"👤 用户：{username}")
    if uid is not None:
        print(f"🆔 UID：{uid}")

    print(f"🌟 当前星焱：{fmt_number(starflame)}")
    print(f"⬆️ 上传量：{uploaded or '未获取'}")
    print(f"⬇️ 下载量：{downloaded or '未获取'}")
    if ratio is not None:
        print(f"📈 分享率：{fmt_number(ratio)}")

    if att["found"] and att["already"]:
        print("📅 今日状态：已签到")
        print("⚠️ 今日已经签到，无需重复执行")
        if att["reward"] is not None:
            print(f"🎁 今日签到：{fmt_number(att['reward'])} 星焱")
        print("\n执行完成 ✅")
        return 0

    if att["found"]:
        print("📅 今日状态：未签到")
    else:
        print("📅 今日状态：未签到或首页未明确显示")

    print("🎯 开始签到...")

    try:
        att_resp = safe_get(
            session,
            "/attendance.php",
            referer=BASE_URL + "/",
        )
        att_resp.raise_for_status()
        att_html = att_resp.text or ""
    except Exception as e:
        print(f"❌ 签到请求失败：{e}")
        return 1

    verification = detect_verification(clean_text(att_html), att_resp.url)
    if verification:
        print(f"❌ 签到页面触发{verification}")
        return 1

    if page_is_login_page(att_html, att_resp.url):
        print("❌ 签到页面提示登录失效")
        return 1

    parsed = parse_attendance_page(att_html)

    # 页面可能回到首页，补做一次首页签到状态识别
    if not parsed["success"]:
        returned = parse_home_attendance(att_html)
        if returned["found"] and returned["already"]:
            parsed["success"] = True
            parsed["already"] = True
            parsed["reward"] = returned["reward"]

    if not parsed["success"]:
        print("❌ 未能确认签到成功")
        if parsed["message"]:
            print(f"   页面返回：{parsed['message']}")
        return 1

    print("⚠️ 今日已经签到，无需重复执行" if parsed["already"] else "✅ 签到成功")

    if parsed["reward"] is not None:
        print(f"🎁 今日签到：{fmt_number(parsed['reward'])} 星焱")
    else:
        print("🎁 今日签到：未获取")

    # 签到后重新读取星焱
    try:
        after_resp = safe_get(session, "/")
        after_html = after_resp.text or ""
        after_starflame = parse_starflame(after_html)

        if after_starflame is not None:
            print(f"📊 当前星焱：{fmt_number(after_starflame)}")
            if starflame is not None and after_starflame != starflame:
                delta = after_starflame - starflame
                sign = "+" if delta > 0 else ""
                print(f"🎁 星焱变化：{sign}{fmt_number(delta)}")
    except Exception:
        pass

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
