#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# cron: 55 8 * * *
# new Env("QingWa 青蛙签到")

"""
QingWa / 青蛙 青龙独立签到脚本

环境变量：
  QINGWA_COOKIE    必填，QingWa 完整 Cookie
  QINGWA_BASE_URL  可选，默认 https://www.qingwapt.com

依赖：
  curl_cffi

功能：
  - 检查 Cookie 登录状态
  - 获取用户名与 UID
  - 优先从 userdetails.php 读取当前魔力值
  - 检查今日签到状态
  - 使用 /attendance.php 执行或确认每日签到
  - 解析累计签到次数、连续签到天数、本次签到奖励
  - 签到后重新读取魔力值
  - 每天一次在首页群聊发送“蛙总，求上传”请求额外上传量
  - 顶部读取当前上传量，发送后再次读取并计算实际增加值
  - 按 UID + 日期记录本地状态，避免重复发送
  - 遇到 2FA、验证码、人机验证或 Cloudflare 风控时停止，不尝试绕过

说明：
  无法确认的数据会显示“未获取”，不会自行猜测。
"""

import os
import re
import time
import json
from datetime import datetime
from html import unescape
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse

from curl_cffi import requests


COOKIE = os.getenv("QINGWA_COOKIE", "").strip()
BASE_URL = os.getenv("QINGWA_BASE_URL", "https://www.qingwapt.com").strip().rstrip("/")

TIMEOUT = 20
SHOUT_TEXT = "蛙总，求上传"
STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".qingwa_state")
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


def is_qingwa_host(hostname: str) -> bool:
    """只允许 QingWa 自己的 qingwapt.com 域名族。"""
    host = (hostname or "").lower().strip(".")
    return host == "qingwapt.com" or host.endswith(".qingwapt.com")


