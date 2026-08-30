#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# cron: 7 9 * * *
# new Env("MomentPT 签到")

"""
MomentPT 青龙独立签到脚本

环境变量：
  MOMENT_COOKIE    必填，MomentPT 完整 Cookie
  MOMENT_BASE_URL  可选，默认 https://www.momentpt.top

依赖：
  requests

功能：
  - 检查 Cookie 登录状态
  - 获取用户名与 UID
  - 读取当前魔力值、上传量、下载量
  - 使用 /attendance.php 完成或确认每日签到
  - 解析今日签到奖励与补签卡
  - 每天自动向喊话框依次发送：
      1. 茄子
      2. 保一条
    两条之间随机等待 4~5 秒
  - 按 UID + 日期 + 每条消息分别记录状态，避免重复发送
  - 遇到 2FA、验证码、人机验证或风控时停止，不尝试绕过
"""

import json
import os
import random
import re
import time
from datetime import datetime
from html import unescape
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse

import requests


COOKIE = os.getenv("MOMENT_COOKIE", "").strip()
BASE_URL = os.getenv("MOMENT_BASE_URL", "https://www.momentpt.top").strip().rstrip("/")

TIMEOUT = 20
SHOUT_MESSAGES = ["茄子", "保一条"]
STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".moment_state")

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
    if not base_host:
        return False
    return host == base_host or host.endswith("." + base_host)


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        "Connection": "keep-alive",
    })

    host = urlparse(BASE_URL).hostname or ""
    for key, value in cookie_dict(COOKIE).items():
        session.cookies.set(key, value, domain=host, path="/")

    return session


