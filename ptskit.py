#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# cron: 59 8 * * *
# new Env("PTSKIT 拾刻签到")

"""
PTSKIT / 拾刻 青龙独立签到脚本

环境变量：
  PTSKIT_COOKIE    必填，PTSKIT 完整 Cookie
  PTSKIT_BASE_URL  可选，默认 https://www.ptskit.com

依赖：
  requests

功能：
  - 检查 Cookie 登录状态
  - 获取用户名与 UID
  - 从首页精确读取魔力值
  - 从首页精确读取上传量 / 下载量
  - 从首页精确读取做种积分
  - 检查今日签到状态
  - 使用 /attendance.php 执行或确认每日签到
  - 解析今日签到奖励与补签卡数量
  - 尝试解析累计签到次数 / 连续签到天数
  - 遇到 2FA、验证码、人机验证或风控时停止，不尝试绕过

说明：
  无法确认的数据会显示“未获取”，不会自行猜测。
"""

import os
import re
from html import unescape
from typing import Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests


COOKIE = os.getenv("PTSKIT_COOKIE", "").strip()
BASE_URL = os.getenv("PTSKIT_BASE_URL", "https://www.ptskit.com").strip().rstrip("/")

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
        "Upgrade-Insecure-Requests": "1",
    })

    # Cookie 绑定到当前 PTSKIT 主域，避免跨域跳转时被带到无关站点。
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

    # 仅允许站内跳转
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
        r"just a moment|checking your browser|"
        r"滑块验证|滑塊驗證|安全校验|安全驗證",
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

    raw = html or ""
    return bool(re.search(
        r"logout\.php|usercp\.php|userdetails\.php\?id=\d+|attendance\.php|"
        r"欢迎回来|歡迎回來|控制面板|收藏",
        raw,
        flags=re.I,
    ))