def make_session() -> requests.Session:
    session = requests.Session(impersonate="chrome")
    session.headers.update({
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    return session


def qingwa_request(
    session: requests.Session,
    method: str,
    path: str,
    *,
    params=None,
    referer: Optional[str] = None,
    max_redirects: int = 5,
) -> requests.Response:
    """
    Cookie 只对 *.qingwapt.com 发送。
    不自动跟随重定向；仅手动跟随 qingwapt.com 域名族内的跳转。
    """
    url = urljoin(BASE_URL + "/", path.lstrip("/"))
    current_method = method.upper()
    current_params = params

    for _ in range(max_redirects + 1):
        parsed = urlparse(url)
        if not is_qingwa_host(parsed.hostname or ""):
            raise RuntimeError(f"检测到外域地址，已阻止请求：{url}")

        headers = {
            "Cookie": COOKIE,
            "Referer": referer or (BASE_URL + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        resp = session.request(
            current_method,
            url,
            params=current_params,
            headers=headers,
            timeout=TIMEOUT,
            allow_redirects=False,
        )

        if resp.status_code not in (301, 302, 303, 307, 308):
            return resp

        location = resp.headers.get("Location") or resp.headers.get("location")
        if not location:
            return resp

        next_url = urljoin(url, location)
        next_host = urlparse(next_url).hostname or ""

        if not is_qingwa_host(next_host):
            raise RuntimeError(
                "站点返回外域跳转，已阻止继续访问，Cookie 未发送到目标域名："
                + next_url
            )

        if resp.status_code == 303:
            current_method = "GET"
            current_params = None

        url = next_url

    raise RuntimeError("站内重定向次数过多，已停止请求")


def get(
    session: requests.Session,
    path: str,
    referer: Optional[str] = None,
) -> requests.Response:
    return qingwa_request(
        session,
        "GET",
        path,
        referer=referer,
    )


def detect_verification(text: str, final_url: str = "") -> Optional[str]:
    source = f"{final_url}\n{text or ''}"

    if re.search(r"take2fa\.php", final_url or "", flags=re.I):
        return "两步验证 / 2FA"

    if re.search(
        r"验证码|驗證碼|人机验证|人機驗證|机器人验证|機器人驗證|"
        r"captcha|geetest|turnstile|cloudflare challenge|cf-chl-|"
        r"just a moment|checking your browser|"
        r"滑块验证|滑塊驗證|安全校验|安全驗證|请确认您是合法用户",
        source,
        flags=re.I,
    ):
        return "验证码 / 人机验证 / Cloudflare 风控"

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


def parse_user_id(html: str) -> Optional[int]:
    m = re.search(
        r'href=["\'][^"\']*userdetails\.php\?id=(\d+)[^"\']*["\']',
        html or "",
        flags=re.I,
    )
    return int(m.group(1)) if m else None


def page_is_login_page(html: str, final_url: str) -> bool:
    """识别真正的登录页，而不是仅凭缺少某些首页元素判断 Cookie 失效。"""
    text = clean_text(html)

    if "login.php" in (final_url or "").lower():
        return True

    if re.search(
        r"该页面必须在登录后才能访问|該頁面必須在登錄後才能訪問|"
        r"请先登录|請先登錄|登录后才能访问|登錄後才能訪問|"
        r"you must be logged in|please log in",
        text,
        flags=re.I,
    ):
        return True

    raw = html or ""
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
    if has_user and has_pass:
        return True

    return False


def login_is_valid(
    session: requests.Session,
    html: str,
    final_url: str,
) -> bool:
    """
    QingWa 使用自定义首页主题，不能只依赖 logout.php / 欢迎回来等传统
    NexusPHP 标记。

    验证顺序：
      1. 首页明确是登录页 -> 无效
      2. 首页有明确登录态标记 -> 有效
      3. 主动访问 usercp.php（只读）验证
      4. 再访问 shoutbox.php?type=shoutbox；出现 shbox_text 输入框即有效
    """
    if page_is_login_page(html, final_url):
        return False

    if re.search(
        r"userdetails\.php\?id=\d+|logout\.php|欢迎回来|歡迎回來|"
        r"控制面板|用户中心|用戶中心|usercp\.php|attendance\.php",
        html or "",
        flags=re.I,
    ):
        return True

    if parse_username(html) is not None:
        return True

    try:
        probe = get(session, "/usercp.php", referer=BASE_URL + "/")
        probe_html = probe.text or ""
        if probe.status_code == 200 and not page_is_login_page(probe_html, probe.url):
            if re.search(
                r"usercp|用户控制面板|用戶控制面板|个人设置|個人設置|"
                r"tracker|安全设置|安全設置",
                probe_html,
                flags=re.I,
            ):
                return True
    except Exception:
        pass

    try:
        probe = get(
            session,
            "/shoutbox.php?type=shoutbox",
            referer=BASE_URL + "/",
        )
        probe_html = probe.text or ""
        if (
            probe.status_code == 200
            and not page_is_login_page(probe_html, probe.url)
            and re.search(
                r'id=["\']shbox_text["\']|'
                r'name=["\']shbox_text["\']|'
                r'action=["\']shoutbox\.php["\']',
                probe_html,
                flags=re.I,
            )
        ):
            return True
    except Exception:
        pass

    return False


def number_from_string(value: str) -> Optional[float]:
    if value is None:
        return None
    raw = str(value).replace(",", "").strip()
    try:
        return float(raw)
    except ValueError:
        return None


def fmt_number(value: Optional[float]) -> str:
    if value is None:
        return "未获取"
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.3f}".rstrip("0").rstrip(".")


def extract_numbers(value: str):
    result = []
    for raw in re.findall(r"(?<!\d)(\d[\d,.]*)(?!\d)", value or ""):
        num = number_from_string(raw)
        if num is not None:
            result.append(num)
    return result


def parse_bonus_balance(html: str) -> Optional[float]:
    raw = html or ""

    row_re = re.compile(
        r'<td[^>]*class=["\'][^"\']*rowhead[^"\']*["\'][^>]*>\s*'
        r'(?:魔力值|魔力|Bonus|Karma)\s*</td>\s*'
        r'<td[^>]*>([\s\S]*?)</td>',
        flags=re.I,
    )
    for m in row_re.finditer(raw):
        cell = clean_text(m.group(1))
        nums = extract_numbers(cell)
        if nums:
            return max(nums)

    text = clean_text(raw)

    direct_patterns = [
        r"魔力值\s*(?:\([^)]*\))?\s*(?:\[[^\]]*\])?\s*[:：]\s*([0-9][0-9,.]*)",
        r"魔力\s*(?:\([^)]*\))?\s*(?:\[[^\]]*\])?\s*[:：]\s*([0-9][0-9,.]*)",
        r"Bonus\s*(?:\([^)]*\))?\s*(?:\[[^\]]*\])?\s*[:：]\s*([0-9][0-9,.]*)",
        r"Karma\s*(?:\([^)]*\))?\s*(?:\[[^\]]*\])?\s*[:：]\s*([0-9][0-9,.]*)",
    ]
    for pattern in direct_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            value = number_from_string(m.group(1))
            if value is not None:
                return value

    return None


def get_bonus_balance(session: requests.Session, home_html: str) -> Optional[float]:
    uid = parse_user_id(home_html)

    if uid is not None:
        try:
            resp = get(session, f"/userdetails.php?id={uid}", referer=BASE_URL + "/")
            if resp.status_code == 200:
                body = resp.text or ""
                page_text = clean_text(body)
                if (
                    "login.php" not in (resp.url or "").lower()
                    and not detect_verification(page_text, resp.url)
                ):
                    value = parse_bonus_balance(body)
                    if value is not None:
                        return value
        except Exception:
            pass

    return parse_bonus_balance(home_html)


def shout_state_path(uid: Optional[int]) -> str:
    os.makedirs(STATE_DIR, exist_ok=True)
    suffix = str(uid) if uid is not None else "unknown"
    return os.path.join(STATE_DIR, f"shout_{suffix}.json")


def already_shouted_today(uid: Optional[int]) -> bool:
    path = shout_state_path(uid)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("date") == datetime.now().strftime("%Y-%m-%d")
    except Exception:
        return False


def mark_shouted_today(uid: Optional[int]) -> None:
    path = shout_state_path(uid)
    data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "message": SHOUT_TEXT,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def shout_response_ok(resp: requests.Response) -> bool:
    if resp.status_code != 200:
        return False

    body = resp.text or ""
    text = clean_text(body)

    if "login.php" in (resp.url or "").lower():
        return False

    if detect_verification(text, resp.url):
        return False

    fatal_patterns = [
        r"发送失败",
        r"發送失敗",
        r"禁止发言",
        r"禁止發言",
        r"没有权限",
        r"沒有權限",
        r"forbidden",
        r"permission denied",
        r"error",
    ]
    if any(re.search(p, text, flags=re.I) for p in fatal_patterns):
        return False

    return True


def send_upload_request(
    session: requests.Session,
    uid: Optional[int],
) -> str:
    if already_shouted_today(uid):
        print("🐸 今日已经发送过“蛙总，求上传”，跳过重复发送")
        return "skipped"

    params = {
        "shbox_text": SHOUT_TEXT,
        "shout": "我喊",
        "sent": "yes",
        "type": "shoutbox",
    }

    try:
        resp = qingwa_request(
            session,
            "GET",
            "/shoutbox.php",
            params=params,
            referer=BASE_URL + "/",
        )
    except Exception as e:
        print(f"❌ 群聊发送失败：{e}")
        return "failed"

    body_text = clean_text(resp.text or "")
    verification = detect_verification(body_text, resp.url)
    if verification:
        print(f"❌ 群聊页面触发{verification}")
        print("   脚本不会尝试绕过，请人工处理。")
        return "failed"

    if "login.php" in (resp.url or "").lower():
        print("❌ 群聊页面提示登录失效，请重新获取 QINGWA_COOKIE")
        return "failed"

    if not shout_response_ok(resp):
        print("❌ 未能确认群聊消息发送成功")
        if body_text:
            print(f"   站点返回：{body_text[:300]}")
        return "failed"

    mark_shouted_today(uid)
    print(f"💬 发送：{SHOUT_TEXT}")
    print("✅ 群聊消息发送成功")
    return "sent"


def parse_size_bytes(value: str) -> Optional[float]:
    if not value:
        return None

    m = re.search(
        r"([0-9][0-9,.]*)\s*([KMGTPE]?i?B)",
        value,
        flags=re.I,
    )
    if not m:
        return None

    number = number_from_string(m.group(1))
    if number is None:
        return None

    unit = m.group(2).upper()
    units = {
        "B": 1,
        "KB": 1024,
        "MB": 1024 ** 2,
        "GB": 1024 ** 3,
        "TB": 1024 ** 4,
        "PB": 1024 ** 5,
        "EB": 1024 ** 6,
        "KIB": 1024,
        "MIB": 1024 ** 2,
        "GIB": 1024 ** 3,
        "TIB": 1024 ** 4,
        "PIB": 1024 ** 5,
        "EIB": 1024 ** 6,
    }

    multiplier = units.get(unit)
    if multiplier is None:
        return None

    return number * multiplier


def human_size(num_bytes: Optional[float]) -> str:
    if num_bytes is None:
        return "未获取"

    value = float(num_bytes)
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    idx = 0

    while abs(value) >= 1024 and idx < len(units) - 1:
        value /= 1024.0
        idx += 1

    if idx == 0:
        return f"{int(round(value))} {units[idx]}"

    return f"{value:,.2f} {units[idx]}"


def parse_homepage_uploaded(html: str):
    raw = html or ""

    patterns = [
        r'<font[^>]+class=["\'][^"\']*color_uploaded[^"\']*["\'][^>]*>'
        r'[\s\S]*?</font>\s*([0-9][0-9,.]*\s*[KMGTPE]?i?B)',
        r'class=["\'][^"\']*color_uploaded[^"\']*["\'][^>]*>'
        r'[\s\S]*?</[^>]+>\s*([0-9][0-9,.]*\s*[KMGTPE]?i?B)',
    ]

    for pattern in patterns:
        m = re.search(pattern, raw, flags=re.I)
        if m:
            display = re.sub(r"\s+", " ", m.group(1)).strip()
            value = parse_size_bytes(display)
            if value is not None:
                return display, value

    text_only = clean_text(raw)
    m = re.search(
        r"(?:上传量|上傳量)\s*[:：]?\s*([0-9][0-9,.]*\s*[KMGTPE]?i?B)",
        text_only,
        flags=re.I,
    )
    if m:
        display = re.sub(r"\s+", " ", m.group(1)).strip()
        value = parse_size_bytes(display)
        if value is not None:
            return display, value

    return None, None


def parse_uploaded_bytes(html: str) -> Optional[float]:
    raw = html or ""

    row_patterns = [
        r'<td[^>]*class=["\'][^"\']*rowhead[^"\']*["\'][^>]*>\s*'
        r'(?:上传量|上傳量|Uploaded)\s*</td>\s*'
        r'<td[^>]*>([\s\S]*?)</td>',
        r'<td[^>]*>\s*(?:上传量|上傳量|Uploaded)\s*</td>\s*'
        r'<td[^>]*>([\s\S]*?)</td>',
    ]

    for pattern in row_patterns:
        m = re.search(pattern, raw, flags=re.I)
        if m:
            cell = clean_text(m.group(1))
            value = parse_size_bytes(cell)
            if value is not None:
                return value

    text = clean_text(raw)

    direct_patterns = [
        r"(?:上传量|上傳量|Uploaded)\s*[:：]?\s*([0-9][0-9,.]*\s*[KMGTPE]?i?B)",
    ]
    for pattern in direct_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            value = parse_size_bytes(m.group(1))
            if value is not None:
                return value

    return None


def get_uploaded_info(
    session: requests.Session,
    home_html: str,
):
    display, value = parse_homepage_uploaded(home_html)
    if value is not None:
        return display, value

    uid = parse_user_id(home_html)
    if uid is None:
        return None, None

    try:
        resp = get(
            session,
            f"/userdetails.php?id={uid}",
            referer=BASE_URL + "/",
        )
        if resp.status_code != 200:
            return None, None

        body = resp.text or ""
        page_text = clean_text(body)

        if "login.php" in (resp.url or "").lower():
            return None, None

        if detect_verification(page_text, resp.url):
            return None, None

        value = parse_uploaded_bytes(body)
        if value is not None:
            return human_size(value), value
    except Exception:
        pass

    return None, None


def wait_uploaded_change(
    session: requests.Session,
    before_uploaded: Optional[float],
    attempts: int = 4,
    delay_seconds: float = 2.0,
):
    latest_display = None
    latest_value = before_uploaded

    for _ in range(attempts):
        time.sleep(delay_seconds)

        try:
            home_resp = get(session, "/")
            home_html = home_resp.text or ""
            display, current = get_uploaded_info(session, home_html)
        except Exception:
            display, current = None, None

        if current is None:
            continue

        latest_display = display
        latest_value = current

        if before_uploaded is None or current > before_uploaded:
            return latest_display, latest_value

    return latest_display, latest_value


def homepage_already_signed(html: str) -> bool:
    text = clean_text(html)
    return bool(re.search(
        r"签到已得\s*[0-9,.]+|簽到已得\s*[0-9,.]+|"
        r"Attend got\s*[:：]?\s*[0-9,.]+|"
        r"今日已签到|今日已簽到|今天已经签到|今天已經簽到|"
        r"已经签到|已經簽到|已签到|已簽到|Showed\s*Up",
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

    full_patterns = [
        (
            r"这是您的第\s*(\d+)\s*次签到[,，]?\s*"
            r"已连续签到\s*(\d+)\s*天[,，]?\s*"
            r"本次签到获得\s*([0-9,.]+)\s*个?(?:魔力值|魔力|Bonus)",
            1, 2, 3,
        ),
        (
            r"這是您的第\s*(\d+)\s*次簽到[,，]?\s*"
            r"已連續簽到\s*(\d+)\s*天[,，]?\s*"
            r"本次簽到獲得\s*([0-9,.]+)\s*個?(?:魔力值|魔力|Bonus)",
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
        r"签到已得\s*([0-9,.]+)",
        r"簽到已得\s*([0-9,.]+)",
        r"Attend got\s*[:：]?\s*([0-9,.]+)",
        r"本次签到获得\s*([0-9,.]+)\s*个?(?:魔力值|魔力|Bonus)",
        r"本次簽到獲得\s*([0-9,.]+)\s*個?(?:魔力值|魔力|Bonus)",
        r"签到获得\s*([0-9,.]+)\s*个?(?:魔力值|魔力|Bonus)",
        r"(?:魔力值?|Bonus)\s*[+＋]\s*([0-9,.]+)",
    ]
    for pattern in reward_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            result["reward"] = number_from_string(m.group(1))
            result["success"] = True
            result["message"] = m.group(0)
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
    print("========== QingWa 青蛙 ==========\n")

    if not COOKIE:
        print("❌ 未配置环境变量 QINGWA_COOKIE")
        return 1

    session = make_session()

    try:
        home_resp = get(session, "/")
        home_resp.raise_for_status()
        home_html = home_resp.text or ""
    except Exception as e:
        print(f"❌ 无法安全访问 QingWa 首页：{e}")
        return 1

    home_text = clean_text(home_html)

    verification = detect_verification(home_text, home_resp.url)
    if verification:
        print(f"❌ 检测到{verification}")
        print("   脚本不会尝试绕过，请先在浏览器中人工处理。")
        return 1

    if not login_is_valid(session, home_html, home_resp.url):
        print("❌ 未能确认登录状态（并不等同于 Cookie 一定失效）")
        print(f"   当前地址：{home_resp.url}")
        print("   请把这段日志发我，不需要提供 Cookie。")
        return 1

    username = parse_username(home_html) or "未获取"
    uid = parse_user_id(home_html)
    before_bonus = get_bonus_balance(session, home_html)
    before_uploaded_display, before_uploaded = get_uploaded_info(session, home_html)
    home_signed = homepage_already_signed(home_html)

    print("✅ Cookie 登录有效")
    print(f"👤 用户：{username}")
    if uid is not None:
        print(f"🆔 UID：{uid}")
    if before_bonus is not None:
        print(f"💰 当前魔力：{fmt_number(before_bonus)}")
    if before_uploaded is not None:
        print(f"⬆️ 当前上传量：{before_uploaded_display or human_size(before_uploaded)}")

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
            r"该页面必须在登录后才能访问|該頁面必須在登錄後才能訪問|"
            r"请先登录|請先登錄|登录后才能访问|登錄後才能訪問|"
            r"you must be logged in|please log in",
            att_text,
            flags=re.I,
        )
    ):
        print("❌ 签到页面提示登录失效，请重新获取 QINGWA_COOKIE")
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

    if reward is not None and not parsed["already"]:
        print(f"🎁 本次签到：{fmt_number(reward)} 魔力")
    elif not (parsed["already"] or home_signed):
        print("🎁 本次签到：未获取")

    if not (parsed["already"] or home_signed):
        time.sleep(1.0)

    print("\n🐸 请求额外上传量...")

    shout_status = send_upload_request(session, uid)

    if shout_status == "sent":
        after_uploaded_display, after_uploaded = wait_uploaded_change(session, before_uploaded)

        if after_uploaded is not None:
            print(f"⬆️ 获取后上传量：{after_uploaded_display or human_size(after_uploaded)}")

            if (
                before_uploaded is not None
                and after_uploaded > before_uploaded
            ):
                delta = after_uploaded - before_uploaded
                print(f"🎁 本次增加上传量：+{human_size(delta)}")
            elif before_uploaded is not None:
                print("ℹ️ 上传量暂未变化，可能存在站点结算延迟")
        else:
            print("⬆️ 获取后上传量：未获取")

    try:
        after_resp = get(session, "/")
        after_home = after_resp.text or ""
        after_bonus = get_bonus_balance(session, after_home)
    except Exception:
        after_bonus = before_bonus

    if after_bonus is not None:
        print(f"📊 当前魔力：{fmt_number(after_bonus)}")
    elif before_bonus is not None:
        print(f"📊 当前魔力：{fmt_number(before_bonus)}")
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