def safe_get(
    session: requests.Session,
    path: str,
    *,
    params=None,
    referer: Optional[str] = None,
) -> requests.Response:
    url = urljoin(BASE_URL + "/", path.lstrip("/"))

    resp = session.get(
        url,
        params=params,
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

    has_user = bool(re.search(r'<input[^>]+name=["\']username["\']', raw, flags=re.I))
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
        r"logout\.php|usercp\.php|userdetails\.php\?id=\d+|attendance\.php|"
        r"欢迎回来|歡迎回來|控制面板|收藏",
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


def parse_moment_bonus(html: str) -> Optional[float]:
    """
    截图已确认：
      <font class="color_bonus">魔力值</font>
      [<a href="mybonus.php">使用</a>]
      2,395,492.0
    """
    raw = html or ""

    # 最稳锚点：mybonus.php 使用链接后的第一个数字
    m = re.search(
        r'<a[^>]+href=["\'][^"\']*mybonus\.php[^"\']*["\'][^>]*>'
        r'[\s\S]*?</a>[\s\]\)】）:：&nbsp;]{0,120}'
        r'([0-9][0-9,.]*)',
        raw,
        flags=re.I,
    )
    if m:
        return number_from_string(m.group(1))

    return None


def parse_labeled_size(html: str, labels) -> Optional[str]:
    raw = html or ""
    label_alt = "|".join(re.escape(x) for x in labels)

    for pattern in [
        rf'<font[^>]*>\s*(?:{label_alt})\s*[:：]?\s*</font>\s*'
        rf'([0-9][0-9,.]*\s*[KMGTPE]?i?B)',
        rf'(?:{label_alt})\s*[:：]\s*([0-9][0-9,.]*\s*[KMGTPE]?i?B)',
    ]:
        m = re.search(pattern, raw, flags=re.I)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()

    text = clean_text(raw)
    m = re.search(
        rf'(?:{label_alt})\s*[:：]?\s*([0-9][0-9,.]*\s*[KMGTPE]?i?B)',
        text,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


def parse_home_attendance(html: str) -> Dict[str, object]:
    result: Dict[str, object] = {
        "already": False,
        "reward": None,
        "makeup_cards": None,
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
    result["text"] = text

    if re.search(r"签到已得|簽到已得|今日已签到|今日已簽到|已签到|已簽到", text, flags=re.I):
        result["already"] = True

    m_reward = re.search(r"(?:签到已得|簽到已得|已得)\s*([0-9][0-9,.]*)", text, flags=re.I)
    if m_reward:
        result["reward"] = number_from_string(m_reward.group(1))

    m_card = re.search(r"(?:补签卡|補簽卡)\s*[:：]?\s*(\d+)", text, flags=re.I)
    if m_card:
        result["makeup_cards"] = int(m_card.group(1))

    return result


def parse_attendance_page(html: str) -> Dict[str, object]:
    text = clean_text(html)
    result: Dict[str, object] = {
        "success": False,
        "already": False,
        "reward": None,
        "makeup_cards": None,
    }

    if re.search(r"签到成功|簽到成功|签到已得\s*[0-9,.]+|簽到已得\s*[0-9,.]+", text, flags=re.I):
        result["success"] = True

    if re.search(
        r"今天已经签到|今天已經簽到|今日已签到|今日已簽到|"
        r"已经签到过|已經簽到過|请勿重复签到|請勿重複簽到",
        text,
        flags=re.I,
    ):
        result["success"] = True
        result["already"] = True

    m_reward = re.search(
        r"(?:签到已得|簽到已得|本次签到(?:获得|得到)?|本次簽到(?:獲得|得到)?)"
        r"\s*([0-9][0-9,.]*)",
        text,
        flags=re.I,
    )
    if m_reward:
        result["reward"] = number_from_string(m_reward.group(1))
        result["success"] = True

    m_card = re.search(r"(?:补签卡|補簽卡)\s*[:：]?\s*(\d+)", text, flags=re.I)
    if m_card:
        result["makeup_cards"] = int(m_card.group(1))

    return result


def state_path(uid: Optional[int]) -> str:
    os.makedirs(STATE_DIR, exist_ok=True)
    return os.path.join(STATE_DIR, f"shout_{uid if uid is not None else 'unknown'}.json")


def load_state(uid: Optional[int]) -> Dict[str, object]:
    today = datetime.now().strftime("%Y-%m-%d")
    path = state_path(uid)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    if data.get("date") != today:
        return {"date": today, "sent": []}

    sent = data.get("sent")
    if not isinstance(sent, list):
        sent = []

    return {"date": today, "sent": sent}


def save_state(uid: Optional[int], state: Dict[str, object]) -> None:
    with open(state_path(uid), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def shoutbox_endpoint_available(session: requests.Session) -> bool:
    """
    Moment 首页中的喊话框可能由父页面或 JS 动态挂载，
    因此不能要求 shoutbox.php 的原始 HTML 一定包含完整 form。

    这里只确认 shoutbox.php 可访问、没有登录失效/验证挑战。
    """
    for path in (
        "/shoutbox.php",
        "/shoutbox.php?type=shoutbox",
    ):
        try:
            resp = safe_get(
                session,
                path,
                referer=BASE_URL + "/",
            )
        except Exception:
            continue

        if resp.status_code != 200:
            continue

        body = resp.text or ""
        text = clean_text(body)

        if page_is_login_page(body, resp.url):
            continue

        if detect_verification(text, resp.url):
            continue

        return True

    return False


def strip_shout_input_area(html: str) -> str:
    """
    移除喊话输入表单、input/textarea/button 等区域，
    防止提交失败时 shbox_text 被回显在输入框里而误判成功。
    """
    raw = html or ""

    raw = re.sub(
        r"<form\b[^>]*>[\s\S]*?</form>",
        " ",
        raw,
        flags=re.I,
    )
    raw = re.sub(
        r"<textarea\b[^>]*>[\s\S]*?</textarea>",
        " ",
        raw,
        flags=re.I,
    )
    raw = re.sub(
        r"<input\b[^>]*>",
        " ",
        raw,
        flags=re.I,
    )
    raw = re.sub(
        r"<button\b[^>]*>[\s\S]*?</button>",
        " ",
        raw,
        flags=re.I,
    )

    return raw


def shout_history_contains_message(
    session: requests.Session,
    message: str,
) -> bool:
    """
    只在“去掉输入表单后的页面内容”里确认消息，
    避免把输入框 value / 回显参数误认为已进入聊天记录。
    """
    for path in (
        "/shoutbox.php?type=shoutbox",
        "/shoutbox.php",
        "/",
    ):
        try:
            resp = safe_get(
                session,
                path,
                referer=BASE_URL + "/",
            )
        except Exception:
            continue

        if resp.status_code != 200:
            continue

        history_html = strip_shout_input_area(resp.text or "")
        history_text = clean_text(history_html)

        if message in history_text:
            return True

    return False


def send_shout(session: requests.Session, message: str) -> bool:
    """
    NexusPHP 标准喊话提交核心参数：
      GET /shoutbox.php
      shbox_text=<消息>
      sent=yes

    type=shoutbox 作为兼容参数一并提交。
    发送后重新读取喊话内容确认，确认成功后才记录每日状态。
    """
    params = {
        "shbox_text": message,
        "sent": "yes",
        "type": "shoutbox",
    }

    try:
        resp = safe_get(
            session,
            "/shoutbox.php",
            params=params,
            referer=BASE_URL + "/",
        )
    except Exception as e:
        print(f"❌ 群聊发送失败：{e}")
        return False

    body = resp.text or ""
    page_text = clean_text(body)

    verification = detect_verification(page_text, resp.url)
    if verification:
        print(f"❌ 群聊触发{verification}")
        return False

    if page_is_login_page(body, resp.url):
        print("❌ 群聊页面提示登录失效")
        return False

    if resp.status_code != 200:
        print(f"❌ 群聊 HTTP {resp.status_code}")
        return False

    if re.search(
        r"发送失败|發送失敗|禁止发言|禁止發言|没有权限|沒有權限|"
        r"permission denied|forbidden",
        page_text,
        flags=re.I,
    ):
        print(f"❌ 群聊返回异常：{page_text[:300]}")
        return False

    # 页面有时不会在提交响应中立即带回消息，稍等后再检查。
    time.sleep(1.0)

    confirmed = False
    for _ in range(3):
        if shout_history_contains_message(session, message):
            confirmed = True
            break
        time.sleep(1.0)

    if confirmed:
        print(f"💬 发送：{message}")
        print("✅ 群聊消息发送成功")
        return True

    print(f"❌ 未能确认“{message}”真正进入喊话记录")
    print("   可能是站点限速或消息未提交成功；本次不会记录为已发送。")
    return False


def run_daily_shouts(session: requests.Session, uid: Optional[int]) -> None:
    print("\n🎞️ Moment 每日喊话...")

    if not shoutbox_endpoint_available(session):
        print("❌ Moment 喊话接口不可访问，未发送任何消息")
        return

    state = load_state(uid)
    sent = set(state.get("sent", []))

    for index, message in enumerate(SHOUT_MESSAGES):
        if message in sent:
            print(f"⏭️ 今日已发送“{message}”，跳过")
            continue

        # 若第一条刚发成功，第二条随机等待 4~5 秒。
        if index > 0 and SHOUT_MESSAGES[index - 1] in sent:
            delay = random.uniform(4.0, 5.0)
            print(f"⏳ 等待 {delay:.1f} 秒后发送下一条...")
            time.sleep(delay)

        if send_shout(session, message):
            sent.add(message)
            state["sent"] = list(sent)
            save_state(uid, state)
        else:
            # 当前一条失败时停止，避免继续刷后续内容。
            break


def main() -> int:
    print("========== MomentPT ==========\n")

    if not COOKIE:
        print("❌ 未配置环境变量 MOMENT_COOKIE")
        return 1

    session = make_session()

    try:
        home_resp = safe_get(session, "/")
        home_resp.raise_for_status()
        home_html = home_resp.text or ""
    except Exception as e:
        print(f"❌ 无法访问 MomentPT 首页：{e}")
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
    bonus = parse_moment_bonus(home_html)
    uploaded = parse_labeled_size(home_html, ["上传量", "上傳量", "Uploaded"])
    downloaded = parse_labeled_size(home_html, ["下载量", "下載量", "Downloaded"])
    home_att = parse_home_attendance(home_html)

    print("✅ Cookie 登录有效")
    print(f"👤 用户：{username}")
    if uid is not None:
        print(f"🆔 UID：{uid}")

    print(f"💰 当前魔力：{fmt_number(bonus)}")
    print(f"⬆️ 上传量：{uploaded or '未获取'}")
    print(f"⬇️ 下载量：{downloaded or '未获取'}")

    if home_att["already"]:
        print("📅 今日状态：已签到")
        print("⚠️ 今日已经签到，无需重复执行")
    else:
        print("📅 今日状态：未签到或首页未明确显示")
        print("🎯 开始签到...")

        try:
            att_resp = safe_get(session, "/attendance.php", referer=BASE_URL + "/")
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
        if not parsed["success"]:
            returned = parse_home_attendance(att_html)
            if returned["already"]:
                parsed["success"] = True
                parsed["already"] = True
                parsed["reward"] = returned["reward"]
                parsed["makeup_cards"] = returned["makeup_cards"]

        if not parsed["success"]:
            print("❌ 未能确认签到成功")
            print(f"   页面返回：{clean_text(att_html)[:500]}")
            return 1

        print("⚠️ 今日已经签到，无需重复执行" if parsed["already"] else "✅ 签到成功")
        home_att["reward"] = parsed["reward"]
        home_att["makeup_cards"] = parsed["makeup_cards"]

    if home_att["reward"] is not None:
        print(f"🎁 今日签到：{fmt_number(home_att['reward'])} 魔力")
    else:
        print("🎁 今日签到：未获取")

    if home_att["makeup_cards"] is not None:
        print(f"🎫 补签卡：{home_att['makeup_cards']}")
    else:
        print("🎫 补签卡：未获取")

    run_daily_shouts(session, uid)

    # 两条喊话后重读一次魔力，便于观察是否有奖励变化。
    try:
        after_resp = safe_get(session, "/")
        after_html = after_resp.text or ""
        after_bonus = parse_moment_bonus(after_html)

        if after_bonus is not None:
            print(f"\n📊 当前魔力：{fmt_number(after_bonus)}")
            if bonus is not None and after_bonus != bonus:
                delta = after_bonus - bonus
                sign = "+" if delta > 0 else ""
                print(f"🎁 魔力变化：{sign}{fmt_number(delta)}")
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