def parse_username(html: str) -> Optional[str]:
    raw = html or ""
    text = clean_text(raw)

    patterns = [
        r"欢迎回来[,，]?\s*([^\s\[\]，,]+)",
        r"歡迎回來[,，]?\s*([^\s\[\]，,]+)",
        r"([^\s\[\]，,]+)\s*\[退出\]",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            name = m.group(1).strip()
            if name:
                return name

    # 优先找欢迎栏中的 userdetails 链接
    m = re.search(
        r'<a[^>]+href=["\'][^"\']*userdetails\.php\?id=\d+[^"\']*["\'][^>]*>'
        r'([\s\S]*?)</a>',
        raw,
        flags=re.I,
    )
    if m:
        name = clean_text(m.group(1))
        if name:
            return name

    return None


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



def parse_ptskit_bonus(html: str) -> Optional[float]:
    """
    PTSKIT 首页魔力结构以 mybonus.php 的“使用”链接为最稳锚点：

      <font class="color_bonus">魔力值</font>
      [<a href="mybonus.php">使用</a>]
      367,621.3

    优先从 mybonus.php 链接后读取第一个数字；
    再回退到 color_bonus + 魔力值附近读取。
    全程只在局部片段内解析，避免误抓公告/活动数字。
    """
    raw = html or ""

    # 方案 1：最强锚点 —— “使用”链接后面的第一个数字就是余额。
    patterns = [
        r'<a[^>]+href=["\'][^"\']*mybonus\.php[^"\']*["\'][^>]*>'
        r'[\s\S]*?</a>'
        r'[\s\]\)】）:：&nbsp;]{0,120}'
        r'([0-9][0-9,.]*)',

        # 有些主题可能在链接结束后夹少量其它标签。
        r'<a[^>]+href=["\'][^"\']*mybonus\.php[^"\']*["\'][^>]*>'
        r'[\s\S]*?</a>'
        r'([\s\S]{0,180}?)'
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

    # 方案 2：后备 —— 只截取“魔力值”节点到 attendance.php 之前的小片段。
    m = re.search(
        r'<font[^>]+class=["\'][^"\']*color_bonus[^"\']*["\'][^>]*>'
        r'[\s\S]*?(?:魔力值|魔力)[\s\S]*?</font>'
        r'([\s\S]{0,400}?)'
        r'(?=<a[^>]+href=["\'][^"\']*attendance\.php|<font\b|</td>|$)',
        raw,
        flags=re.I,
    )
    if m:
        local = m.group(1)

        # 如果局部中有 mybonus.php，优先取它后面的数字。
        mm = re.search(
            r'mybonus\.php[\s\S]*?</a>[\s\S]{0,120}?([0-9][0-9,.]*)',
            local,
            flags=re.I,
        )
        if mm:
            value = number_from_string(mm.group(1))
            if value is not None:
                return value

        local_text = clean_text(local)
        nums = re.findall(r'(?<!\d)([0-9][0-9,.]*)(?!\d)', local_text)
        for raw_num in nums:
            value = number_from_string(raw_num)
            if value is not None:
                return value

    return None


def parse_labeled_number(html: str, labels) -> Optional[float]:
    """
    精确匹配类似：
      <font class="color_bonus">魔力值</font> 367,621.3
      <font class="color_bonus">做种积分</font> 149,087
    """
    raw = html or ""
    label_alt = "|".join(re.escape(x) for x in labels)

    patterns = [
        rf'<font[^>]*>\s*(?:{label_alt})\s*[:：]?\s*</font>\s*([0-9][0-9,.]*)',
        rf'(?:{label_alt})\s*[:：]\s*([0-9][0-9,.]*)',
    ]

    for pattern in patterns:
        m = re.search(pattern, raw, flags=re.I)
        if m:
            value = number_from_string(m.group(1))
            if value is not None:
                return value

    text = clean_text(raw)
    m = re.search(
        rf'(?:{label_alt})\s*[:：]?\s*([0-9][0-9,.]*)',
        text,
        flags=re.I,
    )
    if m:
        return number_from_string(m.group(1))

    return None


def parse_labeled_size(html: str, labels) -> Optional[str]:
    """
    原样读取站点容量文本，不自行换算。
    例如：
      上传量: 60.485 TB
      下载量: 1.116 TB
    """
    raw = html or ""
    label_alt = "|".join(re.escape(x) for x in labels)

    patterns = [
        rf'<font[^>]*>\s*(?:{label_alt})\s*[:：]?\s*</font>\s*'
        rf'([0-9][0-9,.]*\s*[KMGTPE]?i?B)',
        rf'(?:{label_alt})\s*[:：]\s*([0-9][0-9,.]*\s*[KMGTPE]?i?B)',
    ]

    for pattern in patterns:
        m = re.search(pattern, raw, flags=re.I)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()

    text = clean_text(raw)
    m = re.search(
        rf'(?:{label_alt})\s*[:：]?\s*([0-9][0-9,.]*\s*[KMGTPE]?i?B)',
        text,
        flags=re.I,
    )
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()

    return None


def parse_home_stats(html: str) -> Dict[str, object]:
    return {
        "bonus": parse_ptskit_bonus(html),
        "uploaded": parse_labeled_size(html, ["上传量", "上傳量", "Uploaded"]),
        "downloaded": parse_labeled_size(html, ["下载量", "下載量", "Downloaded"]),
        "seed_points": parse_labeled_number(html, ["做种积分", "做種積分", "Seed Points"]),
    }


def parse_home_attendance(html: str) -> Dict[str, object]:
    """
    截图已确认首页存在：
      <a href="attendance.php">签到已得10, 补签卡20</a>
    """
    raw = html or ""

    result: Dict[str, object] = {
        "already": False,
        "reward": None,
        "makeup_cards": None,
        "text": "",
    }

    m = re.search(
        r'<a[^>]+href=["\'][^"\']*attendance\.php[^"\']*["\'][^>]*>'
        r'([\s\S]*?)</a>',
        raw,
        flags=re.I,
    )
    if not m:
        return result

    text = clean_text(m.group(1))
    result["text"] = text

    if re.search(r"签到已得|簽到已得|今日已签到|今日已簽到|已签到|已簽到", text, flags=re.I):
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

    card_patterns = [
        r"补签卡\s*[:：]?\s*(\d+)",
        r"補簽卡\s*[:：]?\s*(\d+)",
    ]
    for pattern in card_patterns:
        cm = re.search(pattern, text, flags=re.I)
        if cm:
            result["makeup_cards"] = int(cm.group(1))
            break

    return result


def parse_attendance_page(html: str) -> Dict[str, object]:
    text = clean_text(html)

    result: Dict[str, object] = {
        "success": False,
        "already": False,
        "reward": None,
        "makeup_cards": None,
        "total_times": None,
        "streak_days": None,
        "message": "",
    }

    # 已签到 / 签到成功
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
        r"本次签到(?:获得|得到)?\s*([0-9][0-9,.]*)",
        r"本次簽到(?:獲得|得到)?\s*([0-9][0-9,.]*)",
        r"奖励\s*[:：]?\s*([0-9][0-9,.]*)\s*(?:魔力|魔力值)?",
        r"獎勵\s*[:：]?\s*([0-9][0-9,.]*)\s*(?:魔力|魔力值)?",
    ]
    for pattern in reward_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            result["reward"] = number_from_string(m.group(1))
            result["success"] = True
            break

    card_patterns = [
        r"补签卡\s*[:：]?\s*(\d+)",
        r"補簽卡\s*[:：]?\s*(\d+)",
    ]
    for pattern in card_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            result["makeup_cards"] = int(m.group(1))
            break

    total_patterns = [
        r"第\s*(\d+)\s*次签到",
        r"第\s*(\d+)\s*次簽到",
        r"累计签到\s*[:：]?\s*(\d+)",
        r"累計簽到\s*[:：]?\s*(\d+)",
    ]
    for pattern in total_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            result["total_times"] = int(m.group(1))
            break

    streak_patterns = [
        r"连续签到\s*[:：]?\s*(\d+)\s*天",
        r"連續簽到\s*[:：]?\s*(\d+)\s*天",
        r"已连续签到\s*(\d+)\s*天",
        r"已連續簽到\s*(\d+)\s*天",
    ]
    for pattern in streak_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            result["streak_days"] = int(m.group(1))
            break

    # 保存简短可读返回
    for pattern in [
        r"[^。！!]{0,60}(?:签到成功|簽到成功)[^。！!]{0,100}",
        r"[^。！!]{0,60}(?:请勿重复签到|請勿重複簽到)[^。！!]{0,100}",
    ]:
        m = re.search(pattern, text, flags=re.I)
        if m:
            result["message"] = m.group(0).strip()
            break

    return result


def main() -> int:
    print("========== PTSKIT 拾刻 ==========\n")

    if not COOKIE:
        print("❌ 未配置环境变量 PTSKIT_COOKIE")
        return 1

    session = make_session()

    try:
        home_resp = safe_get(session, "/")
        home_resp.raise_for_status()
        home_html = home_resp.text or ""
    except Exception as e:
        print(f"❌ 无法访问 PTSKIT 首页：{e}")
        return 1

    verification = detect_verification(clean_text(home_html), home_resp.url)
    if verification:
        print(f"❌ 检测到{verification}")
        print("   脚本不会尝试绕过，请先在浏览器中人工处理。")
        return 1

    if not login_is_valid(home_html, home_resp.url):
        print("❌ 未能确认 Cookie 登录状态")
        print(f"   当前地址：{home_resp.url}")
        return 1

    username = parse_username(home_html) or "未获取"
    uid = parse_user_id(home_html)
    stats = parse_home_stats(home_html)
    home_att = parse_home_attendance(home_html)

    print("✅ Cookie 登录有效")
    print(f"👤 用户：{username}")
    if uid is not None:
        print(f"🆔 UID：{uid}")

    if stats["bonus"] is not None:
        print(f"💰 当前魔力：{fmt_number(stats['bonus'])}")
    else:
        print("💰 当前魔力：未获取")

    if stats["uploaded"]:
        print(f"⬆️ 上传量：{stats['uploaded']}")
    else:
        print("⬆️ 上传量：未获取")

    if stats["downloaded"]:
        print(f"⬇️ 下载量：{stats['downloaded']}")
    else:
        print("⬇️ 下载量：未获取")

    if stats["seed_points"] is not None:
        print(f"🌱 做种积分：{fmt_number(stats['seed_points'])}")
    else:
        print("🌱 做种积分：未获取")

    if home_att["already"]:
        print("📅 今日状态：已签到")
        print("⚠️ 今日已经签到，无需重复执行")

        if home_att["reward"] is not None:
            print(f"🎁 今日签到：{fmt_number(home_att['reward'])} 魔力")
        else:
            print("🎁 今日签到：未获取")

        if home_att["makeup_cards"] is not None:
            print(f"🎫 补签卡：{home_att['makeup_cards']}")
        else:
            print("🎫 补签卡：未获取")

        print("\n执行完成 ✅")
        return 0

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
        print("   脚本不会尝试绕过，请人工处理。")
        return 1

    if page_is_login_page(att_html, att_resp.url):
        print("❌ 签到页面提示登录失效，请重新获取 PTSKIT_COOKIE")
        return 1

    parsed = parse_attendance_page(att_html)

    # 签到页可能跳回首页，因此再从返回页面尝试读首页签到文字
    if not parsed["success"]:
        returned_home_att = parse_home_attendance(att_html)
        if returned_home_att["already"]:
            parsed["success"] = True
            parsed["already"] = True
            parsed["reward"] = returned_home_att["reward"]
            parsed["makeup_cards"] = returned_home_att["makeup_cards"]

    if not parsed["success"]:
        print("❌ 未能确认签到成功")
        page_text = clean_text(att_html)
        if page_text:
            print(f"   页面返回：{page_text[:500]}")
        return 1

    if parsed["already"]:
        print("⚠️ 今日已经签到，无需重复执行")
    else:
        print("✅ 签到成功")

    if parsed["total_times"] is not None:
        print(f"📆 累计签到：{parsed['total_times']} 次")
    else:
        print("📆 累计签到：未获取")

    if parsed["streak_days"] is not None:
        print(f"🔥 连续签到：{parsed['streak_days']} 天")
    else:
        print("🔥 连续签到：未获取")

    if parsed["reward"] is not None:
        print(f"🎁 今日签到：{fmt_number(parsed['reward'])} 魔力")
    else:
        print("🎁 今日签到：未获取")

    if parsed["makeup_cards"] is not None:
        print(f"🎫 补签卡：{parsed['makeup_cards']}")
    else:
        print("🎫 补签卡：未获取")

    # 签到后重新读取首页账户数据
    try:
        after_resp = safe_get(session, "/")
        after_html = after_resp.text or ""
        after_stats = parse_home_stats(after_html)

        if after_stats["bonus"] is not None:
            print(f"📊 当前魔力：{fmt_number(after_stats['bonus'])}")
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
